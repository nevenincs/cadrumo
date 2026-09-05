---
tags:
  - '#plan'
  - '#reachability-burndown'
date: '2026-09-04'
tier: L3
related:
  - '[[2026-09-04-reachability-burndown-adr]]'
  - '[[2026-09-04-reachability-burndown-reference]]'
modified: '2026-09-05'
body_schema: body-v2
body_hash: 'sha256:fd663f1e104064df4471c1f8553b575230390bac94fcd511065e14898adcff20'
---

# `reachability-burndown` plan

## Description

Close the false green in entrypoint reachability. The audit reports 43 modules and 1408 symbols that no declared console script reaches, plus 21 orphaned test modules, while the standing ratchet exits 0 because it adjudicates modules only and defers a frozen prefix. W01 turns one undifferentiated population into evidenced classes, because the remedies differ completely and the wrong remedy either deletes capability or wires code to nothing. W02 relocates code whose callers prove it belongs elsewhere, smallest blast radius first. W03 clears the symbol backlog by owning package. W04 extends the gate to symbols and orphaned tests and proves the joined state.

## Steps

## Wave `W01` - classify the population

Turn one undifferentiated audit population into evidenced classes. Every later wave depends on knowing which remedy a finding needs, and applying the wrong remedy deletes capability or wires code to nothing.

### Phase `W01.P01` - survey and classify

Produce an evidenced classification for every module and orphaned-test finding, and for the symbol population by owning package.

- [x] `W01.P01.S01` - Classify every unreachable and module-exec-only module by outside-use label and semantic uniqueness probe, recording the evidence behind each supersession or staging claim; `dev/audit`.
- [x] `W01.P01.S02` - Classify the 21 orphaned test modules against whether their shipped subjects are themselves findings; `src/cadrumo`.
- [x] `W01.P01.S03` - Partition the exact-confidence symbol population by owning package and record the dominant kinds per area; `dev/audit`.

## Wave `W02` - resolve by owning home

Relocate code whose only callers prove it belongs elsewhere, smallest blast radius first. Dev-only harness code precedes test-only support because it leaves the shipped wheel without touching the product surface.

### Phase `W02.P02` - relocate dev-only harness code

Move modules whose only callers are dev/ beside the consumer that drives them.

- [x] `W02.P02.S04` - Relocate dev-only harness modules beside their dev consumers and shrink the ratchet by the entries resolved; `dev`.
- [x] `W02.P02.S15` - Record the design-time-authority modules as intentional in the module ratchet with their conformance-gate reader named, rather than relocating product declarations into dev; `dev/quality`.

### Phase `W02.P03` - relocate test-only support

Move shared test support into the wheel-excluded test tree and verify the distributed artifact.

- [x] `W02.P03.S05` - Relocate test-only support into the wheel-excluded test tree and prove the distributed artifact no longer carries it; `src/cadrumo/tests`.

### Phase `W02.P04` - adjudicate owner-decision modules

Resolve modules requiring a delete-or-wire decision, each with its authorising record.

- [x] `W02.P04.S06` - Resolve the operator_surface CRUD catalogue cluster against its conformance-test consumer; `src/cadrumo/application/operator_surface`.
- [x] `W02.P04.S07` - Adjudicate the staged-capability modules against their authorising decisions and classify or wire each; `src/cadrumo/application`.

## Wave `W03` - burn down the symbol backlog

Resolve the 1408 unused symbols by owning package, largest concentration first. Symbols are ungated today, so this wave carries the bulk of the false green.

### Phase `W03.P05` - resolve domain and registry symbols

Clear the largest exact-confidence concentration at its owning boundary.

- [x] `W03.P05.S08` - Resolve the domain/calculations exact-confidence symbol concentration at its owning boundary; `src/cadrumo/domain/calculations`.
- [x] `W03.P05.S13` - Resolve the superseded-constant population detected by literal-value supersession, naming the live holder for each before removal; `src/cadrumo`.
- [x] `W03.P05.S14` - Triage the test-only symbol population into behaviour that retires with its test and seams whose missing production call is the defect; `dev/audit`.

### Phase `W03.P06` - resolve CLI and application symbols

Clear the entrypoints and application concentrations without disturbing command contracts.

- [x] `W03.P06.S09` - Resolve the entrypoints/cli symbol concentration without altering command contracts; `src/cadrumo/entrypoints/cli`.
- [x] `W03.P06.S10` - Resolve the application/modelo and adapters/persistence symbol concentrations; `src/cadrumo/application`.

### Phase `W03.P09` - merge duplicate definitions to canonical homes

Duplicate module-level definitions are a correctness hazard, not untidiness: two copies drift, and a caller reaching the stale one gets a value nobody updated. Each family merges to one canonical home with every call site repointed.

- [x] `W03.P09.S16` - Merge the duplicated Decimal constants to a canonical home and repoint every call site, since a drifted numeric constant is a calculation defect; `src/cadrumo/core`.
- [x] `W03.P09.S17` - Merge the duplicated TypeAdapter declarations at their owning registry boundary; `src/cadrumo/domain/calculations/registry`.
- [x] `W03.P09.S18` - Adjudicate the 76 names defined with DIFFERENT values across modules, where merging would be wrong and one side needs renaming; `dev/audit`.
- [x] `W03.P09.S19` - Resolve the _WHITESPACE_RE collision, where one module compiles a single-whitespace matcher and three compile a run matcher under the same name; `src/cadrumo`.

## Wave `W04` - extend the gate and close

Extend the ratchet to symbols and orphaned test modules once their populations carry classifications, then prove the joined state. Extension is shrink-only from the day it lands.

