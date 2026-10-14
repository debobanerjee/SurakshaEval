#!/usr/bin/env python3
"""Download a Hugging Face model snapshot; authentication comes only from HF_TOKEN."""
import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys

from logging_utils import configure_logging
from pipeline_common import positive

LOG = logging.getLogger("download-checkpoint")
MANIFEST = ".surakshaeval-checkpoint.json"


def download(model_id, directory, revision, workers):
    try:
        from huggingface_hub import HfApi, snapshot_download
        from huggingface_hub.errors import HfHubHTTPError
    except ImportError as exc:
        raise RuntimeError("Install requirements.txt or pipeline/requirements.txt first") from exc
    # False disables fallback to cached credentials when no environment key is set.
    token = os.environ.get("HF_TOKEN") or False
    try:
        LOG.info("Resolving model=%s revision=%s", model_id, revision)
        info = HfApi(token=token).model_info(model_id, revision=revision)
        if not info.sha:
            raise RuntimeError("Hub did not return a checkpoint commit")
        manifest = directory / MANIFEST
        record = json.loads(manifest.read_text(encoding="utf-8"))
        record["commit"] = info.sha
        temporary = manifest.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        temporary.replace(manifest)
        LOG.info("Downloading model=%s commit=%s destination=%s", model_id, info.sha, directory)
        snapshot_download(repo_id=model_id, repo_type="model", revision=info.sha,
                          local_dir=str(directory), token=token, max_workers=workers)
        return info.sha
    except HfHubHTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        raise RuntimeError(f"Checkpoint download failed (HTTP {status}); check model ID, revision and HF_TOKEN access") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_id", help="Hugging Face model ID, for example CohereLabs/aya-23-8B")
    parser.add_argument("download_dir", type=Path, help="Directory for this checkpoint only")
    parser.add_argument("--revision", default="main", help="Branch, tag or commit; resolved to a pinned commit")
    parser.add_argument("--max-workers", type=positive, default=8)
    args = parser.parse_args(argv)
    configure_logging("download-checkpoint", model=args.model_id)
    directory = args.download_dir.expanduser().resolve()
    manifest = directory / MANIFEST
    if directory.exists() and not directory.is_dir():
        raise ValueError("Download destination must be a directory")
    if manifest.exists():
        previous = json.loads(manifest.read_text(encoding="utf-8"))
        if previous.get("model_id") != args.model_id or previous.get("requested_revision") != args.revision:
            raise ValueError("Destination belongs to another model/revision; select a separate directory")
    elif directory.exists() and any(directory.iterdir()):
        raise ValueError("Use an empty directory or one previously initialized by this downloader")
    directory.mkdir(parents=True, exist_ok=True)
    # Save identity before downloading so interrupted downloads can be rerun safely.
    record = {"model_id": args.model_id, "requested_revision": args.revision}
    if manifest.exists():
        record = json.loads(manifest.read_text(encoding="utf-8"))
    temporary = manifest.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(manifest)
    commit = download(args.model_id, directory, record.get("commit", args.revision), args.max_workers)
    record.update(commit=commit, downloaded_at=datetime.now(timezone.utc).isoformat())
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(manifest)
    LOG.info("Checkpoint ready model=%s commit=%s destination=%s", args.model_id, commit, directory)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        LOG.error("%s", exc)
        sys.exit(1)
