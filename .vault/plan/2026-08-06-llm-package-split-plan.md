---
tags:
  - '#plan'
  - '#llm-package-split'
date: '2026-08-06'
modified: '2026-08-06'
body_hash: 'sha256:ddfe61307df5f8d29cc5696fbb4c9eb370073ea9977bb210685f58d14da13db4'
tier: L3
related:
  - '[[2026-08-06-llm-package-split-adr]]'
  - '[[2026-08-06-llm-package-split-research]]'
  - '[[2026-08-06-llm-package-split-enforcement-and-disposition-audit]]'
  - '[[2026-08-06-llm-package-split-measurement-basis-reference]]'
  - '[[2026-08-06-llm-package-split-ingest-cascade-reference]]'
---

# `llm-package-split` plan

Quarantine probabilistic document inference behind an opt-in extra, move exact structured reading into the deterministic core, and retire the off-host path.

## Description

Executes `2026-08-06-llm-package-split-adr`, grounded in `2026-08-06-llm-package-split-research`. One ADR, one plan.

The ADR decides that the document-ingestion-and-inference path moves to `src/cadrumo/llm/` as a gated subpackage behind a new `llm` extra rather than to a sibling top-level package, because the enforcement controls that protect decrypted invoice bytes are scoped to `src/cadrumo` and a sibling root would put precisely that code beyond them. It further decides that exact structured-document reading is not inference and stays in the core, that the interchange value is a typed validated payload rather than free text, and that the cloud subprocess path is deleted once a local text reader exists.

**Tier `L3`, chosen from the real structure.** The work carries five Waves with hard ordering between most of them, and the Phases inside each Wave are genuine groupings rather than invented containers. `L2` cannot express the Wave-level ordering, which is the plan's principal safety property. `L4` would demand an external project-management association that does not exist for this work.

Wave ordering is the safety property. `W01` hardens the enforcement instruments before anything relies on them. `W02` lands exact structured reading, which is independent of the boundary work and shrinks what the extension must cover. `W03` fixes the contract before `W04` moves behaviour behind it. `W04` enrols the subpackage under every control and proves each one. `W05` wires a local text reader before deleting the cloud path, and that order is mandated by the ADR rather than preferred.

### The defect class this plan exists to avoid

A prior draft of this plan failed a fresh-context honesty review on a single recurring shape: **Steps that pass without proving anything.** Three instances, each of which would have closed a checkbox while leaving its stated property unestablished.

A Step enrolled `src/cadrumo/llm/` in the sensitive-surface list two Waves before the directory was created. Because that list is an enumerated tuple with no existence check, the enrolment would have iterated zero files and passed green - and the same relocation would have silently emptied the surviving `adapters/outbound/llm` entry, which also passes green. A Step scheduled a mutation proof against a subpackage that did not yet exist, so it could only be skipped, faked against a stub, or deferred; it was also the one control that would have caught the first defect. And a Step said *"confirm the layered import contract covers the new subpackage"* against a contract that has no opinion on it - import-linter would have passed, because `cadrumo.llm` appears in no contract and the layers contract is not exhaustive. Confirming a check with no opinion is not verification.

**The rule this plan adopts, and against which it should be reviewed: every Step must be able to FAIL for the reason it exists, at the point it is scheduled.** Each Step row therefore carries its red condition in its action text - not as decoration, but because writing it forces the question of whether the Step can fail at all. Where a Step asserts a safety property, the proof is executable when it runs, not when the property is finally true. Three consequences run through the structure: nothing that names the inference subpackage is scheduled before `W04` creates it; the shared gate is made non-vacuous in `W01`, before any Step relies on it; and every enforcement control is proven by mutation - introduce the violation, observe red, revert - rather than by inspection.

One procedural hazard governs every Step that moves code. The `llm-invoice-read-reconciliation` research records three deliverables that shipped correct, tested and unreferenced, because a unit test passes whether or not anything calls the code. A package migration is that failure mode at larger scale: every moved module can be green while the core still routes around it. Each relocation Step therefore carries an enrolment gate proving the core call site reaches the moved code, not merely that the moved code works. The same hazard is why `W02` opens the ingest-time gate: a Facturae parser behind a front door that still refuses `.xml` is that failure in its purest form.

### Execution context a receiving team must inherit

This plan is written to be executed by a team with no context from the session that authored it.
Everything load-bearing is in the vault; nothing depends on a conversation. Read the feature's
audit document before the first Step - it is why the plan is shaped this way - and the
measurement-basis reference before quoting any figure from this campaign.

**The supporting evidence has been landed and the scratch originals are gone.** The honesty
review, the source discovery, the disposition register, the cascade blueprint, the injection
posture and the full quantitative trace were produced outside the git tree. They are now the
audit and two reference documents in this feature's `related:` set. Do not go looking for a
scratch directory; it will not be there.

**Shared worktree, concurrent peer campaigns.** Destructive git is categorically forbidden here
in every form: no stash, no reset (including an index-only pathspec reset), no checkout or
switch or restore of a path or branch, no clean, no rebase, no force push, no worktree removal,
no revert of another agent's commit. There is no reset escape hatch and no debugging exception.
Peers hold uncommitted work in the shared index and working tree at all times, and peer TOML
edits have been found staged there. **Every commit needs an explicit pathspec naming only files
you authored**, verified with a staged-diff read immediately before committing - a bare commit
takes the whole index, including a peer's staged work. Before a first edit to any shared file,
diff it and abort on non-authored changes.

**No live model inference.** A prior session's inference run crashed the development host and
terminated four concurrent agent sessions. No Step in this plan requires running a model. The
two measurements that would need one - the stage-isolation run that settles the pipeline shape,
and the vision matrix at usable sample size - are written up as offline procedures in the
measurement-basis reference, with their preconditions. Neither is a precondition of this plan.
Do not start either casually.

