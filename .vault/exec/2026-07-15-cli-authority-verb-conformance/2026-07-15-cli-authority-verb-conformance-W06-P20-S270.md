---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S270'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove the permissive not-read-only default for unknown command keys, or prove every gate resting on it still discriminates an absent key from a live write verb

## Scope

- `src/cadrumo/application/operator_surface/_classification.py`

## Description

- Enumerate the consumers of the permissive not-read-only default before deciding. Production by-key consumers of `command_classification` (which resolves an unknown family to `LOCAL_STATE_MUTATING`): the MCP identity gate (fail-CLOSED — an unknown key is not read-only, so it enforces), the HITL confirmation gate and `is_handoff_command` (fail-OPEN, grounded under `S285`), and the persona-scope handoff read. Consumers passing explicit mutability (the MCP annotation projection, the risk-table parity gate's synthetic verb) do not use the default. Test gates resting on it: the risk-table no-silent-default parity gate (grounds via the exposed descriptor set first, and the default makes an undeclared mutating verb stricter), the write-guard catalogue gate (grounds against the materialised tree), the agent-eval goldens (assert over known mutating keys), and the identity-gate retired-key case (requires a retired key to classify non-read-only so the gate enforces).
- Choose route (b): KEEP the default and prove discrimination. Removing it — raising on an unknown family — would turn the identity gate's retired-key refusal into a crash and defeat the risk-table parity gate's stricter read, so a blanket removal makes correct gates wrong.
- Record the decision in `_classification.py`: expand `_mutability_for`'s docstring to state the default is deliberate and fail-closed, must not be removed, cannot distinguish an absent key from a live write verb, and that any consumer needing that distinction must ground its key against the live surface (as the write-guard catalogue, risk-table parity, and HITL gates now do).
- Add two discrimination-proof tests to `test_classification_parity.py`: an absent key classifies non-read-only and all-false (the fail-closed direction the read-only-gated consumers depend on), and an absent key is byte-for-byte indistinguishable from a live non-destructive mutation at the classification level (the property that mandates grounding).

## Outcome

Route taken: (b) — keep the default, prove discrimination. Verified at HEAD `1437055950f5b8f4082d323578294fc32ad1d9fe`.

Command: `uv run --no-sync pytest -p no:randomly -m "unit or integration" -n0 -q --no-header src/cadrumo/application/operator_surface/tests/test_classification_parity.py` — `9 passed in 1.54s`.

Per-consumer discrimination proof, in place across existing and new gates: risk-table parity discriminates via `test_a_new_unclassified_mutating_verb_would_be_caught`; the write-guard catalogue via `test_live_command_check_rejects_a_stale_catalogue_entry`; the identity gate's retired-key fail-closed via `test_identity_gate.py`; the HITL auto-approve path via the new `S285` grounding.

Mutation-check per added assertion (throwaway rebind probe; real passes, defect fails):

- `absent-key fail-closed (read_only is False)`: real_passes=True; default-`READ_ONLY` defect makes the absent key read-only → defect_fails=True.
- `absent == live-mutation axes`: real_passes=True; default-`READ_ONLY` defect diverges the axes → defect_fails=True.

Both classification mutation probes reported OK. `ruff check` and `ruff format --check` clean on both touched files.

## Notes

The default is not removed because its removal is a net safety regression: it is the fail-closed direction for every read-only-gated consumer, and the only place it was unsafe (the HITL auto-approve fall-through) is grounded at the gate under `S285` rather than by weakening the shared default. No production behaviour changed here; the change is one docstring recording the decision plus two locking tests.
