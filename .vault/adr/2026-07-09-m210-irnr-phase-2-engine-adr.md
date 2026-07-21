---
tags:
  - "#adr"
  - "#m210-irnr-phase-2-engine"
date: '2026-07-09'
related:
  - "[[2026-06-04-m210-irnr-phase-2-engine-research]]"
  - "[[2026-05-27-m210-irnr-full-engine-adr]]"
  - "[[2026-06-30-convenio-doble-imposicion-adr]]"
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
superseded_by: '2026-07-10-m210-irnr-phase-2-engine-adr'
modified: '2026-07-17'
---
# `m210-irnr-phase-2-engine` adr: `Phase 2 registry design, grounding strategy, and slice decomposition` | (**status:** `superseded`)

## Problem Statement

Phase 1 shipped a working M210 IRNR engine baseline: 13 casillas, the TRLIRNR
Art 24 base + Art 25 rate composition chain, the Art 25.1.b pension tariff,
Art 25.1.f interest/ganancia rows, the Art 13.1.h imputed-real-estate branch,
and treaty dispatch - since generalised by the convenio-doble-imposicion
framework (`registry/aeat/treaties/`, `ConvenioAuthority`, `TipoRentaIrnr`,
`ConvenioOverrideKind`; four treaties: ES-AR, ES-DE, ES-GB, ES-MA). Phase 2 was
deferred as "full diseno de registro (~80 casillas x 12 tipo-de-renta variants),
~92-country Convenios roster, agrupacion anual per Orden HAC/56/2024" - one
monolithic design-gated wave (`W01` of the Phase 2 sub-plan; step `W09.P41.S397`
of the cross-domain-continuity plan). This ADR converts that monolith into
decided structure, an honest bundled-vs-needs-fetch grounding map, and
executable slices.

## Considerations

- **What is bundled (verified against the shipped corpus).** The base order
  Orden EHA/3316/2010 consolidated (`orden-eha-3316-2010.html`, 249 KB, source
  `boe-modelo-210-base-order`); Orden HAC/56/2024 / BOE-A-2024-1772
  (`orden-hac-56-2024.html`, source `boe-modelo-210-2024-form-layout`), whose
  Articulo cuarto amends EHA/3316/2010 with the agrupacion rules, periodo `0A`,
  codigo 35, and the plazo table; Orden HAC/623/2026 / BOE-A-2026-13573
  (`orden-hac-623-2026.html`, the 2027-onward M210 content change plus the 2026
  domiciliacion-plazo update); the full consolidated TRLIRNR
  (`trlirnr-rdleg-5-2004.html`); the AEAT Sede M210 instructions
  (`modelo-210-instrucciones.html`, 116 KB); the imputed-real-estate guidance
  page; and four CDI article excerpts (AR-1992, DE-2011, GB-2013, MA-1978).
- **What is NOT bundled (verified absent).** (1) The complete official M210
  field enumeration: the bundled instructions reference only a casilla subset
  (5, 6, 9, 10, 11, 12, 25, 31 by grep) and the consolidated EHA/3316/2010 HTML
  carries no annex field tables. (2) All CDI texts beyond the four excerpts:
  roughly 88 of the ~92 Convenios Espana have zero corpus presence. Per the
  `legal-grounding-verifies-bundled-authoritative-corpus` rule and the
  no-fabrication mandate, neither surface may be authored from memory.
- **The "12 variants" are dispatch values, not layouts.** The official
  tipo-de-renta axis is a numeric code list (bundled instructions and orden
  text show 01, 02, 27, 28, 29, 33, 35, ...). The form is ONE layout whose
  branches key on the declared code; the engine already dispatches on the
  conceptual `TipoRentaIrnr` enum. Modelling 12 parallel casilla schemas would
  duplicate the layout twelvefold.
- **Agrupacion anual is presentation/period semantics, not arithmetic.** The
  bundled HAC/56/2024 text fixes: grouping requires same tipo-de-renta code,
  same pagador (waived for arrendamientos, which take codigo 35 when several
  pagadores), same tipo de gravamen, and same bien/derecho; grouped rentas
  never offset each other; the grouping period is quarterly for a-ingresar,
  annual for cuota-cero/devolucion, and annual for arrendamientos; a-ingresar
  plazos are the first 20 natural days of April/July/October/January, and for
  agrupacion anual the first 20 days of January of the following year.
- **Existing period and deadline machinery.** `Period.contains()` is the single
  boundary authority; M210 cadence is `ad_hoc` today; the deadline engine
  already carries per-modelo windows.
