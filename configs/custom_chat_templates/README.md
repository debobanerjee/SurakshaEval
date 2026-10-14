# Custom chat templates

These five repository-authored templates preserve the existing single-turn text
safety prompt formats in `configs/inference/eval_models/` for Gajendra, Airavata,
the two AryaBhatta models, and Indic-Gemma Navarasa. They support one user message
and an optional system message, omit empty system prompts, and reject tool or
multi-turn input.

Only models configured with custom prompting have local template files. Meta and
other models use their tokenizer-provided chat templates without local copies or
`chat-template` overrides.

Run vLLM from the repository root to resolve configured template paths. Do not
preformat a prompt and then apply its chat template again.

`pipeline/run-deployment.sh` resolves the repository root before starting vLLM.
`pipeline/generate-responses.py` sends text messages to that server and counts
rendered tokens through `/tokenize`; it never applies the Jinja template a second
time. Gemini generation uses the provider API and does not use these templates.
See [generation](../../SKILLS/generate_response.md) and
[the pipeline reference](../../docs/pipeline.md) for input, output and `--retry`.
