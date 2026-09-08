---
tags:
  - '#reference'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:2e0230aaf787d4ca4e859bbb95c6bf66174c316ad8c84ac90d6a830c231d2a70'
related: []
---
# `reachability-burndown` reference: live signals and cadence

## Scope

The shipped package carries modules and symbols no declared product command reaches.
`dev.audit.unreachable_code` walks the import graph from `[project.scripts]`; the
quality gates project its current findings without accepting a baseline, frozen prefix,
status, disposition, or module-specific exception.

## Live measurements

## Live measurements

Measured 2026-09-07 from the zero-target gates:

| Signal | Current findings | Target |
| --- | ---: | ---: |
| Modules no product command reaches | 32 | 0 |
| Exact unused symbols | 381 | 0 |
| Orphaned test modules | 20 | 0 |
| Exact unused exports with no production importer | 262 | 0 |
| Concrete TUI interfaces with no render surface | 8 | 0 |

The numbers are observations, not thresholds. They are never copied into gate inputs.
Each gate fails while its live finding set is non-empty and names every current finding.

## Signal-burndown cadence

For each Step:

1. Re-run the owning live detector and select one current finding or one coherent
   mechanically-derived cluster.
2. Ground the responsibility semantically against production code and accepted ADRs,
   then confirm exact imports, exports, declarations, and tests with structural search.
3. Resolve the finding through the mechanism that owns it: connect a required product
   path, relocate development-only machinery outside the shipped package, delete a
   displaced or abandoned implementation with its tests, or correct the detector when
   its structural inference is false.
4. Run the smallest gate that proves the resolution and its detector-teeth controls.
5. Record the changed files, focused verification, and newly measured live count in the
   Step Record; close the Step only through the plan verb.
6. Add the next Step only after remeasurement. Amend an ADR when the evidence contradicts
   its decision, and strengthen a detector when a defect class escaped it.

No Step is closed by increasing a threshold, recording a baseline, adding an allowlist,
freezing a namespace, or assigning a development status to a production identity.


A new detector's first non-empty result is a candidate population, not an implementation worklist. Before migrating any finding, sample each recurring AST role and prove the detector distinguishes regulatory policy from algebraic identities, unit conversions, schema bounds, documentation, and grammar literals. Narrow by semantic syntax shared across the class, add both positive and negative planted controls, and remeasure. Never encode the sampled paths, symbols, values, or adjudications as exclusions. The refined detector's remaining identities become the live backlog only after this calibration.

A writerless-store finding is resolved at the product boundary before its ratchet is removed. If an accepted ADR allowed readers, schemas, storage, or domain types to ship ahead of the acquisition path that makes them real, amend that ADR and delete the entire partial feature; synthetic roundtrips do not establish production reachability. Retain the detector as an aggregated zero-target gate, and prove both arms with the same planted surface: absent writer is red, live writer is green.

A dangling-reference baseline is still a list of production identities with development dispositions, even when the prose accurately describes deleted history. Preserve historical names as ordinary code literals rather than resolvable documentation roles, correct claims that name a replacement that never shipped, and let the structural reference scanner enforce live zero directly. The detector and the gate should be one execution path so an advisory screen cannot stay green while a separate count ledger absorbs its findings.

Before wiring an unreached reporting helper, prove that the owning live pipeline actually possesses every distinction the report claims. A captured item is not necessarily a selected winner, and a gap may mean supersession, a capture failure, finalization refusal, or an unattempted row under a limit. If the canonical owner does not expose enough evidence to distinguish those states, do not add parallel bookkeeping merely to activate the helper: delete the speculative model, projection, renderer, locale leaves, and identity-only tests together. Detector proof for retained selection reporting must drive real duplicate, limit, and failure paths through the owning selector.

A buildable policy with dedicated allow/refuse tests is still unreachable safety machinery when the live operation never consults it. Wire the guard immediately before each remote mutation—not merely at provider construction—and give detector-teeth proof that a forced refusal prevents the corresponding call. For multi-action flows, exercise every action position so an early guarded operation cannot conceal an unguarded later mutation.

