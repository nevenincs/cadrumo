---
tags:
  - '#adr'
  - '#export-parity'
date: '2026-11-01'
modified: '2026-11-03'
body_schema: 'body-v2'
body_hash: 'sha256:3e7de7f23d8af7c08e6d7f65ee5686004f4d4dbe0ab8ae0083ae35e3a6444edb'
related:
  - "[[2026-09-27-export-parity-renta-withholding-sources-adr]]"
  - "[[2026-09-27-export-parity-renta-withholding-sources-research]]"
  - "[[2026-09-11-binding-schema-adr]]"
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-adr]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
  - "[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]"
  - "[[2026-08-24-registry-completeness-closure-adr]]"
  - "[[2026-09-09-registry-edition-authoring-adr]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
---
# `export-parity` adr: `declared per-binding grade cap that blocks verify, export and local filing` | (**status:** `accepted`)

Accepted 2026-11-01 on the operator's rulings recorded below.
## Problem Statement

On 2026-11-01 the operator ruled that an advisory value must block verify and export, and must not block calculation or preview. The operator also chose a typed per-binding grade, so that the grade is declared in the registry and not inferred from a fact name.

Two values are advisory today. Both carry ledger invoice withholding whose year imputation is not grounded. RIRPF art. 79 imputes a retención to the period of its income. The ledger keys each row by its bank date (`src/cadrumo/application/aggregation/renta_income_ledger.py:933`), and that is correct only under the RIRPF art. 7.2 cash-criterion election. The first value is Modelo 130 casilla 06, from binding `modelo-130-actividad-economica-retenciones-cumulative` (`src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0001-declarations.toml:113`). The second is Modelo 100 casilla 0599, bound on side branch commit d5493eed10 to `renta-ledger-actividad-retenciones-0599` at the 2022 baseline.

The resolver expresses their grade only as the note `advisory_retencion_credit_grade`. It emits that note for any non-zero declared credit of the shared fact (`src/cadrumo/application/aggregation/modelo_bindings.py:553-565`). The note has CHECK attention (`src/cadrumo/application/modelo/calculation_notes.py:146`), it is not a durable source-issue reason (`src/cadrumo/application/modelo/calculation_bucket_actions.py:968`), and it has no locale entry. An exported file therefore carries the value.

The registry already has a grade at revision level (`RegistryAuthorityGrade`, `src/cadrumo/core/authority_grade.py:24-80`; `ModeloRevision.authority_grade`) and a disposition at provider-kind level (`ProviderDisposition`, `src/cadrumo/domain/calculations/registry/binding_provider_registration.py:135`). Neither can say that one binding's value is not filing grade. The accepted withholding-sources decision requires 0599 to "stay advisory grade" until imputation is grounded (`2026-09-27-export-parity-renta-withholding-sources-adr`, Step 3 and the second-round rulings). This record decides what that grade is, and how it is declared, carried and enforced.

## Considerations

