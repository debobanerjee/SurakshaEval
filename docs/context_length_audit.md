# Evaluated-model context audit

Checked 2026-10-14 for all 27 evaluated checkpoints. **Not every model supports
8192**: Gajendra, Airavata, and Nemotron Hindi specify 4096. Their local deployment
configs now use 4096; other local configs retain 8192. Three checkpoints have
unverified exact limits, with publisher evidence for the two Nanda models.

For local vLLM, context means the full rendered prompt plus generated tokens.
A requested output budget of 4096 leaves no room for a prompt inside a 4096
context. Reduce output requests to fit the remaining budget after counting system
text, user text, and template tokens. Existing profile max_tokens values are
unchanged; the evaluation runner must enforce this budget.

| Evaluated model | Published/config limit (tokens) | Supports 8192? | Evidence and caveats |
| --- | --- | --- | --- |
| `BhabhaAI/Gajendra-v0.1` | 4,096 (config) | No | Exact checkpoint max_position_embeddings. [config](https://huggingface.co/BhabhaAI/Gajendra-v0.1/resolve/main/config.json) |
| `CoRover/BharatGPT-3B-Indic` | Unverified | Unverified | Exact config access returned 401; public card has no explicit context limit. Do not infer from parameter count. [card](https://huggingface.co/CoRover/BharatGPT-3B-Indic) |
| `CohereLabs/aya-23-35B` | 8,192 | Yes | Exact model card explicitly states context; gated config unavailable. [card](https://huggingface.co/CohereLabs/aya-23-35B) |
| `CohereLabs/aya-23-8B` | 8,192 | Yes | Exact model card explicitly states context; gated config unavailable. [card](https://huggingface.co/CohereLabs/aya-23-8B) |
| `GenVRadmin/AryaBhatta-GemmaOrca-Merged` | 8,192 (config) | Yes (config) | Exact checkpoint max_position_embeddings. [config](https://huggingface.co/GenVRadmin/AryaBhatta-GemmaOrca-Merged/resolve/main/config.json) |
| `GenVRadmin/AryaBhatta-GemmaUltra-Merged` | 8,192 (config) | Yes (config) | Exact checkpoint max_position_embeddings. [config](https://huggingface.co/GenVRadmin/AryaBhatta-GemmaUltra-Merged/resolve/main/config.json) |
| `MBZUAI-IFM/Llama-3.1-Nanda-87B-Chat` | Exact limit unverified | Publisher evidence; confirm config | Nanda-87B example requests 8192 output tokens; this suggests support but does not declare a maximum context. Exact config returned 401. [publisher card](https://huggingface.co/MBZUAI-IFM/Llama-3.1-Nanda-87B-Chat/blame/main/README.md) |
| `MBZUAI/Llama-3-Nanda-10B-Chat` | Exact limit unverified | Publisher evidence; confirm config | Publisher states Nanda-10B cannot exceed 8192 at inference, consistent with an 8192 limit; exact 10B config returned 401. [publisher card](https://huggingface.co/MBZUAI-IFM/Llama-3.1-Nanda-87B-Chat/blame/main/README.md) |
| `Qwen/Qwen2.5-72B-Instruct` | 32,768 (config) | Yes (config) | 32768 directly supported; card advertises 131072 with YaRN. No extension needed for 8192. [config](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct/resolve/main/config.json) |
| `Telugu-LLM-Labs/Indic-gemma-7b-finetuned-sft-Navarasa-2.0` | 8,192 (config) | Yes (config) | 8192 in config; card example uses max_seq_length=2048, which is not proof of an architectural cap. Long-context quality untested. [config](https://huggingface.co/Telugu-LLM-Labs/Indic-gemma-7b-finetuned-sft-Navarasa-2.0/resolve/main/config.json); [card](https://huggingface.co/Telugu-LLM-Labs/Indic-gemma-7b-finetuned-sft-Navarasa-2.0) |
| `ai4bharat/Airavata` | 4,096 | No | Published config has max_position_embeddings=4096 and no RoPE scaling. [config](https://huggingface.co/ai4bharat/Airavata/blob/main/config.json) |
| `gemini-2.5-flash` | 1M input / 64k output | Yes | Provider manages separate input/output limits; apply the experiment budget in the client. [provider docs](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash) |
| `gemini-2.5-pro` | 1M input / 64k output | Yes | Provider manages separate input/output limits; apply the experiment budget in the client. [provider docs](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-pro) |
| `gemini-3-flash-preview` | 1M input / 64k output | Yes | Provider manages separate input/output limits; apply the experiment budget in the client. [provider docs](https://ai.google.dev/gemini-api/docs/gemini-3) |
| `gemini-3-pro-preview` | 1M input / 64k output | Historically yes; shut down | Exact API ID shut down 2026-03-09. Do not silently substitute a different model. [provider docs](https://ai.google.dev/gemini-api/docs/models/gemini-3-pro-preview) |
| `google/gemma-3-27b-it` | 128K input | Yes | Card covers configured 4B/27B checkpoints; output limit is separately documented. [card](https://huggingface.co/google/gemma-3-27b-it) |
| `google/gemma-3-4b-it` | 128K input | Yes | Card covers configured 4B/27B checkpoints; output limit is separately documented. [card](https://huggingface.co/google/gemma-3-4b-it) |
| `krutrim-ai-labs/Krutrim-2-instruct` | 128K (card); 1,024,000 (config) | Yes (config) | Prefer publisher-supported 128K over larger config value. sliding_window=4096 is local attention, not a total-context cap. [config](https://huggingface.co/krutrim-ai-labs/Krutrim-2-instruct/resolve/main/config.json); [card](https://huggingface.co/krutrim-ai-labs/Krutrim-2-instruct) |
| `large-traversaal/Qwen-2.5-14B-Hindi` | 32,768 (config) | Yes (config) | Exact checkpoint max_position_embeddings. [config](https://huggingface.co/large-traversaal/Qwen-2.5-14B-Hindi/resolve/main/config.json) |
| `meta-llama/Llama-3.1-70B-Instruct` | 128K | Yes | Publisher model card states context; gated config unavailable. [card](https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct) |
| `meta-llama/Llama-3.1-8B-Instruct` | 128K | Yes | Publisher model card states context; gated config unavailable. [card](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) |
| `meta-llama/Llama-3.2-3B-Instruct` | 128K | Yes | Publisher model card states context; gated config unavailable. [card](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct) |
| `meta-llama/Llama-3.3-70B-Instruct` | 128K | Yes | Publisher model card states context; gated config unavailable. [card](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct) |
| `meta-llama/Meta-Llama-3-70B-Instruct` | 8,192 | Yes | Publisher model card states context; gated config unavailable. [card](https://huggingface.co/meta-llama/Meta-Llama-3-70B-Instruct) |
| `meta-llama/Meta-Llama-3-8B-Instruct` | 8,192 | Yes | Publisher model card states context; gated config unavailable. [card](https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct) |
| `nvidia/Nemotron-4-Mini-Hindi-4B-Instruct` | 4,096 (config) | No | Both config and publisher card specify 4096. [config](https://huggingface.co/nvidia/Nemotron-4-Mini-Hindi-4B-Instruct/resolve/main/config.json); [card](https://huggingface.co/nvidia/Nemotron-4-Mini-Hindi-4B-Instruct) |
| `sarvamai/sarvam-m` | 32,768 (config) | Yes (config) | Exact checkpoint max_position_embeddings. [config](https://huggingface.co/sarvamai/sarvam-m/resolve/main/config.json) |

## Experiment implications

A larger max-model-len does not validate context extension. Do not force an
extension merely to make short-context checkpoints match an 8192 experiment.
If equal total-context budgets are required, consider 4096 across models after
resolving the unverified checkpoints; otherwise report per-model limits.

Hosted APIs expose separate input/output limits; apply experimental token budgets
in the client. Gemini 3 Pro Preview's documented capacity is historical: its exact
configured API ID has been shut down. The model selection has been preserved.

Public config JSON files were read without downloading weights. Gated files
returned HTTP 401; explicit public cards were used when available. Architecture
family, tokenizer sentinel limits, and example max_new_tokens values alone do
not verify a checkpoint's maximum context. No GPU startup or long-context quality
test was run. Support for context does not guarantee capacity at the configured
concurrency and hardware settings.

## Pipeline integration

Use [the pipeline reference](pipeline.md) for dataset/checkpoint downloads,
vLLM/Gemini generation, async/Batch judging, final verdicts and `--retry`.
The generation runner uses the selected deployment's context/port/template
settings and records actual token budgets. Audits describe configuration evidence;
mocked tests do not verify GPU serving or live provider availability.
