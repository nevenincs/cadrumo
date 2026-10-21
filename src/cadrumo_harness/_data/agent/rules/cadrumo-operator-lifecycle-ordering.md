# Lifecycle ordering: calculate, then verify, then file

**Calculate before you verify. Verify before you export or record the filed marker.
Never claim reconciled with AEAT before the person has filed and you have pulled back
evidence of that.** Treat any attempt to skip a step, or any result that lets you skip
one, as a refusal to work around, not a shortcut. A local filing record is not evidence
that AEAT accepted a filing. Keep each operation's receipt.

- **Calculate first.** `aeat app modelo work create` establishes the work unit and
  `aeat app modelo work calculate` stores the first draft revision. Nothing downstream
  has a value to check before this runs.
- **Verify next.** `aeat app modelo work verify` runs independently of the calculation;
  a calculate result does not certify itself. Read the verify result, and do not go on
  to `aeat app modelo export` or `aeat app modelo work file` while it reports a
  blocking finding.
- **Export and file only after a clean verify.** `aeat app modelo export` produces
  the local fichero-BOE and `aeat app modelo work file` records the local filed marker.
  Both are irreversible local steps and neither reaches AEAT. Tell the person what
  you are about to do and run each only on their go-ahead in the conversation; a
  clean verify informs that decision and never replaces it, and a second run by you is
  not an independent verifier. Record the marker only after the person has filed
  outside the application. The go-ahead for one does not cover the other.
- **Reconcile is separate and later.** `aeat app modelo reconcile pull`, or
  `aeat app modelo reconcile import --file`, runs after the person has filed outside
  the application. Both only read: you may start either. Relay the verdict and every
  difference verbatim, and let the person decide what follows. Never report a filing
  as reconciled or accepted before this has run and returned official evidence.

## Contradictions between surfaces are a stop, not a retry

If one surface says a work unit is ready (for example `readiness: true`) while another
blocks it (a verify result naming an unmet obligation or a cross-period dependency),
do not retry past the disagreement or pick the convenient answer. Stop, report both
results verbatim, and resolve the contradiction first. A silent retry-until-it-works
pattern is how a wrong revision or period gets filed.

## Never reorder to "fix" a number

If verify blocks on a finding you do not like, correct the input (the ledger entry, the
profile fact, the declared casilla) and recalculate. Never run export or file against
an unverified or previously blocked revision to route around the finding.
