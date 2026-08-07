---
name: vaultspec-archive-discipline.builtin
trigger: always_on
---

# Archive discipline: audit incoming references before retiring a feature

## Rule

Before invoking `vaultspec-core vault feature archive <feature-tag>`, run the
same verb with `--dry-run` as the discovery pass and audit the preview for
**incoming references**: documents outside the feature whose `related:`
frontmatter points at documents inside it. Decide whether each incoming
reference should be rewritten, acknowledged as dangling, or block the archive
entirely, before applying the real run.

## Why

The CLI closes the verb-level gaps — `archive` carries `--dry-run`, a paired
`vault feature unarchive` reverses a mistake, and archiving a nonexistent tag
exits non-zero with an error. What the CLI cannot decide is whether an incoming
cross-feature reference is provenance to preserve, a stale link to drop, or a
dependency that should block retirement. That judgment is this rule.

## How

- Run the archive with `--dry-run`, read the previewed changes, and classify
  every incoming reference before the real run.
- After the real run, verify `vaultspec-core vault check all` stays green.
- If the archive was a mistake, `vaultspec-core vault feature unarchive
  <feature-tag>` reverses it.

## Source

Audit `2026-05-17-cli-simplification-ux-audit` (finding B9); sibling decision
ADR `2026-05-17-cli-memory-lifecycle-adr`.
