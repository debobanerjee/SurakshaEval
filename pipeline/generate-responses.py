#!/usr/bin/env python3
"""Generate independent SurakshaEval responses using deployed vLLM or the Gemini API.

Requires httpx and PyYAML, but no local weights, tokenizer, CUDA, or vLLM import.
vLLM /tokenize must use the same template as /v1/chat/completions.
Gemini uses its native countTokens and generateContent REST methods.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
from urllib.parse import quote


from logging_utils import configure_logging
from pipeline_common import ResponseClient, load_yaml, digest, read_rows, positive, retry_count, write_checkpoint

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger("generate-responses")


class VLLMClient(ResponseClient):
    def __init__(self, base_url, key, timeout=120, retries=5, transport=None):
        if not base_url.rstrip("/").endswith("/v1"):
            raise ValueError("vLLM --base-url must end in /v1")
        super().__init__(base_url, {"Authorization": f"Bearer {key}"}, LOG,
                         timeout, retries, transport)
        self.server_url = self.base_url[:-3]

    async def check_model(self, model):
        LOG.info("Checking hosted vLLM model %s", model)
        data = await self.metadata(self.base_url + "/models")
        if model not in {item["id"] for item in data["data"]}:
            raise ValueError(f"Server does not advertise requested model: {model}")

    async def _generate(self, row, system_prompt, model, sampling, template_kwargs, context_len):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": row["question"]})
        chat = {"model": model, "messages": messages, "add_generation_prompt": True,
                "add_special_tokens": False}
        if template_kwargs:
            chat["chat_template_kwargs"] = template_kwargs
        tokens = await self.request(self.server_url + "/tokenize", chat)
        count = tokens.get("count")
        server_limit = tokens.get("max_model_len")
        if type(count) is not int or count < 0 or type(server_limit) is not int or server_limit < 1:
            raise ValueError("/tokenize must return integer count and max_model_len")
        effective_context = min(context_len, server_limit)
        remaining = effective_context - count
        if remaining < 1:
            raise ValueError(f"Rendered prompt uses {count} tokens; context is {effective_context}")
        actual_sampling = dict(sampling, max_tokens=min(sampling["max_tokens"], remaining))
        response = await self.request(self.base_url + "/chat/completions",
                                dict(chat, **actual_sampling, stream=False, n=1))
        choice = response["choices"][0]
        message = choice["message"]
        content = message.get("content")
        if content is not None and not isinstance(content, str):
            raise ValueError("Expected text response content")
        # Preserve reasoning/tool fields separately rather than silently discarding them.
        return {**row, "output": content or "", "system_instruction": system_prompt,
                "messages": messages,
                "generation": {"model": model, "base_url": self.base_url,
                    "sampling_params": actual_sampling, "chat_template_kwargs": template_kwargs,
                    "prompt_tokens": count, "context_limit": effective_context,
                    "finish_reason": choice.get("finish_reason"),
                    "usage": response.get("usage"), "assistant_message": message,
                    "response_id": response.get("id"),
                    "created_at": datetime.now(timezone.utc).isoformat()}}


class GeminiClient(ResponseClient):
    """Native Gemini REST adapter sharing async transport/retry lifecycle."""

    def __init__(self, base_url, key, timeout=120, retries=5, transport=None):
        if not base_url.rstrip("/").endswith("/v1beta"):
            raise ValueError("Gemini --base-url must end in /v1beta")
        super().__init__(base_url, {"x-goog-api-key": key}, LOG, timeout, retries, transport)
        self.input_limit = self.output_limit = None

    def model_url(self, model):
        return self.base_url + "/models/" + quote(model.removeprefix("models/"), safe="")

    async def check_model(self, model):
        LOG.info("Checking Gemini model %s", model)
        info = await self.metadata(self.model_url(model))
        if "generateContent" not in info.get("supportedGenerationMethods", []):
            raise ValueError(f"Gemini model does not advertise generateContent: {model}")
        self.input_limit, self.output_limit = info.get("inputTokenLimit"), info.get("outputTokenLimit")
        if any(type(limit) is not int or limit < 1 for limit in (self.input_limit, self.output_limit)):
            raise ValueError("Gemini model metadata must provide input/output token limits")

    async def _generate(self, row, system_prompt, model, sampling, template_kwargs, context_len):
        if self.input_limit is None or self.output_limit is None:
            raise RuntimeError("Check Gemini model metadata before generating responses")
        if template_kwargs:
            raise ValueError("vLLM chat-template kwargs are not Gemini generation settings")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": row["question"]})
        payload = {"contents": [{"role": "user", "parts": [{"text": row["question"]}]}]}
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        resource = "models/" + model.removeprefix("models/")
        tokens = await self.request(self.model_url(model) + ":countTokens",
                                    {"generateContentRequest": dict(payload, model=resource)})
        count = tokens.get("totalTokens")
        if type(count) is not int or count < 0:
            raise ValueError("Gemini countTokens must return integer totalTokens")
        if count > self.input_limit:
            raise ValueError(f"Gemini prompt uses {count} tokens; input limit is {self.input_limit}")
        remaining = context_len - count
        if remaining < 1:
            raise ValueError(f"Gemini prompt uses {count} tokens; experimental context is {context_len}")
        actual_sampling = dict(sampling, max_tokens=min(sampling["max_tokens"], remaining, self.output_limit))
        names = {"temperature": "temperature", "top_p": "topP", "top_k": "topK",
                 "max_tokens": "maxOutputTokens", "seed": "seed", "stop": "stopSequences",
                 "presence_penalty": "presencePenalty", "frequency_penalty": "frequencyPenalty"}
        if set(actual_sampling) - names.keys():
            raise ValueError("Unsupported Gemini sampling setting in the evaluated-model profile")
        payload["generationConfig"] = {names[key]: value for key, value in actual_sampling.items()}
        payload["generationConfig"]["candidateCount"] = 1
        # Keep provider-default thinking and safety settings; record all returned feedback.
        response = await self.request(self.model_url(model) + ":generateContent", payload)
        feedback = response.get("promptFeedback", {})
        candidates = response.get("candidates", [])
        if not candidates and not feedback.get("blockReason"):
            raise ValueError("Gemini returned no candidates or prompt-block feedback")
        candidate = candidates[0] if candidates else {}
        parts = candidate.get("content", {}).get("parts", [])
        content = "".join(part["text"] for part in parts if "text" in part and not part.get("thought"))
        finish_reason = candidate.get("finishReason") or ("PROMPT_BLOCKED" if feedback.get("blockReason") else None)
        blocked = bool(feedback.get("blockReason")) or finish_reason in {
            "SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "RECITATION", "SPII"}
        return {**row, "output": content, "system_instruction": system_prompt, "messages": messages,
                "generation": {"provider": "google_gemini", "model": model,
                    "base_url": self.base_url, "model_version": response.get("modelVersion"),
                    "sampling_params": actual_sampling, "chat_template_kwargs": {},
                    "prompt_tokens": count, "context_limit": context_len,
                    "provider_input_limit": self.input_limit, "provider_output_limit": self.output_limit,
                    "finish_reason": finish_reason, "blocked": blocked,
                    "prompt_feedback": feedback, "safety_ratings": candidate.get("safetyRatings", []),
                    "usage": response.get("usageMetadata"), "provider_response": response,
                    "assistant_message": {"role": "assistant", "content": content,
                                          "parts": parts},
                    "response_id": response.get("responseId"),
                    "created_at": datetime.now(timezone.utc).isoformat()}}


async def generate_file(client, source, output, rows, settings, retry, concurrency):
    fingerprint = digest({"settings": settings})
    completed = set()
    saved = {}
    if output.exists():
        if not retry:
            raise FileExistsError(f"Output exists; use --retry or a different output directory: {output}")
        for old in read_rows(output):
            generation = old.get("generation", {})
            position = generation.get("source_row")
            if generation.get("run_fingerprint") != fingerprint:
                raise ValueError(f"Resume input/config mismatch: {output}")
            if type(position) is not int or position not in range(len(rows)) or position in saved:
                raise ValueError(f"Invalid/duplicate retry source_row: {output}")
            saved[position] = old
            status = generation.get("status", old.get("status", "SUCCESS" if "output" in old else "ERROR"))
            if status == "SUCCESS" and generation.get("task_fingerprint") == digest(rows[position]):
                completed.add(position)
    pending = [i for i in range(len(rows)) if i not in completed]
    if not pending:
        LOG.info("Complete, skipping %s", output)
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    failures = 0

    semaphore = asyncio.Semaphore(concurrency)

    async def work(position):
        task_settings = settings[position] if isinstance(settings, list) else settings
        LOG.info("Generating item=%d region=%s language=%s turn=%s", position,
                 task_settings.get("region"), task_settings.get("language"), task_settings.get("turn"))
        try:
            async with semaphore:
                result = await client.generate(rows[position], task_settings["system_prompt"],
                                               task_settings["served_model"], task_settings["sampling"],
                                               task_settings["template_kwargs"], task_settings["context_len"])
            result["generation"].update(run_fingerprint=fingerprint, task_fingerprint=digest(rows[position]), source_row=position,
                                        source_file=task_settings.get("source_file", str(source)), turn=task_settings["turn"],
                                        system_prompt_type=task_settings["system_prompt_type"])
            for key in ("region", "language", "input_row"):
                if key in task_settings:
                    result["generation"][key] = task_settings[key]
            result["status"] = result["generation"]["status"] = "SUCCESS"
            return position, result, None
        except (RuntimeError, ValueError, KeyError, IndexError, TypeError) as exc:
            error = str(exc)
            previous = saved.get(position, {}).get("generation", {})
            result = {**rows[position], "output": None, "status": "ERROR",
                "system_instruction": task_settings["system_prompt"],
                "generation": {"status": "ERROR", "model": task_settings["served_model"],
                    "base_url": task_settings.get("base_url", client.base_url), "error": error,
                    "attempts": client.retries + 1, "run_fingerprint": fingerprint, "task_fingerprint": digest(rows[position]),
                    "source_row": position, "source_file": task_settings.get("source_file", str(source)),
                    "turn": task_settings["turn"], "system_prompt_type": task_settings["system_prompt_type"],
                    "region": task_settings.get("region"), "language": task_settings.get("language"),
                    "input_row": task_settings.get("input_row"),
                    "total_attempts": previous.get("total_attempts", previous.get("attempts", 0)) + client.retries + 1}}
            return position, result, error

    # Bounded task batches avoid creating a task for every dataset row at once.
    batch_size = concurrency * 4
    for start in range(0, len(pending), batch_size):
        results = await asyncio.gather(*(work(i) for i in pending[start:start + batch_size]))
        for position, result, error in results:
            previous = saved.get(position, {}).get("generation", {})
            if error is not None:
                failures += 1
                LOG.info("Generation item=%d status=ERROR after all retries", position)
            else:
                result["generation"]["total_attempts"] = previous.get("total_attempts", previous.get("attempts", 0)) + result["generation"]["attempts"]
                LOG.info("Generation item=%d status=SUCCESS finish_reason=%s", position, result["generation"].get("finish_reason"))
            saved[position] = result
        write_checkpoint(output, saved)
        LOG.info("Checkpoint saved %s: processed %d/%d pending rows", output.name,
                 min(start + batch_size, len(pending)), len(pending))
    return failures


async def async_main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Evaluated HF checkpoint or Gemini model ID")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "configs/common.config.yaml")
    parser.add_argument("--input-dir", type=Path, help="Parent of filtered_and_updated/")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "pipeline/output/respones",
                        help="Model response directory; default pipeline/output/respones")
    parser.add_argument("--base-url", help="vLLM endpoint ending in /v1, or Gemini REST root ending in /v1beta")
    parser.add_argument("--context-length", type=positive, help="Experimental total-token cap; Gemini default 8192, vLLM uses deployment YAML")
    parser.add_argument("--served-model", help="Override model name advertised by vLLM")
    parser.add_argument("--regions", nargs="+")
    parser.add_argument("--languages", nargs="+", help="Subset of configured supported languages")
    parser.add_argument("--turns", type=positive, help="Independent samples per question, not dialogue")
    parser.add_argument("--ablations", action="store_true")
    parser.add_argument("--system-prompt", help="Select a configured system-prompt name")
    parser.add_argument("--max-tokens", type=positive)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--concurrency", type=positive, default=8)
    parser.add_argument("--timeout", type=positive, default=120)
    parser.add_argument("--retries", type=retry_count, default=5, help="At least five retries per failed sample")
    parser.add_argument("--limit", type=positive, help="First N questions per selected file")
    parser.add_argument("--retry", action="store_true", help="Skip matching SUCCESS records; retry ERROR and unprocessed records")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and show plan without HTTP calls")
    args = parser.parse_args(argv)
    configure_logging("generate-responses", model=args.model)
    LOG.info("Starting generate-responses; loading CLI/configuration")
    stem = args.model.replace("/", "--")
    local_path = REPO_ROOT / "configs/model-access/local/open-weight/vllm" / f"{stem}.deployment.config.yaml"
    gemini_path = REPO_ROOT / "configs/model-access/api/proprietary/google" / f"{stem}.deployment.config.yaml"
    if local_path.is_file():
        backend, deployment_path = "vllm", local_path
    elif gemini_path.is_file():
        backend, deployment_path = "gemini", gemini_path
    else:
        parser.error("Select a configured vLLM or Gemini evaluated model")
    shared = load_yaml(args.config)
    profile = load_yaml(REPO_ROOT / "configs/inference/eval_models" / f"{stem}.config.yaml")["eval_models"][args.model]
    deployment = load_yaml(deployment_path)
    LOG.info("Selected backend=%s model=%s access_config=%s", backend, args.model, deployment_path)
    if backend == "gemini":
        if args.served_model:
            parser.error("--served-model is only for vLLM; select Gemini IDs using --model")
        served = deployment["model"]
        base_url = args.base_url or "https://generativelanguage.googleapis.com/v1beta"
        context_len = args.context_length or 8192
        key_env = deployment["api-key-env"]
    else:
        configured_names = deployment.get("served-model-name") or [args.model]
        if isinstance(configured_names, str):
            configured_names = [configured_names]
        if not isinstance(configured_names, list) or any(not isinstance(name, str) or not name for name in configured_names):
            parser.error("Deployment served-model-name must be a name or list of names")
        served = args.served_model or configured_names[0]
        host = deployment.get("host", "127.0.0.1")
        if host in {"0.0.0.0", "::"}:
            host = "127.0.0.1"
        base_url = args.base_url or f"http://{host}:{deployment['port']}/v1"
        context_len = min(args.context_length or deployment["max-model-len"], deployment["max-model-len"])
        key_env = "VLLM_API_KEY"
    input_dir = args.input_dir or REPO_ROOT / shared["input_dir"]
    output_dir = args.output_dir
    regions = args.regions or shared["regions"]
    if set(regions) - set(shared["regions"]) or len(set(regions)) != len(regions):
        parser.error("--regions must be unique configured region names")
    languages = args.languages or profile["supported_languages"]
    if set(languages) - set(profile["supported_languages"]) or len(set(languages)) != len(languages):
        parser.error("--languages must be unique languages supported by the selected profile")
    prompts = profile["system_prompts"].get("ablations" if args.ablations else "default", {})
    if args.system_prompt:
        if args.system_prompt not in prompts:
            parser.error("--system-prompt is not in the selected default/ablation group")
        prompts = {args.system_prompt: prompts[args.system_prompt]}
    if not prompts or any(not isinstance(v, str) for v in prompts.values()):
        parser.error("No valid system prompts configured for the selected group")
    sampling = {k: v for k, v in profile["sampling_params"].items() if v is not None and v != "None"}
    sampling["max_tokens"] = args.max_tokens or sampling.get("max_tokens", 4096)
    if type(sampling["max_tokens"]) is not int or sampling["max_tokens"] < 1:
        parser.error("Configured max_tokens must be positive")
    template_kwargs = {}
    if "enable_thinking" in profile:
        template_kwargs["enable_thinking"] = profile["enable_thinking"]
    template_digest = None
    if profile["prompt_format"] == "custom_chat_template":
        template_path = REPO_ROOT / deployment["chat-template"]
        template_digest = hashlib.sha256(template_path.read_bytes()).hexdigest()
    turns = args.turns or profile.get("n_turns", 1)
    if type(turns) is not int or turns < 1:
        parser.error("Configured n_turns must be positive")
    jobs = []
    checkpoint = args.model.replace("/", "--")
    for region in regions:
        for language in [shared["language_codes"][region], "en"]:
            if language not in languages:
                continue
            source = input_dir / "filtered_and_updated" / region / f"{language}_questions.jsonl"
            LOG.info("Reading downloaded questions %s", source)
            rows = read_rows(source)
            if any(not isinstance(row.get("question"), str) or not row["question"].strip() for row in rows):
                raise ValueError(f"Missing or empty question text: {source}")
            if args.limit:
                rows = rows[:args.limit]
            for prompt_name, prompt in prompts.items():
                for turn in range(1, turns + 1):
                    output = output_dir / f"{checkpoint}_turn_{turn}_response.jsonl"
                    settings = {"served_model": served, "base_url": base_url,
                        "sampling": dict(sampling, seed=args.seed + turn - 1),
                        "context_len": context_len, "template_kwargs": template_kwargs,
                        "system_prompt": prompt, "system_prompt_type": prompt_name, "turn": turn,
                        "deployment": deployment, "template_sha256": template_digest,
                        "source_file": str(source), "region": region, "language": language}
                    jobs.append((source, output, rows, settings))
    if not jobs:
        parser.error("No files selected by the requested regions/languages")
    outputs = {}
    for source, output, rows, settings in jobs:
        all_rows, all_settings = outputs.setdefault(output, ([], []))
        for input_row, row in enumerate(rows):
            all_rows.append(row)
            all_settings.append(dict(settings, input_row=input_row))
    for output, (rows, _) in outputs.items():
        LOG.info("Endpoint %s; %d requests; output %s", base_url, len(rows), output)
        if output.exists() and not args.retry:
            raise FileExistsError(f"Output already exists: {output}; use --retry or a different output directory")
    if args.dry_run:
        for source, output, rows, settings in jobs:
            print(f"{source} -> {output} ({len(rows)} questions; prompt={settings['system_prompt_type']}, turn={settings['turn']})")
        return 0
    key = os.environ.get(key_env)
    if not key and backend == "gemini":
        key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        parser.error(f"Set {key_env} to the server/provider key")
    client_class = GeminiClient if backend == "gemini" else VLLMClient
    async with client_class(base_url, key, args.timeout, args.retries) as client:
        await client.check_model(served)
        failures = 0
        for output, (rows, settings) in outputs.items():
            failures += await generate_file(client, input_dir, output, rows, settings,
                                            args.retry, args.concurrency)
    if failures:
        LOG.error("%d requests failed; rerun with --retry to retry ERROR and unprocessed rows", failures)
        return 1
    LOG.info("Response generation complete")
    return 0


def main(argv=None):
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        LOG.error("%s", exc)
        sys.exit(1)
