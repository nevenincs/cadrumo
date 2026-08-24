---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:09aa25414e3206b88d0145da249bc88ecdbba62fdcc176dfbfb65756d880e7e8'
step_id: 'S219'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Remove stale password-only creation and later-enrollment claims from operator guidance, four locale catalogues, and generated reference sequences, then regenerate CLI-owned artifacts

## Scope

- `docs/how-to/protect-data-access.md and docs/locales/ and docs/_sequences/`

## Description

- State mandatory verified recovery at creation, no later enrollment, and
  password-login independence in the operator guide and its Spanish, Catalan,
  and Hungarian catalogues.
- State that recovery material is restore-only, excluded from normal archives,
  and incomplete without an externally provisioned artifact and source capsule.
- Regenerate only the protect-data-access sequence goldens through their owning
  CLI and complete an independent formal review of that surface.

## Outcome

The protect-data-access operator guide and its three maintained catalogues no
longer describe password-only creation or later recovery enrollment. They state
that a profile creation refuses before publication unless exact recovery
possession is verified. Password login stays independent, and recovery proof is
limited to explicit restore.

Evidence:

- `python -m dev.docs.sequences check --page how-to/protect-data-access`: clean.
- The regenerated source message set and each target catalogue have matching
  message identifiers and zero untranslated or fuzzy active entries.
- `pytest -n 0 dev/docs/tests/test_docs_build.py`: 17 passed.
- Independent target-surface re-review: pass, with no critical, high, or
  medium findings.

## Notes

The CLI currently has no production recovery-artifact export command. Guidance
states this capability gap explicitly instead of promising an unavailable
operator workflow.

The profile-setup sequence contracts and generated goldens are external to this
commit and remain unresolved here. The full documented-command conformance gate
also has two external failures: a stale workstation agent contract and an
inline command in the concurrently changed profile setup guide. The full locale
gate remains red outside this Step: 30 of 57 pages are incomplete in each
target language, `download.md` introduces three dash violations per language,
and each language retains an orphan environment-overrides catalogue. No
non-S219 locale artifact is staged in this corrective commit.
