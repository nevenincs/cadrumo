---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-14'
modified: '2026-07-17'
body_hash: 'sha256:5d728b78f00de36d02e615317ff2f8d87ad5e5192fde7faaa8da517437cfe3c9'
step_id: 'S75'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
  - "[[2026-07-14-cadrumo-product-rename-audit]]"
---

# Render and inspect the complete documentation site for stale product identity and broken references

## Scope

- `built documentation site`

## Description

- Run the mandatory full nitpicky Sphinx build gate (`uv run --no-sync pytest dev/docs/tests/test_docs_build.py -q`) against the complete documentation tree at HEAD, after S68-S74's content and generated-reference changes had landed.
- Confirm the run reflects the current tree rather than a stale process by checking live worker activity while it ran (this shared worktree was carrying heavy concurrent campaign load, extending the build's wall-clock time well past the ~200-300 second runs the individual S68/S69/S72 audits measured in isolation).

## Outcome

19 tests passed in 1181.70s (0:19:41). The full warnings-as-errors nitpicky Sphinx build completes clean across the rewritten `README.md`, `RELEASING.md`, `docs/how-to`, `docs/architecture/index.md`, `docs/conf.py`/`docs/_static` site identity, and the regenerated API reference tree — no stale product identity or broken cross-reference surfaced. Combined with S74's clean `apidocs scaffold --check`, the phase's two mechanical gates both pass.

## Notes

The extended wall-clock time (~20 minutes versus the individually-measured ~3-5 minutes) is attributed to concurrent load from other active campaigns on this shared worktree machine (over 200 live `python.exe` processes observed during the run), not a build regression; the run completed with exit code 0 and no error output.
