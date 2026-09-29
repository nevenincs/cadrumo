---
tags:
  - '#audit'
  - '#file-size-optimisation'
date: '2026-09-29'
modified: '2026-09-29'
body_schema: 'body-v2'
body_hash: 'sha256:eeb873ae450a111ee15785c6c02985f18ab4c846c850ce1d6df8715e72cbbf90'
related:
  - "[[2026-09-29-file-size-optimisation-plan]]"
  - "[[2026-09-29-file-size-optimisation-sequence-golden-storage-adr]]"
---

# `file-size-optimisation` audit: `Sequence golden fingerprints review`

## Scope

Plan-close review of `2026-09-29-file-size-optimisation-plan` (S01 to S04), commits `9c9d295d60` to `46c01eade9`, against `2026-09-29-file-size-optimisation-sequence-golden-storage-adr` and the golden storage amendment of `2026-07-13-docs-cli-sequences-adr`. Covered: the engine (`dev/docs/sequences/`), the directive and build gate (`dev/docs/sequence_directive.py`, `dev/docs/sequence_build_gate.py`), the deploy (`dev/deploy/docs_static_site.py`), their tests, and a shape check of the regenerated goldens. Verdict: pass, with no critical or high finding. The digest compares exactly the form the earlier envelope and text comparison did, and no path renders output that was not compared with the committed golden. Findings below are resolved on this branch unless marked open.

## Findings

### render-masking | medium | rendered JSON was not host-masked (resolved)

`dev/docs/sequence_directive.py` `_output_view` masked the central fields but not host-conditional rows, while the digest covers the host-masked form. A JSON `config check` frame would have rendered the building machine's hardware sentence and free-memory facts, which no gate verifies. Latent: no enrolled sequence renders that frame as JSON. Resolved: the page now renders exactly the form the digest verifies, with a test that a hardware row's detail and free memory do not render while its id and total memory do.

### render-contract-drift | medium | a contract argv edit can pair a new command with old output (open, pre-existing)

`dev/docs/sequence_directive.py` `build_sequence_payload` aligns a record with the authored frames by count and kind only. After editing a contract's argv without refreshing, a build that skipped the check renders the new command line above the previous run's output. The check itself refuses the argv divergence, so the deploy's pre-check blocks publication; the exposure is non-published builds. The same gap existed when output was read from committed goldens. Left open as outside this change's scope.

### detector-teeth | medium | fault-rule wiring was proved by source inspection (resolved)

`dev/docs/sequences/tests/test_recorded_faults.py` asserted that the engine functions call the three fault rules by name. Resolved: two integration tests drive the real engine with a real refusal that echoes a traceback marker and a version literal. Refresh refuses to write a golden. A golden written before the rules existed matches the live run yet still fails the check, and its record lands in the diverged directory.

### test-naming | low | the skipped-build test proved an empty tree, not verified records (resolved)

`dev/docs/tests/test_sequence_build_gate.py`: the test now seeds a golden and its matching record under a contract that cannot execute. Removing the record was confirmed to make the hook run the check and fail.

### stale-prose | low | docstrings described goldens as the rendered artifact (resolved)

`dev/docs/sequences/golden_store.py` version and host-row passages now name records. `dev/docs/sequences/verdict_cache.py` states that a verdict is reused only while every record is verified.

### env-key-drift | low | the skip key was a second literal (resolved)

`dev/docs/i18n.py` now uses `SEQUENCE_CHECK_SKIP_ENV`.

### stderr-version | low | the version token did not resolve on stderr (resolved)

`_stderr_view` now resolves the token like stdout, with a test.

### decision-coverage | low | the plan linked one of three governing decisions (resolved)

The plan's `related:` now lists the docs CLI sequences and deterministic output replay decisions.

### import-load-targets | low | the loadability target inventory was stale (resolved)

The two new engine modules were missing from `dev/quality/metadata/import_load_targets.json`; it was regenerated through `python -m dev.quality.import_load_probe --compile-targets`. The import gate's remaining failure, import-linter unavailable in this environment, is identical at the baseline commit.

## Recommendations

- render-contract-drift: compare each record frame's argv with the authored frame's argv, treating `{placeholder}` tokens as wildcards, in `build_sequence_payload`. If exact alignment proves impractical, a follow-on decision must settle whether a record carries the authored command line.
- The full HTML resolvability sweep now runs the sequence check before it renders, which added about seven minutes to the docs lane on a 4-core host. Sharing records across the lane's workers would recover most of it; that is a test-harness change, not a decision.
