---
tags:
  - '#reference'
  - '#live-parity-oracle'
date: '2026-05-07'
modified: '2026-05-07'
related:
  - "[[2026-05-07-live-parity-oracle-adr]]"
  - "[[2026-05-07-aeat-vies-surface-split-ixvi-vs-groi-adr]]"
  - "[[2026-05-07-live-parity-oracle-plan]]"
  - "[[2026-05-08-live-parity-oracle-adr]]"
---

# `live-parity-oracle` reference: `binding-an-oracle-to-a-cross-reference`

This how-to walks an agent through the end-to-end procedure for
binding a registered live-parity oracle to a modelo cross-reference.
The procedure is the canonical path for adding a new AEAT
cross-reference that exercises a real oracle (drift detector,
verifier, or validator) without re-implementing audit logic.

## Step 1: pick the oracle id from the registered catalogue

Run `uv run --no-sync aeat app registry audit-oracles --json` and
read the `registered_oracle_ids` field. Every value listed there is
backed by a `LiveParityOracle` Protocol implementation that
`LiveParityCatalogue` already knows how to construct, exercise, and
compare. Pick one whose `surface_kind` matches the cross-reference
you intend to add.

Surface-kinds in the catalogue today: `vat_id_check`,
`pre_filing_validator`, `file_validator`, `open_simulator`, and
`integration_test_service`. Each kind constrains the
cross-reference's allowed `surface` field (the cross-reference
surface, not to be confused with the oracle's `surface_kind`).

## Step 2: confirm surface compatibility

Cross-reference `surface` (declared in the modelo TOML) and oracle
`surface_kind` (declared by the oracle implementation) must form a
known-compatible pair. The whitelist lives in
`_COMPATIBLE_SURFACE_PAIRS` inside `_live_parity.py`. Today's
allowed pairs include `(public_read_surface, vat_id_check)`,
`(open_simulator, vat_id_check)`, and the new
`(authenticated_simulator, vat_id_check)` (added by ADR
2026-05-07-live-parity-oracle).

If your binding's pair isn't in the whitelist, you do not get to
just add it: extend the cross-reference surface taxonomy via a new
ADR (the procedure used for `authenticated_simulator`), then add the
pair to the whitelist as part of that ADR's execution.

## Step 3: declare the cross-reference in the modelo TOML

Add a new entry under the modelo's `[[live_cross_references]]`
table with these required fields:

- `id` — kebab-case, prefix with the modelo number, e.g.
  `modelo-349-groi-spanish-counterparty-check`
- `evidence_tier` — must align with the surface (see schema
  validator rules)
- `surface` — one of the registered cross-reference surface
  categories
- `guard_policy_id` — the `RemoteStateGuardPolicy` id this
  cross-reference operates under
- `allowed_hosts` — non-empty tuple of hosts the oracle is
  permitted to contact
- `allowed_methods` — request methods the oracle may use
- `forbidden_actions` — must include the canonical
  `AEAT_WRITE_FORBIDDEN_ACTIONS` set
- `synthetic_data_allowed` — true only if the surface accepts
  arbitrary fixture data without affecting AEAT state
- `requires_authentication` / `requires_aeat_authorization` — must
  reflect the empirical reality of the surface
- `legal_refs` — at least one legal anchor that grounds the
  cross-reference's existence
- `source_refs` — at least one entry from the legal/source
  catalogues; see Step 5 if you need to add a new source

## Step 3.5: declare applicability predicates for optional bindings

Not every cross-reference applies to every taxpayer. Bindings whose
relevance depends on profile state (ROI enrollment, OSS enrollment,
recargo de equivalencia regime, etc.) declare
`applicability_predicates` so the resolver, audit, and live tests
can skip them cleanly when the profile says off.

Decide whether your binding is:
- **Universal** — every taxpayer who files the parent modelo needs
  it. Leave `applicability_predicates` empty (the default); the
  binding is unconditionally applicable.
- **Optional** — only some subjects need it. Declare a tuple of
  `ProfilePredicateDefinition`s that gate it.

To declare predicates, add a `[[live_cross_references.
applicability_predicates]]` array-of-tables block under your
cross-reference with each entry providing `field`, `op`
(`equals` / `not_equals`), `value`, `explanation`, `legal_refs`,
and `source_refs`. The aggregation mode defaults to `all` (every
predicate must match); flip to `any` only when independent
sufficient conditions exist.

