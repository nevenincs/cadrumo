# Lifecycle ordering — calculate, then verify, then file

The modelo lifecycle has one canonical order. The manifest carries it as data
(the MCP `contract` tool → `contract.lifecycle.steps`, currently
`calculate → verify → file`) so this ordering is never a convention you invent —
confirm it against that field if you are ever unsure, rather than trusting a stale
paraphrase.

## The invariant

**Calculate before you verify. Verify before you export or mark filed. Never claim
reconciled with AEAT before a human has actually filed and you have pulled back
evidence of that.** This is not a suggestion to follow when convenient; treat any
attempt to skip a step, or any tool result that lets you skip one, as a refusal to
work around, not a shortcut to take.

- **Calculate first.** `aeat app modelo work create` establishes the work unit;
  `aeat app modelo work calculate` produces the first draft revision. Nothing
  downstream has a value to check before this runs.
- **Verify before you export or file.** `aeat app modelo work verify` runs
  independently of the calculation step — do not treat a calculate result as
  self-certifying. Read the verify envelope; do not proceed to `aeat app modelo
  export` or `aeat app modelo work file` while it reports a blocking finding.
- **File and export only after a clean verify.** `aeat app modelo export`
  (produce the fichero-BOE) and `aeat app modelo work file` (mark internally
  filed) are the terminal, irreversible steps of the local half. Both still stop
  short of AEAT — see the safety rule.
- **Reconcile is a separate, later step.** `aeat app modelo reconcile pull` or
  `reconcile file --file ...` runs after the human has actually filed outside the
  application. Never report a filing as reconciled or accepted before this step
  has actually run and returned official evidence.

## Contradictions between surfaces are a stop, not a retry

If one surface says a work unit is ready (for example `readiness: true`) while
another blocks it (for example a verify result naming an unmet obligation or a
cross-period dependency), do not retry past the disagreement or pick whichever
answer is more convenient. Stop, report both results verbatim to the taxpayer, and
resolve the contradiction before continuing — a silent retry-until-it-works
pattern is how a wrong revision or a wrong period gets filed.

## Never reorder to "fix" a number

If verify blocks on a finding you do not like, the fix is to correct the input
(the ledger entry, the profile fact, the declared casilla) and recalculate — never
to re-run export or file against an unverified or previously-blocked revision to
route around the finding.
