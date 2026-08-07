---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:ecb8d1b76b3c1d8b5be0f35105339534b9175b30ea5966c327829062dfe9dad8'
step_id: 'S55'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Complete the llm extra dependency closure (Pillow, pynvml) in the packaging metadata with the boundary rationale recorded, gated by deptry and the packaging smoke lanes

## Scope

- `pyproject.toml`

## Description

- Map the NVML binding's distribution name to its import name so the accelerator probe stops reading as an undeclared dependency.
- Suppress the imaging package's unused-dependency diagnostic with the import asymmetry recorded as the rationale.
- Refresh the lockfile so the extra resolves.

## Outcome

The Step's premise had already been half-satisfied when this record's work began, and the correction matters for anyone comparing the diff to the Step text. Both dependencies — the imaging package and the NVML binding at `>=13,<14` — were already declared in the extra at HEAD, carried in by a peer sweep commit along with the boundary rationale comment the Step asks for. Reading the Step against the diff alone would suggest almost nothing was delivered.

What was missing was the **gating half**, and the dependency gate was RED at HEAD as a direct consequence of that earlier landing: four issues, exit 1. The accelerator probe's import read as an undeclared dependency, the matching declaration read as unused, and the imaging package read as unused twice over — once for its base declaration and once for its declaration in the extra. So the Step's real deliverable was making the declaration survive the gate that is supposed to police it.

The root cause of the NVML pair is genuinely non-obvious and worth carrying forward. The dependency scanner derives a distribution's module name from that distribution's **installed** metadata. A dependency declared only in an extra the development environment does not install has no installed metadata, so the scanner falls back to guessing a module name from the distribution name — which for this package guesses wrong, because the distribution and its import name differ. One entry in the package-to-module map closes both diagnostics at once: the import resolves to a declared distribution, and the declaration resolves to a real import.

The imaging package's diagnostic is a true false positive and was handled as one rather than silenced. Nothing under the source tree imports it by name; the page rasteriser reaches it from inside the PDF rendering library's conversion call and then operates on what comes back. The scanner sees only the absent import statement and reads both declarations as unused. The suppression records that asymmetry as its stated reason, and says explicitly that the declaration is the fix rather than the problem — deleting either declaration to satisfy the scanner would restore the undeclared-direct-reliance defect the declarations exist to close.

The distribution name was verified against the published package rather than from recall, and the method is worth propagating: the wheel was downloaded and its members listed, confirming directly that the distribution ships the top-level module the probe imports. Distribution name and import name differ for this package, which is exactly the situation where memory is least reliable and a one-command check is decisive.

## Verification

The dependency gate, run as the project recipe invokes it, before and after:

    uv run --no-sync python -m dev.quality.quiet deptry src/cadrumo --known-first-party cadrumo --extend-exclude ".*test_.*[.]py" --extend-exclude ".*_test_.*[.]py" --extend-exclude ".*[\\/]tests[\\/].*"
    Found 4 dependency issues.
    EXIT=1

After:

    EXIT=0

The packaging surface tests over the same declarations:

    uv run --no-sync pytest dev/packaging/tests/test_inference_imports_are_declared.py dev/packaging/tests/test_dependency_surface.py -q
    5 passed in 13.48s

Lockfile resolution:

    uv lock
    Resolved 252 packages in 399ms
    Added nvidia-ml-py v13.610.43
    EXIT=0

The published distribution, confirmed by listing the downloaded wheel's members rather than trusting recall: version 13.610.43, BSD licensed, shipping a top-level module whose name differs from the distribution name — which is the whole reason the scanner needed the mapping.

## Notes

The lockfile was refreshed but **no environment sync was run**, deliberately: several agents were executing against the shared virtual environment at the time, and mutating it underneath them would have broken every running lane. No gate for this Step needs one. Both the dependency gate and the packaging surface tests assert against the declaration metadata rather than against importability, by design — a package declared in an extra is expected to be absent from the development environment, and a gate that required it installed would be asserting the opposite of what the extra means.

The consequence is that the declaration half is complete while the live NVML read on this host still waits on a coordinated sync, which the operator has queued.

The gate was red at HEAD before this work began. That red was not caused here and was not treated as pre-existing breakage to route elsewhere: it was created by the same landing that put the dependency in the extra, and closing it is what this Step is for.
