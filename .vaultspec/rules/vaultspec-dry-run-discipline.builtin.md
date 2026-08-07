# Dry-run discipline: preview destructive verbs before applying

## Rule

Before invoking any vaultspec CLI verb that writes or removes state, run the
same verb with `--dry-run` first, read the previewed change list carefully, and
apply the real run only after the preview matches your intent. `--dry-run` is
the canonical preview path on every destructive verb.

## Why

A preview only protects the operator who reads it. Running a state-writing verb
in a busy repository without one produces dozens of file changes, a rewritten
`.gitignore`, and a manual cleanup.

**A preview is a claim about intent; the diff is evidence about output.** Some
verbs rewrite a whole document to change part of it, and their preview renders
only the intended change while the real write also touches unrelated rows — so
for those, capture the file before the run and diff the whole file afterwards
rather than trusting the preview. See `vaultspec-plan-editing-discipline`.

**If a preview is empty on a verb that should produce side effects, escalate.**
An empty preview is a finding, not a green light.

## How

- **Good:** `vaultspec-core install --dry-run` against a directory, read the
  file list, confirm provider selection, then run the real install.
- **Good:** scaffold a document with `--dry-run` to preview the path,
  frontmatter and tier before the file is created.
- **Bad:** running a state-writing verb in a busy repository without a preview.

## Source

Audit `2026-05-17-cli-simplification-ux-audit` (findings S4, S14, and the gating
dimension of B9); sibling decision ADR
`2026-05-17-cli-blast-radius-gating-adr`.
