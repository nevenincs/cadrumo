---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S34'
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
     The S34 and 2026-07-27-conformance-cli-plan placeholders are machine-filled by
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
     The derive the governance field set from a marker on the field declarations so a fifth governance scalar enrols itself into the placement refusal instead of silently escaping it and ## Scope

- `src/cadrumo/domain/calculations/registry/_schema.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# derive the governance field set from a marker on the field declarations so a fifth governance scalar enrols itself into the placement refusal instead of silently escaping it

## Scope

- `src/cadrumo/domain/calculations/registry/_schema.py`

## Description

- Add a frozen `GovernanceStampMarker` metadata class, its `GOVERNANCE_STAMP`
  singleton, and a `governance_stamp_fields` derivation that reads the marker
  back out of pydantic's retained `Annotated` metadata, all beside the
  `RevisionReviewStatusField` alias that already serves the stamp.
- Wrap the four revision governance scalars in `Annotated[..., GOVERNANCE_STAMP]`
  so enrolment is declared at the field.
- Replace the hand-written `REVISION_GOVERNANCE_FIELDS` frozenset with the
  derivation over the revision model, leaving the loader's placement refusal
  reading the same name and behaving identically.
- Add four proof tests: the set pinned to today's four fields, the loader's gate
  input pinned to the derived object itself, a marked field added by a subclass
  enrolling while an unmarked sibling stays out, and the marked/unmarked flip.

## Outcome

The hand-written set could catch a rename, because the names would stop
matching real fields, but not an addition. That asymmetry matters more than it
sounds, because this set is the sole input to the loader refusal that keeps a
governance stamp out of the section fragments; a fifth scalar forgotten there
would become declarable in any fragment file, and a fragment-declared value
merges and wins while the revision manifest still reads unstamped. That is the
laundering route the refusal was built to close.

The gap was reproduced end to end rather than argued. A fifth field carrying
nothing but the marker was added to the real revision model for the length of
one child process, first against the pre-change hand-written set:

```
REVISION_GOVERNANCE_FIELDS = ['engineered_by', 'review_status', 'reviewed_at', 'reviewed_by']
enrolled = False
LOADED CLEAN: the fragment-placed stamp merged silently
```

Then, with only the derivation swapped in and the field set untouched, the same
probe against the same fragment TOML:

```
REVISION_GOVERNANCE_FIELDS = ['countersigned_by', 'engineered_by', 'review_status', 'reviewed_at', 'reviewed_by']
REFUSED: revision governance field 'countersigned_by' must be declared in the
revision's revision.toml manifest, not in a per-section fragment; the stamp is a
claim about the whole revision and must be readable in one place
```

The probe restored the schema byte-for-byte in a `finally` and confirmed the
restore, so the fifth field exists in neither the tree nor the commit.

Governance-ness is not derivable from an annotation, which is why the marker is
declared rather than inferred: the stamp is free text, a closed enum and a date,
shapes that many non-governance fields on the same model share. The marker is
the smallest declaration that makes enrolment a property of the field instead of
a second list to remember.

The existing behaviour is unchanged for the original four. The parametrised
placement-refusal test runs over the derived set and still covers exactly those
four, and the whole stamp module reports `31 passed`. Across the stamp module
plus the directory-loader, cache-isolation and disk-cache-fingerprint modules the
figure is `83 passed in 128.87s`, and the shipped tree still compiles to
`modelos=73 revisions=90` with the derived set reading exactly the four scalars.

## Notes

The marker and the derivation live beside the review-status coercion alias
rather than next to the field set, because the marker has to exist before the
revision class body is evaluated and because that module is already the shared
home of the stamp's schema vocabulary.

One test pins the loader's gate input to the derived object by identity. Without
it the derivation could be perfectly correct and still inert, because a second
literal set re-declared in the loader would satisfy every other assertion in the
module.

A residual is worth naming: the end-to-end enrolment proof is an out-of-band
probe rather than a committed test, because proving it in-tree would require
either shipping a fifth field or patching the loader's module global, and the
project bars test doubles on this surface. The committed tests prove the two
halves separately -- the derivation captures a marked field added by a subclass,
and the loader reads that exact derived object -- which is the strongest form
available without either compromise.

One combined registry run reported a single failure in the disk-cache isolation
module, asserting a child process must not write a second cache pickle. It is
peer churn, not this surface. The cache key folds a content hash of every
registry-package source file, so any peer write to that tree between the
parent's key and the child's yields two keys and two pickles; a peer commit
touching the classification-coherence module landed inside the run window,
another registry commit landed two minutes after it, and the module passes
`11 passed` in isolation both before and after. The same run reported 3136
passed.

**Discovery waiver.** The mandatory semantic-discovery probe was explicitly
waived by the operator for this Step: the semantic index is broken and its
service stopped, with a standing instruction not to start, reindex or otherwise
touch it. Grounding was done with literal search plus whole-file reads of the
schema base module, the revision model, and the loader's fragment merge.

A peer has already built on this derivation, promoting the field set to the
registry package facade and retiring a second hand-written copy of it in the
dev-side stamp writer, which is the outcome the change was meant to enable.