**GPU contention is a live confound.** A same-class query on this host swung from 1.58 s to
126.6 s under fleet load. Anything timed while the fleet is busy measures the fleet.

**The semantic code index reports itself SHRUNKEN - absence in it is NOT evidence.** Use it to
find things by meaning, then confirm every conclusion, and especially every *negative* claim,
with a targeted search at HEAD. A related trap that manufactured a false finding during this
campaign: in ripgrep, `-r` is `--replace`, not `--recursive`, so a `-rn` invocation silently
rewrites every match and produces plausible nonsense.

**The defect class this plan exists to prevent - do not reintroduce it.** Three shapes, all of
which close a checkbox while proving nothing: a **gate enrolled before its target exists** (an
enumerated surface list with no existence check iterates zero files and reports success); a
**mutation proof scheduled where it cannot run** (leaving an executor only skip, fake, or
defer); and a **"confirm" against a check with no opinion** (import-linter passes on an
unenrolled module). The compounding hazard is that the encryption exemption this campaign rests
on is valid only while the controls establishing its persists-nothing premise actually exist -
so all three defects together yield a correctly reasoned exemption resting on controls that
check nothing, with every gate green. If you re-sequence this plan, re-check that property
first.

## Steps

## Wave `W01` - Harden the enforcement instruments and establish the boundary

Declares the llm extra with its real runtime dependencies, closes the undeclared-direct-Pillow defect, adds the missing hardware-capability axis, and closes the fail-open hole in the strictest gate tier. Nothing here names the inference subpackage, which does not yet exist, so every Step in this Wave is executable at the point it is scheduled.

### Phase `W01.P01` - Declare the llm extra and close the dependency defects

Registers the extra in the shared classifier and forces the undeclared runtime packages into the open.

- [ ] `W01.P01.S01` - Register an llm OptionalExtra in the declared set rather than hand-rolling it like the agent extra, red if the extra resolves outside OPTIONAL_EXTRAS; `src/cadrumo/core/_optional_extras.py`.
- [ ] `W01.P01.S02` - Declare the llm extra's runtime packages explicitly, gated red if a clean non-extra install still resolves an inference-only package; `pyproject.toml`.
- [ ] `W01.P01.S65` - Declare Pillow as a direct project dependency carrying the lxml comment's incidental-transitive rationale, since the extra alone leaves the direct reliance undeclared in the base closure; `pyproject.toml`.
- [ ] `W01.P01.S03` - Guard the rasterisation path with require_optional_extra immediately before its lazy import, red if the import raises ModuleNotFoundError instead of the typed refusal when the extra is absent; `src/cadrumo/adapters/outbound/llm/_providers/local.py`.
- [ ] `W01.P01.S04` - Replace the misdiagnosed Ollama remediation raised on a missing-Pillow failure with the extra's install hint, red if the rasteriser still reports a missing PIL as a broken PDF; `src/cadrumo/application/ledger/_evidence_draft.py`.
- [ ] `W01.P01.S05` - Assert an absent llm extra degrades the command group to the install-hint placeholder, red if any inference verb raises ModuleNotFoundError on a clean install; `src/cadrumo/entrypoints/cli/tests/`.
- [ ] `W01.P01.S66` - Assert every module importing PIL is reachable only through a declared dependency, red if a direct import rests on an undeclared incidental transitive; `dev/packaging/`.

### Phase `W01.P02` - Harden the enforcement instruments and add the capable axis

Closes the fail-open hole in the strictest gate tier before any Step relies on it, and adds the missing hardware-capability probe. The non-vacuity assertion lands first because a campaign that relocates code across two named surfaces is exactly the event that exercises the failure, and an instrument repaired afterwards proves nothing about the interval.

- [ ] `W01.P02.S08` - Add a non-vacuity assertion to the sensitive-surface list so every entry must resolve to at least one non-test module or the gate fails naming the entry, closing the fail-open hole for all eighteen surfaces; `src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`.
- [ ] `W01.P02.S09` - Prove the non-vacuity assertion by pointing one entry at a nonexistent path and observing the gate red, then reverting, red if a nonexistent surface still reports success; `src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`.
- [ ] `W01.P02.S72` - Record per check which of the five secure-storage gates scans by whole-tree rglob, which enumerates a fixed surface list, and which is test-side only, so a coverage claim about any new directory is checkable rather than asserted; `src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`.
- [ ] `W01.P02.S06` - Add a hardware-capability probe reporting the model runtime floor through the existing DependencyStatus shape, red if an under-specified machine reports capable; `src/cadrumo/application/provisioning.py`.
- [ ] `W01.P02.S07` - Surface the hardware probe as a typed refusal naming the shortfall in the config doctor, red if the refusal omits the accepted floor; `src/cadrumo/entrypoints/cli/_check_cli.py`.

## Wave `W02` - Land exact structured-document reading in the deterministic core

Implements D7. Adds a content-shape probe and deterministic EN16931 (CII and UBL) and Facturae parsers in the inbound adapter layer on the already-declared defusedxml, so a structured e-invoice is read exactly on a default install with no extra enabled and no model involved. Extends the extraction draft to carry a line set and a per-rate IVA breakdown, which is what the sibling campaign's reader half is waiting on. Opens the ingest-time gate so the formats the parsers read can actually arrive, and fixes the evidence-record identity defect that any re-ingest or batch verb would otherwise turn from annoying into corrupting.

### Phase `W02.P03` - Probe document shape from content

Replaces a two-member media kind derived from a declared MIME with a typed shape derived from content bytes, so an embedded XML payload inside a PDF is visible rather than invisible.

