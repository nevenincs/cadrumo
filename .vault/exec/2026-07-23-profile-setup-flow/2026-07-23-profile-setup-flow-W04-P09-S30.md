---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:4c259ad82a89ac31e6750fcc4dbfaea8cac008fe41807fb710a62957eeda964a'
step_id: 'S30'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Verify the portable-export shape against the compatibility lifecycle for every schema addition

## Scope

- `src/cadrumo/domain/user_profile/_portable_export.py`

## Description

- Prove, rather than assert, that the portable export carries every schema surface this campaign added: a populated record with divergence rows, descendant extensions, and the setup-incomplete status round-trips through the version-3 bundle with strict profile equality and the status surviving (a drop would re-default to active and fail).
- Confirm the no-version-bump conclusion under the pre-release compatibility regime: the export composes the whole record generically, its shape did not change, and the commit adds no fabricated old-version fixture, no upgrader, and touches no floor constant — exactly what the regime requires.
- Add the export-boundary anti-tautology: mangling a unique fact value inside the serialized bundle (asserted-applied) makes the reloaded profile strictly differ.

## Outcome

Landed as `807a51aae2` on `chore/s29-s30-roundtrip-hardening`. Review verdict: clean pass; the compatibility-lifecycle rules were verified respected in both directions — the shape is carried, not versioned against bytes nothing released ever wrote.

## Notes

- The bundle version stays three; any future post-checkpoint bump follows the frozen-floor rules, not this campaign's surfaces.
