---
tags:
  - '#audit'
  - '#llm-evidence-classification'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
  - "[[2026-06-12-llm-evidence-classification-audit]]"
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

# `llm-evidence-classification` audit: `Persona roll round 2: full evidence-aware pipeline against real codex CLI`

## Scope

W04.P09 persona roll, round 2, after the round-1 blockers were resolved. An
operator persona drove the complete evidence-aware LLM pipeline end to end
through the real CLI against the real authenticated `codex` cloud CLI and real
text-layer purchase-invoice PDFs, in an isolated storage root
(`AEAT_LOCAL_STORAGE_ROOT` / `AEAT_SECRET_STORE_DIR` / `AEAT_BLOB_STORE_DIR` /
`AEAT_AUDIT_DIR` under a throwaway temp dir; `AEAT_EVIDENCE_CLOUD_UPLOAD_PERMITTED=1`,
`AEAT_EVIDENCE_GESTOR_MODE=0`). This is the binding fallback validation the plan
depends on, covering S34–S37.

## Findings

### Round-1 blockers F2/F3/F4 are all resolved at HEAD (confirmed by real CLI)

- **F3 (peer refactor unsettled):** resolved. The ledger CLI imports cleanly;
  `LedgerClassifyResult` was renamed during the `_ledger_payloads.py` refactor
  and no source references the old name.
- **F2 (two-store evidence split):** resolved by peer commit `1df080678` — the
  `_verify_purchase_invoice_evidence` validator now resolves the
  `PurchaseInvoiceEvidence` store (evidence-add ids) before the
  `InvoiceCatalogue`. The real-CLI roll confirmed an `evidence add` id is now
  accepted by `attach` in the same session.
- **F4 (wizard-only profile create):** resolved. `config profile create` gained
  `--quiet` / `--accept-defaults`; a profile bootstraps headlessly with
  `--quiet --accept-defaults --tax-id <NIF>`.

### S34 — setup (profile / import / evidence add / attach) — PASS

`config profile create persona-roll --quiet --accept-defaults --tax-id 12345678Z`,
`ledger import statement.csv --provider csv` (1 row), `ledger evidence add
factura.pdf ...` (returned `evidence_id`), and `ledger attach <tx>
--purchase-invoice-evidence-id <id>` all succeeded. The link persists: a second
identical `attach` refuses with "manual ledger update must change at least one
ledger field" (idempotent no-op), proving the first persisted. Every required
secret/flag refusal along the way (`--tax-id`, `AEAT_SECRET_PASSPHRASE`) was
instructive and named the exact runnable form.

### S35/S36 — classify --llm codex --saturate --read-evidence — PASS

`ledger classify <tx> --llm codex --saturate --read-evidence
--evidence-acknowledged` returned BUSINESS / `hardware_amortizable` /
`domestic_general_21` with base 250.00, rate 0.21, IVA 52.50. The bank row
carried only "PAGO SUMINISTROS … 302.50"; the base/IVA decomposition and the
category could only come from the model reading the invoice, confirming the
on-host text-layer read reached the model. The regulated numbers are
system-derived (250.00 = 302.50 / 1.21), not model-emitted. `--apply` stamped
`clasificado-por: llm:codex`, persisted the fields, set review status `reviewed`,
and emitted a `ledger.transaction.classified` event.

### S37 — split --llm codex --read-evidence --apply — PASS

