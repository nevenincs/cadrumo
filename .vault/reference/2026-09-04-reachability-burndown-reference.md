---
tags:
  - '#reference'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:eb4b4e850d8885d9d06d4a8da25887794020f146fb41c4e1288a0189b5db0435'
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

Do not export a read-only proxy of a private runtime catalogue merely so tests can call a generic helper with production identities. Keep the live catalogue private to its aggregator and prove generic refusal behavior with a minimal synthetic mapping. The synthetic mapping tests the mechanism; the aggregator’s behavioral suite tests the real catalogue, without creating a second public name or a test-facing production seam.

A constructor for an empty or sentinel fingerprint is test support when production always self-loads the real source and only tests inject the empty digest to avoid a bucket dependency. Move the constructor into the excluded shared test-support package, where it may call the production owner’s private canonical fingerprint primitive. Keep production overrides generic for legitimate precomputed values, but remove docstrings that advertise test-only empty helpers as product APIs.

A production accessor whose only consumer is a test enumerating a private runtime set is a development census, even when the underlying set drives live behavior. Delete the accessor and its export; retain the private runtime authority. Rewrite the proof around explicit input/output behavior and, where useful, separately assert that the public production computation supplies the expected prerequisites rather than exposing internal membership for inspection.

An exhaustive production mapping plus a second `excluded` or `ignored` inventory is development metastate when no live product path consumes either collection. If an accepted ADR prescribed that completeness scheme, amend the ADR first: retain the semantic boundary and the real wire vocabulary, but defer event conversion to the future live producer that owns it. Delete the inventories, exclusion-reason enum, exports, and census tests together; behavioral tests belong at the real producer once it exists.

A cache-reset composition exported from production solely so tests can mutate time-windowed cache state is test support. Remove the facade, its export, and production documentation that advertises test/tool mutation. Let the focused test clear the real cache owners directly, keeping each production cache and the live read path unchanged; do not replace the facade with another shipped diagnostic wrapper.

A production convenience that only chains already-public owners and has no product caller is a test seam, not an application service. Remove the wrapper, export, and module-level advertising; make the test compose the canonical state load and projection functions directly. Preserve any error translation only when a live caller consumes that contract—tests alone do not justify shipping it.

A public alias of a private canonical predicate is removable when exact reachability shows no consumers and the private predicate remains live through another public operation. Delete the alias and export together; verify the shared live path rather than adding an alias-specific test. This preserves one semantic owner and avoids manufacturing API surface for internal implementation detail.

Field partitions such as `compared`, `derived`, and `non-identity` are development metastate when only a completeness test consumes the non-live partitions. Keep the subset that drives the runtime comparison; delete explanatory inventories used only to make an exhaustive union and remove that union test. Preserve safety with behavioral proofs that retries no-op on agreement, refuse changed caller input, retain timestamps, and do not repeat custody writes.

A production `uncovered_*` reporter and its pure comparison helper are development tooling when only a test calls them. Keep the live mapping in production, but move union introspection and set-difference logic into the coverage test. Preserve detector teeth by subtracting one real member in test-owned data and proving the missing member is detected; production should not expose the test's audit operation.

A generated production aggregate of otherwise-live contracts is development metastate when no assembly, capture, revalidation, or reader consumes the aggregate. Retain each owner-specific contract at its live port boundary, delete the inventory model, digest, singleton, exports, and inventory-only tests, and amend any ADR that prescribed the aggregate. A completeness gate may discover live contract instances by their semantic type and compare their kinds with the typed runtime denominator; it must not introduce a second tuple of contracts, constant-name census, or shipped inventory version.

A test is not valuable merely because it checks a detailed synthetic contract. When an exact finding's removal exposes the contract's defining module as wholly unreachable and every remaining consumer is its own test suite, follow that reachability edge before closing the Step. Delete the abandoned production model, its synthetic fixtures, identity/export censuses, and orphaned primitive together unless a real product boundary owns the behavior. Remeasure after the first edit: a newly unreachable module is evidence that the initial symbol was only the outermost layer of the same dead slice, not a reason to preserve the layer or repair its tests.

A reflective test that scans a hand-maintained package list, converts live types into qualified-name strings, and compares them with an enrolled/classified name census is not a second safety authority when the production composition already validates typed membership and the exact reachability detector already reports dormant implementations. Delete the reflective gate rather than updating its module list, disposition map, or pinned counts. Keep production validation over the actual typed route and behavioral tests that execute representative resolvers; those fail on real composition defects without encoding development classifications or duplicate code identities.

A dormant release-regime switch, future floor mapping, or persisted-format classification table is development lifecycle state when no production path consumes it and its only consumers are synthetic predicates or inventory tests. Delete that production metastate and its census tests together. Retain concrete storage protections at their owning modules: current writes stamp a version, future or malformed records refuse, and an upgrade-chain test is valuable only when it exercises hops the product actually registers rather than a branch made vacuously green by the dormant regime.

