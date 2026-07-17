---
tags:
  - '#audit'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` audit: `execution-traceability-reconciliation`

## Scope

Reconcile the checked rows in the open-ended cross-domain-continuity plan against retained execution evidence at current HEAD. The pass distinguishes a checked row backed by a reviewed historical commit or execution record from a checked row supported only by code inspection, an obsolete aggregate record, or a deferral. It does not create, alter, or validate production behavior.

## Findings

### historical-exec-link-recovery | low | every checked row now has an individual evidence record

The plan began this reconciliation with 209 checked rows lacking a resolvable per-step execution record. Historical audits, named commits, and grouped execution records directly support 187 of those rows. Twenty-two unsupported checks were initially returned to open state; current code, official-source, and real regression evidence revalidated S62-S64, S94, S181-S186, S315, and S369, while the discovered broader surface required a repair before S415 could complete. Individual records now preserve every credited evidence edge without rewriting implementation history or changing production code.

### retained-direct-evidence | low | 84 additional checks have a named evidence source

The following inventory was the authoritative input for the final per-step record backfill. Each commit or retained historical record maps only to the listed plan steps.

| Evidence | Supported steps |
| --- | --- |
| `ed332d752b` | S157, S158 |
| `7cc0ef0b5a` | S159 |
| `c2cf725b21` | S161 |
| `afde39b58a` | S163, S195 |
| `e591f99eb8` | S200 |
| `cb0c684f83` | S201 |
| `ffa83cf095` | S206, S207 |
| `db43a24f89` | S212 |
| `03c4c475cb` | S213, S240 |
| `9f364a2f90` | S214 |
| `c25b14a549` | S215 |
| `5429f5eca1` | S216 |
| `5b1c1ac233` | S217, S241-S243, S245, S259, S261, S263, S265, S276, S339 |
| `a69608c47b` | S244 |
| `c195c7d46b` | S258 |
| `199178c136` | S262, S266 |
| `20f143b762` | S264 |
| `868829fc27` | S274 |
| `a3a1ad3da3` | S275 |
| `58f450eacf` | S310 |
| `19c283b388` | S313 |
| `c3118ec50c` | S314 |
| `38526f2984` | S321 |
| `f8c86f2b98` | S326, S327, S334 |
| `ec1c67cb36` | S346 |
| `688ed67133` | S349 |
| `21cab5df04` | S354 |
| `a375aa309e` | S357 |
| `a2dc84adc3` | S359 |
| `b645c8df3c` | S408 |
| `2dfc2fd75e` | S360 |
| `7ce749dff9` | S364 |
| `c6788acb4c` | S366 |
| `9272ee0a0d` | S368 |
| `7ff039f4ca` | S379 |
| `8dbd72ee8e` | S388 |
| `d0b1cf0cbf` | S389 |
| `bc13eca50d` | S401 |
| `699044acfe` | S400 |
| `e5e3c630ea` | S390 |
| `b6129ba9e4` | S391 |
| `4db159e3a8` | S397, S412 |
| `f79cc34a8a` | S402 |
| `e19c7f4063` | S166 |
| `899f853769` | S167 |
| `59ab5807b5` | S203 |
| `4c678f6551` | S232 |
| `3e5b5ea798` | S316 |
| `2f5395f70d` | S175 |
| `ef2616180f` | S180 |
| `3def43cc78` | S182 |
| `72532f0ba0` | S187 |
| `3a7d44dd2c` | S188 |
| `8181596898` | S196 |
| `46ecfb9668` | S150-S156 |
| `f984e4bb5d` | S403 |
| 2026-06-03 cross-domain-continuity audit | S404, S406 |
| `7d854a9382` | S405 |
| `ae0713adcb` | S407 |

### modelo-111-2026-deadline-review | low | all four quarterly windows are correct; focused date pin is still advisable

The independent review accepted the existing Modelo 111 2026 windows. The live registry resolves 1T through 4T to the statutory 1st-through-20th windows, with the 2026 4T filing window correctly falling in January 2027. The current AEAT 2026 calendar and the bundled legal sources agree. Existing tests cover runtime selection and registered-window presence; a future focused regression should pin the four exact date tuples.

### modelo-232-2025-2026-deadline-review | low | annual windows verified and their exact dates are now pinned

The independent review confirmed that the 2025 and 2026 Modelo 232 annual windows implement the month-after-ten-months rule from Orden HFP/816/2017 article 4. The live registry returns November 2026 for 2025 0A and November 2027 for 2026 0A. The review identified an absent 2025 exact-date assertion; it was added to the dedicated real-registry suite and accepted on follow-up.

### modelo-349-2025-2026-deadline-review | low | both cadence families and their statutory exceptions are verified

The independent review confirmed complete 2025 and 2026 Modelo 349 deadline coverage. The live registry resolves all monthly and quarterly periods, applies the €50,000 cadence predicate, and correctly uses the July-to-September, December-to-January, and fourth-quarter-to-January statutory windows. The committed-registry test now pins the corresponding 2026 date classes.

### modelo-390-2025-2026-deadline-review | low | annual January windows and raw statutory-close treatment are verified

The independent review confirmed that the 2025 and 2026 Modelo 390 annual windows resolve to 1–30 January of the following year, as required by Orden EHA/3111/2009 article 8. Dedicated committed-registry coverage pins both exact tuples. The engine, rather than the registry, is responsible for shifting a raw statutory close that falls on a weekend or holiday; the unavailable 2027 holiday record is not a defect in this deadline-window step.

### modelo-131-revision-scope-review | low | full populated revision family replaces obsolete empty-directory premise

The independent review confirmed that Modelo 131 is not an empty scaffold: it has four complete revision families through 2026, including legal and source provenance, calculation closure, and objective-estimation deadline windows. Live resolution selects the correct yearly revision and direct committed-registry and deadline-engine suites exercise it. A generic first-quarter date assertion could name Modelo 131 more precisely, but this does not undermine the scope decision or require a plan expansion.

### ledger-rule-engine-adr-review | low | accepted ADR fully decides the prerequisite contract

The accepted rule-engine ADR selects regex matching, profile-scoped encrypted storage, deterministic priority ordering, ACTIVE plus NOT_YET_PROCESSED application scope, and manual-classification reaffirm semantics. The repository, action, and CLI surfaces conform to that contract. No new ADR or implementation work is required; the reconciliation record supplies the missing plan evidence edge.

### applicability-authority-review | low | source boundary holds; historic test count was corrected

The registry applicability module remains the sole modelo-level authority, while TOML conditions choose only among already applicable deadline windows. No duplicate production rule-table assignment is present, and the retired application shim remains absent. The direct suite has three current tests, not the four claimed in the historical row; the step action was corrected through the plan CLI before closure.

### profile-source-mesh-repair | medium | Modelo 036 and 202 profile inputs now reach the calculation resolver

The original S415 record correctly validated every profile selector against the schema but did not exercise the resolver beyond Modelo 100. Direct runtime evidence exposed a canonical boundary defect: the resolver admitted only formula-consumed and bound-numeric bindings, so Modelo 036's censo enum and Modelo 202's calculation-only INCN selector were silently excluded. The resolver now admits profile selectors without an XSD, XML-attribute, or dictionary export address, routes calculation-only typed enums through the enum channel, and continues to exclude export-only identity values. A real source-mesh suite covers Modelo 036; Modelo 100 revisions 2020–2025; and Modelos 200, 202, 210, and 303 with binding-value and provenance assertions. Focused gates passed 32 plus 29 tests and Ruff; independent code review approved with no findings.

### wave-3-supplemental-review | low | complete commit inventory and all-model profile resolution are now evidenced

The retained Wave-3 audit, its named commit inventory, the 38-binding Modelo 100 guard, and supplemental review cover the original scope and omitted Modelo 200 enum-routing and Modelo 100 CCAA-replay changes. The only supplemental medium gap was S415's lack of real resolver coverage beyond Modelo 100. The repaired source mesh now covers every discovered profile-source revision, and the supplemental reviewer accepted the result with no critical, high, or medium finding. S68 is re-credited through its individual execution record.

### monthly-period-end-authority-drift | high | monthly helpers disagree with the canonical Period end date

For registry token `03`, canonical `Period` returns 31 March but `period_end_date` returns 1 March. The helper reaches calculation `filing_period` context, taxation comparison, registry replay, export fallback, and Modelo 349 raw-ledger filtering; a 20 March intracommunity row can therefore escape the M349 fail-closed guard. The historical Wave-1 unification covered 1P–3P but did not test monthly parity, and no current plan row tracked the divergence. The new W09.P46.S416 corrective step must delegate contiguous tokens to `Period` while retaining the non-date-span Modelo 202 instalment mapping, with all-token parity and a real M349 midpoint regression.

### s416-contiguous-period-parity-coverage | medium | direct canonical parity omits quarters and the annual token

S416 correctly delegates all contiguous tokens to `Period`, and the real Modelo 349 March-20 calculation regression proves the formerly unsafe monthly path. However, the new canonical-parity parametrization covers only `01` through `12`; `1T` through `4T` and `0A` are checked only against literal dates. Those five tokens are contiguous and now share the same delegation branch, so the plan's explicit all-contiguous-token parity evidence remains incomplete. Extend the parity case to the four quarterly tokens and `0A`, retaining the separate literal assertions for the Modelo 202 `1P` through `3P` mapping.

### s416-contiguous-period-parity-resolution | low | full delegated surface is now pinned and independently approved

The parity regression now checks helper start and end dates against canonical `Period` for 1T–4T, 0A, and 01–12; 1P–3P retain their separate payment-month assertions. The real March-20 Modelo 349 calculation case continues to prove the live fail-closed outcome. Ruff and the focused 38-test slice passed, and the independent re-review approved the correction with no remaining finding.

### modelo-303-article-20-prorrata-review | high | casilla-61 absence is correct, but a false deduction route remains live

The current Modelo 303 registry correctly omits casilla 61, which AEAT removed in 2021. The open issue is not a missing field: Article 20.Uno.26 appears in a live exception that classifies its domestic-exempt amount as prorrata volume with a deduction right. Primary BOE and current AEAT sources place Article 20 domestic exemptions outside the right-to-deduct list. The exception can overstate the prorrata numerator and recoverable IVA. Research recommends withdrawing the unused discriminator and its special route while retaining the ordinary domestic-exempt treatment; the contrary accepted ADR requires formal supersession before implementation.

### modelo-100-carry-regression-attribution | medium | behavior is green only against concurrent uncommitted work

The real encrypted-storage carry-forward test failed first because a concurrent Modelo 210 edit called a missing helper in the shared calculation module. It passed after that helper appeared in uncommitted peer work. The Article 48 carry binding itself remains well grounded, but S365 cannot be re-credited until the unrelated shared-path change stabilizes and the focused regression is rerun against a durable state.

### articulo-27-exact-twelve-month-boundary | high | current recargo tail begins one day too early

The recargo table resolves the exact twelve-month anniversary to the 15-percent-plus-interest tail. AEAT guidance starts that consequence on the day after the twelve-month period, while the anniversary still belongs to the one-percent-plus-one-percent-per-completed-month rule. The direct runtime case for 2026-04-20 through 2027-04-20 demonstrated the incorrect 15-percent result. Existing tests cover only later tail dates; an exact-boundary real-behavior regression is required.

### articulo-27-statute-fact-gate | high | rate-only overdue notice overclaims eligibility and omits monetary computation

The calculate path receives only an overdue work unit and date, yet emits an imperative Article 27 rate payload for every model. It has no amount payable, actual presentation date, or no-prior-requirement evidence, and cannot calculate a recargo or interest amount. This can label informational or zero/refund work as recargo-eligible. A correction must distinguish a rate-only conditional advisory from a statutory recargo computation and fail closed when the required facts are absent.

### round-8-cli-persona-fleet | major | calendar applicability and work readiness disagree for the no-business landlord scenario

The landlord/pensioner profile correctly surfaces Modelo 100 as applicable and suppresses Modelo 130, 303, and 390. Creating the only applicable Modelo 100 work unit then refuses the absent `activities.description` filing-baseline value, despite the profile having no economic activity. Source grounding confirms this is invalid: activities are repeatable, the no-business schema and wizard do not require them, and the calendar only pads the value for schedule diagnostics. The universal work-unit gate and profile status therefore impose an unrelated activity requirement after applicability. W02.P67.S418 must repair the target-aware readiness boundary and prove the real CLI journey without weakening the M130 or 303 applicability refusals. The autonomous and corporate personas either completed their work-unit path or received clear missing-input calculation refusals. The gestor multi-profile path passed with the canonical root command `aeat config switch <name>`; the prior `config profile switch` attempt was an operator namespace error, not a product defect. The existing S343 Article 27 high finding was reproduced for Modelo 202 and remains open.

### modelo-303-intracom-export-binding-review | low | registry-owned 59/60 route, R12 boundary, and cash-accounting separation hold

Independent review confirmed that the zero-rated repercutido selectors for casillas 59 and 60 belong to the Modelo 303 registry, carry the appropriate legal and official-form sources, and resolve through the live aggregation path. Goods supplies to a non-Spanish EU counterparty feed 59; R12 B2B services remain domestic-not-subject and do not. Casilla 62 is governed only by the independent cash-accounting route. The direct focused suite and Ruff passed with no material review finding.

### unsupported-checked-rows | medium | 6 checks remain open pending direct evidence or implementation

The following former checked rows lack retained direct execution evidence and cannot remain credited under the plan-closure rule: `S103`, `S122`, `S147`, `S343`, `S355`, and `S365`. S35, S37, S52-S54, S62-S64, S68, S71, S94, S181-S186, S315, and S369 have since been revalidated with current direct evidence and individual records.

`S94` and `S147` are especially clear: their retained historical evidence records deferral, not completion. `S50` has a documented real-storage test-quality caveat; its execution record carries that caveat but does not overstate it as resolved.

### termination-contract-still-open | high | the campaign is at-rest, not terminated

The 2026-07-09 checkpoint audit proves the plan's at-rest conditions, but it explicitly retains `W11.P60.S197` as the guard against a completion claim. The plan still requires a new full persona fleet with zero BLOCKER and MAJOR findings and a full drift sweep with zero in-scope drift before it can terminate.

### deferred-and-cadence-rows | low | intentional open rows remain open

`S351` and `S370` are explicit deferred-with-reason items. `S192`, `S193`, `S194`, and `S337` are ongoing maintenance cadence obligations. They are not implementation completions and must not be checked merely to improve the percentage.

### s418-attribution-profile-status-divergence | medium | attribution entities can be reported configured while their applicable work remains baseline-blocked

The targetless S418 baseline requires `activities.description` only for legal entities or profiles that declare `actividad_economica`. An attribution entity with no declared IRPF economic-income category therefore reaches `config profile status` as configured even though its applicable Modelo 184 or Modelo 349 work still takes the non-Modelo-100 branch and requires that same activity description. The existing Modelo 349 attribution-entity readiness coverage demonstrates that this entity class has a live filing route. Align the targetless condition with every non-natural entity (or otherwise prove the divergent status contract) and add a real CLI regression before S418 is credited.

### s418-attribution-profile-status-resolution | low | only declared non-business natural persons receive the readiness exception

The targetless baseline now requires the activity description for every non-natural entity, economically active natural person, and natural person with undeclared income categories. A real encrypted-storage CLI regression creates a no-activity attribution entity, proves `config profile status` returns `configured=false`, and confirms Modelo 184 work creation refuses on the same missing fact. The landlord/pensioner path continues to pass Modelo 100 readiness and work creation while Modelo 130 and 303 refuse as inapplicable. The final independent re-review approved the converged boundary.

### wave-3-corporate-persona-rerun | low | corporate work paths fail closed with target-specific remediation

Fresh S.L. and high-INCN S.A. personas both surface M200 and M202 calendar obligations, resolve the S.A. INCN profile input, and create the relevant work units. Their calculation paths refuse only on explicit prior-year or profile inputs without drafts, raw template leakage, or a visible inverted modality. M200's 2024 PyME bracket itself was not reached because the persona did not provide all lawful accounting inputs, so S69 remains open for that direct historical proof. The pre-existing S343 Article 27 behavior was reproduced and remains separately open.

### wave-3-corporate-persona-rerun-resolution | low | fresh Micro PyME CLI replay proves the 2024 23-percent bracket route

A fresh encrypted-store S.L. persona with common-regime legal-entity facts, economic activity, INCN €500,000.00, and no new-entity treatment created the 2024 Modelo 200 work unit through the live CLI. The real `work calculate` call supplied the authoritative test contract: €100,000.00 base, zero statutory corrections, zero carry-forwards, Estado share 100, and zero Modelo 202 payments. It persisted draft `c3990f60442d4a9cf722e42c99a6b9f79e20913513544a1ac58c7237ef9e98e1` for work unit `a3fcb3c11f5fbb4a697a85982c41c2a4008e4d574b8bbc098dd0c85adb8e54f7`, returned `DP200014:00562 = 23000.00`, and emitted no `bracket_no_window`. This is the real CLI oracle for the 2024 Ley 27/2014 article 29 micro-entity rate and resolves S69's remaining Modelo 200 temporal-bracket evidence gap; it does not resolve the separately tracked Article 27 finding S343.

### wave-3-pere-tariff-prerequisite | major | non-business Modelo 100 calculation demands an economic-activity binding

A fully declared Catalunya pensioner/landlord with no activity validates ready, has `configured=true`, sees Modelo 100 applicable, and opens its 2025 annual work unit. With pension and rental casillas plus the legitimate zero prior negative-base binding, calculation refuses `renta-2025-modelo-100-estimacion-directa-es-normal`. That profile must not declare an activity estimation regime. Several stored personal profile values also remain listed as unresolved. A target-aware Modelo 100 calculation-binding correction is required before S70 can prove the IRPF tariff.

### s419-direct-estimation-scenario-regression | high | activity predicate is absent from real direct-estimation scenarios

S419 adds `renta-2025-profile-has-economic-activity` as the first operand of formula 0075, but the live registry scenarios still supply only the direct-estimation modality binding. `pytest src/aeat/domain/calculations/registry/tests/test_registry_scenarios.py` now fails on the normal direct-estimation scenario: casilla 0224 is not calculated, so its expected provenance and the downstream 0235 provenance are both absent. Add the derived predicate explicitly to every direct-estimation scenario with value `1`, retain it as `0` for non-business rental scenarios, and add a direct assertion that an economic-activity profile still requires the modality binding. This is necessary before S419 can be credited.

### s419-non-business-tariff-resolution | low | activity predicate preserves both Renta calculation branches

Formula 0075 now short-circuits to zero only when the profile's canonical income categories contain no economic activity; the manual estimación-directa modality remains the selected-branch prerequisite for an economic profile. The no-business Catalunya CLI persona calculates Modelo 100 with positive 0545 and 0546 tariff casillas and no invented activity input. All direct-estimation scenarios provide predicate `1` and retain their original 0224 provenance; the real economic CLI persona still refuses an absent modality. The independent re-review approved the correction.

## W04.P21.S79 fresh CLI persona rerun

### CLOSED | Marc autónomo verification, period grammar, and empty-ledger boundaries

In a fresh encrypted store, a Catalan direct-simplified Marc profile created Modelo 130 2026/1T work `34ffaf0e993fe106d349020d056074e4d8ad948b6ac0d6cbb72a02ba9a73a852`. Empty verification refused because no selectable calculation revision exists. The populated calculation saved draft `d82fe1d6e3631c6f30f5ad15cc41d61c334d6096a9b7d0f851d9f00e325ba022`; its first clear refusal requested prior-year activity income, and its later verification first required the factual 2026-01-01 activity-start date. Once that fact was recorded through the CLI, verification returned `completeness_status=complete` and `granted_verificado_completo=true`, with only a pre-activity advisory.

`ledger import --period 2026T1 --year 2026` correctly refuses in Catalan and teaches the canonical `--period 1T --year 2026` form. The canonical dry run accepts the same CSV and previews two entries. Empty-ledger `classify` and `view` return structured refusals, while `list` returns an explicit empty result; the historical silent-empty condition did not recur. The normal work list renders the state as `Esborrany` with no human-facing English leakage.

### MINOR | Marc Modelo 349 probe uses a retired work-list filter and exposes parser-language drift

The operating brief's `modelo work list --modelo 349` form is no longer supported: work-list has no modelo filter. Its parser error ignores Marc's selected Catalan output language and mixes Spanish help with English option text. The canonical fallback, `overview explain 349`, reports applicability as incomplete because no intracommunity-operation fact is declared. This is informational for the no-intracom Marc persona; retain the parser-language issue for the localisation follow-up rather than treating Modelo 349 as an obligation.

### BLOCKER | S.A. profile drift leaks traceback and cannot reach verified-complete without prior evidence

A fresh Spanish S.A. profile created Modelo 200 2026/0A work `529dbd6264c2352f283bc2632684780301ac1480d316e64fbf79a79bcf8de126`. Empty verification refused correctly. A populated calculation using base `00501=100000`, the declared not-new-entity fact, and Estado share `100` saved draft `f19c84f4273f6f6ed5c6fbcd5de0ffb4770b16dbc27340dc2fca2ea69157301d`. The catalog now disambiguates printed `00562` into manual `DP200010:00562` and computed cuota-integral `DP200014:00562`, so this run did not inject the unrelated manual field.

The draft cannot be granted `verificado_completo` without evidence for the 2025 Modelo 200 relations and 2026 Modelo 202 instalments. More seriously, after a legitimate CLI profile edit records activity-start 2026-01-01, `modelo work verify` emits a full Python traceback before its error envelope and returns `REFUSED_MODELO_WORKFLOW_GATE` with `UNHANDLED_EXCEPTION` for `modelo-200-2024-rel-202-pagos-fraccionados`. This is the stored-calculation-drift journey the breakpoint requires to be safe. The CLI must keep that failure on the diagnostic-notice/error-envelope boundary and distinguish pre-activity history from genuinely required Modelo 202 evidence.

| Finding | Tier | Mapping |
| --- | --- | --- |
| Marc empty-draft refusal and populated verification grant | CLOSED | S79 evidence; S80 may consolidate |
| Marc work-list Modelo 349 filter and parser localisation | MINOR | S79 evidence; locale follow-up during S80 |
| S.A. stored-calculation-drift traceback and unavailable verified-complete path | BLOCKER | S79 evidence; S80 must expand before closure |

## W05.P27.S102 ledger, OSS, intracommunity, and wallet rerun

### CLOSED | rich-invoice M349, UK export, and IVA-wallet paths retain explicit evidence boundaries

Fresh Laia, Marc, and Joan personas reached the intended local-only surfaces. UK third-country invoices retained their zero-rated export classification and GB source jurisdiction; the empty IVA wallet remained an explicit zero balance. Rich DE and FR intracommunity invoices produced their one-operator Modelo 349 rows, and invalid French VAT identification failed at the CLI boundary with a precise format remedy. A raw intra-community ledger transaction failed closed with the transaction id, count, and invoice-entry next action instead of silently inventing a 349 operator.

### MAJOR | unresolved OSS sources can be verified and exported as a complete Modelo 369

Laia's fresh Modelo 369 2025/1T work unit saved a zero draft while reporting six `ledger_oss_aggregation` unresolved-source advisories. Verification nevertheless exited successfully and granted `verificado_completo`, enabling export. The advisory admits that source data is unavailable; a zero return under that condition is not a complete OSS result. New W05.P69.S420 owns the fail-closed verification correction and must prove that a disclosed missing-source or zero-source draft cannot gain a complete verification grant.

### MINOR | source mutation after a saved Modelo 349 draft needs a separate invalidation assessment

Recalculating Marc's existing 2025/1T work after adding a same-period raw ledger row returned the original draft unchanged. A fresh 2025/2T control proved the raw-ledger guard itself fails closed, so this rerun does not claim a second calculation defect. S103 retains the observation for the S420 investigation: determine whether saved calculation revisions are deliberately immutable or need source-revision invalidation before treating it as a separate plan item.

### Wave-4 and Wave-5 breakpoint consolidation

The S79 rerun closed Marc's verification and empty-ledger checks but reproduced a Modelo 200 stored-calculation-drift traceback after a normal profile edit; new W04.P70.S421 owns that typed-error-boundary repair. The S102 rerun verified the intended M349, UK-export, and wallet boundaries while exposing the independent Modelo 369 verification MAJOR; new W05.P69.S420 owns it. Both persona evidence steps are complete as observations, and their consolidation steps expand the plan rather than treating the findings as closed.

### s421-stored-calculation-drift-review | low | typed draft-build refusal is independently approved

Independent review approved the narrow `ModeloBuilderError` branch at the workflow draft-builder seam. Known registry/build refusals now become `DRAFT_HAS_ERRORS`, retaining the exact missing relation and a recalculate next action; unexpected exceptions remain on the existing unhandled diagnostic route. The real encrypted-store S.A. CLI replay changes activity-start after calculation, verifies the exact relation refusal and typed error code, and confirms no traceback appears in CLI output or workflow logs.

### s420-unrouted-oss-review | high | source provenance alone cannot certify a Modelo 369 OSS result

The first S420 correction blocks empty OSS catalogues but treats any `ledger_oss_aggregation` provenance as resolved. A positive Italian OSS observation that no current M369 binding consumes still creates such provenance, emits only a transient `unrouted_observation` diagnostic, and leaves all selected values at zero. It can therefore still verify and export unless that unresolved condition is persisted and consumed at verification. S420 remains open: add the real calculate-to-verify-to-export regression for this route, block it, and retain a genuine zero-valued OSS invoice positive control before re-review.

### s420-pre-repair-revision-continuity | high | existing unresolved drafts must not bypass newly persisted source issues

The first persisted-source-issue correction leaves revision identity unchanged. A pre-repair Modelo 369 draft with unresolved unrouted OSS data therefore retains an existing calculation revision without the new issue when recalculated, even though current code would generate one; it can then gain verification and export. S420 remains open until a real existing-draft lifecycle regression proves recalculation backfills the issue or otherwise creates a verification-blocked revision. The follow-up review also requires the persisted source-kind boundary to use the existing typed taxonomy and lifecycle assertions to show the old revision cannot become verified complete.

### s420-oss-verification-resolution | low | all unresolved-source routes now fail closed with immutable revision continuity

The final correction persists a canonical typed source issue only for the positive OSS observation that the current binding set does not consume. Modelo 369 verification blocks that issue as well as a missing OSS provenance row; routed invoices and a genuine zero-valued OSS invoice retain their valid paths. The issue is part of the content-addressed revision identity and registry integrity rehash, so recalculating a real legacy issue-free unresolved draft creates a new current blocked revision instead of rewriting historical evidence. The encrypted-store regression proves that revision remains `BORRADOR` and cannot export; the focused M369 and source-boundary suite passed 16 tests, and final independent review approved.

### s420-direct-legacy-verify-bypass | high | recalculation continuity does not protect an existing current draft

Subsequent independent review found that the continuity regression recalculates the legacy draft before verifying it. A pre-S420 unresolved current Modelo 369 revision can still have OSS provenance and no source issues; direct `work verify` then treats it as sourced and may grant verification/export before recalculation. The prior S420 resolution is superseded, S420 is reopened, and the repair must fail closed on this legacy shape with a direct verify-to-export refusal regression before any recalculation.

### s420-source-resolution-marker-integrity | high | assessment state must be derived and identity-protected

Review of the legacy fallback identified that `source_resolution_assessed` changes whether verification reconstructs source resolution, yet the initial implementation permitted lower-level caller input and omitted the field from revision identity and integrity rehash. A legacy unresolved revision could therefore claim assessment without changing its id and bypass the reconstruction boundary. S420 remains open until the marker is derived exclusively from the source mesh, included in canonical identity and integrity when true, and covered by negative bypass plus legacy routed/zero promotion regressions.

### s420-sealed-source-resolution-resolution | low | Modelo 369 verification now preserves unresolved-source continuity without caller bypass

The final S420 implementation derives source-resolution assessment exclusively from the Modelo 369 source mesh; calculation and persistence callers cannot set it. A true assessment is conditionally included in both revision identity and integrity rehash, while legacy false or absent state keeps its compatible identity. Verification reconstructs legacy source resolution before granting: unavailable and positive-unrouted current drafts stay `BORRADOR` and cannot export; legacy routed and genuine-zero drafts can promote to new assessed revisions. The focused M369/source-boundary suite passed 16 tests, the override-rejection and legacy lifecycle regressions passed, and final independent review approved.

### s420-public-provenance-authority-gap | medium | public calculation inputs cannot establish source-mesh assessment

An additional review found that the public calculation façade still accepts caller-provided source provenance and source issues. A caller can manufacture a `ledger_oss_aggregation` row, make the assessment marker true at persistence, and avoid legacy reconstruction without a real M369 source mesh. The prior resolution is superseded and S420 is reopened: establish the mesh-to-persistence trust boundary by making those facts internal-only or independently recomputed, and add a real public-API/storage bypass regression that cannot verify or export.

### s420-trusted-mesh-boundary-resolution | low | only resolver-derived M369 source evidence can establish assessment

The public `calculate_modelo_revision` façade no longer accepts source provenance or source issues; it supplies empty trusted-source channels. Only the private bucket-mesh bridge receives resolver-derived metadata, and persistence derives the assessment marker from those channels before conditionally sealing it into revision identity and integrity. The real encrypted-store forged-argument regression rejects public provenance injection, leaves the legacy current revision unchanged, and confirms verification/export still refuse. Routed and zero legacy controls remain viable. Both independent reviewers approved; the 16-test focused suite and scoped Ruff pass.

### wave-7-s121-pere-tariff-rerun | low | no-business Catalunya tariff route remains calculable without activity facts

In a fresh encrypted local store, Pere's pensioner-landlord profile retained `activities.description <unset>` and no economic-activity category. The live Modelo 100 2025 calculation saved draft `715b358cf863939c39941136cc8e5a676c68a54d33c3ec474ef0d40c04f0fe14` for work unit `325ea7b76e375a8612fdc49ded897ad60dcf472b67b7173008129831be48060b`, with positive Catalunya tariff casillas `0545=4910.25` and `0546=5132.50` (`0670=10042.75`). The calculation binding payload omitted `renta-2025-modelo-100-estimacion-directa-es-normal`. This independently reaffirms the S419 non-business branch: pension and rental inputs calculate the tariff without an invented activity or estimation regime.

### wave-7-s121-marc-2026-projection-registry-gap | major | public projection is discoverable but cannot cross into an unregistered Modelo 100 year

Marc's fresh autonomous persona created and calculated 2026/2T Modelo 130 draft `0b14631781c04c9c06c8874d292f9961d8867450d06a15cf795d12aa7dd93e29` for work unit `58900fe2c9f3c460befcf8e3222fc48dce91bf28dc5362b274aa669d466cf505`; the empty ledger and the three explicit prior-filing zeros produced no invented activity values. The same live profile's `aeat app modelo iva-wallet balance --as-of-year 2026` returned an explicit queryable zero balance (`total_balance=0`, `active_balance=0`, `expired_balance=0`, `lot_count=0`). The public `aeat app modelo project --year 2026 --ccaa madrid` then refused because no registry revision covers Modelo 100 2026/0A, and direct M100 2026 work creation confirmed no law-determined revision exists. The requested 2026 M130-to-M100 projection is therefore not executable, despite being operator-discoverable; do not mark S121 closed until the W07.P34 consolidation records the disposition. The plan's bare €1,250 gestor phrase has no identified source or live-input basis, so it remains unreconciled.

## W08.P38.S147 Catalan and Hungarian locale rerun

### MAJOR | selected-language CLI journeys still leak English and Spanish operational prose

Fresh Catalan and Hungarian M130 personas used the supported root form `aeat --language ca|hu` across profile, work, verification, status, ledger, and auth-clear journeys in isolated encrypted stores. Normal headings, notices, and empty-ledger output localize, but parser errors retain English `Missing option` and `Invalid value` wrappers. Successful calculation exposes English formula terms such as `subtract`, `max`, `percent`, and `if_then_else` plus Spanish `borrador`; successful verification carries an English advisory and next action. Stable schema keys are not counted as prose leakage. New W08.P72.S423 owns these operator-visible surfaces; S147 is evidence-complete but not a parity pass.

### modelo-100-2026-publication-dependency | low | no official 2026 form or schema is available to register

Official AEAT design material currently identifies Modelo 100 exercise 2025 and its 2025 XSD; the operative current order is Orden HAC/277/2026 for exercise 2025. No exercise-2026 Modelo 100 form or schema is published. W07.P71.S422 is therefore an explicit publication dependency: it will ingest the official revision when released, then prove the 2026 projection, rather than cloning or guessing a legal form.

### s423-locale-verification-identity | high | translated presentation text must not enter persisted verification findings

The first S423 correction translated the pre-activity advisory before building `ModeloVerificationFinding`. Verification report identity is content-addressed from the full findings tuple, so the same revision and actor produced locale-dependent report IDs and durable history. S423 is reopened: retain locale-neutral persisted finding semantics, move advisory translation to the rendering boundary, and add a same-revision cross-locale regression proving stable report identity alongside localized Catalan and Hungarian display text.

### s423-reverify-state-localization | major | selected-language verification refusal leaks canonical lifecycle labels

The persistence-boundary repair is sound, but a fresh Catalan verification followed by Hungarian `work verify` correctly refuses the already verified revision while rendering `verificado_completo` and `borrador` beneath a Hungarian wrapper. The current cross-locale regression only views the Catalan report in Hungarian, so it cannot exercise that real refusal path or prove repeat verification report continuity for a draft that remains ungranted. S423 remains open: localize the CLI projection of the state-gate refusal without changing the canonical domain error, add the already-verified Hungarian refusal regression, and prove same-record identity through a Catalan-to-Hungarian draft/non-granted verification route.

### s423-non-granted-cross-period-projection | major | M390 blocking findings remain English in selected-language verification

The narrowed state-gate adapter repair localizes the already-verified refusal without changing domain persistence, but the real non-granted M390 Catalan-to-Hungarian verification route still renders repeated canonical `cross-period dependency is not clean` blocking findings and English next actions. Its new regression asserts only the stable report id and one stored report, masking the presentation leak. S423 remains open: render this structured canonical blocking finding at the CLI boundary, retain canonical persisted message/action and machine fields, and assert localized blocking message plus next action on both selected-language outputs.

### s423-selected-language-continuity-resolution | low | locale presentation is now isolated from verification identity

The approved repair recognizes the exact canonical structured cross-period advisory or blocking-finding contracts only at the CLI projection boundary. It localizes text and next actions for notices, text output, and JSON while retaining persisted English canonical findings, report identity, kind, severity, legal references, source references, and machine context. A fresh non-granted M390 Catalan-to-Hungarian re-verification produced one report with canonical encrypted findings and localized blocking guidance in both languages; parameterized Catalan and Hungarian retry personas also render the already-verified refusal without raw lifecycle labels. Independent review approved after scoped tests and lint passed.

### s343-article-27-closure-reconciliation | major | a deadline posture is not a statutory recargo assessment

The checked S343 row claims the existing deadline code completes Article 27, but grounded review finds two material defects: completed-month selection applies the 15-percent-plus-interest band on the exact twelve-month anniversary instead of the following day, and every overdue draft is presented as a recargo despite no evidence of actual presentation, positive amount payable, or no prior administrative requirement. The row is reopened. A decision record is required before implementation to separate deadline posture from statutory assessment and define the new evidence boundary.

### s169-period-boundary-drift | major | verification and filing replay diverge from the canonical end-date contract

The full period-token audit proves two live calculation-date errors after S416. For `Period(2026, "03")`, core and the sanctioned domain helper return 2026-03-31 while verification returns 2026-03-01. For Modelo 202 `1P` and `2P`, the sanctioned helper and verification return the AEAT payment-month ends (2026-04-30 and 2026-10-31) while filing replay returns 2026-12-31. S169 remains open: append and execute convergence work that retains the intentional Modelo 202 mapping and proves all consumers agree.

### s169-period-surface-matrix-approved | low | every genuine residual authority has an explicit follow-on

Independent review approved the RAG-grounded classification and direct runtime probes. Canonical adapters, external parser conversions, registry selector syntax, and official wire grammars remain excluded; each genuine date, grammar, ordinal, ordering, settlement, or display survivor maps exactly once to S424 through S431. S169 is evidence-complete and does not claim the repairs are already implemented.

### s424-calc-sheets-layout-compatibility | high | a filing-date correction can alter workbook coordinates

The calculation-sheet export engine uses its own 31 December filing-date default when selecting date-effective tariff rows for the workbook layout. Correcting `EXT-nT` to its legally declared quarter end can therefore alter addresses or row counts, while existing pull metadata omits an engine-version check and may classify a pre-change workbook as matching. S432 owns an explicit layout parity regression and compatibility/re-export disposition; S424 must not silently route old workbooks through shifted coordinates.

### s432-layout-version-guard-resolution | low | stale calculation-sheet layouts now fail before coordinates are read

The public calculation-sheet engine stamp is incremented and included in both metadata classification and the compute-time binding guard. Pull rejects a non-matching workbook immediately after developer-metadata readback, before `plan_layout` or any coordinate/value request. A real Modelo 369 exterior export accepts the live version and rejects the preceding version, while a forged in-memory matching verdict cannot bypass compute-time validation. Independent review approved the 34-test focused suite and scoped lint.

### s424-calculation-filing-date-resolution | low | typed date policy now governs every calculation context

The approved resolver returns contiguous period ends, Modelo 369 exterior quarter ends, sanctioned Modelo 202 payment-month ends, and explicit residual non-span fallbacks without weakening the strict range helper. Verification, filing replay, formula runtime, normal preparation, filed-state and taxation replay, and all Sheets surfaces now consume that single policy. Independent review reproduced the focused 127-test suite and verified that the S432 version guard still rejects a pre-change exterior workbook before coordinate read. S425 remains open for its durable cross-path regression matrix.

### s425-exterior-anchor-oracle | medium | M369 regression needs the legacy year-end contrast

The S425 exterior test proves that the corrected 2021-03-31 anchor does not select the later Modelo 369 exterior revision, but initially omitted the required positive 2021-12-31 legacy contrast. Without both assertions, a path where neither date resolves could pass. S425 remains open until the real registry test asserts the March refusal and the December selection of `esquema-exterior` together.

### s425-cross-path-period-date-resolution | low | non-vacuous period-date matrix is independently approved

The corrected exterior oracle proves both the March 2021 refusal and the December 2021 selection of `esquema-exterior`. The approved matrix also retains real encrypted Modelo 202 calculation-to-draft replay, all contiguous and residual period cases, Sheets export/pull/normal calculation parity, and the S432 stale-layout guard. The focused 71-test suite and lint pass without fake or patched behavior.

### s426-mcp-period-grammar-resolution | low | guided prompts now advertise the canonical finite vocabulary

MCP completions derive from core `accepted_period_codes()`, removing invalid `ANUAL` and exposing the actual finite token set. Prompt descriptions derive from the associated patterns, so `EVENT-N` remains operator-visible as an open grammar rather than a fabricated finite completion. Independent review exercised the real prompt-list and completion handlers and approved the 10-test integration suite.

### s427-prior-quarter-authority-resolution | low | same-ejercicio M130 quarter expansion has one registry owner

The registry offset module now provides the common ordered same-ejercicio prior-quarter anchor sequence. Previous-filing expansion and the Modelo 130 prior-payment advisory delegate to it while retaining their own contextual refusal and first-filer behavior. Independent review approved manually enumerated anchor tests and the encrypted-store 3T advisory proof that names 1T and 2T while excluding the prior-year 4T.

### s428-typed-period-projection-resolution | low | quarterly classification and declaration ordinals have one core contract

Core `Period` now owns ordinary-quarter classification, quarter ordinal, and the established declaration-period ordinal. Modelo 130 projection, declaration binding resolution, and workflow deadline lookup consume those typed projections. Independent review confirmed that extended, instalment, ad-hoc, and event forms remain non-quarterly; real encrypted-store CLI projection and focused core/application suites pass.

### s429-non-iva-history-ordering | medium | IVA consolidation must not lexical-sort generic filed history

The IVA-specific ordering policy is correct, but the first history integration replaced non-M303 numeric-quarter/month/annual-last order with a lexical token key. A direct probe changes `1T, 2T, 10, 0A` into `0A, 10, 1T, 2T`. S429 remains open: retain the new IVA authority for M303 rows and restore the prior generic ordering for all other modelos.

### s429-iva-ordering-resolution | low | M303 uses one IVA order without changing generic history chronology

The repair restricts the IVA compensation ordering authority to Modelo 303 and restores numeric generic ordering for every other model. A mixed real-model regression proves 111 1T/2T/10, 303 4T, and 190 0A are ordered as `1T, 2T, 4T, 10, 0A`; IVA FIFO, wallet sealing, and annual M390 history controls remain intact. Independent review approved the combined 52-test suite.

### s430-annual-settlement-precedence | medium | a later legal annual observation must outrank 4T

The first settlement-predicate migration filtered eligible M303 4T and 0A observations but one prorrata advisory still returned the first repository row, whose iteration order is unspecified. A valid later 0A could therefore lose to 4T. S430 remains open until every eligible selection uses the maximum settlement order and capture time, with a real encrypted-store 4T-plus-0A control proving the annual observation wins.

### s430-m303-settlement-policy-resolution | low | one IVA-law predicate preserves current ingress truth and future annual precedence

The IVA domain now owns M303 settlement eligibility and the shared order key used by every migrated selector. A real encrypted M303/0A ingress attempt correctly raises `ObservationCasillaReferenceError` and leaves no row because the bundled registry has no annual M303 revision; this fail-closed fact is explicit in the execution evidence. The typed policy independently orders 4T before a future legal 0A and latest capture within a period, while real stamped-4T M390 fallback and midyear silence/no-write remain proven. Independent review approved the focused 71-test suite.

### s431-ledger-check-display-oracle | medium | changed ledger check output needs its existing real CLI regression updated

The initial S431 suite covered overview, ledger preflight, and status but omitted the ledger check surface in its changed-output audit. The real encrypted check regression still expected reversed `1T 2026` text after production correctly changed it to canonical `2026 1T`. S431 remains open: update that direct CLI assertion and pin raw JSON/context fields where the check surface emits them.

### s431-typed-period-display-resolution | low | operator display uses canonical typed order without changing machine fields

Overview status plus ledger check, preflight, and status now project human period text through `str(Period)` as `YYYY token`. Real encrypted CLI coverage includes ledger check text and its display-list JSON contract, explicitly excludes reversed output, and separately preserves preflight raw `filing_year`/`code` plus token/year notice context. Independent review approved the full 41-test integration slice.

### s171-period-year-alias | medium | core retains a duplicate period-year compatibility vocabulary

The Wave 9 drift sweep found `Period.year` is an exact alias of the documented canonical `filing_year`, with active production consumers across workflow, overview, modelo, deadline, aggregation, and CLI paths. This has no divergent behavior today but violates the typed canonical vocabulary and no-compatibility direction. S433 owns migration to `filing_year`, removal of the alias, consumer reconciliation, and full period/calendar/workflow/CLI evidence.

### s171-m347-threshold-reexport | medium | a domain row model re-exports a core-owned threshold without owning it

Five cross-package consumers import `M347_THRESHOLD_EUR` from the non-facade `core.external_constants`: the domain row model, application calculation input, application counterpart aggregation, and two calculation-registry binding modules. The row model also republishes it in `__all__`, although ownership remains in core. S434 owns promotion through the core facade, migration of all five consumers, removal of the row-model re-export, and import-boundary evidence.

### s433-period-year-vocabulary-resolution | low | typed periods now expose one filing-year name

`Period.year` is removed and all active typed-period consumers now use `filing_year`. A real isolated-storage CLI journey proves canonical `2026 1T` display and structured `filing_year` plus `code` output, while the core contract rejects the retired alias. The remaining `.year` attributes belong to dates and distinct record models, not `Period`. Independent review approved the focused suites; the local review-adapter master-key mismatch fails before test behavior and is unrelated.

### s434-m347-facade-boundary-resolution | low | the M347 threshold has one public cross-package path

`M347_THRESHOLD_EUR` remains owned by `core.external_constants` and is exposed only through `aeat.core` to its five external production consumers. The domain row model no longer republishes it. A source-level AST regression requires each named production import to use the public facade, rejects the private leaf, and asserts the removed `__all__` export; it avoids relying on object identity. Independent review approved the 61-test focused gate and owned lint.

### s172-cross-period-placeholder-parity | medium | renderer splats hide live locale arguments from static validation

Three live cross-period verification translations received regex `groupdict()` through dynamic keyword splats. Runtime substitution succeeds, but the required placeholder-parity gate cannot prove the arguments and reports fifteen orphan tokens. S436 owns explicit renderer arguments, real persisted-report localization proof, and restoration of the gate without weakening validation.

### s172-language-resolver-docstring | low | a behavior description still names the retired registration mechanism

The language resolver docstring says registration occurs as an import side effect, while the package initializer now calls explicit registration. S437 owns this documentation correction under the required documentation workflow.

### s173-prorrata-register-facade-duplication | high | closed core axes have two unused public facades

`ProrrataProvisionalProvenance` and `ProrrataRegisterRegime` are core-owned closed axes, but domain and application prorrata-register facades also publish them. Production consumers already use `aeat.core`; the duplicate exports are genuine Family-3 hygiene violations. S435 owns removal and source-boundary proof.

### s173-private-test-imports | medium | private imports hide the tested public contract

Seven private import statements in three test modules block the hygiene gate. S438 owns the two non-conflicting test surfaces, migrating public symbols and replacing underscore-helper assertions with real public behavior. The peer-owned prorrata test remains isolated as S439 until its active WIP is stable; no test-only re-export is permitted.

### s174-wave-9-persona-rerun | low | named taxpayer shapes preserve their supported calculation and refusal paths

Fresh encrypted personas created the expected M184 entity work, objective-estimation M131-to-M100 fold, salary and pension M100 paths, and foreign-pension M210 tariff calculation. Source-incomplete M184 rows, incomplete local export layouts, and annual tariff-corpus gaps are explicit registry or publication dependencies; the rerun found no new product defect.

### s435-prorrata-register-core-facade-resolution | low | prorrata closed axes now have one public authority

The domain and application facades retain private core aliases only for internal typing and no longer publish the two prorrata-register enums. A runtime plus AST regression proves `aeat.core` is the sole public owner and the focused duplicate-symbol hygiene slice passes. Independent review approved the 52-test gate and owned lint.

### s438-public-test-boundary-resolution | low | six test imports now exercise supported behavior

The M210 and M303 snapshot tests now import public facades and prove their two formerly private details through persisted verification evidence and public registry validation behavior. Independent review approved the five-test owned slice without a test-only re-export. The hygiene gate still has two separately owned findings: peer-WIP `CalculationSourceDiagnostic` migration is S439, and cross-period renderer test imports are S440.

### s436-cross-period-placeholder-parity-resolution | low | locale rendering is statically provable and persistence-neutral

The three cross-period translation calls now pass explicit placeholder arguments, restoring static parity validation. A real encrypted M390 workflow persists the report, renders Catalan blocking and advisory findings through notices, typed payload, and text lines, reloads it, and exactly compares every canonical message and next action. Independent review approved the 1-test persisted workflow, 3-test parity gate, and 10-test CLI integration slice. Private renderer imports in a separate legacy test remain owned by S440.

### s440-public-renderer-test-resolution | low | localized cross-period tests use only the public CLI

The legacy cross-period test now drives root `work verify` in Catalan JSON and text rather than importing private renderer helpers. Its encrypted M390 journey proves localized blocking and advisory output while reloading and preserving canonical evidence. Independent review approved the real public behavior; no new renderer facade exists.

### s439-prorrata-test-import-resolution | low | the final hygiene import reaches its existing public facade

After confirming the deferred test file was clean, its diagnostic type import moved to `aeat.application.aggregation`, which already owns the public facade. The live prorrata suite and the complete 11-test import-hygiene gate pass; independent review is recorded with the step evidence.

### s189-annual-deadline-tax-year-key | high | registry discovery and workflow schedule selected different annual-window keys

Modelo 100 2020/2021 and Modelo 180 2024/2025 retained their correct following-year legal dates but stored campaign years in `filing_year`. Raw calendar discovery can list those rows, while the deadline engine and workflow gate query by the work unit's tax year and omit their own deadlines. S441 and S442 own independent tax-year-key repairs and direct engine/workflow proof.

### s190-wave-10-calendar-personas | low | supported deadline registry entries appear and applicability suppression remains honest

Fresh encrypted personas exposed the expected W10 M100, M111, M131, M180, M200, M202, M349, and M390 deadline entries. M232 remains a suppressed incomplete entry without qualifying related-party facts rather than a false obligation. This registry-discovery pass does not replace the separate workflow-selection repair required by S441 and S442.

### s441-s442-annual-deadline-key-resolution | low | annual campaigns are keyed by tax year and retain their legal dates

M100 2020/2021 and M180 2024/2025 annual windows now use their tax/work-unit years as registry keys while preserving every official campaign opening, close, and direct-debit date. Direct DeadlineEngine coverage and real M100 work-plazo plus M180 workflow runs prove each tax year selects its following-year campaign. Independent review approved 93 focused tests. A stale explanatory phrase is separately owned by S443.

### s355-modelo-303-casilla-61-legal-conflict | high | local IVA prose names a route absent from the current official form

The bundled 2023-y-siguientes registry and current AEAT Modelo 303 instructions move from casilla 60 to 120, while `Art20Uno26` still claims it routes to casilla 61. Older AEAT material did include a different casilla 61, so neither adding a new current-form field nor silently deleting the claim is legally safe. S444 owns formal legal reconciliation and a decision before behavior changes.

### s365-negative-base-general-carry-resolution | low | Art. 50 carry and Art. 48 base-imponible mechanisms are separated

The M100 carry path now consistently applies LIRPF Art. 50 to prior 1391, opening 1388, taxpayer-applied 1389, computed 0501, and 0500. Art. 48 remains only on the distinct 0432-to-0433 base-imponible formula. A real encrypted-store two-run regression proves that 2,000 on 1389 computes 0501 at 2,000, reduces 0500 by 2,000, and leaves 0435 unchanged; 2024 and 2025 legal-reference guards agree. Independent review approved the 13-test application slice and 18-test catalogue validation.

### s370-workflow-next-action-projection-resolution | low | recovery prose localizes without entering encrypted workflow history

The engine stores canonical recovery summary and next-action values. Public `work runs` projects recognized final-step prose in Catalan and Hungarian text/tab and JSON while retaining command tokens, run identifiers, stages, and reasons. A real encrypted run is reloaded before and after both language projections and remains byte-equivalent; verification-report tabs use the same CLI-only localization boundary. Independent review approved 13 cross-locale persisted-run, 23 workflow/renderer, 3 parity, and 8 command-conformance tests.

### s445-annual-deadline-exact-key-resolution | low | unknown annual work cannot borrow a successor campaign

Plazo and overview consumers now require exact modelo, tax/work-unit year, and period-token matches, like DeadlineEngine and workflow. Real M180 2023 and M100 2019 annual units return no window rather than borrowing M180 2024 or M100 2020; valid successor windows retain their legal campaigns. Independent review approved the 74-test deadline/overview slice and preserved concurrent typed-period WIP.

### s343-fallback-preview-wording | low | no-preview fallback says that a rate preview is displayed

`_work_unit_deadline_output_from_posture()` intentionally supports an overdue posture whose conditional rate preview could not be resolved, and its payload correctly leaves `conditional_recargo_preview` null. Both that fallback and the real-preview branch use `plazo_vencido_warning`; every shipped translation says that the displayed rate is an unassessed preview. A direct runtime probe with `ModeloWorkDeadlinePosture(closes_on=date(2026, 1, 30), days_overdue=1)` produced the Spanish displayed-rate wording while its payload contained no preview. This does not assert Article 27 liability, but it is a false operator statement and leaves the text/locales semantically misaligned with the JSON fallback. Split the no-preview warning from the preview wording, localize both, and add a fallback text regression before closing S343.

### s343-fallback-preview-wording-resolution | low | null preview now receives a distinct no-rate warning

The renderer now selects `plazo_vencido_sin_previsualizacion_warning` whenever `conditional_recargo_preview` is absent, for both tab text and JSON notice projection; the preview-present branch retains the explicitly unassessed-preview wording. All four shipped locales define the new no-preview key without a displayed-rate claim. A direct runtime probe again produced `conditional_recargo_preview: null` and the Spanish message only says that the application does not determine Article 27 surcharge or interest liability. The focused real renderer regression asserts the null JSON field and absence of both English displayed-rate and Spanish preview wording; it passed with the integration marker enabled. This resolves the fallback semantic mismatch without turning the posture into an assessment.

## Recommendations

- Preserve the one-record-per-checked-step linkage; do not fabricate a record from current code inspection.
- Add a focused Modelo 111 regression that pins every 2026 quarterly deadline date, including the January 2027 close for 4T.
- Run the still-open W09 and W10 closure work, then reassess the W11 terminal gate with new persona and drift evidence.