- [ ] `W02.P03.S10` - Add a typed DocumentShape probe deriving shape from content bytes rather than from a declared MIME, red if a ZUGFeRD PDF whose MIME says application/pdf resolves to a shape carrying no embedded XML; `src/cadrumo/adapters/inbound/einvoice/`.
- [ ] `W02.P03.S11` - Extract the sanitizer's embedded-file walker into a reusable reader so an embedded XML payload is visible, red if the walker's stripping behaviour changes for the sanitizer's own callers; `src/cadrumo/adapters/inbound/sanitizer/_dynamic.py`.
- [ ] `W02.P03.S12` - Route read-time evidence resolution through DocumentShape and retire the read-time media-kind derivation, red if any caller still branches on the two-member media kind; `src/cadrumo/application/ledger/_evidence_input.py`.

### Phase `W02.P04` - Parse the structured formats exactly, in the inbound adapter layer

Adds hardened deterministic parsers for both EN16931 syntaxes and for Facturae, mapping to one line-carrying extraction draft. They land under adapters/inbound alongside the seven sibling packages that already parse externally-authored formats, because a record whose subject is a boundary decision cannot put format parsing in the application layer without contradicting itself.

- [ ] `W02.P04.S67` - Extend the extraction draft to carry a line set and a per-rate IVA breakdown, red if a two-rate document still collapses to a single base and cuota pair; `src/cadrumo/application/ledger/_evidence_draft.py`.
- [ ] `W02.P04.S79` - Add a representable recargo slot to the extraction draft, since the printed-total discrepancy advisory now fires with no field for the operator to resolve it into, red if a recargo-bearing document still leaves the operator no place to record it; `src/cadrumo/application/ledger/_evidence_draft.py`.
- [ ] `W02.P04.S13` - Add a deterministic EN16931 CII parser mapping to the line-carrying extraction draft, red if a CII document with two tax rates yields fewer than two per-rate entries; `src/cadrumo/adapters/inbound/einvoice/`.
- [ ] `W02.P04.S14` - Add a deterministic EN16931 UBL parser, since a CII-only reader silently returns nothing for half the standard, red if a UBL document yields no record where the CII path yields one; `src/cadrumo/adapters/inbound/einvoice/`.
- [ ] `W02.P04.S15` - Add a deterministic Facturae 3.2.x parser mapping to the same line-carrying draft, red if a Facturae document maps to a shape the CII and UBL parsers do not also produce; `src/cadrumo/adapters/inbound/einvoice/`.
- [ ] `W02.P04.S80` - Map the parsed percentage onto the closed IvaRate slot enum and refuse loudly when no slot matches, never rounding to the nearest member, red if a 5 percent pre-2025 line resolves to any slot rather than refusing; `src/cadrumo/adapters/inbound/einvoice/`.
- [ ] `W02.P04.S16` - Harden every XML read with entity resolution and external DTD loading disabled and with size and depth bounds, red if an XXE probe document resolves an external entity or a billion-laughs payload is not refused; `src/cadrumo/adapters/inbound/einvoice/`.
- [ ] `W02.P04.S17` - Select the VAT number as the party tax identifier rather than a French SIRET or German Steuernummer, red if a ZUGFeRD fixture carrying both still yields the SIRET; `src/cadrumo/adapters/inbound/einvoice/`.
- [ ] `W02.P04.S56` - Map emisor and destinatario the right way round on received-invoice SII records, red if a received-invoice fixture still reports the taxpayer as the issuer; `src/cadrumo/adapters/inbound/einvoice/`.
- [ ] `W02.P04.S57` - Read the invoice number from the document identifier element rather than the first identifier in the tree, red if a document whose first identifier is a guideline identifier still yields that guideline string as the invoice number; `src/cadrumo/adapters/inbound/einvoice/`.

### Phase `W02.P05` - Replace the vacuous assertions, open the front door, and enrol the parsers

Turns the ZUGFeRD fixture into a real field-level gate, proves the core path reaches the new parsers, opens the ingest-time gate so the formats the parsers read can actually arrive, and fixes the evidence-record identity defect that would multiply records on any re-ingest.

- [ ] `W02.P05.S18` - Replace the ZUGFeRD assertion that only checks for a German word with an exact field-level assertion against the fixture's printed values, red if a parser returning a wrong tax identifier still passes; `src/cadrumo/application/ledger/tests/test_evidence_corpus_parsing.py`.
- [ ] `W02.P05.S19` - Add an EN16931 UBL corpus fixture with its provenance sidecar declaring provenance explicitly, red if the sidecar's declared provenance disagrees with the file's own producer evidence; `src/cadrumo/application/ledger/tests/_evidence_corpus/`.
- [ ] `W02.P05.S20` - Add a Facturae 3.2.x corpus fixture with its provenance sidecar declaring provenance explicitly, red if the sidecar's declared provenance disagrees with the file's own producer evidence; `src/cadrumo/application/ledger/tests/_evidence_corpus/`.
- [ ] `W02.P05.S21` - Prove the core evidence read path reaches the new parsers rather than routing around them, red if the parser is removed and the corpus test still passes; `src/cadrumo/application/ledger/tests/`.
- [ ] `W02.P05.S22` - Open the ingest-time suffix gate to the XML shapes so a standalone Facturae or EN16931 file is accepted at evidence add, red if a Facturae XML is still refused at the front door after the parser lands; `src/cadrumo/application/ledger/_evidence.py`.
- [ ] `W02.P05.S68` - Remove the dangling evidence-source-expansion reference from the refusal message, since this campaign discharges that deferral and a vault stem cited from source breaches Code Stands Alone; `src/cadrumo/application/ledger/_evidence.py`.
- [ ] `W02.P05.S58` - Assert a malformed structured document refuses loudly with a parse error rather than yielding a partial record, red if a truncated document produces a record carrying any field at all; `src/cadrumo/application/ledger/tests/`.
- [ ] `W02.P05.S69` - Add a caller-supplied idempotency key to evidence add deriving a clock-free id when one is passed, keeping the keyless path additive with its documented genuine-duplicate rationale, red if a keyed re-add over one blob still mints a second record and a second bucket event; `src/cadrumo/application/ledger/_evidence.py`.
- [ ] `W02.P05.S71` - Assert the keyed guard compares every persisted field so a same-key re-add whose content differs refuses with an instructive conflict, red if a re-add changing one field is reported as an unchanged no-op and the new value is silently dropped; `src/cadrumo/application/ledger/tests/`.
- [ ] `W02.P05.S70` - Prove the parsers give the sibling campaign's multi-line writer a real per-rate producer by round-tripping a two-rate structured document from parse to a confirmed multi-line invoice, sequenced after that campaign's writer Step lands, red if the confirm boundary is bypassed or the second rate is lost in transit; `src/cadrumo/application/ledger/tests/`.
- [ ] `W02.P05.S81` - Assert the invoice-level identity holds exactly on a parsed multi-rate document with grand total equal to base plus IVA plus recargo and retencion outside it, red if per-line rounding is allowed to accumulate into the invoice-level total; `src/cadrumo/application/ledger/tests/`.

