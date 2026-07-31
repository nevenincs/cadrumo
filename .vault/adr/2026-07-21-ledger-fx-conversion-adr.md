---
tags:
  - "#adr"
  - "#ledger-fx-conversion"
date: '2026-07-21'
related:
  - "[[2026-06-02-ledger-fx-conversion-adr]]"
  - "[[2026-06-02-ledger-fx-conversion-research]]"
supersedes:
  - '2026-06-02-ledger-fx-conversion-adr'
modified: '2026-07-21'
body_hash: 'sha256:1c31bcff3e6d1027ad1a3fe549fd9cf48c2cfdc5ceb540dc2a1af87cdb26f111'
---
# `ledger-fx-conversion` adr: `Dynamic ECB Data Portal resolution replaces the bundled rate snapshot` | (**status:** `accepted`)

## Problem Statement

`2026-06-02-ledger-fx-conversion-adr` adopted the ECB euro reference rate as the
canonical FX source and acquired it by bundling a point-in-time snapshot of the
ECB full history under the data tree, refreshed on release. The source decision —
the ECB rate as the official rate of Spanish law — is unchanged and correct. The
acquisition decision failed in practice and must be replaced.

Verification of the shipped artifact against the live ECB series found that the
bundled file was not an ECB snapshot at all. It carried 18 monthly samples for
two currencies; the real series is daily, spans 30+ currencies, and reaches back
to 1999. Its figures did not match the ECB's: for 2026-06-01 it asserted USD
1.1850 and GBP 0.8380 where the ECB published 1.1646 and 0.86493, a 3.1% GBP
error. Every one of its 36 values terminated in a zero at the fourth decimal,
which the real series does not, and the ECB quotes GBP at five decimals. The
refresh utility the prior decision relied on to keep the bundle current had no
caller in any release, CI, or CLI path. The file shipped in the wheel, so those
figures reached installed users, and the provider's own tests pinned their
expectations to them, so nothing in the suite could notice.

The operator directive is that no bundled rate document should exist: every date
resolves dynamically.

## Considerations

- The legal grounding is untouched: Ley 46/1998 art. 36 and the IRPF/IVA/PGC
  chain established in `2026-06-02-ledger-fx-conversion-research` still make the
  ECB reference rate the single official per-date source.
- A rate for a past date is immutable once published, so "dynamic" is a coverage
  and freshness property, not a volatility problem — the risk the prior decision
  guarded against (a moving number breaking reproducibility) does not arise.
- Reproducibility is already carried by provenance, not by the data file: the
  filing snapshot fingerprints `fx_rate` and `value_in_eur`, so a filed
  calculation remains re-derivable from its own record regardless of acquisition.
- A crippled offline table degrades silently — an uncovered currency or date is
  indistinguishable from a genuinely unpublished one, and both book a zero EUR
  value. That failure mode is what shipped.

## Considered options

- **Correct and keep the bundle.** Replace the fabricated file with the genuine
  ECB history and wire the refresh to release. Rejected: it preserves a snapshot
  that is stale between releases by construction, adds roughly 3 MB to the wheel,
  and leaves the same silent-degradation shape when a date falls past the
  snapshot edge.
- **Trimmed real bundle plus dynamic fallback.** Rejected: two acquisition paths
  for one value, and the bundled half would mask failures in the dynamic half.
- **Dynamic per-date resolution against the ECB Data Portal.** Chosen. One
  acquisition path, complete coverage of currency and date, no shipped data.

## Constraints

- The lookup is on the ledger import path, so a per-row network call is
  unacceptable; resolution must be memoized per currency and date.
- The suite must not reach the network, so the transport is an injected seam.
- A transport failure must not be reported as a missing rate: conflating them
  would let an outage silently book rows at zero EUR, which
  `no-silent-under-declaration` forbids.
- The ECB publishes only on TARGET working days and answers a non-publication
  date with an empty result set rather than an error.

## Implementation

Resolve each rate from the ECB Data Portal daily spot series at lookup time. The
provider queries one currency over a window ending at the requested date and
widened backwards by a bounded lookback, then takes the most recent observation
in that window — which is the operation-date rate when the ECB published that
day, and the most recent prior publication otherwise. The EUR-base quote is
inverted into the CCY-to-EUR multiplier the normalization service expects, as
before.

The lookback is bounded rather than unlimited. The prior implementation searched
backwards without limit, which combined with the sparse bundle meant a rate could
be drawn from an arbitrarily distant date; a fourteen-day bound covers the
longest TARGET closure with margin while refusing to convert at a materially
stale rate.

Resolved results are memoized per currency and date for the life of the provider,
and the process-wide default provider is cached, so a multi-row import re-uses
rates across rows. The HTTPS transport is constrained to the ECB Data Portal
host, its timeout is a central settings field, and it is injectable so suites
declare observations instead of reaching the network. Transport and protocol
failures raise the existing exchange-rate provider error; only a genuinely
unpublished currency or an empty window yields no rate. The bundled data file,
the refresh utility, and the corpus rate fixture are deleted.

## Rationale

Dynamic resolution is the only option that makes coverage total. The defect was
not that the bundled numbers were wrong — that was a symptom — but that a shipped
table has an edge, and every edge case degrades into the same silent zero. A
per-date query has no edge: any currency the ECB publishes, on any date it
published, resolves, and anything else is an explicit refusal.

It also removes the class of failure this episode belongs to. A committed data
file asserting regulatory figures can drift from its authority without any gate
noticing, exactly as
`legal-grounding-verifies-bundled-authoritative-corpus` warns; deleting the file
removes the surface on which that drift can occur, rather than adding a gate to
watch it.

The prior decision's reproducibility argument does not survive scrutiny: past ECB
rates are immutable, and the filing snapshot already fingerprints the rate it
used, so the filed artifact is re-derivable from its own provenance whether the
rate was bundled or fetched.

## Consequences

- Gains: complete currency and date coverage; no shipped data to fabricate,
  stale, or drift; roughly 3 MB of wheel weight never incurred; a transport
  failure is now loud rather than a silent zero; the fabricated figures are out
  of users' hands.
- Costs: ledger import of foreign rows now requires network reachability, which
  the prior decision explicitly avoided. This is the real trade being made. An
  operator importing offline gets a refusal naming the ECB lookup rather than a
  silently unconverted row.
- The bounded lookback is a behaviour change beyond acquisition: a date more than
  fourteen days after the last publication now refuses instead of silently using
  a distant rate. The corpus fidelity fixture depended on the unbounded reach and
  was re-declared across its period.
- Supersedes the acquisition half of `2026-06-02-ledger-fx-conversion-adr`; that
  record's source, legal grounding, and inversion decisions stand unchanged.
- Pitfall: the memo is per-process and unbounded. A long-lived process converting
  across many currencies and dates accumulates entries; the ledger import
  lifetime makes this immaterial today, and a bounded cache is the follow-on if a
  long-running server surface ever consumes the provider.
