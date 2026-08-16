---
tags:
  - '#adr'
  - '#registry-campaign-sequencing'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:6163bab1bbe30f81a05fb805b412a81f876a5bbb8c6189bac2bc9fe8e824d90e'
related:
  - "[[2026-08-14-registry-campaign-sequencing-adr]]"
  - "[[2026-08-16-registry-temporal-coverage-designless-modelo-adjudication-audit]]"
---

# `registry-campaign-sequencing` adr: `registry membership requires an AEAT-published machine filing format` | (**status:** `accepted`)

## Problem Statement

`2026-08-14-registry-campaign-sequencing-adr` rules that registry build refuses
any revision declaring no export layout, unconditionally, with no allowlist and
no per-modelo carve-out. That decision stands and is not reopened here.

It was reasoned entirely over revisions whose layout *could* be authored — its
worked cases (303, 200, 390) had real export layouts in git history that a
2026-08-11 sweep had withdrawn. It never contemplated a revision for which no
layout can ever be authored because AEAT publishes no record design for that
modelo at all.

`2026-08-16-registry-temporal-coverage-designless-modelo-adjudication-audit`
establishes that seventeen modelos are in exactly that position, confirmed
against all five current AEAT Diseño de Registro index pages and all four
`ejercicios anteriores` pages. For these, the refusal is unanswerable as posed:
authoring is impossible, and the only currently-available action that clears it
— deleting the definition — reads as asserting the form does not exist, which is
false for sixteen of them.

The decision needed is not an exemption. It is what registry membership *means*.

## Considerations

- The parent ADR's rejection of allowlists is a rejection of a mute button, not
  of a membership criterion. A criterion applied uniformly is the opposite of a
  carve-out: it admits and excludes by a stated property, and the exclusion is
  visible in a different structure rather than silenced in place.
- `core/_modelo.py` already carries the vocabulary this needs, and already
  applies the criterion this record generalises. `_UNMODELED_OUT_OF_SCOPE_
  OBLIGATIONS` holds recognized AEAT obligations with no registry definition,
  each with a recorded reason, and `NON_REGISTRY_MODELOS` unions it so the
  registry-parity gate does not read the absence as drift.
- That mapping is already inconsistent in a way this record resolves rather than
  creates. M290 (FATCA, financial institutions) sits there while its structural
  twin M289 (CRS/DAC2, the same institutions, the same XSD channel) carries a
  registry definition. M235 and M236 sit there reasoned as "complementa el
  Modelo 234, filers especializados" while M234 itself, their parent, carries a
  registry definition. M172 and M173 (monedas virtuales, declared by providers)
  sit there. The criterion is already ratified; its application is partial.
- The audit's channel evidence splits the seventeen by *who files* and *what AEAT
  publishes*, and those two axes decide different things. Filer decides product
  scope; published format decides whether a filing artefact is constructible.
- `UNMODELED_OBLIGATIONS` is documented as intentionally empty, with an explicit
  standing gate: adding a member asserts a taxpayer bears a filing duty, which
  "is a TAX REVIEW against official BOE and AEAT sources, per entry, with human
  reviewer sign-off". That gate is load-bearing and is honoured below.
- The application never submits to AEAT (`sensitive-financial-data-secure-
  storage-only`): it builds, validates and exports, and a human files outside
  it. For a modelo AEAT accepts only through a web form, there is no artefact to
  build — the human transcribes. That is a genuine absence of the product's unit
  of work, not a missing feature.

## Considered options

- **Extend `ExportLayoutFormat` with a web-service/XSD member (rejected, for
  now).** Correct eventually for the DAC-family modelos, which do have a
  machine format. Rejected as the answer *here* because it does not address the
  web-form-only modelos at all, and because
  `2026-08-15-registry-temporal-coverage-structural-decisions-audit` shows the
  existing `xml_dictionary` renderer branches on `draft.modelo == Modelo.M100`
  at four points, so the second format member is Modelo 100's format with a
  general name. Generalising it is prerequisite work, not this decision.
- **Add a declared "no published fixed-width design" state the export-exemption
  validator accepts (rejected).** This is the shape the adjudication audit
  named as plausible, and it is an allowlist wearing a citation. The parent ADR
  rejected precisely this, and its reasoning holds: a declarable absence lets an
  eighteenth entry slip in the way the first nine withdrawals did.
- **Delete all seventeen registry definitions outright (rejected).** Clears the
  refusal but destroys real authored grounding — deadline windows, applicability,
  legal citations — and for the taxpayer-facing subset removes the obligation
  from the operator's view entirely, which is under-declaration by omission.