### Phase `W04.P07` - extend the ratchet

Bring symbols and orphaned test modules under the gate, shrink-only.

- [x] `W04.P07.S11` - Extend the ratchet to unused symbols and orphaned test modules with detector-teeth proof; `dev/quality`.

### Phase `W04.P08` - prove the joined state

Re-measure every signal from one stable revision and prove no false green remains.

- [x] `W04.P08.S12` - Re-measure every signal from one stable revision and prove no false green remains; `dev/audit`.

## Wave `W05` - Residue the completed waves did not reach

Waves one to four closed on their declared scope, and the live audit still reports 136 unreferenced in-scope symbols, 58 unreachable modules and 25 orphaned test modules. The gap is not unfinished execution but unclassified residue: 85 of the 136 are names their module publishes in `__all__`, so removing one changes what the package offers and is an owner's decision rather than a deletion. This wave separates the 51 that are safe to delete from the 85 that need a published-surface ruling, and stops treating a complete plan as a closed backlog.

### Phase `W05.P10` - Delete the residue that publishes nothing

The 51 findings no module publishes and no caller reaches. Each is removed at its definition with its deletion cascade followed to the helpers it orphans, and the module's ratchet count lowered rather than dropped whenever findings remain.

- [x] `W05.P10.S20` - Retire the constants superseded by the file-backed master-key provider's deletion and merge the storage KDF salt length onto its one canonical home; `src/cadrumo/adapters/persistence/storage`.
- [x] `W05.P10.S21` - Extend the constant-agreement screen to detect a canonical value restated under a related name, with detector-teeth proof for both noise guards; `dev/quality/constant_value_agreement.py`.
- [x] `W05.P10.S22` - Delete the remaining unreferenced non-exported findings module by module, following each deletion cascade and lowering the ratchet rather than removing a still-populated entry; `src/cadrumo`.

### Phase `W05.P11` - Rule on the published surface

The 85 exported findings, and the 367 declared exports package-wide that no module imports. Removal changes what the package publishes, so this phase produces the inventory and a proposed disposition per area for an owner to rule on; it does not delete a published name on the executor's own authority.

- [x] `W05.P11.S23` - Inventory every exported-but-unimported name by owning area and propose a disposition per area for an owner's ruling; `dev/audit`.
- [x] `W05.P11.S24` - Gate the unconsumed-export population so the owner review is not overtaken by growth, and triage it by area and by shape; `dev/quality/unconsumed_export_ratchet.py`.

### Phase `W05.P12` - residue classification after plan closure

The plan closed at 24/24 while the live audit still reports 58 unreachable modules, 1322 unused symbols and 25 orphaned test modules. The completed steps were genuinely done; they simply did not enumerate the whole backlog. This phase carries the residue that measurement, not planning, identified.

- [x] `W05.P12.S25` - Establish whether the enum-member tier is dead code or an instrument gap: 204 of 305 enum-member findings carry a literal value present in shipped registry declarations, 174 of them in one module bound by value in the Modelo 200 projection_endpoints declarations, and fix the binding rule tightly enough that it cannot suppress a real finding; `dev/audit/unreachable_code.py`.
- [x] `W05.P12.S26` - Classify with their owners the shipped modules that block the ratchet and fit no available disposition, since IntentionalReachabilityKind admits only design_time_authority and the allowed list is shrink-only; `dev/quality/unreachable_module_ratchet.toml`.
- [x] `W05.P12.S27` - Re-measure the orphaned test population against its anchors and resolve any test still reported after the module or symbol it covers has been resolved; `dev/audit`.
- [ ] `W05.P12.S28` - Obtain the owner decisions the three blocked modules need, since classification is evidenced and none can be recorded without them: re-wire or withdraw the ledger import-preparation capability its contract still requires, and either record the decision the two staged domain packages are waiting on or withdraw them; `src/cadrumo/application/ledger/import_preparation.py`.
- [x] `W05.P12.S29` - Close the orphan-walk blind spot in which 239 of 3334 test modules name no shipped subject because they reach their code through a support module inside their own test package, so a dead test behind that hop can never be reported; traverse the hop without letting a live subject reached that way suppress an existing finding; `dev/audit/unreachable_code.py`.

## Parallelization

Waves are ordered: no resolution proceeds before its finding is classified, and the gate extends only after the populations it will cover carry classifications. Within W02 the three phases are independent by ownership and may run in parallel, though P02 precedes P03 in practice because dev-only relocation leaves the shipped wheel untouched. Within W03 the two phases own disjoint packages. The `cadrumo.entrypoints.tui` prefix stays deferred throughout while its owning campaign is in flight, so 26 of the module findings are out of scope here. Executors check the shared worktree before every step and must not modify peer-owned dirty files.

## Verification

- Every module, orphaned-test, and exact-confidence symbol finding carries exactly one class from the ADR's closed taxonomy, and every supersession or staging claim names the evidence that established it.
- Semantic uniqueness claims are grounded by a recorded `vaultspec-rag` query over production code, not by name similarity; class-level supersession additionally names the live type that discharges the responsibility.
- Each relocation is proven by the distributed artifact no longer carrying the module, and by the owning tests passing from their new home.
- Each deletion of shipped capability cites the record authorising it; no capability is removed on the audit's say-so alone.
- The ratchet's `allowed` list only ever shrinks, and the extended gate demonstrates a representative defect is detected for both symbols and orphaned test modules.
- No threshold, exclusion, baseline, skip, or allowlist widening appears in any step's diff.
- Closure requires the audit and the extended ratchet to agree from one stable revision, with the remaining count explained entirely by classified, recorded dispositions.
