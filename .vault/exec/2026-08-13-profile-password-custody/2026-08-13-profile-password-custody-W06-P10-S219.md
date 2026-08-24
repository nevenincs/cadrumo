---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:085c6b8483d0ccee385f2d24b79da0e134cd014e18d87ae8e86dbeddfc9f5bbc'
step_id: 'S219'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S219 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Remove stale password-only creation and later-enrollment claims from operator guidance, four locale catalogues, and generated reference sequences, then regenerate CLI-owned artifacts and ## Scope

- `docs/how-to/protect-data-access.md and docs/locales/ and docs/_sequences/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove stale password-only creation and later-enrollment claims from operator guidance, four locale catalogues, and generated reference sequences, then regenerate CLI-owned artifacts

## Scope

- `docs/how-to/protect-data-access.md and docs/locales/ and docs/_sequences/`

## Description

- State mandatory verified recovery at creation, no later enrollment, and password-login independence in operator guidance and all four CLI locales.
- State that recovery material is restore-only, excluded from normal archives, and incomplete without an externally provisioned artifact and source capsule.
- Replace stale password-only profile-setup prerequisites with truthful seeded-profile or stable-help sequences and regenerate their committed goldens.
- Regenerate the CLI-owned command reference, verify locale parity, and complete an independent formal review.

## Outcome

Operator-facing material no longer describes password-only creation or later recovery enrollment. Every creation lane is documented as refusing before publication unless exact recovery possession is verified. Password login stays independent, and recovery proof is limited to explicit restore.

Evidence:

- `python -m dev.docs.sequences check --page how-to/profile-setup`: clean.
- `python -m dev.docs.sequences check --page how-to/protect-data-access`: clean.
- `vaultspec-core spec reference generate --check`: generated CLI reference in sync.
- `python -m dev.locales scaffold --check` and `python -m dev.locales audit`: ca, en, es, and hu clean.
- Focused documented-command suite: 347 passed; two unrelated standing failures remain in the retired `app agent` contract and an existing inline profile-delete span.
- Comprehensive sequence-golden suite: 10 passed and two repository-wide gates failed on unrelated pages outside the two S219 pages.
- Independent S219 re-review: pass, with no critical, high, or medium findings.

## Notes

The CLI currently has no production recovery-artifact export command. Guidance states this capability gap explicitly instead of promising an unavailable operator workflow. No unrelated sequence, registry, live-facade, or translation worktree changes were modified or absorbed.
