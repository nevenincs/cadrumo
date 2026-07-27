---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S33'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace conformance-cli with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S33 and 2026-07-27-conformance-cli-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The refuse a blank or whitespace-only reviewed_by and engineered_by so a stamp cannot claim signoff while naming nobody, bound reviewed_at against a future date, and tighten the bundled-tree invariant from not-null to non-blank and ## Scope

- `src/cadrumo/domain/calculations/registry/_schema.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# refuse a blank or whitespace-only reviewed_by and engineered_by so a stamp cannot claim signoff while naming nobody, bound reviewed_at against a future date, and tighten the bundled-tree invariant from not-null to non-blank

## Scope

- `src/cadrumo/domain/calculations/registry/_schema.py`

## Description

- Replace the `min_length=1` constraint on the revision governance attributions
  with a field validator refusing any declared value whose `.strip()` is empty,
  following the house precedent already in the same package where source
  citation `required_text` entries are rejected on `not item.strip()`.
- Add a `reviewed_at` field validator bounding the signoff date against a fixed
  calendar ceiling declared as `REVISION_REVIEW_DATE_CEILING`.
- Tighten the bundled-tree stamp invariant from not-null to non-blank, and
  assert the shipped tree's signoff dates sit below the ceiling.
- Add six blank-attribution refusal cases, a padded-but-named differential, a
  beyond-horizon refusal and a below-horizon differential.

## Outcome

The finding reproduced exactly as reported. A stamp reading
`review_status = "operator_reviewed"` with `reviewed_by = "   "` and a real
date loaded clean, because a length constraint counts whitespace. The revision
left the unreviewed backlog and rendered as operator-signed-off while naming
nobody -- the same unfalsifiable claim the companion validator exists to
refuse, and worse, because a blank column reads as a signature rather than as
an omission.

The new assertions were written and run against the pre-fix schema first. Four
of the six blank cases did not raise at all:

```
E   Failed: DID NOT RAISE RegistryLoadError
```

for the space and tab forms of both `engineered_by` and `reviewed_by`, and for
the `3999-12-31` signoff. The two empty-string cases did raise, but on the
wrong concept:

```
E     Expected regex: 'must name somebody'
E     Actual message: "...invalid revision '2025': 1 validation error for
      ModeloRevision\nreviewed_by\n  String should have at least 1 character
      [type=string_too_short, input_value='', input_type=str]"
```

Seven failures pre-fix, all of them behavioural. After the validators landed
the same module reports `31 passed`, including the bundled-tree invariant, so
every shipped revision still loads under the tightened rules.

A differential pins the refusal to emptiness rather than to whitespace: a
`reviewed_by = "  operator  "` still loads and keeps its padding. Without that
pairing the refusal could have been passing because the loader had started
rejecting whitespace in an attribution at all. A second differential does the
same for the date: a signoff one day below the ceiling still loads, so the
bound is a boundary and not a blanket refusal of far-off dates.

Verification at the settled tree: the stamp module plus the directory-loader,
cache-isolation and disk-cache-fingerprint modules report `83 passed in 128.87s`.
The whole shipped registry still loads under the tightened validators --
`modelos=73 revisions=90`, with no blank attribution and no signoff beyond the
horizon on any revision, and all 90 still reading `pending_review`, which is the
honest backlog this stamp exists to expose.

## Notes

**Ruling on the future-date bound.** The bound is a fixed calendar ceiling of
2100-01-01, deliberately not a comparison against the local clock, and it is
documented at the constant as an absurdity floor rather than a freshness check.

The reasoning is an asymmetry of failure cost. The registry is the authority
behind every calculation the application performs, so a validation rule that
consults the wall clock makes the shipped tree's validity a property of the
machine that loads it. A container restored from a snapshot with no time sync,
or a stamp written the other side of a timezone boundary from the loading
process, would then refuse the whole registry and take the product with it. A
false refusal there costs incomparably more than a missed absurd date, and no
tolerance window closes it: an unsynced clock can be years behind, not hours.

A tree-derived bound was considered and rejected as unsound rather than merely
weak. Bounding `reviewed_at` relative to the revision's own `valid_from` fails
in both directions: reviewing a 2009 revision today is legitimate and would
need a window of decades, and a revision whose approving orden publishes in
November can legitimately be engineered and signed off before the applicability
window it declares opens.

The accepted cost is stated rather than hidden: a fixed ceiling catches the
sentinel class (`3999-12-31`, `9999-12-31`) that is the realistic failure mode
of a scripted or templated stamp, and does not catch a near-future typo. That
residual is a freshness question, and freshness belongs to the dev-side
conformance audit verb this campaign has yet to ship, where consulting the
clock costs one contributor a re-run instead of bricking the registry. The
audit step is already an open row in this plan and is the natural owner; no new
row was added for it.

**A peer sweep committed this work.** The implementation and its tests were
finished and green in the working tree when an operator-directed commit,
subject `chore(worktree): operator-directed commit of all in-flight work`, took
every in-flight file in the shared worktree including both of this Step's
files. The change landed intact and complete under that SHA, which is recorded
here in place of an own-authored explicit-pathspec commit; nothing was reverted
or re-committed, since unwinding a peer commit is forbidden here. One
consequence is visible: the test module was swept before the formatter ran over
it, and the formatting was corrected in the sibling Step's commit.

**Discovery waiver.** The mandatory semantic-discovery probe was explicitly
waived by the operator for this Step: the semantic index is broken and its
service stopped, with a standing instruction not to start, reindex or otherwise
touch it. Grounding was done with literal search plus whole-file reads of the
schema, the loader placement refusal, the review vocabulary and the existing
stamp tests.
