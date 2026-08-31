---
tags:
  - '#audit'
  - '#agent-context-governance'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:bd4927b1f44f68140b6834f38086a9c89c7692587ef76c2e282779caac89fc6d'
related:
  - '[[2026-06-01-agent-rule-consolidation-adr]]'
  - '[[2026-07-01-import-centralization-adr]]'
  - '[[2026-07-13-docs-cli-sequences-audit]]'
---

# `agent-context-governance` audit: `Full context rewrite`

## Scope

This audit covered every project rule loaded by the root Codex harness, every project Vaultspec skill, the Vaultspec system and built-in corpus, provider sync configuration, user-global agent skills, and user-global always-on rules. It compared those instructions with accepted architecture decisions, current registry and CLI code, the active semantic-consolidation refactor, and the live quality gates.

Built-in Vaultspec rules and skills were read for conflicts but not modified. Provider copies are generated; project edits were made only under `.vaultspec`. Existing source citations require the nineteen custom rule slugs to remain stable during this rewrite.

## Findings

### `full-context-rewrite` | critical | orchestration rules displaced task judgment

`aeat-agent-orchestration` required swarms, persistent role teams, campaign balancing, and agent-count process regardless of task shape or operator instruction. Several built-in project skills repeat mandatory delegation. These demands consume context and can directly contradict an operator's explicit single-agent requirement without improving a technical invariant.

### `full-context-rewrite` | critical | registry re-export exception contradicted accepted architecture

`aeat-registry-authority-flow` allowed a curated `core.external_constants` re-export layer while `aeat-architecture-boundaries` and the accepted import-centralization decision require one public definition, direct consumer imports, and inert package initializers. The active semantic-consolidation plan is still retiring facades, so the exception weakened the exact boundary under repair.

### `full-context-rewrite` | high | custom context was dominated by history and frozen measurements

The nineteen custom rules contained 92,781 bytes and about 12,803 words. They mixed stable invariants with dated campaign instructions, counts, migration narratives, repeated commands, review topologies, and duplicated examples. The rewrite retains all slugs but reduces the rule corpus to 29,320 bytes and 4,172 words, with each rule focused on an enforceable boundary.

### `full-context-rewrite` | high | continuity skill embedded broken and stale automation

The continuity skill contained 536 lines, dated measurements, and pasted scripts that imported `resources().modelos`. The current `ResourceRegistry` has no `modelos` member, so following the skill would fail before adjudication. The repository already exposes `bundled_authority()` and a dedicated AEIP workflow for its supported family.

### `full-context-rewrite` | high | feature gate skill encoded obsolete campaign state

`feature-surface-gate` hard-coded a retired branch, Unix temporary paths and shell pipelines, multi-agent assumptions, missing vault documents, and prose append behavior that conflicts with the current Step Record schema. It had no live project references and did not represent a reusable capability.

### `full-context-rewrite` | high | global skills created duplicated and always-on context

`context7-mcp` and `find-docs` duplicated the same broad trigger; the latter instructed a global package installation during normal use. Separate Cursor and OpenCode rules mandated Context7 for every interaction. `find-skills` encouraged further global installation, `improve-animations` imposed a non-Vaultspec multi-agent planning system, `aeat-ref` was an unfinished scaffold, and unrelated vendor/design skills added substantial global context without serving AEAT work. A subsequent operator ruling removed the remaining `impeccable` and `rmux` skills as well: user scope now carries no non-built-in skill, rule, instruction entrypoint, connector, Claude hook, or user-scope plugin. Tooling is enrolled by the project that needs it.

### `full-context-rewrite` | medium | Claude task history was mistaken for rule authority

An old Claude task record contained a long note about `aeat-vaultspec-centralisation`, while completed job snapshots contained copied provider files. The only live repository rule is authored at `.vaultspec/rules/aeat-vaultspec-centralisation.md`; `.claude/rules/aeat-vaultspec-centralisation.md` is its generated projection and matches the source body. The stale task record was removed. Job snapshots are runtime history, not loaded global instructions, and were not treated as rule authority.

### `full-context-rewrite` | medium | documentation and CLI rules contained stale interface instructions

The documentation rule mandated role-based review and `file://` chat links, both properties of an agent harness rather than the product. The naming rule showed `censo file` although the live CLI contract uses `censo import --file`. These details would cause compliant agents to produce incorrect output.

### `full-context-rewrite` | medium | governance was leaking back into production context

The project centralisation rule previously preserved rule citations in source while the Vaultspec core contract says production code and documentation stand alone and cite code one-way from the vault. The repository has extensive existing slug citations, so deleting or renaming rules in this task would create a separate source migration, but new leakage must stop.

### `full-context-rewrite` | medium | broad vault health is already red for unrelated work

The read-only full vault check reported substantial pre-existing feature, mapping, schema, body, and annotation debt across active work. A broad fix would rewrite concurrent work and is outside this governance change; validation must therefore remain feature-scoped plus source/sync checks.

## Recommendations

1. Keep delegation optional and operator-controlled; judge completion by live evidence and gates, not agent topology.
2. Enforce direct imports from semantic public defining modules with no re-export exception. Treat current facade-preserving tests as refactor debt, not authority to weaken the target rule.
3. Maintain the rewritten rules as concise invariants. Do not add new custom rules; strengthen an existing rule or executable gate.
4. Use the rewritten continuity skill, `bundled_authority()`, official AEAT/BOE evidence, the dedicated AEIP workflow where applicable, and the four strict continuity gates. Never restore embedded census scripts or frozen totals.
5. Keep `feature-surface-gate` removed. Path-scoped validation can be selected from changed files without a branch- and campaign-specific skill.
6. Keep user scope empty of non-built-in skills, rules, instruction entrypoints, connectors, hooks, and plugins. Enroll tooling only in the project that needs it. Installation-owned default marketplaces and plugin-management facilities may remain present but carry no installed user plugin.
7. Migrate existing production and test citations to self-contained code contracts in a separately scoped change, preserving current rule slugs until that migration is validated.
8. Preview provider sync, force-prune only generated stale artifacts, and run focused spec, feature, rule-citation, and import-boundary checks. Do not apply a broad vault fix to unrelated active work.
