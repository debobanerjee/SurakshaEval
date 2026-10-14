#!/usr/bin/env python3
"""Cancel selected OpenAI Batch jobs; credentials from OPENAI_API_KEY."""
import logging
import sys
from batch_management import main

if __name__ == '__main__':
    try:
        sys.exit(main(True))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        logging.getLogger('cancel-batch-jobs').error('%s', exc)
        sys.exit(1)
