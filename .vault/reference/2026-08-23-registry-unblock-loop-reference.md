---
related: []
date: '2026-08-23'
modified: '2026-08-25'
body_hash: 'sha256:60c4778ed13ca383e6b9af18abf36fefcd49a91d3024b090b086716208894a1f'
tags:
  - '#reference'
  - '#registry-completeness-closure'
---
# REGISTRY UNBLOCK LOOP v2 — make the application file what it claims to file

Supersedes v1 and the retired REGISTRY LOOP v7.

**v7 was wrong about the goal.** It told you to author casilla sets because "a casilla set is
the prerequisite for an export layout". Of 14 blocked revisions exactly ONE waits on
casillas. Two days went into modelo 220, whose gate prints on every run that it waits on
*producer vocabulary*. Do not resume it.

**v1 was too narrow.** It aimed only at the filing worklist. That worklist has ~1 actionable
calculating-form line and peers hold it, so fires idled — and the idle fires, spent on
read-only investigation instead, produced the single most valuable finding of the campaign.
That is now the design, not the accident.

## THE GOAL

Not "clear the worklist". **Make the application actually file what it already claims to
file, and unblock what it cannot.** Those are two queues and the first outranks the second,
because a modelo that passes every gate and emits a wrong return is worse than one that
honestly refuses.

## MEASURED STATE — 2026-08-23

- **88 of 102 revisions carry an export layout**; 14 do not. Registry-wide: 80,163 casillas
  across 58 modelos, no revision empty.
- **The generator is real and in production**: `dev/registry/pipeline/` renders, validates,
  publishes and checks export trees for 17 modelos. **Never hand-author a layout.**
- Its three authored inputs are a **semantic map** (`dev/registry/mappings/`), a **render
  profile** (`dev/registry/render_profiles/`, "AUTHORED evidence, not generator output"),
  and the parsed design. **No tool scaffolds either.** The campaign's own unit of work is
  400–650 anchors per (modelo, epoch) Step, and the m303/m390 Steps have been open since
  2026-08-10. Modelo 220's design is 16,079 fields — 25–40× one of those Steps.
- **A confirmed defect in shipped code**: modelo 222 renders 23 header fields blank because
  nothing resolves its `m222.*` producer keys and they are `required = false`. It files with
  the fiscal group number and parent entity empty, every gate green. See the audit entry.

## QUEUE ORDER — recompute every fire, take the first that is dispatchable

1. **Shipped defects — things that pass every gate and are still wrong.** Highest value,
   because no gate will ever surface them. The m222 finding is the worked example. The open
   one: **do the other namespaced modelos resolve their producer keys, or do m111, m200,
   m202, m296, m353, m360 have the same hole?** That sweep is undone.
2. **Worklist lines that are actionable AND unowned.** Calculating forms first — this is a
   tax calculation project. 136 and 721 have no published design: dropped, never work them.
   Informative and registration forms (036, 038, 182, 185, 187, 188, 194, 763, 840) wait.
3. **Verification that could expose more of (1).** Never idle.

## AN UNPUBLISHED FUTURE DESIGN IS NOT A BLOCKER

`_OPEN_ENDED_HORIZON = 2026` makes every open-ended revision claim 2026, so any annual
return whose design AEAT publishes IN ARREARS shows a permanent phantom uncovered year.
Modelo 220's ejercicio 2026 is filed in July 2027. That line cannot clear; nobody should
try. Real past gaps: 182 (2007–2023), 187 (2019–2021), 188 (2019–2022), 194 (2019–2022),
763 (2011). Artefact: 220/2025. Take the horizon question to that gate's owner.

## EACH FIRE

1. **Re-measure.** Read the worklist gate's TEXT, never diff its count. It names what each
   revision waits on and calls itself "the capability worklist, not a defect to suppress".
2. **Check peer ownership before choosing.** Four sessions share this tree.
   `git log -3 --format="%h %ad %s" --date=format:"%H:%M" -- <path>`. **A modelo touched by
   a peer within the hour is off-limits to a writer.** Learned by dispatching one at modelo
   390 forty minutes after a peer merged a branch into it.
3. **Dispatch at most two subagents, in one message: one WRITER, one read-only SCOUT.**
   Never two writers — one writer and one reader cannot collide.
   **If no writer target is dispatchable, dispatch two scouts and do queue item 3 yourself.
   A fire with nothing to write is a fire for finding what nobody knows is broken.**
4. **Verify every writer claim against the tree yourself.** Sub-agent output is inventory.
   Check the actual file, the actual count, the actual commit.
5. **Report honestly.** Progress is a worklist line cleared or a shipped defect proven. A
   fire that added data without either **did not advance** and must say so.
6. **DO NOT WRITE AUDIT PROSE.** The vault holds 180,865 lines of it across 1,330 files and
   it fixed nothing. A finding is recorded by FIXING IT, or by one line in the commit
   message of the fix. If you cannot fix it, say it in chat and move on. Never open a new
   audit document.

## LESSONS ALREADY PAID FOR

1. **Never fabricate** an offset, casilla number, rate, deadline or stamp — nor a claim
   *about* AEAT. A note saying "AEAT does something odd here" carries the same burden as a
   number; one was drafted from the shape of an anomaly and the design refuted it. A casilla
   number is TRANSCRIBED, never minted and never corrected.
2. **A slow suite run is evidence about the run, not the code.** One returned 558 failures
   in 1h50m against a normal 20–28 min; the three largest failing modules passed
   individually and the re-run gave 8. Re-run one failing module before believing any list.
3. **Measure the loaded authority, not the serialised form.** Grepping line-wrapped locale
   YAML produced a false claim that reached a stamp. A stale loader cache produced another.
   When the finding is "someone changed my work", check the bytes before acting.
4. **Check the quoting before trusting a parse.** Three consecutive measurements of modelo
   222 returned zero because the TOML uses single quotes and the regex wanted double. A
   zero from a parser is a claim about the parser until proven otherwise.
5. **Do not pass source or legal text through a shell heredoc.** It ate escaped newlines
   three times and once put a refuted claim into a shipped fragment.
6. **Commit early, by explicit pathspec.** A peer will capture uncommitted work; a pathspec
   commit also consumes *their* uncommitted edits to the named files, which has happened.
   Put the real claims inside the artefact — the commit message does not survive.
7. **Wait out a peer's merge or index lock.** Never resolve another hand's conflict.
8. **Report a per-modelo number as a per-modelo number.** "9791 remain" was quoted for
   weeks as if it were the project's state; it was one revision of the largest modelo, over
   a denominator (11,603 `(record, number)` pairs) that double-counts the 2,663 box numbers
   AEAT prints on more than one sheet.

## STAMPING

Only via `python -m dev.registry.conformance stamp <modelo> <revision> --bundled-registry
--review-status agent_reviewed --reviewed-by "..."`. `operator_reviewed` is refused by
design. State what is NOT claimed. Never stamp to make a test pass. A new export layout
raises the revision's scope from `inspection_only` to `filing` — re-stamp, or the old stamp
over-claims.