## Wave `W03` - Define and enforce the core-to-extension interchange contract

Implements D3 and D4. Establishes the typed validated payload the core accepts and refuses, its provenance carriage, and the import contract keeping the inference side free of any persistence handle. Lands before behaviour moves, because the contract is what the relocated modules are relocated behind.

### Phase `W03.P06` - Define the validated interchange payload

Declares the strict closed payload the core accepts, with its shape grounding and provenance carriage.

- [ ] `W03.P06.S23` - Declare the strict closed interchange payload the core accepts, with forbidden extras and a fixed key set, red if an unexpected key survives validation; `src/cadrumo/application/ledger/_llm_suggestions.py`.
- [ ] `W03.P06.S24` - Apply the existing shape grounding to every payload field reusing the checksum, date and decimal validators rather than rewriting them, red if a checksum-invalid tax id or unparseable date reaches the core; `src/cadrumo/application/ledger/`.
- [ ] `W03.P06.S25` - Carry legal_refs, source_refs and the typed source kind on the payload, red if a payload constructed without them validates; `src/cadrumo/application/ledger/_llm_suggestions.py`.
- [ ] `W03.P06.S26` - Carry the producing model identity and revision on the payload so a persisted record can answer how each field was recovered, red if a payload omitting the producer validates; `src/cadrumo/application/ledger/_llm_suggestions.py`.
- [ ] `W03.P06.S27` - Refuse a malformed payload at the core boundary rather than coercing it and pin the refusal by test, red if a malformed payload is silently normalised into a valid one; `src/cadrumo/application/ledger/`.
- [ ] `W03.P06.S28` - Prove the refusal is not vacuous by mutating a well-formed payload field by field and asserting each mutation reddens, red if any single-field mutation still validates; `src/cadrumo/application/ledger/tests/`.
- [ ] `W03.P06.S29` - Prove provenance survives persistence with a strict save-load-equality roundtrip against the real encrypted namespace with every defaultable field populated non-default, paired with an anti-tautology proof that deleting a persisted field reddens the load; `src/cadrumo/application/ledger/tests/`.

### Phase `W03.P07` - Keep every durable artefact on the core side

Implements D9's carve-out list. Every artefact the inference path is under pressure to write is storage rather than processing and returns to the core's encrypted bucket-scoped repository. The controls that name the subpackage itself moved to W04.P12, because a control naming a directory that does not yet exist checks nothing.

- [ ] `W03.P07.S59` - Persist the extracted-document cache through the core's content-addressed encrypted secure object repository, deliberately not named a normalization cache since that name presupposes the two-stage shape the ADR leaves open, red if any cache byte reaches disk unencrypted; `src/cadrumo/adapters/persistence/storage/attachment.py`.
- [ ] `W03.P07.S62` - Route persisted extracted field drafts through the core, since derived financial data is storage rather than processing, red if a draft is written by anything other than the core's secure repository; `src/cadrumo/application/ledger/`.
- [ ] `W03.P07.S64` - Pin by test that in-memory reading, rasterising and inference require no encryption and no consent gate, red if a later change reintroduces a consent prompt or a custody wrapper on the in-flight path; `src/cadrumo/application/ledger/tests/`.

## Wave `W04` - Relocate pure inference and divide the mixed module

Implements D1, D11's ordering constraint and D12. Moves the purely-inferential members under the gated subpackage and divides the module that mixes inference call sites with core writes, leaving the persistence-touching telemetry, cache and usage stores on the core side. Every relocation Step carries an enrolment gate proving the core call site reaches the moved code. The final Phase enrols the subpackage under every enforcement control and proves each by mutation, because this is the first point at which a control naming that directory checks anything at all.

### Phase `W04.P08` - Move the purely-inferential members

Relocates the modules that carry no core writes, each with an enrolment gate.

