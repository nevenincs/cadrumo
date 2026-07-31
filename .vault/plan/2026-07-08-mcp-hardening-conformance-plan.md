---
tags:
  - '#plan'
  - '#mcp-protocol-hardening'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:1acef48d0b5554fff5a4468109e671e9c46441c9cb66b418475bdc2e9103d657'
tier: L2
related:
  - '[[2026-07-08-mcp-console-review-audit]]'
  - '[[2026-07-08-mcp-protocol-hardening-adr]]'
  - '[[2026-07-08-mcp-progressive-discovery-adr]]'
  - '[[2026-07-08-mcp-protocol-hardening-research]]'
---

# `mcp-hardening-conformance` plan

### Phase `P01` - Declared per-command risk table

Close the mcp-protocol-hardening H3 conformance gap and the one safety-grade finding: replace the hand-listed leaf-name frozensets with a declared per-command risk table keyed by full command key, gated no-silent-default, so a new mutating verb can no longer auto-approve or escape handoff denial (audit finding risk-classification-hand-listed). Ships FIRST.

- [x] `P01.S01` - Add the CommandRiskDeclaration model and the per-command risk table (destructive, idempotent, handoff, live_write) keyed by full command key, scaffolded from the current frozensets for every command in a mutating family, with a documented human-review pass in the exec record sweeping the known misses (sandbox discard/prune, repair quarantine, config reset, ledger stash, quickfile, modelo.work.file); `src/aeat/application/operator_surface/_risk_table.py`.
- [x] `P01.S02` - Rewire classify_command onto the declared table and delete the destructive, idempotent and handoff leaf frozensets as production inference in the same atomic commit, keeping read_only and idempotent derived from manifest mutability and open_world derived from the app.live and pull facts; `src/aeat/application/operator_surface/_classification.py`.
- [x] `P01.S03` - Move the _hitl re-exports and the persona handoff-deny set onto the declared handoff axis so the confirmation gate and the handoff denial read the table, not the leaf strings; `src/aeat/entrypoints/mcp/_persona_scope.py`.
- [x] `P01.S04` - Add the no-silent-default parity gate: every command in a mutating family carries exactly one risk row, every row references a live command key, and an unclassified mutating verb fails loudly; `src/aeat/application/operator_surface/tests/test_risk_table_parity.py`.
- [x] `P01.S05` - Add the live-write leaf tripwire test (any exposed command whose leaf is submit/present/send must declare live_write true) and the bidirectional write-policy-vs-mutability parity gate against PROFILE_BOUND_WRITE_VERB_PATHS; `src/aeat/application/operator_surface/tests/test_write_policy_mutability_parity.py`.
- [x] `P01.S06` - Update the annotation and classification tests for the table-backed classification and confirm the existing coherence + annotation-coverage gates stay green; `src/aeat/entrypoints/mcp/tests/test_annotations.py`.

### Phase `P02` - Discovery quality

Close the mcp-progressive-discovery P2 conformance gap: semantic-back the command index so search stops mis-ranking homonyms, add a describe-by-key meta-tool, and add a search overflow signal (audit findings command-search-lexical-only-mis-ranks, discovery-schema-and-overflow-gaps).

- [x] `P02.S07` - Add the semantic side to the command index: precompute model2vec embeddings over the command docs at build/first-use, fuse lexical + semantic with RRF, preserve the lexical-only degraded mode, and add per-column BM25 weighting (command key and tool name over description over help); `src/aeat/application/command_search/_index.py`.
- [x] `P02.S08` - Add alias vocabulary to the composite quickfile command document so outcome-phrased queries surface it, and re-back search ranking on the hybrid retriever; `src/aeat/entrypoints/mcp/_meta_tools.py`.
- [x] `P02.S09` - Add a pinned retrieval golden set built from the review failing queries (import a bank statement ranks ledger.import first, and file my quarterly VAT surfaces quickfile in the top hits) and assert the ranking; `src/aeat/application/command_search/tests/test_command_ranking_golden.py`.
- [x] `P02.S10` - Add the describe meta-tool returning one command's full descriptor by key (description, input schema, annotations, confirmation tier, risk classification, owning toolset, persona reachability); `src/aeat/entrypoints/mcp/_meta_tools.py`.
- [x] `P02.S11` - Add the search overflow signal (total_matches, truncated, and a hint naming describe and toolset activation) to the search meta-tool result; `src/aeat/entrypoints/mcp/_meta_tools.py`.
- [x] `P02.S12` - Wire the describe meta-tool into the server, advertise it in the core surface alongside search/execute/toolsets, and add its tests; `src/aeat/entrypoints/mcp/tests/test_meta_tools.py`.

### Phase `P03` - Discoverability prose and schema fidelity

Teach the long-tail discovery path and document the toolset feature so a cold agent finds it, and close the schema-fidelity tails (prose-only enums, one-of identifiers) (audit findings toolsets-undiscoverable, discovery-schema-and-overflow-gaps).

