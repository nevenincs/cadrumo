---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S33'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace storage-backend-security-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S33 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The LARGER FOLLOW-UP: enable journal_mode=WAL and synchronous=NORMAL after migrating the ~21 at-rest raw-db test readers to a shared WAL-aware helper that also scans the -wal sidecar and ## Scope

- `src/aeat/adapters/persistence/storage/sql/engine.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# LARGER FOLLOW-UP: enable journal_mode=WAL and synchronous=NORMAL after migrating the ~21 at-rest raw-db test readers to a shared WAL-aware helper that also scans the -wal sidecar

## Scope

- `src/aeat/adapters/persistence/storage/sql/engine.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Add `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL` to the bucket
  engine's connect listener (alongside `foreign_keys` and `busy_timeout`); update
  the docstring from "WAL is a separate larger change" to the WAL rationale.
- Add `read_db_at_rest_bytes(db_path)` to the shared test surface
  (`aeat.tests.secure_sql`): concatenate the main `.db` and its `-wal` sidecar so
  an at-rest plaintext scan covers every committed byte regardless of checkpoint
  state.
- Lock the helper with a deterministic non-tautology unit test (`-wal` sidecar
  bytes must appear in the combined view, absent from a main-only read).
- Migrate every at-rest reader that broke under WAL — the in-context readers that
  scan before the close-checkpoint folds schema+rows into `.db`: the shared
  envelope contract suite plus the submission / attachments / filing(×3) /
  usage_ratios / justificante / workflow-persistence repository tests.
- Verify the remaining at-rest readers are post-dispose (valid via the
  last-connection checkpoint) and non-tautological by their own positive marker
  assertions.

## Outcome

STEP COMPLETE. WAL + `synchronous=NORMAL` are enabled on the bucket engine, with
the at-rest test surface taught to read the `-wal` sidecar.

The earlier "~21 readers" estimate proved pessimistic: routing the **shared**
envelope contract suite (`_repository_test_suite.py`) through the helper covered
most repos at once, leaving **10** standalone in-context readers to migrate. The
empirical method — enable WAL, run the suites, migrate exactly what broke — was
backed by the recognition that a *passing* at-rest test can be tautological under
WAL, so each remaining (passing) reader was checked to carry a positive marker
assertion (`b"secure_objects" in raw`) that only holds for a post-checkpoint read.
The failure mode that defined the migration set was the table-marker assertion
(in WAL even `CREATE TABLE` lives in `-wal` until checkpoint), not the
witness-absence check — which is itself why a naive main-only scan would go
tautological.

Concurrency: readers and the writer no longer block each other (WAL), a real gain
over S10's `busy_timeout` (which only made the loser wait). Durability:
`synchronous=NORMAL` cannot corrupt the database and at most loses the last
transaction on a power crash — acceptable for a local build/export store and never
used for live AEAT submission.

Gates: storage suite + migrated consumers **1181 passed** under WAL; ruff clean;
the at-rest consumer sweeps (outbound/profile/live/observations/modelos/
user-profile) pass under WAL with marker safeguards intact.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The key safety insight: under WAL a raw `.db` scan can pass *tautologically*
(data sits in the `-wal` sidecar), so "the test still passes" is not proof of a
valid at-rest assertion. The `read_db_at_rest_bytes` helper + its non-tautology
unit test + the per-reader marker-assertion audit close that gap. The helper is
the canonical pattern for any future at-rest reader. No production data shape
changed; WAL is a runtime pragma, fully forward (no migration).
