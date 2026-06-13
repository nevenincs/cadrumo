---
tags:
  - '#audit'
  - '#llm-evidence-classification'
date: '2026-06-12'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
  - "[[2026-06-11-llm-evidence-classification-audit]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace llm-evidence-classification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `llm-evidence-classification` audit: `Plan closeout: 9 remaining-item disposition`

## Scope

Closeout pass over the nine open Steps of the Stage-3 evidence-aware LLM
classification plan: `W02.P05.S17`-`S20` (on-host vision reader plus cache key),
`W03.P08.S32` (nitpicky docs-build gate), and `W04.P09.S34`-`S37` (real
cloud-CLI persona rolls). Goal: complete only real remaining work, preserve
strict evidence semantics, and record an honest disposition for each item.
`W05` was already retired and `W04.P09.S38` (capture the persona testimonial)
was already closed by the round-1 persona audit.

## Findings

### W02.P05.S17 — LocalAdapter Ollama images + on-host PDF rasterisation — COMPLETED

Added an `images` base64 field to `ProviderRequest`, forwarded it on the Ollama
`messages[].images` field in `LocalAdapter.complete`, switched the chat URL to a
per-call `load_settings()` read, and added `rasterise_pdf_pages_to_base64_png`
(pypdfium2 + Pillow, in-memory, no temp file). Files: `_providers/local.py`,
`_providers/base.py`. Verified by `test_local_vision.py`; ruff + ty clean.

### W02.P05.S18 — fold Attachment sha256 into the cache key — COMPLETED

Added the frozen `MultimodalImageInput` model (`content_sha256` + `repr`-hidden
`base64_data`) and an `images` field on `LLMRequest`; `LLMCache.build_key` now
folds each `content_sha256` into `args_payload`; `LLMClient` threads images to
`ProviderRequest`; the model is re-exported from the package root. Files:
`_models.py`, `_cache.py`, `_client.py`, `__init__.py`. Only the content
address (never the bytes) enters the key.

### W02.P05.S19 — cache-key collision test — COMPLETED

`test_cache_key_distinguishes_multimodal_evidence` proves two evidence
documents under one prompt yield distinct keys and that the same content
address reproduces the same key. File: `tests/test_cache.py`.

### W02.P05.S20 — on-host vision read test — COMPLETED

`test_local_vision.py` rasterises a scan-only PDF in memory and drives
`LocalAdapter` against a loopback Ollama-shaped HTTP server, asserting the
base64 images reach the request body with no byte leaving `127.0.0.1`.

### W03.P08.S32 — nitpicky docs-build gate — BLOCKED (peer-owned drift), owner surface clean

`apidocs scaffold --check` reports drift of 2 missing and 2 stale stubs, all in
peer-owned modules (`aeat.application.modelo._dt12_advisory`,
`aeat.application.overview._calendar_models`) from concurrent campaigns — none
in the `adapters/outbound/llm` surface this closeout touched. The W02.P05 change
adds no new module (only symbols to existing modules) so it contributes zero
stub drift, and its new docstrings use no Sphinx cross-reference roles (the one
dotted `:class:` draft was reduced to plain prose to keep `-n -W` green). Per
the `full-tree-gate-must-distinguish-owner` rule the red full-tree docs-build is
peer-owned, not this feature's; the Step is left open rather than falsely
checked, and the peer modules are NOT scaffolded here (they belong to active
peer campaigns).

### W04.P09.S34–S37 — real cloud-CLI persona rolls — BLOCKED / DEFERRED

These are hands-on operator rolls against real authenticated cloud CLIs
(`agy`/`codex`), not automated tests, and remain blocked by two live defects
re-confirmed at HEAD:

- **F3 (transient peer WIP, still live):** `from ._ledger_payloads import
  LedgerClassifyResult` still raises `ImportError` at HEAD — the peer refactor of
  `_ledger_payloads.py` has not settled, so `classify --llm` cannot even import.
  S35/S36 cannot run until it lands.
- **F2 (pre-existing architecture defect):** the evidence-aware flow is split
  across two stores — `evidence add` writes the purchase-invoice-evidence store
  while `attach`/`classify --read-evidence` disagree on which store holds a
  readable invoice — so the documented operator flow cannot be driven end to end.
  The round-1 audit already records this needs an ADR.

S34 (profile setup, import, attach) is partially exercisable but the end-to-end
classify/split rolls (S35–S37) depend on F3 settling and F2 being resolved. They
are deferred to a follow-up persona round, not completed or faked.

## Recommendations

- Re-run the cloud-classify persona legs (S35–S37) once the peer
  `_ledger_payloads.py` refactor lands `LedgerClassifyResult` (F3) and the F2
  two-store split is resolved by ADR; until then they stay open.
- Resolve S32 by scaffolding the two missing peer stubs in the campaigns that
  own `_dt12_advisory` and `_calendar_models`, then re-run the docs-build gate;
  do not scaffold them from this feature.
- Commit the W02.P05 surface (six source/test files) independently of the still
  un-landed peer `_ledger_payloads.py` work to avoid bundling peer WIP.
- Plan is NOT closed: four of nine Steps land (S17–S20); S32 and S34–S37 remain
  open with the blockers recorded above.

## Codification candidates

<!-- Findings that satisfy the three durability criteria
(cross-session, constraint-shaped, project-bound) and should be
promoted into project-shared rules under `.vaultspec/rules/rules/`
(the directory the CLI's `vaultspec-core spec rules add` writes to today; the
planned `--scope project` flag will move authored rules under
`.vaultspec/rules/rules/project/`).

Each candidate names the finding it derives from, the proposed
rule slug (kebab-case, naming the constraint's subject not the
failure), and a one-sentence statement of the rule.

Most audits produce zero codification candidates. Some produce one.
Only the rare framework-wide-pattern audit produces several. If
none of the findings above meet the bar, state that explicitly and
move on -- an empty Codification candidates section is a positive
signal, not a failure. -->

None. This closeout surfaced no new cross-session, constraint-shaped,
project-bound lesson: S17–S20 are ordinary feature completion; S32 and
S34–S37 are owner-triage and blocked-dependency dispositions already covered by
`full-tree-gate-must-distinguish-owner` and the round-1 audit's F2/F3
recommendations. The earlier `cli-payload-schema-mirrors-emitted-record`
candidate (F1) still awaits a second occurrence before promotion.
