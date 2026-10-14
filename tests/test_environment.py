"""Repository .env loading, precedence and inheritance without exposing values."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
import environment


class EnvironmentTests(unittest.TestCase):
    def test_repo_file_and_exported_environment_precedence(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            (root / '.env').write_text('VLLM_API_KEY=fixture-from-file\nOPENAI_API_KEY=file-value\n')
            os.environ['OPENAI_API_KEY'] = 'exported-value'
            with patch.object(environment, 'REPO_ROOT', root):
                environment.load_environment()
            self.assertEqual(os.environ['VLLM_API_KEY'], 'fixture-from-file')
            self.assertEqual(os.environ['OPENAI_API_KEY'], 'exported-value')

    def test_launcher_inherits_dotenv_without_sourcing_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pipeline = root / 'pipeline'; pipeline.mkdir()
            shutil.copy(ROOT / 'pipeline/environment.py', pipeline / 'environment.py')
            marker = root / 'should-not-exist'
            (root / '.env').write_text(f'VLLM_API_KEY=fixture-key\nUNEXECUTED=$(touch {marker})\nPYTHON_BIN={sys.executable}\n')
            child = root / 'child.py'
            child.write_text('import os\nassert os.environ["VLLM_API_KEY"] == "fixture-key"\nassert os.environ["UNEXECUTED"].startswith("$(touch ")\n')
            env = {k: v for k, v in os.environ.items() if k not in {'VLLM_API_KEY', 'UNEXECUTED', 'PYTHON_BIN'}}
            for args in [['--python', str(child)], ['--exec', sys.executable, str(child)]]:
                result = subprocess.run([sys.executable, str(pipeline / 'environment.py'), *args],
                                        env=env, cwd='/tmp', capture_output=True, text=True, check=True)
                self.assertEqual(result.stdout, '')
                self.assertNotIn('fixture-key', result.stderr)
                self.assertFalse(marker.exists())

    def test_deployment_inherits_repo_dotenv_on_shell_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pipeline = root / 'pipeline'; pipeline.mkdir()
            for name in ['run-deployment.sh', 'environment.py', 'logging_utils.py']:
                shutil.copy(ROOT / 'pipeline' / name, pipeline / name)
            configs = root / 'configs/model-access/local/open-weight/vllm'; configs.mkdir(parents=True)
            config_name = 'CohereLabs--aya-23-8B.deployment.config.yaml'
            shutil.copy(ROOT / 'configs/model-access/local/open-weight/vllm' / config_name, configs / config_name)
            (root / '.env').write_text(f'VLLM_API_KEY=fixture-server-key\nCUDA_VISIBLE_DEVICES=0\nPYTHON_BIN={sys.executable}\n')
            binaries = root / 'bin'; binaries.mkdir()
            fake = binaries / 'vllm'
            fake.write_text(f'#!{sys.executable}\nimport os\nassert os.environ["VLLM_API_KEY"] == "fixture-server-key"\nassert os.environ["CUDA_VISIBLE_DEVICES"] == "0"\nprint("mock server launch verified")\n')
            fake.chmod(0o755)
            env = {k: v for k, v in os.environ.items() if k not in {'VLLM_API_KEY', 'CUDA_VISIBLE_DEVICES', 'SURAKSHA_ENV_LOADED'}}
            env.update(PATH=str(binaries) + os.pathsep + os.environ['PATH'], PYTHON_BIN=sys.executable,
                       PIPELINE_LOG_DIR=str(root / 'logs'))
            result = subprocess.run(['bash', str(pipeline / 'run-deployment.sh'), 'CohereLabs/aya-23-8B'],
                env=env, cwd='/tmp', capture_output=True, text=True, check=True)
            self.assertIn('mock server launch verified', result.stdout)
            self.assertNotIn('fixture-server-key', result.stdout + result.stderr)

    def test_environment_template_is_trackable_and_dotenv_ignored(self):
        dotenv = subprocess.run(['git', '-C', str(ROOT), 'check-ignore', '--no-index', '.env'], capture_output=True)
        example = subprocess.run(['git', '-C', str(ROOT), 'check-ignore', '--no-index', '.env.example'], capture_output=True)
        self.assertEqual(dotenv.returncode, 0)
        self.assertEqual(example.returncode, 1)


if __name__ == '__main__': unittest.main()