- [ ] `W04.P08.S32` - Create the gated subpackage and move the vision field extractor into it in one atomic explicit-path commit that also carries its sensitive-surface enumeration, red if the extractor is deleted and the core corpus test still passes; `src/cadrumo/application/ledger/_evidence_draft_vision.py`.
- [ ] `W04.P08.S33` - Move the local vision classifier under the gated subpackage and prove the core call site reaches it, red if the moved module is deleted and the classify test still passes; `src/cadrumo/application/ledger/_vision_classifier.py`.
- [ ] `W04.P08.S34` - Move the outbound LLM client under the gated subpackage and prove the core call site reaches it, red if the moved module is deleted and the classify test still passes; `src/cadrumo/adapters/outbound/llm/_client.py`.
- [ ] `W04.P08.S35` - Move the outbound LLM models, errors and pricing modules under the gated subpackage, red if any error qualname in the registry still resolves to the vacated path; `src/cadrumo/adapters/outbound/llm/_models.py, src/cadrumo/adapters/outbound/llm/_errors.py, src/cadrumo/adapters/outbound/llm/_pricing.py`.
- [ ] `W04.P08.S36` - Move the outbound provider adapters under the gated subpackage, red if a provider is deleted and its integration test still passes; `src/cadrumo/adapters/outbound/llm/_providers/`.
- [ ] `W04.P08.S37` - Move the pure retention selection function under the gated subpackage, red if the core still imports it from the vacated path; `src/cadrumo/adapters/outbound/llm/_retention.py`.
- [ ] `W04.P08.S38` - Re-point the owner labels and error-registry qualnames that name the moved modules by string, red if any string owner label still names a path that no longer exists; `src/cadrumo/core/paths.py, src/cadrumo/core/_namespace_registry.py, src/cadrumo/core/errors/registry/_adapters_part2.py`.

### Phase `W04.P09` - Divide the mixed classification module

Splits the module that holds both inference call sites and core writes, leaving persistence on the core side.

- [ ] `W04.P09.S39` - Extract the inference call sites from the mixed classification module into the gated subpackage, red if any extracted call site still performs a core write; `src/cadrumo/application/ledger/_llm_classification.py`.
- [ ] `W04.P09.S40` - Keep classification writes, bucket-event history and split persistence on the core side of the division, red if a bucket event is emitted from inside the subpackage; `src/cadrumo/application/ledger/_llm_classification.py`.
- [ ] `W04.P09.S41` - Leave the cache, run-telemetry and usage stores on the core side so the non-ledger diagnostics consumer stays unconditional, red if any of the three resolves secure storage from inside the subpackage; `src/cadrumo/adapters/outbound/llm/_cache.py, src/cadrumo/adapters/outbound/llm/_run_telemetry.py, src/cadrumo/adapters/outbound/llm/_usage.py`.
- [ ] `W04.P09.S42` - Settle the review workflow's dependency on the apply and reject functions once the division lands, red if the workflow imports across the boundary in the forbidden direction; `src/cadrumo/application/ledger/_llm_review_workflow.py`.
- [ ] `W04.P09.S43` - Prove the core diagnostics run-health verbs still resolve without the llm extra installed, red if the verb raises rather than reporting run health on a clean install; `src/cadrumo/application/diagnostics_run_health.py`.

### Phase `W04.P12` - Enrol the relocated subpackage under every enforcement control

Runs only after the subpackage exists, because every control here names it. Enumerates it in the sensitive-surface list, enrols it in the layering contract, forbids its reach into persistence, and proves each control by mutation rather than by inspection. An earlier plan scheduled this work two waves before the directory existed, where each check passed against nothing.

- [ ] `W04.P12.S63` - Enumerate the new subpackage in the sensitive-surface list in the same change that creates it, never earlier, red if the entry is added while the directory is absent since the non-vacuity assertion must refuse it; `src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`.
- [ ] `W04.P12.S30` - Add an import contract forbidding any persistence import from the inference subpackage, red if a deliberate adapters.persistence import inside the subpackage does not fail import-linter; `.importlinter`.
- [ ] `W04.P12.S31` - Assert no module under the inference subpackage constructs an attachment store or resolves secure storage, red if the assertion passes against a module that does; `src/cadrumo/tests/`.
- [ ] `W04.P12.S60` - Assert no rasterised page image reaches disk in the clear including as an intermediate, red if a deliberate page-image write inside the subpackage is not refused; `src/cadrumo/tests/`.
- [ ] `W04.P12.S61` - Assert the subpackage carries no debug-dump or temp-file escape hatch at any log level, red if a deliberate NamedTemporaryFile added under debug logging is not refused; `src/cadrumo/tests/`.
- [ ] `W04.P12.S73` - Enrol the inference subpackage in the layered import contract's layer list, since a subpackage inherits no layering and the contract has no opinion on an unlisted module; `.importlinter`.
- [ ] `W04.P12.S74` - Add the inference subpackage to the forbidden-module contracts that must catch a core or domain module importing it, red if a deliberate import of the subpackage from core does not fail import-linter; `.importlinter`.
- [ ] `W04.P12.S75` - Prove the enumerated sensitive-surface tier reaches the relocated code by introducing and reverting a temp-file write inside the subpackage, targeting the enumerated tier specifically rather than the whole-tree rglob tier which was never in doubt; `src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`.
- [ ] `W04.P12.S76` - Prove the vacated outbound llm surface entry is either removed or still resolves to real modules, red if the relocation leaves a named entry pointing at an emptied directory; `src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`.

## Wave `W05` - Wire local text inference, then delete the cloud subprocess path

Implements D5 in its mandated order. A local text reader is wired and proven first; only then is the cloud subprocess path and its orphan set deleted. Reordering these Steps would open a window in which text-layer PDFs cannot be classified at all.

### Phase `W05.P10` - Wire and prove a local text reader

Closes the capability gap that the cloud deletion would otherwise open.