- Grades must be declared, preserved through resolved results, and never promoted by a downstream consumer (`.claude/rules/14-tax-calculation-domain.md`, bindings and authority invariants; `.claude/rules/07-aggregation-and-calculation-services.md`, completeness invariants).
- Each binding family has one typed declaration and one enrolled validator, and the binding row is a closed, self-describing declaration (`2026-09-11-binding-schema-adr`).
- The grading unit has to be the binding, not the provider kind. `ledger_renta_income_aggregation` also feeds the filing-grade income casilla 0171, and 0171, 0599 and Modelo 130 casilla 06 differ only in their `fact` selector. A kind-level change would demote 0171.
- Development progress may not be encoded as a source disposition (`2026-06-10-calculation-aggregation-taxonomy-adr`, amendment of 2026-09-07). An advisory binding still has an executable owner. Its grade is a claim about legal grounding, not about routing.
- Revision grade sets snapshot reach, and snapshot admission refuses rather than downgrades (`src/cadrumo/domain/calculations/registry/snapshot.py:124-130`, `:435`; `2026-08-24-tui-registry-api-gate-adr`). Grade promotion is a human attestation; demotion is derivable (`2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr`, which is still proposed but implemented in `src/cadrumo/core/authority_grade.py`).
- One refusal mechanism already covers exactly the operator's split. `require_work_unit_calculation_unblocked` (`src/cadrumo/application/modelo/calculation_note_gate.py:102-119`) runs at verify (`src/cadrumo/application/modelo/verification_actions.py:222`), export (`src/cadrumo/application/modelo/export.py:706`) and local filing (`src/cadrumo/application/modelo/filing_actions.py:621`). Calculation, the form and the review read the same notes without refusing (`src/cadrumo/application/modelo/work_form_notes.py:115-124`).
- The gate and the form agree only because both decide through one predicate, `gate_refuses` (`calculation_note_gate.py:40-49`). The gate calls it through `blocking_calculation_issues` (`:51-63`); the form imports it (`work_form_notes.py:18`) and sets `withholds_filing` from it (`:123-124`). Any reason the gate refuses on must therefore enter through that predicate's canonical set, `GATE_REFUSED_REASONS` (`src/cadrumo/application/modelo/calculation_notes.py:67-76`), or the form will show a value as fileable that verify refuses.
- The routing disposition `advisory` has a consumer outside the product: the binding-signal analysis maps it to `closed_advisory` (`dev/registry/binding_signal/semantics.py:279-280`).
- Bindings inherit across editions by identifier, and a stated member supersedes the inherited member in full (`2026-09-09-registry-edition-authoring-adr`). A grade carried on the binding therefore inherits and is promoted as an ordinary delta.
- A shipped-completeness claim accepts a connected source only with an evidence-backed terminal disposition, or a bounded blocked disposition that has an owner and a reconsideration condition (`2026-08-24-registry-completeness-closure-adr`).
- Most provisions an advisory value rests on are not in the legal catalogue today. The catalogue keys articles as `<norm>:art-<n>` and subparagraphs as `<norm>:art-<n>.<sub>` (for example `ley-35-2006:art-14.2.m` and `rd-1619-2012:art-6.1.i`). It has no `rd-439-2007:art-7`, `rd-439-2007:art-79` or `ley-35-2006:art-14` entry; `src/cadrumo/_data/registry/aeat/legal/irpf.toml` holds only `ley-35-2006:art-14.2.m`. `ley-27-2014:art-11` already exists (`src/cadrumo/_data/registry/aeat/legal/is.toml:42`).

## Considered options

- **(A) A declared grade cap on the binding.** The registry binding gains an optional typed cap with a closed grade, a closed reason and legal references, validated at build. The snapshot projects the cap onto the casillas it reaches. The calculation persists one durable note per capped resolved value, and the existing calculation-note gate refuses verify, export and local filing on that note. Chosen.
- **(B) Move the existing note into the refusing set.** Add `advisory_retencion_credit_grade` to `GATE_REFUSED_REASONS` or `EXPORT_REFUSED_REASONS` and make it durable. This is the smallest change, but the grade stays hard-coded in one resolver and keyed on the fact `declared_withheld_amount_sum`. That fact is shared by casilla 06 and 0599, so their promotions could not be separated. A promotion would be a code change rather than a registry delta. The resolver, not the registry, would own a regulated capability claim. Rejected: it does not meet the operator's "declared, not inferred" ruling.
- **(C) A per-binding override of `ProviderDisposition`.** Reuses a vocabulary that already has an unused `advisory` member. Disposition is the provider kind's routing contract, and `_require_disposition_matches_route` (`src/cadrumo/domain/calculations/registry/binding_provider_registration.py:714-724`) ties it to route ownership. A per-binding override would give a binding two disagreeing statements of one property. It would also reintroduce a lifecycle-flavoured disposition, which the 2026-09-07 taxonomy amendment withdrew. Rejected.
- **(D) Lower the whole revision's `authority_grade`.** Rejected. It would refuse the Modelo 100 export for every taxpayer, including those with no activity withholding, and it misstates a value-level gap as a revision-level one.
- **(E) A grade that holds only when a profile fact holds (for example the cash-criterion election).** Rejected for now. The plan's P05 re-keys the ledger by the elected criterion, which changes the resolver itself, so the right endpoint is removing the cap, not adding a conditional one. Reconsider if a regulated value is ever filing grade only under a profile condition that the resolver cannot absorb.

## Constraints