- **Make registry membership conditional on an AEAT-published machine filing
  format, and relocate the excluded modelos into the existing recognized-
  obligation vocabulary, partitioned by filer (chosen).** Uniform criterion, no
  per-modelo exemption, obligation stays visible, parent ADR untouched.

## Constraints

- The parent ADR is `accepted` and is not superseded or amended by this record.
  This record narrows what the registry *contains*; the parent governs what a
  revision inside it must declare. Both hold simultaneously.
- `UNMODELED_OBLIGATIONS` stays EMPTY. Enrolling M721 there was tried and
  reverted: the mapping asserts a duty the application does not model, and M721
  is modelled — it has foreign-asset threshold and redeclaration resolvers and a
  cross-year E2E fidelity suite. The gate held; what it caught was a
  misclassification, not a missing signature.
- A modelo's calculation machinery is part of the membership question, not a
  detail of it. Deleting a definition deletes formulas, resolvers and their
  tests, so "no published design" is necessary but not sufficient for
  relocation.
- Relocation is not free of blast radius: `NON_REGISTRY_MODELOS` membership makes
  `validate_modelo` raise, and the core parity gate binds the enum's registry-
  backed members to `application.modelo.registry_modelo_codes`. Each relocation
  is a registry-tree deletion plus an enum mapping entry plus a parity-gate
  re-run, landed together.
- Modelo 179 is a different case that must not be folded in: it was legally
  abolished for ejercicio 2024 onwards, which is the `Modelo.M037` shape, and its
  open-ended revision span is a factual error independent of this decision.

## Implementation

A modelo earns a registry definition when AEAT publishes a machine-readable
submission format for it — a diseño de registro, or an XSD/WSDL the product
commits to rendering. Absent both, the modelo is a recognized obligation, not a
registry modelo, and it lives in the `core/_modelo.py` obligation vocabulary
with its recorded reason.

The seventeen partition into three groups by the two axes above.

**Group R — relocate now (eight).** Filed by third parties or by specialised
filers a general autónomo, PYME or entity never is, matching the criterion
`_UNMODELED_OUT_OF_SCOPE_OBLIGATIONS` already applies: M186 (registros civiles),
M231 (CbC, large multinational groups), M233 (guarderías), M234 (DAC6, joining
its own M235/M236 siblings), M238 (DAC7 platform operators), M289 (CRS/DAC2,
joining its M290 FATCA twin), M379 (CESOP, payment service providers), M592
(envases de plástico, sector filers, joining the impuesto-especial family).
Each gets a Spanish-language reason line in the existing style, the registry
definition is deleted, and the enum mapping carries the obligation forward.

**Group S — retire (one).** M179, abolished for 2024 onwards and replaced by
M238. This is the `Modelo.M037` treatment: the form ceased to exist in law, so
the registry definition is deleted and the enum records the suppression and its
successor. Bounding its `2021-y-siguientes` span is therefore moot and is not
done — that fix would only apply had the modelo stayed in the registry, and
recording it as a live-through-2023 revision the application still cannot file
would reintroduce the exact state this record removes.

**Group W — resolved, and it split in two.** The eight live web-form-only
modelos were reviewed per entry against official AEAT and BOE sources, and they
do not share one answer.

*Relocated (six),* each out of scope by filer or by election rather than by
format: M121, M140 and M143 are elective IRPF deduction trámites resolved in the
annual campaign, not standing obligations; M361 serves empresarios **no
establecidos** in the TAI, confirmed from its own bundled procedure page, so a
Spanish-established filer never files it; M380 covers LIVA art. 19 abandonment
of the arts. 23/24 regimes — zonas francas and depósitos distintos del aduanero
— which is sector-operator territory; M848 is filed only by IAE-liable
non-exempt taxpayers and only when the INCN is not already reported through IS,
IRNR or M184, and AEAT accepts it in person or by post with no electronic file
at all.

*Kept (two), and this is the category this record did not anticipate.* M136 and
M721 have no published design either, but both carry real calculation
machinery the application exercises: M136 declares base-imponible,
cuota-gravamen-especial and resultado-a-ingresar formulas; M721 has the
foreign-asset threshold and cross-year redeclaration resolvers, the €50,000 and
€20,000 art. 42-quater thresholds, and a two-cycle E2E data-fidelity suite.
Relocating them would delete working, tested capability in order to record an
absence — a strictly worse outcome than the red they cause.

So the criterion needs its second half stated: a modelo leaves the registry when
AEAT publishes no machine-readable format **and** the application has no
modelled capability that would be destroyed by its removal. M136 and M721 are
**calculate-capable but unfileable**.

