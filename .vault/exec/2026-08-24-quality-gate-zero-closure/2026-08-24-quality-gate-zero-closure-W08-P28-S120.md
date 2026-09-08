---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:15613f38efb40183ecf7e2a4ffd74c3608642103aee24ed798912f22294e1069'
step_id: 'S120'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---
# Land the verdict-grammar detector over real gate-output provenance

## Scope

- `dev/quality/gate_verdict_grammar.py`
- `dev/quality/tests/test_gate_verdict_grammar.py`
- named non-collected verdict fixtures under `dev/quality/tests/fixtures/`

## Changes

- Detect direct containment, prefix, and suffix predicates against verdict tokens only when the module is enrolled by a declared producer grammar.
- Resolve literal verdict names from bounded assignments and loops, including the historical dynamic `KEPT` / `BROKEN` loop in `dev/audit/report.py`.
- Attribute predicates to captured gate output through reaching assignments, direct producer results, selected value-preserving expressions, comprehensions, and positional helper parameters.
- Treat overwrites, destructuring, named expressions, loops, definitions, parameters, imports, and future or cyclic bindings as provenance barriers where they replace the relevant value or callable.
- Recognize positional and `args=` subprocess invocations plus verified module-aliased and directly imported `subprocess.run` spellings, while rejecting shadowed or foreign callables that merely share the name `run`.
- Removed the superseded scope-wide fixed-set implementation rather than retaining a compatibility path.
- Removed the 224-line omnibus mutation-controls fixture and its catch-all test. The remaining named fixtures describe public detector behaviors; mutation-directed implementation mirroring is not part of the shipped gate.

## Verification

- Exact detector SHA-256: `3F567EA4740B7D648F3FD0931B0048BF9FACE275BBEECA568EC6CD5553A37031`.
- Exact gate SHA-256: `FC96F3451C04876E0504AED722FA4E09FA53845D288BEC87EC294F3891D7FAFF`.
- Aggregate SHA-256 of the 16 sorted `gate_verdict_*.py.fixture` filename/hash entries: `831C28DF49A03BCC825CFD46EBF8C6212BE4C23F6FC2F838C30C17734AC050A7`.
- The 16-test focused gate passes its historical positive, anti-vacuity, provenance, source-order, overwrite, direct-result, helper, import-origin, UTF-8, path-attribution, and real-tree controls.
- The combined current P28 surface passes all 35 tests in 110.60 seconds.
- Ruff lint, Ruff formatting, `ty`, and basedpyright pass for the detector/gate pair with no diagnostics.
- Formal semantic and fixture-design approval is recorded in `[[2026-09-07-quality-gate-zero-closure-s120-s121-verdict-grammar-detector-review-audit]]`.
- Exact-current mutation evidence and individual survivor dispositions are owned by S121 and are not inherited from superseded implementations.