- The cap only narrows. A binding without a cap reaches as far as its revision's declared grade. A cap is never above the revision grade and never raises it.
- Removing a cap is a promotion, so it is an attestation: it lands only on an accepted ruling that cites the grounding, and no tool, migration or generator removes or rewrites a cap. Adding a cap is a demotion and needs only its grounds.
- There is one refusal mechanism: the calculation-note gate, deciding through `gate_refuses`. No second gate, export-only allowlist, parallel reason set or resolver-specific branch may enforce the grade.
- There is one staleness mechanism: the shared calculation screen stamp defined below, which this record, `2026-11-01-calculation-aggregation-taxonomy-tier-divergence-adr` and `2026-11-01-export-parity-suffered-withholding-schemas-adr` all use. It names no modelo.
- The cap is independent of the borrador. `aeat_prefilled` and the borrador participation marker of `2026-11-01-export-parity-suffered-withholding-schemas-adr` (section 6) neither set, clear nor bypass a cap; a capped binding whose value the borrador also carries stays capped.
- Calculation, recalculation, the work form, the review and the calculation summary must keep working on a capped value. Each shows the value with a blocking note that names the box, the binding, the reason and the legal references.
- `advisory_retencion_credit_grade` is retired in the same change, with all its consumers: the resolver emission, the diagnostic reason, the attention entry and the tests. The inferred-row note `inferred_retencion_excluded_from_credit` and the unknown-row note `unresolved_retencion_substrate` stay. They describe different states (a value left out, a value unknown) that the 2026-09-27 decision governs, and neither is a grade.
- Persisted revisions written before this change must not reach a file carrying a now-capped value without that value being caught, and adding the new note reason must not change their content-addressed ids.
- The S08 promotion of 0599 is out of scope, as is any other promotion. So are the TUI, MCP and frontend code, and the workspace V1 contract.

## Implementation

We will declare a grade cap per registry binding, carry it through resolution to the persisted revision as one durable note, and refuse verify, export and local filing on it through the existing calculation-note gate. Calculation and preview stay open.

**Vocabulary.** The cap reuses `RegistryAuthorityGrade`. Calculation, preview and every display read a capped value. Verify, export and local filing refuse it. That is the calculation rung of the ladder, so a new parallel enum is not needed, and "advisory" is the operator-facing word for a value whose reach is capped at calculation. The cap's grade admits `calculation` only. `filing` would restate the default. `applicability` would declare a binding that cannot be calculated, and such a binding should not exist. A new closed `BindingGradeCapReason` `StrEnum` sits beside `RegistryAuthorityGrade` in `src/cadrumo/core/authority_grade.py`. Its first member is `imputation_period_ungrounded`, and each member maps totally onto one `CalculationNoteSentence`. The unused `advisory` member is removed from `ProviderDisposition`, so per-kind disposition cannot become a second grade vocabulary.

**Where it is declared.** `BindingDefinition` (`src/cadrumo/domain/calculations/registry/schema.py:275`) gains an optional `grade_cap` member of a strict `BindingGradeCap` model that carries `grade`, `reason` and `legal_refs`. Absence means the binding is not capped. The authored form is one inline table on the binding row, for example `grade_cap = { grade = "calculation", reason = "imputation_period_ungrounded", legal_refs = [...] }`. It follows the binding through edition inheritance by identifier like every other binding field.

**Build validation.** Each rule refuses at registry build:

- an unknown grade or reason, or a grade other than `calculation`;
- a cap on a binding whose revision declares a grade at or below `calculation`;
- empty `legal_refs`, or a reference that does not resolve in the legal catalogue;
- a capped binding that reaches no casilla, either through a bound casilla or through a declared output redirect such as the governed fact `m130-retenciones-output-routing` (`src/cadrumo/_data/registry/aeat/facts/0090-m130-retenciones-output-routing.toml`);
- an alternate whose cap differs from its primary. The cap is part of the value contract that the binding-schema decision already requires alternates to share.

The snapshot derives, from those same edges, a read-only map from each capped binding to the casillas it reaches. The resolver and the gate both read that map, and nothing re-derives it.

**Propagation.** After the mesh merge, the canonical resolution step emits one diagnostic with reason `advisory_binding_value` for every capped binding that produced a value. It does this for all resolvers together, and no resolver emits the grade itself. The diagnostic carries the binding id, the reached casilla, the binding source, the reason and the amount. Resolver provenance is unchanged. The reason joins `_DurableSourceIssueReason` and the `CalculationSourceIssue.reason` literal, so it persists in the revision's `source_issues` (`src/cadrumo/domain/modelos/calculation_revision.py:789`). It is stored with `casilla_id` set to the reached casilla, `source_ref` set to the binding id, and a `CalculationNoteFact` whose sentence is the reason's mapped sentence and whose values are the binding and the amount. The note joins the revision identity only where it is present, so revisions persisted earlier keep their ids. Formula dependents of a capped casilla carry no note of their own. The revision-level refusal already withholds them.

