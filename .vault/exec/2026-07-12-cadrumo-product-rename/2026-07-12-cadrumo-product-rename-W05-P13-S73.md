---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S73'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
  - "[[2026-07-14-cadrumo-product-rename-audit]]"
---

# Update release templates, checklist, and current verification proofs

## Scope

- `docs release and verification surfaces`

## Description

- Rewrite `docs/_release_checklist.yaml` (the machine-validated `ReleaseChecklist` read by `dev/release/readiness.py`) so its header comment and beta-channel note name Cadrumo and the future `cadrumo-beta` PyPI project instead of `aeat-cli`/`aeat-cli-beta`, and so the audit-state-gate check description points at `src/cadrumo/__init__.py` instead of `src/aeat/__init__.py`; landed in `ba5bc9e033`.
- Rewrite `docs/_release_notes_template.md` (the hand-filled GitHub Release body companion to `CHANGELOG.md`) so the heading, `uvx --from`/`uv tool upgrade`/`pip install` install commands, and verification checklist name the `cadrumo` distribution instead of `aeat-cli`; landed in the same commit.
- Rewrite the current verification proofs under `docs/verification/` (`claude-code-install-proof.md`, `claude-desktop-install-proof.md`, `cowork-install-proof.md`, `neve-marketplace-install-proof.md`, `support-matrix.md`) to record the Cadrumo/`aeat`/AEAT identity boundary; landed in the same commit.
- Confirm no stale `aeat-cli` token survives in either the checklist or the notes template.

## Outcome

The release checklist, release-notes template, and current verification proofs all read Cadrumo product identity and `aeat` CLI naming consistently with the accepted naming law, and `dev/release/readiness.py` continues to validate the checklist schema unchanged. Audit `2026-07-14-cadrumo-product-rename-audit` grants this Step's Phase 3/Phase 8 approval on the basis of the principal-documentation-writer session's direct review of the release-and-verification surface set at HEAD.

## Notes

This record documents work already committed in `ba5bc9e033` under the combined subject `W05.P13.S68-S71, S73`. Per the plan text, this Step "does not block PyPI publication; after all three PyPI distributions are published, it blocks only GitHub Release creation" — that gate remains open in `RELEASING.md` independent of this content review closing.
