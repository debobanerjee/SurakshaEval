"""Shared console/file activity logging; never pass credentials as messages."""
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import re
import sys

from environment import load_environment

load_environment()
REPO_ROOT = Path(__file__).resolve().parents[1]


def safe_name(value):
    return re.sub(r'[^\w.-]+', '--', value or 'unknown')


def configure_logging(task, model=None, evaluated_model=None):
    logger = logging.getLogger(task)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    root = Path(os.environ.get('PIPELINE_LOG_DIR', REPO_ROOT / 'logs'))
    stamp = os.environ.get('PIPELINE_LOG_RUN_ID') or datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    model = model or os.environ.get('PIPELINE_LOG_MODEL')
    if task == 'download-data':
        directory, prefix = root / 'dataset', 'download'
    elif task == 'final-verdict':
        directory, prefix = root / 'judge', safe_name(model) + '_verdicts'
    elif task in {'check-batch-jobs', 'cancel-batch-jobs'}:
        directory, prefix = root / 'judge', task.replace('-', '_')
    elif task == 'safety-audit-report':
        directory, prefix = root / 'reports', 'safety_audit'
    elif task == 'safety-dashboard':
        directory, prefix = root / 'reports', 'safety_dashboard'
    elif task == 'download-checkpoint':
        directory, prefix = root / 'checkpoints', safe_name(model)
    elif task == 'generate-responses':
        directory, prefix = root / 'model_response', safe_name(model)
    elif task == 'judge-questions':
        directory, prefix = root / 'judge', safe_name(model) + '_questions'
    elif task == 'judge-model-responses':
        directory, prefix = root / 'judge', safe_name(model) + '_eval_models'
        if evaluated_model:
            prefix += '_' + safe_name(evaluated_model)
    else:
        directory, prefix = root / 'deployment', safe_name(model)
    directory.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')
    log_path = directory / f'{prefix}_{stamp}.log'
    for handler in (logging.StreamHandler(), logging.FileHandler(log_path, encoding='utf-8')):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.info('Activity log: %s (filename timestamp in UTC)', log_path)
    return logger


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: logging_utils.py TASK MESSAGE')
    configure_logging(sys.argv[1]).info(sys.argv[2])
