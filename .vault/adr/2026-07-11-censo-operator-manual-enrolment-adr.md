---
tags:
  - "#adr"
  - "#censo-operator-manual-enrolment"
date: '2026-07-11'
related:
  - "[[2026-07-12-censo-operator-manual-enrolment-research]]"
supersedes:
  - '2026-07-10-censo-g313-launcher-fix-adr'
superseded_by: '2026-07-25-censal-profile-autofill-adr'
modified: '2026-07-25'
---
# `censo-operator-manual-enrolment` adr: `censal facts are operator-manual; retire the live censo scrape` | (**status:** `superseded`)

> **The central factual premise below is disproven. Do not act on it.**
> This record states that `/wlpl/BUGC-JDIT/MdcAcceso` returns HTTP 404 and
> that AEAT exposes no read-only censal projection, and concludes that the
> automated read must be abandoned. The launcher renders: 200, roughly
> 85KB, eleven tables, carrying the taxpayer's NIF, name and censal
> information, confirmed on a live authenticated session on 2026-07-25.
>
> The 404 was real but was measured against hosts that do not serve the
> route at all. AEAT dispatches an authenticated session to one of several
> numbered hosts, and the same path with the same cookies returns 200 on
> one, a genuine 404 on others, and an auth-gate bounce on another. A 404
> surviving a valid session is a routing fact about the host, not a fact
> about the endpoint, and reading it as the latter is what produced this
> record's conclusion.
>
> The reasoning that follows remains sound on its own terms, and its
> safety argument still binds: reading current census state by operating
> the modification tool would be a live-write path with extra steps. What
> changed is the premise that operating the modification tool was the ONLY
> route. This record's own revival condition - a genuine consulta-only
> endpoint would justify a new ADR - is met, and
> `2026-07-25-censal-profile-autofill-adr` is that record.

## Problem Statement

The live censo (Modelo 036 / "Mis Datos Censales") read is broken and cannot be
safely fixed. A 2026-07-10 authenticated live investigation proved the
configured launcher `/wlpl/BUGC-JDIT/MdcAcceso` returns HTTP 404, and that AEAT
exposes NO read-only "Mis datos censales" projection: the real census data lives
only inside the multi-step "Censos WEB" ZKoss (`.zul`) MODIFICATION tool
(`BU36-ASIS/M036/index.zul`), behind a representation gate and a prefilled-036
modification form. Reading census data therefore requires operating a write
tool. This ADR decides the direction and supersedes
`2026-07-10-censo-g313-launcher-fix-adr` (whose chosen option — drive/wait — is
rejected). Decided by an authorized Fable architecture pass on operator
delegation.

## Considerations

- `aeat-safety-legal-gates` prohibits live AEAT mutation paths and mandates
  guarding every external write surface. "Censos WEB" IS a write surface (Baja /
  Modificación de datos).
- ZKoss multiplexes reads, panel-opens, and submits over one session-rekeyed
  `zkau` AU-engine POST channel, so a "never-submit" guard cannot be structural —
  it degrades to heuristics over button captions and generated component ids. The
  P02.S04 capture already saw that heuristic surface misbehave (a "Modificación
  de datos" click that silently did nothing).
- The consuming surface already degrades honestly: the overview calendar warns
  `censo.enrolment_unverified` for modelos 100/130/303/390 and refuses strict
  projection when censo is unverified (`no-silent-under-declaration` satisfied
  today). The operator-manual profile path (`config profile edit`) already
  exists.

## Considered options

1. **Drive the Censos-WEB modification tool read-only.** Rejected: a read path
   "one accidental submit away from mutating AEAT census state" is a live-write
   path with extra steps — the category `aeat-safety-legal-gates` prohibits — and
   the guard cannot be made structural on a ZKoss AU channel. Also
   disproportionately fragile (multi-step SPA AEAT reshapes freely, validatable
   only by operator-run live pulls).
2. **Hunt for a true read-only consulta endpoint elsewhere on the sede.**
   Rejected as a workstream: P01 swept the censal hub and found none; P02.S04
   concluded no read-only projection exists. If AEAT ever ships one, a new ADR
   revives the live read — a note, not a plan.
3. **Operator-manual censo enrolment; retire the scrape (chosen).** Censal facts
   are operator-supplied via the profile; the calendar keeps its unverified
   posture. Cheapest, safest, rule-aligned; loses automated censo pull.

## Constraints

- Revival condition: a genuine AEAT consulta-only "datos censales" endpoint
  (rendering data without the modification tool) would justify a new ADR to
  restore an automated read. Absent that, no live censo read ships.
- The retirement is a delete-not-stub change (`no-legacy-compatibility`,
  no-dormant-surface): the dead scrape chain is removed, not left inert.
- Operator-entered censal facts MUST stay a non-official evidence tier — never
  stamped AEAT-verified — mirroring
  `local-filed-observations-are-non-official-evidence`.

## Implementation

Retire the live censo scrape chain in one atomic explicit-path change: the
`censo_g313_launcher` constant (`core/external_constants.toml`), the launcher
drive in `adapters/outbound/aeat/sede/_censo_live.py`, and the
`parse_g313_html` / `_G313_LABELS` parser in `_censo.py`, plus the
`config profile censo pull` verb. Because a live snapshot is the second operand
of `censo compare`/`apply`, default to retiring the whole `censo pull/compare/apply`
family onto `config profile edit` (one path, no parallel write route, per
`composition-service-no-parallel-write-path`); re-seat compare/apply over an
operator-entered fact set only if a real workflow needs the diff (decided in the
retirement plan). Sweep the verb-removal blast radius the
`aeat-cli-pull-and-file-standard` rule enumerates: locale keys (via the locales
CLI), how-to docs, the documented-command conformance gate, the storage
write-policy allowlist, and that rule's own source (it cites `censo pull` as a
worked example) via `vaultspec-core sync`. Censo enrolment facts flow only from
`config profile edit` onto the encrypted profile, driving obligation derivation
at the operator-declared (non-official) tier; the calendar continues to emit the
unverified advisory (optionally refined to a distinct
`censo.enrolment_operator_declared` info `Notice`).

