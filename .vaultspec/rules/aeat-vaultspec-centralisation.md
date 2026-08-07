# AEAT vaultspec centralisation

Keep all repo-specific agent rules in `.vaultspec/rules/`. Do not place project
rules, policies, handover mandates, or provider-specific instructions in any
provider's own config; treat provider files as generated outputs, not authorship
surfaces.

**Do not author new rules.** Codification is retired: the always-on corpus is
loaded into every agent context, so each new rule taxes every session forever.
Record durable lessons in the campaign's `.vault/audit/` document instead.

**Rules must not reference private agent memory** — a rule is repo-committed and
shared, so a citation to a private memory file is a dangling reference for every
other reader. State the mandate inline.

Correct or remove an existing rule on its `.vaultspec/rules/*.md` source (or via
`vaultspec-core spec rules edit|remove`) and propagate with
`vaultspec-core sync`. Never hand-edit the generated `.claude/`, `.agents/`,
`.codex/`, `AGENTS.md`, `GEMINI.md`, or `CLAUDE.md` copies — the next sync
reverts the change, so the fix is lost.

Prefer merging a new mandate into the nearest existing rule over adding a file.
When a rule's name is cited from `src/` docstrings, keep the name even while
compressing the body.
