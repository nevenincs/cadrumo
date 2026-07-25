---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S16'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Regenerate and update every documentation surface for the new grammar (user docs via the documentation workflow, generated API stubs via python -m dev.docs.apidocs scaffold, docs sequences naming switch or profile logout), verified by scaffold --check clean, the Sphinx nitpicky build gate, and documented-command conformance green

## Scope

- `docs/`
- `dev/docs`

## Description

- Regenerate the terminology coverage report through its owning CLI so the corpus measures the live command surface rather than the retired one.
- Confirm the English how-to prose, the re-recorded sequence goldens, the twelve translated catalogues, and the sixty-four locale leaves landed across the peer lanes that owned them.
- Verify at the committed tree, by PARSING each format rather than scanning lines, that no retired verb survives in the documentation set, the four locale catalogues, the operator agent harness, or the terminology report.

## Outcome

Zero occurrences of either retired verb remain in the documentation tree, the operator harness, the four locale catalogues, or the terminology report, measured at the committed tree.

The verification parses each format instead of scanning text: the catalogues are loaded as YAML and every leaf string re-joined, the report is loaded as JSON, and adjacent quoted chunks in the translated catalogues are concatenated before matching. A line-oriented scan undercounts all three formats, because a long value wraps and splits the phrase being searched for across physical lines.

## Notes

The line-scan hazard is the reason this verification is worth its cost rather than a formality. A line-oriented count had previously reported a documentation surface clean, and a parse of the same surface then found a stale key the scan had split in half and missed. Every check recorded here is therefore parse-based, and the translated catalogues additionally have their continuation chunks joined, since a wrapped entry can break a phrase at an arbitrary character.

The bulk of this work was carried by peer lanes that owned the surfaces: the English prose and sequence goldens, the translated catalogues, and the locale leaves each landed under their own owner. Only the terminology report was regenerated here. This record closes the step against verified evidence rather than claiming the authorship.