After deleting an unreachable wrapper or builder, remeasure the owning module before closing the Step. Private constants and one-use construction aliases can become unreachable only after the outer symbol disappears, so a pre-edit census cannot reveal the whole coherent cluster. Collapse those aliases into the remaining live owner when they add no domain meaning, and keep behavioral tests over the live output rather than replacing the deleted implementation with a name inventory.

A self-tested persistence substrate is still abandoned when no product repository or composition root calls its read/write pair. Remove the complete wire model, version marker, migration helper, derivation aliases, and self-tests together; retain only shared primitives with independent live consumers. Update structural detector vocabularies by semantic category, and classify unrelated live inventory drift separately rather than widening or silently repairing it inside the withdrawal step.

A production registry must expose only lifecycle operations that product callers need. Test-only count or snapshot diagnostics are development metastate even when they inspect a live security boundary: remove them and prove registration, idempotence, and weak ownership through observable sealing, zeroised buffers, sweep results, and object collection instead.

A live one-way representation does not justify a reverse codec merely to prove its own roundtrip. Ground the consumer boundary: when the product deliberately treats an emitted recovery phrase, token, or artifact as an opaque value, retain canonical generation and validate it against an external vector or live consumer contract; delete a test-only decoder, reverse index, validation branches, and roundtrip tests together. If an accepted ADR prescribed the symmetric API before the live flow settled, amend that implementation prescription rather than preserving the unused half.

A runtime-checkable protocol with one concrete implementation is not an application port when no production consumer accepts or returns the protocol type. If only an `isinstance` self-test and export census use it, delete the duplicate interface and name the sole live owner directly in annotations and documentation. Retain a protocol only where substitutability is exercised by a composition boundary, not to mirror methods already declared by one class.

A production `*_ALLOWED_COLUMNS` aggregate used only by a cross-cutting coverage test is a development census even when every member is accurate. Derive the test population from the live row schema (`model_fields`) or the runtime parser authority, and keep only subsets the product itself consumes for required-field refusal or dispatch. Detector proof must move when the executable schema moves without requiring a mirrored constant edit.

## Authority boundaries

A production setting or public parameter that is read only to be discarded is development metastate even when its name describes plausible future policy. Delete the configuration field, parameter, environment spelling, and self-referential tests together; keep the invariant at the live schema or execution mechanism that already enforces it. A focused contract test should assert the dead switch is absent from both the callable signature and the settings model, which gives the removal detector teeth without maintaining an identity list.

The same rule applies to result-schema fields reserved for a future execution mode. If the owning path fails fast and can never populate the field, a constant default is not a product fact; it is an implementation-plan placeholder serialized to every consumer. Delete it from the model and prove absence at both schema and serialized-output boundaries rather than retaining a zero-valued compatibility promise.

An exception class with no raise or catch path remains production metastate when its only rationale is a hypothetical future failure. Delete the class atomically with its central error-code registration and localized messages; otherwise each mirror independently makes the nonexistent failure look shipped. Verify the error-subclass registry after deletion and use the locale owner for catalogue edits, while classifying unrelated pre-existing locale drift separately.

Operator-facing refusals must describe the product invariant and the available recovery action, never the implementation team's missing or future work. When behavior is already intentionally fail-closed, replace “not implemented” wording in both the internal refusal and every localized rendering with the actual immutability or unsupported-operation contract; verify the owning behavior suite so a prose cleanup cannot accidentally weaken the refusal.

A uniform callable signature is not an authority when sibling implementations delete or ignore parameters solely for dispatch convenience. Replace tuple-driven polymorphism with explicit calls when the variants consume different evidence, then remove each no-op argument from its production signature. Detector teeth belong at the signature boundary: assert each implementation accepts exactly the inputs it evaluates while the variant that owns the extra evidence retains them.

A public-looking helper used only by its own tests and documentation is not a product contract. When the real application path already uses a stronger content-validating mechanism, delete the weaker orphan helper, its dedicated tests, and its prose atomically. Confirm that the application still calls the authoritative mechanism and that exact search finds no remaining reference; do not preserve the abandoned helper as a compatibility surface without a production consumer.

An inventory test must protect a semantic class, not require a named production alias to exist. If a shared authority already owns the value and no product caller uses the local alias, delete the alias and its identity-specific existence or uniqueness test. Keep the class-level literal detector with discriminating positive and negative controls, expressed against the shared authority, so reintroducing the underlying duplication still fails without maintaining a census of approved names.

