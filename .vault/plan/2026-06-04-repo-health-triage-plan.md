---
tags:
  - '#plan'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
tier: L3
related:
  - '[[2026-06-04-repo-health-triage-research]]'
  - '[[2026-06-04-repo-health-triage-reference]]'
  - '[[2026-06-04-repo-health-triage-adr]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
  - '[[2026-06-04-uv-venv-lock-workaround-audit]]'
  - '[[2026-05-19-code-duplication-sweep-plan]]'
  - '[[2026-05-26-secure-storage-test-hygiene-audit]]'
---


# `repo-health-triage` `diagnostic remediation` plan

## Description

Execute the repository-health findings from the first full diagnostic pass in a
sequence that protects the shared worktree: stabilize hard gates first, repair type
root causes second, decompose complexity hotspots third, clean focused hygiene
findings fourth, and promote ratchets only after baselines are reviewed.

## Steps

## Wave `W01` - stabilize diagnostic gates

Close small hard-gate failures and make the current diagnostic surface dependable before broader remediation begins.

### Phase `W01.P01` - environment and RAG baseline

Preserve the repaired no-sync environment and record that semantic searches must use the resident RAG service.

- [x] `W01.P01.S01` - Verify no-sync tooling doctor remains green; `justfile`.
- [x] `W01.P01.S02` - Record resident RAG port usage for health triage searches; `.vault/reference/2026-06-04-repo-health-triage-reference.md`.

### Phase `W01.P02` - structural import gates

Close the small relative-import and layered-boundary blockers without weakening production architecture rules.

- [x] `W01.P02.S03` - Remove corpus provenance AST absolute self-import through the resource boundary; `src/aeat/_data/corpus/test_corpus_provenance.py`.
- [x] `W01.P02.S04` - Convert ECB provider self-imports to relative imports; `src/aeat/adapters/outbound/fx/_ecb_provider.py`.
- [x] `W01.P02.S05` - Convert ECB refresh self-import to a relative import; `src/aeat/adapters/outbound/fx/_ecb_refresh.py`.
- [x] `W01.P02.S06` - Convert user-profile re-export tests to relative package imports; `src/aeat/application/user_profile/test_bundle_reexports.py`.
- [x] `W01.P02.S07` - Convert workflow declaration-key test to relative package import; `src/aeat/application/workflow/test_declaration_key.py`.
- [x] `W01.P02.S08` - Encode layered test-helper import policy without masking production violations; `.importlinter`.

### Phase `W01.P03` - shim and test-hygiene gates

Repair broken shim/test guard surfaces and remove concrete monkeypatch inventory failures.

- [x] `W01.P03.S09` - Repair the missing verify-shims command surface; `justfile`.
- [x] `W01.P03.S10` - Remove undocumented Google resolver monkeypatch service seams; `src/aeat/adapters/outbound/google/test_document_link_resolver.py`.
- [x] `W01.P03.S11` - Verify skip mock and monkeypatch inventory gates after repair; `src/aeat/test_monkeypatch_inventory.py`.

## Wave `W02` - repair type-control root causes

Reduce type diagnostics by fixing shared contract patterns instead of adding local casts or ignores.

### Phase `W02.P04` - aggregation source-kind taxonomy

Make aggregation source-kind values enum-backed internally with explicit boundary narrowing.

- [x] `W02.P04.S12` - Normalize aggregation counterpart source-kind construction; `src/aeat/application/aggregation/_counterpart.py`.
- [x] `W02.P04.S13` - Add explicit counterpart source-kind narrowing helper; `src/aeat/core/aggregation.py`.
- [x] `W02.P04.S14` - Migrate registry binding source-kind callers to enum-backed values; `src/aeat/domain/calculations/registry/_bindings.py`.

### Phase `W02.P05` - secure repository payload typing

Repair the generic payload contract once in the secure repository base and apply it to subclasses.

