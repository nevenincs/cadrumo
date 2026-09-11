---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:9fa46cc3caec0890665feb1b6e683653f7c19e42c2a40c1a27becf1027c5c30a'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# `facts-registry` audit: `S74 activity selector review`

## Scope

Reviewed plan step `W03.P13.S74` against the governed-fact ADR, source-grounded
Article 95 rate work, and the current candidate diff. The scope was the four
authored Modelo 036 selector facts, AEAT table capture and source row, Article
95 bridge evidence, adapter retirement, entity-set TOML parsing, and focused
tests. Concurrent Article 109/110 work was excluded.

## Findings

No critical, high, or medium findings. The finite AEAT table is hash-pinned,
the source and Article 95 citations bind each selector to its vocabulary and
legal partition, the variants do not claim an earlier mapping, and the retired
adapter no longer publishes the same identities. The TOML arrays load as
immutable entity sets and the focused tests prove resolution and prior-date
refusal.

### m036-table-date-semantics | low | The page update timestamp is recorded as a publication date

The retained AEAT page explicitly says that it was updated on 2026-03-26, which
supports the conservative variant and source lower bound used here. It does not
expressly state that day as the page's original publication date, so
`published_at` labels a revision/update timestamp more strongly than the
source text proves. This does not create a retrospective claim or affect the
fail-closed resolver.

## Recommendations

If the source catalogue needs to distinguish publication from last revision,
record this datum as an update/revision value or clarify the source metadata
contract. Retain the current 2026-03-26 lower bound unless an earlier exact
AEAT mapping is captured.
