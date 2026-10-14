#!/usr/bin/env python3
"""Judge aggregate model-response files; credentials from OPENAI_API_KEY."""
import logging
import sys
from judging import main

if __name__ == "__main__":
    try:
        sys.exit(main("responses"))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        logging.getLogger("judge-model-responses").error("%s", exc)
        sys.exit(1)
