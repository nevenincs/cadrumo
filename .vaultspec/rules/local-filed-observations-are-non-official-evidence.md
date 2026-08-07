# Local-filed observations are non-official evidence

Observations persisted by the local `file` flow MUST carry a non-official
`source_kind` (`app_filing`) and MUST NEVER be added to `_OFFICIAL_SOURCE_KINDS`
— the set that satisfies the cross-period clean-state gate
(`aeat_sede_justificante`, `aeat_sede_live_capture`, `aeat_csv_register`).

Automatic cross-period `previous_filing` carry may feed calculate and draft from
these observations, but they must never substitute for external AEAT filing
evidence.

A same-filing-year local chain may reach local verify and export ONLY when the
chain is present, value-consistent, revision-confirmed, and its only blockers are
the official-evidence delta. That path MUST surface a non-blocking
non-official-local-chain advisory and MUST NOT assert AEAT acceptance. Cross-year
priors, operator-manual sources, missing filing or observation data, and value or
revision divergence remain blocking.

Automatic local carry makes `source_kind` the load-bearing safety decision:
treating `app_filing` as official would let an unevidenced local-only chain
silently claim AEAT-evidenced acceptance.

## How

- **Good:** the local filing path stamps `source_kind="app_filing"`; the carry
  resolver reads it to populate a calculate binding; everything outside the narrow
  same-year scope raises `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`. A regression
  test asserts `app_filing not in _OFFICIAL_SOURCE_KINDS`.
- **Bad:** adding `app_filing` to `_OFFICIAL_SOURCE_KINDS`, or persisting the
  local-filed observation under an official `source_kind` to reuse the
  live-capture path.

Source: ADRs `2026-06-09-modelo-iva-routing-carry-adr` (D1),
`2026-06-19-crossperiod-filing-deadlock-adr`. Companions:
`aeat-safety-legal-gates`, `no-silent-under-declaration`.
