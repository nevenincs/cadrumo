---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:cafc326f4eb37f83853f58ae2d59e722e15b8a7bda36b69a14d9b3f779865e46'
step_id: 'S59'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Distinguish runtime residents from peer-process device usage in the contention snapshot and add the explicit unload action for Cadrumo-selected models, with the refusal naming which remediation applies, gated by injected readings covering both causes and an unload-path test, never touching another process

## Scope

- `src/cadrumo/application/provisioning.py`

## Description

- Add `RuntimeResident` and `read_runtime_residents`, reading the local model
  runtime's own resident set over a short-timeout process-list request.
- Add `cadrumo_selected_models`, resolving the two configured model roles into
  the boundary of what may be unloaded.
- Add `ContentionSnapshot` and `assess_model_load_contention`, comparing the
  declared requirement plus a configured safety margin against measured free
  headroom and attributing any shortfall.
- Add `UnloadOutcome` and `unload_runtime_model`, releasing one
  Cadrumo-selected model behind an ownership guard and a residency guard.
- Declare `ContentionCause` in `src/cadrumo/core/_hardware.py` and export it
  from the core facade, in the same commit as the module itself.
- Add the two settings the refusal must name — the safety margin and the
  explicit override — as strictly additive fields, reordering and reformatting
  nothing around them.

## Outcome

Attribution has **three outcomes, not two**, because the remediations are not
interchangeable and one of them is not ours to perform. A shortfall covered by
our own residents is `RUNTIME_RESIDENT` and the refusal names the unload. A
shortfall unexplained by them is `PEER_PROCESS` and the refusal says to close
the other application, never "unload" — telling an operator to unload something
they do not own is a false instruction. A shortfall only partly explained
carries **both** causes and both remediations, so a partial remedy cannot read
as a complete one.

A **fourth case was added beyond the Step's wording**, because the three above
still allowed a wrong instruction. A model resident in the local runtime that
Cadrumo did not select is reported in the refusal detail but never appears in
the unloadable set: the runtime holding it does not make it ours to evict, and
the remediation says to ask whoever loaded it. This makes ownership, not mere
residency, the thing that licenses the action.

The authority split is explicit and is what makes the attribution possible.
NVML is authoritative for the free-VRAM figure, per device and in process. The
runtime's own process list is authoritative for how much of that is ours. **The
gap between the two is the peer-process quantity.** A whole-device shell-out
reading is used nowhere, because it is contaminated by every process on the card
and so cannot answer either question.

Acting fails closed where reporting fails open. `None` is never headroom. An
unreadable free figure refuses. A *measured* shortfall whose resident set could
not be read also refuses, and refuses as `UNREADABLE` rather than silently
blaming a peer — the shortfall is real either way, but its cause is unknown and
the record says so. The one escape is an explicit override setting scoped to an
*unmeasurable* machine, which never admits a *measured* shortfall.

Cadrumo never evicts, signals, kills or otherwise touches a process it did not
start. Pressure caused by a peer is reported and refused, never managed. The
unload path carries two guards in order: the model must be one Cadrumo selected,
and it must already be resident. The residency guard is what keeps the action
from becoming a load, since the runtime's release call would otherwise bring a
non-resident model in before releasing it.

The observation layer stays side-effect-free: this module's shipped contract is
that probes never raise, so a refusal is a typed snapshot carrying
`admitted=False`, the attributed cause and the remediation. The dispatch choke
point is where that becomes a raised refusal. That boundary kept this Step out
of error-registry changes entirely.

## Verification

Runtime interaction is driven against a **real threading HTTP server on a
loopback port** speaking the runtime's wire shape, so the process-list read and
the release request exercise real HTTP through the real client. Hardware figures
arrive as injected measurements on the production function's own arguments. No
mock, stub, patch, skip or xfail anywhere.

    uv run --no-sync pytest src/cadrumo/application/tests/test_provisioning_hardware_contention.py src/cadrumo/application/tests/test_provisioning.py -p no:randomly -n 0 -q
    45 passed in 8.40s

Every refusal test carries a positive control proving the permit case passes
through the same call: measured headroom admits, a measured figure renders as a
number rather than as unverified, the CPU-only machine admits and refuses on
either side of its threshold, and the margin test admits once the margin drops
to zero.

Two mutations bear on this Step, both applied at runtime from a throwaway plugin
**outside** the repository so nothing under `src` was edited. Precision is the
point — each reddens exactly its intended tests rather than the file:

- **The fail-open flip**, the highest-value mutation here: the unreadable branch
  admits instead of refusing. **4 failed, 26 passed** — the unreadable
  accelerator, the readable accelerator with an unreadable free figure, the
  CPU-only machine with unreadable free memory, and the measured shortfall with
  an unreadable resident set. Exactly the four fail-closed paths and nothing
  else.
- **The ownership guard passes everything**: **2 failed, 28 passed** — the
  "resident Cadrumo did not select" test and the "unload refuses and sends
  nothing" test.

The two guarded unload cases are proven by **silence on the wire**, not merely
by a return value: the tests assert the server's event queue is empty, so a
refused or non-resident release provably never reached the runtime at all.

## Notes

No model was loaded, pulled, or inferred at any point, by this Step or any agent
it dispatched. Reading device state is the instrument's job; loading is not, and
an overflow on this host would destroy every concurrent agent's running work.

The safety-margin and override settings were added to a configuration module a
later Step also targets. The edit is strictly additive and touches no existing
field, so that Step's eventual diff stays readable.

A peer subsequently staged a purely cosmetic re-wrap of one line in the scope
file — three insertions, one deletion, no added or removed definitions. It was
read, confirmed semantically inert, and left staged rather than committed, since
the index also held two unrelated peer files at the time.

The index lock was held frozen with a dead holder across three commit attempts
spanning roughly nine minutes. It was never removed, waited on, or worked
around; the commit was skipped and a later sweep carried the work. The
delivered surface was afterwards verified present in the committed tree rather
than assumed — every public function of both Steps, the test file, the generated
API stub and its table-of-contents entry.