A layered port does not establish product reachability when no composition root supplies its adapter and no command or UI consumes the application verb. Treat an adapter wrapper, application protocol, application verb, exports, and integration-style tests that call one another as one abandoned slice when their only stated consumer is a hypothetical setup suggestion. Delete the slice atomically, then run the neighbouring live registration, health, and parsing suites to prove the owning product capability remains intact.

A test-only public alias remains duplicate vocabulary when its target is imported rather than locally defined. Alias detection must treat imports as module bindings and flag any public assignment whose second spelling has test consumers but no production consumer. Prove both locally-defined and imported-target cases with planted controls; migrate tests to the canonical defining module, and let any newly exposed owning-mechanism failures remain live rather than restoring a deferred or accepted-set wrapper.

Route-ownership gates must distinguish scalar calculation bindings from row-producing bindings. A binding with aggregation operation `rows` is executed by the detail-row and export channel and must not be admitted through a fake scalar resolver or deferred-source census. Derive the population from the binding's typed aggregation operation, prove an invented scalar source stays red and an invented row source does not enter that gate, then pursue any remaining scalar source through its actual resolver or registry input mechanism.

When official evidence requires an exported total but research proves there is no secure source owner, do not retain a bound scalar declaration behind an ingress-blocked or deferred census. Remove the unsupported scalar binding and its unreachable resolver, keep the official casilla required as explicit manual input, and preserve separately executable repeated-row bindings. Detector teeth must prove the total has no binding while every surviving family binding uses the row aggregation operation.

A production command declaration may own executable transport facts, but it must not also carry a campaign census assigning each command a reviewed architectural disposition such as transport-only, mixed, or policy-bearing. When the governing ADR defines the boundary positively by code shape, delete the disposition enum, per-command annotations, derived census projection, and identity-pinning tests together. Keep the live command graph as the product authority and let the development detector derive boundary violations from behavior; an exhaustive adjudication ledger is evidence for a plan or reference, never shipped behavior.

A security invariant enforced by default-deny does not need a production registry of paths classified as never exempt. Derive the protected leaf from the live command graph in the focused gate and exercise the actual exemption matcher, including prefix swallowing. Delete companion implemented, not-yet-mounted, or future-path ledgers: they are development lifecycle state, and once the command exists they are weaker than the executable graph they duplicate.

## Authority boundaries

The source tree owns executable product behaviour and product contracts. Development
tools may inspect those authorities but do not make production code cite a campaign,
quality gate, fixture harness, or temporary implementation state. Development-only
prototypes and render fixtures belong outside the shipped package.

Plans and Step Records are the sole home for temporary campaign state. Neither product
code nor development tooling may maintain a second list of module, symbol, action,
screen, provider, source, or fixture identities labelled implemented, in-flight,
deferred, ignored, intentional, superseded, or equivalent. A quality gate derives its
current finding set from executable authorities on every run and reports that set
verbatim; an empty derived set is its only closure condition.

When an older decision made development metastate a product input, remove it atomically:
amend the governing ADR, detach every production consumer, delete the list and its
reader, and leave any newly exposed live findings red for their owning mechanism. Do not
preserve aliases, default censuses, dual readers, expiry dates, or reserved vocabulary.
Detector-teeth tests must prove that reintroducing the forbidden input changes a focused
gate from green to red.

## Semantic grounding technique

Reachability proves absence of an import path, not what the code means. Query the
behaviour and domain responsibility rather than the reported identifier, restricted to
production, and read the governing accepted ADRs. Then use exact search to verify the
candidate's callers and declarations. This establishes whether a live path already owns
the responsibility, whether the product actually needs it, or whether the code exists
only for development or tests.

The finding is not resolved until the live detector stops reporting it. A prose rationale
or a test importing the subject is evidence to investigate, never a substitute for a
product reachability edge.

Detector-teeth fixtures must not mirror the live population they guard. Exercise classification, omission, sorting, completeness, and rejection with a small synthetic authority, while the live gate derives its population directly from the production owner. A hand-written expected tuple of current format, module, command, or symbol identities is a second census even when it appears only in tests and is described as an independent expectation.

