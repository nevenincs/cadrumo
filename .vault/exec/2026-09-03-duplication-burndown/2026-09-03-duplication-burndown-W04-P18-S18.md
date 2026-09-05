---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-04'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:958dfdf0b065920e5dca8cf3fa553ea03327d21ab49272a891e32dd44cf3689a'
step_id: 'S18'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

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

## Re-measurement

Re-run against the current tree. The verdict is unchanged and the Step stays open.

Green: duplication, dead code, `ruff check` over `src` and `dev`, all eleven import
contracts, `dev.audit.semantic`, and the four architecture gates (32 tests).

Still failing, still peer-owned: `check-types` on
`domain/bienes_inversion/regularizacion_parameters.py`, and `check-format` on eleven
files.

One correction to the count above. `ruff format --check` reported fifteen files, not
eleven: four had become this campaign's own drift, introduced after the original
measurement by edits that ran `ruff check` but not `ruff format` afterwards -
`dev/audit/unreachable_code.py`, the two new screen test modules, and
`domain/calculations/registry/applicability.py`. Those four are now formatted, which
returns the count to the eleven peer-owned files this record already named. The lesson
is that a campaign auditing drift can introduce it: run the format check over the whole
tree periodically, not only over the files an iteration touched.

## Blocker trajectory

Watched across several days rather than sampled once, because the direction
matters more than the number to whoever closes this Step.

`check-format` went 11 files, then 12, then 13, each addition arriving with a
peer commit that touched `dev/` -- `test_no_unbounded_subprocess_wait.py`, then
`test_i18n.py` -- and holding steady across commits that touched only docs and
vault records. Every one of the thirteen is peer-owned: none appears in a
`## Changes` list in this campaign's execution records.

So this blocker is not a fixed backlog waiting to be cleared; it grows with the
work landing beside it, which suggests `check-format` is not running in that
workflow. Left alone it will not converge, and this Step drifts further from
closable rather than nearer. `just check-format` on the owning branch before
the next batch lands is what changes that.

`check-types` is unchanged over the same period: 16 diagnostics across
`domain/bienes_inversion/regularizacion_parameters.py` and
`application/workbench_generation.py`, neither of which this campaign touched.
