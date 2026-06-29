---
name: local-filed-observations-are-non-official-evidence
trigger: always_on
---

# Local-filed observations are non-official evidence

## Rule

Observations persisted by the local `file` flow (`persist_filed_revision_observation`) MUST
carry a non-official `source_kind` (`app_filing`) and MUST NEVER be added to
`_OFFICIAL_SOURCE_KINDS` — the set that satisfies the cross-period clean-state gate
(`aeat_sede_justificante`, `aeat_sede_live_capture`, `aeat_csv_register`). Automatic
cross-period `previous_filing` carry may feed calculate/draft from these observations, but
they must never substitute for external AEAT filing evidence. A same-filing-year local chain
may reach local verify/export only when the chain is present, value-consistent,
revision-confirmed, and its only blockers are the official-evidence delta; that path MUST
surface a non-blocking non-official-local-chain advisory and MUST NOT assert AEAT acceptance.
Cross-year priors, operator-manual sources, missing filing/observation data, and value or
revision divergence remain blocking.

## Why

Wave C wired automatic local cross-period carry: local `file` now persists the filed
revision's observations so a later period's calculate can auto-carry the prior value. The
load-bearing safety decision is the `source_kind`. The cross-period clean-state guard blocks
unsafe dependent filings whose upstream evidence is non-official
(`LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`). Decision B later narrowed one reachability gap:
same-filing-year local reconstruction may proceed to local export with a warning when every
upstream dependency is otherwise clean and only the official-evidence delta is missing. If
`app_filing` were treated as official, an unevidenced local-only chain could silently claim
AEAT-evidenced acceptance, violating `aeat-safety-legal-gates` and
`no-silent-under-declaration`. Stamping the carry observation non-official keeps the prior
value available for calculation while still disclosing the local-only basis and still demanding
a real justificante / CSV register / live capture before any official-evidence assertion.

## How

- **Good:** `persist_filed_revision_observation` stamps `source_kind="app_filing"`; the carry
  resolver reads it to populate a calculate binding; a same-filing-year, value-consistent,
  revision-confirmed local chain whose only blockers are the official-evidence delta reaches
  local verify/export with a non-blocking non-official-local-chain advisory.
- **Good:** cross-year local chains, operator-manual sources, missing filing/observation data,
  and value or revision divergence remain blocking; the official-evidence delta still raises
  `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE` outside the narrow same-year advisory scope.
- **Good:** a regression test asserts `app_filing not in _OFFICIAL_SOURCE_KINDS` and fails the
  moment it is added.
- **Bad:** adding `app_filing` to `_OFFICIAL_SOURCE_KINDS` to make cross-period filing "just
  work" — it launders an unevidenced local chain past the evidence gate.
- **Bad:** persisting the local-filed observation under an official `source_kind` to reuse the
  live-capture path verbatim — the non-official kind is the deliberate delta from that template.

## Source

ADR `2026-06-09-modelo-iva-routing-carry-adr` (accepted) codification candidate, ruling D1;
research `2026-06-09-modelo-iva-routing-carry-research`; commit `10167440f` (Wave C carry).
Refined same-year Decision B scope: ADR `2026-06-19-crossperiod-filing-deadlock-adr`,
commit `84add274d`.
Companion to `aeat-safety-legal-gates`, `no-silent-under-declaration`, and
`ledger-derived-revisions-bundle-evidence`.
