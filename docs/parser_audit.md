# Model-card and parser audit

Reviewed 2026-10-14 against the 27 configured evaluated models. Public model cards
were checked for 22 open-weight checkpoints; Nanda-87B's exact card was unavailable
(HTTP authorization/retrieval errors), so its [publisher repository](https://github.com/MBZUAI-IFM/Nanda-Family)
was checked as a fallback. Google provider documentation covers the four Gemini IDs.

The audit separates documented model capability from a compatible output parser.
Absent documentation is recorded as unverified, not proof that a model cannot use
tools or reason. Model names, reasoning benchmark scores, and base architectures
alone do not establish a structured-thinking or tool serialization format.

Six local configs enable tool parsing. No local reasoning parser is enabled:
the only checkpoint documenting a separate thinking channel here is Sarvam-M,
whose marker/tokenizer format does not satisfy the examined built-in parser.
Preserve its raw generated text, including thinking, until a compatible parser
is implemented and validated. Do not silently drop reasoning from safety results.

| Evaluated checkpoint / model-card source | Tool parser | Reasoning parser | Recipe | Decision evidence |
| --- | --- | --- | --- | --- |
| [BhabhaAI/Gajendra-v0.1](https://huggingface.co/BhabhaAI/Gajendra-v0.1) | Omitted | Omitted | No exact recipe found | Card does not document a verified structured tool/thinking output format. |
| [CoRover/BharatGPT-3B-Indic](https://huggingface.co/CoRover/BharatGPT-3B-Indic) | Omitted | Omitted | No exact recipe found | Card does not document a verified structured tool/thinking output format. |
| [CohereLabs/aya-23-35B](https://huggingface.co/CohereLabs/aya-23-35B) | Omitted | Omitted | No exact recipe found | Card does not document a verified structured tool/thinking output format. |
| [CohereLabs/aya-23-8B](https://huggingface.co/CohereLabs/aya-23-8B) | Omitted | Omitted | No exact recipe found | Card does not document a verified structured tool/thinking output format. |
| [GenVRadmin/AryaBhatta-GemmaOrca-Merged](https://huggingface.co/GenVRadmin/AryaBhatta-GemmaOrca-Merged) | Omitted | Omitted | No exact recipe found | Card does not document a verified structured tool/thinking output format. |
| [GenVRadmin/AryaBhatta-GemmaUltra-Merged](https://huggingface.co/GenVRadmin/AryaBhatta-GemmaUltra-Merged) | Omitted | Omitted | No exact recipe found | Card does not document a verified structured tool/thinking output format. |
| [MBZUAI/Llama-3-Nanda-10B-Chat](https://huggingface.co/MBZUAI/Llama-3-Nanda-10B-Chat) | Omitted | Omitted | No exact recipe found | Card does not document a verified structured tool/thinking output format. |
| [MBZUAI-IFM/Llama-3.1-Nanda-87B-Chat](https://huggingface.co/MBZUAI-IFM/Llama-3.1-Nanda-87B-Chat) | Omitted | Omitted | No exact recipe found | Exact model card could not be retrieved; publisher Nanda repository checked as fallback. No checkpoint parser verified. |
| [Qwen/Qwen2.5-72B-Instruct](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct) | `hermes` | Omitted | No exact recipe found | vLLM documents Qwen2.5 Hermes tools; exact tokenizer template contains tools and <tool_call> markers. |
| [Telugu-LLM-Labs/Indic-gemma-7b-finetuned-sft-Navarasa-2.0](https://huggingface.co/Telugu-LLM-Labs/Indic-gemma-7b-finetuned-sft-Navarasa-2.0) | Omitted | Omitted | No exact recipe found | Card does not document a verified structured tool/thinking output format. |
| [ai4bharat/Airavata](https://huggingface.co/ai4bharat/Airavata) | Omitted | Omitted | No exact recipe found | Card does not document a verified structured tool/thinking output format. |
| [gemini-2.5-flash](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash) | Provider API | Provider API | Not applicable | Provider docs document function calls and thinking; no local vLLM parser. Preview model availability must be checked with the account. |
| [gemini-2.5-pro](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-pro) | Provider API | Provider API | Not applicable | Provider docs document function calls and thinking; no local vLLM parser. Preview model availability must be checked with the account. |
| [gemini-3-flash-preview](https://ai.google.dev/gemini-api/docs/gemini-3) | Provider API | Provider API | Not applicable | Provider docs document function calls and thinking; no local vLLM parser. Preview model availability must be checked with the account. |
| [gemini-3-pro-preview](https://ai.google.dev/gemini-api/docs/gemini-3) | Provider API | Provider API | Not applicable | Provider docs document function calls and thinking; no local vLLM parser. Preview model availability must be checked with the account. |
| [google/gemma-3-27b-it](https://huggingface.co/google/gemma-3-27b-it) | Omitted | Omitted | No exact recipe found | Card does not document a verified structured tool/thinking output format. |
| [google/gemma-3-4b-it](https://huggingface.co/google/gemma-3-4b-it) | Omitted | Omitted | No exact recipe found | Card does not document a verified structured tool/thinking output format. |
| [krutrim-ai-labs/Krutrim-2-instruct](https://huggingface.co/krutrim-ai-labs/Krutrim-2-instruct) | Omitted | Omitted | No exact recipe found | Card does not document a verified structured tool/thinking output format. |
| [large-traversaal/Qwen-2.5-14B-Hindi](https://huggingface.co/large-traversaal/Qwen-2.5-14B-Hindi) | `hermes` | Omitted | No exact recipe found | Card has no tool claim; exact tokenizer retains Hermes tools. Enabled as a format match; capability remains unvalidated. |
| [meta-llama/Llama-3.1-70B-Instruct](https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct) | `llama3_json` | Omitted | [Family recipe](https://github.com/vllm-project/recipes/blob/main/Llama/Llama3.1.md) | Tools documented by Meta; JSON parser matches vLLM guidance; tokenizer-provided chat template retained for safety inference. |
| [meta-llama/Llama-3.1-8B-Instruct](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) | `llama3_json` | Omitted | [Exact recipe](https://recipes.vllm.ai/meta-llama/Llama-3.1-8B-Instruct) | Tools documented by Meta; JSON parser matches vLLM guidance; tokenizer-provided chat template retained for safety inference. |
| [meta-llama/Llama-3.2-3B-Instruct](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct) | `llama3_json` | Omitted | [Exact recipe](https://recipes.vllm.ai/meta-llama/Llama-3.2-3B-Instruct) | Tools documented by Meta; JSON parser matches vLLM guidance; tokenizer-provided chat template retained for safety inference. |
| [meta-llama/Llama-3.3-70B-Instruct](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct) | `llama3_json` | Omitted | [Exact recipe](https://recipes.vllm.ai/meta-llama/Llama-3.3-70B-Instruct) | Tools documented by Meta; JSON-format match to Llama parser is an inference, not a checkpoint-specific runtime validation. |
| [meta-llama/Meta-Llama-3-70B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3-70B-Instruct) | Omitted | Omitted | No exact recipe found | Card does not document a verified structured tool/thinking output format. |
| [meta-llama/Meta-Llama-3-8B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct) | Omitted | Omitted | No exact recipe found | Card does not document a verified structured tool/thinking output format. |
| [nvidia/Nemotron-4-Mini-Hindi-4B-Instruct](https://huggingface.co/nvidia/Nemotron-4-Mini-Hindi-4B-Instruct) | Omitted | Omitted | No exact recipe found | Card does not document a verified structured tool/thinking output format. |
| [sarvamai/sarvam-m](https://huggingface.co/sarvamai/sarvam-m) | Omitted | Omitted: incompatible built-in | No exact recipe found | Card documents thinking; neither thinking marker is an atomic vocabulary entry. DeepSeek R1 built-in initialization would reject this tokenizer. |

## Implementation sources

- [vLLM tool calling](https://docs.vllm.ai/en/latest/features/tool_calling/): Llama JSON/Python and Qwen Hermes parser/template requirements.
- [vLLM reasoning outputs](https://docs.vllm.ai/en/latest/features/reasoning_outputs/): supported built-in reasoning parsers.
- [DeepSeek R1 parser](https://github.com/vllm-project/vllm/blob/main/vllm/reasoning/deepseek_r1_reasoning_parser.py) uses `<think>` and `</think>`.
- [Base thinking parser](https://github.com/vllm-project/vllm/blob/main/vllm/reasoning/basic_parsers.py) requires those markers to exist as individual vocabulary entries.
- Sarvam-M's [tokenizer config](https://huggingface.co/sarvamai/sarvam-m/blob/main/tokenizer_config.json) and [tokenizer vocabulary](https://huggingface.co/sarvamai/sarvam-m/blob/main/tokenizer.json) were inspected; both exact marker lookups returned no token ID.
- [Official recipe catalog](https://recipes.vllm.ai/browse) and [upstream recipes](https://github.com/vllm-project/recipes) were checked. Recipes for newer Gemma, Qwen, or Nemotron models were not substituted for these older checkpoints.

## Chat templates and experimental behavior

Five repository-authored templates preserve the original single-turn text formats
for Gajendra, Airavata, the two AryaBhatta checkpoints, and Indic-Gemma Navarasa.
Meta models use their tokenizer-provided chat templates without local copies or
`chat-template` overrides, matching their inference profiles. Llama 3.2 uses the
JSON parser rather than the Pythonic parser, which would require a matching tool
template. Qwen configs also use their checkpoint tokenizer templates. All custom
template paths resolve from the repository root; see [supported inputs](../configs/custom_chat_templates/README.md).

Tool parsers do not execute tools. Ordinary safety requests should omit tool
schemas unless tool use is an explicit experimental condition. vLLM recommends
adapted Meta templates for tool calling; those templates are not vendored or
applied to these safety configs. A separate tool-use experiment must validate
its template/parser pairing before use. Record the checkpoint revision and
prompt format used when comparing runs.

Existing resource settings remain BF16, 0.95 GPU memory utilization, 256 sequences,
block size 256, and seed 42. Context is 8192, with 4096 for Gajendra, Airavata,
and Nemotron Hindi following the [context audit](context_length_audit.md). Recipe hardware/performance
defaults were not imported over those experimental choices.

Validation covered YAML, local path resolution, exact single-turn custom prompt
rendering (including empty system prompts and Indic text), and absence of local
Meta template overrides. No model weights or vLLM runtime were loaded;
model-generated parser behavior, attention backend/block-size support, and GPU
memory capacity still need serving smoke tests. Llama 3.3 and Hindi Qwen mappings
are explicitly format-based, rather than advertised as GPU-validated recipes.

## Pipeline integration

Use [the pipeline reference](pipeline.md) for dataset/checkpoint downloads,
vLLM/Gemini generation, async/Batch judging, final verdicts and `--retry`.
The generation runner uses the selected deployment's context/port/template
settings and records actual token budgets. Audits describe configuration evidence;
mocked tests do not verify GPU serving or live provider availability.
