# REGISTRY LOOP v3 — make the registry GREEN and WHOLE

GOAL, set by the operator: **the registry is green (every gate passes) and whole (every
revision is complete enough to file what it claims).** Nothing else is progress.

## WHAT IS ACTUALLY BROKEN — measured, not assumed

**395 producer keys across 7 modelos were cited by shipped export layouts and resolved by
nothing.** They are `required = false`, so `_header_field_value` returns `None` and the
field renders BLANK instead of refusing. Those returns file with their identifying headers
empty and every gate stays green.

Modelo 222 is FIXED (commit 198ae6d001) and is the worked pattern:
1. a typed `ModeloNNNProfileFacts` in `application/filing/_producer_snapshot.py`
2. added to the `FilingModelProfileFacts` union
3. a snapshot validator dispatched from `_validate_snapshot_model_profile`
4. an `mNNN_producer_values()` resolver in `_export_producer.py`
5. its keys moved into the `shared` set in `filing_producer_ownership()`

**Remaining, in size order: m200 (132), m296 (112), m210 (104), m202 (18), m353 (5),
m232 (1).** The gate is
`src/cadrumo/application/filing/tests/test_export_producer_resolution.py` and it names them
on every run. Run it with `-m integration`.

## DISCOVERY: USE vaultspec-rag, NOT BLIND GREP

`uvx vaultspec-rag search "<behaviour> <domain nouns>" --type code` finds by meaning.
`--type vault --doc-type adr` finds the governing decision. If the service is down, start it
with `uvx vaultspec-rag server start`; it needs the GPU torch wheel. Lead with rag, read the
epicenter file whole, confirm exact symbols with grep.

## EACH FIRE

1. Run the producer-resolution gate. It names the next target and its exact keys.
2. `git log -3 --date=format:"%H:%M" -- <path>` first. Four sessions share this tree; a
   modelo a peer touched within the hour is off-limits to a writer.
3. Dispatch at most TWO subagents in one message: one WRITER, one read-only SCOUT. Never two
   writers. With no writer target, dispatch two scouts and verify something yourself.
4. Verify every writer claim against the tree yourself.
5. Before committing a fix, run the OWNING test directory and compare against the same run
   with your change stashed. Identical failures = pre-existing, not yours. 63 failures in
   `application/filing/tests/` are pre-existing as of 198ae6d001.
6. Commit by explicit pathspec, early.

## NEVER

- Write audit prose. The vault holds 180,865 lines across 1,330 files and it fixed nothing.
  A finding is recorded by FIXING it, or in one line of the commit message.
- Hand-author an export layout. `dev/registry/pipeline/` generates them.
- Fabricate an offset, casilla number, stamp, or a claim about AEAT.
- Treat an unpublished future design as a blocker. The worklist horizon is 2026, so every
  annual return published in arrears shows a phantom uncovered year.
- Trust a zero from a parser. The export TOML uses SINGLE quotes; a double-quote regex
  returns zero and every assertion passes vacuously. Measure the loaded authority, not the
  serialised form.
- Believe a slow suite. One returned 558 failures in 1h50m against a normal 20-28 min; the
  three largest failing modules passed individually.
