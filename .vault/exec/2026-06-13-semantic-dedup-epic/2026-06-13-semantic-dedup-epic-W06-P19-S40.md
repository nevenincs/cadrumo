---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S40'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S40 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The B2 Migrate the borrador/censo/justificante hand-rolled snapshot repos onto SecureSnapshotRepository and ## Scope

- `src/aeat/application/live/_snapshot_base.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# B2 Migrate the borrador/censo/justificante hand-rolled snapshot repos onto SecureSnapshotRepository

## Scope

- `src/aeat/application/live/_snapshot_base.py`

## Description

- Verified `SecureSnapshotRepository` is behaviour-equivalent to the hand-rolled
  borrador/censo repos (decode/version/classification/load-mismatch guards) with
  `domain_label`, and confirmed the one real divergence: the base RAISES on a
  cross-bucket row where the hand-rolled list silently FILTERED.
- borrador: composed the base; preserved class identity, not-found/ambiguous
  messages (factory closures), and `captured_at` list ordering (wrapper re-sort);
  removed `_snapshot_from_record` + orphaned imports/constants. Updated the one
  shared-store filter test to assert the stronger cross-bucket-pollution refusal.
- censo: same composition with a LAZY delegate (built on first use) to preserve
  censo's pre-runtime construction semantics; no test changes needed (no
  shared-store filter test, no mismatch-message assertions).

## Outcome

borrador committed as `3afbf7162` (-64), censo as `4af42a6aa` (-149). Ruff clean;
155 borrador-surface tests + 37 censo tests green, including roundtrip,
not-found/ambiguous/prefix, anti-tautology corruption, and the runtime-migrated
bucket-scoping tests.

## Notes

**B2 COMPLETE (all three repos).** justificante was completed via authorised
cross-commit (`5e53c3629`): its read surface (load/resolve/list/exists)
composes the base, but `save` is kept local because justificante stamps
`written_at = snapshot.captured_at` (not `now()`) — a deliberate divergence the
base does not model. The commit cross-committed a small concurrent peer
docstring addition with operator authorisation. borrador (`3afbf7162`) + censo
(`4af42a6aa`) + justificante (`5e53c3629`); 33 justificante tests green. The
filter->raise behaviour change is production-safe: each bucket owns its encrypted
DB, so cross-bucket rows never occur in production; the divergence only manifests
in an artificial shared-store test, and the raise is the canonical guard
expedientes/notifications already use.
