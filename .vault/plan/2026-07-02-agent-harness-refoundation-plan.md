---
tags:
  - '#plan'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-08-01'
body_hash: 'sha256:ab7d9ba04f6262b1bd76f5b57a6eaf7bd7e87fc13b687f5277768bbedb2d0871'
tier: L3
related:
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
  - '[[2026-07-02-agent-harness-refoundation-research]]'
---
# `agent-harness-refoundation` plan

## Wave `W01` - Console tool architecture

Replace the flat args-bag tool surface with per-verb input schemas, manifest-derived domain toolsets (renta, iva, ledger, censo, modelo-lifecycle), a search-plus-execute meta-tool fallback, and prompts/resources capability registration. This is the foundation every later Wave extends: the delivery channels of W02, the gates of W03, and the live verification of W04 all build on the server this Wave reshapes. Backed by ADR decision R2.

### Phase `W01.P01` - Per-verb input schemas and domain toolsets

Replace the shared args bag with per-verb input schemas and group the manifest-derived tools into domain toolsets with complete annotation coverage.

- [x] `W01.P01.S01` - Derive a per-verb input schema from the CLI command registry click parameters, replacing the shared args bag; `src/aeat/entrypoints/mcp/_input_schema.py`.
- [x] `W01.P01.S02` - Consume per-verb input schemas in build_tool_descriptors and retire the _ARGS_INPUT_SCHEMA bag; `src/aeat/entrypoints/mcp/_tools.py`.
- [x] `W01.P01.S03` - Add a domain-toolset grouping derived from the operator-surface manifest for renta, iva, ledger, censo, and modelo-lifecycle; `src/aeat/entrypoints/mcp/_toolsets.py`.
- [x] `W01.P01.S04` - Assert readOnlyHint and destructiveHint annotation coverage on every descriptor and close any gap; `src/aeat/entrypoints/mcp/_annotations.py`.
- [x] `W01.P01.S05` - Extend the tool-descriptor tests for per-verb schemas, toolsets, and annotation coverage; `src/aeat/entrypoints/mcp/tests/test_tools_and_dispatch.py`.

### Phase `W01.P02` - Meta-tool fallback and capability registration

Add the search-plus-execute long-tail fallback and register the prompts and resources server capabilities the later delivery channels need.

- [x] `W01.P02.S06` - Add the search-plus-execute meta-tool pair for verbs outside the curated toolsets; `src/aeat/entrypoints/mcp/_meta_tools.py`.
- [x] `W01.P02.S07` - Register the prompts and resources server capabilities on the stdio server; `src/aeat/entrypoints/mcp/_server.py`.
- [x] `W01.P02.S08` - Add tests for the meta-tool fallback and capability registration; `src/aeat/entrypoints/mcp/tests/test_meta_tools.py`.

## Wave `W02` - Operating layer through the protocol

Deliver the operator rules, personas, and skills to any MCP client through the protocol: a harness.load floor tool, aeat skill/rule/persona resource templates, and guided-workflow prompts that embed the matching skill plus grounding, with the workspace materialiser demoted to an optional Claude-native mirror. Depends on W01 capability registration. Backed by ADR decision R4.

### Phase `W02.P03` - Floor tool and resource templates

Deliver the operating layer as a harness.load floor tool and aeat skill/rule/persona resource templates.

- [x] `W02.P03.S09` - Add the harness.load floor tool returning operator rules and the active persona via aeat.agent; `src/aeat/entrypoints/mcp/_harness_tools.py`.
- [x] `W02.P03.S10` - Add aeat skill, rule, and persona resource templates with a read handler; `src/aeat/entrypoints/mcp/_resources.py`.
- [x] `W02.P03.S11` - Wire the resource list and read handlers into the server; `src/aeat/entrypoints/mcp/_server.py`.
- [x] `W02.P03.S12` - Add tests for the floor tool and resource templates; `src/aeat/entrypoints/mcp/tests/test_harness_delivery.py`.

