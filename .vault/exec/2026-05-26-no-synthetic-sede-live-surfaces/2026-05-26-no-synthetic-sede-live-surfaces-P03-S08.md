---
tags:
  - '#exec'
  - '#no-synthetic-sede-live-surfaces'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S08'
related:
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-adr]]'
---

# `no-synthetic-sede-live-surfaces` `P03.S08`

Recorded final P03 validation evidence and closed the declaration-extraction S124 handoff.

- Modified: `.vault/plan/2026-05-26-no-synthetic-sede-live-surfaces-plan.md`
- Modified: `.vault/plan/2026-05-21-declaracion-extraction-architecture-plan.md`
- Created: `.vault/exec/2026-05-26-no-synthetic-sede-live-surfaces/2026-05-26-no-synthetic-sede-live-surfaces-P03-S07.md`
- Created: `.vault/exec/2026-05-26-no-synthetic-sede-live-surfaces/2026-05-26-no-synthetic-sede-live-surfaces-P03-S08.md`
- Created: `.vault/exec/2026-05-21-declaracion-extraction-architecture/2026-05-26-declaracion-extraction-architecture-W05-P18-S124.md`

## Description

P01 landed the schema invariant and remote-state guard policy invariant rejecting
AEAT-hosted live cross-references that allow synthetic input. Production commits:
`08fe0f68e` (schema), `905e3a5a8` (remote-state guard), `8b77c1ab8` (registry
test coverage for the invariant).

P02 flipped the committed AEAT-hosted Modelo 100 Renta WEB Open and Modelo 349
GROI / IXVI live cross-references to `synthetic_data_allowed = false`, with
provenance comments citing this ADR (`7dfcaac94`), retired the three Sede live
tests that previously sent synthetic data to AEAT (`18174f577`), and closed
plan rows P02.S04, P02.S05, P02.S06 (`4564a10b0`).

P03 re-ran the focused registry and Sede policy gates and confirmed zero
production `synthetic_data_allowed = true` declarations remain on AEAT-hosted
surfaces. The originating declaration-extraction handoff `W05.P18.S124` is now
closed against the accepted ADR and the hardened registry / Sede surfaces.

## Tests

Focused registry policy gates (`uv run --no-sync python -m pytest
src/aeat/domain/calculations/registry/test_remote_state_guard.py
src/aeat/domain/calculations/registry/test_authenticated_simulator_surface.py
src/aeat/domain/calculations/registry/test_live_parity_audit.py
src/aeat/domain/calculations/registry/test_cross_reference_applicability.py -q
--no-header -p no:cacheprovider`): 61 passed in 57.86s.

Outbound Sede tests (`uv run --no-sync python -m pytest
src/aeat/adapters/outbound/aeat/sede/ -q --no-header -p no:cacheprovider
--tb=short`): 173 passed, 4 failed, 13 deselected. Every failure is unrelated
to the no-synthetic policy and traces to concurrent-campaign foreign WIP:
three Modelo 303 `test_declarations.py` cases fail in `parse_export_payload`
with `export literal field 'modelo-303-envelope-marker' does not match the
registry layout`, and `test_no_write_surface.py::test_verb_never_called[save]`
fails on three new `self._repository.save(` call sites in
`_observation_store.py` from a different campaign. None of these touch
`synthetic_data_allowed` or any AEAT-hosted live-surface policy.

Smoke gates: `aeat app modelo describe 100` and `aeat app modelo describe 349`
both clean exit with their full revision metadata. `aeat app registry verify`
exits non-zero on unrelated foreign WIP (Modelo 190 `total_percepciones_count`
/ `total_percepciones_amount` `intentional_singleton` cardinality violations
in revisions 2024 and 2025-y-siguientes from the schema-hardening campaign);
no Modelo 100, 349, or `synthetic_data_allowed` finding surfaces.

Production sweep (`rg "synthetic_data_allowed\s*=\s*[Tt]rue" src/aeat/`):
empty for AEAT-hosted production data. Remaining matches are policy-invariant
tests in `src/aeat/domain/calculations/registry/`, registry TOML comments
documenting the rule, and `_schema.py` / `_remote_state_guard.py` error
messages that quote the rejected value.

## Handoff to declaration-extraction S124

The originating plan row reads:

> `W05.P18.S124` - Open and execute the follow-up no-synthetic-Sede ADR/plan
> slice for AEAT-hosted synthetic live-surface policy conflicts discovered
> outside this declaration-acquisition slice; Modelo 100 Renta WEB Open,
> Modelo 349 GROI/IXVI, and direct GROI/NIF-IVA Sede guard policies now
> disallow AEAT-hosted synthetic input.

What this no-synthetic-Sede campaign delivers to that row:

- Schema-level invariant in `_schema.py` rejecting any AEAT-hosted live cross
  reference with `synthetic_data_allowed = true`.
- Remote-state guard invariant in `_remote_state_guard.py` rejecting any
  AEAT-hosted policy with the same shape.
- Modelo 100 Renta WEB Open `live_cross_references` flipped to
  `synthetic_data_allowed = false`.
- Modelo 349 GROI and IXVI `live_cross_references` flipped to
  `synthetic_data_allowed = false`.
- Retirement of the three outbound Sede live tests that previously transmitted
  synthetic data to AEAT.
- Provenance comments on the registry TOMLs citing the accepted ADR.

S124 is closed; the declaration-extraction plan now references the accepted
ADR `2026-05-26-no-synthetic-sede-live-surfaces-adr` and the executed plan
`2026-05-26-no-synthetic-sede-live-surfaces-plan` as the durable record of
that handoff.
