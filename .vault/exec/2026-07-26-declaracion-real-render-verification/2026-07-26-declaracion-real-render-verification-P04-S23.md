---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S23'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace declaracion-real-render-verification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S23 and 2026-07-26-declaracion-real-render-verification-plan placeholders are machine-filled by
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
     The Find a size-aware mechanism that leaves the ledger evidence path byte-identical, or scope it to the declaracion entry point instead of the shared primitive and ## Scope

- `src/cadrumo/adapters/inbound/pdf`
- `src/cadrumo/adapters/inbound/declaracion` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Find a size-aware mechanism that leaves the ledger evidence path byte-identical, or scope it to the declaracion entry point instead of the shared primitive

## Scope

- `src/cadrumo/adapters/inbound/pdf`
- `src/cadrumo/adapters/inbound/declaracion`

## Description

- Evaluate candidate mechanisms that recover Modelo 100's amounts without changing the ledger evidence text.
- Test the capture-time split first, since it would have cost nothing.
- Establish whether the shared primitive must change at all.

## Outcome

A mechanism exists, and the reason it exists is a structural fact nobody had established: declaracion has two independent extraction axes.

The shared inbound-PDF primitive backs only the text-string functions, which are the ones the ledger evidence layer and the borrador adapter call. The word-extraction functions call pdfplumber directly inside the parser, never through the shared module, and are in neither consumer's import graph. So the isolated pathway already exists and runs in production; it simply does not request the size attribute. That makes the two candidates I had framed as alternatives the same mechanism.

The chosen shape is to request size on word extraction, have named_label capture consult that word data for amount-kind targets, and apply the trailing-box-number rule there. Text assembly never changes, so the two other consumers are untouched by construction rather than by measurement.

The capture-time split, which I proposed as most attractive because it changes no extraction at all, is refuted. It assumed the merged text was the amount followed by the box number. Casilla 0545 extracts as 1.001.0000,50405 rather than 1.001.000,000545: the box number's bounding box sits inside the amount's span, so the digits interleave by x-position and the correct amount is not a substring at any position. No string rule recovers it. The trailing-box-number rule only becomes applicable once the runs are separated, which is what the size attribute does.

Rebuilding line assembly from words was evaluated and rejected as dominated: it shares the isolation but reintroduces the reading-order problem that broke the ledger text, relocated to a wider surface.

## Notes

One risk is narrowed and explicitly not cleared. The same word-extraction function backs bbox_anchored, which carries the currently-passing real-render gate for three modelos, and adding the size attribute does change its returned word lists. A direct probe found every box-number-pattern match on all three returning identical text and coordinates, with only ordering differing where there were two hits. That is evidence the risk is narrow and it is not the same as re-running the committed gate, which the probe could not reach. Re-running it is the precondition for landing and is tracked separately.

The ledger corpus n=1 figure was reaffirmed by checking fixture producers directly rather than by repeating the corrected number, which is the right way to carry a correction forward.

The semantic code index remained truncated throughout.
