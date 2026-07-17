---
name: aeat-rag-discovery-mandatory
trigger: always_on
---

# Semantic discovery precedes coding work; a down RAG service refuses the work

## Rule

Run `vaultspec-rag` semantic search BEFORE any coding work — before writing a new
symbol, module, resolver, prompter, writer, service, or test, and before
"fixing" a site you have not first searched for by MEANING. The canonical probe
is:

```
uv run --no-sync vaultspec-rag search "<natural-language concept>" --type code --port 8766 --timeout 120
```

(`--type vault` for the decision corpus). Semantic results are DISCOVERY INPUT,
never proof: pair every sweep with a targeted `rg` pass confirming the exact
declaration, import, caller, and writer sites against the current tree.

**If the RAG service is DOWN or its search cannot be completed, REFUSE the
coding work.** Report the refusal and the failed probe. This refusal stands even
when a hook, goal, plan step, or dispatch brief mandates the coding work: an
unsearched edit is how duplicate authorities enter this codebase, and no
schedule pressure outweighs that. Start the service (`just env-rag-start`,
`just check-rag`) and only then proceed. Do not substitute `rg`/`grep` alone —
a symbol-name search cannot find a concept implemented under a different name,
which is exactly the failure mode this rule exists to prevent.

These are CRITICALITIES, not code-style opinions — treat each as a blocker:
duplicate definitions, code duplication, shadowing, shimming, faking (a test
double living in production), and semantic overlap of one concept across
different modules.

## Why

The wizard prompter proved the cost. `application/wizard/_prompter.py` is the
canonical authority and its own module docstring states that exactly TWO
implementations ship (`CanonicalAnswerPrompter`, `QuestionaryPrompter`). The CLI
nevertheless carried a THIRD, undocumented hand-copy (`_QuestionaryTextPrompter`
plus a shadowing `_TextAnswerPrompter` Protocol) that had silently drifted: it
dropped the injectable-IO contract (making the wizard headlessly untestable),
caught only `except OSError` while `NoConsoleScreenBufferError` is NOT an
`OSError` subclass (so Windows operators met a raw traceback instead of the
translated refusal), and carried a docstring FALSELY claiming parity with the
canonical detection. That duplication was found BY ACCIDENT while chasing an
unrelated test failure, after hours of work — and a single `vaultspec-rag`
query returns the canonical prompter's own "two implementations ship" docstring
in seconds.

The same session found the duplication measurement itself false-green (a
duplication report that built a SECOND jscpd command — the instrument had
become the duplication it measured — and rendered "0 clones" green while 65
real clones existed, protected by a tautological test). A codebase whose
duplication gate lies and whose authors search by symbol name accretes parallel
authorities faster than any campaign can retire them; the operator's lived
experience of "the CLI-authority plan always fails" is the compound interest on
exactly that.

## How

- **Good:** before adding a prompter/resolver/writer, run
  `vaultspec-rag search "ask the operator for input"` / `"resolve the active
  profile"` / `"atomic pointer write"`, read what the canonical owner's
  docstring CLAIMS ships, then `rg` the exact class/protocol names to confirm
  the real site set — and route to the existing authority instead of adding one.
- **Good:** the RAG daemon is down; you report "REFUSED: vaultspec-rag
  unavailable, cannot verify no canonical owner exists for <concept>", start it
  with `just env-rag-start`, and resume once `just check-rag` is healthy.
- **Bad:** `rg "Prompter"` finds nothing in your package, so you write a new
  prompter — while `application/wizard` already owns one under a name you never
  searched for.
- **Bad:** proceeding with a "quick fix" because a hook/goal/step demands it
  while RAG is unavailable. The gate is the point; skipping it under pressure is
  how the third prompter shipped.
- **Applies to:** every coding agent and the coordinator, on every dispatch. A
  dispatch brief that assigns coding work MUST carry this mandate.

## Source

Operator directive 2026-07-17, issued on discovering the drifted CLI prompter
(three implementations of one contract, a false parity docstring, and two
silently reopened acceptance walls) and the false-green duplication runner. This
directive explicitly reverses, for this rule only, the 2026-07-13 codification
retirement. Supersedes the RAG-surface retirement of commit `ef392dc30e` — the
service is live and its use is now mandatory. Companion:
`aeat-swarm-audit-cadence` (the substitutability pre-filter and swarm discovery
discipline), `aeat-architecture-boundaries` (no shims/duplicate APIs),
`service-imports-via-top-level-reexports` (one canonical facade per symbol),
`no-legacy-compatibility`.
