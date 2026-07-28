---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_schema: 'body-v1'
step_id: 'S212'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S212 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Record a zero-blocker and zero-major formal review verdict and ## Scope

- `.vault/audit/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Record a zero-blocker and zero-major formal review verdict

## Scope

- `.vault/audit/`

## Description

- Record the formal review verdict once its one major finding was actually
  resolved rather than argued down.
- State the review's depth alongside the verdict, so the verdict cannot be
  read as stronger than the review that produced it.

## Outcome

ZERO BLOCKERS AND ZERO OPEN MAJORS, recorded at a stated depth.

This row was deliberately held open earlier in the campaign and the reason is
worth keeping: a major-class finding stood, and recording a zero-major verdict
over it would have been the inferred green this campaign exists to remove. The
verdict is signable now because the finding was FIXED, not because it was
reclassified.

WHAT THE MAJOR WAS AND HOW IT CLOSED. The false-green class - a gate asserting
a property of a set it never proves is non-empty - was found systemic, with a
screening heuristic reporting 246 candidates tree-wide and 87 in-surface. Its
owning Step is now complete: roughly 17 genuine gates floored across the CLI,
entrypoints, core-tests and dev-audit surfaces, every one mutation-verified to
fail on a collapsed corpus, and the remainder read and excluded as
already-controlled with a stated mechanism each.

I verified four of those floors independently rather than accepting the report:
the CLI-module corpus helper at 456 modules failing at 0, the marker-integrity
live-opt-in scan failing at 0 on relocated roots, the combined-period gate's
corpus floor, and the final direct-translation gate failing at 0 on a relocated
`PROJECT_ROOT`.

THE FINDING GOT STRONGER BEFORE IT CLOSED, and the record should say so. I
classified the class as LATENT. That was wrong: it contained a gate already
lying at HEAD. The retired-command-phrase gate derived its repository root one
directory too shallow, so both runtime surfaces resolved to non-existent paths
and it scanned zero files while passing green. Fixing it also fixed the shape -
the replacement anchors on the canonical `PROJECT_ROOT` constant instead of
another positional `parents[N]` count, which is what made the original defect
possible.

ZERO BLOCKERS throughout. No safety, boundary-direction or intent finding rose
above minor at any point in the review.

THE DEPTH, stated because the verdict is only as strong as it. This was a
PERSONA-SWITCH review by the agent that drove the campaign, used after a
dispatched independent reviewer produced nothing across three idle signals and
two direct requests. The campaign's close discipline sanctions that form as one
of three, and it is the weakest of them. Test quality was reviewed with a
purpose-built instrument; safety, boundary direction and intent were confirmed
against measurements taken earlier in the campaign rather than re-derived. A
genuinely independent pass over those three axes is still worth having and is
recommended in the audit.

Gates at HEAD `65da23cf3f801f03e3ce4c502d28515f8d547194`:

- Owning Step for the major finding: closed, with its own command, corpus
  figures, exit line and HEAD.
- Independent mutation of the final floor: `scanned only 0 modules under
  src/cadrumo; the scan corpus collapsed`.
- Locale suite plus direct-translation gate: `64 passed in 93.43s`.

## Notes

The honest reading of this verdict: zero blockers and zero open majors AT THE
DEPTH REACHED, not zero defects in the surface. Two residues named elsewhere
remain and are not review findings - the semantic sweep is unperformed and its
row is held open, and six keychain-marked custody cases have never been observed
green under an agent logon.

One number belongs here because it will mislead whoever re-runs the screening
tool. Roughly 17 genuine gates against roughly 90 excluded is a false-positive
rate near ninety percent. The original "87 in-surface candidates" was never 87
defects, and the exclusion reasoning - fixtures over an already-floored shared
inventory, self-flooring symmetric comparisons, detector controls over synthetic
input, fixed-path reads that raise loudly - is the durable output of that work
rather than the floors themselves.
