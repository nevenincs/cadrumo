---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:d7f729177643c0bce2012196b09d0a06be3c651536963985e4f57feedca46882'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-source-casilla-integration-adr]]"
---

# `source-casilla-integration` audit: `W01 P01 S145 resolver identity review`

## Scope

Formal no-edit review of S145 commit `6504f93909`, covering all 35 changed paths and the production resolver-to-provenance-to-encrypted-revision-to-CLI chain. The review checked exact resolver ownership at every production `CalculationSourceProvenance` constructor, merge attribution, application/domain projection, encrypted persistence, operator payload projection, live connectivity-authority joins, manual-input ownership, content-address behavior, and adversarial wrong-resolver, mixed-resolver, contradictory-source-axis, and corrupted-storage cases. The review also ran Ruff over every changed Python path, collected every changed test module, and executed the full selected changed-test surface.

## Findings

### persisted-source-axis-integrity | high | Contradictory persisted source axes authenticate as an exact connection

`CalculationSourceRef` requires `resolver_id`, `source_kind`, and `source_ref`, but does not enforce the application provenance invariant that a canonical `source_kind` and `binding_source` agree. `LiveSourceConnectivityProofAuthority.encrypted_revision_matches` then joins on resolver id, `binding_source`, source reference, and fingerprint without checking the persisted `source_kind`. An adversarial probe constructed a valid encrypted-domain row with `source_kind="payable_invoice"` and `binding_source=collectible_invoice`; the authority authenticated it as a collectible-invoice connection. This defeats the promised exact resolver/source/reference/fingerprint join and means corruption of one of the two persisted source axes does not fail closed. The relevant carriers and join are `CalculationSourceRef` and `LiveSourceConnectivityProofAuthority.encrypted_revision_matches`.

### provenance-content-address-collision | high | Different resolver provenance collapses onto the same immutable revision id and first write wins

S145 explicitly pins that changing or deleting `source_provenance`, including `resolver_id`, leaves `calculation_revision_id` unchanged. That is not established by the authorizing source-connectivity ADR, whose completion contract requires exact provenance and an encrypted strict round trip. It also conflicts with the domain contract that structurally different `CalculationRevision` records cannot share an id. The application writer derives the id without provenance and immediately returns an existing row on collision, before writing the newly resolved provenance or its event digest. Therefore two calculation runs with identical values and transaction ids but a changed source fingerprint or resolver trace do not create two immutable revisions and do not update the event digest: the earlier trace silently wins. Including `resolver_id` in `_source_provenance_trace_sha256` does not repair this because the second event is never emitted. Unlike ledger filing evidence captured later at verify/file time, this provenance already exists at calculation-revision creation, so the later-annotation precedent does not authorize its exclusion. This is a release blocker for a campaign whose connected proof is keyed to the exact encrypted revision trace.

### changed-test-surface-red | high | The full changed-test surface fails after the required resolver-id migration

The changed `test_local_cross_period_carry` module constructs a composite `CalculationSourceResolution` named `reused-binding-regression` containing provenance owned by `previous_filing` and `relation_prefill`. S145's new validator correctly rejects that mismatch, but the S145 edit only added the two child resolver ids and did not update the composite test fixture to use the canonical merged-envelope contract. Running every changed test module produced `1 failed, 150 passed`: `test_source_resolution_keeps_reused_wallet_binding_outside_m303_coordinate` fails with `aggregation.source_mesh.errors.provenance_resolver_mismatch`. The implementation cannot pass formal review while its own changed test surface is red.

### mixed-resolver-source-ambiguity | medium | Rival resolver rows for the same persisted source identity remain admissible

The authority filters by the asserted resolver before applying its one-row cardinality check. A probe with two otherwise identical persisted rows for the same binding source, source reference, and fingerprint but different resolver ids still authenticated the asserted row. Production route ownership intends one canonical resolver per binding source; an encrypted row simultaneously claiming the same source identity under a rival resolver is therefore corruption or ownership ambiguity, not independent evidence. The authority should reject ambiguity across the persisted source identity before selecting the enrolled resolver.

### composite-envelope-name-bypass | low | Reserved composite resolver names bypass provenance-owner validation by string alone

`CalculationSourceResolution._provenance_names_its_producing_resolver` skips all row-owner checks whenever the envelope id is the bare string `source_mesh` or `source_mesh_precedence`. The real merge functions preserve child resolver ids correctly, so no current production misattribution was found, but any direct constructor can claim either reserved name and carry arbitrary mixed provenance. A typed/private composite construction authority would prevent those names from becoming a spoofable bypass surface.

## Recommendations

- Block S141 and S145 acceptance until `CalculationSourceRef` enforces the same canonical `source_kind`/`binding_source` parity as application provenance and encrypted corruption tests prove both mismatch directions are refused.
- Amend the authorizing ADR before choosing the provenance identity policy. If source provenance is part of a calculation attempt, include its full sort-canonical resolver/source/reference/fingerprint trace in the sole revision identity builder and add first-write collision tests. If it is intentionally a later annotation, define a separate content-addressed provenance record and join rather than storing structurally different immutable revisions under one id.
- Repair the changed cross-period test fixture through the actual canonical composite merge path, then rerun all nine changed test modules with zero failures.
- Make authority matching reject duplicate persisted identity rows across resolver ids, and prove wrong resolver, mixed resolver, source-axis mismatch, source-reference drift, fingerprint drift, and missing resolver at the encrypted boundary.
- Replace the string-name composite validation exemption with a construction boundary that only canonical merge code can mint.

Verification evidence: `git show --check 6504f93909` passed; Ruff passed on all changed Python paths; collection found 151 selected tests with 28 policy-deselected; the full selected run ended `1 failed, 150 passed`; a narrower six-module run passed `61 passed`; adversarial authority probes returned `authority_match=True` for contradictory source axes and `mixed_authority_match=True` for rival resolver duplication.
