# Semantic discovery precedes coding work; a down RAG service refuses the work

Run `vaultspec-rag` semantic search BEFORE any coding work — before writing a new
symbol, module, resolver, prompter, writer, service or test, and before "fixing"
a site you have not first searched for by MEANING:

```
uv run --no-sync vaultspec-rag search "<natural-language concept>" --type code --port 8766 --timeout 120
```

(`--type vault --doc-type adr` for the decision corpus.) Semantic results are
DISCOVERY INPUT, never proof: pair every sweep with a targeted `rg` confirming
the exact declaration, import, caller and writer sites.

**If the service is DOWN, REFUSE the coding work.** Report the refusal and the
failed probe. This stands even when a hook, goal, plan step or dispatch brief
mandates the work: an unsearched edit is how duplicate authorities enter this
codebase. Start it with `just env-rag-start` and verify with `just check-rag`.

**Search for the canonical HOME, not merely for a duplicate.** The purpose is to
find where a concept canonically lives and whether it is already fragmented
across layers. The compliance test is whether the fragmentation got closed, not
whether you confirmed you were not adding a second copy. Read what a result
DOES, never what it is called. Zero callers is not evidence of dead code — it is
evidence of no wired consumer.

These are CRITICALITIES, not style opinions — each is a blocker: duplicate
definitions, code duplication, shadowing, shimming, a test double living in
production, and semantic overlap of one concept across modules.

A symbol-name grep cannot find a concept implemented under a different name,
which is exactly the failure this prevents. The worked example is preserved as a
gate rather than prose: `src/cadrumo/tests/test_wizard_prompter_singularity.py`
records how a third, undocumented copy of a prompt surface shipped alongside the
two its canonical module's docstring said existed — dropping an injectable-IO
contract, catching the wrong exception type, and carrying a docstring falsely
claiming parity. One semantic query returns the canonical owner's own docstring
in seconds; the gate now fails the build if a second prompt surface appears.

## How

- **Bad:** `rg "Prompter"` finds nothing in your package, so you write one —
  while another package already owns one under a name you never searched.
- **Bad:** proceeding with a quick fix because a hook demands it while RAG is
  unavailable.
- **Applies to** every coding agent and the coordinator, on every dispatch. A
  brief assigning coding work MUST carry this mandate, and the coordinator must
  exercise it, not merely mandate it.

Companions: `aeat-swarm-audit-cadence`, `aeat-architecture-boundaries`,
`service-imports-via-top-level-reexports`.
