---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:b28f436505d4fbb9e9b0a1cab4e33bae466ec83247963a2959bc089be3f706c7'
step_id: 'S13'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Resolve the superseded-constant population detected by literal-value supersession, naming the live holder for each before removal

## Scope

- `src/cadrumo`

## Changes

- `M` `src/cadrumo/domain/modelos/calculation_repository.py`
- `M` `src/cadrumo/domain/modelos/filing_repository.py`
- `M` `src/cadrumo/domain/modelos/verification_repository.py`
- `M` `src/cadrumo/application/wizard/commands.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_evidence_consent_cli.py`
- `M` `src/cadrumo/core/external_constants.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/domain/modelos/tests src/cadrumo/core/tests -k "repository or external_constant or tabular"` -> `pass`
- `verify:` `uv run --no-sync ty check <the six modules>` -> `pass`

## Changes

Eight constants removed, taking the unused-symbol count from 1397 to 1389.

The supersession probe -- does the constant's literal value still appear in production
outside its defining module -- was a candidate signal, not proof, and checking each
candidate changed the diagnosis for three of them. `_CALCULATION_PERSISTENCE_MESSAGE`,
`_FILING_PERSISTENCE_MESSAGE` and `_VERIFICATION_PERSISTENCE_MESSAGE` are not superseded
constants at all: each name is defined TWICE with the same literal, once under
adapters/persistence/profile where it is passed as `translated_message` four times, and
once in the domain/modelos repository module where it is used zero times. They are dead
DUPLICATES, which the architecture boundaries forbid separately. The live adapter copies
were left untouched.

That distinction mattered for the remedy. A superseded constant is removed because its
value moved; a duplicate is removed because a second definition exists at all, and deleting
the wrong copy would have broken four call sites in each adapter.

The other five are genuine migration residue, each carrying exactly one tree-wide reference
-- its own assignment -- while the literal now lives at a declaration site: the CLI help
keys as `TranslationKey` entries in the evidence command specs, the descendiente door
command in the CLI payload module, and the encoding literal in `core/tabular.py`.

## Notes

The shared tree's module ratchet remains RED on `cadrumo.domain.contabilidad` and
`cadrumo.domain.is_compensation`, unchanged from the previous Step and still not this
campaign's breakage. It was again left red rather than baselined.