**Refusal points.** `advisory_binding_value` becomes a member of `GATE_REFUSED_REASONS` itself (`src/cadrumo/application/modelo/calculation_notes.py:67-76`), and so of `BLOCKING_REASONS`. No separate grade set is introduced, because `gate_refuses` (`calculation_note_gate.py:40-49`) reads only the canonical set, and a second set would let the form and the gate disagree. Its attention is `BLOCKS`, and the form's `withholds_filing` reads true through the same `gate_refuses` call (`work_form_notes.py:123-124`). The gate therefore refuses verify, export and local filing, the same three call sites listed under Considerations. It refuses nothing at calculation, recalculation, the form, the review, the next-step projection or the calculation summary.

**Shared calculation screen stamp.** Staleness is decided by one stamp, shared with the tier-divergence and credit-reconciliation screens, rather than by one refusal per screen:

- A calculation persists an optional `screen_stamp` on the revision: a screen contract version (one integer for all screens together) and a content digest of the screen-relevant declarations of the pinned registry revision. Those declarations are the binding grade-cap map, the derived filing-bound set and the credit-reconciliation entries. The digest covers only that revision's declarations, never the global authority generation, so a publication that changes nothing a screen reads leaves the stamp current.
- At verify, export and local filing the gate recomputes the expected stamp from the operation's pinned authority. An absent stamp, a lower contract version or a different digest refuses with one derived reason, `calculation_screen_outdated`, whose remedy is to recalculate. It is never persisted, and its text names no modelo.
- It covers every stale case at once. A revision persisted before the cap existed has no stamp. A revision computed before a cap was added, or before a promotion removed one, has a different digest. The same holds for the other two screens.
- Revisions already `PRESENTADO` keep their history and are not re-adjudicated. The stamp joins the revision identity only where it is present, so earlier revisions keep their content-addressed ids.
- P02.S14 lands the stamp, because it is the first screen to land. The other two records enrol their declarations in the digest and raise the contract version when they land.

**Finding shape and locale keys.** The note uses the existing note catalogue. The keys are `application.modelo.calc_diagnostic.advisory_binding_value.what` and `.what_to_do`, `application.modelo.calc_diagnostic.calculation_screen_outdated.what` and `.what_to_do`, and the fact sentence key `application.modelo.calc_diagnostic_fact.advisory_imputation_period_ungrounded`. The fact sentence names the box by its printed number, the amount, and the provisions that leave the year ungrounded. The refusal error is worded by the first blocking note's `what` key, as the gate already does. The keys are authored in every supported locale through the `dev.locales` workflow, with the operator addressed informally in the singular.

**Zero values (decided).** A capped binding that resolves to a proven zero passes, and a capped binding that resolves to zero from rows that carry withholding blocks. A proven zero is a value computed over a window in which the resolver found no withholding-bearing row, so no imputation question arises for it. A zero computed from rows that carry withholding (for example rows whose withholding was excluded as unpaid or as belonging to another window) blocks, because the year question is exactly what produced it. The resolver states which case applies as a typed outcome on the `advisory_binding_value` diagnostic, so the gate reads the outcome and never infers it from the amount. A capped binding with no typed outcome blocks. The proven-zero outcome emits no blocking note, and the diagnostic is still recorded so the form can show that the zero was proven. S14 tests cover both zero cases and the absent-outcome case through the real resolver and gate.

**Previews and certificates (decided).** The signed calculation report and the Google Sheets calculation workbook are previews: they show the capped value with its note and are not refused. An agreeing payer certificate or datos fiscales record for the same ejercicio does not clear a cap for that value; only a promotion by registry delta removes it.

