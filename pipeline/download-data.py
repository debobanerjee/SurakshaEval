#!/usr/bin/env python3
"""Download the gated paired dataset and prepare regional question JSONL files.

Credentials are read exclusively from HF_TOKEN. No credentials are accepted via
CLI or written to manifests. Accept dataset access conditions on Hugging Face first.
"""
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import tempfile

import yaml

from logging_utils import configure_logging

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger("download-data")


def read_pairs(path, region, language):
    pairs = []
    indices, ids = set(), set()
    with Path(path).open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {region}:{line_no}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected paired JSON object at {region}:{line_no}")
            index = row.get("index")
            pair_id = row.get("id")
            if type(index) is not int or index < 0 or index in indices:
                raise ValueError(f"Invalid or duplicate index at {region}:{line_no}")
            if not isinstance(pair_id, str) or not pair_id or pair_id in ids:
                raise ValueError(f"Invalid or duplicate pair ID at {region}:{line_no}")
            if row.get("region") != region or row.get("language") != language:
                raise ValueError(f"Region/language mismatch at {region}:{line_no}")
            for field in ("question_en", "question_indic"):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    raise ValueError(f"Missing {field} at {region}:{line_no}")
            for field in ("risk_area", "type_of_harm", "question_type"):
                if not isinstance(row.get(field), str):
                    raise ValueError(f"Invalid {field} at {region}:{line_no}")
            indices.add(index)
            ids.add(pair_id)
            pairs.append(row)
    if not pairs:
        raise ValueError(f"No question pairs downloaded for {region}")
    return pairs


def question_rows(pairs, language):
    for pair in pairs:
        meta = {field: pair[field] for field in ("risk_area", "type_of_harm", "question_type")}
        shared = {"index": pair["index"], "pair_id": pair["id"], "meta": meta}
        yield ({**shared, "question": pair["question_en"], "language": "en"},
               {**shared, "question": pair["question_indic"], "language": "in-" + language})


def download_sources(repo_id, revision, regions, token):
    try:
        from huggingface_hub import HfApi, hf_hub_download
        from huggingface_hub.errors import GatedRepoError, HfHubHTTPError
    except ImportError as exc:
        raise RuntimeError("Install pipeline/requirements.txt or root requirements.txt first") from exc
    try:
        LOG.info("Resolving dataset=%s revision=%s", repo_id, revision)
        info = HfApi(token=token).dataset_info(repo_id, revision=revision)
        if not info.sha:
            raise RuntimeError("Hugging Face did not return a dataset commit")
        # Pin every file to the same commit even if main changes during download.
        sources = {}
        for region in regions:
            LOG.info("Downloading paired data region=%s commit=%s", region, info.sha)
            sources[region] = Path(hf_hub_download(repo_id=repo_id, repo_type="dataset",
                filename=f"data/{region}/test.jsonl", revision=info.sha, token=token))
        return info.sha, sources
    except GatedRepoError as exc:
        raise RuntimeError("Dataset access denied. Accept the access conditions on the dataset page and use that account's HF_TOKEN") from exc
    except HfHubHTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        raise RuntimeError(f"Hugging Face request failed (HTTP {status}); check dataset ID, revision, and HF_TOKEN access") from exc


def write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".download-", delete=False) as handle:
            temp_path = Path(handle.name)
            handle.write(text)
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default="SurakshaAI/SurakshaEval")
    parser.add_argument("--revision", default="main", help="Dataset branch/tag/commit, resolved to one commit")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "configs/common.config.yaml")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "data",
                        help="Data root containing filtered_and_updated/; default repo data/")
    parser.add_argument("--regions", nargs="+", help="Subset of configured regional contexts")
    parser.add_argument("--overwrite", action="store_true", help="Replace selected region question files/manifests")
    args = parser.parse_args(argv)
    configure_logging("download-data")
    LOG.info("Starting download-data; loading CLI/configuration")
    token = os.environ.get("HF_TOKEN")
    if not token:
        parser.error("Set HF_TOKEN for an account granted access to this gated dataset")
    with args.config.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    regions = args.regions or config["regions"]
    if set(regions) - set(config["regions"]) or len(set(regions)) != len(regions):
        parser.error("--regions must be unique configured region names")
    paths = {}
    for region in regions:
        code = config["language_codes"][region]
        directory = args.output_dir / "filtered_and_updated" / region
        paths[region] = (directory / "en_questions.jsonl", directory / f"{code}_questions.jsonl",
                         directory / "download_manifest.json")
        for path in paths[region]:
            if path.exists() and not args.overwrite:
                raise FileExistsError(f"Existing file protected: {path}; select --overwrite to replace it")
    commit, sources = download_sources(args.repo_id, args.revision, regions, token)
    # Validate every selected region before writing any output.
    prepared = {}
    for region, source in sources.items():
        language = config["language_codes"][region].removeprefix("in-")
        LOG.info("Validating and converting paired rows region=%s", region)
        pairs = read_pairs(source, region, language)
        LOG.info("Validated region=%s pairs=%d prompts=%d", region, len(pairs), 2 * len(pairs))
        if config["language_codes"][region] != "in-" + language:
            raise ValueError(f"Unsupported configured language code for {region}")
        english, indic = zip(*question_rows(pairs, language))
        encode = lambda rows: "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        en_text, indic_text = encode(english), encode(indic)
        manifest = {"repo_id": args.repo_id, "revision": commit,
                    "source_file": f"data/{region}/test.jsonl", "region": region,
                    "pairs": len(pairs), "prompts": len(pairs) * 2,
                    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "outputs": {paths[region][0].name: hashlib.sha256(en_text.encode()).hexdigest(),
                                paths[region][1].name: hashlib.sha256(indic_text.encode()).hexdigest()}}
        prepared[region] = (en_text, indic_text, json.dumps(manifest, indent=2) + "\n")
    for region, texts in prepared.items():
        for path, text in zip(paths[region], texts):
            LOG.info("Writing prepared dataset file %s", path)
            write_atomic(path, text)
        LOG.info("Prepared %s at %s", region, paths[region][0].parent)
    LOG.info("Dataset %s pinned to %s; %d regions ready", args.repo_id, commit, len(regions))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        LOG.error("%s", exc)
        sys.exit(1)
