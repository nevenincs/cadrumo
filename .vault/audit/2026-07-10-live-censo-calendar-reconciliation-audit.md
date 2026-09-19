---
tags:
  - '#audit'
  - '#live-censo-calendar-reconciliation'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:8578ea8f7dc240825d2c69c573479e1f573d906ebceb36e1e062e53e10cf4799'
related:
  - "[[2026-06-05-live-censo-calendar-reconciliation-plan]]"
  - "[[2026-07-10-live-censo-calendar-reconciliation-reference]]"
---

# `live-censo-calendar-reconciliation` audit: `live sweep closeout honesty review`

## Scope

Fresh-context honesty review triggered by the campaign-close discipline before
declaring `live-censo-calendar-reconciliation` structurally complete. On
2026-07-10 the plan's two remaining open rows (`W04.P04.S10`, `W04.P04.S11`)
were exercised for the first time under a real authenticated Cl@ve Movil live
session against the operator's persistent `me` profile. This audit records what
that session actually proved, what remained blocked, and the honest checkbox
state. Inherited context: the plan was at 30/32 with fifteen-plus prior
attempts (`2026-06-12` blocker audit) that never obtained a completed auth.

## Findings

### live-auth-acquired | info | First authenticated live session obtained for this plan

`config auth login --provider clave_movil --fresh --reset-lock` reached the
non-QR Cl@ve flow (page verification code `H84`), the operator approved on the
phone, and it returned `authenticated=true`, `fresh=true`, `acquired_lock=true`.
Every subsequent read ran under `auth_persisted_session_state=live` with
`auth_identity_alignment=matches`. This eliminates the operator-mediated-auth
blocker that dominated the `2026-06-12` audit.

### live-read-transport-proven | info | All read facades reach AEAT and persist real snapshots

Under the single live session, notifications pull, filed list 2026, filed pull
303/2026, expedientes pull 303/2026, and justificante list all succeeded and
persisted real snapshots. The AEAT account is empty for 2026 so every read
returned zero rows. This proves the read transport end-to-end; the empty result
is account state, not a code defect.

### censo-g313-launcher-defect | medium | Censo pull lands on an access-gate page under a valid session

`config profile censo pull` reached G313 but navigated to
`/wlpl/BUGC-JDIT/MdcAcceso` (an access gate) and produced an empty
`CensoFactSet` (`ERROR_SEDE_NAVIGATION`, `censal_marker_present=false`,
`populated_field_count=0`). This is a sharper diagnosis than the prior "no
readable censo" framing and is a launcher/parser grounding defect in the
outbound AEAT G313 path — NOT auth and NOT the reconciliation plan's
application/CLI scope. It blocks positive censo `compare`/`apply` and therefore
positive censo-backed calendar enrolment. Carried in
`2026-07-10-live-censo-calendar-reconciliation-reference` (Blocker 1).

### calendar-refuses-unverified | info | S11 calendar reconciles honestly against empty live evidence

Strict `app overview calendar` REFUSES (`REFUSED_CLI_BOUNDARY`) on
`censo.enrolment_unverified` + `irpf.estimation_regime`. `--allow-incomplete`
projects 10 local obligation rows (modelos 100/130/303/390) with the
`censo.enrolment_unverified` warning and its fix command, and NO fabricated
submitted / justificante-verified rows and 0 message events — consistent with
the empty account. The W05 calendar hardening behaves exactly as designed.

### s11-positive-proof-unobtainable | medium | S11 positive claim cannot be met on current account/G313 state

`W04.P04.S11` literally requires proving the calendar "reconciled with live
submitted and justificante-verified evidence". No submitted or
justificante-verified evidence exists (empty account) and censo enrolment is
blocked by the G313 launcher defect, so the positive claim is environmentally
unobtainable. The calendar's correct refusal is proven, but that is the
negative/enforcement direction, not the positive proof the step names.

### s11-operator-accepted | info | Operator accepted the enforcement-direction proof and confirmed the empty account is genuine

The operator — the sole party able to run the live account — accepted the
calendar's correct-refusal behaviour as sufficient evidence for `W04.P04.S11`
and confirmed the empty 2026 account is genuine: they have never filed the
modelo, so the zero-row live reads are the expected real state, not a defect or
a transport gap. On that acceptance `W04.P04.S11` is closed. Blocker 2
(empty-account) is therefore an accepted environmental condition; only Blocker 1
(the G313 launcher grounding defect) remains as an outbound-adapter follow-up.

## Recommendations

- `W04.P04.S10` is checked: its action — rerun every listed live pull under an
  authenticated session and record the exact result or blocker — was executed in
  full and captured in the S10 exec record, including the censo G313 blocker.
- `W04.P04.S11` is CLOSED on operator acceptance (see finding
  `s11-operator-accepted`). The operator accepted the calendar's correct-refusal
  behaviour as the evidence and confirmed the empty account is genuine (never
  filed the modelo). The positive submitted/justificante-verified projection
  remains producible in future once the G313 launcher is re-grounded and a filed
  declaration exists, but is no longer a gate on this plan.
- Open a separate outbound-adapter defect for the G313 `Mis Datos Censales`
  launcher landing on `/wlpl/BUGC-JDIT/MdcAcceso`; capture the authenticated
  landing HTML and re-point the launcher or re-ground the parser labels.
- No codification candidate: the plan already codifies that an external live
  blocker keeps the relevant step open; this pass narrows the censo blocker from
  "no readable censo" to "launcher access-gate landing" but does not add a new
  cross-session rule.