**Interaction with revision grade and screens.** A value's reach is the lower of its revision's declared grade and its binding's cap. Snapshot admission stays revision-level: a filing-grade request on Modelo 100 or 130 is still admitted, and the cap refuses only the revision values it touches. A cap neither demotes the revision nor counts against it in the `grade_earned` screen (`dev/registry/analysis/grade_earned.py`), whose `under_supported` and `under_declared` findings stay revision-level. The cross-period clean-state gate (`src/cadrumo/application/calculations/cross_period_clean_state.py:219`) stays revision-level as well. A revision that carries a capped value cannot be filed locally, so it never becomes a filed prior that a later period could consume.

**Promotion as a registry delta.** Promotion removes `grade_cap` from the binding in the edition where the grounding begins: the baseline for an across-the-board promotion, or a successor edition that restates the binding without the cap when the grounding starts in a later ejercicio. The cap's legal references and reason state the reconsideration condition. Removal lands only with the accepted ruling and goes through publication and runtime adoption, each reported separately. Each capped binding has its own promotion path: 0599 through plan Step P05.S08, and Modelo 130 casilla 06 through P05.S31. The evidence each must present is set by `2026-11-01-export-parity-income-imputation-criterion-adr` (Implementation item 9) as resolver properties proven by tests, not as conditions on a taxpayer, consistent with the rejection of option E. Existing revisions then refuse with `calculation_screen_outdated` until they are recalculated.

**Bounded to plan Steps.** P02.S14 lands the vocabulary, schema field, validation, snapshot map, generic emission, durable reason, its membership in `GATE_REFUSED_REASONS` and the shared screen stamp. It adds the legal catalogue entries the cap cites, `rd-439-2007:art-7`, `rd-439-2007:art-79` and `ley-35-2006:art-14`, with source excerpts for the subparagraphs relied on (RIRPF art. 7.2, LIRPF art. 14.1.b). It retires `advisory_retencion_credit_grade` and the `advisory` disposition, adds the locale keys, and caps `modelo-130-actividad-economica-retenciones-cumulative`. Its write set includes `dev/registry/binding_signal/semantics.py:279`, whose `closed_advisory` branch reads the retired disposition and must be removed in the same change; any other path correction is recorded through the plan verbs. Its tests run through the real compiler, resolver, calculation and export path, and prove six things:

- each build refusal fires on an isolated defective fixture, with a control showing that the live corpus passes;
- calculation, the form and the summary succeed and show the blocking note, and the form's `withholds_filing` agrees with the gate on every capped value;
- verify, export and local filing refuse;
- a revision persisted before the cap, and a revision whose screen digest differs, refuse with `calculation_screen_outdated`;
- a publication that changes no screen-relevant declaration leaves a stamped revision current;
- casilla 0171, fed by the same provider kind, stays filing grade.

**Cross-domain dependencies.** The operator has ruled on the zero-cap and casilla 06 questions (Operator rulings 2026-11-01 below), so S14 is no longer waiting on them. Capping casilla 06 changes Modelo 130 goldens that other sessions own, and the shared screen stamp refuses every unstamped revision of every modelo at verify and export. Both are cross-domain effects that plan Step P01.S28 coordinates before S14 lands, and cross-domain coordination is authorized by the operator. This dependency adds no product scope to S14.

P02.S05 rebases d5493eed10 onto that work and adds the same cap to `renta-ledger-actividad-retenciones-0599` at the 2022 baseline. It rewrites the binding comment so it no longer names the retired note, and adapts that commit's tests to assert that calculation succeeds while verify and export refuse. Oracle-checked tests with independent oracles prove that inferred and unknown rows still leave 0599 unchanged. Authority publication remains with the shared publication session.

## Rationale

Option A is the only option that meets the operator's ruling exactly and keeps one mechanism for each concern. The grade is declared on the binding, which is the smallest unit that separates 0599 and casilla 06 from 0171. The registry validates it. It reaches the persisted revision as a typed durable fact. Its promotion is an ordinary edition delta behind an attestation. The refusal reuses the gate that already draws the operator's line between verify, export and filing on one side and calculation and preview on the other, so no parallel gate appears. Option B leaves the regulated claim in resolver code, keyed on a shared fact name. Option C overloads the routing disposition the binding-schema decision made per kind. Option D refuses legitimate returns. Option E solves a problem the plan solves by fixing the resolver. Reusing `RegistryAuthorityGrade` keeps one grade ladder, so "the lower of revision and binding" is an ordinary comparison and not a mapping between two vocabularies.

## Consequences

