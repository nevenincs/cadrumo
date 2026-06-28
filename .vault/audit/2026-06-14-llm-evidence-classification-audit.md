---
tags:
  - '#audit'
  - '#llm-evidence-classification'
date: '2026-06-14'
modified: '2026-06-15'
related:
  - "[[2026-06-13-llm-evidence-classification-adr]]"
---



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

### RESOLVED (was network-blocked) — `qwen2.5vl:7b` pulled and live-verified

`qwen2.5vl:7b` support was code-complete and tested but the ~6 GB weights pull was
previously blocked by host connectivity to Ollama's Cloudflare R2 blob CDN
(`dial tcp 172.64.66.2:443: i/o timeout` on the final blob, ~5.97 GB cached). On
2026-06-15 the network path recovered: `ollama pull qwen2.5vl:7b` resumed from the
cached blobs and completed (`success`), and the model now lists at 6.0 GB. A live
end-to-end vision classification against the real local `qwen2.5vl:7b` — feeding a
real public-domain invoice image through `LocalVisionLLMClassifier` — returned
`classification=BUSINESS`, `category=material_oficina`, `iva=domestic_general_21`,
`multiple_components=False`, stamped `llm:local-vision:qwen2.5vl:7b`. The
`--vision-model` operator path is now verified live for both `3b` and `7b`.

## Recommendations

- Operators with a GPU should `ollama pull qwen2.5vl:7b` and pass
  `--vision-model qwen2.5vl:7b` for stronger OCR on dense invoices; CPU-only
  operators can use `moondream`. The defaults (`qwen2.5vl:3b`, `num_ctx` 8192,
  300s vision timeout) are tuned for normal consumer hardware.
- The `7b` weights pull (previously blocked by the host's Cloudflare R2 path) was
  resolved on 2026-06-15: the pull completed and a live `qwen2.5vl:7b` classification
  succeeded end to end. GPU operators run `classify --read-evidence --vision-model
  qwen2.5vl:7b` for stronger OCR on dense invoices; the path is now live-verified for
  both `3b` and `7b`.

## Codification candidates


None. This is a live-verification + feature pass; it surfaced a concrete config
fix (num_ctx) and a model-selection flag, neither of which is a durable
cross-session rule.
