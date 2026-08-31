# AEAT Vaultspec centralisation

## Authority and sync

- `.vaultspec/rules/` and `.vaultspec/skills/` are the authored project sources. Provider directories such as `.codex/rules/`, `.agents/skills/`, `.claude/`, `.gemini/`, and `.agent/` are generated destinations.
- Edit, add, or remove project governance only at the Vaultspec source, then preview and run `vaultspec-core sync`. Do not hand-edit provider copies.
- Files ending in `.builtin.md` and built-in Vaultspec skills are installation-owned. Never edit, delete, fork, or shadow them from the project.
- Use the Vaultspec CLI for vault lifecycle metadata, status, links, stamps, archive operations, and generated indexes. Body-only edits still require the owning focused check afterward.

## Context budget

- Do not add a rule for a one-off defect, campaign, plan step, tool preference, or fact already enforced by code. Codification is retired for this project; strengthen the owning gate, schema, type, generator, or existing rule instead.
- A rule states stable, enforceable invariants and the boundary they protect. Exclude dated inventories, frozen counts, migration history, agent topology, repeated examples, and long command transcripts.
- A skill contains only a repeatable workflow whose procedural detail is genuinely needed at invocation time. Move optional detail into referenced resources; remove a skill when normal repository instructions are sufficient.
- Provider-global skills and rules must be narrowly triggered and useful across projects. Project-specific behavior belongs here, not in a user's global context.

## Separation

- Do not create private agent memory or a parallel policy directory.
- Production code, tests, configuration, and user documentation do not cite Vaultspec documents, rule slugs, plan steps, audit names, or agent metadata. Existing citations are migration debt; do not add new ones.
- Preserve existing rule slugs while they are referenced by current gates or source. Rename or consolidate only with an explicit repository-wide citation migration and validation.
