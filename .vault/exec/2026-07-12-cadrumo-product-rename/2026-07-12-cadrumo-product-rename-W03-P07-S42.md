---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S42'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Build and inspect both companion wheels for disjoint cadrumo_data members

## Scope

- `local companion wheel artifacts`

## Description

- Build fresh manuals and official companion wheels into a system temporary directory outside the project tree.
- Inspect each wheel's `METADATA`, `RECORD`, archive members, namespace shape, payload bytes, and file size.
- Derive expected ownership independently from Git-tracked `src/cadrumo/_data/corpus` source binaries.
- Prove canonical distribution names and version, exact disjoint and exhaustive partition ownership, PEP 420 namespace behavior, byte equality, and PyPI size-cap compliance.

## Outcome

Both fresh companion wheels are canonical version `0.1.1`. The manuals wheel
contains exactly 14 tracked payloads under `cadrumo_data/_data/corpus/manuals` and
is 76,656,178 bytes. The official wheel contains exactly 179 tracked payloads
under the `aeat_official` and `normatives` partitions and is 62,537,621 bytes.
Together they exactly cover all 193 tracked split-owned binaries with no overlap,
no `aeat_data` or `aeat` import root, and no namespace initializer.

Every wheel payload byte equals its tracked source. The official wheel owns the
S41-split `.docx` and `.zip` members, one of each. Both wheel member sets equal
their `RECORD` entries and both artifacts remain below the 100 MB publication cap.

## Notes

- `uv run --no-sync pytest -q dev/packaging/tests/test_cadrumo_data_distribution.py` passed all five tests in 12.55 seconds.
- The fresh artifact inspection completed successfully without writing wheel artifacts into the repository.
- No companion defect was found, so this Step changes only its plan checkbox and execution record.
- The unapproved conflicting ADR and unrelated shared-worktree ADR changes were not staged or committed.
