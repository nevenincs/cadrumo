---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:d291478a329747d37bae0318cf66a058df24449f856edb61f96b1cc2ddf59775'
step_id: 'S238'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove certificate backend selectors and replay-specific fields from every payload and schema projection while preserving independent master-key keyring custody contracts

## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py`
- `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`

## Description

- Sweep the two named payload modules for certificate backend selectors and replay-specific fields.
- Confirm the master-key custody contract this Step preserves is still projected.
- Disambiguate the surviving backend field against the certificate selectors the Step removes.

## Outcome

All three clauses hold, and the third is the one a careless sweep would have broken.

The certificate payloads project no backend descriptor, and the secret-mutation payload records why: named certificate secrets have exactly one storage authority, so no selector is meaningful. That payload also never carries the secret value, exposing only whether one is registered and whether the call rotated an existing secret. The replay-specific fields are absent from the modelo auxiliary payload module.

The surviving `backend_kind` field belongs to the login result and names the master-key custody backend that performed the unwrap. That is the independent keyring custody contract this Step explicitly preserves, not a certificate backend selector; removing it on a name match would have destroyed the contract the Step was written to protect.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
