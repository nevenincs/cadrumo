---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S69'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace distribution-installation-readiness with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S69 and 2026-07-15-distribution-installation-readiness-plan placeholders are machine-filled by
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
     The Capture each real Claude client's harness identifier inventory, MCP server name, English MCP product description, and Spanish MCP product description and compare them with the exact cohort and ## Scope

- `.github/workflows/packaging-claude.yml`
- `var/distribution-install-readiness` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Capture each real Claude client's harness identifier inventory, MCP server name, English MCP product description, and Spanish MCP product description and compare them with the exact cohort

## Scope

- `.github/workflows/packaging-claude.yml`
- `var/distribution-install-readiness`

## Description

- Inventory retained Claude Code, Claude Desktop, and Cowork client evidence without
  launching, installing, or altering a client.
- Bind each real observation to its client version, surface, server identity, artifact
  identity, installed metadata, harness identifiers, and bilingual claim verdicts.
- Preserve missing artifact hashes, unobserved harness projections, unprefixed names,
  and absent Spanish text as explicit failures rather than inferred passes.
- Validate the retained JSON record and its evidence-source digests.

## Outcome

The retained client-identity record has SHA-256
`ddda9b49c91ea173858e26c684804c181569c0ab0505bcf7e62985d34b72ff76`.
It records three real Claude surfaces and concludes that none complies with the complete
identity and bilingual-description contract.

Claude Code 2.1.211 installed `cadrumo@neve`, connected to server `cadrumo`, and
completed the real tax oracle. Its installed plugin exposes 7 unprefixed agents and 34
unprefixed skills. Its client-generated installed-plugin commit is not the accepted
source commit, and the record has no immutable plugin-artifact or wheel digest. It also
has no standalone rule inventory and no captured prompt/resource names, so it cannot be
matched to the accepted cohort. Its product description is English-only and states only
capability, gated execution, and never-files-live claims.

Claude Desktop 1.22209.0.0 installed and connected the exact MCPB with SHA-256
`8615c66cc05441a8b60f82ccef7f5a1374af81dd37890acf03a6341c62f24cd2`.
The installed manifest SHA-256 is
`b35b25791ffa3cc28cc2b9c2549bf21c30f79c3463f2a6ab7a28f401e9ecc1ba`,
the accepted root-wheel SHA-256 is
`cac6c982a5be58006533214f3cf5d1340c6a45d92953995d573737b84199134d`,
and server `cadrumo` connected with 16 tools. Its installed client configuration names
7 unprefixed personas; client evidence does not enumerate skills, rules, prompts, or
resources. Its short description carries capability, gated-execution, and
never-files-live claims in English; its long description carries all six required
claims in English. Neither field contains Spanish text.

The successful Desktop local-agent host-loop session is retained as the real Cowork
surface because its client record advertises Cowork tools and plugin-management commands
and runs beneath local-agent-mode storage. It used the same exact installed MCPB and
completed the real tax operation. Its session did not enumerate the complete harness or
repeat product-description metadata; those fields are bound to the shared installed
extension manifest and explicitly marked as absent from the session transcript. The
description remains English-only.

## Notes

This row remains unchecked. Every observed client carries at least one unprefixed
harness identifier and lacks a Spanish MCP product description. Claude Code also lacks
exact-cohort artifact binding, and none of the three client records captures a complete
installed agent, skill, rule, prompt, and resource inventory.

No workflow change was made. The current evidence can support an honest failure record,
but there is not yet an executable, tested workflow that acquires these client metadata
surfaces and binds every field automatically. The ignored evidence file remains under
`var/distribution-install-readiness/s69-claude-client-identity`.
