---
tags:
  - '#audit'
  - '#m303-carry-reconciliation'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:270d2e704de41857573a0de2fa6867f74014c3b07df1440b8acf3eb3acd21fa6'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
  - "[[2026-06-21-m303-carry-reconciliation-adr]]"
  - "[[2026-08-10-m303-carry-reconciliation-s16-submitted-file-notice-route-reference]]"
---

# `m303-carry-reconciliation` audit: `M303 S16 submitted-file Notice route`

## Scope

Audited the S16 path from the Sede-recorded submitted-file layout refusal,
through the shared filed-capture accumulator and report models, to the live CLI
notice envelope. The review checks that the declaration-PDF fallback and stored
metadata remain authoritative, all capture modes share the notice lane, and
registered result payloads do not gain an advisory field.

## Findings

### test-boundary-direction | high | Outbound-adapter proof imported private inward layers

The initial S16 test placed the accumulator and envelope chain in the Sede
adapter suite by importing private application and CLI modules. That reverses
the package-direction boundary and makes an outbound-adapter test depend on
inner orchestration. Relocate the assertions by owner: the adapter proves its
recorded refusal and fallback, the application suite proves accumulator/report
propagation, and the CLI suite proves envelope forwarding through public seams.

### test-boundary-direction-remediated | low | The proof now follows package ownership

The corrected Sede test uses only Sede and public domain seams. The application
test owns the accumulator and capture-report proof, while the CLI test uses
public live report models and entrypoint-local relays to verify the envelopes.
Independent re-review found no remaining scoped issue.

## Recommendations

No follow-up recommendation. The boundary remediation passed focused tests and
independent re-review.