- [ ] `W05.P10.S44` - Wire the local provider into the classify path as a text reader for the first time, red if a text-layer PDF still routes to a non-local transport; `src/cadrumo/application/ledger/_llm_classification.py`.
- [ ] `W05.P10.S45` - Choose the local text model under the consumer-hardware constraint that binds the vision default, red if the chosen model's floor exceeds the declared hardware floor; `src/cadrumo/application/provisioning.py`.
- [ ] `W05.P10.S46` - Prove a text-layer PDF classifies through the local reader before any deletion Step closes, red if the proof is recorded against a fixture the local reader never touched; `src/cadrumo/application/ledger/tests/`.

### Phase `W05.P11` - Delete the cloud path and its orphan set

Removes the off-host transport and everything it alone kept alive.

- [ ] `W05.P11.S47` - Delete the subprocess classifier family and its provider builders, red if the shared prompt and parse machinery the local classifier reuses is removed with it; `src/cadrumo/domain/transactions/_llm.py`.
- [ ] `W05.P11.S48` - Delete the cloud consent gate and its service capability branch across the evidence input, core capabilities and profile capabilities, red if any capability resolver still returns a cloud-upload branch; `src/cadrumo/application/ledger/_evidence_input.py`.
- [ ] `W05.P11.S49` - Delete the gestor-mode and cloud-upload settings left orphaned by the consent gate, red if any settings field survives with no reader; `src/cadrumo/core/config.py`.
- [ ] `W05.P11.S50` - Delete the provider selection flag and the evidence acknowledgement flag from the classify verb, red if either flag still parses; `src/cadrumo/entrypoints/cli/_ledger.py`.
- [ ] `W05.P11.S51` - Delete the subprocess provider probe and its config-check branch, red if config check still reports a subprocess provider; `src/cadrumo/application/provisioning.py`.
- [ ] `W05.P11.S52` - Delete the providers listing command left with nothing to list, red if the verb still registers in the operator surface manifest; `src/cadrumo/entrypoints/cli/_ledger_read_cli.py`.
- [ ] `W05.P11.S53` - Delete the cloud-only test modules wholesale, counting them against a fresh sweep rather than against the ADR's unverified estimate of nine; `src/cadrumo/application/ledger/tests/`.
- [ ] `W05.P11.S54` - Edit the remaining mixed test modules case by case since the evidence resolver branches internally, red if a case is deleted rather than re-pointed and its coverage silently disappears; `src/cadrumo/application/ledger/tests/`.
- [ ] `W05.P11.S55` - Prove by tree-wide search that no cloud transport reference survives dormant anywhere in the tree, red if the search pattern is narrowed until it returns clean rather than the tree being cleaned; `src/cadrumo/`.
- [ ] `W05.P11.S77` - Amend the superseded ADR's status to record that its cloud-read ruling is narrowed by this campaign, landing in the same change as the deletion so the corpus never carries two accepted records sanctioning opposite postures; `.vault/adr/`.
- [ ] `W05.P11.S78` - Update the provenance stamp's documentation to record that the provider axis collapses to the local runtime after the deletion, without rewriting any pre-existing stamped record; `src/cadrumo/application/ledger/`.

## Parallelization

`W01` and `W02` are mutually independent and may run concurrently. `W01` touches packaging, provisioning and the gate corpus; `W02` touches ingestion and adds no dependency, since `defusedxml` is already a declared runtime requirement.

**`W01.P02`'s non-vacuity assertion must land before any Step that creates or empties a sensitive surface**, which means before `W04` in every ordering. It is placed in `W01` rather than in `W04` deliberately: an instrument repaired after the interval it was supposed to police proves nothing about that interval, and the assertion protects all eighteen enumerated surfaces rather than only this campaign's. It is independent of everything else in the plan and could be lifted out and landed on its own.

`W03` must complete before `W04` begins. The interchange contract is what the relocated modules are relocated behind, and moving behaviour before the contract exists would require rewriting each moved call site twice.

**Nothing that names `src/cadrumo/llm/` may be scheduled before `W04.P08` creates it.** This is the ordering constraint a prior draft violated in three places, and it is not a stylistic preference: an enumerated-surface entry, an import contract, and an AST assertion all pass silently against a path that does not exist. `W04.P12` therefore holds every control that names the subpackage, and it runs last within `W04`. The surface enumeration is the one exception to "last": it lands inside `W04.P08.S32`, the same atomic commit that creates the directory, because between creation and enumeration the code is unguarded.

`W04` must complete before `W05` begins, because the cloud path's deletion touches the same module that `W04` divides.

Inside `W05` the ordering is mandated rather than preferred: the local text reader is wired and proven before any deletion Step runs. Reordering opens a window in which text-layer PDFs cannot be classified at all. A plan executor may not reorder those Steps for convenience.

Two campaigns are live on adjacent surfaces: `2026-08-05-ledger-invoice-decomposition` and `2026-08-06-invoice-canonical-structure`, the latter owning the invoice stores and the writer surface. Before any first edit to a shared file, run `git diff -- <file>` and abort on non-authored WIP.

## Coordination with the invoice-canonical-structure campaign

Both campaigns hand off to separate teams in the same worktree. Two teams colliding here is the
failure mode, so the partition below is agreed with that lane rather than assumed, and is
recorded here so neither team has to reconstruct it from a conversation.

**The file both campaigns touch is `application/ledger/_evidence_draft.py`, and the partition
runs between the model and the function.**

- **This campaign owns the `InvoiceDraft` model and the extraction/parse path** - the
  line-carrying structure, the per-rate breakdown, and the recargo slot.
- **That campaign owns the confirm *function*** - widening the override parameter list of
  `confirm_invoice_draft_from_evidence`, and the plausibility gate inside it. Neither of its
  Steps touches a draft field.
- **The recargo draft slot transferred to this campaign** as `W02.P04.S79`. That lane is
  re-scoping its own Step to the confirm side. The reason it cannot simply be dropped: the draft
  path already records that a recargo "has nowhere to go", and a peer-landed printed-total
  discrepancy check now *detects* the resulting under-declaration while the operator has no
  field to resolve it into. A firing advisory with no available remedy is worse than none.

