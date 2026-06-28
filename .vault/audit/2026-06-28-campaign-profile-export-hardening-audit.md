---
tags:
  - '#audit'
  - '#campaign-profile-export-hardening'
date: '2026-06-28'
modified: '2026-06-28'
related:
  - "[[2026-06-27-campaign-profile-export-hardening-audit]]"
---

# `campaign-profile-export-hardening` audit: `persona campaign wave two hardening`

## Scope

Second-wave persona campaign for blank-state CLI operation across autonomous,
small-company, employed-plus-autonomous, and non-resident profiles. Personas were
delegated to CLI-only subagents with isolated local storage roots, no source-code
access, no real taxpayer data, and no live AEAT contact. The coordinator used
RAG and code-facing subagents to triage testimonial failures into implementation
or backlog items.

Personas exercised profile creation, ledger input, category/classification
friction, quarterly Modelo 303 / 130 / 202 / 200 flows where applicable,
Modelo 390 annual summary calculation, local file/export surfaces, manual
arithmetic cross-checks, and visible exported-file sanity checks. External BOE
verification was limited to local artifact structure and officially named model
identity, year, period, fake tax id, and known unsupported layout boundaries;
no persona was allowed to assume CLI export correctness as legal truth.

Wave-three continuation on the same date reran CLI-only personas from blank
state after the first hardening pass. The coordinator initially briefed personas
to set `AEAT_DATABASE_URL`; code triage and direct smoke testing confirmed that
is not a valid isolation knob for profile-bound storage. The corrected campaign
contract is `AEAT_LOCAL_STORAGE_ROOT` plus a non-interactive
`AEAT_SECRET_PASSPHRASE`, leaving the database route to the active profile
bucket. This coordinator brief defect was retained as campaign evidence because
it materially blocked every persona before modelo work.

## Findings

### persona-arithmetic-cross-check | low | Quarterly and annual IVA calculations matched manual persona arithmetic

Lucia, Diego, and Marta each entered simple sales and purchase ledgers, calculated
quarterly Modelo 303 revisions, and manually recomputed bases, output IVA,
input IVA, and result. The calculated Modelo 303 figures matched manual sums.
Their Modelo 390 annual calculations also reconciled to the sum of the quarterly
Modelo 303 outputs. Produced Modelo 303, Modelo 130, Modelo 202, and Modelo 200
local export artifacts carried visible model/year/period and fake taxpayer
identity markers. This is evidence of arithmetic wiring and export-surface
continuity for the exercised paths, not a legal claim that the BOE layouts are
complete or correct.

### iva-wallet-explicit-zero | high | Explicit zero prior-compensation bypassed local wallet reconciliation

Multiple personas hit `wallet_missing` in later Modelo 303 periods despite a
local zero compensation posture. Read-only triage found that
`src/aeat/application/modelo/_iva_wallet_gate.py` short-circuited local
reconciliation when the caller supplied `modelo-303-compensacion-pendiente-anteriores=0`,
then later raised `iva_wallet_not_seeded`. The hardening now reconciles supplied
prior-compensation inputs against local wallet/history authority, accepts explicit
zero only when concrete local zero authority exists, rejects mismatches with
`iva_wallet_caller_binding_conflict`, and preserves first-period-zero proof
through lifecycle activity-start and registry dependency grounding. Review found
no remaining issues.

### m202-incomplete-modality | high | Modelo 202 incomplete modality could verify, file, and export

Marta's S.L. persona calculated Modelo 202 with `modality incomplete`, then still
verified, locally filed, and exported the revision. Triage confirmed that
incomplete modality is the correct diagnostic when `taxpayer_type.incn_prior_12_months`
is absent, but a filing-grade revision must not be granted without the Art. 40.2
vs Art. 40.3 modality. `src/aeat/application/modelo/_verification_actions.py`
now emits a blocking finding for incomplete Modelo 202 modality and names the
missing profile fact. New real-behavior lifecycle coverage proves incomplete
M202 remains draft and cannot file or become export-selectable, while declared
INCN values below and above threshold still verify complete. Review found no
remaining issues.

### readiness-fail-open | high | Readiness over-reported readiness on invalid registry targets and missing bindings

Claire, Diego, and Marta all found readiness overstatements: M210 `AD-HOC`
and M130 wrong revision targets reported ready or were accepted; M200 readiness
reported ready before calculation failed on missing bindings; M303 readiness did
not predict the wallet gate. Stage-1 hardening in `src/aeat/application/state_projection.py`
and `src/aeat/entrypoints/cli/_modelo_readiness_cli.py` now resolves readiness
against the requested revision and period, fails closed with `registry_ready=false`
and an actionable `registry_refusal` when no registry snapshot exists, and reports
formula-consumed profile/manual binding gaps with `binding_ready=false` and
`missing_bindings`. Wallet/applicability aggregation remains a later stage by
design. Review found no issues in the stage-1 implementation.

### unsupported-m390-export | medium | Modelo 390 has calculation and verification coverage but no BOE export layout

Lucia, Diego, and Marta calculated and locally filed Modelo 390 annual summaries
but export failed because the registry snapshot declares no export layout.
Read-only export triage confirmed this is not a disconnected layout: the current
M390 registry has calculation and workbook parity metadata but no complete
fichero-BOE `export_layouts`, no export application link, and incomplete
semantic-to-DR mapping. This is a feature implementation gap, not a safe
connection task for this campaign. Short-term hardening remains to improve the
operator-facing error text so it names the unsupported M390 fichero-BOE boundary
instead of only the generic missing-layout message.

### wave-three-blank-state-isolation | high | Persona scratch roots still reached workspace master-key material

Lucia, Diego, Marta, and Claire independently failed at profile creation from
blank persona scratch roots. They saw missing passphrase refusals first, then
`passphrase does not unwrap the master key` after setting a fake local
passphrase. Their repair logs showed master-key locking under workspace
`var/secrets`, not their scratch roots. Code triage classified the missing
passphrase as intended but under-guided, and the workspace `var/secrets`
fallback as a storage-root isolation defect. `src/aeat/core/config.py` now
derives unset secret, blob, and audit directories under
`AEAT_LOCAL_STORAGE_ROOT`, preserving explicit `AEAT_SECRET_STORE_DIR`
overrides. A corrected direct CLI smoke, with no `AEAT_DATABASE_URL`, created a
fresh profile successfully and wrote secrets/buckets under the scratch local
root.

### m303-pre-activity-target-period | high | Modelo 303 target periods before alta could create zero drafts

Prior Diego feedback reported that a part-year autonomous profile could create
or calculate a Modelo 303 quarter before the declared activity-start date. A
read-only triage pass confirmed this as a defect: the deadline engine suppresses
obligations whose period closes before `censo.activity_start_date`, while modelo
work creation and calculation only used activity-start to scope prior-period
dependencies. `src/aeat/application/modelo/_profile_readiness_gate.py` now
refuses complete profiles when the target Modelo 303 period end is before the
activity-start date. The guard runs before work-unit persistence, before stale
calculation/wallet work, and on the visible-target reuse path in
`src/aeat/application/modelo/_work_addressing.py`. A corrected CLI smoke proved
Modelo 303 2026 1T is refused for activity start 2026-05-01, while 2T creates a
work unit.

### m390-export-refusal-wording | medium | Missing BOE layout refusal now names the unsupported boundary

The M390 export gap remains a feature boundary, not a layout connection task.
The operator-facing lower-level refusal now says fichero-BOE export is
unsupported because the registry snapshot has no complete `export_layouts`
definition, that calculation/verification/local filing surfaces may still
exist, that the command cannot produce a BOE export file, and that the message
does not certify legal correctness. A real-registry M390 test asserts the live
M390 snapshot has no export layouts and refuses without writing a file.

### m210-registry-readiness-boundary | medium | M210 is listed for registry discovery but not work-create supported

Claire's non-resident persona found Modelo 210 in list/describe/readiness
surfaces but work creation refused as unsupported. Read-only triage classified
the work-create refusal as the current intended boundary while the M210 engine
flag is off. The defect portion is readiness/period fail-open: period tokens
and unresolved snapshots must not report ready. Stage-1 readiness hardening
now makes unresolved M210 registry targets not ready. The larger product
decision remains the canonical ad-hoc token and how list/describe/readiness
should label models that are registry-visible but not work-unit-supported.

Wave-three Claire found the period-token contradiction more directly:
`modelo describe 210` advertised `evento`, readiness rejected `evento` while
suggesting `AD-HOC` / `EVENT-N`, and `describe --period EVENT-1` then failed
registry selection. Read-only triage confirmed this is a defect against the
accepted CLI period union: core grammar accepts `AD-HOC` and `EVENT-N`, while
the M210 registry revision still declares `periods = ["evento"]`. The owner
files for this fix are already carrying unrelated M210 legal-grounding and
readiness WIP in the shared worktree, so this campaign records the defect and
does not start an overlapping schema edit here.

### cli-ux-policy-residuals | low | Personas surfaced trust issues that are not code defects in this pass

Personas repeatedly noted local-only surprise at `llm_vision` and `google_export`
defaulting on, `business_pct=1` being rejected unless classification is `MIXED`,
Spanish flag spelling surprises, noisy out-of-period and duplicate advisory
messages, and work-list rows showing `state=borrador` with filed revision ids.
RAG/code triage showed several of these are current documented policy or UX
surfaces rather than correctness defects. They remain backlog items for operator
trust and explainability, not part of the no-new-feature hardening work completed
in this wave.

### corrected-persona-rerun | high | Corrected isolation reached filing work and exposed remaining readiness/wallet gaps

After the isolation fix and corrected brief, Diego created a blank-state
part-year autónomo profile, entered Q2 ledger rows, and completed Modelo 303 and
Modelo 130 create/calculate/verify/local-file/export. Manual arithmetic matched
the CLI: M303 Q2 output IVA 735.00 minus input IVA 84.00 equalled 651.00, and
M130 Q2 net income 3,100.00 produced 620.00 before the CLI's 100.00 minoration.
Modelo 303 1T work creation refused as pre-activity for activity start
2026-05-01, confirming the target-period guard from a persona path.

Lucia's corrected rerun completed all four Modelo 303 quarters, verified and
locally filed them, exported four local 303 artifacts, and calculated/verified/
locally filed Modelo 390. Manual quarterly IVA and annual M390 totals reconciled:
annual output IVA 1,113.00 minus input IVA 462.00 equalled 651.00, matching the
CLI annual result. She confirmed all exported 303 files contained visible model,
year, period, and fake identity markers, while explicitly not treating those
bytes as legal proof.

The rerun also surfaced unresolved defects. Diego saw Modelo 303 1T readiness
report `ready True` even though create correctly refused the same target as
pre-activity. Lucia still needed explicit IVA wallet overrides for Q2, Q3, and
Q4, and after Q3 generated an 84.00 compensation carry the wallet balance
reported zero while Q4 required an 84.00 override. Both items were briefed to
read-only triage agents rather than being assumed closed.

Readiness triage classified Diego's M303 1T readiness mismatch as
`intended-deferred`: current readiness stage 1 covers registry resolution,
profile preflight, missing bindings, and ledger preflight, while applicability
and wallet aggregation are explicitly stage-2 backlog. If stage 2 is promoted,
readiness should report M303 2026 1T as `ready False` with a pre-activity reason
and leave 2T eligible.

