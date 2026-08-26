---
generated: true
tags:
  - '#index'
  - '#conformance-cli'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:96bb51461c40e331b5ba6d3ec2bae42633d2a9f4d7f41bb7ee8b15ff17218565'
related:
  - '[[2026-07-27-conformance-cli-adr]]'
  - '[[2026-07-27-conformance-cli-fact-lifts-and-boundary-gate-audit]]'
  - '[[2026-07-27-conformance-cli-governance-stamp-and-classification-audit]]'
  - '[[2026-07-27-conformance-cli-plan]]'
  - '[[2026-07-27-conformance-cli-research]]'
  - '[[2026-07-28-conformance-cli-campaign-close-honesty-review-audit]]'
  - '[[2026-07-28-conformance-cli-first-conformance-measurement-audit]]'
---

# `conformance-cli` feature index

Auto-generated index of all documents tagged with `#conformance-cli`.

## Documents

### adr

- `2026-07-27-conformance-cli-adr` - `conformance-cli` adr: `derived conformance facts in src, governance CLI in dev, one-way boundary` | (**status:** `accepted`)

### audit

- `2026-07-27-conformance-cli-fact-lifts-and-boundary-gate-audit` - `conformance-cli` audit: `fact lifts and boundary gate`
- `2026-07-27-conformance-cli-governance-stamp-and-classification-audit` - `conformance-cli` audit: `governance stamp and classification coherence`
- `2026-07-28-conformance-cli-campaign-close-honesty-review-audit` - `conformance-cli` audit: `campaign-close honesty review`
- `2026-07-28-conformance-cli-first-conformance-measurement-audit` - `conformance-cli` audit: `first conformance measurement`

### exec

