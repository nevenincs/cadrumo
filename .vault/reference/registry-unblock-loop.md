# REGISTRY UNBLOCK LOOP v1 — clear the filing worklist, one blocker at a time

Supersedes REGISTRY LOOP v7. v7 is retired: it told you to author casilla sets on the
premise that a casilla set is the prerequisite for an export layout. **That premise is
false for most of the worklist.** Two days were spent adding casillas to modelo 220, whose
gate has been printing, on every run, that it is blocked on *producer vocabulary* — not
casillas. Do not resume it.

## MEASURED STATE — 2026-08-23

- **88 of 102 revisions already carry an export layout.** The application can file them.
- **14 cannot.** They are the whole of the remaining work on this axis.
- **The generator already exists and is in production use.** `dev/registry/pipeline/`
  renders, validates, publishes and checks generated `export/` trees from three authored
  authorities: a **semantic map**, a **render profile**, and the **parsed record design**.
  17 modelos have render profiles. **Never hand-author an export layout.**
- Layouts are near-identical year to year — modelo 390 2023→2024 differs on 90 of 332
  lines and every difference is the year token. Anything you find yourself copying by hand
  is a generator input you have not located yet.

## THE GATE IS THE INSTRUCTION — READ ITS TEXT, NOT ITS COUNT

```
uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py \
  -p no:randomly -n0 -q --no-header -p no:logging
```

It prints one line per blocked revision **naming exactly what that revision waits on**. It
calls itself "the capability worklist, not a defect to suppress". Treating it as a number
to diff against a baseline is what wasted two days. **Start every iteration by reading
these lines.**

The six blocker classes, as the gate states them:

| Class | Revisions | What actually unblocks it |
|---|---|---|
| producer vocabulary | 036, 220/2024, 840 | a semantic map + `mNNN.` `FilingProducerKey` members, then generate |
| design covers wrong years | 182, 187, 188, 194, 763, 220/2025 | acquire the older design, or split the revision by era |
| no design published | 136, 721 | acquisition — record and move on, do not spend iterations |
| design bundled but not cited | 185 | possibly a citation only; **185 already has a render profile** |
| bundled artefact is a diagram | 038 | re-acquire; no parser repair helps |
| casilla surface too thin | 390/2021 | author casillas; **390 already has a render profile** |

**Start with 185 and 390** — their render profile, the expensive input, already exists.

## EACH ITERATION

1. **Re-measure.** Run the worklist gate and read every line. Peers are working; a line may
   have cleared or changed class.
2. **Pick ONE entry** — the cheapest still-actionable one. Prefer an entry whose render
   profile exists. Skip the acquisition-blocked pair.
3. **Dispatch two subagents, at most two, in one message so they run concurrently:**
   - **WRITER** — executes the unblock on the chosen entry, end to end. Sole writer.
   - **SCOUT** — *read-only*. Investigates the **next** entry and returns: what its missing
     inputs concretely are, which already exist, and the cheapest first step. Its findings
     go in the audit so the following iteration starts warm.

   One writer and one reader cannot collide. **Never run two writers.**
4. **Verify what the writer claims** against the tree yourself. Sub-agent output is
   inventory, not gospel.
5. **Re-run the worklist gate.** The iteration succeeded only if a line is **gone**, or the
   entry is proven acquisition-blocked and recorded as such.
6. **Record** in `.vault/audit/2026-08-20-registry-temporal-coverage-casilla-provenance-and-review-blockers-audit`.

## PROGRESS IS WORKLIST LINES CLEARED — NOTHING ELSE

Not casillas authored, not commits, not "identical FAILED list". An iteration that adds
data without removing a line **did not advance**, and must say so plainly. If an iteration
cannot honestly advance, say so and stop rather than manufacture work.

## LESSONS ALREADY PAID FOR — do not re-buy

1. **Never fabricate** an offset, casilla number, rate, deadline, or stamp. A casilla
   number is TRANSCRIBED from the design, never minted and never corrected — modelo 220's
   `[000304]` is printed with an extra zero and ships exactly as printed.
2. **A slow suite run is evidence about the run, not the code.** One returned 558 failures
   in 1h50m against a normal 20–28 min; the three largest failing modules passed
   individually and the re-run gave 8. Confirm by re-running one failing module before
   believing any failure list.
3. **Do not measure a catalogue by grepping its serialised form.** Locale YAML wraps long
   values; a grep that misses across the fold produced a false claim that went into a
   stamp. Query the loaded authority.
4. **Do not pass source or legal text through a shell heredoc.** It ate escaped newlines
   three times and once put a refuted claim into a shipped fragment.
5. **Commit early, by explicit pathspec.** A peer commits continuously and will capture
   your work; a pathspec commit also consumes *their* uncommitted edits to the named files,
   which has already happened. Put the real claims inside the artefact, not the commit
   message.
6. **Wait out a peer's in-flight merge or lock.** Never resolve another hand's conflict.
7. **A gate's silence is not evidence of absence**, and neither is your own — a confident
   conclusion drawn from the wrong instrument is worse than no conclusion.

## STAMPING

Only via `python -m dev.registry.conformance stamp <modelo> <revision> --bundled-registry
--review-status agent_reviewed --reviewed-by "..."`. `operator_reviewed` is refused by
design. State what is NOT claimed. Never stamp to make a test pass. Adding an export layout
raises the revision's derived authority scope from `inspection_only` to `filing` — re-stamp
when that happens, or the old stamp silently over-claims.
