# vLLM eval-model ports

Launch a model with `bash pipeline/run-deployment.sh <model_id>`, or use
its deployment YAML with `vllm serve --config <path>`.
Ports are assigned in filename order. Hosted Gemini models do not use local ports.

| Model | Port | API base URL |
| --- | --- | --- |
| `BhabhaAI/Gajendra-v0.1` | 8801 | `http://127.0.0.1:8801/v1` |
| `CoRover/BharatGPT-3B-Indic` | 8802 | `http://127.0.0.1:8802/v1` |
| `CohereLabs/aya-23-35B` | 8803 | `http://127.0.0.1:8803/v1` |
| `CohereLabs/aya-23-8B` | 8804 | `http://127.0.0.1:8804/v1` |
| `GenVRadmin/AryaBhatta-GemmaOrca-Merged` | 8805 | `http://127.0.0.1:8805/v1` |
| `GenVRadmin/AryaBhatta-GemmaUltra-Merged` | 8806 | `http://127.0.0.1:8806/v1` |
| `MBZUAI/Llama-3-Nanda-10B-Chat` | 8807 | `http://127.0.0.1:8807/v1` |
| `MBZUAI-IFM/Llama-3.1-Nanda-87B-Chat` | 8808 | `http://127.0.0.1:8808/v1` |
| `Qwen/Qwen2.5-72B-Instruct` | 8809 | `http://127.0.0.1:8809/v1` |
| `Telugu-LLM-Labs/Indic-gemma-7b-finetuned-sft-Navarasa-2.0` | 8810 | `http://127.0.0.1:8810/v1` |
| `ai4bharat/Airavata` | 8811 | `http://127.0.0.1:8811/v1` |
| `google/gemma-3-27b-it` | 8812 | `http://127.0.0.1:8812/v1` |
| `google/gemma-3-4b-it` | 8813 | `http://127.0.0.1:8813/v1` |
| `krutrim-ai-labs/Krutrim-2-instruct` | 8814 | `http://127.0.0.1:8814/v1` |
| `large-traversaal/Qwen-2.5-14B-Hindi` | 8815 | `http://127.0.0.1:8815/v1` |
| `meta-llama/Llama-3.1-70B-Instruct` | 8816 | `http://127.0.0.1:8816/v1` |
| `meta-llama/Llama-3.1-8B-Instruct` | 8817 | `http://127.0.0.1:8817/v1` |
| `meta-llama/Llama-3.2-3B-Instruct` | 8818 | `http://127.0.0.1:8818/v1` |
| `meta-llama/Llama-3.3-70B-Instruct` | 8819 | `http://127.0.0.1:8819/v1` |
| `meta-llama/Meta-Llama-3-70B-Instruct` | 8820 | `http://127.0.0.1:8820/v1` |
| `meta-llama/Meta-Llama-3-8B-Instruct` | 8821 | `http://127.0.0.1:8821/v1` |
| `nvidia/Nemotron-4-Mini-Hindi-4B-Instruct` | 8822 | `http://127.0.0.1:8822/v1` |
| `sarvamai/sarvam-m` | 8823 | `http://127.0.0.1:8823/v1` |

## Pipeline integration

Use [the pipeline reference](pipeline.md) for dataset/checkpoint downloads,
vLLM/Gemini generation, async/Batch judging, final verdicts and `--retry`.
The generation runner uses the selected deployment's context/port/template
settings and records actual token budgets. Audits describe configuration evidence;
mocked tests do not verify GPU serving or live provider availability.
