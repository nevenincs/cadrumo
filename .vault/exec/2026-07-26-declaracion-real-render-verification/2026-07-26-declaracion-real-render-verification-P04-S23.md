---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:095d3f91f645c315debcbc7376f7b6217b5476c5367637db87fa1a84f9c1a988'
step_id: 'S23'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

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
