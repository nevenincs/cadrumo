---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:6e7274189a505c3815da51717301e56dff084e9d08de842b87437e92b8922976'
step_id: 'S45'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Add the HardwareProfile probe carrying free system memory, accelerator presence, and NVML-backed total and free VRAM, with unknown reported as unverified on diagnostic rows, gated by injected-measurement tests covering every branch

## Scope

- `src/cadrumo/application/provisioning.py`

## Description

- Adjudicate the home before writing anything: semantic search plus targeted
  `rg` established `src/cadrumo/application/provisioning.py` as the sole
  capability-probe surface in the tree, and found **no existing VRAM, GPU or
  NVML reading anywhere** — no `nvidia-smi` call, no NVML binding, nothing under
  a Spanish or otherwise non-obvious name. There was nothing to adopt, so the
  module was extended in place per the provisioning decision's first ruling
  rather than given a sibling.
- Close a duplication found on the way in: the new `_ollama_endpoint` derivation
  subsumed the existing `_ollama_tags_url`, so the two were folded into one
  helper instead of shipping a second URL builder beside the first.
- Add `SystemMemoryReading` carrying total and free physical memory as
  independently optional figures.
- Refactor `read_total_system_memory_bytes` into a narrowing of a new
  `read_system_memory`, so total and free come from one measurement and there is
  no second platform branch to drift. Windows already had `ullAvailPhys` in the
  struct it filled; POSIX reads `SC_AVPHYS_PAGES` beside the pages it already
  read.
- Add `AcceleratorDevice`, `AcceleratorReading` and `read_accelerator`, reading
  per-device totals and free figures through NVML with a lazy import.
- Add `HardwareProfile` composing the two readings, with the reporting and
  acting aggregations as separate properties.
- Add `probe_hardware_profile` as the injectable composition seam and
  `probe_local_inference_hardware` as the operator-facing diagnostic row.
- Declare `AcceleratorKind` in `src/cadrumo/core/_hardware.py` and export it
  from the core facade, in the same commit as the module itself.

## Outcome

The decision's totals-versus-free split is enforced **structurally rather than
by convention**, which is the most reusable thing this Step produced.
`total_vram_bytes` **sums** across devices, because the reporting question —
what is installed in this machine — is additive. `free_vram_bytes` takes the
**maximum of any single device** and never the sum, because a model is resident
on one card: two cards with 3 GiB free each are not 6 GiB of headroom, and
summing them manufactures capacity that no allocation can reach. A caller
cannot reach for the wrong quantity by accident, because the wrong quantity is
not exposed under a name that invites it.

Unknown is never headroom. Every figure is independently optional and `None`
means "not measured", never "zero" and never "plenty". A device whose free
figure is unreadable is skipped rather than counted as zero; a device set where
nothing is readable yields `None`, which fails closed at the act. On the
reporting side the shipped direction is preserved: `probe_local_inference_hardware`
keeps the row available on every accelerator kind and renders unknown figures as
`unverified`, because a diagnostic must not manufacture a shortfall on a
platform it merely cannot measure.

`AcceleratorKind` distinguishes `NONE` from `UNKNOWN`, and the distinction is
between two *measurements* rather than a presence flag with a fallback. `NONE`
is a positive reading — the device library initialised and enumerated zero
devices — and legitimately permits judging a load against free system memory.
`UNKNOWN` is the absence of a reading and refuses. Collapsing the two would let
a machine that cannot be measured pass as a machine measured to have no
accelerator.

NVML is preferred over a whole-device shell-out deliberately, and the reason
belongs to the next Step as much as this one: NVML yields **per-device** figures
from an in-process query, whereas a whole-device reading is contaminated by
every process on the card. That contamination is precisely the quantity the
contention attribution has to split, so a whole-device reading is used nowhere.

## Verification

Injectability without mocking was the design constraint, because a test may not
depend on this host's GPU state, which changes minute to minute under a running
agent fleet. Measurements are arguments on the production functions themselves —
`probe_hardware_profile(memory=..., accelerator=...)` — following the
`cache_root` and `env` pattern the module already shipped. Every test constructs
real models and runs the real comparison logic. No mock, stub, patch, skip or
xfail anywhere.

    uv run --no-sync pytest src/cadrumo/application/tests/test_provisioning_hardware_contention.py src/cadrumo/application/tests/test_provisioning.py -p no:randomly -n 0 -q
    45 passed in 8.40s

The 45 are this Step's and the next Step's 30 new tests plus the 15 pre-existing
probe tests, which confirm the `read_total_system_memory_bytes` refactor is
non-regressive.

Two mutations bear on this Step, both applied at runtime from a throwaway plugin
**outside** the repository so nothing under `src` was edited. Each reddens
exactly its intended test rather than the file:

- Free VRAM falls back to the **total** when no free figure is readable — the
  "unknown reads as plenty" defect: **1 failed, 29 passed**
  (`test_readable_accelerator_with_unreadable_free_figure_refuses`).
- Free VRAM **sums** across devices instead of taking the maximum: **1 failed,
  29 passed**
  (`test_total_vram_sums_devices_but_free_vram_takes_the_largest_single_device`).

The wider gate batch ran clean for this surface:

    uv run --no-sync pytest ... -p no:randomly -n 0
    4 failed, 855 passed in 535.26s (0:08:55)

All four failures were peer-owned and untouched — three from one undocumented
test-only private import in another lane's test file, and one missing docstring
cross-link in an aggregation module. Recorded, not patched.

## Notes

The NVML binding is **not installed in this environment**, so this host reads
the accelerator as `unknown` and fail-closes at the act. That is the decision
behaving correctly, not a gap in the instrument: the dependency is declared in
the inference extra and the lockfile, and every branch is covered by injected
measurements, so the gates are complete without the library present. Real-VRAM
reading here awaits an environment sync that was **deliberately deferred** while
several agents were executing in this worktree, because syncing mutates the
shared virtualenv underneath every one of them mid-run. The live-machine
acceptance case in the sibling contention Step travels with that sync.

The packaging declaration for the NVML binding was authored during this Step
before its owning packaging Step was dispatched. The two did not conflict — the
tree carries exactly one declaration, with the packaging Step's dependency-gate
mapping and lockfile refresh landing on top — but the packaging Step did not
author the declaration line itself, which its own record should reflect.
