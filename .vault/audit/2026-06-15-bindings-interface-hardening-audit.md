---
tags:
  - '#audit'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - "[[2026-06-14-bindings-interface-hardening-adr]]"
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---



# `bindings-interface-hardening` audit: `bindings interface hardening close audit and fresh-context honesty review`

## Scope

Campaign-close audit and fresh-context honesty review of the
`bindings-interface-hardening` campaign (plan
`2026-06-15-bindings-interface-hardening-plan`, L3, 6 waves / 12 phases / 33
steps), performed before declaring the campaign structurally complete per the
`aeat-campaign-close-honesty-review` rule. The review was conducted as a
persona switch: the campaign was re-read "as if just inherited," and every
deliverable cross-checked against HEAD. Covers the six finding clusters the
research surfaced (A validation contract, B typed aggregation + source-kind
taxonomy, C fail-closed parity, D operator-boundary provenance, E semantic
disambiguation, F structural-extraction codification), the verification gates,
and the full-tree owner triage.

## Findings

### What landed (verified against HEAD)

- **W01 — typed foundations.** `BindingAggregationOp` + typed `BindingAggregation`
  (complete 5-member registry set) and `binding_aggregation_op` accessor replace
  the ~10 ad-hoc `op` re-parses (commit `type binding aggregation op`). One
  canonical `BindingSourceKind` enum replaces the mixed Literal; per-family
  frozensets derive from it; `LEDGER_BINDING_SOURCE_KINDS` fixed 2→4; `typed_enum`
  confirmed LIVE and retained; parity gate `test_binding_source_kind_taxonomy.py`.
- **W02 — one validation contract.** Single `validate(binding) -> list[str]` per
  family in one dispatch table, run at registry-build for all families;
  detail-record + previous_filing op/fact invariants lifted to build time;
  invoice/counterpart duplication collapsed; `test_binding_build_validation.py`
  (32 build-rejection + anti-tautology cases). No latent registry TOML needed
  fixing (the bundled registry was already conformant).
- **W03 — fail-closed parity.** Per-family unrouted-observation screens
  (renta-expense / renta-income / OSS) mirror the IVA precedent with a
  zero-magnitude false-fire guard, wired live on the calculate path via the
  `unrouted_observation` diagnostic; the three R2 revision-carry gate copies
  unified onto `_revision_carry_gate.revision_carry_outcome`; unresolved
  non-formula relation now advises instead of silently blanking.
- **W04 — operator-boundary provenance.** `ModeloBindingValue` carries
  `legal_refs`/`source_refs` + typed `BindingSourceKind` source, populated from
  the binding definition (hardcoded `"registry binding input"` deleted); proven on
  the ENCRYPTED filing-draft boundary by a real save→load→equality roundtrip + an
  anti-tautology proof (`test_binding_value_provenance_roundtrip.py`). CLI: typed
  `BindingRowPayload` list (the `dict[str,object]` bag retired), `--modelo`
  registry-derived `click.Choice` with accepted-codes refusal, `--binding`
  numeric-vs-enum routed by the declared engine channel (malformed numeric now
  refuses, no longer silently reclassified).
- **W05 — semantic disambiguation.** The OAuth homonym renamed
  (`_profile_binding.py` → `_active_profile.py`, `resolve_active_profile`), the
  misfiled parser reclassified (`_decimal_binding_value.py` → `_decimal_parsing.py`),
  the verification gate renamed (`test_legal_basis_rate_grounding.py`) — each an
  atomic relocation with docs-scaffold regen; a `BindingSourceResolution` Protocol
  names the one role the profile/borrador result types fill
  (`test_binding_source_resolution_role.py`).
- **W06 — codification.** Six rules authored and synced to every provider:
  `binding-validation-single-contract`, `binding-aggregation-is-typed`,
  `binding-source-kind-single-taxonomy`, `binding-values-carry-provenance`,
  `binding-names-reserved-for-registry-input`, `registry-resolver-family-extraction`.

### Gate status (owner triage)