- Gains: no advisory value reaches an exported file or a local filing. The operator sees why, box by box, in every language. 0599 and casilla 06 can be promoted independently by a reviewable registry delta. The resolver no longer owns a capability claim. A shipped-completeness report can list every capped binding as a bounded disposition with its grounds and reconsideration condition.
- Costs: a schema field, five build rules, one durable reason, one derived gate reason shared with two other screens, locale keys in every supported locale, and new legal catalogue entries. Every revision that holds a capped value is blocked at verify and export until promotion. With casilla 06 capped, that may mean many Modelo 130 exports for autonomos; the proven-zero rule limits it to quarters with withholding-bearing rows.
- Pitfalls: an author may copy a cap onto a binding without a grounded reason. The closed reason vocabulary and the legal-reference rule make that a deliberate act. The screen stamp detects a changed cap map but not an incomplete emission, so the emission must cover every resolved channel, scalar and row alike, and a test proves it.
- Reconsider if a value proves filing grade only under a taxpayer condition (option E), or if a later decision lets per-value evidence such as an agreeing payer certificate for the same ejercicio clear a cap for that value only; the operator ruled that today it does not.

## Proposed edits to accepted records

These are proposals only. No accepted text changes until each is authorized.

- `2026-09-27-export-parity-renta-withholding-sources-adr`, Step 3, last sentence. Replace "0599 stays advisory grade until the temporal rule below is grounded." with "0599, and Modelo 130 casilla 06, carry a declared binding grade cap of `calculation` with reason `imputation_period_ungrounded` under the binding-capability-grade decision, which blocks verify, export and local filing until the temporal rule below is grounded and the cap is removed by ruling. The inferred-row advisory finding is a calculation note, not a grade."
- `2026-06-10-calculation-aggregation-taxonomy-adr`, amendment of 2026-09-07. Append: "A declared binding grade cap is a grounded capability claim on a routed binding, not a source disposition; it neither makes a missing resolver acceptable nor substitutes for one."
- `2026-09-11-binding-schema-adr`, Implementation, the authored row field list. Add `grade_cap` after `aeat_prefilled` (beside the borrador participation marker proposed by `2026-11-01-export-parity-suffered-withholding-schemas-adr`, so both field edits are applied together), and add to the compiler refusals: "a grade cap outside the closed grade and reason vocabularies, not strictly below the revision grade, without resolving legal references, reaching no casilla, or differing between an alternate and its primary". Record that `ProviderDisposition` no longer carries `advisory`.
- `2026-08-24-registry-completeness-closure-adr`, Implementation, limb 2. After "a bounded blocked disposition with an owner, review condition, and follow-up", add "including a connected binding under a declared grade cap, whose grounds and removal ruling are its review condition".
- `2026-09-09-registry-edition-authoring-adr` and `2026-08-24-tui-registry-api-gate-adr` need no edit. The cap is an ordinary binding field under the inheritance rule. A successor that adds a cap is not withholding by design, because that refusal is keyed on revision grades. The workspace receives the cap only through the existing notes and findings.

## Operator rulings 2026-11-01

Basis: Operator rulings 2026-11-01, given in conversation. Each earlier open question is answered as follows, and none remains open.

