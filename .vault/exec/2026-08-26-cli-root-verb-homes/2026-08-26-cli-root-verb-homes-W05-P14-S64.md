---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:4fe51fe2e2f2d284a92c23e3201af01a4fb25798ac796adddb991216efc13290'
step_id: 'S64'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Check the overstating half of name/help/handler agreement across the filing, export and completeness-claiming verbs

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `verify:` `python -c "...completeness-claim census over leaf help..."` -> `18 claims, all checked, none overstated`

## Notes

No code changed. S61 caught help that understated a verb's power; this is the
opposite direction -- help promising more than the handler delivers -- run over
the verbs where an overstatement would matter most.

Led with semantic search rather than grep, which routed straight from "filing or
export handler that omits records" to `application/modelo/_export.py` and the
filing-record specs.

**The three filing verbs under-promise rather than overstate, and their
preconditions are enforced.** `app modelo export` says it exports "a
verified-complete or filed" revision and is "local-only; never contacts AEAT";
that precondition is real -- `_export.py` carries
`ModeloExportReadinessRefusal` and `_COMPLETENESS_UNVERIFIED_MESSAGE`, and its
module docstring lists the refusals: non-exportable revision states,
cross-bucket targets, missing profile facts, unclean cross-period prerequisites,
unmatched IVA. `app modelo work file` says "Does NOT submit to AEAT" in the help
itself. `app modelo work verify` names the contract it verifies against.

**Eighteen leaf help strings make a completeness claim** ("every", "all",
"complete", "entire"). Most are `list` verbs, where enumerating everything is
the verb. One deserved a real check and is recorded because the raw number looks
alarming without the reason.

`app modelo list` says it lists "all official tax forms (modelos) registered in
the system", and it lists the REGISTRY modelos -- at most 58 of the 149 members
of the `Modelo` enum, because **91 have no registry definition**. That is not a
gap and not an overstatement. `core/_modelo.py` states those 91 have no registry
definition BY DESIGN: modelos suppressed by a later norm (M037 under Orden
HAC/1526/2024, M179 from ejercicio 2024) plus obligations filed by third parties
or specialised filers. The enum is the closed-set identifier type -- "it tells
you which modelos exist; the registry tells you what (if anything) they
contain" -- and the help's qualifier "registered in the system" is the accurate
reading.

Calling that a defect would have been over-reach, and it is recorded as examined
so a later reader does not re-open it on the 58-of-149 figure alone.