- **Revision-window discipline.** Each filing year must resolve to exactly one
  revision; the layout authorities are time-windowed (the HAC/56/2024 form
  entry applies 2024-02-01 through 2026-12-31; HAC/623/2026 content applies
  from 2027).

## Considered options

- **O1 registry shape: per-variant casilla schemas (12 sub-layouts).** Pro:
  mirrors the "12 variants" phrasing. Con: duplicates one official layout
  twelve times, invites copy drift, contradicts how the engine already branches
  on `tipo_renta`. Rejected.
- **O2 registry shape (chosen): one casilla schema per revision + official
  tipo-de-renta code axis + code-conditional formulas/predicates.** Pro:
  matches the official form (one layout, code-keyed branches) and extends the
  shipped `m210_resolve_base_imponible` branching pattern. Con: per-code
  casilla applicability must be expressed as verification predicates rather
  than layout structure. Accepted.
- **O3 tipo-renta axis: replace `TipoRentaIrnr` with raw official codes.** Pro:
  one axis. Con: destroys the treaty/rate keying `ConvenioAuthority` and the
  baseline table already use; official codes are many-to-one onto rate
  concepts. Rejected.
- **O4 tipo-renta axis (chosen): add the official numeric code as declared
  registry data with a registry-authored code-to-`TipoRentaIrnr` projection
  (each code row citing its EHA/3316/2010 / instructions grounding); unmapped
  codes refuse loudly at registry build.** Pro: the operator declares the
  official code the form asks for; the rate machinery keeps its conceptual key;
  the mapping is gate-checkable registry data, extendable code-by-code as each
  is grounded. Con: two related axes to hold in parity - mitigated by a
  registry-build parity gate. Accepted.
- **O5 roster: author the ~92-country Convenios roster as one wave.** Rejected:
  ~88 treaties need per-treaty BOE fetches; a bulk wave either fabricates rates
  or stalls the campaign (the convenio ADR already rejected this as its
  Option 4A).
- **O6 roster (chosen): demand-driven per-treaty enrolment tranches.** Each
  treaty = one named BOE fetch, corpus file, legal entries, one
  `treaties/es-XX.toml`, and a parity test, prioritised by non-resident filer
  volume. The roster is an enrolment CONTRACT, not a step. Accepted (ratifies
  the convenio ADR D4 for Phase 2).
- **O7 agrupacion: model agrupacion anual as a new aggregation mechanism.**
  Rejected: no new value channel exists; it is a period/plazo/grouping-validity
  concern, and the aggregation-taxonomy discipline forbids a new mechanism
  without a taxonomy row.
- **O8 agrupacion (chosen): period token + deadline windows + grouping-validity
  predicates.** Add the M210 period token `0A` (agrupacion anual) beside 1T-4T
  on the canonical period grammar, declare the HAC/56/2024 plazo windows in the
  deadline engine, and enforce the grouping-validity rules as registry
  verification predicates over the declared rows. Accepted.
- **O9 revisions: retro-author a 2024 revision now.** Rejected: no persona or
  campaign requires M210 filing year 2024; it duplicates the 2025 work without
  a consumer. The window map stays: revision `2025` under the HAC/56/2024
  layout; a `2027` revision is authored when HAC/623/2026 content applies.

## Constraints

- **NEEDS-FETCH 1 (gates the full casilla schema):** the official complete M210
  field enumeration. Named artefacts: the AEAT Sede "Disenos de registro -
  modelo 210" document for the current campaign
  (sede.agenciatributaria.gob.es, Ayuda > Disenos de registro > Modelos 200 al
  299) and/or the official M210 form specimen PDF from the Sede M210 procedure
  page. Until one is fetched and bundled as a `layout_authority` source, only
  the instructions-groundable casilla subset may be authored. The "~80
  casillas" figure itself is unverified against any bundled authority and MUST
  be re-derived from the fetched document, never assumed.
- **NEEDS-FETCH 2 (gates each roster tranche):** the per-treaty BOE
  consolidated convenio text; each tranche names its exact BOE ids at fetch
  time from the AEAT Convenios bibliography. No treaty row ships without its
  corpus text.
- **BUNDLED-SUFFICIENT:** the tipo-de-renta official code list, the agrupacion
  rules and periodo `0A`, the plazo windows, the TRLIRNR rate/base law, and the
  2027 dividend-refund content change are groundable from the shipped corpus
  today.
- **Parent stability:** the Phase 1 engine, `ConvenioAuthority`, and the typed
  unresolved-outcome channel are landed and test-pinned; this ADR adds no
  parallel path.
