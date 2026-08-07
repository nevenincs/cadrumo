---
name: aeat-rag-discovery-mandatory
trigger: always_on
---

# Semantic discovery precedes coding work; a down RAG service refuses the work

## Rule

Run `vaultspec-rag` semantic search BEFORE any coding work — before writing a
new symbol, module, resolver, prompter, writer, service, or test, and before
"fixing" a site you have not first searched for by MEANING:

```
uv run --no-sync vaultspec-rag search "<natural-language concept>" --type code --port 8766 --timeout 120
```

(`--type vault` for the decision corpus.) Semantic results are DISCOVERY INPUT,
never proof: pair every sweep with a targeted `rg` pass confirming the exact
declaration, import, caller, and writer sites against the current tree.

**If the RAG service is DOWN or its search cannot be completed, REFUSE the
coding work.** Report the refusal and the failed probe. This refusal stands even
when a hook, goal, plan step, or dispatch brief mandates the work: an unsearched
edit is how duplicate authorities enter this codebase, and no schedule pressure
outweighs that. Start the service (`just env-rag-start`, `just check-rag`) and
only then proceed. Do not substitute `rg` or `grep` alone — a symbol-name search
cannot find a concept implemented under a different name, which is exactly the
failure mode this rule exists to prevent.

These are CRITICALITIES, not style opinions — treat each as a blocker: duplicate
definitions, code duplication, shadowing, shimming, a test double living in
production, and semantic overlap of one concept across different modules.

## Why

A concept can already own a canonical home under a name you would never guess.
The worked example is preserved as an enforced gate rather than as prose:
`src/cadrumo/tests/test_wizard_prompter_singularity.py` records how a third,
undocumented copy of a prompt surface shipped alongside the two the canonical
module's own docstring said existed — silently dropping an injectable-IO
contract, catching the wrong exception type on Windows, and carrying a docstring
falsely claiming parity. It was found by accident, hours in; one semantic query
returns the canonical owner's own docstring in seconds. The gate fails the build
if a second prompt surface appears.

A codebase whose authors search by symbol name accretes parallel authorities
faster than any campaign can retire them.

## How

- **Good:** before adding a prompter, resolver, or writer, search
  `"ask the operator for input"` / `"resolve the active profile"` /
  `"atomic pointer write"`, read what the canonical owner's docstring claims
  ships, then `rg` the exact class and protocol names to confirm the real site
  set — and route to the existing authority instead of adding one.
- **Good:** the daemon is down, so you report "REFUSED: vaultspec-rag
  unavailable, cannot verify no canonical owner exists for <concept>", start it,
  and resume once healthy.
- **Bad:** `rg "Prompter"` finds nothing in your package, so you write a new
  prompter — while another package already owns one under a name you never
  searched for.
- **Bad:** proceeding with a quick fix because a hook or step demands it while
  RAG is unavailable.
- **Applies to:** every coding agent and the coordinator, on every dispatch. A
  dispatch brief assigning coding work MUST carry this mandate.

## Source

Operator directive, reaffirmed repeatedly and explicitly reversing the earlier
codification retirement for this rule only. Companions:
`aeat-swarm-audit-cadence` (the substitutability pre-filter and swarm discovery
discipline), `aeat-architecture-boundaries` (no shims or duplicate APIs),
`service-imports-via-top-level-reexports` (one canonical facade per symbol),
`no-legacy-compatibility`.