**Ordering constraint, and it binds.** That lane's writer half has **not** landed - it is an
open Step with no execution record - and it is larger than its ADR first said: there are **two**
single-line synthesis sites, the canonical builder and the live bulk-import surface reachable
from the catalogue import verb, whose own docstring says it synthesises a single line exactly as
the builder does. Its Step now covers both. **`W02.P05.S70` here must be sequenced after that
writer Step**, because the writer half alone ships no operator-visible change on the extraction
path and the reader half is what makes it visible. Expect the writer Step to be proven first by
an operator-supplied multi-rate invoice rather than by a parsed one.

**Four constraints from the receiving shape, verified at HEAD**, which the parsers must be built
against rather than discovering later:

1. **`InvoiceLine.iva_rate` is the closed `IvaRate` slot enum, not a `Decimal`.** The draft's
   rate is a bare decimal today, so the draft-to-line mapping crosses an enum boundary. A parsed
   rate with no matching slot **must refuse loudly and must never round to the nearest member** -
   an unread rate currently resolves to the exempt slot, minting a zero-cuota invoice whose
   printed total still shows the cuota charged. Note the trap this makes concrete: the enum
   deliberately omits a slot for the transient 2022-2024 5% rate, so a pre-2025 document is
   exactly the case that must refuse. Carried as `W02.P04.S80`.
2. **`InvoiceLine.category_id` is being renamed by that lane.** Do not bind the parsers to that
   name; leave it unset and take the new name when it lands.
3. **Invoice-level identity:** grand total equals base plus IVA plus recargo, with retención
   **outside** the grand total. Per-line tolerance is 0.01; **invoice-level is exact**. Carried
   as `W02.P05.S81`.
4. **A persisted invoice requires at least one line**, a non-empty counterparty name and a
   two-letter counterparty country.

**Not shared:** this plan does not touch the invoice stores, the canonical writer, the bulk
import surface, or the M303 and M390 screens. `Invoice.lines` and the per-line aggregation
already exist, so **neither side authorises a persisted-schema change**. The evidence-record
identity defect is owned here, not there, because the surface is evidence registration.

## Decision-to-Step coverage

Every ADR decision maps to at least one Step, with two deliberate exceptions. **D2** defers the
distribution boundary and **D8** leaves the internal pipeline shape open; both are decisions
*not* to build something, so a Step implementing either would be a Step implementing a
non-decision. They are recorded here so a reviewer checking coverage does not read their
absence as an omission. The remaining map: D1 → `S01`, `S02`, `S65`, `S03`, `S32`-`S38`;
D3 → `S30`, `S31`, `S41`; D4 → `S23`-`S28`; D5 → `S44`-`S55`, `S77`, `S78`; D6 → `S06`, `S07`;
D7 → `S10`-`S22`, `S56`-`S58`, `S67`-`S71`; D9 → `S59`-`S62`, `S64`; D10 → `S63`, `S75`, `S76`;
D11 → `S08`, `S09`, `S72`; D12 → `S73`, `S74`; D13 → `S69`, `S71`.

## What this plan deliberately does not do

The governing ADR carries a *Deliberately out of scope* section naming every source-discovery finding this campaign drops and why: ingest-time sanitization, the residual accept-then-refuse formats (CSV, XLSX, plain text, `.eml`), the scale verbs, the remaining reader-only field gaps, recargo on the extraction draft, the manifest-merge provenance discard, generalising `PrintedTotalDiscrepancy`, and the injection-through-markdown regression gate. An executor who finds one of those adjacent to a Step should read that section rather than absorb the work, and should treat a finding that is *not* listed there as genuinely unhandled rather than silently accepted.

## Verification

The plan is complete when every Step is closed and the following hold.

**Every claim below is stated so that it can be false.** A verification line that no execution could fail is not a verification line, and the prior draft carried three.

The extra is real, not nominal: a clean install without the `llm` extra exposes the inference verbs as a placeholder group refusing with the declared install hint, and never raises `ModuleNotFoundError`. The extra is registered in `OPTIONAL_EXTRAS` rather than hand-rolled. `Pillow` is declared as a **direct** `[project.dependencies]` entry in addition to the extra, carrying the `lxml` comment's incidental-transitive rationale - the extra alone does not remove the undeclared direct reliance, since `pdfplumber` and `pikepdf` keep Pillow in the base closure regardless. `pypdfium2` was already declared and is not part of this fix.

**The enumerated gate tier fails loudly, and this is checked before anything depends on it.** Every entry in `_SENSITIVE_SURFACES` resolves to at least one non-test module or the gate fails naming the entry. The assertion is proven by pointing an entry at a nonexistent path and observing red. Absent this, the tier reports success identically for a clean surface and for a surface that has been deleted, renamed, emptied by relocation, or enumerated before it exists.

**Gate coverage is stated per check, with its mechanism named, because "the five gates scan `src/cadrumo/llm/`" is not a checkable outcome.** The five checks do not share a mechanism: the whole-tree file-write inventory and the storage-provenance restriction scan by rglob and therefore reach any new directory under the scanned root automatically; the sensitive-surface check **enumerates** and reaches a new directory only when that directory is added to its list; the staging-directory pin and the ephemeral-key check have different scopes again and do not bear on a new subpackage at all. The verification is: the subpackage is enumerated in the sensitive-surface list in the same change that creates it, and a deliberately introduced temp-file write inside that directory is refused by the **enumerated** tier specifically - a mutation proof run and reverted within the Step, after the directory exists. Proving the rglob tier would prove the tier that was never in doubt.