### Phase `W02.P04` - Guided prompts and Claude-native mirror

Add guided-workflow prompts embedding skill plus grounding and demote the workspace materialiser to an optional Claude-native mirror.

- [x] `W02.P04.S13` - Add guided-workflow prompts that embed the matching skill plus its grounding excerpt; `src/aeat/entrypoints/mcp/_prompts.py`.
- [x] `W02.P04.S14` - Wire the prompt list and get handlers into the server; `src/aeat/entrypoints/mcp/_server.py`.
- [x] `W02.P04.S15` - Demote the workspace materialiser to an optional Claude-native .claude/skills mirror layout; `src/aeat/agent/_workspace.py`.
- [x] `W02.P04.S16` - Update the app-agent workspace CLI to emit the Claude-native mirror; `src/aeat/entrypoints/cli/_app_agent_workspace.py`.
- [x] `W02.P04.S17` - Add tests for the guided-workflow prompts; `src/aeat/entrypoints/mcp/tests/test_prompts.py`.
- [x] `W02.P04.S18` - Update the workspace materialiser tests for the mirror layout; `src/aeat/agent/tests/test_workspace.py`.

## Wave `W03` - Gates and telemetry

Turn the two nominal safety gates real: an elicitation-backed CONFIRM tier with the decided capability-degradation matrix, and the faithfulness check wired into the serving path as an advisory notice that hard-blocks at the export and record-marker boundary. Add per-verb handoff deny rules over the family-granular persona scope and persist local session telemetry. Depends on W01. Backed by ADR decision R6.

### Phase `W03.P05` - Elicitation-backed CONFIRM

Enforce the CONFIRM tier through MCP elicitation with the decided capability-degradation matrix.

- [x] `W03.P05.S19` - Add the elicitation module with the capability-degradation matrix over accept, decline, and cancel, a destructiveHint fallback, and a default handoff refusal when elicitation is absent; `src/aeat/entrypoints/mcp/_elicitation.py`.
- [x] `W03.P05.S20` - Enforce the CONFIRM tier through elicitation in the call-tool path; `src/aeat/entrypoints/mcp/_server.py`.
- [x] `W03.P05.S21` - Add tests for elicitation enforcement and the degradation matrix; `src/aeat/entrypoints/mcp/tests/test_elicitation.py`.

### Phase `W03.P06` - Faithfulness serving path, handoff deny, and telemetry

Wire faithfulness into the serving path with a handoff hard block, add per-verb handoff deny rules, and persist local session telemetry.

- [x] `W03.P06.S22` - Extend the faithfulness check with the serving-path advisory-plus-handoff-block integration surface; `src/aeat/entrypoints/mcp/_faithfulness.py`.
- [x] `W03.P06.S23` - Wire faithfulness into the serving path as an advisory notice with a hard block at the export and record-marker boundary; `src/aeat/entrypoints/mcp/_server.py`.
- [x] `W03.P06.S24` - Add per-verb handoff deny rules over the family-granular persona scope; `src/aeat/entrypoints/mcp/_persona_scope.py`.
- [x] `W03.P06.S25` - Add local session telemetry recording per-call trajectory records with session ids; `src/aeat/entrypoints/mcp/_telemetry.py`.
- [x] `W03.P06.S26` - Add tests for the faithfulness serving path, the handoff deny rules, and telemetry; `src/aeat/entrypoints/mcp/tests/test_serving_gates.py`.

## Wave `W04` - Live verification

Prove the console functions by driving it with live subagent personas. A real-client handshake test is the floor; the live persona harness starts the real server, drives a real client session, captures the trajectory, and scores observed calls against golden scenarios plus faithfulness and confirmation, with hard zero-live-submit and zero-handoff-faithfulness invariants, a flywheel promoting live failures to golden scenarios, and a measurement report. Depends on W01, W02, and W03. Backed by ADR decision R7.

### Phase `W04.P07` - Handshake conformance floor

Prove a real MCP client can initialize, list tools, and round-trip a call over stdio.

