---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:c9e5a4372735fbefd346516ac0eac3803261105bf5e00033279e2040f30b4b67'
step_id: 'S35'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Validate the applies_when field at skill load

## Scope

- `src/aeat/agent/__init__.py`

## Description

- Extract the skill-directory walk into a reusable `_iter_skill_dirs` helper yielding `(directory name, SKILL.md)` pairs.
- Reimplement `iter_skill_documents` over that helper so its public behaviour and signature are unchanged for the materialiser, the eval runner, and the conformance gate.
- Add `iter_skill_metadata` yielding every shipped skill's validated `SkillMetadata`; it parses each frontmatter through the structured predicate schema and raises the typed `SkillMetadataError` on a missing or malformed frontmatter, an invalid `applies_when` predicate, or a frontmatter name that disagrees with the skill directory name.
- Add a `TYPE_CHECKING`-guarded import of `SkillMetadata` for the annotation, and publish `iter_skill_metadata` in `__all__`.

## Outcome

The skill loader validates the `applies_when` predicate at load time and refuses to yield metadata for a malformed skill. Existing consumers keep the stable `iter_skill_documents` surface (28 skill documents still enumerate). Ruff check/format clean; pyright reports 0 errors (two pre-existing lazy `__getattr__` `reportUnsupportedDunderAll` warnings are unchanged from HEAD).

SCOPE-CUT REVISION (operator directive, 2026-07-02): the loader was redesigned so `applies_when` is OPTIONAL at the load path - a skill whose predicate has not yet been lifted from prose still loads with `applies_when` `None`, and a predicate that IS present is fully validated (a malformed predicate still raises `SkillMetadataError`). Strict presence enforcement was moved to the S36 coverage gate, so the tree stays loadable while the coordinator authors the P10 lifts.

## Notes

Shared-worktree entanglement: `src/aeat/agent/__init__.py` carried a peer's uncommitted 3-line import-alias refactor (`UTF_8_ENCODING as _UTF_8`, `packaged_data as _packaged_data`) on this same file. That WIP was preserved, never discarded. My own additions were built HEAD-independently and staged through a HEAD-anchored own-only patch (`git apply --cached`), but a peer campaign concurrently staged 19 unrelated files into the shared index, so a verified-index no-pathspec commit was impossible and `git reset` is categorically forbidden here. The commit was therefore made with an explicit single-file pathspec, which excluded all 19 foreign files but committed the working-tree copy of this file and so incidentally carried the peer's small same-file alias rename. No peer work was destroyed; the 19 foreign files remained intact (unstaged or committed by their own campaign).