- **Numeric amounts and rates** cross-check live BOE/AEAT even when bundled,
  per the corpus-verification rule.

## Implementation

Slices ordered by grounding availability; each is independently landable.

**Slice A (bundled-groundable now) - official tipo-de-renta code axis.** Author
the official code list as registry data on the 2025 revision (each code row
citing the bundled EHA/3316/2010 / instructions text), with the
code-to-`TipoRentaIrnr` projection and a registry-build parity gate (every
declared code maps; unmapped codes refuse at build). The CLI declares the code
as a typed Choice; the conceptual enum stays the rate key.

**Slice B (bundled-groundable now) - agrupacion anual.** Period token `0A` on
the canonical period grammar scoped to M210; HAC/56/2024 plazo windows in the
deadline engine (a-ingresar quarterly 1-20 Apr/Jul/Oct/Jan; agrupacion anual
1-20 Jan; arrendamiento annual-only); grouping-validity verification predicates
(same code / same pagador save codigo 35 / same gravamen / same bien; no
offsetting between grouped rentas) grounded in the bundled Articulo cuarto
text.

**Slice C (fetch-gated) - full casilla schema.** Fetch NEEDS-FETCH 1, bundle it
as a `layout_authority` source, then author the complete casilla set on the
2025 revision with completeness manifest, extraction-profile targets, and
export parity per the official-structure export rule. Casilla count and
numbering come from the fetched document.

**Slice D (fetch-gated, repeating) - Convenios roster tranches.** Tranche N =
fetch the named BOE convenio texts, author corpus + legal entries +
`treaties/*.toml` rows keyed by `TipoRentaIrnr` with typed
`ConvenioOverrideKind`, and pin continuity parity tests. First tranche
proposal: FR, PT, US, NL, BE (high non-resident filer traffic); subsequent
tranches enrol without framework change.

**Slice E (2027, deferred until the filing year approaches) - HAC/623/2026
revision.** Author revision `2027` carrying the bundled dividend-refund control
fields; the 2026 domiciliacion plazo update folds into the Slice B deadline
windows.

## Rationale

The through-line is grounding-honesty: every sub-decision splits what the
shipped corpus proves today (code axis, agrupacion semantics, plazos, rates)
from what requires named fetches (the full field layout, ~88 treaties), so no
slice waits on a blocker it does not need and no step invites fabrication.
O2/O4 follow the form's real shape (one layout, code-keyed branches) and
preserve the landed treaty/rate keying. O6 ratifies the already-accepted
enrolment-contract pattern rather than re-deciding it. O8 places agrupacion in
the period/deadline/predicate machinery that already has single-authority
rules, avoiding a new aggregation mechanism the taxonomy discipline would have
to bless.

## Consequences

- **Gain:** `S397` stops being one design-gated monolith; Slices A and B are
  executable immediately from bundled corpus, and the fetch-gated slices carry
  named artefacts instead of vague "full diseno" language.
- **Gain:** the official code axis makes the operator-facing surface match the
  real form while leaving the treaty framework untouched.
- **Cost (accepted):** two related income-type axes (official code, conceptual
  enum) held together by a parity gate.
- **Cost (accepted):** the casilla-count claim (~80) stays unverified until
  NEEDS-FETCH 1 lands; Slice C scope is fixed by the fetched document.
- **Bounded:** the M216 withholding consumer, PE thresholds, and bulk roster
  authoring stay out of scope, per the convenio ADR.
- **Ownership:** all Phase 2 slices live in the `m210-irnr-phase-2-engine`
  sub-plan; cross-domain-continuity `W09.P41.S397` reduces to a tracking
  pointer that closes when the sub-plan's Slice A+B phases close.

## Code-surface footprint

- `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2025/` (casillas,
  parameters, verification_expectations, completeness manifest; Slices A/B/C)
- `src/cadrumo/_data/registry/aeat/treaties/` plus
  `src/cadrumo/_data/registry/aeat/legal/irnr.toml` plus
  `src/cadrumo/_data/corpus/normatives/html/` (Slice D tranches)
- `src/cadrumo/core/_irnr.py` (official-code axis projection; Slice A)
- the canonical period grammar home in `src/cadrumo/core/` (token `0A`; Slice B)
- `src/cadrumo/domain/deadlines/` (M210 plazo windows; Slice B)
- `src/cadrumo/domain/calculations/registry/_formula_runtime_irnr.py` plus
  `_validate_revision_rules.py` (code-conditional dispatch + parity gate;
  Slice A)
- `src/cadrumo/application/modelo/_m210_rate.py` plus
  `_verification_predicates.py` (grouping-validity findings; Slice B)