Wallet triage classified Lucia's override requirement as intended but the
balance projection as a scoped defect. Local filed history must not silently
unblock casilla 110 without AEAT wallet evidence, so `wallet_missing` plus an
explicit taxpayer override remains the correct filing-grade posture. However,
local filed M303 periods that generate compensation are not currently projected
into `IvaCompensationHistoryRepository`, so `iva-wallet balance` can show zero
after a local Q3 filing generated an 84.00 carry. The follow-up owner area is
local filing observation persistence into IVA compensation history, not export
or automatic wallet authority relaxation.

Follow-up implementation closed the scoped balance projection defect without
relaxing the filing-grade wallet gate. RAG/code triage located the existing
live-filed observation projection and the local filing observation path, then a
coder subagent connected local M303 filing observations to
`IvaCompensationHistoryRepository` when the active profile tax id is available.
The projected history uses the filed registry observation after refund carry
zeroing, so compensation elections that refund instead of carry forward do not
create false available lots. A review subagent found no issues: `iva-wallet
balance` now sees locally generated carry, while a later M303 still fails closed
as `filed_history_only` without AEAT wallet evidence or explicit taxpayer
override.

### wave-four-persona-rerun | high | Fresh CLI-only personas verified wallet projection and surfaced a cross-model registry blocker

After the local compensation-history projection landed, fresh CLI-only personas
reran from blank storage roots. Lucia's autónoma persona locally filed a Q1
Modelo 303 with a negative result and then ran `app modelo iva-wallet balance`;
the CLI reported `total_balance 420.00`, `lot_count 1`, and
`next_expiry_year 2030`, confirming the new local-filed history projection from
the operator surface. Marta's S.L. persona confirmed the M202 incomplete-modality
guard from the CLI: an S.L. profile without `taxpayer_type.incn_prior_12_months`
did not become filing/export grade, while a completed profile reached M202
calculate/verify/local-file/export.

Both personas then hit the same unrelated registry validation blocker:
`boe-modelo-721-2023-layout` pointed at the missing corpus file
`corpus/normatives/pdf/boe-a-2023-17429-modelo-721-layout.pdf`, aborting unrelated
M303 and M200 work. RAG/vault lookup confirmed this was a known high-risk Modelo
721 legal-grounding gap: Modelo 721 belongs to Orden HFP/886/2023 /
BOE-A-2023-17429, and a reviewed source that cannot resolve is a hard trust
failure. A coder subagent fixed and verified the source path by bundling the
official BOE PDF with the registry-declared byte count and SHA-256. After that,
`app registry inspect` loaded all 30 modelos and both personas resumed from the
blocked checkpoint.

Lucia then completed all four M303 quarters with exports. Manual checks matched
her quarterly IVA figures: Q2 applied the Q1 420.00 carry after an explicit
taxpayer override, Q3 calculated 798.00, Q4 calculated 210.00, and final wallet
balance returned zero. The override requirement is intentional safety behavior:
RAG/code triage reconfirmed that `filed_history_only` fallback evidence must
remain blocking without direct AEAT wallet/cartera evidence or explicit taxpayer
confirmation. She also calculated, verified, and locally filed M390; annual M390
totals matched manual arithmetic (output IVA 2730.00 minus input IVA 1512.00 =
1218.00), while export correctly refused because M390 has no complete
fichero-BOE layout.

Marta resumed M200 after the registry repair. M200 calculated, verified, and
exported successfully from a complete S.L. profile; local filing refused because
there was no pending filing obligation/window, which is a workflow/calendar
boundary rather than a registry failure. Her manual review flagged that M200
casilla `DP200014:00558` displayed `23` while a 16000 base produced a 3040.00
quota. RAG classified this as the already-documented M200 scalar-rate echo gap:
for a 2026 micro-empresa the cuota is bracket-correct at 19% on the first 50000
EUR, but the display scalar still echoes stale 23%. This is a trust/export
surface defect, not an under-declaration in Marta's exercised scenario.

### wave-five-persona-rerun | high | CLI-only personas confirmed quarterly paths and isolated annual/model-boundary gaps

Sara, Diego, and Claire reran from isolated blank storage roots with CLI-only
instructions and fake data. Sara's employed-plus-autonomous profile completed
Modelo 303 and Modelo 130 for 2026 1T and 2T: create, calculate, verify,
local-file, and export all succeeded. Her manual checks matched the CLI for M303
Q1/Q2 output IVA, input IVA, and result, and for M130 Q1/Q2 cumulative income,
expenses, prior payments, and final payment. She treated exported M303/M130 files
as visual artifact sanity only and did not treat them as legal proof.

Diego's part-year autonomous run completed supported Q3/Q4 Modelo 303 and Modelo
130 work and reconciled M303 quarterly totals to the annual Modelo 390
calculation. M390 calculate/verify/local-file remained supported while export
correctly refused the known missing `export_layouts` boundary. His run exposed a
new high-risk consistency defect: with `censo.activity_start_date=2026-07-15`,
Modelo 303 2026 1T refused as pre-activity but Modelo 130 2026 2T still created,
calculated, and verified despite the period ending on 2026-06-30.

Claire's GB non-resident IRNR run confirmed the current M210 boundary. The CLI
could create a non-resident profile and import Spanish-source rental ledger rows,
but M210 remained registry-visible and work-create-unsupported. Her run also
showed `overview status` telling a non-resident profile with ledger data to run
`modelo work create`, which is misleading while M210 local work units are not
supported. The separate `evento` / `EVENT-N` token contradiction remains backlog.

Sara also confirmed that the 2026 annual Modelo 100 path is not currently
covered: `describe 100` lists revisions through 2025, and `work create --modelo
100 --year 2026 --period 0A` refuses because no registry revision covers the
target. A 2025 M100 probe could calculate and verify after explicit bindings and
zero relations, but export refused the unsupported `xml_dictionary` layout. This
is recorded as annual coverage/export backlog, not as a hidden quarterly
calculation failure.

### m210-overview-unsupported-guidance | medium | Overview no longer steers non-resident profiles into unsupported M210 work-create

Claire's M210 testimonial produced a bounded UX defect: when a non-resident IRNR
profile had ledger rows, `overview status` suggested `aeat app modelo work
create`, even though Modelo 210 work-unit creation is intentionally unsupported
until the M210 engine plan lands. The hardening derives registry-visible but
locally unsupported work-create modelos from raw profile values, carries that on
`OverviewStatusReport`, and renders `modelo describe 210` plus AEAT Sede G320
guidance instead of `modelo work create` for the M210 IRNR case.

A code-review subagent found two hygiene issues in the first patch: bare Modelo
code literals and a missing locale key. Follow-up work sourced the public string
value from `Modelo.M210.value`, kept translation keys visible to the locale
scanner, and updated the locale catalogues through `python -m aeat.locales`. The
review found no functional issue with the unsupported-M210 boundary; the period
token contradiction remains separately tracked.

### m130-pre-activity-target-period | high | Modelo 130 now fails hard before pre-activity work, calculation, or verification

Diego's wave-five run proved the Modelo 303 pre-activity guard had not been
generalized to Modelo 130. RAG grounding tied the behavior to the same
activity-start policy used by the deadline engine and first-filer decisions: a
period whose end date is before `censo.activity_start_date` must not become a
filing-grade target. The readiness gate now includes Modelo 130, using the core
`Modelo` enum, and raises before creating a work unit, calculating from a stale
work unit, or marking an existing revision verified.

Application tests cover M130 create refusal with no persisted work unit and stale
calculate/verify refusal without revision mutation. CLI coverage proves `aeat app
modelo work create --modelo 130 --year 2026 --period 2T` refuses for a profile
whose activity starts on 2026-07-15. A review subagent found no correctness
issues in the M130 refusal; its only note was that the same CLI test module also
contains the separate M210 overview coverage from Claire's fix.

### wave-six-persona-rerun | high | Fresh blank-state personas exposed profile completeness, provenance, and row-model defects

Wave-six reran four CLI-only personas from blank isolated storage roots: Hugo
Martin, Ingrid Bauer, Valeria Soto S.L., and Northbridge Digital Ltd. They were
not allowed to read source code and used fake data only. Each persona performed
profile setup, transaction entry/import, classification, modelo work creation,
calculation, verification, local filing/export where supported, visible export
sanity checks, and manual arithmetic cross-reference against the individual
modelo outputs.

The run confirmed earlier hardening and produced new bounded defects:
non-resident IRNR profiles could validate ready without a fiscal residence
country or, for GB/non-EU-EEA residence, without representative facts; explicit
`source_jurisdiction` accepted through `ledger add` and CSV import was lost in
canonical CSV/JSONL export; all-failed bulk classification exited successfully;
M130 could be created and filed for an IRNR profile; `overview status --period
1P` rejected the M202 instalment period token that modelo work accepts; and
M349 `--row operador` created an unverifiable draft whose summary casillas
remained zero.

The run also classified non-bounded findings. A foreign legal entity declaring
non-resident IRNR but "no Spanish permanent establishment" cannot be safely
made not-applicable for M200/M202 without a grounded profile axis: the current
M200/M202 manifests include IS taxpayers plus IRNR permanent establishments and
foreign entities with Spanish presence, but the profile schema does not encode
"no Spanish PE". M210 `evento`/`EVENT-N`, Modelo 100 2026 and `xml_dictionary`
export, M202/M200 export-name length, M200 final-differential display, M100
withholding/expense discoverability, help truncation, and filed work-unit state
wording remain backlog.

### irnr-profile-hard-gate | high | Incomplete IRNR profiles now fail before persistence, readiness, and modelo work

The profile hardening added a shared conditional completeness rule for
`taxpayer_type.fiscal_residency=non_resident_irnr`. IRNR profiles now require
`taxpayer_type.country_of_fiscal_residence`, and non-EU/EEA IRNR profiles
require both `taxpayer_type.representante_fiscal_nif` and
`taxpayer_type.representante_fiscal_nombre`. Profile key validation, lifecycle
validation, preflight, profile status, and quiet CLI profile creation all use
the same rule, so broken profiles fail before a user is dragged into modelo
work.

The implementation is in `src/aeat/application/user_profile/_completeness.py`,
`src/aeat/application/user_profile/_keys_validation.py`,
`src/aeat/application/user_profile/_validation.py`,
`src/aeat/application/user_profile/_preflight.py`,
`src/aeat/domain/deadlines/_models.py`, and the profile create/status bridges.
Coverage proves missing IRNR country and missing GB representative facts refuse
before profile registration, while EU/EEA IRNR without representative remains
accepted.

### ledger-source-jurisdiction-and-bulk-classify | high | Ledger provenance now survives add/import/export and all-failed classify exits nonzero

Ingrid and Northbridge proved that `source_jurisdiction` was required and
accepted for IRNR rows but disappeared from canonical exports. The fix reads the
canonical `source_jurisdiction` raw import field into the persisted transaction
and emits `transaction.source_jurisdiction` from canonical CSV and JSONL
exports. Real CLI coverage now proves both `ledger add --source-jurisdiction`
and CSV import preserve ES/DE/FR/GB provenance through export.

Valeria's all-failed classification batch also exposed a misleading success
exit. Bulk classify now emits a warning envelope and exits nonzero when every
row fails while preserving partial-success behavior when at least one row is
applied. This closes the specific "20 failed, exit 0" trust defect without
removing useful partial-apply workflows.

### m130-irnr-applicability | high | Modelo 130 now refuses declared IRNR non-residents

Read-only applicability triage found that M130's rule had entity type, income
category, and estimation-regime axes but no fiscal-residency axis. Bundled
profile and deadline evidence routes `NON_RESIDENT_IRNR` taxpayers to IRNR and
suppresses IRPF-resident deadlines, so M130 must not be available to a declared
IRNR natural person. `src/aeat/domain/calculations/registry/_applicability.py`
now gates M130 to `FiscalResidency.RESIDENT_IRPF` while preserving the existing
resident-default behavior when fiscal residency is undeclared.