**The no-layout refusal is therefore scoped, and this does narrow the parent
ADR.** Its condition becomes "declares no export layout AND AEAT publishes a
record design for this modelo". The parent's refusal instructs the reader to
"author the revision's export layout from its official record design"; where no
such design exists the instruction is not a task but an impossibility, so the
refusal would stand forever and carry no information.

This is not the declarable exemption rejected above, and the difference is
mechanical rather than rhetorical. The condition is a property of the source
catalogue — does any source this modelo cites carry `kind = "record_design"` —
not a field a revision author sets. No revision reaches the quiet side by
declaring anything. Over the bundled corpus the property separates exactly two
modelos from the other forty-six, and that partition was measured before the
change was written, not asserted after it.

**One residual escape is open, and it is named rather than papered over.** A
modelo could in principle reach the quiet side by citing no record-design source
at all. The structural answer to that is
`test_every_bundled_record_design_is_registered`, which refuses a bundled design
no source registers — but that gate is currently RED on 97 of 218 bundled files,
across modelos untouched by this work (714, 390, 200, 190, 180 and others), so a
new omission would land in existing noise rather than stand out. The escape is
therefore guarded in principle and not in practice today. Closing it means
fixing that registration backlog, which is its own acquisition-and-authoring
task and is not folded into this decision. Recorded here so the guarantee is not
read as stronger than it is.

The predicate is deliberately read at MODELO scope, across every revision, not
at revision scope. M185 forced that: its 2026 design is bundled while its
`2003-2025` revision cites none, and a per-revision reading quietly excused that
epoch — which is an ACQUISITION gap, the exact shape the refusal exists to
surface. Modelo scope keeps it red. A `form_spec` does not count either: M721
cites its approving orden's anexo at `layout_authority` tier under an id ending
`-layout`, and keying on tier or name rather than kind would have made the whole
distinction fictional. Both of those are pinned by tests that fail if the
predicate drifts to the weaker reading.

## Rationale

The knockout is that the parent ADR's rejected option and this one differ in
kind, not degree. It rejected recording "cannot file" as a *property of a
revision that stays in the registry* — a worklist nobody is forced to consult.
This records "no machine format exists" as a *membership criterion*, which
removes the revision from the population the gate scans at all. The gate keeps
its unconditional teeth over everything it still sees, and it sees only modelos
for which a filing artefact is constructible. Nothing is declared unfileable
while remaining nominally fileable, which was the exact confusion the parent
closed.

The criterion is not invented for this problem. Applying it to Group R makes
`core/_modelo.py` more internally consistent than it is today, resolving three
standing asymmetries (289/290, 234/235/236, and the virtual-currency pair)
that exist only because enrollment was partial.

Refusing to decide Group W is the honest half of the record. The alternative —
asserting these eight are out of product scope so the tree goes green — would
decide by convenience a question the codebase already marks as requiring human
tax review, and would withdraw obligation advice from taxpayers who genuinely
owe these filings.

## Consequences

- Measured against a real authority load, not estimated: registry validation
  failures fell from 137 to 108, and revisions refused for declaring no export
  layout fell from 48 to 32, across 43 modelos down to 27. Fifteen modelos left
  the registry; nothing was newly broken in either pass, and the failure-set diff
  was checked both times rather than inferred from the totals.
- `CANONICAL_MODELO_FLEET` derives from `NON_REGISTRY_MODELOS`, so the
  authorization denominator moved by construction, 73 to 58, with no list to
  edit. Its pinned assertion is a deliberate tripwire and was updated as the
  conscious decision it demands, with the reasoning added to its narrative.
- The 31 revisions with bundled designs are untouched. Their answer was always to
  author the layout, and nothing here softens that.
- Real authored grounding went with the relocated directories — deadline windows
  and legal citations, and for M289 twenty legal refs tracking thirteen amending
  ordenes. That is a genuine loss, recoverable from history, and the reason
  relocation is per-modelo rather than a sweep.
- The XSD channel question is deferred, not answered. If the product later
  commits to rendering DAC-family submissions, those modelos return by normal
  enrollment rather than by an exemption being revoked.
- M136 and M721 go green as calculate-capable, unfileable modelos, and the
  no-layout refusal now means something narrower and truer: *a design exists and
  the layout has not been authored*. Every one of the remaining refusals is
  actionable, which the previous reading could not claim.
- The scoping is a real narrowing of the parent ADR's unconditional refusal, and
  is recorded as such rather than presented as a clarification. What it does not
  narrow: the refusal keeps full force over all forty-six modelos with a
  published design, and no author-settable field can turn it off.
- The membership criterion generalises to any modelo AEAT moves off fixed-width,
  which is the direction of travel for the DAC and CESOP families. Enrollment
  now has a stated property to test rather than a precedent to match.
