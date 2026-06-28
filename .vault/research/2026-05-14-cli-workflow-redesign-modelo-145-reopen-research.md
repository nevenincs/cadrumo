---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-145-foundation-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-145-foundation-research]]'
  - '[[2026-05-14-cli-workflow-redesign-w51-modelo-145-deferral-baseline-exec]]'
---

# `cli-workflow-redesign` research: `Modelo 145 foundation reopening`

This research reconciles the accepted Modelo 145 foundation ADR, the Apex R22
deferral, current official AEAT/BOE facts, and the current registry shape. The
goal is to decide whether and how Modelo 145 scope can be reopened without
inventing live submission, compatibility shims, placeholders, or fake support.

## Findings

### Official AEAT and BOE facts

- AEAT G603 describes Modelo 145 as an IRPF communication of withholding data
  to the payer or a variation of previously communicated data. AEAT says it does
  not require presentation before the tax administration; the payer must keep a
  copy available to the tax administration. Source URL:
  https://sede.agenciatributaria.gob.es/Sede/procedimientos/G603.shtml

- The same G603 page says the place of presentation is before the payer, the
  resolution body does not apply, and the phases section says it is not an
  Agencia Tributaria procedure and therefore does not require presentation or
  processing by the natural person before the tax administration. The page was
  updated on 2025-02-19. Source URL:
  https://sede.agenciatributaria.gob.es/Sede/procedimientos/G603.shtml

- The AEAT obligations-retainer page for Modelo 145 says the declaration's
  specific characteristics do not allow electronic procedures and that the
  model is processed by the interested person before the payer of the
  remuneration. The page was updated on 2026-03-16. Source URL:
  https://sede.agenciatributaria.gob.es/Sede/irpf/retenciones-ingresos-cuenta-pagos-fraccionados/retenciones-ingresos-cuenta/obligaciones-retenedor/modelo-145.html

- BOE-A-2008-20487 did approve a Modelo 145 communication model, but the BOE
  page marks that disposition as derogated. It remains useful historical legal
  context, not the current primary approving authority. Source URL:
  https://www.boe.es/buscar/doc.php?id=BOE-A-2008-20487

- AEAT G603 currently names BOE-A-2011-208, the Resolution of 2011-01-03, as
  basic regulation approving Modelo 145. A reopened implementation should treat
  the 2011 resolution and later amendments as current legal authority, with the
  2008 resolution only as historical context if retained. Source URL:
  https://www.boe.es/diario_boe/txt.php?id=BOE-A-2011-208

- The current AEAT Spanish form PDF is a two-page Modelo 145 form for
  communication to the payer under article 88 of the IRPF regulation. It is a
  form surface for the payer communication, not an AEAT filing receipt. Source
  URL:
  https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G603/mod145_es_es.pdf

- AEAT `dr145v20.pdf` is a one-page record design, dated 2012-01-31 and marked
  version 2.0, for Modelo 145 withholding-on-work-income communication data. It
  provides fixed-position fields starting with the `<T145010>` model/page
  identifier and continuing through personal, family, disability, pension, and
  housing-payment fields. Source URL:
  https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/archivos/dr145v20.pdf

### Existing project decision state

- The accepted 2026-05-12 Modelo 145 foundation ADR correctly states the core
  domain fact: Modelo 145 is a communication to the payer, retained by the
  payer, and not presented to AEAT through the filing lifecycle.

- That ADR's implementation section is now too broad unless amended: it says
  `app modelo` creates, verifies, exports, and marks the communication completed
  for local records. Current AEAT facts support local creation/export/retention
  semantics, but they do not support a `file` lifecycle or any AEAT electronic
  tramite.

- The Apex closure state later superseded the active implementation plan for
  R22. The W51 baseline records no Modelo 145 implementation, no registry TOML,
  no backend service, no CLI service, no shim, no stub, and no tests. W51 plan
  rows `S1501` through `S1530` are checked as deferred-baseline verification,
  not as shipped Modelo 145 behavior.

- The current plan still says Modelo 145 must not be implemented from stale W51
  rows until a successor ADR reopens scope. This research can support such a
  successor ADR, but does not itself reopen implementation authority.

### Current code and registry shape

- `registry/aeat/modelos/145.toml` is absent. `registry/aeat/modelos/036.toml`
  exists as the active census foundation. There is no active `037.toml`; tests
  assert Modelo 037 is historical catalogue metadata and cannot revive active
  support.

- The registry schema supports modelo cadence values `monthly`, `quarterly`,
  `annual`, `ad_hoc`, and `profile_based`. It does not currently have an
  explicit `communication` or `non_filing` cadence.

- The current registry vocabulary includes `filing_schedules`,
  `deadline_windows`, `application_links`, `live_cross_references`,
  `workbook_parity_refs`, `verification_expectations`, `extraction_profiles`,
  `export_layouts`, `constructs`, and `support_removal_decisions`. Several
  names are filing-oriented even when they can technically hold ad hoc or local
  workflow metadata.

