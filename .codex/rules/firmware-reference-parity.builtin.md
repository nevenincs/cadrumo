---
name: firmware-reference-parity.builtin
trigger: always_on
---

# Firmware reference parity: named artifacts must resolve

## Rule

Every skill, persona, template, or CLI verb named in firmware prose — the
bundled rules, system fragments, skills, personas, and templates shipped under
the vaultspec package — must resolve to a shipped artifact of exactly that name,
and a rename must update every referencing surface in the same change.

## Why

The firmware is consumed by agents at session load, so a dangling name in an
always-on mandate degrades every downstream session. Two such breakages were
recorded: a phantom skill name routing a pipeline phase across the pipeline
table, intent table, and catalog, and an orphaned template left behind by a
rename. Both were renames that updated one surface and left the old name
standing in the others.

## How

- Before naming a skill, persona, template, or verb in firmware prose, confirm
  it ships: `vaultspec-core spec <resource> list` (one of `rules`, `skills`,
  `agents`) enumerates the shipped artifacts, and templates live under the
  package's `builtins/templates/`.
- **Good:** renaming a skill updates the pipeline table, the intent table, the
  catalog, and every cross-reference atomically, so no surface names the old
  slug.
- **Bad:** renaming the directory or template file and leaving the old name in
  the system prompt, a discipline rule, or another skill's prose.

Until a structured firmware-name linter lands, the cross-surface sweep is the
author's discipline and `vaultspec-core spec <resource> list` is the check.

## Source

Audit `2026-06-10-firmware-wording-review-audit` (REVIEW-001, REVIEW-002);
sibling decision ADR `2026-06-09-firmware-wording-review-adr` (D1, D7).