Registry applicability coverage proves a declared IRNR economic-activity profile
is not applicable for M130 and carries TRLIRNR grounding. CLI coverage proves
`modelo work create --modelo 130` refuses a persisted IRNR profile before
creating resident-IRPF work.

### overview-instalment-period-filter | medium | Overview status accepts M202 instalment periods

Northbridge showed `aeat app overview status --period 1P --year 2026` rejected
`1P`, even though Modelo 202 work creation/calculation accepts `1P`, `2P`, and
`3P`. The defect was localized to overview status using the ledger period
normalizer, which intentionally refuses non-date-span instalment tokens. The
overview period branch now resolves through the core registry-period union, so
it can filter stored draft/work periods without weakening ledger filtering.

CLI coverage stores typed `1P` and `1T` drafts in the real draft repository and
proves `overview status --period 1P --year 2026` returns only the M202 draft.

### m349-detail-row-integrity | high | M349 operador rows now feed summary casillas and verify

Ingrid's M349 row-entry path reproduced a content-address mismatch: `--row
operador` persisted detail rows, but integrity rehash ignored `detail_rows`, and
the row totals did not fold into the declarant summary bindings. The fix includes
detail rows in the calculation revision content hash, derives
`decl.numero-operadores` and `decl.importe-operaciones` from operador rows,
replays row-indexed M349 binding inputs into the filing runtime, and satisfies
M349 row-template required checks from real row bindings.

Focused CLI coverage now creates a blank M349 profile, calculates two operador
rows for DE/FR with total 2,400.00, asserts the summary casillas and detail rows
are visible, and verifies without content-address mismatch. Rectification detail
rows remain out of scope because no typed rectification row model exists on this
surface.

### wave-seven-cli-only-confirmations | low | Fresh personas reconfirmed the hardening from blank isolated storage

Helena's EU IRNR persona and Nerea's M349 persona reran from blank
`AEAT_LOCAL_STORAGE_ROOT` roots with no source-code access. Helena confirmed
that invalid IRNR profiles now fail before registration, EU IRNR profile
creation/validation/status succeeds with the required conditional facts, Modelo
130 work creation refuses an IRNR taxpayer, and `source_jurisdiction` survives
manual ledger add, CSV import, CSV export, and JSONL export. Nerea confirmed the
M349 operador-row path now reaches create, calculate, verify, local file, export,
and manual marker inspection with two operators and total operations of
9,124.68.

These confirmations are testimonial evidence from the CLI surface, not a
substitute for the focused tests listed below. The personas did not read source
code, did not contact AEAT live services, and did not treat local export bytes as
legal proof.

### ledger-explicit-direction-import | high | CSV/XLSX imports now honor explicit direction over positive amount sign

Helena's IRNR persona imported a CSV row with positive `amount=300` and
explicit `direction=OUTGOING`; export later showed the row as `INCOMING`. This
was a correctness defect because the documented canonical import shape treats a
positive amount as a magnitude and the `direction` column as the authoritative
flow. RAG pointed at the existing signed-amount fallback and the manual ledger
documentation that says direction carries whether money came in or went out.

The provider parser now carries a canonical `direction` column into the
`ParsedLedgerRow` when present, rejects blank or unsupported explicit direction
values instead of falling back to amount sign, and preserves the existing
positive/negative signed-amount behavior when the column is absent. The shared
tabular parser means XLSX imports receive the same fix. Focused tests prove both
provider-level parsing and ledger import/export persistence for CSV and JSONL.

### m202-legal-entity-export-name | high | M202 legal-entity export now uses the razon-social slot

Rocio's S.L. persona verified and locally filed Modelo 202 1P, then export
failed with `modelo-202-page-01-header-name-pos-83 value exceeds length 20` for
`Rocio Ferrer Administracion Sociedad Limitada`. RAG and bundled export-layout
evidence show the 2025+ M202 official fixed-width layout has `surnames` at
offset 23 length 60 and `name` at offset 83 length 20. This should not be fixed
by widening the official layout. The likely defect is legal-entity identity
mapping: a company's razon social should populate the long surname/razon-social
field and leave the individual name field blank.

The focused patch preserves the official export TOML and maps legal-entity
export identity from `identity.legal_name` into the long `surnames` header slot,
leaving the individual `name` slot blank. The first review found two unsafe
over-broad paths: blank required headers were accepted globally, and legal
entities could pass preflight/export with only `identity.surnames` or a short
`identity.name` fragment. Follow-up narrowed the blank-header allowance to the
Modelo 202 legal-entity individual-name field ids when the composed headers
declare `entity_type=legal_entity`, restored blank-header refusal for every
other required header, and made both profile preflight and export require
`identity.legal_name` for legal entities. Focused tests prove a realistic S.L.
name exports through the M202 layout without tripping the 20-character name
slot, and prove fragment-only legal-entity profiles fail before export.

### m200-m202-payment-guidance | high | M200 M202-payment fold-in guidance is too easy to misuse

Rocio's M200 persona manually cross-checked the annual calculation. With ledger
net income of 49,200.00, M200 computed `00562=9348.00` and `00599=9348.00`.
Supplying the annual M202 relation as 1,800.00 and the unused 40.2 relation as
0.00 produced `00611=7548.00`, matching the manual subtraction. Supplying both
payment relations as 1,800.00 double-counted the credit and produced
`00611=5748.00`.

RAG confirmed the formula intentionally subtracts two relation operands because
M202 Art. 40.3 payments feed casilla 34 and Art. 40.2 payments feed casilla 03;
the modalities are mutually exclusive per filing. The defect was operator
guidance, not calculation arithmetic. The CLI now labels `relation_prefill`
bindings as `relation input`, adds M200/M202 relation guidance to `bindings
list --missing`, expands `work calculate --relation` help, and routes missing
relation refusals to `--relation RELATION_ID=VALUE` rather than `--binding`.
The guidance names both relation ids and tells operators to put `0` on the
unused modality when entering manual values. No formula or registry arithmetic
changed.

### m349-readiness-applicability-alignment | medium | M349 readiness can overstate an attribution-entity target

Nerea first used an `attribution_entity` profile with ROI/intracommunity facts.
Readiness appeared to pass for Modelo 349, but `modelo work create` refused the
same target as not applicable. A later legal-entity profile completed the full
M349 path. This mirrors the known stage-2 readiness gap: stage-1 readiness
currently covers registry resolution, profile preflight, missing bindings, and
ledger preflight more than final applicability.

An explorer is reading the exact readiness and work-create code paths to decide
whether this M349-specific mismatch is a defect, an intended stage boundary, or
a backlog item under the existing applicability-readiness aggregation work. The
read-only result classified it as the existing stage-2
readiness/applicability gap. `modelo readiness` currently computes readiness
from registry resolution, profile preflight, missing bindings, and optional
ledger preflight; it does not call `derive_modelo_applicability`. `modelo work
create` does call the applicability guard and M349 intentionally allows natural
persons and legal entities with intracommunity facts, not attribution entities.
The safe next step is a focused CLI regression for this exact mismatch before
promoting applicability aggregation into readiness.

### blank-state-overview-profile-keys | high | Overview status no longer leaks an internal profile-key registry error

Alvaro's employed-plus-autonomous persona started from a blank storage root and
`aeat app overview status` exited 6 with `profile keys are not registered`.
This blocked a first-contact user before profile setup. RAG showed the same
error in documentation command-output captures. The root cause was that the CLI
root callback registers the wizard/profile-key catalogue only when an active
profile exists, while `overview status` can build the shared state projection
with no active profile. In a fresh process, no earlier import had seeded the
profile-key registry.

`build_operator_state_projection()` now imports the wizard package before any
profile-key metadata can be read, so all projection consumers share the same
cold-start behavior. A fresh-process test invokes `app overview status` against
a pristine storage root and asserts it renders a normal no-profile status report
without leaking profile-key registration internals. A direct blank-root smoke
also rendered the no-profile overview successfully.

### employed-plus-autonomous-evidence-boundaries | medium | Prior-year filing evidence gates blocked annual carry paths correctly but unclearly

Alvaro completed profile setup, ledger import/classification, and a 2024 M130
4T calculate/verify/export bootstrap. The persona then tried to use the local
export and fake justificante/filing-record artifacts to unblock 2025 M130 and
M100. The CLI rejected the fake filing-record import and fake justificante
reconciliation, and 2025 M100 calculation refused because `100/2024/0A` was not
an observed filing. This is the correct legal/evidence boundary: export bytes
and forged PDFs are not official prior filing evidence.

The trust issue is wording. The filing/export guidance made export sound like a
local finish line, while dependency checks correctly require an observed filing
record for prior-year carry. This remains a UX backlog item: distinguish local
export, local filing records, imported official filing evidence, and rejected
fake evidence in the next-step copy.

### residual-wave-seven-cli-friction | medium | Completed personas found additional trust issues for later hardening

The wave-seven reports also found several smaller but real operator-friction
items. M210 still has a period-token contradiction around `evento`, `AD-HOC`,
and `EVENT-N`; this remains the existing M210 token-migration backlog. M349
calculation help/examples did not lead Nerea clearly to `razon_social`, even
though the row model and replay path use it correctly. Invalid M349 row
validation exposed a Pydantic help URL, which is too technical for a CLI-only
taxpayer persona. Bulk ledger classification requires full transaction ids even
though single classification accepts short ids. Rocio also read `Borradores 0`
as suspicious after work units existed; RAG confirmed drafts and work units are
separate stores, so this is wording/trust debt rather than lost data. Alvaro
also found `casillas --form-number 0003` confusing: the flag filters the
physical form/subform number, not the casilla number displayed in the full list,
so M100 `0003` discoverability needs clearer command naming or a separate
casilla-number filter.

### wave-eight-reframed-persona-campaign | high | CLI-only personas exposed profile and ledger trust blockers

This continuation reframed the campaign execution: the coordinator remained a
coding/fixing agent, while CLI-only persona subagents performed taxpayer
journeys from blank isolated storage roots. Personas were explicitly barred from
reading code and used only `uv run --no-sync aeat ...`, command help, scratch
CSV/export files, and public AEAT pages for high-level external sanity. The
wave covered a resident S.L., a UK non-resident company, and an employed-plus-
autonomous natural person, with read-only code triage agents briefed separately
for suspected defects.

Marta's S.L. and Sofia's UK company both reproduced a high-confidence profile
creation blocker: `config profile preflight` could report ready for M200/M202,
while `modelo work create` refused `identity.legal_name`, and
`config profile edit --legal-name` did not exist. A coordinator replay confirmed
the mismatch. The fix exposes `--legal-name` through profile create/edit, stores
it as `identity.legal_name`, and passes the resolved registry revision into
`config profile preflight` so export-header legal-name requirements are visible
before modelo work. A fresh direct replay with `--legal-name` created an M202
2026 1P work unit successfully.

Marta also reproduced two bulk-ledger parity defects: CSV bulk classification
rejected `iva_category`, even though single `ledger classify` accepts
`--iva-category`, and bulk rows required full transaction ids while single
classification accepted unambiguous display ids. The fix adds `iva_category` to
the typed bulk CSV row and allowed-column set, carries it through the same
`ManualLedgerTransactionPatch` write path, resolves unambiguous id prefixes via
the shared live-id resolver, and preserves row-level failures for ambiguous
prefixes.

Ines's employed-plus-autonomous run then found a related IVA correction blocker:
a row classified as `iva_category=erroneous_invoice` blocked ledger preflight,
but `ledger view` hid the category and reclassifying it as
`domestic_general_21` was treated as a no-op. RAG and source triage showed the
mutation signature ignored `iva_category` and `counterparty_eu_member_state`.
The fix adds both fields to mutation/no-op detection, exposes them on the
canonical ledger transaction payload and `ledger view`, and pins the correction
flow through the real CLI. A fresh direct replay now shows `erroneous_invoice`,
accepts the `--reaffirm` correction, and then shows `domestic_general_21`.

The same personas left several residual model-boundary issues out of scope for
this scoped hardening pass: M210 still advertises `evento` while other surfaces
reject it; M130 Q2 can require an observed Q1 filing even when Q1 local filing
is refused as `NO_PENDING_OBLIGATION`; M390/M100 verification can block on
missing observed individual filings even when local calculations exist; M303
IVA wallet zero seed still does not replace explicit taxpayer override; M100
activity-mode binding accepts decimal `1` while rejecting `normal`; and at
least one calculation-preflight path can leak a raw `%{detail}` placeholder.
Those were retained as backlog rather than collapsed into this pass.

### wave-nine-persona-campaign | high | Cross-period personas separated safety gates from bounded bulk-classify parity

Wave nine continued the reframed campaign with four fresh CLI-only personas:
Adrian, a UK-resident non-resident property owner; Beatriz, an employee who
also invoices freelance work; Clara, a small S.L. administrator closing annual
IVA; and Nuria, a retailer under recargo de equivalencia assumptions. Each used
a blank `AEAT_LOCAL_STORAGE_ROOT`, a fake `AEAT_SECRET_PASSPHRASE`, fake
taxpayer identities, no source-code access, no `.vault` reading, no live AEAT
login, CLI help, scratch CSV/export files, and public AEAT/BOE pages for limited
external sanity checks. Each completed a testimonial; each completed
testimonial was routed to a separate read-only code triage subagent before the
coordinator selected any code change.

Adrian confirmed the current Modelo 210 boundary rather than discovering a new
calculation implementation gap. The non-resident profile and rental ledger
import/classify/export path worked, and his manual ledger arithmetic matched
the exported ledger rows. M210 local work creation remained intentionally
refused with the Sede G320 handoff. Code triage confirmed that refusal is
covered by the M210 Path-B tests and should not be weakened. The actionable
backlog is the contradictory period vocabulary: registry discovery still
advertises `evento`, the core `Period` boundary accepts `AD-HOC` and `EVENT-N`,
and readiness can fail closed only after the operator tries several incompatible
tokens. Adrian also externally grounded that 2026 Modelo 210 property-rental
changes under BOE-A-2026-13573 need registry/legal work before any local 2026
support can be claimed.

Beatriz completed M130 2025 1T create/calculate/verify/export with manual
arithmetic matching the CLI. Her Q2 and annual M100 path then hit the existing
clean-state dependency boundary: export artifacts are not observed filings, and
local filing can be refused outside the active obligation window. Code triage
classified the carry and M100 verification blocks as intentional safety gates
under the local-filed-observations rule, but retained UX debt: continuity
messages must say plainly that export alone does not satisfy
`previous_filing`, M100 employment withholding guidance around casilla `0596`
must point to the correct Modelo 111 binding rather than internal-error wording,
and unsupported M100 first-slice expense categories should list the currently
mapped category/casilla set.

Clara completed a legal-entity blank-state IVA annual run through four Modelo
303 quarters. Quarterly M303 calculate/verify/export worked and her manual
checks matched: annual output IVA 1470, deductible IVA 252, and annual result
1218. Modelo 390 calculation matched the same annual arithmetic, but verification
and export blocked because the four M303 dependencies lacked clean filed
evidence. RAG and triage classified this as the documented M390 safety boundary:
verified/exported local drafts are not clean official evidence, and IVA wallet
override only unblocks calculation. The residual product work is guidance and
noise reduction, not a calculation fix.

Nuria's recargo-equivalence retailer run separated legal modelling from bounded
CLI parity. Profile creation accepted `iva_regime=RECARGO_EQUIVALENCIA`, ledger
import/export worked, and manual ledger arithmetic matched. Her M303/M390 path
then blocked late on `anomaly_recargo_on_non_retailer`. Code triage confirmed
retailer-side recargo purchases are intentionally non-declarable and must not
feed deductible M303 IVA, while supplier-side recargo belongs to the separate
`recargo_amount` flow. The real hardening debt is earlier applicability: a pure
recargo-equivalence retailer should not look M303/M390-ready before a late
ledger anomaly. The bounded fix from Nuria's testimonial was narrower and safe:
bulk `ledger classify --from-csv` rejected `irpf_category` even though single-row
classify/update and export already support it. The fix adds `irpf_category` to
the typed bulk CSV row, allowed-column set, shared manual patch handoff, help
text, and real CLI persistence coverage.

### wave-ten-persona-campaign | high | CLI-only personas exposed AD-HOC, recargo wording, and annual M100 guidance gaps

Wave ten continued with three fresh CLI-only personas from blank local storage:
Tomas, an ad-hoc IVA operator exercising Modelos 308/309; Laura, an
employed-plus-autonomous annual Modelo 100 filer; and Pilar, a
recargo-equivalence retailer rerunning the bulk `irpf_category` path. Each used
fake taxpayer identities, scratch CSV/export files, no source-code or `.vault`
access, no live AEAT login, and public AEAT/BOE pages only as external sanity
checks. Their testimonials were each routed to read-only code triage agents
before implementation.

Tomas confirmed a real AD-HOC consistency split. Modelo 308 and 309 discovery
and work creation accept `AD-HOC`, but M308 calculation still reaches the
legacy `period_end_date()` helper and raises `invalid registry period
'AD-HOC'`. Modelo 309 is a different boundary: its ledger aggregation requires
a calendar date span, and triage classified full-year aggregation for `AD-HOC`
as legally unsafe without event-date or selected-transaction semantics. The
safe backlog is therefore two-part: fix M308 calculation so non-span AD-HOC
filings do not call the legacy date helper, and make M309 readiness/guidance
fail closed up front instead of suggesting `ledger preflight --period AD-HOC`.
The likely owner files are dirty in this shared worktree, so no overlapping
patch was made in this wave.

Laura proved that Modelo 100 casilla `0596` can be populated correctly via the
Modelo 111 relation-prefill binding, and her manual annual arithmetic matched
the CLI for employment gross income, autonomous income, deductible expenses,
net activity income, and the `0596` withholding credit. Triage classified her
remaining blockers as guidance, not calculation math: direct `--casilla
0596=...` hits an internal-style bound-input refusal instead of naming the
correct `--binding`; `0604`/`0609` depend on prior filed M130/M131 relation
observations rather than arbitrary binding values; `--form-number 0596` filters
a physical form field, not the printed casilla number; and the estimation-mode
binding exposes a decimal-coded value where the operator expected a named enum.
The related CLI and locale files are carrying unrelated WIP, so these were
retained as UX backlog rather than edited here.

Pilar confirmed the wave-nine `irpf_category` bulk classify fix from a fresh
operator seat: the CSV with both `iva_category` and `irpf_category` applied
five rows, and `ledger view` plus CSV/JSONL exports preserved the IRPF
categories. Her recargo run also reproduced the late M303/M390 retailer
boundary, but added a narrower clean defect: ledger preflight labelled every
`recargo_equivalencia` row as `anomaly_recargo_on_non_retailer` and used
purchase wording even for incoming rows. The calculation boundary remains
unchanged: retailer-side recargo purchases are non-deductible and must not feed
M303 input IVA, while supplier-side recargo belongs to the `recargo_amount`
channel. The bounded fix changes only the preflight issue reason/detail so the
row is reported as non-declarable recargo-equivalence and incoming rows point
to `recargo_amount` instead of purchase/non-retailer wording.

### wave-eleven-persona-campaign | high | Profile hard-stop passed; AD-HOC ledger readiness now fails closed

Wave eleven dispatched three fresh CLI-only personas from blank/scratch
storage: Isabel, a new translator worried about incomplete profile creation;
Mateo, an autónomo trying to drive quarterly filings into annual Modelo 100 and
390 summaries; and Noelia, an occasional non-periodic IVA operator re-testing
Modelos 308/309. Each used fake taxpayer data, no source-code or `.vault`
access, no live AEAT login, scratch artifacts, and public AEAT/BOE pages for
external sanity checks. Each completed testimonial was routed to a separate
read-only source triage agent before implementation.

Isabel proved the critical profile hard-stop works at the filing boundary. A
schema-valid but filing-incomplete profile could be created, but
`config profile preflight --modelo 303/130` reported missing
`identity.name` and `identity.surnames`, and `modelo work create` for both
M303 and M130 refused before any work unit was created. Follow-up
calculate/export attempts then failed with no-work-unit guidance rather than a
late calculation or export error. After completing the profile, M303/M130 work
creation and calculation succeeded; export refused draft/no-verified-revision
state; verification refused auth-not-ready. Triage confirmed this is the
desired safety boundary. Remaining UX debt is separate: `config profile
validate` says `readiness ready` for a schema-valid but filing-incomplete
profile, readiness suggestions use bucket ids rather than friendly names, M130
concurrent calculate may have a stale work-unit pointer race, and enum token
discoverability remains weak.

Mateo exposed the blank-state state-root usability problem from the opposite
direction. He correctly found `uv run aeat`, but stateful commands kept using
workspace `var/storage`; changing `AEAT_SECRET_PASSPHRASE` then failed to open
the existing master key, and common guessed variables such as `AEAT_HOME`,
`AEAT_STORAGE_DIR`, and `AEAT_STATE_DIR` did not redirect storage. Triage
classified this as a high UX/config blocker, not calculation data loss: the
documented setting is `AEAT_LOCAL_STORAGE_ROOT`, and related config/root
derivation files are already carrying broader WIP. The annual M130/M303 to
M100/M390 arithmetic baseline Mateo prepared remains useful for future
workflow validation, but his run did not reach stateful filing execution.

Noelia reproduced the AD-HOC defect from a clean operator path and externally
grounded why quarterly/full-year assumptions would be unsafe. M308/M309 list
and describe as `ad_hoc`, and work creation accepts `AD-HOC`. M308 calculate
still fails late through the legacy `period_end_date()` path. M309 readiness
previously reported `ready True` with `ledger_period 2026 AD-HOC` on an empty
ledger, while the ledger CLI itself rejects `AD-HOC`; after a ledger row was
added, readiness leaked an internal `has_date_span()` integrity message. Triage
confirmed the root cause: ledger preflight iterated by
`Period.contains()` without first rejecting non-span periods. The bounded fix
in this wave adds a typed `unsupported_period` ledger-preflight issue for any
non-calendar-span period, including empty catalogues, so M309 readiness now
fails closed instead of pretending an AD-HOC ledger preflight is ready.

### wave-twelve-persona-campaign | high | Profile creation now fails incomplete profiles and M200 micro display rate is aligned

Wave twelve reran the campaign shape with three fresh CLI-only personas and
separate source triage agents. Ines exercised a blank-state M349 foreign-client
persona; Dario exercised a small S.L. across Modelo 202 instalments and annual
Modelo 200; Sofia exercised an employed-plus-autonomous annual Modelo 100 path.
The personas used only the CLI, fake financial data, scratch local storage, and
external AEAT/BOE sanity checks; they did not read source, vault notes, or git
state. Their findings were routed through read-only source triage before coding.

Ines confirmed that valid M349 DE/FR operator rows still calculate, verify,
locally file, and export with the expected row totals, but a malformed
intra-community VAT row (`ZZ` / `BADVAT`) was accepted before this pass. The
bounded fix now validates M349 row VAT prefixes against the AEAT-supported
country-code set and rejects unsupported prefixes before row persistence. This
is deliberately local validation: it is not VIES verification and does not
assert that a syntactically valid VAT identifier is legally active.

Dario reproduced the M200 trust defect from a 2025 micro-company S.L. with
50,000.00 of taxable base and INCN below 1,000,000. The cuota íntegra already
followed the LIS DT 44ª 2025 first tranche at 21 percent (`00562=10500.00`),
but the display/export scalar `DP200014:00558` still echoed the legacy 23
percent. The fix adds a dated, display-only micro-company scalar that mirrors
the first tranche used by the bracketed cuota path: 23 percent for 2024, 21
percent for 2025, and 19 percent for 2026. The bracketed cuota formula remains
the authority for `00562`.

The profile hardening from this wave moves the critical failure earlier than
Modelo work. `config profile create` now refuses schema-valid but
filing-incomplete create flows before persisting a profile: natural persons
must carry entity type, name, and surnames; legal entities must carry entity
type and legal name; attribution entities must carry entity type and name. Patch
and edit flows remain allowed to repair existing records. This closes the
highest-confidence-loss path where users could create a profile that looked
valid and only discover missing filing identity facts inside modelo work.

Sofia's M100 path remains mostly backlog rather than a quick calculation patch.
The annual calculation engine can receive M130 and withholding relations, but a
bank-ledger-only payroll deposit cannot infer gross employment income or
withholding. The current CLI also makes M100 employment withholding casillas and
activity-mode/category selection hard to discover. Those are retained as UX and
workflow design debt, not recoded as hidden assumptions.

### wave-thirteen-persona-campaign | high | Export replay, profile import, and annual guidance defects were separated from backlog

Wave thirteen kept the corrected campaign shape: the coordinator stayed in the
coder role, while persona subagents operated only the CLI from blank storage
roots. Source triage was separate, read-only, and RAG-first. Elena exercised an
employed-plus-autonomous annual Modelo 100 path; Ramon exercised M308/M309
AD-HOC and annual closure probes; Ines exercised profile bundle export/import;
Marco exercised M349 foreign-operator rows. Personas created or imported
profiles, entered or imported business records, classified rows, calculated,
verified, locally filed or exported where supported, and manually compared
period and annual figures. Export bytes were treated as visual sanity evidence,
not as proof that the CLI matched the BOE structure.

Marco's M349 run reached calculate, verify, local file, and fichero export, but
visual record inspection found the exported operator VAT field duplicated the
country prefix (`DEDE...` and `FRFR...`). Source triage confirmed this as a real
export defect: the row model correctly accepts prefixed VAT identifiers for
operator input, while the fixed-width export has a separate country-code slot
and must write only the VAT number subfield. Commit `fb6d0d662` added a shared
M349 export normalizer, replayed filed row inputs through it, and asserted
500-byte record positions for country code and stripped VAT number.

Elena's M100 run separated a small implementation defect from larger annual UX
debt. `ledger list --year 2025` leaked the internal
`ledger-period-year-pairing` diagnostic even though the supported full-year
filter is `--period 0A --year 2025` or matching `--filter` pairs. Commit
`eeb2de989` keeps the fail-closed parser behavior but renders operator-facing
annual guidance. The M100 salary and withholding problem remains backlog:
gross employment income and retentions cannot be inferred from a net bank
deposit, and casillas `0003` and `0596` remain hard for a CLI-only user to
discover.

Ines proved the profile bundle happy path, then tampered exported bundles. The
previous import guard refused an invalid present tax id, but did not make the
single full `identity.tax_id` fact an explicit import boundary for missing,
blank, non-string, or duplicate values. Commit `d18a8e0b6` now requires exactly
one nonblank string tax id and validates its Spanish checksum before the bundle
can register a profile. This hardens the confidence-loss surface where a broken
profile could otherwise enter persistent storage and fail later inside modelo
work.

Ramon's AD-HOC and annual probes were deliberately not recoded into hidden
assumptions. M309 still needs grounded event-date or transaction-selection
semantics before it can become a smooth AD-HOC workflow, and M100 annual
guidance still needs clearer relation/casilla discovery. Source triage also
kept Marco's GB/XI M349 country-code concern as backlog rather than legal
assumptions.

Follow-up commit `c7ffc6a6f` closed Marco's filing-record list discoverability
defect without changing filing semantics. `aeat app modelo filing-record list`
now accepts `--modelo`, surfaces `modelo_filter` in text and JSON output, and
filters the existing filing-record catalogue by the stored Modelo code. The same
commit completed the localized bare-year ledger guidance introduced in
`eeb2de989`: both `--year 2025` and `--filter year=2026` fail closed with the
matching annual `--period 0A --year ...` guidance instead of leaking internal
parser tokens.

### wave-fourteen-persona-campaign | high | Profile edit/import baseline closure and workflow blockers separated

Wave fourteen re-seeded the campaign with three CLI-only personas from blank
storage roots plus separate read-only source triage. Clara exercised an
employed-plus-autonomous natural-person profile; Yara exercised EU/foreign
operator invoices and M349/M309 edges; Nadia exercised a small-company legal
entity setup path. Each persona used only the public CLI and scratch storage.
The coordinator kept source inspection and implementation in the coder role.

Clara reached profile creation, profile validation, ledger CSV import, and
direction inspection. Bulk `ledger classify --from-csv` then timed out and left
partial state: most rows were reviewed, several invoice rows stayed pending,
and proportional-use phone expenses still lacked `usage_ratio_id` evidence.
That blocked Modelo 303/130/390/100 calculation in this run. Nadia reached a
valid legal-entity profile and overview status, but was interrupted before
transaction/modelo work. Yara reached a valid profile, imported EU rows, and
classified DE/FR intra-community rows plus a DE reverse-charge purchase. Her
XI/Northern-Ireland edge was refused as a member state and had to be treated as
third-country export evidence; that remains legal-grounding backlog rather than
an implementation assumption.

Read-only profile triage confirmed create and modelo-work readiness gates were
already hard, then narrowed the remaining broken-profile confidence surface to
profile mutation/import paths. Follow-up implementation commit `e33403257`
promoted one filing-baseline helper and applies it to non-interactive edit,
full-flow edit, and portable bundle import. A profile edit or import now refuses
before persistence if it would leave the profile without a taxpayer-type axis,
legal-entity `identity.legal_name`, attribution-entity `identity.name`, or
natural-person `identity.name` plus `identity.surnames`. Bundle import still
keeps the prior exactly-one-valid-tax-id gate.

## Recommendations

Implemented and reviewed in this wave:

- IVA wallet explicit-zero reconciliation and first-period-zero grounding in
  `src/aeat/application/modelo/_iva_wallet_gate.py`, with regression coverage in
  `src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py` and
  `src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py`.
- Modelo 202 incomplete-modality blocking verification in
  `src/aeat/application/modelo/_verification_actions.py`, with lifecycle coverage
  in `src/aeat/application/modelo/tests/test_modelo_202_modality_lifecycle.py`
  plus adjacent test setup hardening.
- Stage-1 readiness fail-closed registry and missing-binding reporting in
  `src/aeat/application/state_projection.py`,
  `src/aeat/entrypoints/cli/_modelo_readiness_cli.py`, and
  `src/aeat/entrypoints/cli/_modelo_payloads.py`, with CLI and projection
  coverage in `src/aeat/entrypoints/cli/tests/test_modelo_discovery_defects.py`
  and `src/aeat/application/tests/test_state_projection.py`.
- Wave-three blank-state storage-root isolation in `src/aeat/core/config.py`,
  with regression coverage in
  `src/aeat/core/tests/test_storage_substrate_state_root.py` and
  `src/aeat/entrypoints/cli/tests/test_cold_start_wizard_registration.py`.
- Modelo 303 pre-activity target-period refusal in
  `src/aeat/application/modelo/_profile_readiness_gate.py` and
  `src/aeat/application/modelo/_work_addressing.py`, with coverage in
  `src/aeat/application/modelo/tests/test_profile_readiness_gate.py` and
  `src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py`.
- Modelo 390 unsupported fichero-BOE export wording in
  `src/aeat/application/filing/_export.py`, with no-layout coverage in
  `src/aeat/application/filing/tests/test_export.py` and
  `src/aeat/application/filing/tests/test_modelo_303_390.py`.
- Local filed Modelo 303 compensation-history projection in
  `src/aeat/application/modelo/_filed_revision_observation.py`,
  `src/aeat/application/modelo/_revision_persistence.py`,
  `src/aeat/application/modelo/_filing_actions.py`, and
  `src/aeat/application/calculations/_iva_compensation_history.py`, with
  regression coverage in
  `src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py`
  and adjacent IVA history/refund tests.
- Modelo 721 BOE source grounding repair for the cross-model registry blocker:
  `src/aeat/_data/registry/aeat/legal/monedas-virtuales.toml`, the bundled
  BOE PDFs under `src/aeat/_data/corpus/normatives/pdf/`, and
  `src/aeat/domain/calculations/registry/tests/test_modelo_721_registry.py`.
- M210 unsupported local work-create overview guidance in
  `src/aeat/application/overview/__init__.py`,
  `src/aeat/application/overview/_calendar_models.py`, and
  `src/aeat/entrypoints/cli/_overview_rendering.py`, with real CLI coverage in
  `src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py` and renderer coverage
  in `src/aeat/entrypoints/cli/tests/test_overview_rendering.py`.
- Modelo 130 pre-activity target-period refusal in
  `src/aeat/application/modelo/_profile_readiness_gate.py`, with application and
  CLI coverage in `src/aeat/application/modelo/tests/test_profile_readiness_gate.py`
  and `src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py`.
- IRNR profile conditional completeness hard gate in
  `src/aeat/application/user_profile/_completeness.py` and connected profile
  validation/preflight/create/status paths, with coverage in
  `src/aeat/application/user_profile/tests/test_irnr_profile_completeness.py`
  and `src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py`.
- Ledger source-jurisdiction add/import/export persistence and all-failed bulk
  classify nonzero exit in `src/aeat/application/ledger/_actions_import.py`,
  `src/aeat/application/ledger/_actions_export.py`, and
  `src/aeat/entrypoints/cli/_ledger_classify_cli.py`, with CLI coverage in
  `src/aeat/entrypoints/cli/tests/test_ledger_source_jurisdiction_export.py`
  and `src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py`.
- Ledger explicit `direction` import precedence in
  `src/aeat/adapters/inbound/financial/providers/_csv.py` and
  `src/aeat/adapters/inbound/financial/providers/_xlsx.py`, with provider and
  application coverage in
  `src/aeat/adapters/inbound/financial/providers/tests/test_csv.py` and
  `src/aeat/application/ledger/tests/test_actions_import_export.py`.
- M130 IRNR applicability refusal in
  `src/aeat/domain/calculations/registry/_applicability.py`, with registry and
  CLI coverage in
  `src/aeat/domain/calculations/registry/tests/test_modelo_applicability.py`
  and `src/aeat/entrypoints/cli/tests/test_modelo_work_applicability_guard.py`.
- Overview status instalment-period parsing in `src/aeat/entrypoints/cli/_overview.py`,
  with draft-filter coverage in
  `src/aeat/entrypoints/cli/tests/test_overview_verbs.py`.
- M349 operador row summary/replay/integrity hardening across
  `src/aeat/application/modelo/_calculation_actions.py`,
  `src/aeat/application/modelo/_registry_helpers.py`,
  `src/aeat/application/modelo/_revision_replay_inputs.py`,
  `src/aeat/application/filing/__init__.py`,
  `src/aeat/domain/filing/_validator.py`, and
  `src/aeat/application/modelo/_verification_actions.py`, with CLI coverage in
  `src/aeat/entrypoints/cli/tests/test_work_calculate_row_flag.py`.
- M202 legal-entity export identity mapping in
  `src/aeat/application/modelo/_export.py`,
  `src/aeat/application/filing/_export.py`, and
  `src/aeat/application/user_profile/_preflight.py`, with regression coverage in
  `src/aeat/application/modelo/tests/test_export.py` and
  `src/aeat/application/user_profile/tests/test_services.py`.
- M200/M202 payment-relation guidance in
  `src/aeat/entrypoints/cli/_modelo.py`,
  `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`, and
  `src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py`, with CLI coverage in
  `src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py`.
- Locale scaffold repair for `cli.ledger.classify.bulk_all_failed` in
  `src/aeat/locales/{ca,en,es,hu}.yml`, preserving the all-failed bulk-classify
  warning across translated output.
- Blank-state overview profile-key registration in
  `src/aeat/application/state_projection.py`, with a fresh-process CLI
  regression in
  `src/aeat/entrypoints/cli/tests/test_cold_start_wizard_registration.py`.
- Legal-entity `identity.legal_name` profile entry and preflight alignment in
  `src/aeat/core/setup_answers.py`,
  `src/aeat/application/wizard/_catalogue.py`,
  `src/aeat/application/wizard/_commands.py`, and
  `src/aeat/entrypoints/cli/_config/__init__.py`, with CLI coverage in
  `src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py`
  and `src/aeat/entrypoints/cli/tests/test_config_preflight_revision_default.py`.
- Bulk `ledger classify --from-csv` parity for `iva_category` and unambiguous
  display-id prefixes in `src/aeat/application/ledger/_models.py` and
  `src/aeat/application/ledger/_actions_classification.py`, with real CLI
  coverage in `src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py`.
- Ledger IVA-category correction visibility and mutation detection in
  `src/aeat/application/ledger/_actions_common.py`,
  `src/aeat/application/ledger/_actions_manual.py`,
  `src/aeat/application/ledger/_models.py`,
  `src/aeat/entrypoints/cli/_ledger_payloads.py`, and
  `src/aeat/entrypoints/cli/_ledger_read_cli.py`, with CLI coverage in
  `src/aeat/entrypoints/cli/tests/test_ledger_ux_defect_cluster.py`.
- Bulk `ledger classify --from-csv` parity for `irpf_category` in
  `src/aeat/application/ledger/_models.py`,
  `src/aeat/application/ledger/_actions_classification.py`,
  `src/aeat/entrypoints/cli/_ledger.py`, and
  `src/aeat/locales/{ca,en,es,hu}.yml`, with real CLI persistence coverage in
  `src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py`.
- Recargo-equivalence ledger preflight wording/direction hardening in
  `src/aeat/application/ledger/_preflight.py`, with focused coverage in
  `src/aeat/application/ledger/tests/test_preflight_anomaly.py`.
- Non-span ledger-preflight fail-closed handling for AD-HOC/readiness surfaces
  in `src/aeat/application/ledger/_preflight.py`, with service coverage in
  `src/aeat/application/ledger/tests/test_preflight.py` and projection coverage
  in `src/aeat/application/tests/test_state_projection.py`.
- M349 unsupported intra-community VAT prefix refusal in
  `src/aeat/domain/modelos/_row_models.py`, with row-model and CLI row-entry
  coverage in `src/aeat/domain/modelos/tests/test_row_models.py` and
  `src/aeat/entrypoints/cli/tests/test_work_calculate_row_flag.py`.
- Profile-create filing-baseline refusal in
  `src/aeat/application/wizard/_commands.py` and
  `src/aeat/locales/{ca,en,es,hu}.yml`, with wizard and CLI coverage in
  `src/aeat/application/wizard/tests/test_create_pointer_atomicity.py`,
  `src/aeat/application/wizard/tests/test_commands_helpers.py`,
  `src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py`, and
  `src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py`.
- M200 micro-company display-rate alignment in the 2024-y-siguientes registry
  records for Modelo 200, with grounding and dispatch coverage in
  `src/aeat/domain/calculations/registry/tests/test_modelo_200_tipo_gravamen_dispatch.py`,
  adjacent cuota-lane coverage in
  `src/aeat/domain/calculations/registry/tests/test_modelo_200_cuota_integra_lanes.py`,
  and CLI calculation fixture hardening in
  `src/aeat/entrypoints/cli/tests/test_modelo_calculation_through_real_cli.py`.
- M349 fichero-BOE VAT-number subfield stripping in
  `src/aeat/domain/modelos/_row_models.py`,
  `src/aeat/application/modelo/_revision_replay_inputs.py`,
  `src/aeat/application/modelo/_export.py`, and
  `src/aeat/domain/calculations/registry/_invoice_bindings.py`, with row-model,
  replay, invoice-binding, registry, and CLI export coverage.
- Ledger bare-year filter guidance in
  `src/aeat/entrypoints/cli/_ledger_list.py`, with real CLI filter coverage in
  `src/aeat/entrypoints/cli/tests/test_ledger_list_filter.py`.
- Profile bundle import tax-id hard gate in
  `src/aeat/entrypoints/cli/_config/_profile_bundle.py`, with real bundle
  tamper coverage in
  `src/aeat/entrypoints/cli/tests/test_profile_import_idempotency.py`.
- Filing-record list `--modelo` filtering in
  `src/aeat/application/modelo/_filing_actions.py`,
  `src/aeat/entrypoints/cli/_modelo_records_cli.py`, and
  `src/aeat/entrypoints/cli/_modelo_payloads.py`, with service and CLI coverage
  in `src/aeat/application/modelo/tests/test_file_flow_filing.py` and
  `src/aeat/entrypoints/cli/tests/test_cli_surface.py`.
- Localized ledger period/year pairing guidance in
  `src/aeat/entrypoints/cli/_ledger_list.py`,
  `src/aeat/entrypoints/cli/_ledger_read_cli.py`, and
  `src/aeat/locales/{ca,en,es,hu}.yml`, with `--year` and `--filter year=...`
  CLI coverage.
- Profile filing-baseline hard-stop shared across create/edit/import in
  `src/aeat/application/user_profile/_filing_baseline.py`,
  `src/aeat/application/wizard/_commands.py`,
  `src/aeat/application/wizard/_persistence.py`, and
  `src/aeat/entrypoints/cli/_config/_profile_bundle.py`, with localized
  operator refusals and real CLI/import tamper coverage in
  `src/aeat/application/wizard/tests/test_create_pointer_atomicity.py`,
  `src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py`,
  `src/aeat/entrypoints/cli/tests/test_profile_output_language.py`, and
  `src/aeat/entrypoints/cli/tests/test_profile_import_idempotency.py`.

Verification passed:

- `uv run --no-sync pytest -m "" -q src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py src/aeat/application/modelo/tests/test_iva_wallet_decision_binding.py src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py::test_m303_fresh_profile_binding_override_surfaces_seed_verb_not_mode_flag src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py::test_m303_fresh_profile_calculate_without_binding_override_does_not_raise_wallet_error`
- `uv run --no-sync pytest -m "" -q src/aeat/application/modelo/tests/test_modelo_202_modality_lifecycle.py src/aeat/application/modelo/tests/test_verificado_completo_regression.py`
- `uv run --no-sync pytest -m integration -q src/aeat/entrypoints/cli/tests/test_modelo_202_modality.py src/aeat/entrypoints/cli/tests/test_modelo_discovery_defects.py`
- `uv run --no-sync pytest -m "" -q src/aeat/application/tests/test_state_projection.py src/aeat/application/modelo/tests/test_profile_readiness_gate.py`
- `uv run --no-sync ruff check` on the touched implementation and test files.
- `uv run --no-sync pytest src/aeat/core/tests/test_storage_substrate_state_root.py -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_cold_start_wizard_registration.py -m integration -k profile_create_uses_local_storage_secret_store -q`
- `uv run --no-sync pytest -m "" -q src/aeat/application/modelo/tests/test_profile_readiness_gate.py src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py::test_work_create_refuses_pre_activity_m303_and_creates_no_unit src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py::test_work_create_refuses_incomplete_profile_with_actionable_readiness_error`
- `uv run --no-sync pytest src/aeat/application/filing/tests/test_export.py src/aeat/application/filing/tests/test_modelo_303_390.py -k "without_registry_layout or without_registry_export_layout or modelo_390_export_refuses_missing_boe_layout_from_real_registry"`
- `uv run --no-sync pytest -q src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py`
- `uv run --no-sync pytest -q src/aeat/application/calculations/tests/test_iva_compensation_history.py src/aeat/application/calculations/tests/test_modelo_303_refunded_period_carry.py`
- `uv run --no-sync ruff check src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/__init__.py src/aeat/application/modelo/_filed_revision_observation.py src/aeat/application/modelo/_revision_persistence.py src/aeat/application/modelo/_filing_actions.py src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py`
- `git diff --check -- src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/__init__.py src/aeat/application/modelo/_filed_revision_observation.py src/aeat/application/modelo/_revision_persistence.py src/aeat/application/modelo/_filing_actions.py src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py`
- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/tests/test_modelo_721_registry.py`
- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/tests/test_catalogue_verification.py src/aeat/domain/calculations/registry/tests/test_committed_registry.py -k "source or corpus or required_model_law_coverage or committed_registry_tree"`
- `uv run --no-sync aeat app registry inspect`
- Corrected direct CLI smoke: with `AEAT_LOCAL_STORAGE_ROOT` and
  `AEAT_SECRET_PASSPHRASE`, and without `AEAT_DATABASE_URL`, profile creation
  succeeded, Modelo 303 2026 1T refused as pre-activity for
  `activity_start_date=2026-05-01`, and Modelo 303 2026 2T created a work unit.
- CLI-only Lucia rerun: M303 Q1 local filing projected `iva-wallet balance`
  `total_balance 420.00`; M303 Q1-Q4 calculate/verify/local-file/export passed
  after explicit wallet overrides; M390 calculate/verify/local-file passed and
  export refused the known unsupported layout boundary.
- CLI-only Marta rerun: M202 incomplete profile blocked from filing/export; M202
  complete profile calculate/verify/local-file/export passed; after the M721
  corpus repair, M200 calculate/verify/export passed.
- `uv run --no-sync pytest -m integration -q src/aeat/entrypoints/cli/tests/test_overview_rendering.py::test_next_step_does_not_suggest_unsupported_m210_work_create src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py::test_overview_next_step_does_not_suggest_m210_work_create_for_non_resident src/aeat/entrypoints/cli/tests/test_modelo_210_stub_refusal.py src/aeat/entrypoints/cli/tests/test_modelo_discovery_defects.py::test_modelo_readiness_refuses_period_without_registry_coverage`
- `uv run --no-sync pytest -m "" -q src/aeat/application/modelo/tests/test_profile_readiness_gate.py src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py::test_work_create_refuses_pre_activity_m303_and_creates_no_unit src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py::test_work_create_refuses_pre_activity_m130_and_creates_no_unit`
- `uv run --no-sync python -m aeat.locales scaffold --check`
- `uv run --no-sync python -m aeat.locales audit`
- `uv run --no-sync pytest -q src/aeat/tests/test_locale_coverage_inventory.py src/aeat/tests/test_locale_coverage_hardened_errors.py`
- `uv run --no-sync pytest -q src/aeat/core/tests/test_modelo_string_usage.py`
- `uv run --no-sync ruff check src/aeat/application/overview/__init__.py src/aeat/application/overview/_calendar_models.py src/aeat/entrypoints/cli/_overview_rendering.py src/aeat/entrypoints/cli/tests/test_overview_rendering.py src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py src/aeat/application/modelo/_profile_readiness_gate.py src/aeat/application/modelo/tests/test_profile_readiness_gate.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/tests/test_irnr_profile_completeness.py src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py src/aeat/domain/calculations/registry/tests/test_modelo_applicability.py src/aeat/entrypoints/cli/tests/test_modelo_work_applicability_guard.py src/aeat/entrypoints/cli/tests/test_overview_verbs.py::test_overview_status_period_filter_accepts_instalment_period src/aeat/entrypoints/cli/tests/test_overview_verbs.py::test_overview_status_period_filter_matches_typed_draft_period`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py::test_non_resident_irnr_quiet_create_requires_country_before_registration src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py::test_gb_legal_entity_irnr_quiet_create_requires_representante_before_registration src/aeat/entrypoints/cli/tests/test_modelo_work_applicability_guard.py::test_work_create_refuses_modelo_130_for_non_resident_irnr src/aeat/entrypoints/cli/tests/test_overview_verbs.py::test_overview_status_period_filter_accepts_instalment_period src/aeat/entrypoints/cli/tests/test_overview_verbs.py::test_overview_status_period_filter_matches_typed_draft_period`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_ledger_source_jurisdiction_export.py src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py::test_classify_from_csv_partial_failure_applies_valid_rows src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py::test_classify_from_csv_all_failed_exits_nonzero`
- `uv run --no-sync pytest -q src/aeat/domain/deadlines/tests/test_taxpayer_model.py src/aeat/application/workflow/tests/test_profile_health.py src/aeat/application/wizard/tests/test_status.py src/aeat/application/user_profile/tests/test_profile_repository.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_work_calculate_row_flag.py::TestRevisionViewSurfacesDetailRows::test_m349_operador_rows_feed_summary_and_verify src/aeat/entrypoints/cli/tests/test_work_calculate_row_flag.py`
- `uv run --no-sync pytest -q src/aeat/adapters/inbound/financial/providers/tests/test_csv.py src/aeat/adapters/inbound/financial/providers/tests/test_xlsx.py src/aeat/application/ledger/tests/test_actions_import_export.py::test_import_ledger_source_owns_provider_validation_ingest_and_persistence src/aeat/application/ledger/tests/test_actions_import_export.py::test_import_ledger_source_honors_explicit_direction_column_on_positive_amount_in_exports`
- `uv run --no-sync ruff check src/aeat/adapters/inbound/financial/providers/_csv.py src/aeat/adapters/inbound/financial/providers/_xlsx.py src/aeat/adapters/inbound/financial/providers/tests/test_csv.py src/aeat/application/ledger/tests/test_actions_import_export.py`
- `git diff --check -- src/aeat/adapters/inbound/financial/providers/_csv.py src/aeat/adapters/inbound/financial/providers/_xlsx.py src/aeat/adapters/inbound/financial/providers/tests/test_csv.py src/aeat/application/ledger/tests/test_actions_import_export.py`; only Git CRLF normalization warnings were reported.
- `uv run --no-sync pytest -q src/aeat/application/modelo/tests/test_export.py::test_modelo_202_legal_entity_exports_company_name_in_razon_social_slot src/aeat/application/modelo/tests/test_export.py::test_export_headers_use_typed_instalment_period_dates src/aeat/application/modelo/tests/test_export.py::test_compose_export_headers_emits_devolucion_for_redeme_negative_303 src/aeat/application/filing/tests/test_export.py::test_export_requires_declared_header_values src/aeat/application/user_profile/tests/test_services.py::test_preflight_accepts_legal_entity_legal_name_for_export_headers`
- `uv run --no-sync pytest -q src/aeat/application/filing/tests/test_export.py::test_export_requires_declared_header_values src/aeat/application/filing/tests/test_export.py::test_export_rejects_blank_required_header_values src/aeat/application/modelo/tests/test_export.py::test_modelo_202_legal_entity_exports_company_name_in_razon_social_slot src/aeat/application/modelo/tests/test_export.py::test_modelo_202_legal_entity_export_requires_legal_name src/aeat/application/user_profile/tests/test_services.py::test_preflight_accepts_legal_entity_legal_name_for_export_headers src/aeat/application/user_profile/tests/test_services.py::test_preflight_rejects_legal_entity_export_identity_fragments`
- `uv run --no-sync pytest -q src/aeat/application/filing/tests/test_export.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/tests/test_services.py`
- `uv run --no-sync pytest -q src/aeat/application/modelo/tests/test_export.py::test_modelo_202_legal_entity_exports_company_name_in_razon_social_slot src/aeat/application/modelo/tests/test_export.py::test_modelo_202_legal_entity_export_requires_legal_name src/aeat/application/modelo/tests/test_export.py::test_export_headers_use_typed_instalment_period_dates src/aeat/application/modelo/tests/test_export.py::test_compose_export_headers_emits_devolucion_for_redeme_negative_303 src/aeat/application/modelo/tests/test_export.py::test_export_modelo_303_wallet_only_revision_writes_fichero_with_redacted_wallet_provenance`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_cold_start_wizard_registration.py::test_cold_process_overview_status_without_profile_registers_profile_keys src/aeat/application/tests/test_state_projection.py::test_projection_without_active_profile_is_empty`; the state-projection unit test was deselected by the integration marker and was also run separately without `-m`.
- `uv run --no-sync pytest -q src/aeat/application/tests/test_state_projection.py::test_projection_without_active_profile_is_empty`
- Direct blank-root smoke: with a fresh `AEAT_LOCAL_STORAGE_ROOT`, no `AEAT_DATABASE_URL`, and a fake passphrase, `uv run --no-sync aeat app overview status` rendered a normal no-profile overview instead of the internal profile-key registry error.
- `uv run --no-sync ruff check src/aeat/application/modelo/_export.py src/aeat/application/filing/_export.py src/aeat/application/user_profile/_preflight.py src/aeat/application/modelo/tests/test_export.py src/aeat/application/user_profile/tests/test_services.py src/aeat/application/state_projection.py src/aeat/entrypoints/cli/tests/test_cold_start_wizard_registration.py`
- `uv run --no-sync ruff check src/aeat/application/filing/_export.py src/aeat/application/modelo/_export.py src/aeat/application/user_profile/_preflight.py src/aeat/application/filing/tests/test_export.py src/aeat/application/modelo/tests/test_export.py src/aeat/application/user_profile/tests/test_services.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_discovery_cli.py src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py::test_bindings_list_missing_m200_surfaces_m202_relation_inputs src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py::test_bindings_list_without_missing_does_not_append_m200_relation_guidance src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py::test_work_calculate_missing_m200_m202_relation_prefill_is_advisory src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py::test_missing_relation_guidance_helper_routes_m200_m202_to_relation_flag`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py::test_classify_from_csv_all_failed_exits_nonzero`
- `uv run --no-sync python -m aeat.locales scaffold --check`
- `git diff --check -- src/aeat/application/modelo/_export.py src/aeat/application/filing/_export.py src/aeat/application/user_profile/_preflight.py src/aeat/application/modelo/tests/test_export.py src/aeat/application/user_profile/tests/test_services.py src/aeat/application/state_projection.py src/aeat/entrypoints/cli/tests/test_cold_start_wizard_registration.py`; only Git CRLF normalization warnings were reported.
- `git diff --check --` on the M202 export, M200 guidance, locale, and audit files; only Git CRLF normalization warnings were reported.
- `uv run --no-sync ruff check` on the wave-six touched implementation and test files.
- `git diff --check --` on the wave-six touched implementation and test files; only Git CRLF normalization warnings were reported.
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py::test_legal_entity_profile_create_and_edit_exposes_legal_name src/aeat/entrypoints/cli/tests/test_config_preflight_revision_default.py::test_preflight_reports_legal_entity_export_legal_name_requirement`
- Direct blank-root legal-entity smoke: with `--legal-name`, `config profile
  preflight --modelo 202 --filing-year 2026 --period 1P` returned
  `readiness ready missing=0`, and `app modelo work create --modelo 202 --year
  2026 --period 1P` created a work unit.
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_ledger_ux_defect_cluster.py::test_classify_can_correct_and_view_iva_category src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py::test_classify_from_csv_accepts_iva_category_column src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py::test_classify_from_csv_accepts_display_id_prefix src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py::test_classify_from_csv_ambiguous_prefix_is_row_failure`
- Direct blank-root IVA-category correction smoke: `ledger view` showed
  `erroneous_invoice`, the `--reaffirm --iva-category domestic_general_21`
  correction succeeded, and `ledger view` then showed `domestic_general_21`.
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py src/aeat/entrypoints/cli/tests/test_config_preflight_revision_default.py src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py src/aeat/entrypoints/cli/tests/test_ledger_ux_defect_cluster.py`
- `uv run --no-sync ruff check src/aeat/core/setup_answers.py src/aeat/application/wizard/_catalogue.py src/aeat/application/wizard/_commands.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/application/ledger/_actions_common.py src/aeat/application/ledger/_models.py src/aeat/application/ledger/_actions_manual.py src/aeat/application/ledger/_actions_classification.py src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_payloads.py src/aeat/entrypoints/cli/_ledger_read_cli.py src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py src/aeat/entrypoints/cli/tests/test_config_preflight_revision_default.py src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py src/aeat/entrypoints/cli/tests/test_ledger_ux_defect_cluster.py`
- `uv run --no-sync python -m aeat.locales scaffold --check`
- `uv run --no-sync python -m aeat.locales audit`
- Wave-nine focused bulk IRPF-category fix: `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py::test_classify_from_csv_accepts_irpf_category_column`
- Wave-nine affected bulk-classify set: `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py::test_classify_from_csv_accepts_iva_category_column src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py::test_classify_from_csv_accepts_irpf_category_column src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py::test_classify_from_csv_accepts_display_id_prefix src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py::test_classify_from_csv_ambiguous_prefix_is_row_failure src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py::test_classify_from_csv_rejects_unknown_column`
- Wave-nine focused ruff: `uv run --no-sync ruff check src/aeat/application/ledger/_models.py src/aeat/application/ledger/_actions_classification.py src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py`
- Wave-nine locale scaffold: `uv run --no-sync python -m aeat.locales scaffold --check`
- Wave-ten recargo preflight focused tests: `uv run --no-sync pytest src/aeat/application/ledger/tests/test_preflight_anomaly.py src/aeat/application/ledger/tests/test_preflight.py -q`
- Wave-ten recargo preflight ruff: `uv run --no-sync ruff check src/aeat/application/ledger/_preflight.py src/aeat/application/ledger/tests/test_preflight_anomaly.py`
- Wave-ten bulk-classify regression suite: `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py`
- Wave-eleven AD-HOC ledger-preflight regression: `uv run --no-sync pytest src/aeat/application/ledger/tests/test_preflight.py src/aeat/application/ledger/tests/test_preflight_anomaly.py src/aeat/application/tests/test_state_projection.py::test_modelo_309_ad_hoc_readiness_fails_closed_for_non_span_ledger_period -q`
- Wave-eleven AD-HOC/recargo preflight ruff: `uv run --no-sync ruff check src/aeat/application/ledger/_preflight.py src/aeat/application/ledger/tests/test_preflight.py src/aeat/application/ledger/tests/test_preflight_anomaly.py src/aeat/application/tests/test_state_projection.py`
- Wave-twelve M349 row validation: `uv run --no-sync pytest src/aeat/domain/modelos/tests/test_row_models.py src/aeat/entrypoints/cli/tests/test_work_calculate_row_flag.py -q`
- Wave-twelve M349 row validation ruff: `uv run --no-sync ruff check src/aeat/domain/modelos/_row_models.py src/aeat/domain/modelos/tests/test_row_models.py src/aeat/entrypoints/cli/tests/test_work_calculate_row_flag.py`
- Wave-twelve profile-create hard stop: `uv run --no-sync pytest src/aeat/application/wizard/tests/test_create_pointer_atomicity.py src/aeat/application/wizard/tests/test_commands_helpers.py -q`
- Wave-twelve profile-create CLI regression: `uv run --no-sync pytest -m "integration or unit" src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py::test_profile_create_refuses_incomplete_profile_before_modelo_work src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py::test_work_create_refuses_pre_activity_m303_and_creates_no_unit src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py::test_work_create_refuses_pre_activity_m130_and_creates_no_unit src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py -q`
- Wave-twelve profile-create ruff/YAML: `uv run --no-sync ruff check src/aeat/application/wizard/_commands.py src/aeat/application/wizard/tests/test_create_pointer_atomicity.py src/aeat/entrypoints/cli/tests/_profile_cli_support.py src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py`, plus a PyYAML parse over `src/aeat/locales/{ca,en,es,hu}.yml`.
- Wave-twelve profile-create direct smokes: an incomplete blank-root profile create refused with `REFUSED_WIZARD_MISSING_FLAG`, and a matching create with `--entity-type natural_person --name ... --surnames ...` succeeded.
- Wave-twelve M200 display-rate grounding: `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_modelo_200_tipo_gravamen_dispatch.py src/aeat/domain/calculations/registry/tests/test_modelo_200_cuota_integra_lanes.py -q`
- Wave-twelve M200 CLI calculation regression: `uv run --no-sync pytest -m "integration or unit" src/aeat/entrypoints/cli/tests/test_modelo_calculation_through_real_cli.py -q --tb=short`
- Wave-twelve M200 ruff/diff check: `uv run --no-sync ruff check src/aeat/entrypoints/cli/tests/test_modelo_calculation_through_real_cli.py src/aeat/domain/calculations/registry/tests/test_modelo_200_tipo_gravamen_dispatch.py src/aeat/domain/calculations/registry/tests/test_modelo_200_cuota_integra_lanes.py`; `git diff --check` on the scoped M200 registry/test files and the CLI calculation test reported only Git CRLF normalization warnings before staging, and cached diff check was clean before commit.
- Wave-thirteen M349 export-prefix regression: `uv run --no-sync pytest src/aeat/domain/modelos/tests/test_row_models.py src/aeat/application/modelo/tests/test_revision_replay_inputs.py src/aeat/domain/calculations/registry/tests/test_invoice_bindings.py src/aeat/domain/calculations/registry/tests/test_modelo_349_registry.py src/aeat/entrypoints/cli/tests/test_work_calculate_row_flag.py -q --tb=short -m "unit or integration"`.
- Wave-thirteen ledger annual-filter guidance: `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_ledger_list_filter.py -q --tb=short -m integration` and `uv run --no-sync pytest src/aeat/application/review/tests/test_filter.py -q --tb=short`.
- Wave-thirteen profile bundle tax-id import gate: `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_profile_import_idempotency.py -q --tb=short -m integration`.
- Wave-thirteen focused ruff checks passed for the touched M349, ledger-list,
  and profile-bundle implementation and test files.