- [x] `W04.P07.S27` - Add a real-client handshake conformance test exercising initialize, tools-list, and a call round-trip over stdio; `src/aeat/entrypoints/mcp/tests/test_client_handshake.py`.

### Phase `W04.P08` - Live subagent-persona harness

Drive the real console with live subagent personas, score observed calls, enforce the hard invariants, and feed the flywheel and measurement report.

- [x] `W04.P08.S28` - Build the live subagent-persona harness substrate that starts the real server, drives a real client session, and captures the trajectory; `src/aeat/agent/eval/_live_harness.py`.
- [x] `W04.P08.S29` - Score observed calls against golden scenarios plus faithfulness and confirmation with the zero-live-submit and zero-handoff-faithfulness invariants; `src/aeat/agent/eval/_live_scoring.py`.
- [x] `W04.P08.S30` - Extend the golden-scenario models for live-persona trajectory capture and scoring; `src/aeat/agent/eval/_models.py`.
- [x] `W04.P08.S31` - Add the flywheel that promotes live failures into new golden scenarios; `src/aeat/agent/eval/_flywheel.py`.
- [x] `W04.P08.S32` - Add the local measurement report artefact; `src/aeat/agent/eval/_report.py`.
- [x] `W04.P08.S33` - Add the live-harness test; `src/aeat/agent/eval/tests/test_live_harness.py`.

## Wave `W05` - Situation-keyed skills

Lift each existing skill selection predicate from prose into a structured applies_when frontmatter field with loader validation and a coverage gate, then author the six life-situation skills led by regularizar-atrasos over the already-built backlog and recargo surface, each with a golden scenario. Depends on W01 schema discipline; the applies_when field is consumed by the W02 prompts and the W04 eval. Backed by ADR decision R5.

### Phase `W05.P09` - applies_when schema and gate

Define the structured applies_when frontmatter schema, validate it at skill load, and gate coverage.

- [x] `W05.P09.S34` - Define the structured applies_when frontmatter schema and its parser over TaxpayerProfile facts and lifecycle state; `src/aeat/agent/_skill_metadata.py`.
- [x] `W05.P09.S35` - Validate the applies_when field at skill load; `src/aeat/agent/__init__.py`.
- [x] `W05.P09.S36` - Add the applies_when coverage gate asserting every skill declares a structured predicate; `src/aeat/agent/tests/test_skill_applies_when.py`.

### Phase `W05.P10` - Lift selection predicates into existing skills

Move each existing skill prose selection predicate into the structured applies_when frontmatter field.

