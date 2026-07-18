---
tags:
  - '#exec'
  - '#distribution-harness-identity'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S02'
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
     The S02 and 2026-07-18-distribution-harness-identity-plan placeholders are machine-filled by
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
     The Rename the seven persona documents to the cadrumo- prefix, lift the AgentPersona StrEnum values to match, and sweep every consumer atomically: the persona-scope module and its pinning tests, the harness whoami tool file lookup, MCP server wiring, meta-tools and identity-gate tests, generation tests, and the MCPB manifest persona enumeration and ## Scope

- `src/cadrumo/_data/agent/personas/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rename the seven persona documents to the cadrumo- prefix, lift the AgentPersona StrEnum values to match, and sweep every consumer atomically: the persona-scope module and its pinning tests, the harness whoami tool file lookup, MCP server wiring, meta-tools and identity-gate tests, generation tests, and the MCPB manifest persona enumeration

## Scope

- `src/cadrumo/_data/agent/personas/`

## Description

- Renamed the seven persona documents under `src/cadrumo/_data/agent/personas/` to the `cadrumo-` prefix with `git mv` (`classifier`, `coordinator`, `ledger-groomer`, `modelo-preparer`, `onboarding`, `reconciler`, `verifier` -> `cadrumo-*`).
- Lifted the `AgentPersona` StrEnum values in `_persona_scope.py` to `cadrumo-<stem>` (members unchanged; the stems mirror the renamed document filenames exactly), and swept the module docstring's backticked persona-token citations.
- Swept the inter-persona token cross-references inside the persona prose (`cadrumo-modelo-preparer.md`, `cadrumo-verifier.md`).
- Updated the MCPB manifest persona-enumeration string in `packaging/mcpb/manifest.json` to the seven prefixed tokens.
- Swept every persona-value string consumer: `test_persona_server_wiring.py` (env->enum resolution + refusal message), `test_harness_delivery.py` (`_shipped_persona_text` stems, PERSONA resource-URI leaves, `active_persona.name`), `test_meta_tools.py` (reachable-personas tuple membership + handoff-refusal strings), `test_client_handshake.py` (`CADRUMO_MCP_PERSONA` env), `test_workspace.py` and `test_app_agent_plugin.py` (generated `cadrumo-coordinator.md` agent filename), and `test_live_harness.py` (the server-resolved `CADRUMO_MCP_PERSONA` token).

## Outcome

- The whoami tool lookup (`persona.value + ".md"`), the MCP resource stems, the server wiring, and the plugin/workspace generator all auto-derive persona identity from `.value` / the document filename, so no generator source change was needed; the enum lift and doc renames flow through automatically. `_workspace.py` was intentionally NOT touched (it has live P03 peer WIP and needs no S02 change).
- Green gates: `pytest --collect-only -q src/cadrumo` clean (12967 collected); the combined MCP + agent + eval + CLI-agent run was 398 passed. The persona-scope pinning test (`test_persona_scope.py`) stayed green using enum MEMBERS (value-agnostic). ruff check + format + ty clean on all nine touched Python files.
- Two failures in `test_marketplace_generation.py` are peer-owned P03 (S08) marketplace-bilingual WIP in the working tree (that test and `_workspace.py`/`marketplace.json` are peer-modified and carry zero persona references); they are absent at the committed HEAD and orthogonal to this rename.

## Notes

- INCIDENT (peer commit sweep): the S07 bilingual-wiring commit `8453908726` (a distribution-harness-identity peer commit; the responsible agent is not identifiable from git, since every commit in this worktree shares one committer identity) performed a pathspec commit of the shared `test_plugin_workspace.py` while my uncommitted S02 persona edits (lines ~106-149) were present in the working tree, sweeping my persona-assertion edits into that commit alongside its bilingual edits. The swept content is correct and now at HEAD; `test_plugin_workspace.py` is therefore clean in my tree and is NOT re-committed here. This left HEAD transiently depending on the persona renames landed by this S02 commit (HEAD asserted `cadrumo-coordinator.md` before the file existed under that name); this commit closes that gap. No work was lost. (Correction: an earlier draft of this note attributed the commit to the `p03-executor` teammate; that teammate's P03 work was the compiled-registry cache under `domain/calculations/registry/` and was fully committed, so it did NOT author this bilingual-wiring commit. The commit SHA is the accurate anchor; the agent is unidentified.)