- Wave-thirteen filing-record modelo filter: `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_cli_surface.py::test_app_modelo_filing_record_list_text_header_is_well_formed src/aeat/entrypoints/cli/tests/test_cli_surface.py::test_app_modelo_filing_record_list_accepts_modelo_filter src/aeat/entrypoints/cli/tests/test_cli_surface.py::test_app_ledger_create_manual_transaction_persists_in_active_bucket -q --tb=short -m integration` and `uv run --no-sync pytest src/aeat/application/modelo/tests/test_file_flow_filing.py -q --tb=short -k list_filing_records`.
- Wave-thirteen ledger guidance and locale closure: `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_ledger_list_filter.py -q --tb=short -m integration`, `uv run --no-sync python -m aeat.locales scaffold --check`, and `uv run --no-sync python -m aeat.locales audit`.
- Wave-thirteen filing-record/ledger guidance ruff and diff checks passed for
  the touched implementation, test, and locale files. A read-only code review
  found one medium issue in the `--filter year=...` guidance path; the helper now
  derives a digit-only filter year and the regression is covered.
- Wave-fourteen profile filing-baseline hard stop:
  `uv run --no-sync pytest src/aeat/application/wizard/tests/test_create_pointer_atomicity.py src/aeat/application/wizard/tests/test_persistence_canonical.py src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py src/aeat/entrypoints/cli/tests/test_profile_output_language.py src/aeat/entrypoints/cli/tests/test_profile_import_idempotency.py src/aeat/application/user_profile/tests/test_bundle_reexports.py -q --tb=short -m "not e2e"`.
