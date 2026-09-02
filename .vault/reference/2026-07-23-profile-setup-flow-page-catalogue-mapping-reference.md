---
tags:
  - '#reference'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-09-02'
body_hash: 'sha256:c084ec821082bbd1e4403cd4443e72c2e53fdc68f74f74ae8b3fb05307c0ee6e'
related:
  - "[[2026-07-23-profile-setup-flow-adr]]"
---

# `profile-setup-flow` reference: `page catalogue mapping`

The FlowDefinition expression of the eight-phase setup spine: for every
page, which EXISTING source backs each copy slot, plus the domain
binding, widget, validator, and structural-page decisions. This is the
authoring map for the flow's FlowDefinition; the decisions it projects
live in the related ADR.

## Conventions (every page, unless a section below overrides)

- **domain_key** = the question's existing `profile_key`, unchanged.
  Page id = the existing question id, unchanged. Widget kind maps
  `WizardWidget` to `FlowWidgetKind` one-to-one, with
  TEXT-with-choices bridging to SELECT.
- **prompt / choice labels / failure copy** = the question's existing
  locale keys (`wizard.setup.<section>.<question>.prompt`, the choice
  `.label` keys, the typed `wizard.errors.*` widget-failure keys),
  carried as built-in LOCALE_KEY CopyRefs. No key renames: a moved
  question keeps its historical section prefix inside the key string
  (key strings are opaque identifiers).
- **help zone** = the existing `.help` locale key where one exists,
  plus the optional terminology concept reference (table below).
- **Copy-source registration** (multi-resolver registry: registration
  order, first-non-None wins, LOCALE_KEY built-in only): the flow
  registers two namespace-prefixed resolvers, each returning None for
  any ref outside its namespace —
  `profile-schema:<schema-path>` (the field's schema-declared
  description and legal_refs projection) and
  `profile-terminology:<concept_id>` (the approved Handbook fragment's
  locale-matched short description and definition). An unresolved or
  non-approved reference fails loudly at render, never silently blanks.
- **Legal zone** = derived, never authored: the per-page union of the
  field's `schema.toml` `legal_refs` and the
  `build_profile_grounding_index` entry for the page's profile key
  (consuming modelos plus binding legal_refs). A page absent from both
  renders no legal zone.
- **Validators**: per-answer = the existing widget validators, plus the
  `cadrumo.core.identity` authority on identity pages; section-scope
  and flow-scope = the re-homed `verify_setup_answers` checks (table
  below), registered by id via the substrate validator registries.
- **Checkpoint declaration** (strict, per-mode): CREATE available
  (CheckpointStore implemented over `ProfileLifecycleService` fact
  writes), MODIFY unavailable (declared no-op, loud save refusal).

## Phase structure

The eight FlowDefinition sections group the eight already-re-sequenced
wizard sections one-to-one — identidad, residence, actividad, iva,
enrollment, familia, obligations, preferencias — plus two structural
additions: the entrada routing page (engine-level, no domain_key) and
the phase-8 cotejo block before the substrate review surface.

## Concept zone (terminology references, approved-only)

| page | concept_id |
|---|---|
| `tax-id`, `spouse-tax-id`, descendant `nif` | `nif` |
| `activity-start-date`, `enrollment-large-company` | `censo` |
| cotejo intro page | `modelo-036` |
| `iva-regime` per-choice descriptions | `iva-regimen-simplificado`, `iva-recargo-equivalencia` |

Every other page carries no concept reference today. New concepts
(estimación directa/objetiva, situación familiar) enrol through the
Handbook scaffold when authored here; the assembler's approved-only
gate and loud unresolved-ref refusal police the set.

## Legal-zone hits (computed against the live index and schema)

Binding-derived — 21 pages, all via Modelo 100 bindings today:
`tax-id`, `name`, `surnames` (identidad); `irpf-income-categories`
(actividad); `taxation-type`, `taxpayer-sex`, `taxpayer-marital-status`,
`taxpayer-birth-date`, `taxpayer-disability-grade`,
`taxpayer-death-date`, the nine `spouse-*` pages,
`family-descendants-eu-eea-deduction`, and
`family-minor-children-in-unit` (familia). Schema-declared `legal_refs`
add at minimum the fiscal-address family (`rdleg-1-2004:art-6.3`;
`ley-35-2006:da-23` / `art-30`) and `censo.activity_start_date`
(`rd-1065-2007:art-9`). The two sources union per page at flow-compile.
31 further indexed profile keys have no wizard page (non-wizard facts);
they are out of the flow's scope by construction.

## Identity pages: format hints and failure modes

`tax-id`, `spouse-tax-id`, and the descendant `nif` page bind their
per-answer validator to `validate_identity` / `validate_spanish_tax_id`.
Format-hint CopyRefs and per-`IdentityDocument`-kind failure keys land
as new locale keys under `wizard.setup.identity-format.*` (scaffold
plus set through the locales CLI at implementation time); worked
examples ride the format hint, never hardcoded prose.