An empty production dispatch registry does not become future-proofing because tests can register synthetic handlers into it. If no shipped composition registers a handler and current product data has no prior readable shape, remove the mutation API, chain evaluator, synthetic upgrade tests, and read-time transformation branch together. Keep exact-current validation before decryption and the real current-format roundtrip. Add an upgrader only with the real version transition and persisted old-shape evidence that requires it.

A typed identity alias and canonical formatter are still development support when their only consumers are diagnostic tooling and test fixtures. Delete the shipped alias, facade export, formatter module, named-emitter census, and identity-specific tests together. Let each excluded consumer render its local diagnostic field from the typed domain coordinates it already holds; matching display strings across development and tests do not create a product identity boundary.

A validator-only test can preserve a contradictory product vocabulary after the live boundary has moved. When an unused typed alias duplicates the canonical identity type with different constraints, delete the alias, its export, and the self-test together; retain behavioral tests through the canonical owner and correct prose that attributes live behavior to the dead contract. A detailed validator test is not material quality evidence when no product field consumes the validator.

An orphan-test finding can expose one dead census inside an otherwise material behavioral suite. Split the test responsibilities before deleting the module: if a hand-maintained exact roster duplicates an owning typed authority and is the suite's only direct dead subject, delete that roster assertion and retain the end-to-end tests. Remeasure through the test-support hop; the suite is live only when its helper actually reaches the product entrypoint, not because an allowlist or test-path exception says so.

A shipped module with an exact top-level `__name__ == "__main__"` guard is a product `python -m` surface even when its filename is not `__main__.py`; derive both forms as roots and reject prose or nested comparisons as evidence. When that correction exposes a helper used only to launch the surface from tests, move the launcher helper into test support rather than retaining a shipped test seam. Preserve end-to-end security tests when an accepted decision requires the process boundary they exercise.

An error-code registration does not make the corresponding feature reachable; it only lets a hypothetical raised exception render consistently. When an entire domain package has no acquisition, application, calculation, or presentation consumer and no accepted decision names its representation, delete the package, synthetic model tests, and dormant error registrations together. Audit every test in the package, not only reported orphans: importing a shared live base exception can hide a wholly abandoned test from an all-subjects-dead detector.

A production error registry is a rendering mechanism, not a feature owner. A registry row that names an otherwise unreachable exception cannot justify retaining the exception, its model, or self-tests; first locate the accepted decision and live acquisition, calculation, or presentation path. If that path implements the regulated behavior through a different representation, retain its end-to-end tests and delete the disconnected representation, synthetic suite, and dormant error rows together.

A lifecycle writer is not material merely because its inverse operation sounds symmetrical. When the accepted state model makes finalized records immutable and recovery creates a successor, delete an unused in-place rollback writer and any public prose advertising it. Preserve and test the forward approval, stale-status, and successor mechanisms; do not add a rollback test whose only purpose would be to keep the contradictory transition alive.

A deterministic application projection and its unit tests are not material when the live operator surface independently builds a richer projection from the canonical aggregate and no production caller reaches the narrower one. Delete the narrower DTO, builders, and tests as one slice, but preserve adjacent repository queries that have real application consumers. Run both configured marker lanes for the live operator suite so a selected-lane green cannot conceal lost behavior.

A typed request DTO is duplicate vocabulary when no boundary accepts it and live callers already pass the same typed axes directly to the owning workflow. Delete the unused envelope, its export, prose, and constructor or immutability tests together; retain tests of the live enums' total mapping and the behavior of the actual terminal. A model's validation quality cannot make an unconsumed shape material.

A selector’s named “reserved” tokens are production metastate when the live parser already fail-closes every unknown token through one generic, privacy-safe refusal. Remove the reserved-token map, its reason accessor, specialized exception, error registration, and self-only probes together; retain tests of the actual unknown-token refusal and a representative live refusal class for error-category coverage. A rejected label with no executable producer is not a product contract.

A public string alias derived from a typed persistence definition is duplicate vocabulary when the live repository already receives that definition and no product caller observes the alias. Delete the alias and export, then have storage-boundary tests assert the typed owner’s namespace or schema field directly. Retain encrypted roundtrip and corruption tests: they prove the persistence contract, unlike a second spelling of its identity.

An unused current-version literal does not enforce a persisted-format contract; it is a second, inert statement of the version. Keep version markers only where the owning serializer, typed namespace, or reader actually writes and refuses them. Delete an unconsumed constant and export outright, then run the real encrypted roundtrip and current-schema refusal suites rather than inventing a test for the discarded spelling.

Comments describing a plausible future audit event do not turn its actor or payload-version constants into product metadata. When no writer emits the event and no reader consumes those fields, delete the constants as one abandoned declaration while retaining tests of the real import boundary; do not add an event merely to make speculative metadata reachable.

A security test that hard-codes command identities and importer filenames is not confinement proof, especially when its AST predicate cannot match the live import spelling. Delete the census and preserve graph-derived contract projection plus planted invalid-channel and duplicate-contract cases. Safety gates should fail on forbidden behavior or malformed executable structure, not on divergence from a second list of current code names.

