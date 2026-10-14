---
name: surakshaeval-setup-environment
description: Create the Conda eval-env environment and install all deployment, download, generation and judging packages.
---

# Set up eval-env

Run from the SurakshaEval code repository root. Use a Linux NVIDIA GPU host for
the full vLLM deployment stack; remote clients can use the lightweight requirements
without loading weights or requiring CUDA.

```bash
conda create -n eval-env python=3.13 -y
conda activate eval-env
python -m pip install -r requirements.txt
python -m pip check
```

The full requirements include vllm==0.31.0, Torch, Transformers, HTTPX, PyYAML,
huggingface-hub, python-dotenv, OpenAI and the research/analysis dependencies.
Install them together so vLLM's constraints choose compatible serving libraries.
Match the driver/CUDA environment to [vLLM installation requirements](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/).
Do not independently force conflicting Torch/Transformers versions.

For a separate machine that only downloads data/checkpoints, calls existing API
servers, judges or derives verdicts, use the same environment name but install
`pipeline/requirements.txt` instead of the full GPU stack:

```bash
python -m pip install -r pipeline/requirements.txt
```

```bash
cp -n .env.example .env
```

Fill only the variables required for your workflow in the repo-root .env file:
HF_TOKEN for gated downloads, VLLM_API_KEY for vLLM server/client, GEMINI_API_KEY
(or GOOGLE_API_KEY) for Gemini, and OPENAI_API_KEY for judges and Batch management.
Python scripts and shell entry points load this file automatically, even when
called from another working directory. Already-exported variables take precedence.
Secrets remain environment values; never put them in CLI flags, YAML or logs.
The .env file is ignored by Git; .env.example has empty placeholders.

Optional CUDA_VISIBLE_DEVICES and model-cache/log paths are described in the
[environment template](../.env.example). Use the same vLLM key on the server and
client. Keep model/experiment settings in the YAML configs rather than .env.

```bash
python -m unittest discover -s tests -v
mkdir -p pipeline/output
python -m pip freeze > pipeline/output/environment-packages.txt
```

Tests use mock traffic and need no real keys or
GPU. Record package versions and GPU/driver details with live experiment results.
Continue with [dataset download](download_data.md), [deployment](deployment.md),
[generation](generate_response.md), [judging](judge_eval_models.md), and
[Batch management](batch_management.md). See [the main README](../README.md).
