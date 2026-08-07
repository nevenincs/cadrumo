---
name: local-filed-observations-are-non-official-evidence
trigger: always_on
---

# Local-filed observations are non-official evidence

## Rule

Observations persisted by the local `file` flow MUST carry a non-official
`source_kind` (`app_filing`) and MUST NEVER be added to `_OFFICIAL_SOURCE_KINDS`
— the set that satisfies the cross-period clean-state gate
(`aeat_sede_justificante`, `aeat_sede_live_capture`, `aeat_csv_register`).

Automatic cross-period `previous_filing` carry may feed calculate and draft from
these observations, but they must never substitute for external AEAT filing
evidence.

A same-filing-year local chain may reach local verify and export ONLY when the
chain is present, value-consistent, revision-confirmed, and its only blockers
are the official-evidence delta. That path MUST surface a non-blocking
non-official-local-chain advisory and MUST NOT assert AEAT acceptance.
Cross-year priors, operator-manual sources, missing filing or observation data,
and value or revision divergence remain blocking.

## Why

Automatic local cross-period carry makes `source_kind` the load-bearing safety
decision: the clean-state guard blocks unsafe dependent filings whose upstream
evidence is non-official. Treating `app_filing` as official would let an
unevidenced local-only chain silently claim AEAT-evidenced acceptance, violating
`aeat-safety-legal-gates` and `no-silent-under-declaration`.

## How

- **Good:** the local filing path stamps `source_kind="app_filing"`; the carry
  resolver reads it to populate a calculate binding; a same-filing-year,
  value-consistent, revision-confirmed local chain whose only blockers are the
  official-evidence delta reaches local verify and export with a non-blocking
  advisory. Everything outside that narrow scope raises
  `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`. A regression test asserts
  `app_filing not in _OFFICIAL_SOURCE_KINDS`.
- **Bad:** adding `app_filing` to `_OFFICIAL_SOURCE_KINDS`, which launders an
  unevidenced chain past the gate.
- **Bad:** persisting the local-filed observation under an official
  `source_kind` to reuse the live-capture path verbatim.

## Source

ADR `2026-06-09-modelo-iva-routing-carry-adr` (ruling D1); same-year scope
refined by `2026-06-19-crossperiod-filing-deadlock-adr`. Companions:
`aeat-safety-legal-gates`, `no-silent-under-declaration`,
`ledger-derived-revisions-bundle-evidence`.
