---
tags:
  - '#plan'
  - '#censo-g313-launcher-fix'
date: '2026-07-10'
modified: '2026-07-10'
tier: L2
related:
  - '[[2026-07-10-censo-g313-launcher-fix-adr]]'
  - '[[2026-07-10-censo-g313-launcher-fix-research]]'
---

# `censo-g313-launcher-fix` plan

### Phase `P01` - capture the authenticated censal page

Produce the ground-truth artefact every later step depends on: the authenticated MdcAcceso and es13 Mis Datos Censales HTML, identity redacted.

- [x] `P01.S01` - Capture the authenticated MdcAcceso and es13 Mis Datos Censales HTML/trace with identity redacted, and record whether the MdcAcceso to es13 transition is a passive redirect or an active dispatch; `src/aeat/adapters/outbound/aeat/sede/tests/`.

### Phase `P02` - fix the driver and parser grounding

Re-point the launcher to the representation-gated Modelo 036 ZUL, drive the en-nombre-propio confirm, and re-ground the parser from text scraping to ZK-component extraction.

- [ ] `P02.S02` - Re-point the censo launcher constants to the OVCT-CXEW representation-gated Modelo 036 flow, replacing the 404 MdcAcceso path; `src/aeat/core/external_constants.toml`.
- [ ] `P02.S03` - Drive the en-nombre-propio representation confirm and wait for the ZK censal panel before capture, preserving the fail-closed landing-URL read guard; `src/aeat/adapters/outbound/aeat/sede/_censo_live.py`.
- [ ] `P02.S04` - Capture the authenticated ZK censal panel component structure with identity redacted to ground the parser field anchors; `src/aeat/adapters/outbound/aeat/sede/tests/`.
- [ ] `P02.S05` - Re-ground the censo parser from label:value text scraping to ZK-component extraction against the captured prefilled-036 field structure, keeping the typed CensoFactSet contract; `src/aeat/adapters/outbound/aeat/sede/_censo.py`.

### Phase `P03` - verify

Prove the fix with a recorded-navigation regression and one operator-run live pull returning a populated CensoFactSet.

- [ ] `P03.S06` - Add a recorded-navigation regression through the browser_session_factory seam proving the representation-gated ZK flow yields a populated CensoFactSet, plus the 404/empty-page refusal; `src/aeat/adapters/outbound/aeat/sede/tests/test_censo.py`.
- [ ] `P03.S07` - Run one operator-mediated live config profile censo pull and record a populated CensoFactSet or the exact residual blocker; `.vault/exec/2026-07-10-censo-g313-launcher-fix`.

## Description

**CLOSED BY SUPERSESSION 2026-07-11.** After P01 (done) and P02.S04 (open,
authenticated ZK capture), an authorized Fable architecture pass ruled that
reading census data requires operating AEAT's "Censos WEB" *modification* tool,
which `aeat-safety-legal-gates` prohibits. The direction changed to Option 4 —
retire the live censo scrape; censal facts are operator-manual — recorded in
`2026-07-11-censo-operator-manual-enrolment-adr`, which supersedes this plan's
ADR. P02.S02/S03/S05 and P03.S06/S07 remain unchecked deliberately: they are not
abandoned but replaced by the retirement work under the successor ADR. P01.S01
and the partial P02.S04 exec records stand as the evidentiary anchors.

Fix the outbound censo read defect. P01 (executed 2026-07-10 under a live
authenticated session) proved the configured launcher `/wlpl/BUGC-JDIT/MdcAcceso`
returns HTTP 404 — the premature-capture hypothesis was falsified. The real
censal data is the prefilled Modelo 036 behind the
`OVCT-CXEW/DialogoRepresentacion` representation gate (an en-nombre-propio
confirm), rendered as a ZK-framework (`.zul`) SPA rather than `label:value`
HTML. The fix re-points the launcher to that flow, drives the representation
confirm, and re-grounds the parser from text scraping to ZK-component
extraction, keeping the typed `CensoFactSet` boundary. Scope stays inside the
outbound sede adapter, its parser, and the launcher constants.

## Steps

## Parallelization

The phases are hard-sequenced: P01 (done) established the real endpoint and
surface shape that all of P02 depends on. Within P02, S02 (re-point constants)
and S03 (drive the representation confirm + wait for the ZK panel) come first;
S04 (capture the ZK component structure, operator-gated) grounds S05 (re-ground
the parser to ZK extraction). P03.S06 (regression) follows the P02 code changes;
P03.S07 (operator live pull) is the final gate and is operator-scheduled.

## Verification

- P01 recorded the real endpoint (the 404 of MdcAcceso and the
  representation-gated 036 ZUL surface) — done.
- The authenticated ZK censal panel component structure is captured (identity
  redacted) and the parser anchors are grounded against it.
- The recorded-navigation regression proves the representation-gated ZK flow
  yields a populated `CensoFactSet`, and still refuses on a 404/empty landing.
- Focused lint/tests on the touched sede driver, parser, and constants pass.
- One operator-mediated live `config profile censo pull` returns a populated
  `CensoFactSet`; recorded as the closing exec record. An unresolved live
  blocker keeps `P03.S07` open per the external-blocker discipline.
