---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:a1e75ac7e4a60babfd2c86a1c56cb925dcfc8ce2cc3c790b92a98b4fd1d20971'
step_id: 'S316'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Sweep the remaining stale outbound LLM cross-references by asking the live module whether each named symbol is exported, never by matching the reference string, since more than a third of the population is valid

## Scope

- `src/cadrumo/llm`

## Description

- Re-derive the population at HEAD before executing, since the row's premise was authored earlier and this tree moves.
- Drive substitution per symbol from each package's export list, never from the reference string.
- Split the work so the judgement sites and the mechanical remainder do not race on one file.
- Take the residue the carve-out created rather than reporting it as a shortfall.

## Outcome

**The stale population is closed: 118 references repointed, 0 remaining, and 86 correct references left untouched.**

The instrument is the whole result. More than a third of the references were already correct, because the two packages export different symbols and both are cited through the same path prefix. **A sweep keyed on the prefix would have rewritten every correct reference alongside every stale one.** Substitution was therefore driven by membership in each package's export list, symbol by symbol, which is the same instrument the census used.

**The final three files are the clearest demonstration.** They carried stale and valid references together, so the file was neither wholly in nor wholly out of scope. Five correct references sat beside fifteen stale ones in the same docstrings.

**Nothing was promoted.** The symbols moved to a sibling package; promoting them back onto the original facade would have recreated two homes for the client class and undone the split that produced this drift.

## Verification

    valid as written        86   unchanged
    stale remaining          0
    unresolvable             0

Re-measured at HEAD after the final commit, by the same membership check.

## Notes

**The residue was a carve-out, not a gap.** Three files were excluded from the mechanical pass because uncommitted judgement-site work was live in exactly those files; the mechanical share went out with it and was taken afterwards. Naming that is the difference between a measurement and an excuse.

**One counting trap worth carrying.** A rewriter that skips selectively cannot report its own count from the regular-expression engine: the substitution helper counts matches, including the ones the callback deliberately left alone. The commit statistics are the honest instrument.

**Unverified, and it is the only outstanding risk on this row.** No documentation build was run, so that the repointed anchors resolve under the strict build is unproven by anyone. A convention matching the already-landed commits is a consistency argument, not a resolution proof, and anchor resolution is the entire point of the change.