**`cadrumo.llm` is enrolled in the layering contract, not merely present in the import graph.** It appears in the `layers` list and in the `forbidden` contracts that must catch a `core` or `domain` module importing it. Verified by introducing a deliberate violating import from `core`, observing import-linter red, and reverting. Import-linter passing on an unenrolled module is not evidence, because it has no opinion on one; `exhaustive` remains `false` and is deliberately not changed here.

The vacated `adapters/outbound/llm` entry is either removed or still resolves to real modules. A named entry pointing at an emptied directory is a failed outcome, and before the non-vacuity assertion it was an invisible one.

Structured reading is exact and enrolled: the ZUGFeRD corpus fixture is asserted field by field against its printed values rather than for the presence of a German word, an EN16931 UBL document and a Facturae 3.2.x document each parse to the same line-carrying extraction draft, and the core evidence read path reaches those parsers rather than routing around them - proven by deleting the parser and observing the corpus test red. The two diagnosed parser defects are closed: the VAT number is selected as the party tax identifier rather than a SIRET or Steuernummer, and emisor and destinatario are mapped the right way round on received-invoice SII records.

**The parsers are reachable from the front door.** A standalone Facturae or EN16931 XML is accepted at `aeat app ledger evidence add --file`, not only when it happens to arrive through `doclink` or `pull-folder`. A parser behind a closed ingest gate is the campaign's own named failure mode, not a partial success. The dangling `evidence-source-expansion` reference is gone from the refusal message, since this campaign discharges that deferral and a vault stem cited from source breaches *Code Stands Alone*.

**The reader half the sibling campaign is waiting on exists and is proven end to end.** The extraction draft carries a line set and a per-rate IVA breakdown; a two-rate structured document round-trips from parse through `confirm_invoice_draft_from_evidence` to a confirmed multi-line invoice with both rates intact. A draft that still collapses two rates to one base-and-cuota pair is a failed outcome - it would leave the multi-rate silent collapse alive in a campaign whose claim is that the structured path is exact. The confirm boundary is crossed, not bypassed, so the sibling ADR's plausibility gate keeps its placement.

**Re-ingest is idempotent when the caller asks for it.** `evidence add` accepts an idempotency key; when one is supplied the record id is clock-free and a re-add over one blob resolves to the existing record as a guarded no-op, emitting no second bucket event and re-stamping no timestamp. A same-key re-add whose content differs refuses with an instructive conflict naming the divergent fields, and the match compares **every** persisted field - a no-op that matches on a subset and silently drops a changed value is a failed outcome, not a partial success. The keyless path stays deliberately additive with its documented genuine-duplicate rationale intact: collapsing two legitimate attachments of the same file into one record is equally a failed outcome.

Structured reading fails loudly: a malformed structured document refuses with a parse error and yields no record, rather than returning a partial one.

The interchange refuses rather than coerces: a malformed payload presented at the core boundary raises, and an anti-tautology proof mutates a well-formed payload to prove the refusal fires on the mutation rather than passing vacuously. Free text is never the interchange value.

The persistence boundary holds structurally: no module under `src/cadrumo/llm/` imports from `adapters.persistence`, constructs an `AttachmentStore`, or resolves secure storage, enforced by an import contract rather than by review.

Nothing durable lands in the clear: the extracted-document cache is written content-addressed and encrypted through the core, no rasterised page image or debug dump or temp file reaches disk in any form at any log level, and persisted field drafts route through the core. A plaintext on-disk cache of invoice contents is a failed outcome, not an optimisation. The cache is deliberately **not** called a *normalization* cache: that name presupposes the normalize-then-extract separation the ADR leaves undecided, and no Step title may assert a decision the ADR says is open.

The encryption exemption is pinned, not merely honoured: a test records that in-memory reading, rasterising and local inference require no encryption and no consent gate, so a later agent does not reintroduce custody ceremony the operator ruled unnecessary.

Provenance survives the boundary: a persisted record derived from an extension read carries its `legal_refs`, `source_refs`, typed source kind, and the model identity and revision that produced it, proven through a strict save-load-equality roundtrip against the real encrypted namespace with every defaultable field populated non-default, paired with an anti-tautology proof that deleting a persisted field reddens the load.

The cloud path is gone, not dormant: no reference to the subprocess classifier family, `cloud_evidence_read_permitted`, `ServiceCapability.CLOUD_EVIDENCE_UPLOAD`, the gestor-mode and cloud-upload settings, `--evidence-acknowledged`, `--llm`, `probe_subprocess_providers`, or `aeat app ledger providers` remains in the tree, confirmed by a tree-wide search. A dormant retained path is a failed outcome, not a partial success. The search pattern is fixed before the sweep runs: narrowing a pattern until it returns clean is the failure this line exists to catch.

**The decision corpus is left self-consistent.** `2026-06-10-llm-evidence-classification-adr`'s status records that its cloud-read ruling is narrowed here, amended in the same change that lands the deletion. Two accepted records, one sanctioning a capability the other deletes, is a failed outcome. The `llm:<provider>:<model>` provenance stamp's documentation records that the provider axis collapses to the local runtime, and no pre-existing stamped record is rewritten.

Text-layer PDFs remain classifiable throughout: a test proving the local text reader classifies a text-layer PDF passes before the first deletion Step closes.

Every relocation Step names, in its execution record, the core call site that now reaches the moved code. Every symbol relocation lands as one atomic explicit-path commit carrying the canonical-site move, every consumer update, every fixture update and every `__all__` update, with `uv run --no-sync pytest --collect-only -q` observed clean immediately before the commit. `python -m dev.docs.apidocs scaffold --check` and the locale `scaffold --check` both exit clean after the relocations and deletions.
