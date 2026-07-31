---
tags:
  - '#exec'
  - '#google-optional-adapter-boundary'
date: '2026-07-14'
modified: '2026-07-14'
body_hash: 'sha256:47099fc3b6827fe8150a4880655d44bb674bc1f8bf74e4d93f5b60959563c0d4'
step_id: 'S03'
related:
  - "[[2026-07-14-google-optional-adapter-boundary-plan]]"
---

# Retag only the legacy Google plan as google-oauth-legacy-plan-retirement through the canonical metadata command

## Scope

- `.vault/plan/2026-05-13-google-oauth-plan.md`

## Description

- Preflight the inherited dirty legacy-plan target at HEAD `2fde8d6e0dd91c89d3591eb9556be776131c65f6`.
- Record the pre-mutation target blob `843e1911b64731cf9951e74397c88126ba46598d` and checkbox-row baseline.
- Run `uv run vaultspec-core vault set-frontmatter 2026-05-13-google-oauth-plan --tags '#plan' --tags '#google-oauth-legacy-plan-retirement' --dry-run --json`.
- Require the dry run to report `status: updated`, `changed: true`, no checks, and predicted blob `5f4bb47edb4664f69e49b2857a559a7cee3ebc79`.
- Guard the target against concurrent change, then run the same canonical command without `--dry-run`.
- Verify the exact frontmatter delta, unchanged checkbox-row fingerprint, and feature-scoped Vault checks.

## Outcome

Retagged only the legacy Google plan for the retirement archive workflow. The canonical command replaced feature tag `#google-oauth` with `#google-oauth-legacy-plan-retirement` while preserving directory tag `#plan`, every other frontmatter field, and the body text and checkbox content.

The applied command reported `status: updated`, blob `5f4bb47edb4664f69e49b2857a559a7cee3ebc79`, and no checks. All 183 checkbox rows remain 76 checked and 107 open, with SHA-256 `cb540ee979c5fb3d581926d402ddf43de92d5cedbcfeb7c5736b896693e954a6`.

Feature-scoped `frontmatter`, `placeholders`, `body-links`, `links`, `dangling`, `schema`, and `annotations` checks each exited successfully with zero diagnostics. Targeted `git diff --check` also passed.

## Notes

The target contained inherited reconciliation and checkbox work before S03. The canonical serializer produced its predicted normalized blob while preserving the normalized row fingerprint. This Step made no production source or test change. The parent plan Step remains unchecked, and no commit was created.
