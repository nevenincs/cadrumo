---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:25f480c131bf394b938607dc9baf880b5127375fede6894f990c2013f878ade5'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
  - "[[2026-09-04-clitui-ledger-reference]]"
  - "[[2026-09-04-clitui-ledger-W01-P02-S06]]"
---

# `clitui-ledger` audit: `S06 registry and filing census review`

## Scope

Mandatory independent review of approved-plan step `W01.P02.S06`. The review
compared the S06 reference, execution record, plan checkbox, and feature index
with the live registry authority, binding target graph, calculation resolver
composition, verification gates, filing evidence, export behavior, and focused
tests. No product or TUI implementation was changed.

The live authority independently reproduces seven Ledger binding families, 546
declarations at 35 exact family/modelo/revision sites, and the published family
breakdown. `casillas_by_binding` classifies 510 declarations as canonical
registry-bound and 36 as having no binding/casilla edge. Exact inspection of the
36 confirms three application outputs outside that graph: M130 retenciones to
casilla `06` through `_m130_retenciones_backend_inputs`, and both M210 revisions
to `rendimientos_integros` through `bound_inputs_by_casilla_id`. The remaining
33 are exactly the two M130 declarations and 31 historical IVA declarations
listed in the reference.

All seven families have one selector registration, one build-time validator
registration, and one unique production `mesh` resolver owner. These structural
facts were not accepted as behavioral proof. The M369 suite exercises a real
nonzero invoice-catalogue calculate-to-verify-to-export chain and separately
proves missing-source and unrouted-observation verification/export refusal.
Exact call-site and test inspection confirms the published weaker or missing
chains for M309, M322, M353, M131, M151, M130 casilla `02`, and M210 export/file.
Verification examines persisted `source_issues` only for the OSS family; no
general non-OSS blocker exists in verification, filing, or export. Filing
evidence carries `currency`, `fx_rate`, and `value_in_eur` but no FX source or
effective-date lineage. G0 remains OPEN. The focused S06 suite reproduced 87
passing tests.

The 130-file declaration-source set and published source digest reproduce
exactly when each repository-relative POSIX path and file body is framed by an
unsigned eight-byte big-endian length. The route rows and every published count
and classification reproduce semantically, but the route digest itself does
not have a replayable byte contract, as recorded below.

## Findings

### s06-registry-census-review | high | Route digest has no reproducible projection contract or detector

The reference publishes
`sha256:4e47a06ba217ea66152a756453c70a9a47ea542d6dac46e7742210684f69f705`
as a sorted canonical-JSON projection, but neither the repository nor the S06
record contains the projection schema, generator, serialized payload, or test
that produced those bytes. Exact repository search finds the digest and
coordinate identity only in the reference row. The prose names semantic inputs
such as selector, applicability, target casilla, and section, but does not fix
JSON member names, root shape, null/default handling, section representation,
row ordering tie-breakers, or model-dump normalization. Multiple valid canonical
JSON projections therefore represent the same independently reproduced 546
rows while hashing differently.

This is HIGH because an opaque digest cannot bind an independently reviewable
evidence subject. It also leaves the claimed exact census without detector
teeth: a declaration, selector, applicability interval, target, or section can
change without any checked generator proving that the publication digest and
counts were recomputed. The S06 execution record's prose-only "semantic census
assertion" cannot fail on that drift. The related source-set digest is also
under-specified in prose, although its value was independently recovered and
matched; the route digest could not be reproduced without inventing an identity
schema.

## Recommendations

- Reopen `W01.P02.S06` and commit one canonical route-census projection owner
  that fixes the complete payload schema and byte encoding, derives all rows
  from `ValidatedRegistryAuthority` plus `casillas_by_binding`, and emits the
  published digest and counts. Do the same explicitly for the source-set frame
  rather than relying on reviewers to infer eight-byte big-endian lengths.
