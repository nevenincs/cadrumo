---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S269'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Decide in a follow-on ADR the criterion by which a command path is profile-bound, then reconcile the 48 unguarded mutation-shaped leaves against it per verb

## Scope

- `src/cadrumo/application/storage_write_policy.py`

## Description

- Re-measure the unguarded mutation-shaped leaves against the live tree.
- State the criterion, record it in a follow-on decision record, and enforce it
  with a gate over the live tree rather than a curated list.
- Guard the leaves the criterion identifies, and name the tail it cannot judge.

## Outcome

SATISFIED, with the decision recorded and the reconciliation done for the
unambiguous half.

MEASUREMENT FIRST. 290 live leaves, 84 mutation-shaped, 45 guarded, 39
unguarded. The close review reported 48; the number moved because verbs landed
and the catalogue was repaired in between. Also measured, and the better news:
ZERO dead catalogue entries. The fail-open that started this thread - six
entries naming paths the CLI no longer exposed - has not recurred.

Of the 39 unguarded, 30 sit under `config` and 9 under `app`. The split is not
arbitrary. Four of the config ones are bootstrap-exempt by design: profile
create, passphrase change, recover and the recovery family must run BEFORE a
profile is unlocked, and guarding them would deadlock the operator out of their
own data. The nine under `app` are exempt from nothing and guarded by nothing.

THE CRITERION, now recorded in its own decision record. A live leaf under the
`app` root that mutates active-bucket state must be reachable by exactly one of
two mechanisms - the profile-bound write guard, or the bootstrap exemption -
and never by neither. A read-only leaf is in neither by design. The `app` root
already supplies the warrant: its own help states that app commands operate on
the active profile bucket, so a mutating leaf there that no mechanism covers
contradicts the root's definition.

The nine are now guarded: ledger evidence confirm, ledger restore, the three
invoice-catalogue mutations, live justificante pull, modelo iva-wallet seed,
modelo m145 create, and modelo work resume.

WHAT THE FIRST ATTEMPT GOT WRONG, recorded because it is the substance of the
constraint. The gate initially classified by verb token across the whole `app`
surface and flagged eleven further leaves - four registry `verify` verbs, two
`export` verbs, a `wizard`, an `extract` and a `reconcile`. Those are not
mutations. `app registry verify` reads bundled data and `app modelo export`
writes a file rather than bucket state, exactly as the close review predicted
when it said this is a per-verb judgement that must not be performed
mechanically. The same token means different things in different families:
`app modelo work verify` genuinely mutates revision state while `app registry
verify` does not.

So enforcement is scoped to tokens whose meaning is not in doubt. That buys a
TOTAL guarantee over most mutating verbs rather than a partial guarantee over
all of them, and it leaves the ambiguous tail named rather than swept into
either half. The tail is the residue this Step hands on.

MUTATION-PROVEN. Removing a single one of the nine additions from the catalogue
reds the criterion gate, naming the leaf. The anti-vacuity companion earned its
place immediately: it caught four tokens in my OWN set - delete, edit, prune,
rotate - that name no live `app` verb at all, and would have silently narrowed
the guarantee.

Gates at HEAD `93cd1b0304a87686b06a6d2c9c406dd6fd383f71`:

- `uv run --no-sync pytest
  src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py -n0 -m ""`
  collected 13 cases and exited `13 passed in 72.94s`.
- `uv run --no-sync pytest
  src/cadrumo/entrypoints/mcp/tests/test_write_policy_mutability_parity.py
  src/cadrumo/entrypoints/mcp/tests/test_risk_table_parity.py -n0 -m ""`
  collected 6 cases and exited `6 passed in 5.31s`.
- `ruff check` and `ruff format` clean on both touched files.

## Notes

This is a behaviour change in a safety guard, not a refactor: the nine verbs
now refuse on an unattached storage route rather than proceeding. It was put to
the operator as a decision before implementation and approved, which is why it
is recorded in a decision record rather than applied as a fix.

A stale test NAME was corrected in passing. A case called
`test_config_switch_remains_recovery_path_on_root_fallback_database` tests
`config login`; no `switch` leaf exists anywhere in the live tree.

The residue, stated so it is not mistaken for coverage: leaves ending in
`verify`, `export`, `extract`, `reconcile`, `preview` and `wizard` are outside
the enforced set and each needs a per-verb reading. The 30 unguarded `config`
leaves were not adjudicated either - that root mixes custody, bootstrap and
profile-scoped verbs, and a wrong guard on a custody path can lock an operator
out of their own data.