## Validator re-homing (`verify_setup_answers` to the registries)

| check | scope | placement rationale |
|---|---|---|
| spouse consistency (joint declaration demands the spouse NIF) | section exit, `familia` | inputs complete at phase exit; blocks forward navigation |
| joint taxation vs situación familiar (LIRPF art. 82) | section exit, `familia` | same |
| monoparental requires hijos | flow scope (review) | needs the descendant group, which review consolidates |
| obligations consistency | flow scope (review) | crosses the actividad, iva, and obligations sections |
| EU/EEA country requirement | per-answer on `spouse-eu-eea-country`, section backstop | the existing conditional-requirement pair |

## Descendants repeating group (net-new pages, familia phase)

Group id `descendientes`; instances are added and removed from the
review affordance (no count question). Instance pages (answers key as
`descendientes#i.<page>`): `birth-date` (required, date),
`adoption-date` (date, optional), `discapacidad` (SELECT 0/33/65),
`convivencia` (CONFIRM), `custodia-compartida` (CONFIRM),
`meses-madre-trabajo` (INTEGER 0-12), `gastos-guarderia` (INTEGER,
euros), `nif` (identity-validated, optional). At commit the instances
serialise exclusively through `descendant_facts_from_list` (aggregates
included), emitting exactly the documented
`renta_family.descendiente.{n}.*` paths the
`_minimo_descendientes_facts` injector consumes. Prompts and help are
new locale keys under `wizard.setup.descendientes.*`, authored via the
locales CLI.

## Cotejo censal pages (phase 8, before review)

- `cotejo-intro`: static page offering the artefact route; copy
  references name the Sede download path for the G313 certificate and
  the `config profile edit` manual fallback; concept reference
  `modelo-036`. Display-only certificate fields (condición de
  residencia, representantes, situación tributaria, obligaciones
  periódicas) render here as read-only evidence rows, never as
  compare-select candidates.
- `cotejo-artefact`: file-input page feeding
  `parse_certificado_censal_bytes`; while extraction is unpinned the
  registered parse refusal surfaces as the page's validation failure,
  and the page is skippable.
- Per reconcilable axis holding both an in-flow answer and an artefact
  candidate fact: one COMPARE_SELECT page — candidates are the staged
  answer and the artefact value, each with a provenance label; the
  explicit DEFER choice takes the substrate's deferred status AND
  persists a typed divergence fact at commit.

## Cotejo divergence facts (persisted shape)

A deferred compare-select decision persists as an effective-dated fact
in a repeatable schema section (the descendant family is the
precedent for indexed path families): path
`censo.divergencia.{n}.axis` (the schema path of the diverging fact),
`censo.divergencia.{n}.artefact_value` (the certificate's value,
stringified), `censo.divergencia.{n}.source` (the artefact provenance
token). The operator's retained answer stays at its own path — the
divergence rows record only the unadopted evidence. Profile read
surfaces raise one warning `Notice` when any divergence row exists
(constructed notice codes live under a dynamic translation root,
declared up front). Adopting the artefact value later — through the
flow or `config profile edit` — clears the row through the lifecycle
authority. Divergence rows ride the standard roundtrip discipline
(populated non-default fixtures, anti-tautology proof) and the
portable-export version check.

## Registered-values projection (modify column AND the complete-profile overview)

The review surface's overview presentation composes three existing
channels; the flow's entire contribution is the `registered_values`
mapping, so the projection is designed as the load-bearing piece:

- **Coverage**: every profile-bound page of the active record — not
  only changed pages — keyed by page key (identity projection:
  domain_key equals the fact path; descendant instances key as
  `descendientes#i.<page>`).
- **Display-ready strings, formatted at projection time** (the string
  IS the contract; the frontend renders, never formats): closed-set
  tokens resolve to their choice LABELS through the locale catalogue;
  booleans render as the localized yes/no pair; dates and decimal
  amounts render in the operator's display convention. Projection runs
  AFTER output-language activation (the ordering constraint above), so
  labels resolve in the operator's language.
- **No pre-masking**: secret pages are supplied normally — the review
  screen masks both staged and registered values via its widget-kind
  lookup, and a second masking authority on the projection side could
  only drift from it.
- **Nothing richer than the string**: no provenance column, no typed
  per-row payload — the eligibility authority stays the engine's
  ReviewProjection, untouched. The one provenance fact worth showing —
  a registered value derived from the G313 artefact is non-official
  evidence — is ENCODED INTO the display string as a localized suffix
  (keyed copy landing in the same commit as the projection that
  consumes it), applied when the underlying
  fact carries the artefact provenance token. A typed provenance
  channel is requested only if the suffix proves insufficient in use.

## Domain-construction validation at review (flow-scope)

`TaxpayerProfile`'s cross-field legal validators fire at model
construction, which happens in consumers after commit — so without a
review-time leg, a fact set that constructs an invalid `TaxpayerProfile`
would surface post-commit as a generic refusal. The flow therefore
registers one flow-scope validator, `taxpayer-projection-constructs`,
which runs `projection_for_taxpayer` over the staged answer set at
review, catches the construction `ValidationError`, and maps each
per-field error through the pydantic type/loc-to-key mapping into typed
verdict rows. The model validators stay the single authority — the flow
validator pre-runs the same construction rather than duplicating any
invariant — and submit eligibility blocks until it passes.