- Add positive and representative mutation tests to the existing campaign gate
  owner `dev/quality/tests/test_clitui_ledger_capability_matrix.py`. At minimum,
  adding/removing a declaration and changing a selector, applicability window,
  target casilla, or target section must move the digest or fail the check.
  Refresh the reference, S06 execution record, plan state, and feature index,
  then obtain another independent review before marking S06 complete.

## Remediation review

Ruling: **NOT ACCEPTED**. The remediation closes the original byte-contract
finding only in part. Independent serialization from the live validated
authority reproduces 546 rows, 35 family/modelo/revision sites, seven source
families, 510 direct routes, 36 rows without a direct edge, and 130 source
frames. The independently assembled framed payloads reproduce route digest
`sha256:247b82a244e2a8c9a6ca476cc6aa46a3e15b7357f2aa206f4148fee18175f9ac`
and source digest
`sha256:194a9f26ddfbae6c5d7f265ffe58f50964fbe2fcd02a5670fa19845dead5cf6d`.
The root, version, row keys and types, target section tuple, canonical ASCII
JSON, domain prefixes, unsigned eight-byte big-endian framing, sorting,
duplicate rejection, and serializer revalidation all match the published
contract. The builder validates and projects the live authority through
`casillas_by_binding`; it does not introduce a second business registry.
Reversing injected source records is normalized by the declared sort, while a
reordered already-built census is correctly rejected as noncanonical.

The substantive census remains unchanged: 510 canonical routes plus three
application-sidecar outputs plus 33 unresolved destinations. The prior review's
production-chain gaps, non-OSS `source_issues` blocker gap, and FX-provenance
gap remain accurately published as unproven work. G0 remains OPEN. The S06
record, plan checkbox, and feature index agree, and the remediation commits
contain no product or TUI changes.

### s06-registry-census-remediation | high | Full typed selector projection still omits defaults and nulls

The published contract says `selector_json` retains model defaults and nulls
and later says the digest binds every full typed selector. The implementation
instead passes every selector through `selector_as_dict`, whose Pydantic branch
uses `model_dump(exclude={"source"}, exclude_none=True,
exclude_unset=True)`. Independent comparison of the live Pydantic selector
values with their census projections found omissions in 498 of 546 Ledger
declarations; representative IVA rows omit both nullable
`exemption_articles` and `applied_rates`.

Consequently, a selector-model default or nullable-field representation can
change outside the 130 TOML source frames without changing the route digest.
The existing selector mutation test edits an already-projected JSON object and
does not exercise this loss at the live-authority projection boundary. This is
still HIGH under the detector-teeth and typed-meaning rules: the evidence
subject is narrower than its documented identity, so the original freshness
claim can silently under-declare selector state.

Remediation must choose and implement one truthful contract. If the evidence
subject is the full validated selector, serialize the selector model with
defaults and nulls retained (excluding only injected `source`) and add a live
projection test that fails when an unset/default/null field is dropped or its
default changes. If the intended subject is the operational normalized
selector returned by `selector_as_dict`, narrow the reference claim and add a
test proving that normalization is intentional and semantically sufficient.
The former is required to preserve the current published full-typed-selector
claim.

### s06-registry-census-static | medium | New census construction is not clean under `ty`

`ty check` reports scoped errors at
`dev/quality/clitui_ledger_capability_matrix.py:201-202`: constants annotated
as `Final[str]` and `Final[int]` are passed to fields requiring the exact root
and schema `Literal` types. Nine additional diagnostics in the same command are
pre-existing campaign-matrix test/helper issues and are reported separately,
not charged to S06. Ruff formatting and lint both pass. The scoped literal
errors should be resolved without weakening the strict root/schema model.

Focused evidence: `dev/quality/tests/test_clitui_ledger_capability_matrix.py`
passes 131 tests, including the committed positive and route/source mutation
cases. The nine-file S06 behavior suite was rerun independently. Its result and
the feature-scoped Vault checks are recorded in the final review handoff.
