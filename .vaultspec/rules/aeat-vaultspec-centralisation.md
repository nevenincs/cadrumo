---
name: aeat-vaultspec-centralisation
trigger: always_on
---

# AEAT vaultspec centralisation

Keep all repo-specific agent rules in `.vaultspec/rules/`. Do not place project rules, policies, handover mandates, or provider-specific instructions in Claude, Codex, Gemini, or user-level agent config. Treat provider files as generated outputs, not authorship surfaces.

Do not author new rules: the operator retired codification on 2026-07-13 because the always-on rule corpus bloats every agent context. Record durable lessons in the campaign's audit document instead.

Correct or remove an existing rule on its `.vaultspec/rules/*.md` source (or via `uv run --no-sync vaultspec-core spec rules edit|remove`) and propagate with `vaultspec-core sync`. Never hand-edit the generated `.claude/rules/`, `AGENTS.md`, `GEMINI.md`, or `CLAUDE.md` copies — the next sync silently reverts the change, so the fix is lost.