## Rationale

The safety rule was written for exactly this moment: when the only way to read is
to operate the write tool, the correct engineering answer is to stop reading.
Option 4 degrades nothing that is load-bearing — safety, honesty, and the
hexagonal boundary are all preserved; only automated convenience is lost — and it
is ~90% already built (the calendar's unverified posture and `config profile
edit`). Options 1 and 2 spend engineering to buy, respectively, a prohibited
mutation risk and an endpoint we have positive evidence does not exist. Grounded
in `2026-07-10-censo-g313-launcher-fix-P01-S01`,
`2026-07-10-censo-g313-launcher-fix-P02-S04`, and the fork in
`2026-07-10-censo-g313-launcher-fix-adr`.

## Consequences

- Gains: no fragile safety-critical SPA driver; the census read stops brushing a
  mutation surface; one enrolment path (`config profile edit`), no parallel write
  route.
- Honestly: automated censo pull is lost permanently until AEAT ships a
  consulta-only endpoint. Census drift (the taxpayer's real AEAT census diverging
  from the profile) becomes undetectable by the app; the standing
  `censo.enrolment_unverified` advisory is the mitigation and the disclosure.
- Operator-entered censal facts can be wrong and propagate into obligation
  derivation; mitigated by the non-official evidence tier and the calendar's
  refusal to project strictly on unverified censo.
- Guard/test requirements the retirement plan must carry: a regression pinning
  the calendar unverified-posture (warning present + strict refusal) so the
  honest default cannot rot; a regression pinning that operator-entered censal
  facts are never stamped AEAT-verified; docs/CLI conformance gates green after
  the verb removal.
- Opens: a low-cost revival path (watch for a real AEAT consulta endpoint; new
  ADR restores the automated read if one appears).

## Update 2026-07-11 — ratio re-seat, snapshot substrate deletion, provenance reconcile

This update completes the accepted decision: with the scrape and the
`censo pull/compare/apply` family already retired, the surviving read still
sourced its value from the now-producerless snapshot store, so it was dead. Three
follow-ups were implemented by an authorized Opus pass on operator delegation.

Re-seat. `CensoSyncService.bound_raw_afectacion_ratio` now derives
`office_m2 / total_m2` from the operator-declared `vivienda_office` m² facts on the
encrypted profile record — the same canonical path-values the deadline engine
hydrates and `config profile edit` writes — instead of
`CensoSnapshotService.latest_active(...).censo_facts`. The call-site signature is
unchanged, so the ledger ratios CLI, the classify path, and the preflight guard are
untouched. The existing home-office guard (`load_usage_ratios_with_censo_guard`,
`derive_home_office_ratios_from_censo`, `censo_override_warning`,
`censo_business_pct_for`, `CensoRatioMismatchError`) is kept intact and becomes live
again: the "update via `config profile edit`" refusal is now a true instruction. The
"censo" stem stays correct — the m² facts are censal Modelo 036 facts, now
operator-declared and non-official; nothing stamps the CENSO source tags, so the
overview calendar keeps its empty verified-key set and the `censo.enrolment_unverified`
posture, unchanged.

Substrate deletion. The producerless snapshot substrate was deleted outright
(`no-legacy-compatibility`, no shims): the `application/live/_censo.py` module
(`CensoSnapshot`, `CensoSnapshotService`, `CensoSnapshotRepository`,
`CensoSnapshotNotFoundError`, `censo_snapshot_object_key`, `derive_censo_snapshot_id`),
its `live_censo_snapshot` secure-object namespace registration, the custody-carry
resolver for `cadrumo.application.live.censo_snapshot`, the `application/live` and storage
`__all__` re-exports, the `REFUSED_LIVE_CENSO_SNAPSHOT_NOT_FOUND` error-registry entry
and its four locale leaves, the generated api stub, and the substrate tests. After the
re-seat `_censo_sync` no longer imports from `application/live`.

Provenance reconcile. `NoPriorObligationProvenanceKind.CENSO_CORROBORATED` and the
`NoPriorObligationProvenance.censo_snapshot_id` field were removed per
`retired-enum-members-need-consumer-reconciliation`: their precondition ("until the
live censo read is functional") is now permanently false, no production site ever
constructed the member or set the field (every site is `OPERATOR_DECLARED`), and the
evidence model is computed fresh at calculate time (not a persisted shape), so deletion
strands no data. The validator now accepts `OPERATOR_DECLARED` as the sole provenance
kind.

Guard tests (real-behavior). Profile m² facts written through the real profile path
drive the ratio; a matching HOME_OFFICE override passes the guard and a diverging one
refuses naming both values; a single-profile regression proves an override with the
facts absent refuses naming `config profile edit` and that declaring the facts clears
the refusal (the dead-instruction fix); the classify path stamps the derived business_pct
when the operator omits one and the facts are present. Full-tree collection is clean.
The only red in the touched-suite run is a pre-existing peer `test_exception_base_hygiene`
failure for the unrelated m210 `Modelo210AgrupacionRentaRowsError` class — not owned by
this change.
