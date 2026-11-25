---
tags:
  - '#research'
  - '#agent-owned-models'
date: '2026-10-25'
modified: '2026-10-25'
body_schema: 'body-v2'
body_hash: 'sha256:467b2522f4df3c0b8730048b4c5edb39bb4c83bac8e9f9f68b60f95caf72699a'
related: []
---

# `agent-owned-models` research: `Hosted models declared without vision`

Question: does cadrumo-agent's catalogue (commit `821f4ff`) state which hosted models read images? It matters because ADR constraint 6 and its 2026-10-25 amendment admit only a model the catalogue marks vision-capable for the vision role. Conclusion: the catalogue states vision for no hosted model. That is a gap in how it compiles its sources, not a fact about the models. Both of its aggregate sources and the vendors' own documentation state image input for most hosted models, Claude and GPT included. Until the gap closes, Cadrumo's vision role can be set only on the local Ollama lane.

## Findings

### Every hosted model in the declared catalogue has vision null

cadrumo-agent's `providers --declared --json` at `821f4ff` gives 13 lanes. Only `ollama_api` states vision: 2 models true, 2 false. All other lanes report `vision: null` for every model, 180 models in total: `claude_api` 13, `claude_cli` 4, `codex_api` 79, `codex_cli` 8, `qwen_cli` 22, `zhipu_cli` 24, `zai_cli` 8, `kimi_cli` 6, `moonshot_cli` 6, `deepseek_cli` 2, `minimax_cli` 2 and `antigravity_cli` 6. Yet the same lanes declare `background.inputs` including `image`, so the lane carries images while no model on it is said to read them.

### The compiler never reads the input-modality fields its sources carry

The metadata compiler reads two aggregates: models.dev (`dev/provider_metadata/sources.py:79`) and the LiteLLM price file (`sources.py:81-82`).
- **models.dev:** the parser models only `modalities.output` (`dev/provider_metadata/aggregates.py:40-41`). From it, it derives `text_only` (`aggregates.py:55-57`, `:98`).
- **LiteLLM:** the parser reads `supported_output_modalities` only (`aggregates.py:156`, `:211`). It ignores `supports_vision`.
- **The merge:** it takes vision only from voices that set `facts.vision` (`dev/provider_metadata/merge.py:343-347`). In practice that is the Ollama registry voice alone, which leaves every hosted model null.

### Both sources state image input for most of those models, and never disagree

Both documents were fetched on 2026-10-25: https://models.dev/api.json and https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json. Each declared model id was matched against the provider groups the lane plan names (`dev/provider_metadata/lanes.py:124-179`). For models.dev that is `modalities.input` containing `image`; for LiteLLM it is `supports_vision`.

| Lane | Models | Image input stated true | Stated false | Neither source states it |
| --- | --- | --- | --- | --- |
| claude_api | 13 | 13 | 0 | 0 |
| codex_api | 79 | 72 | 4 | 3 |
| codex_cli | 8 | 8 | 0 | 0 |
| kimi_cli | 6 | 6 | 0 | 0 |
| moonshot_cli | 6 | 6 | 0 | 0 |
| minimax_cli | 2 | 2 | 0 | 0 |
| qwen_cli | 22 | 17 | 5 | 0 |
| zhipu_cli | 24 | 5 | 10 | 9 |
| zai_cli | 8 | 2 | 6 | 0 |
| deepseek_cli | 2 | 1 | 1 | 0 |
| claude_cli | 4 | 0 | 0 | 4 |

Where both sources state the fact, they agree for every model. The rows include false as well as true, so reading the fields would also mark the text-only models correctly, not just add vision everywhere.

### Vendor documentation agrees

- **Anthropic:** the vision guide splits image resolution into two tiers, "Claude 4.7 and later models" and "All other models". So it describes image input for every Claude model, and its examples use `claude-opus-5-5`. https://platform.claude.com/docs/en/build-with-claude/vision
- **OpenAI:** the vision guide lists as vision models gpt-6-astra, the gpt-5.6 family (sol, terra, luna), gpt-5.5, the gpt-5.4 family, gpt-5.2, gpt-5.1, gpt-4.1 and gpt-4o. It points to the models page for the full modality list. https://developers.openai.com/api/docs/guides/images-vision

### The CLI aliases need their own source

`claude_cli` lists the aliases `fable`, `haiku`, `opus` and `sonnet`, which neither aggregate keys. Each alias resolves to a Claude model the vision guide covers. Stating vision for them needs either an alias-to-model mapping cadrumo-agent already holds or a documented manual fact. Joining by name similarity would be guesswork, so it is not an option.

### Consequence for Cadrumo

With the gap, Cadrumo's vision role is effectively local-only. `vision_required` refuses every hosted model (`src/cadrumo_agent_service/providers/application/model_role_selections.py`), even ones the vendors document as reading images. Once cadrumo-agent states vision, the role can name a hosted model with no Cadrumo change. Such a model reads off the host, so off-host consent applies (ADR constraint 4).

What the fix must settle, and who owns it: cadrumo-agent owns its metadata compile, so the change is that project's decision. Cadrumo neither patches nor overrides catalogue facts (ADR constraint 1).
- **Source precedence:** a model the two aggregates disagree on, should one ever appear.
- **CLI aliases:** how they get a vision fact.
- **Lane coverage:** whether a lane whose transport carries no images (`antigravity_cli`, empty `background.inputs`) should still report a model's vision.

Not investigated:
- the PDF capability per model;
- whether each lane's transport passes images through for every model it lists.

## Sources

- `Y:\code\cadrumo-agent-worktrees\main` at `821f4ff`: `dev/provider_metadata/sources.py:79-82`, `dev/provider_metadata/aggregates.py:40-57`, `:98`, `:156`, `:211`, `dev/provider_metadata/merge.py:343-347`, `dev/provider_metadata/lanes.py:124-179`.
- `cadrumo-agent providers --declared --json` at `821f4ff`, run on 2026-10-25.
- https://models.dev/api.json, fetched 2026-10-25.
- https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json, fetched 2026-10-25.
- https://platform.claude.com/docs/en/build-with-claude/vision
- https://developers.openai.com/api/docs/guides/images-vision
