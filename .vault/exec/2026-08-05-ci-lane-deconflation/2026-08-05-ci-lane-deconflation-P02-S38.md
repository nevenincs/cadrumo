---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:2c0b539572d829e90786dd99ca4e294aa1a4a90c74ac35f27b433895bd629806'
step_id: 'S38'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S38 and 2026-08-05-ci-lane-deconflation-plan placeholders are machine-filled by
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
     The export provenance writer recorded as a deliberate superset and ## Scope

- `dev/registry/_provenance_manifest.py`
- `dev/registry/tests/test_export_tree.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# export provenance writer recorded as a deliberate superset

## Scope

- `dev/registry/_provenance_manifest.py`
- `dev/registry/tests/test_export_tree.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Falsify the row's own premise before making the first edit.
- Prove the core hardened tier clobbers an existing target, by execution rather than by reading its docstring.
- Document `_write_canonical_manifest_atomically` as a deliberate superset of that tier, naming `os.link` as the primitive that would make the publish atomic and why it is unavailable here.
- Add the test the refusal never had, with a positive control.
- Rewrite the Step row so the falsified premise cannot survive as an instruction.

## Outcome

Landed as `aea803897f`: two files, 51 insertions, 1 deletion, no foreign paths.

The row originally specified delegating the writer to the shared hardened atomic-write tier, on the stated premise that the core tier already offered the refusal-on-pre-existing behaviour the site open-codes. The premise was false and the row carried it verbatim, so the row itself was rewritten rather than merely re-scoped.

`atomic_write_hardened_bytes` applies `O_EXCL` to its staging tempfile, not to the destination, and publishes with `os.replace`, which overwrites an existing target by definition. That is the entire difference between `os.replace` and `os.rename`. The registry writer refuses a pre-existing target instead, making it a superset of the core tier rather than a redeclaration of it. Delegating would have deleted the refusal, not relocated it.

This was measured, not inferred: two successive hardened writes to one path leave the second payload on disk. The proof was run against the real helper, because a docstring was what produced the wrong reading in the first place.

The rejected delegation's cost was a widened window rather than mere inelegance. Two exists-checks guard this path. The outer one runs before the manifest is built, and building walks and hashes the entire export tree. The inner one runs immediately before the replace. The core helper's write-and-replace is a single opaque call with nowhere to interpose, so delegation could only have kept the outer check, widening the window from microseconds to a full tree walk plus hash.

## Retraction

**This Step's conclusion is withdrawn. Documenting the duplicate was the wrong outcome, and the reasoning that produced it rested on a claim never tested.**

The record above argued that adding a publish-once option to the core tier would make it absorb a compromise rather than gain a primitive, because the only atomic alternative, `os.link`, "needs hardlink support this project's network-share working tree does not reliably provide". **That claim was asserted, never measured, and it is false.** Measured on this working tree: `os.link` links, and a second link to an existing target raises `FileExistsError` atomically.

So the compromise was never forced. Core could gain a genuine publish-once primitive all along, which means the correct outcome was consolidation and not annotation. Leaving a hand-rolled stage-fsync-publish sequence in place with a docstring explaining why is still a parallel write path, and the architecture boundary forbids re-implementing a write path rather than delegating to the single-writer primitive. A prose justification does not convert a duplicate into a design.

The irony is exact and worth keeping: this Step exists because an untested claim in a docstring produced a wrong ruling, and its own conclusion then rested on an untested claim about a filesystem. Proving the clobber by execution was right; not applying the same standard to the constraint that justified leaving the duplicate was the failure.

`core.atomic_write.atomic_write_publish_once_bytes` now carries the guarantee, published with `os.link`. The delegation of this site, and the deletion of its hand-rolled writer, remain outstanding.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The refusal was previously exercised by necessity and asserted by nothing. The emit-level test must unlink the manifest before it can call emit at all, because the render has already written one, so removing the guard would have gone green. The new test uses its first write as a positive control, so a writer that refused unconditionally, or never wrote, cannot pass it, and it also asserts the refused write neither replaced the target nor left its staging tempfile behind.

All four assertions were exercised directly against the real function before committing, alongside the clobber proof. Lint and format pass on both files. The module's execution and hex markers are inherited unchanged and the new test adds no function-level execution marker.

Two mistakes worth carrying forward. A first attempt scaffolded this record through a path that produced a stray top-level filename instead of the feature-folder form, which was removed and redone through the owning verb with a dry-run first. And a commit retry loop tested the exit status of a pipe rather than of the command, so it treated a lock failure as success and exited after one attempt; the corrected loop captured the status directly and landed on the fourth try.

The general lesson this Step records is that a duplication census screens on mechanism, and mechanism cannot separate a site that duplicates the canonical home from a site implementing a wider contract than it. Both produce identical census entries and opposite remedies. Only reading what a site actually guarantees decides which one is in hand, and that has to be done per site. The original instruction was itself an instance of the failure it was meant to correct: a name read as a claim about the wrong object, since the exclusivity flag asserts exclusivity of the staging file, one file away from the one the reader is asking about.
