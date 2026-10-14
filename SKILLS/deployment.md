---
name: surakshaeval-deployment
description: Deploy a configured SurakshaEval open-weight model through the prepared vLLM launcher.
---

# Deploy an evaluated model

Run commands from this repository root, or invoke the launcher using an
absolute path.

Create a Conda or uv environment and install root `requirements.txt` using
[the README setup](../README.md#setup) before deployment.

Read the selected model's
`configs/model-access/local/open-weight/vllm/<model>.deployment.config.yaml`.
Filenames replace `/` in model IDs with `--`. Hosted proprietary API profiles
are not vLLM deployments.

```bash
export VLLM_API_KEY="<shared-secret>"
# Set HF_TOKEN when the checkpoint requires gated Hugging Face access.
CUDA_VISIBLE_DEVICES=0 bash pipeline/run-deployment.sh CohereLabs/aya-23-8B
```

Preview without loading weights:

```bash
bash pipeline/run-deployment.sh --dry-run CohereLabs/aya-23-8B
```

Use `--config PATH` to select a native YAML directly. Deliberate vLLM overrides
follow `--`; for example `-- --tensor-parallel-size 2`. The launcher uses YAML
defaults, resolves the code-repo root for Jinja paths, inherits `VLLM_API_KEY`,
and runs in the foreground. Ctrl+C stops it.

The native `api-key: null` field leaves the secret to vLLM's environment
authentication. Never replace it with a committed secret. Direct launches with
`vllm serve --config ...` also require that environment variable for authentication.

Check the model ID and assigned port in
[the port mapping](../docs/vllm_ports.md).
Ports span 8801–8823. Verify the advertised model before generation:

```bash
curl -H "Authorization: Bearer $VLLM_API_KEY" http://127.0.0.1:8804/v1/models
```

Preserve experimental BF16, seed, context, and sampling choices unless asked to
change them. Gajendra, Airavata, and Nemotron Hindi have 4096-context configs;
others use 8192, with verification gaps in
[the context audit](../docs/context_length_audit.md).
Backend selection remains automatic. Check GPU memory and runtime compatibility
at startup; a valid YAML file does not prove serving capacity.

## Local checkpoint downloads and logs

Download into a dedicated directory with
`bash pipeline/run-download-checkpoint.sh MODEL_ID checkpoints/MODEL_NAME`.
The optional `--revision` is pinned to a commit. HF_TOKEN is environment-only;
public models need no key. Reuse the same command after an interruption. To use
these weights, launch the matching deployment with
`-- --model /absolute/checkpoint/path --served-model-name MODEL_ID` so generation
can keep its configured API model ID. Never mix models in the same destination.

Deployment validation/launch activity uses logger.info and
`logs/deployment/<model>_<date_time>.log`; vLLM runtime output stays on the terminal.
Checkpoint downloads use `logs/checkpoints/<model>_<date_time>.log`.
See [the pipeline reference](../docs/pipeline.md) for the full workflow and tests.

## Environment and workflow references

Use [setup_environment.md](setup_environment.md) to create Conda eval-env and
install requirements. Repo-root .env is loaded automatically by Python and shell
entry points; exported variables take precedence. See [the environment template](../.env.example).
For dataset preparation use [download_data.md](download_data.md). For active
Batch inspection/cancellation and partial collection without resubmission use
[batch_management.md](batch_management.md).
