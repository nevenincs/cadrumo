---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S23'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Author the shared two-tier atomic-write helper with the hardened master-key pattern as the strong tier

## Scope

- `src/cadrumo/core`

## Description

- Read ADR ruling R7 (one atomic-write helper) and research finding F2.1
  (four in-tree atomic-write dialects) as the grounding authority.
- Read the two named model implementations end to end:
  `adapters/persistence/storage/envelope/_envelope.py` (`save_envelope`, the
  standard NamedTemporaryFile-sibling + fsync + `os.replace` + parent-fsync
  sequence, plus its `_cleanup_tmp_file` helper) and
  `adapters/persistence/storage/master_key/_master_key_io.py`
  (`atomic_write_secure_bytes`, the hardened `O_EXCL`/mode-0o600/pid+token
  tempname pattern). Also read `core/env_io.py`'s `_atomic_write_text` for
  the `try`/`finally` (BaseException-safe, not `except OSError`-only)
  cleanup discipline the brief asked to model, and `core/locks.py`'s
  `fsync_parent_dir` for the parent-directory durability step.
- Authored `src/cadrumo/core/atomic_write.py` with four public functions:
  `atomic_write_bytes` / `atomic_write_text` (standard tier) and
  `atomic_write_hardened_bytes` / `atomic_write_hardened_text` (hardened
  tier), the text variants encoding to bytes and delegating to their bytes
  sibling so there is one canonical write path per tier. Both tiers guard
  the whole write with `try`/`except BaseException`/`finally` so any
  exception -- including `KeyboardInterrupt` -- triggers tempfile cleanup;
  neither tier wraps or translates the raised exception, and the failure log
  line carries only the target path and exception type name, never payload
  bytes.
- Confirmed via `dev.docs.apidocs audit` that the module imports nothing
  from the `CORE_STRUCTS` docstring-cross-link anchor set (only
  `core.locks.fsync_parent_dir`, a function, not a class), so no
  `:class:` cross-link was fabricated, per the core-struct-docstring-links
  rule's "do not fabricate" instruction.
- Authored 16 real-behaviour tests in
  `src/cadrumo/core/tests/test_atomic_write.py` covering both tiers:
  roundtrip (bytes and text), parent-directory creation, no-leftover-tmp-
  file-on-success, overwrite of an existing target, and two genuinely
  induced failure modes rather than any mock/patch/monkeypatch -- a real
  `os.replace` refusal (the target pre-exists as a directory, which
  `os.replace` cannot replace with a file) and a real write-time `TypeError`
  (a wrongly-typed `str` payload passed where `bytes` is required, which
  `handle.write`/`os.write` genuinely reject) -- both asserting the tempfile
  is gone afterward and any pre-existing target content is byte-for-byte
  untouched. Added a POSIX-conditional (not skipped) assertion of the
  hardened tier's default and an explicit `0o600`/custom file mode.
- Ran `python -m dev.docs.apidocs scaffold` and landed the regenerated
  `docs/api/cadrumo.core.rst` (one new submodule line) and the new
  `docs/api/cadrumo.core.atomic_write.rst` stub in the same commit as the
  module, per the `aeat-docs-scaffolding-cli` rule.

## Outcome

New module ships with zero call-site migration (S24/S25 remain separate
Steps, per the brief). Gates: targeted suite 16/16 passing; `ruff check`
clean on both the module and its test file; the docstring core-struct-link
gate (`-m docs test_docstring_core_struct_links.py`) passes (3/3, unaffected
-- confirms no fabricated cross-link was needed); `dev.docs.apidocs audit`
reports a fully conformant stub tree (0 missing, 0 orphan, 0 stale);
`pytest --collect-only -q` on `src/cadrumo/core` (715 collected) and the
full tree (12835 collected, up by the 16 new tests plus concurrent peer
work) both collect cleanly; `test_import_hygiene_gate.py` passes (11/11).
Committed at `b25d705c01` (module + tests + apidocs stubs, one atomic
commit).

## Notes

No incidents. One acknowledged test-coverage limitation: the hardened
tier's `O_EXCL` collision-refusal branch (a pre-existing tempfile at the
exact `{name}.{pid}.{token_hex}.tmp` path) is not independently exercised,
because forcing that exact collision deterministically would require
patching `secrets.token_hex`, which the no-mock/no-patch discipline
forbids. The general OSError-propagation-and-cleanup contract is proven by
the directory-collision replace-failure test instead; a future reviewer
wanting `O_EXCL`-specific coverage would need a different real-behaviour
technique (e.g. two concurrent real writers racing on the same path) rather
than a patched RNG.

This Step ran ahead of Wave W02 (lifecycle policy) per the coordinator's
explicit dispatch instruction: a sequencing relaxation distinct from the
plan document's own Parallelization section (which only names W03.P05 and
W05.P09's dependency on W01.P01). W05.P08 has no structural dependency on
W02, so the relaxation carries no correctness risk; recording it here
rather than editing the plan's Parallelization prose, per the coordinator's
instruction.