Worked example: the GROI Spanish-ROI counterparty consult on
Modelo 349 is gated on `iva.does_intracomunitario == true`. A
taxpayer who doesn't conduct intracom operations files no Modelo
349 at all and never invokes the GROI surface. A future binding
that requires the user themselves to be ROI-registered would also
declare `iva.roi_enrolled == true` (the field exists in the
profile schema and is independent of the operational fact).

The applicability evaluation lives in
`evaluate_cross_reference_applicability(decision, profile_facts)`
and returns a typed `CrossReferenceApplicability` carrying
`applicable: bool`, `matched_explanations`, and
`unmet_predicate_fields`. Always consume the typed shape — the
unmet-fields list is the diagnostic future agents need when
something silently no-ops.

## Step 4: link the cross-reference to its construct

Edit the construct that owns the modelo revision (e.g.
`modelo-349-informative`) and add the new cross-reference id to its
`live_cross_references` array. Also add any new `source_refs` you
declared on the cross-reference to the construct's `source_refs`
array — the schema validator enforces that the construct
re-publishes every source its members consume.

## Step 5: choosing legal_refs and source_refs

`legal_refs` point at entries in `registry/aeat/legal/<area>.toml`
under `[references]` (BOE-published normatives). Reuse existing
references; only add a new one if the cross-reference is grounded
in a legal article that no other modelo cites.

`source_refs` point at entries under the same files'
`[sources."..."]` tables (AEAT-published procedural artefacts:
forms, instructions, BOE/AEAT pages). Each source must have:
- `evidence_tier` — see the `EvidenceTier` Literal in `_schema.py`
- `authority` — usually `aeat`
- `kind` — `instructions`, `form`, `record_design`, etc.
- `corpus_path` — path to a captured local artefact under
  `corpus/aeat_official/...` (the registry verifies the file's
  byte length and SHA-256 match the declared values)
- `sha256` and `bytes` — computed from the captured artefact
- `retrieved_at` and `applies_from` — dates
- `source_url` — the public URL the artefact came from
- `review_status` — usually `reviewed` or `pending`

To capture a new corpus artefact, fetch the public URL into the
appropriate corpus subdirectory (`corpus/aeat_official/<kind>/<modelo
or topic>/`), then compute its SHA-256 and byte count and register
both in the source entry.

## Step 6: write the regression test

Add a `live_read` test under
`src/aeat/adapters/outbound/aeat/sede/` that:
1. Resolves the oracle from the catalogue using
   `resolve_cross_reference_oracle(catalogue, registry, modelo_id,
   cross_reference_id)`. The resolver enforces the surface
   compatibility constraint at runtime, so your test fails noisily
   if the binding regresses.
2. Calls the oracle against AEAT under `requires_live_enabled()`.
3. Asserts the response shape parses into the oracle's
   `Observation` model and the verdict text matches the expected
   value for a known external ground truth.

## Step 7: the no-tautology mandate

The test must query an external authority — AEAT response, public
registry, BOE-published worked example — not a hand-computed
Decimal authored alongside the test. Self-authored "expected" values
mask implementation gaps and are forbidden by project policy. Use
public ground truth (e.g. for ROI: a publicly-listed corporate NIF
known to be on the ROI registry) so an unrelated reader can verify
the assertion is sound.

## Step 8: run the gates

Run, in order, until all green:
- `uv run --no-sync aeat app registry verify --json`
- `uv run --no-sync aeat app registry audit-oracles --json`
  (the new cross-reference's oracle_id must appear among the
  registered oracles, no failures reported)
- `uv run --no-sync ruff check <touched files>`
- `uv run --no-sync ty check <touched files>`
- `AEAT_LIVE_TESTS_ENABLED=1 uv run --no-sync pytest <new test>`

If audit-oracles reports a failure, the cross-reference's
`surface` and the oracle's `surface_kind` are incompatible — go
back to Step 2.

## Step 9: prefer public re-exports for adapter tests

When the live test lives outside the registry package
(e.g. under `src/aeat/adapters/...`), import every registry symbol
from the public `aeat.domain.calculations.registry` package
namespace. The boundary test
`test_source_tree_does_not_use_absolute_registry_private_imports`
rejects absolute imports of `aeat.domain.calculations.registry._*`
private modules from non-registry source files. Add the symbol to
the registry's `__all__` if it isn't already exported.
