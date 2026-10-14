"""Resumable OpenAI Batch judging with bounded per-item attempts."""
import asyncio
import json
from pathlib import Path
import time

import httpx

from judging import judge_payload, judging_fingerprint, make_record, parse_reply, response_scores, saved_tasks
from pipeline_common import digest, retry_async, write_checkpoint


def save_state(path, state):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


async def upload_file(client, path):
    client.logger.info("Uploading batch request file %s", path)
    try:
        with path.open("rb") as handle:
            response = await client.http.post(client.base_url + "/files",
                data={"purpose": "batch"}, files={"file": (path.name, handle, "application/jsonl")})
        response.raise_for_status()
        return response.json()["id"]
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        raise RuntimeError("Batch file upload failed; credentials remain in environment headers") from exc


async def file_content(client, file_id):
    client.logger.info("Downloading batch result file %s", file_id)
    async def fetch():
        try:
            response = await client.http.get(client.base_url + f"/files/{file_id}/content")
            response.raise_for_status()
            return response.text
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise RuntimeError("Batch result download failed") from exc
    text, _ = await retry_async(fetch, client.retries, client.logger, "Downloading batch result")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


async def run_batch(client, tasks, role, config, model, sampling, output, retry,
                    action, poll_interval, wait_timeout, logger):
    fingerprint = judging_fingerprint(tasks, role, config, model, sampling, client.base_url)
    state_path = output.with_suffix(".batch_state.json")
    errors_path = output.with_suffix(".errors.jsonl")
    if any(p.exists() for p in (state_path, output, errors_path)) and not retry:
        raise FileExistsError("Batch artifacts exist; use --retry or select a new --output-file")
    if action in {"collect", "collect-only"} and not state_path.exists():
        raise FileNotFoundError("No batch state to collect; submit or run the batch first")
    state = json.loads(state_path.read_text()) if state_path.exists() else {
        "run_fingerprint": fingerprint, "attempts": {}, "active_batch": None, "batches": []}
    if state.get("run_fingerprint") != fingerprint:
        raise ValueError("Batch retry input/config mismatch")
    if state.get("submission_in_progress") and not state.get("active_batch"):
        raise RuntimeError("A batch submission has an uncertain result. Check OpenAI batch metadata before resubmitting this state")
    output.parent.mkdir(parents=True, exist_ok=True)
    saved, completed = saved_tasks(output, tasks, fingerprint, retry)
    task_hashes = [digest(task) for task in tasks]
    if state.get("active_batch") and state.get("task_hashes") != task_hashes:
        raise ValueError("Batch inputs changed while a job is pending; collect using the original inputs")
    state["task_hashes"] = task_hashes
    # A fresh explicit retry grants ERROR/unprocessed items a new bounded cycle.
    # Collecting an active job retains its current five-attempt budget.
    if not state.get("active_batch"):
        state["attempts"] = {}
    state.setdefault("totals", {})
    for position, record in saved.items():
        info = record["judging"]
        state["totals"][str(position)] = max(state["totals"].get(str(position), 0),
                                            info.get("total_attempts", info.get("attempts", 0)))
    max_attempts = client.retries + 1
    started = time.monotonic()

    unjudgable = set()
    for position, task in enumerate(tasks):
        if position not in completed and task.get("skip_reason"):
            record = make_record(task, position, role, model, fingerprint)
            record["status"] = "ERROR"
            record["judging"].update(status="ERROR", execution_mode="batch", error=task["skip_reason"],
                attempts=0, total_attempts=state["totals"].get(str(position), 0))
            saved[position] = record
            unjudgable.add(position)
            logger.info("Batch item=%d status=ERROR reason=%s", position, task["skip_reason"])
    if unjudgable:
        write_checkpoint(output, saved)

    while True:
        active = state.get("active_batch")
        if active:
            job, _ = await retry_async(lambda: client.request(client.base_url + f"/batches/{active['id']}"),
                                       client.retries, logger, "Polling batch")
            logger.info("Batch id=%s status=%s", active["id"], job["status"])
            if job["status"] not in {"completed", "failed", "expired", "cancelled"}:
                if action != "run" or time.monotonic() - started >= wait_timeout:
                    save_state(state_path, state)
                    logger.info("Batch is pending; use --retry --mode batch --batch-action collect")
                    return 2
                await asyncio.sleep(poll_interval)
                continue
            entries = []
            for field in ("output_file_id", "error_file_id"):
                if job.get(field):
                    entries.extend(await file_content(client, job[field]))
            mapped = {}
            for entry in entries:
                custom_id = entry.get("custom_id", "")
                if not custom_id.startswith("task-") or not custom_id[5:].isdigit():
                    raise ValueError("Unexpected batch result custom_id")
                position = int(custom_id[5:])
                if position not in active["indices"] or position in mapped:
                    raise ValueError("Unknown or duplicate batch result task")
                mapped[position] = entry
            for position in active["indices"]:
                if position in completed:
                    continue
                task = tasks[position]
                record = make_record(task, position, role, model, fingerprint)
                entry = mapped.get(position, {})
                body = None
                attempt = state["attempts"][str(position)]
                try:
                    response = entry.get("response") or {}
                    if not isinstance(response, dict):
                        raise ValueError("Batch response must be an object or null")
                    body = response.get("body")
                    if entry.get("error") or response.get("status_code") != 200:
                        raise ValueError("Batch item failed or returned no successful result")
                    answers = parse_reply(body, role, task["rubric"])
                    record["judging"].update(status="SUCCESS", execution_mode="batch", answers=answers,
                        attempts=attempt, batch_id=active["id"], raw_response=body, request_settings=sampling)
                    if role == "responses":
                        record["judging"]["scores"] = response_scores(answers, task["rubric"])
                    record["status"] = "SUCCESS"
                    saved[position] = record
                    completed.add(position)
                    logger.info("Saved batch item=%d attempt=%d", position, attempt)
                except (ValueError, KeyError, IndexError, TypeError) as exc:
                    record["judging"].update(status="ERROR", execution_mode="batch", attempts=attempt,
                        batch_id=active["id"], error=str(exc), raw_response=body, batch_result=entry)
                    record["status"] = "ERROR"
                    saved[position] = record
                    logger.info("Batch item=%d failed attempt=%d/%d", position, attempt, max_attempts)
            for position in active["indices"]:
                saved[position]["judging"]["total_attempts"] = state["totals"].get(str(position), 0)
            write_checkpoint(output, saved)
            state["active_batch"] = None
            save_state(state_path, state)

        pending = [i for i in range(len(tasks)) if i not in completed and i not in unjudgable
                   and state["attempts"].get(str(i), 0) < max_attempts]
        if not pending:
            failed = len(tasks) - len(completed)
            save_state(state_path, state)
            logger.info("Batch judging finished; completed=%d failed=%d", len(completed), failed)
            return int(failed > 0)

        if action == "collect-only":
            save_state(state_path, state)
            logger.info("Collected available results without submitting work; remaining=%d", len(tasks) - len(completed))
            return 1

        # Every request targets this selected judge; enforce provider batch limits.
        lines, indices, size = [], [], 0
        for position in pending[:50000]:
            line = json.dumps({"custom_id": f"task-{position}", "method": "POST", "url": "/v1/chat/completions",
                               "body": judge_payload(tasks[position], model, sampling)}, ensure_ascii=False) + "\n"
            length = len(line.encode())
            if length > 200_000_000:
                raise ValueError("A single judging request exceeds the batch file limit")
            if size + length > 200_000_000:
                break
            lines.append(line)
            indices.append(position)
            size += length
        sequence = len(state["batches"]) + 1
        request_path = output.with_suffix(f".batch_{sequence}.requests.jsonl")
        request_path.write_text("".join(lines), encoding="utf-8")
        input_id = await upload_file(client, request_path)
        state["submission_in_progress"] = {"input_file_id": input_id, "indices": indices}
        save_state(state_path, state)
        logger.info("Submitting batch number=%d items=%d", sequence, len(indices))
        # Persist intent before creating a non-idempotent external job. A timeout
        # leaves an explicit recovery marker rather than auto-submitting duplicates.
        job = await client.request(client.base_url + "/batches", {
            "input_file_id": input_id, "endpoint": "/v1/chat/completions", "completion_window": "24h",
            "metadata": {"run_fingerprint": fingerprint, "role": role}})
        state.pop("submission_in_progress", None)
        for position in indices:
            key = str(position)
            state["attempts"][key] = state["attempts"].get(key, 0) + 1
            state["totals"][key] = state["totals"].get(key, 0) + 1
        state["active_batch"] = {"id": job["id"], "indices": indices}
        state["batches"].append({"id": job["id"], "input_file_id": input_id, "request_file": str(request_path)})
        save_state(state_path, state)
        logger.info("Submitted batch id=%s", job["id"])
        if action != "run":
            logger.info("Batch submitted; use --retry --mode batch --batch-action collect")
            return 2
