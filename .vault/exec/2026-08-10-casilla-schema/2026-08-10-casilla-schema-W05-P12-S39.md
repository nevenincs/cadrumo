---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:2306100357b394ae70f33259c686f99b970cf84e94fe0acb9b88b06d63f89091'
step_id: 'S39'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---

# retire the casilla-schema-buildout campaign rule and sync the provider copies in the same action as the closing review

## Scope

- `.vaultspec/rules/casilla-schema-buildout.md`

## Description

- Remove the campaign rule at its `.vaultspec/rules/` source through the owning CLI verb, never by hand-editing a generated provider copy.
- Preview the provider sweep before applying it, since the stale generated copies require an explicit force to remove.
- Propagate to every provider directory and to the generated instruction files.
- Prove no reference to the retired slug survives outside the vault record of the campaign itself.

## Outcome

The rule source is removed. The forced sync reports `203 unchanged, 4 removed`, retiring the generated copies under `.claude/rules/`, `.gemini/rules/`, `.agents/rules/` and `.codex/rules/`, and the generated `CLAUDE.md` rule list no longer names it.

A repository-wide search outside `.vault/` finds no surviving reference to the slug, and no source file references it. The vault's own campaign records keep their references, which is correct: they are the historical record of the campaign, not live instruction.

This retirement is the rule's own instruction. It was written to survive rate limits, context rot and attention attenuation during the buildout, and it says outright that it does not outlive the campaign and must be retired in the same action as the closing honesty review. That review is `2026-08-12-casilla-schema-s36-campaign-close-re-review-audit`, verdict PASS, recorded under S36 immediately before this Step.

## Notes

The removal verb has no `--dry-run`, so the preview discipline was satisfied one level down: `sync` first reported the four generated copies as stale and refused to remove them without a force, and `sync --force --dry-run` previewed exactly those four paths before the real run. Nothing else was in the preview.

The rule's standing content is not lost by retirement. Its durable mandates - one plan entered through its next open step, canonical answers before consumers, one Step to one atomic commit, counts only against a named denominator - are either already carried by the permanent rule corpus or recorded in the campaign's audits, which is where the centralisation rule says a campaign lesson belongs rather than in a new always-on file taxing every future session.

No generated provider file was hand-edited. No data loss and no destructive Git operation occurred.
