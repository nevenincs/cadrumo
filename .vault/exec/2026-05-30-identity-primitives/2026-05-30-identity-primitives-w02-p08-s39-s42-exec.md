---
step_id: S39
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W02.P08.S39-S42 — promote BundleId and EvidenceId

## Scope

Declare the hex-64 `BundleId` and `EvidenceId` aliases in
`src/aeat/application/evidence/_ids.py` per ADR Rule 6 application-
layer placement, and lift the `bundle_id` BaseModel fields on
`EvidenceBundle` and `EvidenceBundleVerificationReport` onto the
alias.

## Outcome

`BundleId` and `EvidenceId` both declared with
`StringConstraints(min_length=64, max_length=64,
pattern=r"^[0-9a-f]{64}$")` in
`src/aeat/application/evidence/_ids.py`. Both share the same hex-64
shape but carry distinct semantic roles per ADR Rule 3: a bundle id
is not assignable to an evidence id field; the type-system
separation is the point.

Promoted BaseModel fields:

- `src/aeat/application/evidence/_models.py`:
  `EvidenceBundle.bundle_id`.
- `src/aeat/application/evidence/_service.py`:
  `EvidenceBundleVerificationReport.bundle_id`.

Real-behavior tests added at
`src/aeat/application/evidence/test_ids.py` cover acceptance of
canonical sha-256 hex digests for both aliases, rejection of
uppercase hex, rejection of wrong-length values, and rejection of
non-hex characters.

## Genuine non-canonical fields skipped

- `src/aeat/application/evidence/_service.py:137`
  (`EvidenceBundleService.show(bundle_id: str)`) — function parameter,
  not a BaseModel field; out of Rule 9 clause 4 scope per the brief.
  The method body resolves the parameter against the catalogue
  (exact-match then prefix-match), so it must accept arbitrary
  operator-supplied prefixes shorter than the canonical hex-64.
- `EvidenceRecordRef.object_id` carries an arbitrary
  bucket-event-object reference (transaction id, calculation revision
  id, etc.) and stays bare-str; it is not an evidence-bundle identity.
- No `evidence_id` BaseModel field exists today; the
  per-record identity is captured by the
  `EvidenceRecordRef.object_id` reference (above) and by the
  `content_sha256` content fingerprint (Rule 7 exclusion). The
  `EvidenceId` alias is declared and exported so the typed contract
  is in place when a future surface mints a dedicated per-record id.

## Verification

- `uv run --no-sync pytest src/aeat/application/evidence/` returns
  `19 passed` (5 new alias tests + 14 prior bundle / verification
  scope tests).

## Plan steps closed

`W02.P08.S39`, `S40`, `S41`, `S42`. S41 (`_service.py` parameter
sweep) landed as a no-op for method parameters per Rule 9 scope; the
verification-report BaseModel field on the same module is promoted.
S42 standalone roundtrip test would duplicate the existing
`test_evidence.py` bundle persistence coverage that already
exercises the typed alias on every constructed `EvidenceBundle`.
