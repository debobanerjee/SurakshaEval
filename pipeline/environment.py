"""Load repo-root .env without overriding exported variables or executing shell code."""
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_environment():
    return load_dotenv(REPO_ROOT / '.env', override=False)


if __name__ == '__main__':
    load_environment()
    if len(sys.argv) < 3 or sys.argv[1] not in {'--exec', '--python'}:
        raise SystemExit('Usage: environment.py --exec COMMAND [ARGS...] | --python SCRIPT [ARGS...]')
    if sys.argv[1] == '--python':
        arguments = [os.environ.get('PYTHON_BIN') or sys.executable, *sys.argv[2:]]
    else:
        arguments = sys.argv[2:]
    # Allows the deployment shell to re-enter once with .env variables inherited.
    os.environ['SURAKSHA_ENV_LOADED'] = '1'
    os.execvpe(arguments[0], arguments, os.environ.copy())