- Wave-fourteen focused profile regression slice:
  `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py::test_edit_refuses_natural_person_branch_change_without_legal_name src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py::test_edit_refuses_legal_entity_branch_change_without_surnames src/aeat/entrypoints/cli/tests/test_profile_import_idempotency.py::test_import_refuses_missing_filing_identity_baseline -q --tb=short -m integration`.
- Wave-fourteen profile-baseline ruff and locale checks:
  `uv run --no-sync ruff check` on the touched profile/wizard/import/test files,
  `uv run --no-sync python -m aeat.locales scaffold --check`, and
  `uv run --no-sync python -m aeat.locales audit`.

Independent read-only reviews reported no findings for the IVA wallet patch,
the Modelo 202 modality gate, the stage-1 readiness hardening, the M390 export
wording patch, the blank-state storage isolation patch, and the M303
pre-activity target-period guard. The local filed M303 compensation-history
projection also received a no-findings review. The M202 legal-entity export
review first found two high-risk over-broad paths; both were corrected and the
re-review reported no findings. The M200/M202 relation-guidance review first
found two low-risk test/surface gaps; both were corrected, with the real
work-calculate path captured as advisory and the helper-level relation error
path tested separately, and the follow-up review reported no findings. The M210
overview review found hygiene issues that were fixed before verification, and
the M130 pre-activity review found no correctness issues.
The wave-fourteen profile-baseline review found the full-flow edit bypass and
baseline-incomplete test fixtures before commit; both were corrected and covered
before `e33403257` landed.