- [x] `W02.P05.S15` - Replace invariant payload ClassVar override pattern with a typed accessor; `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`.
- [x] `W02.P05.S16` - Migrate justificante repository payload typing to the base pattern; `src/aeat/domain/justificante/_repository.py`.
- [x] `W02.P05.S17` - Migrate submission repository payload typing to the base pattern; `src/aeat/domain/submission/_repository.py`.
- [x] `W02.P05.S18` - Migrate apoderado repository payload typing to the base pattern; `src/aeat/application/auth/_apoderado.py`.

### Phase `W02.P06` - local narrowing and strict generics

Close checker-specific narrowing, return-type, protocol, and generic-argument diagnostics in focused packages.

- [x] `W02.P06.S19` - Fix sanitizer post-error variable narrowing; `src/aeat/adapters/inbound/sanitizer/_pipeline.py`.
- [x] `W02.P06.S20` - Tighten aggregation source-mesh optional narrowing; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `W02.P06.S21` - Tighten registry-provider and currency predicate return types; `src/aeat/application/aggregation/_registry_provider.py`.
- [x] `W02.P06.S22` - Add strict generic arguments to usage-ratio services; `src/aeat/domain/usage_ratios/_service.py`.
- [x] `W02.P06.S23` - Record focused typecheck audit baseline after type repairs; `.vault/audit`.

## Wave `W03` - decompose complexity hotspots

Split the largest cognitive-load clusters behind existing public surfaces after structural and type gates are stable.

### Phase `W03.P07` - modelo CLI command extraction

Turn the modelo CLI hotspot into command-family modules that parse, call application services, and render unchanged outputs.

- [x] `W03.P07.S24` - Split modelo work command family behind existing Typer wiring; `src/aeat/entrypoints/cli/_modelo_work.py`.
- [x] `W03.P07.S25` - Extract work-calculate typed input assembly; `src/aeat/application/modelo/_calculate_input.py`.
- [x] `W03.P07.S26` - Preserve modelo root command compatibility after extraction; `src/aeat/entrypoints/cli/_modelo.py`.

### Phase `W03.P08` - modelo application orchestration

Split modelo application orchestration into typed binding, wallet, and persistence services without changing revision semantics.

- [x] `W03.P08.S27` - Extract modelo binding-resolution service; `src/aeat/application/modelo/_binding_resolution.py`.
- [x] `W03.P08.S28` - Extract modelo IVA wallet gate service; `src/aeat/application/modelo/_iva_wallet_gate.py`.
- [x] `W03.P08.S29` - Extract modelo revision-persistence service; `src/aeat/application/modelo/_revision_persistence.py`.

### Phase `W03.P09` - registry runtime decomposition

Extract registry binding and formula-runtime families one at a time while preserving registry authority flow.

- [x] `W03.P09.S30` - Extract previous-filing binding family; `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`.
- [x] `W03.P09.S31` - Extract formula initial-value materialization; `src/aeat/domain/calculations/registry/_formula_initial_values.py`.
- [x] `W03.P09.S32` - Verify registry workbook parity complexity baseline; `src/aeat/domain/calculations/registry/_workbook_parity.py`.

### Phase `W03.P10` - ledger and diagnostics decomposition

Reduce ledger and identity diagnostic complexity through projection and analyzer boundaries.

