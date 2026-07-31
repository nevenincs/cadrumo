---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:3fffddc9158b0ae0ef8f41ff727e8d1778ffc117c896ef7434e36bc3296e323c'
step_id: 'S21'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Add a split-install packaging-smoke lane proving the advisory path with the core wheel alone and the byte-identical path with the companion installed

## Scope

- `dev/packaging/smoke_split_install.py`

## Description

- Add `dev/packaging/smoke_split_install.py`: builds the slim wheel and the `aeat-data` companion wheel, installs the slim wheel alone into a fresh stdlib venv, and proves the advisory path — registry authority load emits the loud `CorpusCompanionAdvisory` naming `aeat[corpus-sources]`, and `aeat app registry verify` refuses citing the hint.
- Install the companion into the same venv and prove the byte-identical path — the advisory is gone and full source verification is clean.
- Fix a second production consumer of corpus binaries that the research `F10` trace under-scoped: `validate_source_citations` in `_validate_evidence.py` reads citation source bytes for `required_text` checks and hard-failed on the slim install (modelo 202 instruction PDFs). Make it companion-aware — resolve bytes through the companion when the runtime tree lacks the file; a genuinely absent companion binary is unevaluable and skipped, never a duplicate failure; an absent non-companion file or a present-but-unreadable file still fails. Commit `0b60114d00`.
- Add a regression test in `test_catalogue_verification_verifiers.py` covering the companion-aware resolution (42 passed).
- Teach the shared wheel preflight the data-budget tests exclusion (`_data/**/tests/` legitimately absent).

## Outcome

- `dev/packaging/smoke_split_install.py` reproduces both the advisory-path (companion absent) and byte-identical-path (companion present) states end to end.
- `test_catalogue_verification_verifiers.py` passes with the new companion-aware regression coverage (42 passed).

## Notes

The smoke lane caught a split-install consumer no unit test covered (`validate_source_citations`), confirming its value. The lane commit for the smoke script itself was pending its final green run at record time. Peer M390 registry WIP in the shared working tree rides into tree-built wheels and can fail the lane's `validate_registry` probe for reasons outside this campaign's scope; the lane distinguishes owner in its own record rather than absorbing that unrelated failure.

## Final state

- The lane committed at `f0d2ecdf45` and is GREEN on run 6: exit 0, all nine checks pass — HEAD extract, slim wheel sheds every corpus binary, companion build, venv creation, slim-alone loud advisory plus instructive `registry verify` refusal, companion install, advisory-free load, and byte-exact verify clean.
- The lane caught four real pre-release defects across its runs:
  1. The non-companion-aware citation evidence gate (`validate_source_citations`), fixed in `0b60114d00`.
  2. Peer-WIP contamination of tree-built wheels, fixed by adding a git-archive HEAD extract inside the lane itself.
  3. A systemic latent defect: 49 source-catalogue sha256/byte entries were stamped from pre-`eol=lf` working copies, red on every fresh clone; fixed in `c7da92d2f1` plus `af40c71b4b`.
  4. The S17 application-facade re-export left uncommitted by the rate-limited executor; fixed in `172d152a25`.
- Watch item: a peer index operation has staged a deletion of `src/aeat/entrypoints/cli/tests/test_registry_corpus_companion_guard.py` in the shared index; the file is committed and intact at HEAD. If a peer lands a no-pathspec commit it would sweep that deletion — flagged per the shared-worktree discipline, not acted on here.
