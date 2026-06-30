---
tags:
  - '#plan'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-06-30'
tier: L3
related:
  - '[[2026-06-30-agent-harness-adr]]'
  - '[[2026-06-30-agent-harness-research]]'
---

# `agent-harness` plan

## Wave `W01` - Layer 0: capability manifest exposure

Expose the existing operator-surface contract and the JSON schema registry as a read-only 'aeat app contract --format json' manifest. This is the enabling Layer 0: the agent's capability catalogue and the source the MCP server consumes for tools/list. Every later Wave depends on it. Backed by the agent-harness ADR and research.

### Phase `W01.P01` - manifest projection and command

Project the operator-surface contract and schema registry into a registered manifest payload and mount the read-only command that emits it.

- [x] `W01.P01.S01` - Define the operator-surface manifest result payload schema; `src/aeat/entrypoints/cli/_app_contract_payloads.py`.
- [x] `W01.P01.S02` - Project the operator-surface contract and schema registry into the manifest payload; `src/aeat/application/operator_surface/_manifest.py`.
- [x] `W01.P01.S03` - Mount the read-only contract command emitting the manifest envelope; `src/aeat/entrypoints/cli/_app_contract.py`.
- [x] `W01.P01.S04` - Wire the contract command into the app group and register its schema; `src/aeat/entrypoints/cli/__init__.py`.
- [x] `W01.P01.S05` - Add localized help leaves for the contract command via the locales CLI; `src/aeat/locales/en.yml`.
- [x] `W01.P01.S55` - Complete the OperatorSurfaceContract to cover every mounted family and sub-verb, and add a live-Typer-tree drift gate so the agent manifest source can never silently drift; `src/aeat/application/operator_surface/_contract.py`.

### Phase `W01.P02` - manifest conformance and reference

Bind the new command to the conformance gates and regenerate the documentation reference surfaces.

- [x] `W01.P02.S06` - Assert the contract command is registered in the schema conformance gate; `src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`.
- [x] `W01.P02.S07` - Add a behaviour test that the manifest covers every command family, mutability, and the lifecycle; `src/aeat/entrypoints/cli/tests/test_app_contract.py`.
- [x] `W01.P02.S08` - Regenerate the API reference stubs for the new modules; `docs/api`.
- [x] `W01.P02.S09` - Assert the contract verb in the documented-command conformance gate; `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`.

## Wave `W02` - Layer 1: operator rules, harness home, and the agent extra

Establish the operator harness home as reviewed package data under the agent data tree, declare the aeat[agent] optional extra, and author the Layer 1 operator operating rules. Depends on W01 because the rules reference the manifest. Backed by the agent-harness ADR.

### Phase `W02.P03` - harness home and packaging extra

Create the shipped harness data tree, declare the aeat[agent] extra, and prove the data ships in the wheel.

- [x] `W02.P03.S10` - Create the shipped operator-harness data tree skeleton; `src/aeat/_data/agent/`.
- [x] `W02.P03.S11` - Declare the aeat[agent] optional extra carrying no weights or credentials; `pyproject.toml`.
- [x] `W02.P03.S12` - Add the importlib.resources accessor for the harness data tree; `src/aeat/agent/__init__.py`.
- [x] `W02.P03.S13` - Add a packaging-smoke probe asserting harness data ships in the wheel; `Justfile`.

### Phase `W02.P04` - operator operating rules authoring

Author the Layer 1 operator rules and the drift gate that keeps every CLI verb and JSON field they name resolvable at HEAD.

- [x] `W02.P04.S14` - Author the never-compute, provenance-relay operating rule; `src/aeat/_data/agent/rules/operator-operating-rules.md`.
- [x] `W02.P04.S15` - Author the safety and filing-handoff operating rule; `src/aeat/_data/agent/rules/operator-safety-handoff.md`.
- [x] `W02.P04.S16` - Author the envelope-and-exit-code reading rule; `src/aeat/_data/agent/rules/operator-envelope-reading.md`.
- [x] `W02.P04.S17` - Author the revision-by-law and under-declaration-suspicion rule; `src/aeat/_data/agent/rules/operator-grounding.md`.
- [x] `W02.P04.S18` - Add the rule-surface drift gate over named CLI verbs and JSON fields; `src/aeat/_data/agent/tests/test_rule_surface_conformance.py`.