- [x] `W03.P10.S33` - Extract ledger review-filter projection service; `src/aeat/application/ledger/_review_projection.py`.
- [x] `W03.P10.S34` - Split ledger list CLI parsing and rendering; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W03.P10.S35` - Remove unapproved diagnostics source package; `src/aeat/diagnostics`.

### Phase `W03.P11` - live and auth decomposition prep

Capture live/auth invariants and ADR scope before touching high-risk Playwright and encrypted-session flows.

- [x] `W03.P11.S36` - Audit live and auth split invariants before implementation; `.vault/audit`.
- [x] `W03.P11.S37` - Prepare dedicated live-auth decomposition ADR; `.vault/adr`.

## Wave `W04` - clean dependency dead-code and duplication findings

Resolve focused dependency and dead-code issues, then reduce residual duplication one cohesive boundary at a time.

### Phase `W04.P12` - dependency declaration hygiene

Resolve the six Deptry findings by declaring runtime imports explicitly or documenting optional/stale ownership.

- [x] `W04.P12.S38` - Decide formulas runtime optional or stale ownership; `pyproject.toml`.
- [x] `W04.P12.S39` - Decide rich runtime optional or stale ownership; `pyproject.toml`.
- [x] `W04.P12.S40` - Decide torch runtime optional or stale ownership; `pyproject.toml`.
- [x] `W04.P12.S41` - Declare or optionalize playwright-stealth consistently; `pyproject.toml`.
- [x] `W04.P12.S42` - Declare or optionalize prompt-toolkit consistently; `pyproject.toml`.

### Phase `W04.P13` - dead-code candidate triage

Review and close the 15 Vulture candidates without deleting side-effect or protocol surfaces blindly.

- [x] `W04.P13.S43` - Remove or justify unused Google API protocol variables; `src/aeat/adapters/outbound/google/_api.py`.
- [x] `W04.P13.S44` - Remove unused secure SQL CursorResult import; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [x] `W04.P13.S45` - Resolve submission draft-path Vulture candidate; `src/aeat/domain/submission/_protocols.py`.
- [x] `W04.P13.S46` - Convert CLI doc-reference payload imports to explicit registration or allowlist; `src/aeat/entrypoints/cli/_doc_reference.py`.

### Phase `W04.P14` - duplication cluster reduction

Reduce residual clone groups behind existing boundaries rather than introducing cross-layer shared utilities.

- [x] `W04.P14.S47` - Consolidate CSV and XLSX financial provider tabular extraction; `src/aeat/adapters/inbound/financial/providers`.
- [x] `W04.P14.S48` - Consolidate GROi and NIF IVA oracle driver flow; `src/aeat/domain/calculations/registry`.
- [x] `W04.P14.S49` - Review storage manifest and KDF schema overlap; `src/aeat/adapters/persistence/storage`.
- [x] `W04.P14.S50` - Consolidate locale traversal helpers; `src/aeat/locales`.

## Wave `W05` - promote policy ratchets

Separate noisy advisory findings into durable policies and ratchets only after scoped baselines are recorded.

### Phase `W05.P15` - security and site-authority policy

Split security scan policy by production, tests, mirrored data, and live site authority before treating counts as gates.

- [x] `W05.P15.S51` - Add Semgrep include and exclude policy; `.semgrepignore`.
- [x] `W05.P15.S52` - Document mirrored official data security disposition; `src/aeat/_data`.
- [x] `W05.P15.S53` - Add URL authority conformance gate; `src/aeat/domain/portals`.
- [x] `W05.P15.S54` - Add remote-state planned-operation conformance gate; `src/aeat/domain/calculations/registry/_remote_state_guard.py`.

### Phase `W05.P16` - Ruff and shim ratchets

Normalize lint scope and retire compatibility surfaces that conflict with the no-shim posture.

- [x] `W05.P16.S55` - Normalize Ruff scope for scratch and probe files; `pyproject.toml`.
- [x] `W05.P16.S56` - Resolve undefined modelo envelope emitter reference; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W05.P16.S57` - Canonicalize filing-status token and remove shim surface; `src/aeat/application/operator_surface/_filing_status_token.py`.
- [x] `W05.P16.S58` - Remove parsing private compatibility aliases; `src/aeat/core/parsing/__init__.py`.
- [x] `W05.P16.S59` - Review fail-closed HTTPX fallback naming and registration; `src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py`.

### Phase `W05.P17` - closeout baseline and review

Record the post-remediation advisory baseline and complete final code review before any new hard ratchets are promoted.

- [x] `W05.P17.S60` - Run full quality-audit and persist updated baseline; `.vault/audit`.
- [x] `W05.P17.S61` - Run final code review over all closed repo-health slices; `.vault/audit`.
- [x] `W05.P17.S62` - Update execution records and plan closure state; `.vault/exec`.

## Wave `W06` - all-green diagnostic burn-down

Drive every diagnostic class from advisory red to explicit green or documented ratchet state, using one scoped finding class per Step and preserving the shared-worktree no-sync execution discipline.

### Phase `W06.P18` - type checker all-green burn-down