A syntax detector must classify both its source domain and the receiver semantics of a call. Exclude test-package modules structurally rather than by filename, and do not equate every method named `write` with operator output: descriptor transport such as `os.write(fd, bytes)` is not a file-like stream emission. Pair the negative transport fixture with a positive stream-write fixture, then route any surviving production output through the owning renderer instead of adding an exemption.

A production locale-key tuple that exists only to satisfy static discovery reverses the dependency boundary: the shipped package is then carrying a development-tool input. Delete that duplicate registry and teach the locale scanner to derive keys from the executable flow. For inline row tables, admission requires a loop-bound column to reach a translation sink, and collection must retain only that proven column; a dotted machine-routing or notice-code sibling is a negative control, not another locale key.

Do not aggregate runtime locale mappings and fallback literals into a production tuple for scanner or test completeness. The locale owner must derive mapping values, translation-wrapper calls, and literal `mapping.get` fallbacks from executable flow. A planted negative fallback routed to navigation rather than translation proves the call-shape rule does not sweep arbitrary dotted defaults; the full locale audit owns completeness, while behavior tests render representative live paths under strict missing-key mode.

When every constituent locale identity already has a scanner-visible `_LOCALE_KEY` declaration, an exported `*_LOCALE_KEYS` tuple that merely repeats those constants is a second census. Delete the aggregate and its export, then compare the module's derived key set before and after. The unchanged derived set is the detector-teeth proof; no replacement inventory is needed.

Remove scanner-only aggregates as a semantic cluster when sibling modules repeat the same pattern. Measure each module's derived locale-key set before deletion and assert the same sets afterward; this proves a large aggregate removal without copying its members into a replacement test. When focused suites mix unit and serial integration cases, run both marker lanes explicitly rather than accepting a green parallel run that announces held tests.

Treat capability predicates as operation-specific, not interchangeable lifecycle labels. Before deriving a refusal from a registry edge, measure the negative population: here, 29 legitimate structural or informative modelos lack a calculation link, proving that `has_engine == false` cannot own work-unit admission. Delete rollout censuses and feature flags only by routing each request to the registry, readiness, calculation, or filing boundary that owns that capability; retain classifications such as ceded-autonomic taxes only when they describe enduring domain jurisdiction rather than software progress.

When a shipped authority carries a whole-corpus gap projection that no production caller consumes, do not preserve it as an advisory API merely because a development report reads it. Move the derivation outward into the owning `dev/` reporter, keep that reporter reading canonical registry models and catalogues, and prove output continuity by executing the worklist. A capability-bound production authority should retain only state needed by product requests; review residue is development state even when every row is derived rather than hand-authored.

An executable declaration that describes itself as declared, implemented, staged, or otherwise not yet reached is carrying its development disposition inside the shipped product. Delete the unreached surface while retaining any canonical legal or domain authority that live consumers still use. A structural gate may detect explicit status markers on module-level executable declarations, but must pair that positive fixture with ordinary product uses of words such as “declared” so prose vocabulary alone does not become the signal. Newly exposed peers remain live zero-target findings; they are not grounds for suppressing the detector.

A metastate marker on a module can expose a supersession that symbol reachability alone understates. Before wiring an old helper cluster, compare its data model and decision rule with the live end-to-end mechanism authorized for the same responsibility. If the live path already owns ingress, durable state, routing, and calculation, delete the parallel helper model, its constants, and its self-tests, and amend any ADR prose that still calls those primitives stable or consumed. Preserve the accepted product boundary; withdraw only the obsolete implementation prescription.

Cryptographic and secure-storage detector fixtures must write through the current production storage owner, including every identity-bound AAD component. A fixture that mints ciphertext through the consumer's obsolete helper can make both sides agree on a broken format. Prove the boundary with a real repository row: a synthetic profile remains admissible while a decryptable real taxpayer identity is refused; corrupting that same production-shaped payload must exercise the fail-closed branch.

A durable writer's test-only parser or direct unlock facade does not become a product read door. When a stronger live artifact or repository boundary already performs the same proof, delete the duplicate parser/unlock vocabulary and drive retained tests through that live boundary. Writer-output tests may validate the emitted model directly, but must not preserve a second public ingestion path that no composition root can call.