## Wave `W03` - Layer 2/3 vertical slice: one modelo workflow and a golden eval

Prove the harness end-to-end on one modelo workflow (130) over raw 'aeat --format json': a coordinator plus minimal preparer and verifier personas, one workflow skill, and an AEAT-worked-example golden eval. The cheap, falsifiable first increment. Depends on W01 and W02.

### Phase `W03.P05` - minimal persona slice

Author the coordinator and the two lifecycle personas the one-modelo slice needs, each with role-scoped tool access.

- [x] `W03.P05.S19` - Author the coordinator persona; `src/aeat/_data/agent/personas/coordinator.md`.
- [x] `W03.P05.S20` - Author the modelo-preparer persona with role-scoped tool access; `src/aeat/_data/agent/personas/modelo-preparer.md`.
- [x] `W03.P05.S21` - Author the verifier persona running in isolated context; `src/aeat/_data/agent/personas/verifier.md`.

### Phase `W03.P06` - modelo-130 workflow skill

Author the modelo-130 preparation skill as an executable playbook with progressive-disclosure reference material.

- [x] `W03.P06.S22` - Author the modelo-130 preparation skill playbook; `src/aeat/_data/agent/skills/preparar-modelo-130/SKILL.md`.
- [x] `W03.P06.S23` - Author the modelo-130 progressive-disclosure casilla reference; `src/aeat/_data/agent/skills/preparar-modelo-130/reference/casillas.md`.

### Phase `W03.P07` - golden eval substrate for the slice

Stand up the operator golden-task runner and the modelo-130 AEAT-worked-example scenario that proves the slice.

- [x] `W03.P07.S24` - Define the golden-task scenario schema for trajectory, casilla values, and provenance; `src/aeat/agent/eval/_models.py`.
- [x] `W03.P07.S25` - Author the modelo-130 golden scenario from an AEAT worked example; `src/aeat/agent/eval/scenarios/modelo_130.toml`.
- [x] `W03.P07.S26` - Implement the golden-task runner asserting trajectory, value, and provenance; `src/aeat/agent/eval/_runner.py`.
- [x] `W03.P07.S27` - Wire the modelo-130 golden eval into the test surface; `src/aeat/agent/eval/tests/test_modelo_130_golden.py`.

## Wave `W04` - MCP server, HITL tiers, and faithfulness hooks

Build the validated end-state tool exposure: an MCP server reached by a sibling 'aeat-mcp' entry point, sourcing schemas and mutability annotations from the W01 manifest, with PreToolUse human-in-the-loop confirmation tiers and a PostToolUse faithfulness hook. Depends on W01 through W03.

### Phase `W04.P08` - MCP server core

Stand up the MCP server entrypoint, generate tools/list from the manifest, dispatch CLI leaves as typed tools, and project mutability to annotations.

- [ ] `W04.P08.S28` - Create the MCP server entrypoint scaffolding; `src/aeat/entrypoints/mcp/__init__.py`.
- [ ] `W04.P08.S29` - Generate the tools list from the Layer 0 manifest; `src/aeat/entrypoints/mcp/_tools.py`.
- [ ] `W04.P08.S30` - Dispatch CLI leaves as typed MCP tool handlers with input, output, and error shapes; `src/aeat/entrypoints/mcp/_dispatch.py`.
- [ ] `W04.P08.S31` - Project operator mutability into tool annotations; `src/aeat/entrypoints/mcp/_annotations.py`.
- [ ] `W04.P08.S32` - Declare the aeat-mcp console script; `pyproject.toml`.

### Phase `W04.P09` - HITL and faithfulness hooks

Enforce the confirmation tiers and the faithfulness check, with the live-write tool never exposed.

- [ ] `W04.P09.S33` - Implement the PreToolUse confirmation policy across the mutability tiers; `src/aeat/entrypoints/mcp/_hitl.py`.
- [ ] `W04.P09.S34` - Implement the PostToolUse faithfulness hook with advisory flag and handoff block; `src/aeat/entrypoints/mcp/_faithfulness.py`.
- [ ] `W04.P09.S35` - Add the never-expose-live-write enforcement test; `src/aeat/entrypoints/mcp/tests/test_live_write_unexposed.py`.
- [ ] `W04.P09.S36` - Add the HITL tier behaviour test; `src/aeat/entrypoints/mcp/tests/test_hitl_tiers.py`.
- [ ] `W04.P09.S37` - Add the faithfulness advisory-versus-block behaviour test; `src/aeat/entrypoints/mcp/tests/test_faithfulness.py`.

