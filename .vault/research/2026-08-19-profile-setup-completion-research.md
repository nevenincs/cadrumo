---
tags:
  - '#research'
  - '#profile-setup-completion'
date: '2026-08-19'
modified: '2026-08-19'
body_schema: 'body-v1'
body_hash: 'sha256:146b0cc57921f49cc27545ef9c6523f42ed77f489278bc00faabc935d454033e'
related: []
---
# `profile-setup-completion` research: `no production path advances a profile to setup COMPLETE`

Every modelo verb is gated on the active profile's stored `setup_state` reaching
`COMPLETE`. Measured against the tree, nothing in production performs that
transition, so the gate never opens and the whole calculate-to-export path is
unreachable. This was found by operating the CLI rather than by reading it.

## Findings

### The gate, and what it blocks

`aeat app modelo work create` refuses with "La configuración del perfil está
incompleta; termina el asistente de configuración antes de trabajar con modelos."
Because a work unit is the subject every later verb addresses, the refusal also
blocks `work calculate`, `work verify` and `modelo export` — the entire local
finish line the CLI advertises.

### The record is simultaneously valid and incomplete

For a profile created through the documented scripted invocation,
`aeat config profile show` reports `record_validity valid issues=0` together with
`setup_state incomplete`. Two authorities disagree: the computed field-level
completeness in `src/cadrumo/application/user_profile/_completeness.py`
(`conditional_profile_missing_required`, `missing_required_field_paths`) finds
nothing missing, while the stored enum still says incomplete.

### The transition exists, is self-guarding, and has no production caller

`ProfileRecordRepository.complete_setup`
(`src/cadrumo/application/user_profile/_profile_record_repository.py:270`) is the
only code that writes `ProfileSetupState.COMPLETE`. It is compare-and-swap
guarded on `record_revision` plus `content_digest`, returns early when already
complete, and calls `reject_invalid_profile_facts(..., require_complete=True)`
before promoting. So it cannot promote a record that is not actually complete.

Measured call sites across `src/cadrumo/`: two docstring references
(`application/user_profile/_validation.py:137`,
`application/wizard/_checkpoint_store.py:33`) and otherwise tests only —
`application/user_profile/tests/test_capsule_lifecycle.py`,
`test_complete_setup_schema_judgement.py`, `test_cotejo_apply_schema_judgement.py`,
and the shared helper `src/cadrumo/tests/user_profile.py`. No production caller.

That the only exercise is from tests is what makes the capability dormant rather
than merely unreached: the transition is proven to work and proven to be unwired.

### Birth-incompleteness is deliberate; completion is not documented anywhere

`register_profile_from_scripted_invocation`
(`src/cadrumo/entrypoints/cli/_config/_scripted_registration.py:109`) states it
directly: "a profile is born incomplete on purpose, so a rejected fact leaves a
real profile the operator can correct instead of nothing." The wizard agrees from
the other side — `application/wizard/_commands.py` records that a save-and-exit
leaves the profile `SETUP_INCOMPLETE`, and
`application/wizard/_checkpoint_store.py` treats `INCOMPLETE` as the state a
checkpoint is resumed from.

So the design intends birth-incomplete plus a later completing act. The later act
is the part that does not exist.

### The non-interactive path dead-ends while advising the operator onward

`aeat config profile edit lucia --quiet --accept-defaults` exits 0, reports
`estado actualizado`, and prints `Siguiente: aeat app modelo work create` — the
verb that then refuses on the state this command did not change. An operator
following the CLI's own next-step guidance loops.

### Two candidate resolutions

Wiring the existing transition into the scripted create/edit close is the smaller
change and is safe because the transition self-guards, but it works against the
documented intent that creation is deliberately not a completion authority.

An explicit operator verb under `config profile` keeps creation's semantics
untouched and makes completion a visible act, at the cost of one more verb on a
surface whose contract rule cautions against proliferation.

What the ADR must settle is which of those carries the act, and whether the
computed completeness authority or the stored enum is the one the modelo gate
should read.

### Not investigated

Whether the full-screen interactive wizard reaches a completion path that the
scripted arm does not: driving a terminal was not possible here. The narrower
claim stands on its own — the transition has no production caller on any path, so
an interactive route would have to reach it through code that does not exist.

## Sources

- `src/cadrumo/application/user_profile/_profile_record_repository.py:270` — `complete_setup`
- `src/cadrumo/application/user_profile/_completeness.py` — the computed completeness authority
- `src/cadrumo/application/user_profile/_validation.py:137` — docstring reference
- `src/cadrumo/application/wizard/_checkpoint_store.py:33` — docstring reference, and `INCOMPLETE` as the resume state
- `src/cadrumo/application/wizard/_commands.py` — save-and-exit leaves `SETUP_INCOMPLETE`
- `src/cadrumo/entrypoints/cli/_config/_scripted_registration.py:109` — "born incomplete on purpose"
- `src/cadrumo/domain/user_profile/_values.py:147` — `ProfileSetupState`; `:364` — a consumer gating on `COMPLETE`
- `src/cadrumo/application/modelo/_m303_regimen_simplificado_scope.py:41` — another consumer gating on `COMPLETE`
