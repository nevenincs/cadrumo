---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S01'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-release-pipeline with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-07-27-canonical-release-pipeline-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Create the burned-version ledger as a committed data file seeded with 0.2.0 and 0.2.1, each entry carrying version, burn date, and one-line reason, loaded by a typed reader, gate: uv run --no-sync pytest dev/release/tests/test_burned_versions.py -q passes with tests covering both seeded entries and refusal of a malformed or duplicate entry and ## Scope

- `dev/release/burned_versions.toml`
- `dev/release/version_identity.py`
- `dev/release/tests/test_burned_versions.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Create the burned-version ledger as a committed data file seeded with 0.2.0 and 0.2.1, each entry carrying version, burn date, and one-line reason, loaded by a typed reader, gate: uv run --no-sync pytest dev/release/tests/test_burned_versions.py -q passes with tests covering both seeded entries and refusal of a malformed or duplicate entry

## Scope

- `dev/release/burned_versions.toml`
- `dev/release/version_identity.py`
- `dev/release/tests/test_burned_versions.py`

## Description

- Search the tree for any existing burned, retired, forbidden, or yanked version concept.
- Read the one existing version-ownership authority and the owning package's facade.
- Add the committed ledger data file beside its reader so neither ships alone.
- Add the typed reader with refusal on every under-specified shape.
- Add the test module and prove it non-vacuous by mutation.

## Outcome

Landed under the commit subject `feat(release): add the burned-version ledger,
seeded with the two deleted releases`.

The ledger carries the two partial releases that were deleted rather than
delivered. Each entry records the version, the burn date, and a reason stating
the exposure, because a burn nobody can audit later is the shape a future reader
deletes as noise.

The reader refuses rather than degrading. An absent, malformed, under-specified,
duplicate-bearing, or wrong-shaped ledger raises instead of parsing to an empty
set. Reading empty is the silent failure this exists to prevent: the downstream
identity guard would then report a version as unburned when somebody had
deliberately burned it, which is precisely the outcome the ledger was introduced
to make impossible.

Gate: the Step's declared command passes at fourteen tests. Coverage is both
seeded entries, the auditable-evidence requirement on every entry, the negative
case for a version never published, the reason lookup the identity guard will
quote in its refusal, the data-beside-reader placement, seven parametrised
malformed shapes each refusing by name, the duplicate-version case, and the
absent-file case.

Anti-tautology proof: dropping one seeded entry from the ledger turns two tests
red; restoring it returns fourteen green. The gate detects the thing it exists
to detect rather than passing regardless.

## Notes

Discovery substitution, recorded because it departs from the standing mandate.
The semantic discovery service could not be used: the shared daemon resolves its
code from a sibling project's live working tree, which is mid-refactor, so every
index job this workspace queued died on an import error against half-edited
code. Six remediation attempts failed, and each destructive retry reset
accumulated index progress rather than advancing it.

Discovery was therefore performed manually and exhaustively instead, and its
result is recorded here so the substitution is auditable rather than assumed: no
burned, retired, forbidden, or yanked version concept exists anywhere in the
tree; the sole existing version-ownership authority checks one package index
over the network and raises on conflict; and the owning package exposes no
symbol facade to route through. There was accordingly no canonical owner to
duplicate, which is the specific risk the mandate exists to prevent.

The infrastructure defect belongs to the sibling project and is outside this
plan's scope. It is not a cadrumo fault and no cadrumo change can remedy it.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