- [x] `W05.P10.S37` - Lift the alta-contribuyente selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/alta-contribuyente/SKILL.md`.
- [x] `W05.P10.S38` - Lift the arrendador selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/arrendador/SKILL.md`.
- [x] `W05.P10.S39` - Lift the autonomo-estimacion-directa selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/autonomo-estimacion-directa/SKILL.md`.
- [x] `W05.P10.S40` - Lift the autonomo-modulos selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/autonomo-modulos/SKILL.md`.
- [x] `W05.P10.S41` - Lift the clasificar selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/clasificar/SKILL.md`.
- [x] `W05.P10.S42` - Lift the exportar-declaracion selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/exportar-declaracion/SKILL.md`.
- [x] `W05.P10.S43` - Lift the intra-community-operator selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/intra-community-operator/SKILL.md`.
- [x] `W05.P10.S44` - Lift the llevar-libro selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/llevar-libro/SKILL.md`.
- [x] `W05.P10.S45` - Lift the preparar-modelo-100 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-100/SKILL.md`.
- [x] `W05.P10.S46` - Lift the preparar-modelo-111 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-111/SKILL.md`.
- [x] `W05.P10.S47` - Lift the preparar-modelo-115 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-115/SKILL.md`.
- [x] `W05.P10.S48` - Lift the preparar-modelo-130 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-130/SKILL.md`.
- [x] `W05.P10.S49` - Lift the preparar-modelo-131 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-131/SKILL.md`.
- [x] `W05.P10.S50` - Lift the preparar-modelo-180 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-180/SKILL.md`.
- [x] `W05.P10.S51` - Lift the preparar-modelo-190 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-190/SKILL.md`.
- [x] `W05.P10.S52` - Lift the preparar-modelo-193 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-193/SKILL.md`.
- [x] `W05.P10.S53` - Lift the preparar-modelo-200 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-200/SKILL.md`.
- [x] `W05.P10.S54` - Lift the preparar-modelo-202 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-202/SKILL.md`.
- [x] `W05.P10.S55` - Lift the preparar-modelo-303 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-303/SKILL.md`.
- [x] `W05.P10.S56` - Lift the preparar-modelo-309 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-309/SKILL.md`.
- [x] `W05.P10.S57` - Lift the preparar-modelo-322 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-322/SKILL.md`.
- [x] `W05.P10.S58` - Lift the preparar-modelo-349 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-349/SKILL.md`.
- [x] `W05.P10.S59` - Lift the preparar-modelo-353 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-353/SKILL.md`.
- [x] `W05.P10.S60` - Lift the preparar-modelo-369 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-369/SKILL.md`.
- [x] `W05.P10.S61` - Lift the preparar-modelo-390 selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/preparar-modelo-390/SKILL.md`.
- [x] `W05.P10.S62` - Lift the pyme-sociedad selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/pyme-sociedad/SKILL.md`.
- [x] `W05.P10.S63` - Lift the reconciliar selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/reconciliar/SKILL.md`.
- [x] `W05.P10.S64` - Lift the retenedor-empleador selection predicate from prose into the applies_when frontmatter field; `src/aeat/_data/agent/skills/retenedor-empleador/SKILL.md`.

### Phase `W05.P11` - Life-situation skills

Author the six WHEN-layer skills, regularizar-atrasos first, each with a golden scenario.

- [x] `W05.P11.S65` - Author the regularizar-atrasos skill sequencing the overview backlog past-due and recargo extemporaneo surface; `src/aeat/_data/agent/skills/regularizar-atrasos/SKILL.md`.
- [x] `W05.P11.S66` - Add the regularizar-atrasos golden scenario; `src/aeat/agent/eval/scenarios/regularizar_atrasos.toml`.
- [x] `W05.P11.S67` - Author the cierre-trimestre skill sequencing the quarter-boundary agenda obligations; `src/aeat/_data/agent/skills/cierre-trimestre/SKILL.md`.
- [x] `W05.P11.S68` - Add the cierre-trimestre golden scenario; `src/aeat/agent/eval/scenarios/cierre_trimestre.toml`.
- [x] `W05.P11.S69` - Author the resumen-anual skill sequencing the annual-window obligations; `src/aeat/_data/agent/skills/resumen-anual/SKILL.md`.
- [x] `W05.P11.S70` - Add the resumen-anual golden scenario; `src/aeat/agent/eval/scenarios/resumen_anual.toml`.
- [x] `W05.P11.S71` - Author the rectificar-declaracion skill driving work amend and the complementaria and sustitutiva path; `src/aeat/_data/agent/skills/rectificar-declaracion/SKILL.md`.
- [x] `W05.P11.S72` - Add the rectificar-declaracion golden scenario; `src/aeat/agent/eval/scenarios/rectificar_declaracion.toml`.
- [x] `W05.P11.S73` - Author the inicio-actividad skill over the activity-start-date and 036 alta path; `src/aeat/_data/agent/skills/inicio-actividad/SKILL.md`.
- [x] `W05.P11.S74` - Add the inicio-actividad golden scenario; `src/aeat/agent/eval/scenarios/inicio_actividad.toml`.
- [x] `W05.P11.S75` - Author the cese-actividad skill over the activity-end-date and 036 baja path; `src/aeat/_data/agent/skills/cese-actividad/SKILL.md`.
- [x] `W05.P11.S76` - Add the cese-actividad golden scenario; `src/aeat/agent/eval/scenarios/cese_actividad.toml`.

## Wave `W06` - Grounding and packaging

Behind a blocking licence gate, build the on-host hybrid corpus index from the bundled extracted triples, expose corpus and terminology search tools plus aeat corpus resources that resolve citations to verbatim text, and package the console as a signed mcpb Desktop Extension behind the agent extra. Depends on the W01 tool surface; the licence gate blocks the rest of the Wave. Backed by ADR decisions R3 and R8.

Annotation added 2026-08-01: the SEMANTIC half of this Wave is RETIRED and no longer describes the shipped product. The accepted `2026-07-31-semantic-search-precompile-boundary-adr` amends ruling R3, and its execution deleted the runtime query embedder, the corpus-vector build, the cosine and RRF fusion, and the capability-gated `search` extra with its model2vec, huggingface-hub, and numpy pins. The Step rows below are left exactly as executed, because they are a true record of what was built at the time; they are NOT a description of current architecture. What survives from this Wave is the lexical half and the structured half: the FTS5 index with the Spanish stemmed column (`snowballstemmer` promoted to a core dependency), the exact-citation lookup returning verbatim authoritative text, the terminology lookup, and the corpus, resource, and terminology console tools. The shipped product now loads no embedding model, computes no vectors, and reaches no model host for retrieval. Semantic search is a dev-side precompile step whose laundered output ships with the documentation.

### Phase `W06.P12` - Build-time lexical index and precomputed vectors

Build the FTS5 lexical index, the structured citation lookup over registry citation data, and the corpus embeddings precomputed at build time and shipped as data, and confirm the query-model footprint before the download UX lands. The R3 licence gate is resolved in the research doc; these are concrete build steps against the decided stack, not a research gate.

- [x] `W06.P12.S77` - Build the FTS5 lexical index with unicode61 remove_diacritics 2 plus a snowballstemmer Spanish stemmed column from the bundled extracted corpus triples; `src/aeat/application/corpus_search/_lexical_index.py`.
- [x] `W06.P12.S78` - Build the structured citation lookup keyed on citation id over the registry typed legal_refs, corpus_ref, and BOE permalink data; `src/aeat/application/corpus_search/_citation_lookup.py`.
- [x] `W06.P12.S79` - Precompute the corpus embeddings at build time with model2vec potion-multilingual-128M and ship the numpy matrix as bundled data; `src/aeat/application/corpus_search/_embed_build.py`.
- [x] `W06.P12.S87` - Confirm the potion-multilingual-128M packaged footprint and that the wheel ships the precomputed vectors but no model weights, onnxruntime, or caches; `src/aeat/application/corpus_search/tests/test_search_shippability.py`.

### Phase `W06.P13` - Runtime hybrid retrieval and console grounding tools

Add the runtime query embedder behind the capability-gated extra, brute-force numpy cosine plus RRF fusion with a lexical-only degraded mode, and the corpus, citation-resource, and terminology console tools.

- [x] `W06.P13.S80` - Add the runtime query embedder with model2vec potion-multilingual-128M behind the capability-gated extra with a pinned revision, app-controlled cache dir, and install hint; `src/aeat/application/corpus_search/_query_embed.py`.
- [x] `W06.P13.S88` - Add brute-force numpy cosine vector search with RRF k=60 fusion in plain Python and a lexical-only FTS5-plus-citation degraded mode; `src/aeat/application/corpus_search/_retrieval.py`.
- [x] `W06.P13.S81` - Expose the corpus search MCP tool; `src/aeat/entrypoints/mcp/_corpus_tools.py`.
- [x] `W06.P13.S82` - Add aeat corpus ref resources resolving citations to verbatim authoritative text; `src/aeat/entrypoints/mcp/_resources.py`.
- [x] `W06.P13.S83` - Expose the terminology handbook search tool; `src/aeat/entrypoints/mcp/_terminology_tools.py`.
- [x] `W06.P13.S84` - Add retrieval, RRF fusion, and lexical-only degraded-mode tests; `src/aeat/application/corpus_search/tests/test_retrieval.py`.

### Phase `W06.P14` - Packaging, search extra, and attribution

Pin the search-stack dependencies in the capability-gated extra, record the third-party attribution, and assemble and sign the mcpb Desktop Extension behind the agent extra.

- [x] `W06.P14.S89` - Pin the search-stack dependencies snowballstemmer, model2vec, and numpy in the capability-gated search extra with a lexical-only degraded default; `pyproject.toml`.
- [x] `W06.P14.S90` - Author the third-party notices attribution for the potion-multilingual-128M lineage distilled from BGE-m3 on the C4 ODC-BY corpus; `src/aeat/application/corpus_search/THIRD_PARTY_NOTICES.md`.
- [x] `W06.P14.S85` - Author the mcpb Desktop Extension manifest; `packaging/mcpb/manifest.json`.
- [x] `W06.P14.S86` - Add the mcpb build-and-sign script behind the agent extra; `packaging/mcpb/build.py`.

## Description

This plan executes the `2026-07-02-agent-harness-refoundation-adr` (decisions R1 through R9), grounded in the `2026-07-02-agent-harness-refoundation-research` inventory. The corrected universe definition frames the work: the `aeat` CLI is a black-box, deterministic tool universe, and the harness is the framework of rules, personas, and skills for operating safely within it, served to any language model through one MCP operating console. The refoundation turns the console from a verb-wrapper shell plus a static content bundle into an operable, measured operating surface. The CLI itself needs almost nothing new (R1 / the ADR Implementation note); the load-bearing verbs already exist, so the work concentrates in the console server, the operating-layer delivery channels, the safety gates, the situation-skill layer, the grounding surface, and a live model-in-the-loop verification regime.

The work is sequenced framework-first, then verify and measure, then extend. W01 reshapes the tool surface (per-verb schemas, domain toolsets, meta-tool fallback, capability registration) that every later Wave builds on. W02 ships the operating layer through the protocol. W03 makes the two nominal gates real. W04 verifies the whole console by driving it with live subagent personas, which is the operator's stated goal for this campaign. W05 re-keys the skills to the user situation. W06 adds the grounding surface behind a blocking licence gate and packages the console for distribution. Every Step closes only with an execution record per the `plan-closure-requires-exec-records` discipline, and every rule or skill that names a CLI verb co-commits with the surface it cites per `operator-harness-cites-live-cli-surface`.

## Parallelization

Waves are sequenced by default. W01 is the hard prerequisite for W02, W03, and W04: it reshapes the tool descriptors, adds per-verb schemas, and registers the prompts and resources capabilities those later Waves populate. W02 and W03 both extend `_server.py` and may be worked in either order but not concurrently on that file; treat W02 then W03 as the safe sequence. W04 requires W01 through W03 landed, because it drives the fully-gated console end to end. W05 depends only on the W01 schema discipline for its own metadata gate and is otherwise independent of the server Waves; it may proceed in parallel with W02 through W04, but its `applies_when` field is consumed by the W02 guided prompts and the W04 eval, so those two consumers must not assume the field before W05.P09 and W05.P10 land. W06 depends on the W01 tool surface for its search and resource tools.

Within a Wave, Phases that share no file may parallelize. W01.P01 (schemas, toolsets, annotations) and W01.P02 (meta-tools, capability registration) are largely independent except that both touch the descriptor build; land P01 first. In W03, P05 (elicitation) and P06 (faithfulness, deny rules, telemetry) both edit `_server.py`, so sequence P05 then P06. In W05, P09 (the schema and gate) blocks P10 (the per-skill lifts) and P11 (the new skills), because both author `applies_when` the gate validates; P10's 28 per-skill lifts are mutually independent once P09 lands and may be distributed across executors. In W06, P12 (the build-time lexical index and precomputed vectors) is a hard blocker for P13 and P14: the runtime retrieval and console tools consume the precomputed vectors and the FTS5 index, and packaging ships them, so P12 must land before P13 and P14. The R3 licence gate is already resolved in the research doc, so P12 is a concrete build phase, not a research decision. The shared dirty worktree binds every executor: explicit-pathspec commits only, no destructive git, one Step one commit with its execution record.

## Verification

Every Step closes only with a matching execution record under `.vault/exec/2026-07-02-agent-harness-refoundation/` per the `plan-closure-requires-exec-records` discipline; a checked box without an exec record is not a closed Step. All tests are real-behavior only, under domain `tests/` folders, with no mocks, skips, or xfail markers.

Per-Wave runnable gates:

W01 passes when `uv run --no-sync pytest src/aeat/entrypoints/mcp -m "" -q` is green with the extended `test_tools_and_dispatch.py` and new `test_meta_tools.py`, every exposed descriptor carries a non-bag input schema and complete `readOnlyHint`/`destructiveHint` annotations, and the toolsets derive from the live operator-surface manifest.

W02 passes when `uv run --no-sync pytest src/aeat/entrypoints/mcp src/aeat/agent -m "" -q` is green with `test_harness_delivery.py`, `test_prompts.py`, and the updated `test_workspace.py`; the `harness.load` tool returns the shipped operator rules and active persona; and the `aeat://skill|rule|persona/{name}` resources resolve. The rule-surface drift gate `uv run --no-sync pytest src/aeat/agent/tests/test_rule_surface_conformance.py -q` stays green, and any harness document naming a CLI verb co-commits with its surface per `operator-harness-cites-live-cli-surface`.

