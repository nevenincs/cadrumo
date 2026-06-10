---
name: local-filed-observations-are-non-official-evidence
---

# Local-filed observations are non-official evidence

## Rule

Observations persisted by the local `file` flow (`persist_filed_revision_observation`) MUST
carry a non-official `source_kind` (`app_filing`) and MUST NEVER be added to
`_OFFICIAL_SOURCE_KINDS` — the set that satisfies the cross-period clean-state gate
(`aeat_sede_justificante`, `aeat_sede_live_capture`, `aeat_csv_register`). Automatic
cross-period `previous_filing` carry may feed calculate/draft from these observations, but
they must never substitute for external AEAT filing evidence when filing a dependent period.

## Why

Wave C wired automatic local cross-period carry: local `file` now persists the filed
revision's observations so a later period's calculate can auto-carry the prior value. The
load-bearing safety decision is the `source_kind`. The cross-period clean-state guard blocks
filing a dependent period whose upstream evidence is non-official
(`LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`). If `app_filing` were treated as official, an
unevidenced local-only chain could file a dependent period — a silent under-evidenced filing,
violating `aeat-safety-legal-gates` and `no-silent-under-declaration`. Stamping the carry
observation non-official keeps the prior value available for calculation while still demanding
a real justificante / CSV register / live capture before the dependent period is filed.

## How

- **Good:** `persist_filed_revision_observation` stamps `source_kind="app_filing"`; the carry
  resolver reads it to populate a calculate binding; filing a dependent period whose only
  upstream evidence is that `app_filing` observation still raises
  `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`.
- **Good:** a regression test asserts `app_filing not in _OFFICIAL_SOURCE_KINDS` and fails the
  moment it is added.
- **Bad:** adding `app_filing` to `_OFFICIAL_SOURCE_KINDS` to make cross-period filing "just
  work" — it launders an unevidenced local chain past the evidence gate.
- **Bad:** persisting the local-filed observation under an official `source_kind` to reuse the
  live-capture path verbatim — the non-official kind is the deliberate delta from that template.

## Source

ADR `2026-06-09-modelo-iva-routing-carry-adr` (accepted) codification candidate, ruling D1;
research `2026-06-09-modelo-iva-routing-carry-research`; commit `10167440f` (Wave C carry).
Companion to `aeat-safety-legal-gates`, `no-silent-under-declaration`, and
`ledger-derived-revisions-bundle-evidence`.