A migration-in-progress entry that clears an entire parameter-name class is development metastate and a false-green allowlist, even when a stale-entry test polices it. Delete the classification and let the zero-target detector name every live axis. Close the exposure step on detector integrity and then resolve the surfaced population through enum typing or enduring semantic behavior, never by restoring a campaign disposition.

A global closed-axis detector is unsound when it infers semantics from a shared parameter name and whichever model classes happen to be loaded, then repairs false positives with command/parameter allowlists. Delete that detector and keep the architectural rule at owning command contracts, where the real enum, dynamic registry, normalizer, or instructive refusal is observable. A false-green classification gate contributes less quality than focused boundary tests with planted invalid tokens.

A test-owned list of exact layout identities labelled unadjudicated is campaign state, not renderer assurance. Delete the list and the tests that merely require current findings to appear in it; retain tests derived from the live corpus that reconstruct split values, handle absence, and deliberately break a real policy. Undecided regulatory modelling belongs in a plan, while executable renderer properties belong in the suite.

A test that scans function-local imports and assigns every exact path/function pair a status such as documented, deliberate, or unadjudicated is an architecture census, not an architecture boundary. Delete it when the executable import-linter contracts already own layer direction. A status ledger can stay green with dozens of unreviewed edges; the real contract must pass or fail from imports themselves.

A second live-auth session path is not justified by a narrower no-acquisition promise when every product caller enters through the central authenticated-session owner. If exact reachability exposes the narrower verifier after a census test is removed, delete the branch and its export rather than manufacturing a caller. Preserve the identity, storage, provider-lifecycle, and access-gate guarantees through the live `ensure_authenticated_aeat_session` path and its focused behavioral tests.

A reusable presentation component is not material merely because its synthetic suite proves redaction, bounding, and rendering in isolation. When no composition root mounts it and a live feature-specific surface already renders the same safe public DTOs through a stronger owning boundary, delete the generic component, its duplicate DTO vocabulary, helper, locale leaves, and self-only tests together. Amend any ADR that prescribed the speculative widget, and retain behavioral tests on the mounted product surface plus unrelated shared components.

A one-call presentation facade is duplicate vocabulary when it merely constructs the canonical screen around an already-bound controller and no product caller uses it. Delete the protocol, wrapper, outcome predicate, export, and prose advertising the wrapper; let the host mount the canonical screen directly. Preserve the mounted screen’s lifecycle tests, which prove the actual behavior rather than the unused convenience API.

A legally detailed domain package is still an abandoned partial feature when its former command was deleted, no replacement acquisition or calculation binding exists, and its own readiness projection can never become true. Remove the domain models, repository ports, adapter, ORM tables, error registrations, locale leaves, constants, synthetic roundtrips, and census entries as one slice. Preserve the official corpus and canonical registry parameters independently; legal grounding survives without shipping an unreachable implementation.

After withdrawing the last production consumer of a generic persistence decorator, follow the newly exposed exact symbol instead of preserving it for its standalone crypto tests. Delete the decorator, purpose-specific AAD, public prose, and its synthetic ORM column while retaining the live hashed lookup and row-bound secure-object encryption owners. Rewrite nearby tests to exercise those live owners, not the removed storage representation.

A minimal version-header DTO is not a version boundary when no parser, dispatcher, or serializer consumes it. Delete the class and export instead of preserving an uncalled pre-dispatch shape; keep version handling on the live request/result models and prove those contracts through their behavioral model suite.

A gate that makes a dead discriminated-union arm green by recording why it is dead is an allowlist even when it calls the entries rulings or adjudications and checks for staleness. Delete the gate, narrow the union to shapes a live assembler emits, remove synthetic constructor tests and unreachable consumer branches, and keep behavioral coverage on the surviving producer-to-presentation path. A future protocol version or outcome earns a new arm only when its parser or assembler can actually produce it.

A production vocabulary consumed only by a test that checks current enum leaves against the vocabulary is a test-owned census, not a product authority. Delete the constants and census together, retain each live producer key and its owning serializer, and run behavioral schema/export gates. Descriptive domain differences belong beside the actual models; they do not make a disconnected set of approved spellings reachable.

When a shipped constants module explicitly says its only consumer is a development renderer, move the semantic constant to that renderer rather than preserving `src/` as a stable import target for tooling. Delete production-side self-tests and any dev gate exception that blesses the reverse dependency. Validate the development output through its real loader/renderer suite; `dev/` may depend on product types, but product packaging must not exist to serve `dev/`.

A typed event and injection parameter do not establish a measured health dimension when no product path captures the observation. Delete the DTO, evaluator, synthetic event tests, and unreachable reporting branches together; keep the health probe limited to facts it obtains itself. A future live observer should introduce its event at the acquisition boundary and wire it through composition, not predeclare a dormant advisory contract.

When exact reachability exposes a generic projector beside a stronger live workflow-specific projector, compare their evidence inputs before preserving either. Delete the generic helper and self-tests when only the live owner derives grounding from canonical observations and handles domain exclusions; retaining both creates duplicate vocabulary with different safety semantics. Verify the shared evidence model and the live capture/recapture path, not the unused convenience.

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
