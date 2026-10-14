"""Shared configuration, JSONL, asynchronous transport and sample retries."""
import argparse
import asyncio
from contextvars import ContextVar
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import yaml

from environment import load_environment

load_environment()
REQUEST_TIMEOUT_OVERRIDE = ContextVar("request_timeout_override", default=None)


def load_yaml(path):
    with Path(path).open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a YAML mapping: {path}")
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def read_rows(path):
    rows = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON: {path}:{line_no}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected a JSON object: {path}:{line_no}")
            rows.append(row)
    return rows


def write_checkpoint(path, records):
    """Atomically save one latest record per task in source order."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            for position in sorted(records):
                handle.write(json.dumps(records[position], ensure_ascii=False) + "\n")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Must be a positive integer")
    return number


def retry_count(value):
    number = int(value)
    if number < 5:
        raise argparse.ArgumentTypeError("Use at least five retries (six attempts)")
    return number


async def retry_async(action, retries, logger, label, timeout_on_retry=None):
    """Return (result, attempts) within the caller's initial-attempt-plus-retries budget."""
    override_token = REQUEST_TIMEOUT_OVERRIDE.set(None)
    try:
        for attempt in range(retries + 1):
            logger.info("%s attempt=%d/%d", label, attempt + 1, retries + 1)
            try:
                return await action(), attempt + 1
            except (RuntimeError, ValueError, KeyError, IndexError, TypeError, httpx.RequestError) as exc:
                if attempt == retries:
                    logger.info("%s failed after %d attempts", label, attempt + 1)
                    raise
                if timeout_on_retry and (isinstance(exc, httpx.TimeoutException)
                                         or isinstance(exc.__cause__, httpx.TimeoutException)):
                    REQUEST_TIMEOUT_OVERRIDE.set(timeout_on_retry)
                    logger.info("%s timeout; using %s seconds from the next attempt", label, timeout_on_retry)
                logger.info("%s failed (%s); retrying", label, type(exc).__name__)
                await asyncio.sleep(min(2 ** attempt, 8))
    finally:
        REQUEST_TIMEOUT_OVERRIDE.reset(override_token)
    raise RuntimeError("Retry attempts exhausted")


class AsyncAPIClient:
    def __init__(self, base_url, headers, logger, timeout=120, retries=5, transport=None):
        parts = urlsplit(base_url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("Invalid API URL")
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("API URL must not contain credentials, queries or fragments")
        if retries < 0:
            raise ValueError("Retries must be nonnegative")
        self.base_url = base_url.rstrip("/")
        self.logger, self.retries = logger, retries
        self.http = httpx.AsyncClient(timeout=timeout, transport=transport, headers=headers)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.http.aclose()

    async def request(self, url, payload=None):
        self.logger.info("API request path=%s", urlsplit(url).path)
        try:
            response = await self.http.request("GET" if payload is None else "POST", url, json=payload,
                timeout=REQUEST_TIMEOUT_OVERRIDE.get() or self.http.timeout)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Do not include response bodies or header values in task logs.
            raise RuntimeError(f"HTTP {exc.response.status_code} at {urlsplit(url).path}") from exc
        except httpx.RequestError as exc:
            raise RuntimeError("API connection failed or timed out") from exc
        self.logger.info("API request completed path=%s status=%d", urlsplit(url).path, response.status_code)
        return response.json()

    async def metadata(self, url):
        result, _ = await retry_async(lambda: self.request(url), self.retries,
                                      self.logger, "Checking model metadata")
        return result


class ResponseClient(AsyncAPIClient):
    async def generate(self, *args):
        result, attempts = await retry_async(lambda: self._generate(*args), self.retries,
                                             self.logger, "Generating sample", timeout_on_retry=3000)
        result["generation"]["attempts"] = attempts
        return result
