---
tags:
  - '#exec'
  - '#test-harness-honesty'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S13'
related:
  - "[[2026-07-25-test-harness-honesty-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace test-harness-honesty with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S13 and 2026-07-25-test-harness-honesty-plan placeholders are machine-filled by
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
     The Close the stale-fixture family by requiring a test to bind a persisted record's version constant rather than restate its value, since two bucket-manifest fixtures kept writing schema_version=1 after the durability floor moved to 2 and neither failed loudly because both read paths treat the resulting raise as an ordinary degraded state, and the gate found five further stale sites on its first run and ## Scope

- `src/cadrumo/tests/test_persisted_version_literal_inventory.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Close the stale-fixture family by requiring a test to bind a persisted record's version constant rather than restate its value, since two bucket-manifest fixtures kept writing schema_version=1 after the durability floor moved to 2 and neither failed loudly because both read paths treat the resulting raise as an ordinary degraded state, and the gate found five further stale sites on its first run

## Scope

- `src/cadrumo/tests/test_persisted_version_literal_inventory.py`

## Description

- Enrol five persisted record types in a `(class, field) -> constant` table, verifying both anchors resolve live so a rename cannot leave the table enforcing nothing.
- Detect any test construction of an enrolled record passing an integer literal for its version field, and demand the constant instead.
- Bind seven live sites, all `BucketManifest`: four were still writing `1`, below the floor the reader enforces.
- Prove the detector discriminates by feeding it synthetic violating and bound source, and prove it stays silent on an unenrolled version field.
- Ship the exemption mechanism empty, keyed by `(path, enclosing function)` rather than line number, guarded so an entry naming no live site fails.

## Outcome

The gate ships green with seven fixtures bound. Its value was demonstrated on the first run: it found five stale fixtures beyond the two whose symptoms had already been chased down by hand.

The defect class it closes is one where the symptom never names its cause. A fixture restates a version, the format moves, and the read path raises -- but the callers that read these records treat a raise as an ordinary degraded state, because for a genuinely missing or torn record degrading IS correct. So the sandbox indicator stopped appearing, and a health probe answered `manifest_unreadable` instead of reaching the record its test was about, and both looked like ordinary behaviour rather than a broken fixture.

Scoping is the part most likely to be got wrong later. Only a version owned by a single canonical constant is enrolled, because only such a version has something to bind to. Per-namespace secure-object versions vary by namespace, the user-profile record carries an inline field default, and the manifest KDF parameter version is argon2's own protocol number rather than a schema version at all. A test pins that last exclusion, so the gate cannot drift into demanding a binding that does not exist and training authors to read its failures as noise.

Three of the five enrolled records have fields that default to their constant today and cannot currently drift. They are enrolled anyway, at birth: making such a field required later would open the same hole with no gate watching it.

## Notes

Verification: reverting one bound fixture to its literal reds the gate naming that exact site and enclosing function, and restoring from a copy returns it to green. The gate was not assumed to bite.

The live-exemption guard caught a speculative entry on its first run. The entry named a function that does not exist, written from an assumption about how the manifest lineage probes write off-version records. They in fact derive their versions from the constant they test against, so no exemption was needed at all and the table ships empty. The guard earned its place before the gate had any users.

RECOMMENDED NEXT MOVE, not built. Split the version-floor breach out of the general storage validation error as a subclass. Every existing handler keeps catching it, so behaviour is unchanged everywhere and nothing reds, but a targeted gate can then assert that a below-floor record raises specifically that class. Today one discriminable and always-a-defect condition hides inside an error class that also carries conditions where degrading is correct, which is why 43 production handlers cannot tell them apart. That is the complement to this gate: this one stops a stale fixture being written, the subclass would stop a stale record being swallowed.

PROCESS FINDING, worth outliving this campaign. Two gate-overlap violations were introduced and caught during this work, and NEITHER was visible to the scoped test selection being used to verify between commits. A promotion made to satisfy one gate opened a fresh private cross-package import flagged by another, and a seam built to satisfy a third violated an architectural gate that forbids its shape outright. Both surfaced only on a full-tree run. The scoped run answers "did I fix what I set out to fix"; it cannot answer "did I break something adjacent", and in a repository whose gates deliberately overlap those are different questions. A full-tree run belongs before the commit that claims a gate is closed, not only at the end of a session.
