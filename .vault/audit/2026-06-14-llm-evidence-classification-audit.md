---
tags:
  - '#audit'
  - '#llm-evidence-classification'
date: '2026-06-14'
modified: '2026-06-14'
related:
  - "[[2026-06-13-llm-evidence-classification-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace llm-evidence-classification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `llm-evidence-classification` audit: `Live local-vision classification verified end to end (qwen2.5vl)`

## Scope

End-to-end live verification of the on-host vision classification pipeline against
a real local Ollama vision model, plus implementation of operator model selection
(`--vision-model`, e.g. `qwen2.5vl:7b`). Ollama was provisioned on the host and
`qwen2.5vl:3b` pulled; the full `classify --read-evidence` flow was driven through
the real CLI against the real model.

## Findings

### PASS — full live pipeline end to end against `qwen2.5vl:3b`

In an isolated storage root with `AEAT_EVIDENCE_GESTOR_MODE=1` (cloud barred), the
real CLI drove: headless profile create, statement import, `evidence add` of a
real public-domain invoice image, `attach`, then `classify --read-evidence
--saturate --apply` with NO `--llm` provider. The local model read the invoice and
the result stamped `clasificado-por: llm:local-vision:qwen2.5vl:3b`, classified
BUSINESS with a model-selected IVA category, and the regulated base/rate/amount
were system-derived from the gross (the model emitted no number). The evidence
link rendered in `view` and review status was `reviewed`. This confirms the ADR
posture: a gestor reads scanned/image evidence on-host with no upload and no
provider.

### FOUND + FIXED — Ollama 400 exceed-context on the full vision prompt

The first live run failed with a 400 `exceed_context_size_error` (5798 tokens >
4096): the registry allow-list prompt plus the encoded invoice image overflow
Ollama's 4096 default context. Fixed by sending a configurable `num_ctx`
(`aeat_llm_ollama_num_ctx`, default 8192) on local requests. A dedicated vision
timeout (`aeat_llm_vision_read_timeout_s`, default 300s) was also added because a
local vision model on consumer hardware takes ~1 minute per invoice (the general
60s LLM timeout was too short).

### IMPLEMENTED — `--vision-model` operator override (`qwen2.5vl:7b`)

`classify` and `split` gained `--vision-model`, threaded through
suggest/saturate/split to `LocalVisionLLMClassifier(model=...)`, overriding the
settings default per invocation. A real-behaviour test proves the flag routes the
named model to the request and the `llm:local-vision:<model>` provenance. `split`
also gained the provider-optional `--read-evidence` routing (consistent with
`classify`).

### DEFERRED (infra, not code) — pulling the `qwen2.5vl:7b` weights

`qwen2.5vl:7b` support is code-complete and tested, but pulling the ~6 GB weights
into Ollama stalled on the manifest stage on this host (the manifest itself
resolves HTTP 200 from the registry; the `3b` pull succeeded, so it is an
Ollama-pull/host transient, not a code or registry-availability problem). An
operator with an 8 GB+ GPU runs `ollama pull qwen2.5vl:7b` then
`classify --read-evidence --vision-model qwen2.5vl:7b`.

## Recommendations

- Operators with a GPU should `ollama pull qwen2.5vl:7b` and pass
  `--vision-model qwen2.5vl:7b` for stronger OCR on dense invoices; CPU-only
  operators can use `moondream`. The defaults (`qwen2.5vl:3b`, `num_ctx` 8192,
  300s vision timeout) are tuned for normal consumer hardware.
- No action on the `7b` weights-pull stall — it is an Ollama-pull/host transient;
  retry the pull. The code path is verified by the model-override test.

## Codification candidates

<!-- Findings that satisfy the three durability criteria
(cross-session, constraint-shaped, project-bound) and should be
promoted into project-shared rules under `.vaultspec/rules/rules/`
via `vaultspec-core vault rule promote --from <this-audit-stem>
--as <rule-name>`.

Each candidate names the finding it derives from, the proposed
rule slug (kebab-case, naming the constraint's subject not the
failure), and a one-sentence statement of the rule.

Most audits produce zero codification candidates. Some produce one.
Only the rare framework-wide-pattern audit produces several. If
none of the findings above meet the bar, state that explicitly and
move on -- an empty Codification candidates section is a positive
signal, not a failure. -->

None. This is a live-verification + feature pass; it surfaced a concrete config
fix (num_ctx) and a model-selection flag, neither of which is a durable
cross-session rule.
