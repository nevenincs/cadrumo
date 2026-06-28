# Original User Request

## Initial Request — 2026-06-16T17:55:54Z

# Teamwork Project Prompt — Draft

Drive a complete documentation hardening campaign for developer-facing documentation (CLI and Architecture docs). Ensure proper technical contextualization, clear jargon-free prose, and strict adherence to the Diataxis framework using bundled docs CLI tools.

Working directory: Y:\code\aeat-worktrees\chore-476-restructure-execution
Integrity mode: development

## Requirements

### R1. Architecture Primer and CLI Orientation
Focus the documentation on being a primer for architecture orientation. The docs should document the `aeat-cli` architecture, underpinning it with the core architecture so developers can orient themselves. Since the project is self-documenting (the source code contains the docs needed to understand the code deeply), the developer docs should not duplicate code-level details but instead serve as a high-level orientation guide. Ensure compliance with the Diataxis framework where applicable.

### R2. Technically Grounded Prose
Author the documentation using clear, jargon-free prose. Use codebase searches and `vaultspec-rag` to accurately represent the architecture. Do not assume or invent system behavior.

### R3. Strict Tooling Adherence
Any updates to generated surfaces MUST use the appropriate tools (`python -m dev.docs.apidocs scaffold` for API stubs, `vaultspec-core spec reference generate` for CLI references). Do not hand-edit these files.

## Acceptance Criteria

### Technical & Tooling Integrity
- [ ] `just docs-check` passes with zero errors or warnings (no broken cross-references).
- [ ] `vaultspec-core vault check all` passes.
- [ ] No generated API `.rst` stubs or CLI reference generated-zones have been hand-edited.

### Content Quality
- [ ] Developer documentation exhibits distinct materials for all four Diataxis quadrants.
- [ ] Sentences are concise, straightforward, and free of unnecessary technical jargon.