- `2026-07-27-conformance-cli-P01-S01` - add the RevisionReviewStatus StrEnum (pending_review, agent_reviewed, operator_reviewed) to the core closed-value-set surface and export it through the core facade
- `2026-07-27-conformance-cli-P01-S02` - add optional governance scalars engineered_by, review_status, reviewed_by, reviewed_at to ModeloRevision with a model validator refusing reviewed_by or reviewed_at unless review_status is beyond pending_review, absence defaulting to pending_review
- `2026-07-27-conformance-cli-P01-S03` - hydrate the governance scalars from revision.toml in the TOML compiler, rejecting unknown or misplaced governance keys loudly
- `2026-07-27-conformance-cli-P01-S04` - add governance-stamp loader tests covering roundtrip, fail-closed default on absence, refusal of incoherent stamp combinations, and an anti-tautology mutation proof
- `2026-07-27-conformance-cli-P01-S33` - refuse a blank or whitespace-only reviewed_by and engineered_by so a stamp cannot claim signoff while naming nobody, bound reviewed_at against a future date, and tighten the bundled-tree invariant from not-null to non-blank
- `2026-07-27-conformance-cli-P01-S34` - derive the governance field set from a marker on the field declarations so a fifth governance scalar enrols itself into the placement refusal instead of silently escaping it
- `2026-07-27-conformance-cli-P01-S35` - derive the embedded core-type set for the compiled cache key from the compiled models annotations rather than a remembered hand list, or assert the derived set is a subset of the list, covering the ten unenrolled types including the core Modelo enum
- `2026-07-27-conformance-cli-P02-S05` - lift the registry-wide external-oracle grounding fold (per-modelo oracle inventory, revision selection, both-direction honesty facts) into a new importable module exported through the registry facade
- `2026-07-27-conformance-cli-P02-S06` - re-point the external-oracle grounding gate at the lifted library in the same commit, keeping both honesty directions asserted
- `2026-07-27-conformance-cli-P02-S07` - extract the fichero-BOE required-applicable casilla derivation into one shared public function consumed by the export gate
- `2026-07-27-conformance-cli-P02-S08` - re-point the export completeness and fichero-BOE parity tests at the shared required-set derivation, removing the mirrored duplicate
- `2026-07-27-conformance-cli-P02-S09` - add the classification-coherence checker (calculation_class vs tax_domain vs core modelo constants, plus the declared-but-dead axis census) as an importable typed fact-builder
- `2026-07-27-conformance-cli-P02-S10` - add the per-revision conformance profile composer with strict typed row models, composing model-law coverage, support matrix, registry-scope diagnostics, authorization state, external grounding, and governance stamps
- `2026-07-27-conformance-cli-P02-S11` - add structure-and-wiring tests for the classification-coherence checker grounded in the live registry tree
- `2026-07-27-conformance-cli-P02-S12` - add structure-and-wiring tests for the conformance profile composer, asserting provenance fields and degraded-mode labelling, never author-invented numeric expectations
- `2026-07-27-conformance-cli-P02-S25` - widen the oracle attribution rule to read the payload declared modelo and filing year rather than keying solely on the filename, once the malformed payload and the casilla 44 modelling have landed, so the corpus enters the honesty relation without false positives
- `2026-07-27-conformance-cli-P02-S26` - restore an independent registry-grounded oracle for the fichero-BOE required-applicable set so a relaxation of the predicate in either direction flips an assertion, remediating the review finding required-set-oracle-collapse
- `2026-07-27-conformance-cli-P02-S28` - parse each bundled oracle payload through a strict typed model so the declared source_kind token actually hydrates and an unknown token refuses at the boundary, removing the last untyped mapping read in the grounding fold
- `2026-07-27-conformance-cli-P02-S30` - split the scenario input figures out of the M303 prorrata oracle expected-by-casilla map and rename the payload to carry its filing year so its genuine expected figure enters the honesty relation
- `2026-07-27-conformance-cli-P02-S31` - correct the prorrata percentage rounding from the shared integer code, which rounds half-up, to a rounding that always rounds upward as LIVA article 104.Dos.2 requires, adding the new rounding code rather than changing the shared vocabulary
- `2026-07-27-conformance-cli-P02-S36` - bind the classification finding detail bound to the field it mirrors and add the missing case whose single blocker exceeds it so the truncation branch is proven rather than reasoned
- `2026-07-27-conformance-cli-P03-S13` - build the pure manager composing the src fact facades plus ModeloLocaleManager coverage rows, with typed payload models and a self-labelling no-validate degraded mode
- `2026-07-27-conformance-cli-P03-S14` - build the Typer cli and __main__ with report and coverage verbs, greppable key=value text rows and strict --json payloads
- `2026-07-27-conformance-cli-P03-S15` - add the audit verb with --check gating exit, shrink-only JSON baseline, anti-vacuity floor, and empty-input SystemExit refusal
- `2026-07-27-conformance-cli-P03-S16` - add the stamp verb writing the per-revision governance scalars with vocabulary and coherence validation
- `2026-07-27-conformance-cli-P03-S17` - add dev-side CLI behaviour tests covering every verb, the ratchet, the vacuity refusal, and the degraded-mode labelling
- `2026-07-27-conformance-cli-P03-S29` - surface unattributed oracle payloads and unmatched evidence as report and coverage rows with a shrink-only floor so the attribution gap gains a reader instead of remaining a field nothing consumes
- `2026-07-27-conformance-cli-P04-S18` - add the dev-path isolation gate asserting no shipped module imports dev.* or embeds a dev/ path literal, with an injectable-root anti-tautology proof
- `2026-07-27-conformance-cli-P04-S19` - add the dev-side pytest wrapper gate running the conformance audit --check against the committed baseline
- `2026-07-27-conformance-cli-P04-S21` - wire a conformance recipe invoking python -m dev.registry.conformance report and audit into the task runner
- `2026-07-27-conformance-cli-P04-S27` - widen the dev-path literal detection to the realistic PROJECT_ROOT join, os.path.join, f-string and backslash forms, invert the test that pins the hole open, and mirror the missing shipped conftest case, remediating the review finding dev-path-literal-hole
- `2026-07-27-conformance-cli-P05-S32` - amend the ADR boundary wording to name every wheel-shipped module under src/cadrumo and rule the two open questions on single-versus-dual boundary-detector authority and on whether the filing-year grounding resolver belongs on the public registry facade
- `2026-07-27-conformance-cli-P01-S43` - add a fixed lower bound to the signoff horizon so a review dated before the revision existed refuses, mirroring the ceiling that already catches the far-future sentinel
- `2026-07-27-conformance-cli-P02-S38` - declare the prorrata percentage casilla in the external grounding claims now that both preconditions of the oracle-evidence rule are satisfied and verified, so the AEAT manual figure becomes an enforced independent check
- `2026-07-27-conformance-cli-P02-S40` - take the filing-year grounding resolver off the public registry facade or rename it so it cannot be mistaken for the law-determined resolver, implementing the ADR ruling that currently has no code
- `2026-07-27-conformance-cli-P02-S44` - carry the validated label onto the classification row and finding models so a degraded read stays labelled when its findings are flattened, implementing the ADR ruling on row-level labelling
- `2026-07-27-conformance-cli-P02-S45` - bind the registry prorrata percentage formula to the domain prorrata function with a parity gate over ratios that discriminate between the two roundings, closing the two-authorities condition that hid the rounding defect
- `2026-07-27-conformance-cli-P02-S47` - reconcile the zero-volume prorrata branch between the two M303 revisions, where the older revision returns zero and would zero every deduction for a fully-taxable trader who declared no prorrata volumes, grounding the correction as the newer revision already does
- `2026-07-27-conformance-cli-P02-S48` - correct the prorrata module docstring and rounding comment which cite the autoconsumo article rather than the article that actually establishes the formula and the upward rounding, so a reader sent to it finds the rule
- `2026-07-27-conformance-cli-P02-S58` - correct the especial-prorrata mandatory predicate which applies a strict greater-than where the law says exceeds by ten percent or more, so exact equality currently fails to trip a mandatory regime switch
- `2026-07-27-conformance-cli-P02-S59` - declare the full-right-to-deduct article on the prorrata formula legal refs of both M303 revisions rather than only on the enclosing construct, as a coherent two-revision change
- `2026-07-27-conformance-cli-P02-S72` - model the M303 regularizacion prorrata cuota casilla as computed with the AEAT manual figure as its external oracle expectation, the under-declaration-shape gap that fell out of tracking when its tracking step was re-scoped to other work
- `2026-07-27-conformance-cli-P02-S80` - lift the export-format closed set from a bare Literal on the export-layout schema to a core StrEnum so the per-modelo support matrix and the per-revision conformance fold compare enum members rather than each re-spelling the same tokens
- `2026-07-27-conformance-cli-P03-S39` - coerce the review status at the stamp writer function boundary so handing it the core enum member raises instead of writing an operator signoff, and prove the refusal leaves the manifest byte-identical
- `2026-07-27-conformance-cli-P03-S42` - gate the operator backlog rather than the pending backlog by adding a shrink-only ceiling on revisions lacking operator review, so the one number CI protects cannot be moved by an act the tool can perform
- `2026-07-27-conformance-cli-P03-S46` - render the reviewer attribution with its review tier attached so an agent-tier review naming a person cannot be read as an operator signoff when scanning rows
- `2026-07-27-conformance-cli-P03-S53` - apply the vocabulary refusal to the effective review status resolved from the manifest, not only the requested one, so an agent cannot re-attribute an existing operator signoff to itself while leaving an authorship-only write legal
- `2026-07-27-conformance-cli-P03-S54` - write and roll back the manifest through raw bytes so a refused stamp truly restores the file rather than rewriting every line ending, and assert the restoration on bytes instead of normalised text
- `2026-07-27-conformance-cli-P03-S55` - reconcile the reviewer column between the text and JSON surfaces so one key name never carries two different values, and refuse a reviewer value containing the tier separator so the qualified form stays unambiguously parseable
- `2026-07-27-conformance-cli-P03-S57` - compare a recorded baseline against the committed one and surface every counter moving in the weakening direction, and re-anchor the seed invariant to a freshly measured ceiling so the first genuine operator signoff does not red it
- `2026-07-27-conformance-cli-P03-S62` - write the conformance baseline through raw bytes as the manifest writer now does, closing the same line-ending defect in the second dev-side writer where the on-disk artefact the gate reads already differs from its committed bytes for every reader that is not git
- `2026-07-27-conformance-cli-P03-S63` - default the review date on a reviewer-only restatement so a re-attributed review cannot inherit the previous reviewer date and record a person as having reviewed on a day they did not
- `2026-07-27-conformance-cli-P03-S64` - read the declared review status off the compiled revision the writer already loads rather than off the manifest text, so the signoff guard stops depending on the fragment refusal it exists to complement
- `2026-07-27-conformance-cli-P03-S65` - give the stamp CLI command an injectable registry root so its own date defaulting and error translation can be exercised without writing to the shipped registry, and correct the coverage pragma that calls a reachable branch unreachable
- `2026-07-27-conformance-cli-P03-S67` - refuse a stamp write against the bundled registry tree or require the root explicitly, closing the hazard that let a test mutation write a fabricated review into the shipped modelo manifest
- `2026-07-27-conformance-cli-P03-S77` - rebase the three population-pinned governance ceilings onto ratios or deltas so an honest new revision does not red the only gate and force the operator to assert they are weakening the ratchet
- `2026-07-27-conformance-cli-P03-S79` - retire the dev registry matrix package whose manager recomputes ten capability fields the public build_support_matrix already returns on ModeloEntry, sweeping its test-lane entry, its tests, the two shipped docstrings that cite it as their mirror and the planted-import fixtures naming it
- `2026-07-27-conformance-cli-P04-S20` - regenerate the API reference stubs for the new src modules via the apidocs scaffold CLI and land the deltas with the source change
- `2026-07-27-conformance-cli-P04-S41` - consolidate the boundary detection onto the single hygiene scanner authority the ADR chose, deleting the duplicated inline import detector and its stale pending-ruling heading while keeping the injectable-root proof local
- `2026-07-27-conformance-cli-P04-S56` - pin the two detector branches whose individual mutation flips nothing with fixtures for an interpolated device path and an interpolated mid-path segment, and either delete the two redundant branches or correct the docstring that credits one with protection a different mechanism delivers
- `2026-07-27-conformance-cli-P04-S68` - write the two sibling audit baselines and the generated api stubs through explicit newline handling, and fix the stub drift check which reads with universal newlines so a translated stub compares equal to the writer that translated it
- `2026-07-27-conformance-cli-P04-S78` - give the conformance tool a reachable operator page covering the stamp vocabulary, the operator-signoff hand-edit path, the registry-root flag and the baseline re-record procedure, since the prose exists only inside module docstrings
- `2026-07-27-conformance-cli-P05-S22` - run the full-tree collect-only gate and the scoped registry, filing, and dev suites, recording failure signatures and triaging owner vs peer churn
- `2026-07-27-conformance-cli-P05-S23` - run the first real conformance report over the bundled registry and persist the findings as a vault audit document
- `2026-07-27-conformance-cli-P05-S24` - run the fresh-context campaign-close honesty review and track every surfaced item as a new step or a formally deferred follow-up
- `2026-07-27-conformance-cli-P05-S37` - extend the fragment placement refusal to the remaining legally load-bearing revision scalars legal_refs, orden_aplicabilidad and valid_to, closing the last instance of the readability hazard the governance refusal proved worth closing
- `2026-07-27-conformance-cli-P05-S49` - absorb the three tree-wide gate regressions this campaign caused, moving the module marker above the assignment, replacing the bare encoding literal with the shared constant, and extracting a cohesive concern out of each module that broke its size ceiling rather than lifting the ceiling
- `2026-07-27-conformance-cli-P05-S50` - eliminate the monkeypatch machinery from the burned-version ledger tests and the registry snapshot freshness tests without weakening what either test proves, honouring the recorded trap that a threaded authority parameter lets a naive cache key stop colliding so the behavioural test passes with the defect present
- `2026-07-27-conformance-cli-P05-S51` - eliminate the fake-named bindings from the sanitizer residual-identity test, reconcile the test-debt baseline the same test broke, and replace the bare encoding literal in the legal attribution screen
- `2026-07-27-conformance-cli-P05-S52` - reconcile the registry revision diff test whose changed-formula expectation this campaign moved when it corrected the prorrata rounding on both M303 revisions, fixing whichever side is actually wrong rather than re-anchoring the test to make it pass
- `2026-07-27-conformance-cli-P05-S60` - widen or retire the single-filing-year M303 regression that pinned only the newer revision, which is what let the older revision keep returning a zero prorrata percentage undetected
- `2026-07-27-conformance-cli-P05-S61` - extract the verification-predicate concern out of the registry schema module, which now sits one line under its size ceiling so the next peer edit reds a gate they did not break
- `2026-07-27-conformance-cli-P05-S66` - take the whole verification-predicate concern out of the registry schema module in one commit that also owns and removes its size-budget baseline entry, since the concern is larger than the pinned band allows and half-taking it would scatter one concept across two modules
- `2026-07-27-conformance-cli-P05-S69` - measure and gate the tree-wide terminator drift where over a thousand tracked files carry on-disk bytes differing from their committed bytes while git diff stays silent, so the class is bounded rather than known only anecdotally
- `2026-07-27-conformance-cli-P05-S70` - replace the operator real name with a non-identifying stand-in throughout the conformance CLI test module, closing the committed privacy violation this campaign introduced which reds the per-push lane
- `2026-07-27-conformance-cli-P05-S71` - restate the two test docstrings that cite this project development records as self-contained engineering reasoning and move the discovery-waiver process note out of source, honouring the one-way rule that code never cites the vault
- `2026-07-27-conformance-cli-P05-S73` - author a decision record governing the IVA prorrata corrections this campaign made and list it on the plan, since eleven steps changed computed tax outcomes under an ADR that authorises only a governance surface
- `2026-07-27-conformance-cli-P05-S74` - rule the capability-fact duplication between the conformance composer and the registry matrix CLI, which independently recompute the same predicates, applying the single-authority answer this campaign already chose for the boundary detector
- `2026-07-27-conformance-cli-P05-S75` - correct the two step records that misstate their own state, one claiming this campaign left the tree-wide gates clear and one closing while its stated precondition had not landed
- `2026-07-27-conformance-cli-P05-S76` - open a follow-up feature tracking the four measurement-audit recommendations so ninety unreviewed revisions, twenty-four classification divergences and five unused schema axes have an owner rather than living as prose

### plan

- `2026-07-27-conformance-cli-plan` - `conformance-cli` plan

### research

- `2026-07-27-conformance-cli-research` - `conformance-cli` research: `modelo schema conformance governance mini-CLI`
