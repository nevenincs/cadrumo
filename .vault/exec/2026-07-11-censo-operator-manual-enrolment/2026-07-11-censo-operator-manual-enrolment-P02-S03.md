---
tags:
  - '#exec'
  - '#censo-operator-manual-enrolment'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S03'
related:
  - "[[2026-07-11-censo-operator-manual-enrolment-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace censo-operator-manual-enrolment with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-07-11-censo-operator-manual-enrolment-plan placeholders are machine-filled by
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
     The Purge the retired verb family from the generated CLI reference generator and its conformance tests, and from the storage write-policy allowlist if enrolled and ## Scope

- `dev/docs/cli_reference.py`
- `dev/docs/tests/test_cli_reference_conformance.py`
- `src/aeat/application/storage_write_policy.py`
- `docs/cli/config.rst`
- `docs/cli/schemas.rst` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Purge the retired verb family from the generated CLI reference generator and its conformance tests, and from the storage write-policy allowlist if enrolled

## Scope

- `dev/docs/cli_reference.py`
- `dev/docs/tests/test_cli_reference_conformance.py`
- `src/aeat/application/storage_write_policy.py`
- `docs/cli/config.rst`
- `docs/cli/schemas.rst`

## Description

- Confirm the retired `config profile censo pull/compare/apply/show` verb family
  is absent from `dev/docs/cli_reference.py`, its conformance test, and the
  runtime storage write-policy allowlist (`src/cadrumo/application/storage_write_policy.py`).
- Confirm `docs/cli/config.rst` and `docs/cli/schemas.rst` carry no reference to
  the retired verbs, distinguishing legitimate `censo`-modelo (036) period-token
  prose from the retired verb family.

## Outcome

No production edit was required: the earlier P01/P02 landings (`3a48c4fe87`,
`0d2a13351c`) already purged the retired verb family from every surface this
Step scopes.

- `rg` for `profile_censo|censo_g313_launcher|parse_g313_html|_G313_LABELS|censo
  pull|censo compare|censo apply|censo show` across `dev/`, `docs/`, `.vaultspec/`
  returns zero hits outside a single historical retirement note in
  `_censo_sync.py`'s module docstring (describing the retirement, not citing a
  live verb).
- `src/cadrumo/application/storage_write_policy.py` carries zero censo tokens.
- `docs/cli/config.rst` and `docs/cli/schemas.rst` carry zero censo tokens; the
  only `censo` occurrences project-wide in generated CLI docs are the legitimate
  `censo modelos (036)` period-token help text on unrelated commands.
- The generated CLI reference and its conformance test
  (`dev/docs/tests/test_cli_reference_conformance.py`) pass (see the S10 gate
  battery run for the full suite result).

## Notes

None. This Step closes as verification-only: the deletion already landed under
this feature's P01/P02 waves.
