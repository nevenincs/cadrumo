---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:95731f4b4e500921e6e37764fbc97c9919d034c983c2098faf9258e52fc2d30c'
step_id: 'S319'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace unstructured-document-ingestion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S319 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Establish whether the integration lane is executed by any blocking check and plan against the population rather than the known-failure count, since that count is a floor over modules that have never been executed and ## Scope

- `dev/ci` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Establish whether the integration lane is executed by any blocking check and plan against the population rather than the known-failure count, since that count is a floor over modules that have never been executed

## Scope

- `dev/ci`

## Description

- Answer the question the row asks and nothing more: is the lane executed by a blocking check.
- Read the workflow rather than infer from the local configuration, because the two can differ.
- Record the population, not the known-failure count, as the thing to plan against.

## Outcome

**The lane is executed and it blocks nothing.** The workflow step that runs it is marked to continue on error, alongside three sibling steps carrying the same marking. Its own comment records the history: for a long period no lane selected the integration marker over the application source at all, holding several hundred modules out of continuous integration entirely, and the step that now exists was added non-blocking behind a triaged backlog.

**So a gate living in that lane detects a defect and fails nothing.** That is the condition this campaign found the hard way: a defect shipped past a gate that already owned the property and was red for the defect's entire lifetime.

**And the known-failure count is a floor, not a measure.** An audit of the test authority's own run history found four runs carrying the integration selector and none selecting the module in question. The gate was never triaged and never deferred; nothing ever asked for it. **A backlog counted over a population that has never been executed states what someone found, not what exists.**

## Verification

    lane executed by a blocking check      no
    steps marked continue-on-error          4
    modules carrying the integration mark   several hundred

The count of marked modules is a property of the tree at the time of reading and will drift; the blocking status is the answer the row asked for.

## Notes

**The remedy splits in two and only one half has a workflow answer.** Making the lane blocking fixes continuous integration. It does not fix that nobody asks for these — the lane is unwatched by request as well as unenforced, and the standing coverage probe over that population is a collection pass that executes none of it.

**A per-file remedy exists and is narrower than it first appears.** One module in that lane was moved into the default lane on a convention argument: it is a source-tree syntax scan with no fixture, subprocess or network dependency, and five sibling scans of the same kind already carry the default marker. **That does not generalise to the whole population** — most of those modules presumably do need the lane — but it establishes that the population contains outliers movable without a policy decision, which makes the remaining set smaller and better justified.

**Not planned here.** Sizing the enforcement change is a cost decision that belongs with whoever owns the lane.