Full-suite verification was intentionally not claimed because this shared
worktree carries extensive unrelated WIP.

Residual backlog:

- Add readiness stage-2 aggregation for wallet and applicability gates so
  `ready` predicts the existing calculation authority more completely.
- Decide and implement the M210 event-period registry token migration so
  `EVENT-N` is consistently advertised and accepted, while `evento` is no
  longer advertised as a CLI-valid period.
- Decide the M210 2026 property-rental registry/legal update under
  BOE-A-2026-13573 before claiming local 2026 M210 support.
- Add or explicitly scope the 2026 Modelo 100 annual path for employed-plus-
  autonomous personas; current registry coverage stops at 2025.
- Resolve Modelo 100 export for verified 2025 revisions that currently refuse
  because the `xml_dictionary` layout is unsupported by the local exporter.
- Keep the M303 local-filed recurrence gate explicit: local filed history may
  populate `iva-wallet balance`, but calculation must continue to require AEAT
  wallet/cartera evidence or explicit taxpayer override before using
  `filed_history_only` values in casilla 110.
- Add a legally grounded "Spanish permanent establishment / Spanish presence"
  profile axis before suppressing M200/M202 for foreign legal entities that
  assert no Spanish PE; the current profile schema cannot encode the distinction
  safely.
- Decide whether local filing should preflight exportability before stamping a
  local filing record, so export-only layout gaps cannot surprise operators
  after a local filing event.