### Phase `W04.P10` - MCP packaging and determinism

Gate the MCP runtime behind the agent extra and add determinism-replay capture for tool call/response pairs.

- [ ] `W04.P10.S38` - Add the MCP runtime dependency to the aeat[agent] extra; `pyproject.toml`.
- [ ] `W04.P10.S39` - Implement determinism-replay capture and replay for tool call and response pairs; `src/aeat/agent/eval/_replay.py`.
- [ ] `W04.P10.S40` - Add a packaging-smoke probe that aeat-mcp refuses from a bare core install with an install hint; `Justfile`.

## Wave `W05` - Full persona and skill matrix, workspace materialiser, and standing eval gate

Complete the persona roster and the canonical workflow skill matrix, ship the operator-workspace materialiser command, and bind the golden plus determinism-replay eval as a standing harness-change gate. Depends on W01 through W04.

### Phase `W05.P11` - remaining personas

Author the onboarding, ledger-groomer, classifier, and reconciler personas.

- [ ] `W05.P11.S41` - Author the onboarding persona; `src/aeat/_data/agent/personas/onboarding.md`.
- [ ] `W05.P11.S42` - Author the ledger-groomer persona; `src/aeat/_data/agent/personas/ledger-groomer.md`.
- [ ] `W05.P11.S43` - Author the classifier persona; `src/aeat/_data/agent/personas/classifier.md`.
- [ ] `W05.P11.S44` - Author the reconciler persona; `src/aeat/_data/agent/personas/reconciler.md`.

### Phase `W05.P12` - canonical workflow skills

Author the remaining canonical workflow skills across the onboarding-to-reconcile happy path.

- [ ] `W05.P12.S45` - Author the taxpayer-onboarding skill; `src/aeat/_data/agent/skills/alta-contribuyente/SKILL.md`.
- [ ] `W05.P12.S46` - Author the ledger-building skill; `src/aeat/_data/agent/skills/llevar-libro/SKILL.md`.
- [ ] `W05.P12.S47` - Author the classify-and-apportion skill; `src/aeat/_data/agent/skills/clasificar/SKILL.md`.
- [ ] `W05.P12.S48` - Author the export-and-handoff skill; `src/aeat/_data/agent/skills/exportar-declaracion/SKILL.md`.
- [ ] `W05.P12.S49` - Author the reconcile skill; `src/aeat/_data/agent/skills/reconciliar/SKILL.md`.

### Phase `W05.P13` - workspace materialiser and standing gate

Ship the operator-workspace materialiser command and bind the golden plus replay eval as a standing harness-change gate.

- [ ] `W05.P13.S50` - Mount the operator-workspace materialiser command under app; `src/aeat/entrypoints/cli/_app_agent_workspace.py`.
- [ ] `W05.P13.S51` - Register the workspace materialiser schema in the conformance gate; `src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`.
- [ ] `W05.P13.S52` - Expand the golden scenarios to cover the full lifecycle for 303 and 130; `src/aeat/agent/eval/scenarios/`.
- [ ] `W05.P13.S53` - Bind the golden and replay eval as a standing harness-change CI gate; `.github/workflows/agent-harness-eval.yml`.
- [ ] `W05.P13.S54` - Codify the operator co-commit drift discipline as a project rule; `.vaultspec/rules/rules/`.

## Description

This plan implements the agent-harness ADR: the operating layer that lets an LLM
tax-advisor agent drive the deterministic `aeat` CLI to do real tax work without
ever computing a tax value itself. The CLI is the backbone (it computes the tax);
the harness is the operating layer (the agent orchestrates, extracts, classifies,
narrates, and hands off). The build follows the ADR's recommended sequence and the
research's layered shape.