- Zero-cap rule: an advisory (capped) value that is a proven zero passes, because no withholding-bearing rows exist in the window. A zero computed from rows with withholding blocks. This is the rule decided under Implementation, Zero values.
- Casilla 06 endpoint: Modelo 130 casilla 06 is capped like Modelo 100 casilla 0599 (the operator's words: "go with recommend"). Casilla 06 is promoted through its own path, P05.S31, once the imputation resolver properties hold, independently of 0599 (P05.S08). The endpoint is shared with `2026-11-01-export-parity-income-imputation-criterion-adr`.
- Signed calculation report and Google Sheets workbook: both are previews that show the note and are not refused.
- Payer certificate or datos fiscales record: an agreeing record for the same ejercicio does not clear the cap.
- Cross-domain coordination: authorized, for the Modelo 130 goldens and the shared screen stamp (plan Step P01.S28).

## Amendment 2026-11-02: proven-zero persistence and revisions filed before the cap

Authorized by the operator on 2026-11-02 ("follow your recommends; proven-zero can happen now").

- The proven-zero outcome is persisted on the revision's source issues as a typed value outcome, so a reloaded form and the declarations list show that a capped value was proven zero. It stays non-blocking. Stored revisions written before this change are not rewritten and keep their identity.
- A filed (PRESENTADO) revision written before the screen stamp existed, whose pinned revision has a capped binding and whose stored value for that binding's casilla is nonzero or unresolved, is refused at export of the local file until the period is recalculated. Filed revisions with a stamp, and filed revisions with no capped value, keep their existing behaviour. Local filing state, AEAT status and receipts are unaffected.
- The signed calculation report stays limited to sealed revisions and applies the same screen check as export to non-filed sealed revisions, so a revision sealed before the cap is not signed without its note.

## Amendment 2026-11-02: promotion of Modelo 130 casilla 06 and Modelo 100 casilla 0599

Basis: operator ruling 2026-11-02, relayed by the orchestrator as binding for plan Steps P05.S31 and P05.S08. The ruling removes both caps once the resolver and the credit reconciliation hold the properties of `2026-11-01-export-parity-income-imputation-criterion-adr` Implementation item 9. Each promotion is a registry delta at the baseline edition, because the grounding applies to every ejercicio the baseline covers. The provisions did not change across those ejercicios, and no successor edition restates either binding.

- P05.S31, Modelo 130 casilla 06. The cap is removed from `modelo-130-actividad-economica-retenciones-cumulative` at the `2019-y-siguientes` baseline (`src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0001-declarations.toml`).
  - The binding now cites LIRPF art. 14 and RIRPF arts. 7, 79 and 110.
  - Its Modelo 130 instructions citation adds the casilla 06 window text: "correspondientes al período comprendido entre el primer día del año y el último día del trimestre a que se refiere el pago fraccionado".
  - The conditions that held at promotion:
    - each row's retención follows its income into the window the declared criterion imputes it to;
    - an unknown criterion or accrual date leaves the value unresolved;
    - withholding paid after the window's end is reported and left for the quarter it is paid in (RIRPF art. 110.3.a, "practicadas"; TEAC 00/03187/2011);
    - a rental activity's withholding is kept (RIRPF art. 110.3.a.2.º).
- P05.S08, Modelo 100 casilla 0599. The cap is removed from `renta-ledger-actividad-retenciones-0599` at the `2022` baseline (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml`), and the binding now cites LIRPF art. 14 and RIRPF arts. 7 and 79. The conditions that held at promotion:
  - each row's retención follows its income into the ejercicio the criterion imputes it to, whenever it was paid (RIRPF art. 79);
  - only withholding on a linked, wholly paid invoice is credited;
  - accrued-but-unpaid withholding is reported, with a rectification finding when the payment follows a filed return;
  - a rental activity's withholding goes to 0598;
  - the credit reconciliation compares 0599 with the payer records by the payer's payment year (DGT V4965-16), with the borrador, and with casilla 06 of the filed fourth-quarter Modelo 130 on that return's basis. Only a residual difference the itemised timing cannot explain blocks.
- DGT V4965-16 is cited in the 0599 binding comment and here, not as a `legal_refs` entry. The legal catalogue has no entry kind for a DGT consulta and no bundled copy of one.
- The mechanism stays, and no binding in the published registry carries a cap after these promotions. The tests of the reach, the emitted note, the screen digest, the filed-before-cap check and the build refusals declare the cap in memory on a copy of the Modelo 130 revision. Revisions calculated before the promotions refuse with `calculation_screen_outdated` until they are recalculated, as Promotion as a registry delta states. Publication and runtime adoption of the shared authority stay with the shared publication session. These Steps republished only the worktree-local authority.
- Evidence: `2026-11-01-export-parity-withholding-legal-readings-research` (Q1 and Q3), `2026-11-01-export-parity-income-imputation-criterion-research`, `2026-11-01-export-parity-income-imputation-criterion-adr` items 6 to 9, and `2026-11-01-export-parity-suffered-withholding-schemas-adr`. The resolver properties are proven by tests in `src/cadrumo/application/aggregation/tests/test_renta_imputation_criterion.py`, `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_100_retencion_soportada_credits_live.py`, `src/cadrumo/entrypoints/tests/profile_persistence/test_e2e_ledger_m130_retenciones.py` and `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_130_carry_forward_continuity.py`. The last holds the production route: a Modelo 130 with 1.000,00 of activity income and 162,00 withheld verifies complete and exports.