Full-tree `pytest --collect-only -q src/aeat` is clean: 15968 collected, **0
collection errors** — the campaign introduced no collection breakage. The broad
bindings test surface (registry + aggregation + calculations + filing + modelo
test dirs) passes at close: **4088 passed, 0 failed** (8m31s). The 90
campaign-added tests (typed aggregation, source-kind taxonomy parity, build-time
validation, encrypted-boundary provenance roundtrip + anti-tautology, the
`--binding` channel coercion, and the source-resolution role) all pass at final
HEAD. One earlier full-suite failure observed
mid-campaign — `test_referential_integrity_part1.py` importing
`build_config_repair_report` from `aeat.application.diagnostics` — was
**owner-distinct peer churn** (the concurrent graceful-degradation campaign) and
was already fixed by a peer at HEAD; it is not attributable to this campaign.

### Honesty review — missing / vague / assumed-but-unverified

- **(advisory) Exec-record bodies for W04.P07 and W05–W06 steps are concise
  scaffolds**, not full narratives. The records EXIST (plan-closure satisfied) and
  the work is committed + gate-verified, but a future reader will get more from the
  commit messages than from the exec bodies. Non-blocking; enrich on next touch.
- **(assumed) The W01/W02 core changes were partly committed by a peer
  quality-sweep bot** (the `fix(quality)`/`style: green refactor churn` commits)
  rather than under the campaign's own feat messages. Verified that HEAD's content
  matches the intended change and tests are green; attribution is messy but the
  code is correct.
- **(scope-fenced, NOT a gap) The resolver mesh was deliberately untouched** —
  enrollment, `merge_source_resolutions`, novel-source gate, deferred-source
  advisories are settled prior ADRs and rules; this campaign hardened the
  definition/validation/boundary/naming altitude only.
- **(deferred, tracked elsewhere) Six advisory-deferred resolver-less source
  kinds**, the `MultiYearResolver` orphan, the `PurchaseInvoiceEvidenceSourceResolver`
  data-shape blocker, and `payable_invoice` declared by no registry binding remain
  open in their originating audits — explicitly out of this campaign's scope.
- **(verify) The `registry-formula-runtime-facade` candidate** named in the plan's
  S31 brief was NOT promoted (only `registry-resolver-family-extraction` was) — it
  is orthogonal to bindings (it governs `_formula_runtime.py` size) and is left for
  a formula-runtime campaign; recorded here so the omission is honest, not silent.

## Recommendations

- Treat the six new rules as the durable surface of this campaign; future binding
  work inherits them on load.
- When a future campaign touches `_formula_runtime.py`, promote the
  `registry-formula-runtime-facade` candidate from the 2026-06-02 formula-runtime
  boundary audit (deferred here).
- Enrich the concise W04–W06 exec-record bodies opportunistically on next touch.
- No code remediation is outstanding for this campaign's surface; the gate is the
  fresh honest review, and it ran before closure.

## Codification candidates


This campaign's codification candidates were authored and synced in wave W06.P11
(commit `codify the bindings-interface hardening disciplines`), so they are
already promoted, not pending:

- `binding-validation-single-contract` — one `validate()->list[str]` per family,
  run at registry-build.
- `binding-aggregation-is-typed` — typed `BindingAggregation` + closed op enum,
  one accessor.
- `binding-source-kind-single-taxonomy` — one core `BindingSourceKind`, derived
  per-family frozensets.
- `binding-values-carry-provenance` — legal/source refs + typed source at casilla
  parity.
- `binding-names-reserved-for-registry-input` — "binding" reserved for the
  registry-data-input concept.
- `registry-resolver-family-extraction` — per-family modules behind the package
  facade (promotion of the never-promoted 2026-06-02 boundary-audit candidate).

One candidate is deliberately NOT promoted here: `registry-formula-runtime-facade`
(from the 2026-06-02 formula-runtime boundary audit) governs `_formula_runtime.py`
module size, is orthogonal to the bindings interface, and is left for a
formula-runtime campaign.