Wiring: `flow_validators.py` owns the single registry entry at import
time, and `setup_flow_definition` is the composition point — it applies
`attach_taxpayer_projection_validator` to the decorated definition
(before the descendant group, so only top-level pages enrol), which
enrols that definition's page-id → domain-key rows on the registered
validator and appends `taxpayer-projection-constructs` to
`flow_validator_ids`. This mirrors the sibling `attach_descendant_group`
shape; enrolment is idempotent, so re-composing the definition neither
duplicates the id nor re-registers the validator.

Review is the COMPLETE gate: the substrate never runs `answers_model`
validation (raw model errors are library prose), so this one re-run
validator is the coverage for every construction-time cross-field
invariant — one validator re-running the real constructor, never one
restated validator per invariant. Receipt tests pin the coverage at two
levels. Unit receipts drive each of the three named legal checks
(impatriado start date, non-resident country, representante fiscal)
through the registered validator and assert its typed verdict row.
End-to-end receipts walk the real projected setup definition through the
engine and assert that an impatriado election without its start date and
a non-EU/EEA non-resident without a fiscal representative each surface a
blocking verdict at review and refuse submission, while the same answer
sets completed legally stay submit-eligible. Mapped verdicts carry
catalogue KEYS plus redacted context only — the raw model message never
enters a verdict, since library prose is exactly the leak class the
mapping exists to eradicate.

Known limitation: the validator classifies WHICH invariant fired by
token-matching the pydantic message internally (the message is then
discarded). This fails safe — a model wording change collapses the
specific verdicts into the generic check, never a leak — but the
collapse is a silent UX regression. Sturdier discriminator when the
model side is next touched: dedicated exception subtypes or a stable
machine tag on each cross-field validator's error (pydantic custom
error `type`), matched by tag instead of prose; the receipt tests
already pin the three specific classifications, so a silent collapse
reds them.

## Checkpoint lifecycle (create mode)

Save is frontend-owned; COMPLETION-DISCARD IS DOMAIN-OWNED: the commit
path discards only after successful persistence, because the frontend
cannot observe domain persistence success and a frontend
discard-at-submit would destroy the operator's only copy on a
persist failure. Under facts-as-checkpoint this falls out structurally:
the facts ARE the checkpoint, `CheckpointStore.load` offers a resume
ONLY while the active profile's status is `SETUP_INCOMPLETE`, and the
phase-8 `complete_setup` transition — which runs strictly after
flow-scope validation and persistence — IS the completion discard (the
status flip ends resume-eligibility; there is no separate answer-map
artefact to erase). The `CheckpointStore.discard` arm serves explicit
operator abandonment: it erases the incomplete profile through the
lifecycle authority. A crash between persist and the status flip leaves
at worst a stale resume offer that re-validates against the current
definition.

## Mid-walk language activation (the answer-commit hook contract)

The activation wiring attaches to the frontends' per-commit observer
(`on_answer_committed(page_key, committed_value)`), under three binding
constraints:

- The hook fires after a SUCCESSFUL commit only and BEFORE the frontend
  advances, so a handler that re-activates the locale and calls
  `rebuild_for_locale()` renders the next page in the new language with
  no old-locale flash on the forward path — the two-locale render test
  verifies this rather than assuming it.
- The hook also fires per staged checkbox toggle: the handler keys on
  the language page id and ignores every other commit — reacting
  generically would re-activate and rebuild on every checkbox tick.
- The committed value can be SENSITIVE (secret pages fire the hook
  too): the handler never logs, echoes, persists, or places the raw
  value in any diagnostic context — the same discipline as
  `on_complete`, and a hard constraint on any implementation.

## Output-language activation (binding ordering constraint)

The substrate resolves all copy and verdict text lazily at render/emit
time and holds no locale state, so ordering bugs can only live in a CLI
entry that renders before activating. The flow's CLI entries therefore
activate the output language BEFORE constructing or running any
substrate frontend and before resolving `registered_values` copy —
before the FIRST render, not merely most renders, because the i18n
layer may memoize per process and an early default-locale resolution
sticks. When the operator answers the output-language question mid-walk
with no higher-precedence override, the flow enters a settings override
for the remainder of the walk at that answer, so subsequent pages render
in the chosen language. Locale keys constructed at runtime (the cotejo
divergence notice codes) are declared under a dynamic translation root
up front, so the static usage scanner never sweeps them as unknown.

## Structural pages

- `entrada`: FlowIntent routing (create / modify / resume checkpoint /
  discard checkpoint); no domain_key, no persistence.
- Review and submit: substrate primitives — no authoring beyond the
  section grouping above; submit eligibility is the substrate's
  `assert_submit_eligible` plus the flow-scope validators.
