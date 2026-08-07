---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:654c0e7eebaab5a8fda6d25161a1d95fe9a7ba5569546f9f8856a8f9194c5e95'
step_id: 'S47'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Scope

Surface the measured hardware profile and the model-load contention verdict as
rows on `aeat config check`, in `src/cadrumo/entrypoints/cli/_config`.

## What landed

- `_config/_check_hardware_rows.py` — `contention_row`, projecting a
  `ContentionSnapshot` onto the existing dependency-row shape.
- `_config/_check_cli.py` — the hardware and contention rows added to
  `dependencies`.
- `_config/tests/test_check_hardware_rows.py` — 7 cases.

No payload shape change: both are `CheckDependencyPayload` rows in the existing
`dependencies` list. One case pins the envelope's exact key set and every row's
exact key set, so a future bespoke `hardware:` or `contention:` block on the
result fails — that is the shape the envelope contract forbids and the easy
thing to reach for when adding a differently-shaped row.

## The policy call: `available` splits on CAUSE, not on `admitted`

The decision that governs reporting is that acting fails closed where reporting
fails open. The row shape forced a choice about what `available` means, and it
is resolved on the contention CAUSE rather than on the `admitted` flag:

- **unreadable ALONE** → `available` true, detail prefixed `unverified`,
  remediation carried. A diagnostic must not manufacture a shortfall on a
  machine it merely cannot measure.
- **measured shortfall** (`runtime_resident` / `peer_process`) → `available`
  false, with that cause's own remediation. A real state with a real fix, and
  the doctor's existing shape for one.
- **unreadable AND short** → reports the shortfall. Fail-open covers "could not
  tell" alone; burying an actionable shortfall behind "unverified" is the worse
  error.

The classification is READ from `ContentionCause` on the snapshot the
application layer produced, never re-derived here. Attributing a shortfall is
that layer's judgement, and telling an operator to unload a model when the
pressure is a peer application's is a false instruction. A case asserts the two
remediations do not collapse to one.

Neither row touches the exit contract; `ok` still follows `issues` alone. A
contended machine is not a misconfigured one — if contention could set `ok`
false, running the doctor while another application held the GPU would report
the profile as broken.

## Verification

Both marker lanes measured from a log on disk, rather than reporting the green
one:

```
-m "integration or unit"   7 collected, 7 passed in 143.27s
default lane               no tests collected (7 deselected)
```

All 7 carry `integration`, matching the sibling preflight tests, so a bare
default-lane run sees none of them.

**Gate proven to bite**, by runtime mutation from outside the repo with no
tracked file touched. Three plausible WRONG implementations were run against the
assertions and all three are rejected:

- fail-closed-everywhere (correct for the ACTING path, wrong for a diagnostic —
  it manufactures a shortfall on an unmeasurable machine)
- fail-open-everywhere (a diagnostic that never reports a fault)
- treat-any-unreadable-as-open (buries a real, actionable shortfall)

Healthy readings: `unreadable=True peer=False both=False`. Module verified
untouched afterwards. Three wrong implementations rather than one deviation is
what shows the assertions discriminate on the policy itself.

Positive controls sit in the cases, not only in the harness: the admitted and
the no-model-selected states both assert `available` true, so a projection
returning false for everything fails; and their details are asserted to differ,
so collapsing "you have headroom" into "you have no model" fails too.

## Design note

The hardware profile is probed ONCE and threaded into both rows. Two probes
would read the machine at two moments and could disagree, so the profile
reported is the one the verdict was computed against.

The projection was sited in the CLI rather than beside `probe_local_inference_hardware`
because `application/provisioning.py` carried staged and unstaged peer work when
this Step began. Projecting a domain verdict onto a presentation row is
presentation work, so the constraint and the architecture agreed.

Nothing on this path loads or pulls a model. The hardware profile, the runtime's
resident set and the model catalogue are all readings; selection names a model,
it does not load one.