- Surface a clearer M200 final differential after M202 payments and improve
  help/display for long flags and missing corporate bindings.
- Align M349 readiness with the work-create applicability gate, or explicitly
  label readiness as stage-1 so attribution-entity targets do not look
  filing-ready when applicability will refuse them.
- Improve M349 row-entry help and validation wording so `razon_social` is
  discoverable and raw Pydantic documentation URLs do not leak into
  taxpayer-facing refusal text.
- Ground M349 GB/XI country-code validation against the current authoritative
  intra-community rules before tightening accepted prefixes beyond the existing
  local BOE code-set checks.
- Reword overview status so `Borradores 0` cannot be mistaken for lost modelo
  work units when the work-unit store contains active drafts.
- Clarify local export versus local filing versus official/imported filing
  evidence in cross-period dependency guidance, especially for M130/M100 annual
  carry paths.
- Add earlier applicability/preflight refusal for pure recargo-equivalence
  retailer profiles on M303/M390, or otherwise make the unsupported-retailer
  boundary explicit before work creation.
- Investigate `ledger classify --from-csv` timeout/non-atomic partial
  application under medium-sized persona CSVs, and make proportional-use
  `usage_ratio_id` readiness guidance discoverable before modelo calculation.
- Fix M308 `AD-HOC` consistency so describe/create/calculate use the same
  period boundary or fail closed at the first CLI boundary.
