---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:38a336c49d690b1633aec62daeacce06c4ee372e1bff4b025958242ee508bb23'
step_id: 'S18'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Run duplication, import, semantic, architecture, type, lint, focused, and full quality gates without threshold or exclusion changes

## Scope

- `dev/audit/.runs`

## Changes

- `M` `src/cadrumo/application/filing/producer_snapshot.py`
- `verify:` `uv run --no-sync python -m dev.audit.duplication` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.dead_code` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_ratchet` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo dev` -> `pass`
- `verify:` `uv run --no-sync lint-imports` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unreachable_module_ratchet` -> `fail, peer-owned`
- `verify:` `uv run --no-sync ty check src/cadrumo/domain src/cadrumo/application src/cadrumo/core src/cadrumo/llm` -> `fail, peer-owned`
- `verify:` `uv run --no-sync ruff format --check src/cadrumo dev` -> `fail, peer-owned`

## Notes

Measured at revision 96b58acd4b. No threshold, exclusion, baseline, skip or allowlist was
changed to reach any of these results.

Green: the duplication runner, the dead-code audit, the unused-symbol ratchet, the
repository lint, and all eleven import contracts. The clone count stands at 10 with every
group carrying exactly one disposition and zero uncovered, which is the closure the amended
governing decision defines.

One repair was needed to get lint green, and it was not this campaign's breakage.
`application/filing/producer_snapshot.py` carried six `__all__` entries -- `FilingElectionFactSet`,
`GeneralFilingProfileFactSet`, `M303FilingFactSet`, `Modelo111ProfileFactSet`,
`Modelo202ActivityFactSet` and `TaxpayerIdentityFactSet` -- naming types that exist nowhere
in the tree. The file was committed and clean, so this was landed breakage rather than
in-flight work, and it failed the repository-wide lint gate for everyone. The six entries
were removed; nothing defines or imports those names, so no import could have depended on
them, and the module's declared surface now matches what it actually exports. Proven by A/B
that the edit changes nothing else: one type diagnostic before and after.

## Notes on what is not green, and why it is not closed here

Three gates fail, all from one concurrent refactor that is adding a `parameters` argument
across the bienes inversion surface:

* the module ratchet, on `cadrumo.domain.contabilidad` and `cadrumo.domain.is_compensation`;
* `ty`, on call sites in `producer_snapshot` missing the new `parameters` argument, and on a
  malformed import in a registry test whose path repeats a package segment;
* `ruff format`, on eleven files including `dev/ci/tests`.

None is this campaign's, and none is a false green: each is an instrument correctly
reporting a real defect in landed or in-flight peer work. Fixing a peer's mid-refactor call
sites would mean guessing the argument they intend to thread, which is their decision.

This Step's stated bar is that the type, lint, format and repository gates pass from one
stable revision. Lint now does; type and format do not. The Step is therefore recorded and
left OPEN rather than closed against a bar it does not meet, because closing it would assert
a joined green state that does not exist.
