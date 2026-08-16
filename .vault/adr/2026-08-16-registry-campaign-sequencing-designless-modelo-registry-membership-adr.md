---
tags:
  - '#adr'
  - '#registry-campaign-sequencing'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:ae3abbae68dae67c8505043dadd2a7eadff2e39e5bfd55e0483d061083c22709'
related:
  - "[[2026-08-14-registry-campaign-sequencing-adr]]"
  - "[[2026-08-16-registry-temporal-coverage-designless-modelo-adjudication-audit]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace registry-campaign-sequencing with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, superseded, or deprecated. A new ADR starts as proposed; it
     moves to accepted or rejected when the decision is made; it becomes
     superseded when a later ADR replaces it (set by vault adr supersede,
     which also records superseded_by); and deprecated when it is retired
     without a direct successor.

     Amend vs supersede: refinements and concretization rewrite the accepted
     record's body in place (modified: carries the revision); a new ADR with
     supersession is only for a major pivot. One accepted record per
     decision.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `registry-campaign-sequencing` adr: `registry membership requires an AEAT-published machine filing format` | (**status:** `accepted`)

<!-- DOCUMENT BOUNDARY:
     This record owns the decision and only the decision. Grounding evidence
     lives in the related research/reference documents and is cited by stem
     (e.g. `2026-02-04-editor-demo-research`), never restated - a restated
     fact forks and goes stale. A fact this record needs but the grounding
     lacks is added to the grounding first, then cited. -->

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
- `UNMODELED_OBLIGATIONS` may not be populated by this work. Its human tax-review
  gate is a deliberate refusal to infer a taxpayer duty from a form's absence,
  and the taxpayer-facing subset below is exactly the population that gate exists
  for. This record identifies the candidates and stops.
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

**Group W — identified, deliberately not decided (eight).** M121, M136, M140,
M143, M361, M380, M721, M848 are live, taxpayer-facing, and web-form-only. They
are the population `UNMODELED_OBLIGATIONS`'s human tax-review gate governs.
This record names them and hands them to that gate; it does not populate the
mapping and does not delete their definitions.

Group W leaves the registry red until that review lands. That is the parent
ADR's intended behaviour and is not worked around here.

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

- The 48-revision refusal list loses eight entries by relocation and one by
  retirement, and the remaining excluded eight are named with an owner. The 31
  revisions with bundled designs are unaffected: their answer was always to
  author the layout, and this record does not soften that.
- `core/_modelo.py` gains eight mapping entries and loses eight registry
  directories. The obligation-coverage reconciliation continues to account for
  every one, moving them from *surfaced* to *out of scope* with a stated reason
  rather than dropping them.
- Real authored grounding is deleted with the Group R directories — deadline
  windows and legal citations for eight modelos. This is a genuine loss and the
  reason relocation is per-modelo and reversible from git rather than a sweep.
- The XSD channel question is deferred, not answered. If the product later
  commits to rendering DAC-family submissions, Group R members return to the
  registry, and that return is a normal enrollment rather than an exemption
  being revoked.
- Group W is a standing red. Anyone tempted to clear it should read the parent
  ADR's rejected-options section first.