Against a two-line invoice (Portátil base 250 + IVA 52.50; Material base 100 +
IVA 21) booked as one 423.50 transaction, `ledger split <tx> --llm codex
--read-evidence --evidence-acknowledged --apply --yes` produced a 2-child split:
child 1 = 302.50 ("1. Linea 1: Portatil"), child 2 = 121.00 ("2. Linea 2:
Material"). Children sum exactly to the 423.50 parent; descriptions carry the
model's evidence citations; both children stamp `llm:codex`. The destructive-op
`--yes` gate and the cloud-evidence consent gate both fired and were instructive.

### F5 (LOW, UX) — `ledger view` does not display the linked evidence id

`ledger view <tx>` renders no row for the linked `purchase_invoice_evidence_id`
(or attachment ids), so an operator cannot see from `view` that evidence is
attached, even though it is persisted and readable (the classify/split
`--read-evidence` path consumed it successfully). A display gap, not a
persistence defect. Worth surfacing the evidence link in `view`.

### F6 (env, not a code defect) — `claude` provider CLI not authenticated

`classify --llm claude` failed with "claude CLI exited with 1: 'Not logged in ·
Please run /login'". The classifier surfaced the provider's auth error
instructively. `codex` was authenticated and used for the roll. Provider auth is
a documented operator prerequisite (`setup-llm-classification.md`), not a defect.

## Recommendations

- Surface the linked `purchase_invoice_evidence_id` / attachment ids in `ledger
  view` (F5) so evidence attachment is visible without inspecting history; track
  as a small follow-up.
- No action for F6 (operator provider auth); the instructive surfacing is correct.
- The round-1 audit's F1/F2/F4 follow-ups are closed by this roll; the
  `cli-payload-schema-mirrors-emitted-record` codification candidate (round-1 F1)
  still awaits a second occurrence.

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

None. This roll validated existing behaviour against the real cloud CLI and
surfaced one minor UX gap (F5); it produced no new cross-session,
constraint-shaped, project-bound lesson warranting a rule.

## Campaign-close honesty review

A mandatory fresh-context honesty review (per `aeat-campaign-close-honesty-review`)
ran against the closure summary before declaring the campaign structurally
complete. The legally load-bearing constraints all hold: the LLM never emits a
persisted regulated number (rate/base/amount are registry-derived via
`split_gross_at_rate` / `_derive_iva_substrate`), the cache folds only the
sha256 content address (never the base64 bytes), the secure-storage invariant is
respected, and the new tests are real-behaviour (no mocks). Findings and
dispositions:

- **H1/H2 (deferred to follow-up) — on-host vision READ is built but unwired.**
  W02.P05 (S17–S20) shipped the LocalAdapter Ollama-images path, the in-memory
  PDF rasteriser, and the multimodal cache key — exactly as those four Steps
  scoped them, and they are complete and tested. But the shipped
  classify/saturate/split path uses `SubprocessLLMClassifier`
  (`domain/transactions/_llm.py`), whose `classify`/`propose_split` accept only
  `evidence_text: str`; `aeat.adapters.outbound.llm` (LLMClient/LocalAdapter) is
  imported by zero application/CLI modules. So the ADR's headline on-host
  vision read of scanned/image evidence is not reachable by any operator command,
  and `_resolve_evidence_text` still raises on image evidence. This is a
  plan-vs-ADR scope gap: no Step ever covered wiring a local-vision *consumer*.
  The plan's S17–S20 are honestly complete; the operator-facing on-host vision
  capability is **not shipped** and is deferred to a follow-up campaign
  (`llm-evidence-vision-consumer`: add a local-vision classifier that rasterises
  scan-only/image evidence and feeds a local model via the LocalAdapter, dispatch
  it from `_resolve_evidence_text`, and validate against a local Ollama vision
  model). Until then the only working evidence read is the consent-gated cloud
  text path — which the ADR bars for gestors, so gestors have no evidence-read
  path yet; this must be stated plainly rather than implied closed.
- **M1 (accepted) — S18/S19 multimodal cache key is pre-wired for a consumer
  that does not yet exist.** Correct defensive code; it becomes load-bearing once
  the H1 follow-up lands. Kept.
- **M2 (fixed) — F5 view-display.** `ledger view` now renders the linked
  `purchase_invoice_evidence_id` and attachment ids; locale keys added to all
  four catalogues; gated by a real `evidence add -> attach -> view` test.
- **L1 (deferred with H1) — process-state comments** ("until the on-host vision
  reader lands" in `_llm_classification.py` / `_evidence_textlayer.py`) violate
  `aeat-source-hygiene`. They honestly document the H1 gap; rewording them now
  would falsely imply a working route, so they are corrected when the H1 follow-up
  wires the path.
- **L2 (verified) — S32 / persona Steps exec records.** S32's nitpicky
  docs-build gate is green at HEAD (`8 passed`) and carries an exec record; the
  S34–S37 persona Steps each carry exec records.

**Verdict:** the plan is complete *as scoped* (every Step delivered what it
specified, with exec records); the ADR's broader operator-facing on-host vision
read is honestly recorded here as **not shipped** and deferred to the
`llm-evidence-vision-consumer` follow-up, rather than implied complete by the
38/38 count.
