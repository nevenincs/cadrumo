---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:d69f9e87206e2197d43b29808958ca683ced616a3edc2332d186e5ededb4851b'
step_id: 'S22'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S22 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Have Terra XHigh add real filesystem and subprocess custody matrices for isolation, calibration, supervision, crash recovery, deletion, and destructive reset and ## Scope

- `src/cadrumo/adapters/persistence/storage/custody/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Terra XHigh add real filesystem and subprocess custody matrices for isolation, calibration, supervision, crash recovery, deletion, and destructive reset

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/tests/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Three real-behaviour matrix modules landed (commit `115f2908c8`, 6 cases, all green): `test_custody_isolation_matrix.py` — A's password envelope refuses B's passphrase at the real unlock door, and A's recovery artifact refuses to republish B's capsule at the identity check while restoring A from the same artifact succeeds (the refusal is the artifact's identity, not a broken path); `test_custody_reset_subprocess_matrix.py` — fresh-interpreter prepare/confirm/delete through the production reset authority, a legacy-member DESTRUCTIVE_RESET refusal in a fresh interpreter, and a crash mid-erase leaving an INCOMPLETE journal that blocks a second destructive sweep and resumes into a VISIBLE PAUSED state naming the drifted target (the fail-closed no-lost-half-state shape); `test_custody_supervision_orphan_matrix.py` — the supervised child's parent killed mid-hash; the next run reaps the orphaned worker tree and re-acquires the lease.

## Notes

The axes already covered at HEAD (supervision lifecycle, calibration, crash recovery at each durable boundary, deletion) were inventoried first and NOT duplicated. The crash-resume case was re-founded on the OBSERVED fail-closed pause (TARGET_STATE_CHANGED naming the drifted target) rather than a forced COMPLETE — the pause IS the designed no-lost-half-state behaviour. Three executor runs died on prompt overflow mid-step; the lead completed grounding, the crash-test re-found and the gate runs.
