---
name: aeat-vaultspec-centralisation
trigger: always_on
---

# AEAT vaultspec centralisation

Keep all repo-specific agent rules in `.vaultspec/rules/rules/`. Do not place project rules, memories, policies, handover mandates, or provider-specific instructions in Claude, Codex, Gemini, or user-level agent config.

Promote durable repo guidance into vaultspec source rules or vault documents. Delete stale provider memory after migration. Treat provider files as generated outputs, not authorship surfaces.

Use `uv run vaultspec-core spec rules add` for new custom rules. Use `uv run vaultspec-core install --force` after rule changes. Do not edit generated provider rule directories or vaultspec-managed gitignore blocks by hand.