- `ApplicationLinkDefinition.surface` is constrained to known surfaces such as
  `calculation`, `export`, `filing`, `verification`, `extractor`, `review`,
  `approval`, `reconciliation`, `deadline`, `workflow`, and `portal`. There is
  no first-class `communication`, `retention`, or `payer_delivery` surface.

- Committed registry examples expect source authority to be recorded in
  `registry/aeat/legal/*.toml`, with local corpus files and verified checksums.
  Modelo 036 uses `aeat-dr-036-2025` as layout authority and
  `aeat-modelo-036-procedure` as official source guidance. A Modelo 145
  implementation should follow that pattern with new source entries for G603,
  the obligations-retainer page, `mod145_es_es.pdf`, `dr145v20.pdf`, and
  current BOE authority.

- The current validator enforces source and legal catalogue integrity,
  application-link consistency, formula/source tiers, extraction target
  consistency, and support-removal consistency. A partial Modelo 145 TOML that
  lacks corpus-backed source entries, declares filing-grade surfaces, or points
  at non-existent parsers/export fields would be rejected or would encode the
  wrong semantics.

## Design Implications

- Reopening Modelo 145 is safe only as a non-filing communication foundation.
  It must not add live AEAT presentation, electronic tramite, document
  submission, declaration submission, payment, amendment, or filed-declaration
  read surfaces.

- The reopened design should amend or supersede the accepted 2026-05-12 Modelo
  145 foundation ADR. The successor ADR should explicitly state that the old
  "file" vocabulary is not valid for 145, and that completion means local
  communication/export/retention status, not AEAT filing.

- The registry can probably represent Modelo 145 with current primitives, but
  only with careful naming: `cadence = "ad_hoc"` or `profile_based`, a
  year-based/event-like `period_selector`, form fields as bound/manual
  casillas, and export layout from `dr145v20.pdf`. It should omit
  `filing_schedules`, `deadline_windows`, `live_cross_references`, and any
  `filing` application link unless the schema first gains non-filing
  vocabulary.

- If product scope requires visible CLI behavior, it should be exposed through
  backend-owned services under communication language such as create, verify,
  export, complete, and record payer delivery. It should not use `file`, should
  not transition to `filed`, and should not write events named as AEAT
  presentation.

- The cleanest long-term registry shape is to add first-class non-filing
  vocabulary before shipping 145: a lifecycle class or construct kind for
  `payer_communication`, application link surfaces such as `communication` or
  `payer_delivery`, and bucket event names that do not overload filing events.
  That avoids forcing a payer communication into filing-shaped fields.

## Recommended Decision

Reopen Modelo 145 only through a successor ADR that narrows the foundation to a
local payer-communication workflow. The ADR should supersede the active parts
of the 2026-05-12 Modelo 145 foundation ADR and the Apex R22 deferral for
Modelo 145 only after it states these constraints:

- Modelo 145 is not an AEAT filing and is not electronically tramitado through
  AEAT.
- The app may model, validate, export, and retain the communication record for
  the operator and payer.
- The app must not implement AEAT live submission, presentation, payment,
  amendment, declaration-read, document-submission, shims, stubs, or fake
  support for Modelo 145.
- Current BOE authority should be based on BOE-A-2011-208 and amendments, with
  BOE-A-2008-20487 recorded only as historical/derogated context if needed.
- Registry/source entries must be backed by official AEAT/BOE corpus files and
  checksums before tests assert filing-grade source coverage.

## Concrete Implementation Scope

1. Research-backed source corpus:
   add local corpus copies and source catalogue entries for AEAT G603, the AEAT
   obligations-retainer Modelo 145 page, `mod145_es_es.pdf`, `dr145v20.pdf`,
   BOE-A-2011-208, and relevant amendments. Record BOE-A-2008-20487 only as a
   derogated historical source if the ADR needs to explain lineage.

2. Registry foundation:
   add `registry/aeat/modelos/145.toml` only after the successor ADR. Model it
   as non-filing: no `filing` application link, no `deadline_windows`, no
   `filing_schedules` unless schema vocabulary is amended, no
   `live_cross_references`, and no portal read/write links. Use `dr145v20.pdf`
   for export layout and `mod145_es_es.pdf` plus BOE authority for field and
   legal grounding.

3. Schema vocabulary, if needed:
   prefer a small schema extension for non-filing communication semantics over
   overloading filing constructs. Candidate additions are a communication
   lifecycle class, `payer_communication` construct classification,
   `communication` or `payer_delivery` application-link surfaces, and
   non-filing bucket event states.

4. Backend service:
   add backend-owned application/domain service behavior for create, validate,
   export, and mark-local-completed or mark-delivered-to-payer. The service must
   be real behavior backed by registry data and persistence, not a placeholder.

5. CLI exposure:
   expose only thin CLI delegation after backend behavior exists. Use language
   that cannot be read as AEAT submission. Do not add `file` aliases,
   compatibility shims, deprecated spellings, or special CLI-local validation.

6. Tests:
   add real-behavior tests for registry loading, official source integrity,
   export layout against `dr145v20.pdf`, local workflow state transitions, and
   negative assertions that Modelo 145 has no AEAT filing, live submission,
   deadline, portal, shim, or stub surface.
