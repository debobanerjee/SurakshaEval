#!/usr/bin/env python3
"""Inspect running OpenAI Batch jobs; credentials from OPENAI_API_KEY."""
import logging
import sys
from batch_management import main

if __name__ == '__main__':
    try:
        sys.exit(main(False))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        logging.getLogger('check-batch-jobs').error('%s', exc)
        sys.exit(1)
