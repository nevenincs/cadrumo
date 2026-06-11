---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S07'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Add the explicit incremental reindex-before-sweep step to the compile pipeline and a coverage gate asserting every supported-type file under src/aeat/_data is present in the code index metadata, closing the documented watcher staleness hole (ADR D6)

## Scope

- `dev compile pipeline + RAG service discipline`

Implements the ADR D6 index-capability prerequisite: the build-time sweep is
only as good as its index, and the resident service watcher can miss
bulk-written files (the staleness hole). This Step adds the mandated
reindex-before-sweep step and the coverage gate that fails loudly if any
walker-indexable `_data` file is unindexed.

## Description

- Add the reindex-before-sweep helper `_reindex.py` under
  `dev/docs/preprocess/`: `run_incremental_reindex(repo_root, port=8766)`
  delegates an incremental code reindex to the resident service (the
  single-writer store; routing through the service avoids a competing
  in-process Qdrant lock). This is the step the query-vocabulary sweep calls
  first.
- Add the coverage helpers `expected_data_files` (reuse the installed
  walker's own `CodebaseIndexer.scan_files` so the exact gitignore /
  `.vaultragignore` / extension / size / binary filters apply),
  `load_index_meta`, and `missing_data_files`.
- RUN the incremental reindex so the 429 new extraction sidecars enter the
  index.
- Add the coverage gate `test_index_coverage.py`: deterministic, offline
  (reads `code_index_meta.json`, no live search), asserting zero
  walker-indexable `_data` file is absent from the index.
- Verify: ruff check + format clean, `ty check` clean, the gate green over
  the freshly-reindexed metadata.

## Outcome

### The reindex-before-sweep step (location + contract)

`dev/docs/preprocess/_reindex.py`, `run_incremental_reindex(repo_root, *,
port=8766, timeout_s=1800)`. Contract: it shells `vaultspec-rag index --type
code --port 8766` through the resident service (delegated, not in-process -
the local-file Qdrant store is single-writer, so the reindex MUST route
through the service to avoid stranding on the lock), raises `ReindexError` on
non-zero exit, and returns the job-queued acknowledgement. The
query-vocabulary sweep MUST call this first so the index reflects every
freshly-written sidecar before any query runs - this is the
watcher-staleness-hole closure.

### The coverage gate (result + counts)

`dev/docs/preprocess/tests/test_index_coverage.py` (integration + docs
marked, since it reads service-produced index state; no live search, no
self-spawned service). It computes the expected set with the installed
walker's own `CodebaseIndexer.scan_files()` (so the gitignore /
`.vaultragignore` / extension / size / binary filters are byte-identical to
the real index, and any `.vaultragignore` exclusion is honoured - an excluded
raw surface is legitimately absent, not a gap), reads the on-disk
`code_index_meta.json`, and asserts `missing_data_files` is empty.

Counts: **16,801** walker-indexable files under `src/aeat/_data` (including
all **429** `*.extracted.md` extraction sidecars - 219 HTML + 102 workbook +
72 PDF + 36 text-tail - plus the natively-supported corpus TOML/JSON/HTML).
Gate result: GREEN after the reindex - zero supported-type `_data` files
absent from the index metadata. The pre-reindex run confirmed the staleness
hole was real (the 429 newly-written sidecars were absent until the explicit
reindex ran), which is exactly what this Step closes.

### Coordination with the S08 dedup exclusion

The coverage gate reads `.vaultragignore` through `scan_files`, so when S08
adds the raw-`normatives/html/*.html` exclusion, those 219 raw files drop out
of the expected set automatically - the gate treats them as legitimately
absent, not a coverage gap, with no change to the gate code. Their clean
`*.extracted.md` sidecars remain in the expected set and indexed.

## Notes

- No PM wave/phase/step tokens in production code (two `W03` references that
  slipped into docstrings were removed before commit; ADR ids only in this
  exec record). The two `model=None`/`store=None` ty suppressions are
  justified inline (the walker's `scan_files` is documented model/store-free;
  its `__init__` over-types the params), and the one `subprocess` S603
  suppression names the fixed-literal-argv rationale.
- The reindex ran while a peer's full rebuild held the writer lock; because a
  full rebuild reindexes the entire tree (including the new sidecars), the
  coverage gate validates against the rebuilt index. The single-writer
  serialisation is expected service behaviour, not an error.
- Commit discipline: all verification ran first; staging and the commit are a
  single chained `git add ... ; git commit ...` as the very last action,
  explicit paths only, never touching `index.lock`.
