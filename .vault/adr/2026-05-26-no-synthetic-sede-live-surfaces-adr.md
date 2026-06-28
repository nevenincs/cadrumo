---
tags:
  - '#adr'
  - '#no-synthetic-sede-live-surfaces'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-research]]'
  - '[[2026-05-07-live-parity-oracle-adr]]'
  - '[[2026-05-08-live-parity-oracle-adr]]'
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---



# `no-synthetic-sede-live-surfaces` adr: `Synthetic data is prohibited on AEAT-hosted live surfaces` | (**status:** `accepted`)

## Problem Statement

The live-parity architecture previously allowed selected AEAT-hosted simulator
or verifier surfaces to accept synthetic inputs. That posture conflicts with
the current operator constraint: synthetic data must not be sent to Sede or
AEAT-hosted form surfaces.

The conflict is concrete. Modelo 100 Renta WEB Open and Modelo 349 GROI/IXVI
currently declare `synthetic_data_allowed = true` on live AEAT hosts. Those
entries were intentionally introduced through live-parity ADRs, so changing
them requires an architectural decision rather than a silent registry edit.

## Considerations

The declaration-extraction acquisition rows cannot rely on synthetic
preview/download flows. For modelos 180, 036, 369, 720, and 840, acceptable
fixture acquisition is limited to operator-provided authorised fixtures,
read-only retrieval of operator-owned filed declarations, or static official
artifacts that directly match the parser surface.

The broader live-parity system still needs a way to retain evidence already
captured from official surfaces. Local replay payloads can remain valid if
they are already retained in the corpus, source-tracked, and do not require new
live synthetic input.

The 2026-05-07 authenticated-synthetic-surface taxonomy remains useful for
distinguishing authenticated callable verification services from read-only
filed-declaration surfaces, but its permission for synthetic input on
AEAT-hosted endpoints is superseded by this ADR.

## Constraints

No implementation may send synthetic taxpayer, counterparty, declaration,
profile, or form data to Sede or AEAT-hosted live surfaces.

Any live cross-reference whose `allowed_hosts` include an AEAT-owned host under
`agenciatributaria.gob.es` or `aeat.es` must declare
`synthetic_data_allowed = false`.

`open_simulator` and `authenticated_simulator` remain valid classifications,
but those classifications no longer imply permission to send synthetic input
to AEAT-hosted endpoints. They identify the shape of the surface, not the
legality of the input payload.

Read-only authenticated retrieval remains allowed only for operator-owned
filed declarations and only through the existing authentication and
remote-state guards.

## Implementation

Update the registry and guard model so AEAT-hosted cross-references cannot
advertise synthetic input:

- Set Modelo 100 Renta WEB Open to `synthetic_data_allowed = false`.
- Set Modelo 349 GROI and IXVI cross-references to
  `synthetic_data_allowed = false`.
- Add remote-state guard validation that rejects AEAT-hosted policies with
  `synthetic_data_allowed = true`.
- Add registry-schema validation that rejects AEAT-hosted
  `LiveCrossReferenceDecision` entries with `synthetic_data_allowed = true`.
- Update tests that currently construct AEAT-hosted policies with
  `synthetic_data_allowed = true` to use non-AEAT-host examples, local replay,
  or non-synthetic operator-authorised fixtures.
- Preserve existing replay-based tests where no new live AEAT request is made.

The declaration-extraction plan remains blocked for modelos without qualifying
fixtures. It must not replace the missing fixtures with live preview/download
generation using synthetic data.

## Rationale

The hard legal and operator-safety rule is clearer than a case-by-case
exception model. A host-based invariant is also easier to audit: if a
cross-reference points at AEAT infrastructure, the registry must not claim
synthetic input is allowed.

Keeping `open_simulator` and `authenticated_simulator` avoids conflating
surface shape with input policy. Renta WEB Open is still an open simulator;
GROI and IXVI are still authenticated callable verifier surfaces. What changes
is the allowed data class for live execution.

Local replay evidence remains useful because it does not contact AEAT and does
not send new data. The implementation should distinguish replay parity from
live parity rather than discarding existing evidence.

## Consequences

This ADR supersedes the part of the 2026-05-07 live-parity ADR that allowed
`synthetic_data_allowed = true` for AEAT-hosted authenticated simulator
surfaces. It also supersedes the implied Modelo 100 Renta WEB Open posture that
treated AEAT's open simulator as an acceptable live synthetic oracle.

Some live tests must be rewritten or disabled unless they can run against
operator-authorised non-synthetic data. This is intentional; a passing live
test is not worth sending synthetic data to AEAT.

Registry validation becomes stricter. Existing non-AEAT local simulators,
replay fixtures, and static official sources are unaffected.

Declaration fixture acquisition remains slower: missing declaration PDFs must
come from authorised fixtures, read-only filed-copy retrieval, or static
official artifacts, not generated synthetic previews.