- [x] `P03.S13` - Add a long-tail discovery section to the harness floor content teaching the search then describe then execute then toolsets path and the shell-verb-to-command-key translation, authored in the single harness source; `src/aeat/_data/agent/rules/operator-orientation-routing.md`.
- [x] `P03.S14` - Cross-reference the toolsets tool from the search and execute tool descriptions and give the toolsets tool description a when-to-activate explanation; `src/aeat/entrypoints/mcp/_server.py`.
- [x] `P03.S15` - Add the toolset non-empty-against-live-keys gate so a renamed carve-out token fails loudly rather than silently emptying a group; `src/aeat/entrypoints/mcp/tests/test_toolset_activation.py`.
- [x] `P03.S16` - Render the ledger.import provider field as a JSON enum and express one-of identifier combinations via anyOf where the CLI declares alternatives, or a declared description convention where JSON Schema cannot express it; `src/aeat/entrypoints/mcp/_input_schema.py`.
- [x] `P03.S17` - Add the schema-fidelity tests (provider enum present, one-of identifier handling) and confirm the rule-surface drift gate and documented-command conformance stay green; `src/aeat/entrypoints/mcp/tests/test_tools_and_dispatch.py`.

## Description

Closes the conformance debt and discovery gaps the 2026-07-08 MCP console review
surfaced (audit `2026-07-08-mcp-console-review-audit`), under the two already
accepted MCP ADRs - this plan introduces NO new architectural decision. P01
lands the `mcp-protocol-hardening` H3 ruling as it was actually decided (declared
per-command risk data keyed by command key with a no-silent-default parity gate)
in place of the leaf-name frozensets the implementation shipped, closing the one
safety-grade finding: a new mutating verb can no longer auto-approve or escape
handoff denial. P02 lands the `mcp-progressive-discovery` P2 ruling (FTS5 +
model2vec hybrid retrieval) on the command index in place of the lexical-only
ranking that mis-ranks homonyms, plus the `describe` meta-tool P2 delegated to the
plan and a search overflow signal. P03 teaches the long-tail discovery path and
documents the toolset feature so a cold agent finds it, and closes the
schema-fidelity tails. The companion `mcp-identity-linked-operation` plan (a new
ADR) depends on P01's risk table for its mutating-set definition.

## Parallelization

`P01` ships FIRST and alone - it is the safety item, and the identity plan's gate
consumes its risk table. `P01.S01` (author the table) and `P01.S02` (rewire +
delete frozensets) are one atomic commit per the relocation-atomicity rule;
`P01.S03` - `S06` (persona re-home, gates, tests) follow in the same phase. `P02`
and `P03` are independent of each other and may run in parallel after `P01`,
except that both touch `_meta_tools.py` (P02.S02/S04/S05) and `_server.py`
(P02.S06, P03.S02) - serialize edits to those two files. Within `P02`, the
semantic index (S01) and the golden set (S03) gate the ranking claim, so S03
follows S01/S02.

## Verification

- No exposed command in a mutating family lacks a declared risk row, an
  unclassified mutating verb fails the build, and a verb whose leaf is
  submit/present/send that fails to declare `live_write` trips the tripwire test
  (`test_risk_table_parity.py`, `test_write_policy_mutability_parity.py`); the
  frozensets are deleted from production inference; the existing coherence and
  annotation-coverage gates stay green.
- A cross-taxpayer probe: a synthetic new mutating verb named `purge` (leaf not
  in any old frozenset) is classified destructive/confirm ONLY when it has a
  declared row, and the build refuses it when it has none - the anti-tautology
  proof the old heuristic could not give.
- The pinned retrieval golden set passes: "import a bank statement" ranks
  `ledger.import` first (not `import_feedback`), and "file my quarterly VAT"
  surfaces `quickfile` in the top hits (`test_command_ranking_golden.py`); the
  lexical-only degraded mode still returns results.
- `describe_command` returns a known command's full descriptor by key without a
  re-search; `search` results carry `total_matches`/`truncated` and a refine
  hint (`test_meta_tools.py`).
- The harness long-tail section teaches search→describe→execute→toolsets and the
  verb-string→command-key translation; the toolset tool and search/execute
  descriptions cross-reference toolsets; the toolset non-empty gate fails on a
  renamed carve-out token; the rule-surface drift gate and documented-command
  conformance stay green.
- `ledger.import` `provider` renders as a JSON `enum`; one-of identifier combos
  are expressed via `anyOf` or a declared convention (`test_tools_and_dispatch.py`).
- Full-tree gates: `uv run --no-sync pytest src/aeat/entrypoints/mcp
  src/aeat/application/operator_surface src/aeat/application/command_search -q`
  green; `uv run --no-sync pytest --collect-only -q` clean;
  `python -m aeat.locales scaffold --check` clean.

For tier-specific verification cadence, see the authorizing
documents linked in the `related:` frontmatter. -->
