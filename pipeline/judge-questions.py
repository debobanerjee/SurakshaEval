#!/usr/bin/env python3
"""Judge downloaded SurakshaEval questions; credentials from OPENAI_API_KEY."""
import logging
import sys
from judging import main

if __name__ == "__main__":
    try:
        sys.exit(main("questions"))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        logging.getLogger("judge-questions").error("%s", exc)
        sys.exit(1)
