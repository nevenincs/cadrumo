---
tags:
  - '#plan'
  - '#distribution-harness-identity'
date: '2026-07-18'
modified: '2026-07-18'
tier: L2
related:
  - '[[2026-07-16-distribution-harness-identity-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace distribution-harness-identity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries the AUTHORIZING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution Record artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorizing documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `distribution-harness-identity` plan

Bring every authored, generated, and installed harness identifier under the `cadrumo-` prefix and give every MCP product description verified-equivalent English and Spanish copy, until the distribution-identity verifier exits zero.

### Phase `P01` - Rename the authored harness sources under the cadrumo- prefix

Hard-cut every authored persona, skill, and rule identifier to the cadrumo- prefix, each an atomic commit that carries its suite-breaking consumers so the generators follow and the test tree stays green.

- [ ] `P01.S01` - Rename the seven operator rule documents to the cadrumo- prefix and sweep every consumer in one atomic hard-cut commit: generated CLAUDE.md rule imports, MCP rule resources, operator_rules_text callers, the test_operator_rules_exist assertion, and the rule generation tests; `src/cadrumo/_data/agent/rules/`.
- [ ] `P01.S02` - Rename the seven persona documents to the cadrumo- prefix, lift the AgentPersona StrEnum values to match, and sweep every consumer atomically: the persona-scope module and its pinning tests, the harness whoami tool file lookup, MCP server wiring, meta-tools and identity-gate tests, generation tests, and the MCPB manifest persona enumeration; `src/cadrumo/_data/agent/personas/`.
- [ ] `P01.S03` - Rename the 34 skill directories and their SKILL.md name frontmatter to the cadrumo- prefix and sweep intra-skill name cross-references, the eval scenario skill_name fields, and the skill-name generation tests in one atomic commit; `src/cadrumo/_data/agent/skills/`.

### Phase `P02` - Prefix the MCP projection identifiers and re-baseline the eval fixtures

Prefix the one non-derived MCP projection identifier and re-baseline the eval scenarios and golden expectations onto the migrated persona and skill tokens.