- Extend M309 `AD-HOC` fail-closed handling beyond the ledger-preflight
  boundary into calculate/guidance, so operators never receive impossible
  ledger CLI commands; true M309 support needs grounded event-date or
  transaction-selection semantics.
- Decide whether profile import should refuse schema-valid but filing-incomplete
  profiles at import time; profile create now fails hard before persistence, and
  edit/patch remains available for repairing existing profiles.
- Rename or split `config profile validate` output so schema validity cannot
  read as filing readiness, and prefer profile display names over bucket ids in
  readiness repair suggestions.
- Clarify `casillas --form-number` or add a separate casilla-number filter so
  operators can find M100 casilla `0003` from the full casilla listing.
- Improve M100 employed-plus-autonomous discoverability: employment withholdings,
  valid activity expense taxonomy, M130 fold-in dependency, and annual export
  remain hard for CLI-only users to cross-reference.
- Improve M100 casilla `0596` guidance so direct `--casilla` attempts name the
  correct bound input channel and distinguish Modelo 111 periodic withholding
  from Modelo 190 annual summary.
- Make mixed-use allocation/category recovery more understandable; the all-failed
  bulk classify exit-code defect is fixed, but personas still saw category/ratio
  contradictions.
- Reduce repeated local-evidence advisory noise in M390 verification output.
- Add text-output coverage for readiness missing-binding detail rows and direct
  legacy verified-revision coverage for M202 file/export guards if legacy state
  migration becomes relevant.
- Reconcile filed work-unit `state=borrador` wording with visible filed revision
  records so local lifecycle state does not confuse non-technical operators.
- Clarify and/or harden the M130 cross-period observed-filing dependency: a
  persona could calculate/export Q1 locally, but Q2 then required an observed Q1
  filing while Q1 local filing was refused as `NO_PENDING_OBLIGATION`.
- Improve M100 activity-mode binding UX so the operator can select direct
  estimation mode with a named value rather than discovering that decimal `1`
  works while `normal` is rejected.
- Fix raw `%{detail}` placeholder leakage in calculation-preflight refusals.
