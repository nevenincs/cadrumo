---
tags:
  - '#exec'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:f33694219dfd492d8aa86b4e3c88cc042d496a51bb37e3d7b3a9a6c3de28be24'
step_id: 'S02'
related:
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---

# Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then implement the canonical profile-password assessment, typed reasons, safe derived facts, exact-sequence behavior, and advisory strength while deleting obsolete generic profile-policy branches

## Scope

- `src/cadrumo/core/_credentials.py`

## Description

- Ground the credential implementation and accepted decision through semantic
  code and Vaultspec discovery, then confirm live symbols and consumers exactly.
- Establish the profile-specific scalar, strict UTF-8 byte, and surrogate
  contract as one pure core assessment.
- Return only a finite typed refusal reason, scalar and byte measurements, and
  an independent advisory strength band.
- Delete the generic eight-character profile floor, validity-coupled strength
  branch, and public character-class helper instead of retaining aliases.
- Verify lint, format, diff hygiene, and direct probes of the contract's
  principal refusal and acceptance paths.

## Outcome

- `ProfilePasswordAssessment` contains no submitted password, rewritten value,
  hash, or fingerprint; surrogate input exposes no encoded byte count.
- `ProfilePasswordRefusalReason` distinguishes surrogate, lower scalar, upper
  scalar, and UTF-8 byte refusals without operator prose.
- The 15-through-256 scalar and 1,024-byte bounds now have one core owner.
- `PassphraseStrength` is advisory only and has no refusal member or validity
  threshold.
- Ruff lint and formatting, targeted direct boundary probes, and `git diff
  --check` pass for the owned implementation.

## Notes

The facade and existing application consumers intentionally remain for S03 and
S07. Until those ordered steps land, they still request removed legacy symbols;
this execution record does not claim the whole feature tree is coherent yet.
