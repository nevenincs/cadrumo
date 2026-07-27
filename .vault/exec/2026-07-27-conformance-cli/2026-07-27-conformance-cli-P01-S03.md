---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S03'
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
     The S03 and 2026-07-27-conformance-cli-plan placeholders are machine-filled by
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
     The hydrate the governance scalars from revision.toml in the TOML compiler, rejecting unknown or misplaced governance keys loudly and ## Scope

- `src/cadrumo/domain/calculations/registry/_loader.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# hydrate the governance scalars from revision.toml in the TOML compiler, rejecting unknown or misplaced governance keys loudly

## Scope

- `src/cadrumo/domain/calculations/registry/_loader.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Probe the real loader first to establish which parts of this Step were already satisfied and which were genuinely missing.
- Declare the governance field set once in the schema module beside the field declarations, so a rename is caught at a single site.
- Refuse the four governance keys inside a per-section revision fragment, naming the revision manifest as their only legal home.
- Document the manifest-only invariant in both directions on the manifest merge helper.

## Outcome

The governance stamp now hydrates from a revision manifest and cannot be
declared anywhere else in the fragment tree.

Modified files: `src/cadrumo/domain/calculations/registry/_loader.py`,
`src/cadrumo/domain/calculations/registry/_schema.py`.

This Step was smaller than its row implied, and the honest account matters more
than the line count. Three of the four things the row asks for were already
true before any edit, which a probe against the real loader established rather
than a reading of the code:

- Hydration needed no loader change. The revision manifest merge already copies
  every scalar key generically, and the section-vs-scalar classification is
  derived from the schema field annotations, so a newly added scalar is
  classified as non-section automatically. A manifest carrying the full stamp
  loaded and produced the operator-reviewed status, the engineer, the reviewer,
  and the date.
- Rejecting an unknown key needed no loader change. Registry models are strict
  and forbid extra keys, so a mistyped `reviewed_bye` already failed the load
  naming the field.
- Rejecting an unknown status token needed no loader change either; the
  coercion alias added in the previous Step raises out of the enum constructor
  and the loader reports it against the revision.

The one genuine gap was placement. A governance stamp declared inside a
per-section fragment merged silently and won. That is not cosmetic: the stamp
is an authorship and signoff claim, and roughly 15,900 fragment files exist
across the tree, so a stamp hidden in one of them would show a reviewer reading
`revision.toml` an unstamped revision while the loaded snapshot claimed
operator signoff. That is a laundering vector aimed at exactly the unreviewed
backlog this feature exists to make visible, so it is the part that got the
work.

The refusal is scoped to the governance fields rather than generalised to all
scalars. A tree-wide parse of every fragment file showed that one bundled
revision legitimately declares a non-governance scalar in a fragment
subdirectory today, so a blanket scalar ban would have broken a real revision
and pulled unrelated remediation into this Step. Scoping to the stamp is also
the correct posture on its own terms: the stamp is being born now, so it can be
declared manifest-only from birth with no legacy shape to accommodate.

The field set is not promoted to the registry package facade yet. Its only
consumer today is the loader, which is intra-package; the later stamp-writing
verb is the first cross-package consumer, and promotion belongs with that
change rather than ahead of it.

Verification. `ruff format` reported both files unchanged, `ruff check` reported
`All checks passed!`, and `ty check` reported `All checks passed!`. The probe
was run before and after the edit against the real directory loader. Before:
a stamp misplaced into a casillas fragment was accepted and produced an
operator-reviewed revision. After: each of the four governance fields is
refused from a fragment with an error naming the offending file and field,
while a manifest-declared stamp still loads and a non-governance scalar still
merges from a fragment unchanged. Reloading the real bundled tree returned
`modelos 73 revisions 90 {'pending_review': 90}`. The scoped suites ran with an
explicit empty marker selector, because the repo default under-collects here:
`171 passed in 34.85s` across the directory-mode loader, directory-fragment
loader, schema, schema hygiene, registry schema parts one and two, and
authority modules.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Semantic discovery ran under an explicit operator waiver, with `rg` concept
sweeps and whole-file reads standing in for the stopped code index.

One measurement in this Step was initially wrong and is worth recording. The
first sweep for scalar leakage into fragment files used a line-anchored pattern
match and reported thousands of hits for `legal_refs`, `source_refs`, and
`label`. Those were nested keys belonging to individual casilla and parameter
entries inside array-of-tables blocks, not revision-level keys; a text pattern
cannot tell the two apart. Re-running the sweep by actually parsing each
fragment and reading the revision table's own keys gave the true answer: one
non-governance scalar in one revision, and no governance keys anywhere. The
scoping decision above rests on the parsed result, not the pattern match.
