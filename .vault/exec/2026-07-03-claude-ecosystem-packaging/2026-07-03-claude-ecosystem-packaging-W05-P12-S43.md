---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S43'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace claude-ecosystem-packaging with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S43 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Install the plugin from the marketplace into the Claude Code CLI and confirm the local stdio aeat-mcp server runs (the confirmed floor) and ## Scope

- `docs/verification/claude-code-install-proof.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Install the plugin from the marketplace into the Claude Code CLI and confirm the local stdio aeat-mcp server runs (the confirmed floor)

## Scope

- `docs/verification/claude-code-install-proof.md`

## Description

- Materialise the plugin live (`aeat app agent --layout plugin`), compose the marketplace tree from the landed `packaging/marketplace` manifest plus the generated plugin, strict-validate both, register the marketplace with the real Claude Code CLI 2.1.199, and install: `claude plugin install aeat@aeat-marketplace` succeeded (user scope).
- Observe both designed install behaviours live: `defaultEnabled: false` (installs disabled, enable command named) and the persona `userConfig` option detected and configurable.
- Prove the stdio server itself: the real-client MCP handshake conformance tests pass (2 passed).
- Record the proof at `docs/verification/claude-code-install-proof.md`; commit `557d4ba949`.

## Outcome

- The Claude Code floor is verified live end-to-end EXCEPT the final uvx link: the installed `.mcp.json` launches `uvx --from aeat==0.1.0 aeat-mcp`, which cannot resolve until the first wheel is published to PyPI.

## Notes

The residual link is operator-gated by design (PyPI account + scoped token; RELEASING.md name-claim sequencing). The proof document carries the re-run instruction for after the first publish. Executed inline by the coordinator during the executor-fleet rate-limit window.
