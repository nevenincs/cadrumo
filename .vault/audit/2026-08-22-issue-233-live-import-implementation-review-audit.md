---
tags:
  - '#audit'
  - '#issue-233-live-import'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:c4bbc35be247542b1f776ded7481fe874f3b8e13da4f7cf880f8b08b7499ffcd'
related: []
---

# `issue-233-live-import` audit: `implementation review`

## Scope

Reviewed the issue 233 phase-two live filed-observation composition, its
justificante-only boundary, source lexical retention, missing-work-unit path,
refusal behavior, amendment reach, and filed-pull CLI reporting.

## Findings

### baseline-time | medium | Imported historical filing uses capture-run time

The live source passes no clock to `import_external_filing_source`, so the
external baseline is dated at the current capture run rather than the filed
observation's authoritative `presented_at`. This makes historical amendments
chronologically misleading and must be corrected before commit.

## Recommendations

Pass the filed observation's `presented_at` as the baseline clock and pin it in
the behavioral test. Retain the current refusal of M303, non-numeric manifests,
and justificante-only metadata; none of those sources can honestly satisfy the
numeric complete-baseline contract.

The finding is resolved in the corrective implementation: the live observation
now supplies `presented_at` as the baseline clock, and the real persistence test
asserts the filed-record timestamp exactly.

### independent-phase-two-verification | low | Live baseline behavior is sound but two refusal branches lack direct ratchets

Independent review of `af98793af5b482bca436886f058709f13a958251`
confirmed the production `app live filed pull` path reaches the accumulator and
the new baseline composition after encrypted observation persistence and strict
justificante parsing. Exact observation lexical strings enter the phase-one
source service unchanged; its independent registry-required completeness gate
and pre-creation validation remain authoritative. A matching parsed
justificante supplies evidence identity, authenticated taxpayer identity is
rechecked, `presented_at` supplies both creation and filing time, a missing work
unit is created, and the baseline is immediately amendable. Justificante-only,
M303, and value-kind non-numeric observations return without a financial
baseline; a malformed numeric lexical reaches phase-one refusal before work-unit
creation. Focused live and rendering lanes passed 21 tests across unit and
integration markers, and touched-file Ruff is clean.

The new behavioral file directly ratchets the positive create/amend path,
justificante-only refusal, and incomplete-manifest no-work-unit result, but it
does not directly exercise the explicit M303 or non-numeric early-return
branches. Add narrow negative tests for both so a future deletion or inversion
cannot silently fabricate a baseline. This is a non-blocking coverage finding:
the closed branches are direct, precede source composition, and were verified
statically. The phase remains partial and does not claim submitted-file/PDF
declaration extraction owned by issue 305.
