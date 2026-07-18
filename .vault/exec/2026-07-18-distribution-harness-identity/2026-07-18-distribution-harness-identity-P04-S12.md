---
tags:
  - '#exec'
  - '#distribution-harness-identity'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S12'
related:
  - "[[2026-07-18-distribution-harness-identity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace distribution-harness-identity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S12 and 2026-07-18-distribution-harness-identity-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Prove the rule-surface conformance gate and the full harness, generation, eval, and MCP test surface are green, re-run the S69-shape installed-client evidence recapture across the claimed Claude clients, and reconcile every observation in the close audit and ## Scope

- `src/cadrumo/agent/tests/test_rule_surface_conformance.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove the rule-surface conformance gate and the full harness, generation, eval, and MCP test surface are green, re-run the S69-shape installed-client evidence recapture across the claimed Claude clients, and reconcile every observation in the close audit

## Scope

- `src/cadrumo/agent/tests/test_rule_surface_conformance.py`

## Description

- Proved clean collection: `uv run --no-sync pytest --collect-only -q src/cadrumo` reports 12975 tests collected, no collection errors.
- Ran the full migrated surface as one suite: `src/cadrumo/agent/tests` (harness + generation + the rule-surface conformance gate `test_rule_surface_conformance.py`), `src/cadrumo/agent/eval/tests` (golden eval), `src/cadrumo/entrypoints/mcp/tests` (MCP prompt/resource/persona-scope/server-wiring/meta-tools/harness-delivery), the CLI agent workspace/plugin tests, and the distribution-identity verifier self-test.
- Confirmed the acceptance verifier itself (S11) exits 0 against HEAD.

## Outcome

- Full suite: 407 passed (harness, generation, eval, MCP, CLI-agent, and verifier self-test) with clean collection. The rule-surface conformance gate is green: every cited verb, flag, and envelope field still resolves and no operator document names a package internal, against the fully `cadrumo-` prefixed harness.
- The distribution-identity verifier exits 0 with overall `ok: True` across every surface (namespace, inventory parity, product identity, model-facing digest `a025188a...`, and all five client-display product descriptions at six-claim EN/ES parity) - the acceptance invariant of ADR `2026-07-16-distribution-harness-identity-adr` is satisfied for the first time.
- The migration's code + verifier surface is complete: every authored persona (7), rule (7), and skill (34) identifier, and every generated workspace/plugin/marketplace/MCP-prompt/resource projection, carries the `cadrumo-` product prefix; the one non-derived MCP projection identifier (the orientation-prompt rule-resource URI) is prefixed; the eval fixtures are re-baselined; the digest is re-pinned; and the bilingual client-display descriptions carry full claim parity.

## Notes

- POST-COHORT CLIENT LANE (not this executor's scope): the S69-shape installed-client evidence recapture across the claimed Claude clients (Claude Code / Desktop / Cowork) is owned by the separate client-lane executor (readiness campaign rows S27/S30/S38-S40/S69), to be run against the migrated cohort once it is cut. It is explicitly NOT re-run here; this record reconciles the source-side acceptance (verifier exit 0 + full suite green) and defers the installed-client recapture to that lane, per the ADR's "reconcile every observation ... leave failed deliverables open" close discipline.
- No incidents. No production code was changed in S12 (verification-only step). All P04 rows (S10 digest/self-test, S11 verifier exit 0 + evidence, S12 full-suite + conformance) are backed by committed exec records; plan rows remain open for coordinator closure.