W03 passes when the new `test_elicitation.py` and `test_serving_gates.py` are green: the CONFIRM tier is enforced through elicitation with the decided degradation matrix, faithfulness is advisory on the read path and hard-blocks at the export and record-marker boundary, per-verb handoff deny rules refuse a handoff verb outside the active persona, and telemetry persists a per-call trajectory record. Never-live-submit remains enforced as no-such-tool-exists.

W04 passes when the real-client handshake test `uv run --no-sync pytest src/aeat/entrypoints/mcp/tests/test_client_handshake.py -q` completes an initialize, tools-list, and call round-trip over stdio, and the live subagent-persona harness (`src/aeat/agent/eval/tests/test_live_harness.py`, invoked with the agent extra installed) runs the golden scenarios end to end with the two hard invariants observed on captured trajectories: zero live-submit attempts and zero faithfulness violations at the handoff boundary. The measurement report artefact is produced and the flywheel promotes at least one live failure into a golden scenario.

W05 passes when the `applies_when` coverage gate `uv run --no-sync pytest src/aeat/agent/tests/test_skill_applies_when.py -q` asserts every one of the 34 skills declares a structured predicate the loader validates, and each of the six new situation skills has a golden scenario the W04 eval can drive.

W06 builds against the decided retrieval stack (research section "Licence gate - the grounding retrieval stack (resolved 2026-07-02)"): FTS5 lexical plus a snowballstemmer Spanish column, a structured citation lookup over the registry data, model2vec potion-multilingual-128M query embeddings against build-time-precomputed corpus vectors, brute-force numpy cosine, and RRF k=60 fusion with a lexical-only degraded mode. It passes when the shippability gate `uv run --no-sync pytest src/aeat/application/corpus_search/tests/test_search_shippability.py -q` confirms the packaged footprint and that the wheel ships the precomputed vectors but no model weights, onnxruntime, or caches; the retrieval and degraded-mode tests pass; the corpus search and terminology tools return grounded results with `aeat://corpus/{ref}` resolving a citation to verbatim text; the third-party attribution for the potion lineage is recorded; and the `.mcpb` bundle builds and signs behind the `aeat[agent]` extra.

The plan is complete when every Step is closed (`- [x]`) with its execution record, the feature-scoped `uv run --no-sync vaultspec-core vault check features --feature agent-harness-refoundation` is clean, and a closing honesty review per `aeat-campaign-close-honesty-review` has run against the campaign summary before completion is declared.