Wave `W01` lands the enabling Layer 0: a read-only `aeat app contract --format json`
command that emits the existing `OperatorSurfaceContract` plus the schema-registry
payload schemas as the agent's capability catalogue. It mounts under `app` (the CLI
root surface is pinned to `config` and `app`; no third root is permitted) and is the
source the MCP server later consumes for its tool list. Wave `W02` establishes the
operator harness home as reviewed package data under the agent data tree, declares the
`aeat[agent]` optional extra under the accepted self-contained-wheel packaging model,
and authors the Layer 1 operator operating rules (never compute or invent a value;
relay CLI JSON verbatim with provenance; never assert a local export is official; never
submit live; read `status` not stdout/stderr; treat exit `1` as a verdict; treat
positive-income with zero tax as suspect). Wave `W03` proves the harness end-to-end on
one modelo workflow (130) over raw `aeat --format json` with a minimal persona slice, a
workflow skill, and an AEAT-worked-example golden eval, keeping the first increment
cheap and falsifiable. Wave `W04` builds the validated end-state tool exposure: an MCP
server reached by a sibling `aeat-mcp` entry point that sources schemas and mutability
annotations from the Layer 0 manifest, with PreToolUse human-in-the-loop confirmation
tiers and a PostToolUse faithfulness hook (advisory by default, blocking at the
irreversible filing handoff). Wave `W05` completes the persona roster and the canonical
workflow skill matrix, ships the operator-workspace materialiser command, and binds the
golden plus determinism-replay eval as a standing harness-change gate.

The authorizing chain (the agent-harness ADR, its research, and the aligned accepted
operator-surface ADR) is carried once in the plan's `related:` frontmatter and inherited
by every Step.

## Steps

## Parallelization

The five Waves are hard-sequenced and must land in order: `W01` exposes the manifest
that `W02` rules reference, that `W03` proves over the raw CLI, that `W04` consumes for
the MCP tool list, that `W05` completes. Do not start a Wave before its predecessor is
green.

Within Waves, Phases parallelize where they share no hard dependency. In `W01`, `P01`
(projection and command) must precede `P02` (conformance and reference) because the gates
test the command `P01` mounts. In `W02`, `P03` (harness home and extra) must precede `P04`
(rules authoring) because the rules are authored into the data tree `P03` creates. In
`W03`, `P05` (personas) and `P06` (skill) may proceed in parallel once `W02` lands, but
`P07` (golden eval) must follow both because it exercises them. In `W04`, `P08` (server
core) precedes `P09` (hooks) and `P10` (packaging/determinism); `P09` and `P10` may then
run in parallel. In `W05`, `P11` (personas) and `P12` (skills) parallelize, and `P13`
(workspace and standing gate) follows both.

Within any Phase, the authoring Steps that touch distinct files (separate rule, persona,
or skill documents) may be authored in parallel; Steps that share a file (the repeated
`pyproject.toml` and conformance-gate touches) are serialized on that file and must be
landed with the apply-cached gated drive if a peer holds uncommitted work there.

## Verification

The plan is complete when every Step is closed (`- [x]`) and each Wave's success
criterion below is met by a verifiable check, not an assertion.

`W01` is verified when `aeat app contract --format json` emits a `SchemaEnvelope` whose
result covers every mounted command family, its `OperatorMutability`, and the
`CALCULATE -> VERIFY -> FILE` lifecycle, and when the schema-conformance and
documented-command gates pass with the new command registered (no third CLI root
introduced). `W02` is verified when a bare `pip install aeat` still runs MCP-free, the
`aeat[agent]` extra installs the harness data, the packaging-smoke probe finds the
harness data in the wheel, and the rule-surface drift gate confirms every CLI verb and
JSON field named in an operator rule resolves at HEAD. `W03` is verified when the
modelo-130 golden eval passes: the expected tool trajectory, the expected casilla values
sourced from the AEAT worked example (never hand-computed from the registry formula under
test), and provenance present on every emitted value. `W04` is verified when the MCP
`tools/list` is generated from the W01 manifest, no live-write tool is exposed (enforced
by test), the HITL tiers behave per the mutability mapping, the faithfulness hook flags
advisory cases and blocks the handoff path, and `aeat-mcp` refuses from a bare core
install with an install hint. `W05` is verified when the full persona and skill matrix is
present, the operator-workspace materialiser command conforms to the schema gate, the
golden scenarios cover the 303 and 130 lifecycle, and the golden plus replay eval runs
green as a standing harness-change gate.

Two project-wide disciplines bind every Step: golden oracles come only from
AEAT-authoritative worked examples (no tautological calculation tests), and every harness
rule or skill that names a CLI verb or JSON field is co-committed with the surface it
couples to (the drift gate enforces this). Each completed Step carries a matching
execution record; a Step is not marked closed on code inspection alone.
