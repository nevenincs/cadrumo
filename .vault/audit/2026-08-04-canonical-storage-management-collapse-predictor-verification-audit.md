---
tags:
  - '#audit'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:c004484aa557d0820be17d974297ecae585548f44076ecf4870baa5a6f934743'
related:
  - "[[2026-08-04-canonical-storage-management-pre-close-inherited-review-audit]]"
  - "[[2026-08-03-canonical-storage-management-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace canonical-storage-management with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `canonical-storage-management` audit: `collapse predictor verification`

## Scope

The pre-close inherited review left the `S78` collapse predictor unverified and
flagged it as currently shaping unassigned band assignments (`live`, `runs`,
`financial`, and a residual tail). The recommendation was explicit: pick one band,
state the predicted split in advance, classify a sample, and report the actual
split even if it refutes the prediction. This document is that verification pass,
run against `drafts` (`StorageCategory.DRAFTS`), a band from the residual tail
that had not yet been touched by the predictor or by any classification commit.

## Findings

### drafts-confirms-the-refined-predictor-and-falsifies-the-naive-one | medium | A real homonym that does not collapse the path-composition count, exactly as the refined rule predicts

**Prediction, stated before reading a single site:** `drafts` is a real taxonomy
segment (`StorageCategory.DRAFTS`, consumer `_rotation.py`, the offline export
directory) with no known different-namespace fixture-tree collision, and the
codebase's domain vocabulary uses the Spanish stem `borrador` for the
taxpayer-facing draft-filing concept rather than the English word — so I predicted
LOW collapse, most of the roughly 14 hits genuine.

**Measured.** A `"drafts"` grep across `src/cadrumo` returns 23 raw string-literal
occurrences. Filtering to the AST-scan definition task `S78`'s tail already
established — a string constant that is a `/` operand or a joinpath/glob
argument, not a raw substring — leaves 15 sites, and every one of the 15 is
`tmp_path / "drafts"` (or the equivalent `cadrumo_drafts_dir=tmp_path / "drafts"`
keyword form) feeding the real `cadrumo_drafts_dir` settings field. **All 15 are
genuine: zero different-namespace path-composition collapse.** The excluded eight
are a set/tuple membership literal (twice), a dict value mapping a settings-field
name to its subpath segment, an enum-value assignment (`DRAFTS = "drafts"`), the
taxonomy's own `subpath=` declaration, and a dict-subscript assertion — none of
them a `/`-joined path.

**The sharper result: `drafts` DOES have a real, unrelated second referent, and it
still does not collapse.** `adapters/persistence/profile/filing_drafts.py` is a
SQL-backed `SecureBoundRepository` for `ModeloDraft` records — an entirely
different persistence mechanism from the `StorageCategory.DRAFTS` filesystem
export directory, the same declared-location-with-SQL-persistence shape recorded
elsewhere for this campaign. Its namespace is
`"cadrumo.domain.filing.drafts"` — the word `drafts` genuinely names something
else in the codebase, which is exactly the naive predictor's trigger condition
("does the word name something else") and would have predicted collapse. It does
not collapse, because that second referent is a dot-separated SQL namespace
string, never a `/`-joined filesystem path segment. This is the identical shape
the `secrets`-stdlib-module case established for the refined predictor: a genuine
homonym only collapses the path-composition count when the OTHER referent is
itself expressed as a quoted path segment for a different tree, not merely when
the word means something else in prose or in a non-path string.

**My own prediction's rationale was incomplete, corrected here rather than left
standing.** I reasoned from "no known collision" and had not yet found the
`ModeloDraft` SQL-persistence homonym when I stated the prediction; the directional
call (low collapse) held, but the stated reason undersold the actual case. The
refined predictor's precision, not merely the naive one's absence of a hit, is
what makes the prediction survive contact with a real homonym.

## Recommendations

Treat this as one falsifying test of the naive predictor and one confirming test
of the refined predictor, not as a closed verification of either — a single band
is a sample of one, and the sharpest remaining test (per the prior review) is
still `financial`, whose own classification commit did not record an advance
prediction. Whoever sizes the next unassigned band should keep stating the
prediction before reading source, the way this pass did, so the predictor
accumulates falsifiable evidence rather than post-hoc rationalisation.

Do not fold `drafts` into any pending literal-corpus fix Step on the strength of
this finding: every one of its 15 genuine path-composition sites already resolves
through the real `cadrumo_drafts_dir` settings field — there is nothing to
migrate, rename, or pin here. This document records predictor evidence, not a
remaining `S78` band assignment.
