---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S71'
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
     The S71 and 2026-07-27-conformance-cli-plan placeholders are machine-filled by
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
     The restate the two test docstrings that cite this project development records as self-contained engineering reasoning and move the discovery-waiver process note out of source, honouring the one-way rule that code never cites the vault and ## Scope

- `dev/tests/test_registry_conformance_gate.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# restate the two test docstrings that cite this project development records as self-contained engineering reasoning and move the discovery-waiver process note out of source, honouring the one-way rule that code never cites the vault

## Scope

- `dev/tests/test_registry_conformance_gate.py`

## Description

- Sweep both conformance test modules for citations of development records.
- Restate the two-proofs mandate as the reasoning it rests on.
- Delete the discovery-waiver process note from source.
- Restate the reviewer-convention, decision-path, and step-id citations.
- Re-run both modules serially.

## Outcome

Five citations removed, three named in the finding and two more the sweep
surfaced. The finding named a plan document cited for the two-proofs mandate, a
reference to exec records as the authority for a reviewer-name convention, and
the discovery-waiver note. The sweep added a decision record referred to as
"the governing decision", and a bare plan step id standing as a whole test's
subject line — the clearest instance of the whole class, since a reader with no
access to the plan learns nothing from it.

Each was restated rather than deleted, except the waiver. The two-proofs claim
is durable and worth keeping, so it now argues from what a green run cannot
distinguish: a broken invocation, a swallowed exit code, and a baseline
comparison reading nothing all produce the same passing result, and only a
seeded failure separates them. That is a stronger docstring than the citation
was, because it tells a reader why the second test exists instead of telling
them a document said so.

The reviewer-convention line now explains that a role-qualified identity is how
an automated reviewer names itself and that its colon is a role prefix rather
than a status one, which is the fact the assertion actually depends on. The
step-id subject line was replaced by what the test uniquely proves — the
command's own parsing and error translation, unreachable until the verb accepted
a registry root, because without one it could only have written a fabricated
review into the shipped registry.

Both modules pass serially, 74 and 2. The change is docstring-only, so the
value of running them is confirming no docstring is load-bearing for a
doctest or an assertion that matches on text.

## Notes

The discovery-waiver note is recorded here, which is where it belonged: the
conformance gate module was authored while the semantic search service was
unavailable, with grounding done by targeted search and whole-file reads
instead. Source is the wrong home for that fact — it describes the conditions
one author worked under, not anything a later reader of the module needs.

The two citations the finding did not name are the argument for sweeping rather
than patching the reported sites. Both were in the module the finding already
identified, and one of them was a plan step id, which is the least ambiguous
form of the violation.