- [ ] `P02.S04` - Prefix the orientation-prompt embedded rule-resource URI (the synthetic cadrumo://rule/operating-rules leaf) so every embedded reference carries the cadrumo- prefix, and update the prompt and resource projection tests; `src/cadrumo/entrypoints/mcp/_prompts.py`.
- [ ] `P02.S05` - Re-baseline the eval scenarios and golden expectations onto the migrated persona and skill tokens (scenario skill_name and persona fields, identity-switch and discovery golden scores, flywheel report expectations); `src/cadrumo/agent/eval/scenarios/`.

### Phase `P03` - Author and wire the bilingual MCP product descriptions

Author the product-reviewed English and Spanish product copy carrying all six required claims, wire it into each client-display source, and enroll the approved pairs in the verifier.

- [x] `P03.S06` - Author and approve the product-reviewed bilingual product-description copy for the four client-display blocks (plugin, marketplace, MCPB description, MCPB long_description), each carrying labeled English and Spanish text covering the six required claims (capability, safety, privacy, on-host storage, human confirmation, never-files-live) as a docs-authority approval act producing the exact wording with no code change; `.vault/exec/2026-07-18-distribution-harness-identity/`.
- [ ] `P03.S07` - Wire the approved plugin bilingual copy into the plugin description source and enroll its approved English-Spanish pair for the plugin and marketplace-plugin client-display keys in the verifier approval set; `src/cadrumo/agent/_workspace.py`.
- [ ] `P03.S08` - Wire the approved marketplace bilingual copy into the marketplace description source and enroll its approved English-Spanish pair in the verifier approval set; `src/cadrumo/agent/_workspace.py`.
- [ ] `P03.S09` - Wire the approved MCPB bilingual description and long_description into the manifest and enroll their approved English-Spanish pairs in the verifier approval set; `packaging/mcpb/manifest.json`.

### Phase `P04` - Verify every distribution boundary and recapture installed evidence

Re-pin the migrated model-facing inventory, drive the distribution-identity verifier to exit zero, and recapture the installed-client evidence rows in the close audit.

- [ ] `P04.S10` - Re-pin the frozen model-facing-description digest to the migrated prompt and resource identifier inventory and update the verifier self-test expectations to the migrated compliant-surface counts; `dev/packaging/verify_distribution_identity.py`.
- [ ] `P04.S11` - Run the distribution-identity verifier and prove it exits zero, capturing the JSON evidence document as the acceptance artifact; `dev/packaging/verify_distribution_identity.py`.
- [ ] `P04.S12` - Prove the rule-surface conformance gate and the full harness, generation, eval, and MCP test surface are green, re-run the S69-shape installed-client evidence recapture across the claimed Claude clients, and reconcile every observation in the close audit; `src/cadrumo/agent/tests/test_rule_surface_conformance.py`.

## Description

The accepted verification-only ADR `2026-07-16-distribution-harness-identity-adr` added the blocking acceptance invariant but deliberately deferred the migration that satisfies it. The operator has now approved that migration. Its two deliverables are a namespace and a translation parity, both measured by the read-only verifier `dev/packaging/verify_distribution_identity.py`: the migration is done when that verifier exits zero.

The re-derived current failure inventory, taken from `src/cadrumo/_data/agent/` and the generators in `src/cadrumo/agent/`, is: seven authored personas (`classifier`, `coordinator`, `ledger-groomer`, `modelo-preparer`, `onboarding`, `reconciler`, `verifier`), 34 authored skills, and seven authored operator rules (`operator-envelope-reading`, `operator-grounding`, `operator-honest-declaration`, `operator-lifecycle-ordering`, `operator-operating-rules`, `operator-orientation-routing`, `operator-safety-handoff`) all carry unprefixed identifiers, and the generated Claude workspace, plugin, and marketplace agents/skills/rules plus the 48 MCP resources (34 skills, seven rules, seven personas) and the 34 skill-derived prompts inherit them; five client-display description fields (the plugin `description`, the marketplace `description`, the nested marketplace-plugin `description`, and the MCPB `description` and `long_description`) are English-only with zero approved English/Spanish pairs. Top-level MCP identity (`cadrumo`, `cadrumo-mcp`, `cadrumo_`, `cadrumo://`, plugin `cadrumo`) and the resource-template names (`cadrumo-<kind>`) are already compliant and are not touched.

The migration is a hard cut: no alias, no shim, no compatibility name (`no-legacy-compatibility`, `aeat-architecture-boundaries`). Each authored rename is one atomic commit that carries every consumer the change would otherwise break, so `pytest --collect-only` stays clean and the harness-surface conformance gate (`test_rule_surface_conformance.py`) and the generation tests stay green per commit; the distribution-identity verifier is the sole surface that stays red until the final phase, by design. The `AgentPersona` StrEnum values mirror the persona document stems, so the persona rename lifts the enum and sweeps the persona-scope module, the whoami tool file lookup, the MCP server wiring, the MCPB persona enumeration, the eval golden tokens, and every persona-consuming test in the same commit. The bilingual copy is operator-facing filing-grade prose: the coordinator (docs authority) authors and approves the final Spanish wording, and executors wire it and enroll the product-reviewed pairs in the verifier approval set. Spanish-stem naming remains binding; `cadrumo-` is an outer product qualifier that never translates or replaces an established workflow stem.

## Steps

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorizing documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

The phases carry hard ordering: P01 must land before P02 (the projection identifiers and eval tokens follow the authored renames), P02 before P04 (verification observes the settled projection), and P03 is independent of P01 and P02 (the bilingual copy touches description sources, not identifiers) but its wiring steps must precede P04. Within P01 the three authored-family renames (S01 rules, S02 personas, S03 skills) are independent of each other and may proceed in parallel, each as its own atomic hard-cut commit; they are only ordered relative to P02 and P04. Within P03, S06 (the coordinator's copy-approval act) blocks the three wiring steps S07, S08, and S09, which are then mutually independent and may proceed in parallel. Within P04, S10 (the model-facing digest re-pin) must land before S11 (verifier exit-zero), and S12 (conformance, full-suite, and installed-evidence recapture) is last because it depends on the whole migrated surface.

## Verification

The plan is complete when every Step is closed and each of these verifiable checks passes:

- `python -m dev.packaging.verify_distribution_identity` exits zero: every namespace observation is compliant (authored, workspace, plugin, marketplace, and MCP prompt/resource surfaces all carry the `cadrumo-` prefix), every inventory-parity check holds, every product-identity check holds, and every one of the five client-display product descriptions is compliant (labeled English and Spanish present, translation approved, and all six required claims parity-verified in both languages).
- The harness-surface conformance gate `src/cadrumo/agent/tests/test_rule_surface_conformance.py` is green: every cited verb, flag, and envelope field still resolves and no operator document names a package internal.
- The generation tests (`test_workspace.py`, `test_plugin_workspace.py`, `test_marketplace_generation.py`), the MCP prompt/resource/persona-scope tests, and the eval golden tests (`test_identity_switch_scoring_golden.py`, `test_discovery_scoring.py`, `test_report_and_flywheel.py`) are green against the migrated identifiers, and `uv run --no-sync pytest --collect-only -q` reports clean collection.
- The S69-shape installed-client evidence rows are re-captured across the claimed Claude clients against the migrated cohort and reconciled in the close audit, with any failed deliverable left open per the ADR.