Drive Ty and scoped Pyright findings down by cohesive diagnostic class, recording every remaining exception as an explicit ratchet rather than an untracked red baseline.

- [x] `W06.P18.S63` - Classify current Ty and Pyright diagnostics into executable finding buckets; `.vault/audit/2026-06-04-full-repo-health-diagnostics-audit.md`.
- [x] `W06.P18.S64` - Repair Declaracion parser boundary test typing; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [x] `W06.P18.S65` - Repair exception-hygiene AST location narrowing; `src/aeat/adapters/inbound/declaracion/test_exception_hygiene.py`.
- [x] `W06.P18.S66` - Normalize auth Settings test constructor values; `src/aeat/adapters/outbound/aeat/auth`.
- [x] `W06.P18.S67` - Repair aggregation error constructor and optional narrowing findings; `src/aeat/application/aggregation`.
- [x] `W06.P18.S68` - Repair filing repository generic payload residuals; `src/aeat/domain/filing`.
- [x] `W06.P18.S69` - Repair renta and transaction Decimal literal residuals; `src/aeat/domain`.
- [x] `W06.P18.S70` - Persist type all-green baseline or explicit residual ratchets; `.vault/audit`.

### Phase `W06.P19` - complexity all-green burn-down

Separate production complexity from ratchet-test complexity, then decompose the remaining cognitive-load hotspots until the production lane is green or explicitly thresholded.

- [x] `W06.P19.S71` - Split production-only complexity lane from package test ratchets; `justfile`.
- [x] `W06.P19.S72` - Add ratchet-test complexity lane for top-level package tests; `justfile`.
- [x] `W06.P19.S73` - Reduce wizard command catalogue cognitive complexity; `src/aeat/application/wizard/_commands.py`.
- [x] `W06.P19.S74` - Reduce remaining modelo CLI command cognitive complexity; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W06.P19.S75` - Reduce registry formula initial-value cognitive complexity; `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [x] `W06.P19.S76` - Reduce ledger list and review projection cognitive complexity; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W06.P19.S77` - Persist complexity all-green baseline or explicit residual ratchets; `.vault/audit`.

### Phase `W06.P20` - hygiene advisory all-green burn-down

Resolve dependency, dead-code, Ruff, security, and duplication advisory findings one class at a time without weakening hard architectural policies.

- [x] `W06.P20.S78` - Normalize Ruff scope for root scratch and probe artifacts; `pyproject.toml`.
- [x] `W06.P20.S79` - Resolve dependency declaration drift findings; `pyproject.toml`.
- [x] `W06.P20.S80` - Resolve Vulture dead-code candidate findings; `src/aeat`.
- [x] `W06.P20.S81` - Split Semgrep security policy by source class; `.semgrepignore`.
- [x] `W06.P20.S82` - Reduce remaining duplication clone groups or record ratchets; `src/aeat`.

### Phase `W06.P21` - final all-green ratchet and review

Run the complete diagnostic surface, persist a final all-green matrix, close plan rows through the CLI, and complete mandatory VaultSpec review before declaring the campaign green.

- [ ] `W06.P21.S83` - Run hard gate suite and persist green evidence; `.vault/audit`.
- [ ] `W06.P21.S84` - Run full quality-audit and persist final diagnostic matrix; `.vault/audit`.
- [ ] `W06.P21.S85` - Complete mandatory code review and close all-green campaign state; `.vault/exec`.

## Parallelization

Waves are ordered by default. Within `W01`, the relative-import, dependency, and
dead-code phases can run in parallel because they have disjoint write sets.
Within `W02`, aggregation typing and secure repository typing should run before
local narrowing cleanup. Within `W03`, modelo CLI and modelo application work must
be coordinated, while registry and ledger slices can proceed after their local
contracts are identified. `W04` phases can run in parallel after `W01` is closed.
`W05` depends on the earlier waves because it turns advisory baselines into
ratchets.

## Verification

The plan is complete when every Step row is closed, scoped execution records exist
for each Step, `just tooling-doctor` still passes, structural gates pass, focused
type checks for touched packages pass, and `just quality-audit` has an updated
baseline document explaining remaining advisory findings.
