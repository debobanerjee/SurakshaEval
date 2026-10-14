# Hosted access for open-weight eval models

Each provider directory has one config for each of the **23 open-weight evaluated
models**. The four Gemini profiles remain under
[`../proprietary/google/`](../proprietary/google/) for native Google API access.

Verified on **2026-10-14** against the [OpenRouter model catalog](https://openrouter.ai/api/v1/models)
and [Fireworks model library](https://fireworks.ai/models). Seven OpenRouter
mappings and nine Fireworks mappings were verified. This is a dated availability
snapshot, not a guarantee of account access or future service availability.

## Config fields

| Field | Meaning |
| --- | --- |
| `provider` | `fireworks` or `openrouter`. |
| `eval-model` | Original Hugging Face eval checkpoint; selects its inference profile and labels experiment results. |
| `enabled` | True only for a verified catalog mapping. Consumers must reject false entries. |
| `model` | Exact provider API ID, or null when no mapping is verified. Replace with the account deployment inference ID for Fireworks when required. |
| `base-url` | Provider OpenAI-compatible API root ending in `/v1`. |
| `api-key-env` | Environment variable name, never a secret value: FIREWORKS_API_KEY or OPENROUTER_API_KEY. |
| `availability` | `catalog-listed`, `not-listed` in the checked OpenRouter catalog, or `not-verified` for an unverified Fireworks mapping. |
| `checked-on` | Date the source was checked. Recheck before live experiments. |
| `source` | Provider page/catalog supporting the mapping or availability check. |
| `deployment-type` | Fireworks on-demand deployment for mapped models. Catalog listing does not mean an active account endpoint. |
| `provider-hf-model` | Optional publisher alias used by OpenRouter for the two Llama 3.1 checkpoints. |
| `notes` | Identity/activation caveats and unresolved mapping guidance. |

Sampling, supported languages, system prompts and `n_turns: 1` stay in
`../../../inference/eval_models/`. Deployment/GPU settings are not API parameters.
The generation runner currently supports vLLM and native Gemini; these profiles
do not add Fireworks/OpenRouter runtime adapters.

## Mapping inventory

| Eval model | Fireworks model | OpenRouter model |
| --- | --- | --- |
| `BhabhaAI/Gajendra-v0.1` | Disabled; unverified | Disabled; not listed |
| `CoRover/BharatGPT-3B-Indic` | Disabled; unverified | Disabled; not listed |
| `CohereLabs/aya-23-35B` | Disabled; unverified | Disabled; not listed |
| `CohereLabs/aya-23-8B` | Disabled; unverified | Disabled; not listed |
| `GenVRadmin/AryaBhatta-GemmaOrca-Merged` | Disabled; unverified | Disabled; not listed |
| `GenVRadmin/AryaBhatta-GemmaUltra-Merged` | Disabled; unverified | Disabled; not listed |
| `MBZUAI/Llama-3-Nanda-10B-Chat` | Disabled; unverified | Disabled; not listed |
| `MBZUAI-IFM/Llama-3.1-Nanda-87B-Chat` | Disabled; unverified | Disabled; not listed |
| `Qwen/Qwen2.5-72B-Instruct` | [`accounts/fireworks/models/qwen2p5-72b-instruct`](https://fireworks.ai/models/fireworks/qwen2p5-72b-instruct) | `qwen/qwen-2.5-72b-instruct` |
| `Telugu-LLM-Labs/Indic-gemma-7b-finetuned-sft-Navarasa-2.0` | Disabled; unverified | Disabled; not listed |
| `ai4bharat/Airavata` | Disabled; unverified | Disabled; not listed |
| `google/gemma-3-27b-it` | [`accounts/fireworks/models/gemma-3-27b-it`](https://fireworks.ai/models/fireworks/gemma-3-27b-it) | `google/gemma-3-27b-it` |
| `google/gemma-3-4b-it` | [`accounts/fireworks/models/gemma-3-4b-it`](https://fireworks.ai/models/fireworks/gemma-3-4b-it) | `google/gemma-3-4b-it` |
| `krutrim-ai-labs/Krutrim-2-instruct` | Disabled; unverified | Disabled; not listed |
| `large-traversaal/Qwen-2.5-14B-Hindi` | Disabled; unverified | Disabled; not listed |
| `meta-llama/Llama-3.1-70B-Instruct` | [`accounts/fireworks/models/llama-v3p1-70b-instruct`](https://fireworks.ai/models/fireworks/llama-v3p1-70b-instruct) | `meta-llama/llama-3.1-70b-instruct` |
| `meta-llama/Llama-3.1-8B-Instruct` | [`accounts/fireworks/models/llama-v3p1-8b-instruct`](https://fireworks.ai/models/fireworks/llama-v3p1-8b-instruct) | `meta-llama/llama-3.1-8b-instruct` |
| `meta-llama/Llama-3.2-3B-Instruct` | [`accounts/fireworks/models/llama-v3p2-3b-instruct`](https://fireworks.ai/models/fireworks/llama-v3p2-3b-instruct) | `meta-llama/llama-3.2-3b-instruct` |
| `meta-llama/Llama-3.3-70B-Instruct` | [`accounts/fireworks/models/llama-v3p3-70b-instruct`](https://fireworks.ai/models/fireworks/llama-v3p3-70b-instruct) | `meta-llama/llama-3.3-70b-instruct` |
| `meta-llama/Meta-Llama-3-70B-Instruct` | [`accounts/fireworks/models/llama-v3-70b-instruct`](https://fireworks.ai/models/fireworks/llama-v3-70b-instruct) | Disabled; not listed |
| `meta-llama/Meta-Llama-3-8B-Instruct` | [`accounts/fireworks/models/llama-v3-8b-instruct-hf`](https://fireworks.ai/models/fireworks/llama-v3-8b-instruct-hf) | Disabled; not listed |
| `nvidia/Nemotron-4-Mini-Hindi-4B-Instruct` | Disabled; unverified | Disabled; not listed |
| `sarvamai/sarvam-m` | Disabled; unverified | Disabled; not listed |

No disabled profile invents an endpoint ID. For a custom deployment, confirm the
exact checkpoint, then update its model, enabled/status fields and evidence. Do
not replace Aya-23 with Aya Expanse, Nemotron Hindi with another Nemotron, or an
Indic fine-tune with its base model. Keep hosted-provider results separate from
local vLLM results: templates, quantization, safety filtering and routing can differ.

See [configuration overview](../../../README.md), [generation guide](../../../../SKILLS/generate_response.md)
and [the main README](../../../../README.md#hosted-api-access-for-open-weight-models).
