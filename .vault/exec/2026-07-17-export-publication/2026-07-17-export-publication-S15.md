---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S15'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace export-publication with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-07-17-export-publication-plan placeholders are machine-filled by
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
     The Expose an operator-invocable export reconciliation verb under the app root so a crashed operator who never exports again can still clear the orphan journal and its cleartext staged temporary file, reporting cleared and failed operations through the typed notice channel, gated on a crash-simulating test driven through the CLI runner and ## Scope

- `src/cadrumo/entrypoints/cli/_app_maintenance.py`
- `src/cadrumo/entrypoints/cli/_app_maintenance_payloads.py`
- `src/cadrumo/entrypoints/cli/tests/test_app_maintenance_export_reconcile.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Expose an operator-invocable export reconciliation verb under the app root so a crashed operator who never exports again can still clear the orphan journal and its cleartext staged temporary file, reporting cleared and failed operations through the typed notice channel, gated on a crash-simulating test driven through the CLI runner

## Scope

- `src/cadrumo/entrypoints/cli/_app_maintenance.py`
- `src/cadrumo/entrypoints/cli/_app_maintenance_payloads.py`
- `src/cadrumo/entrypoints/cli/tests/test_app_maintenance_export_reconcile.py`

## Description

- Add the `maintenance` command family under the app root, with
  `profile-bundle-reconcile` as its first verb over the existing reconciliation
  authority.
- Add an explicit group callback so Typer does not fold the single command into the
  group and mount the verb under the family's own name.
- Declare typed result payloads for the reconciled and isolated halves, registering the
  result schema against the command key.
- Import the payload module at module level so the schema registry is primed when the
  command module loads, matching the sibling diagnostics transport.
- Report both halves through the typed notice channel, including an explicit notice for
  a sweep that found nothing.
- Declare the command family in the operator-surface contract and add the domain member
  it needed.
- Declare the command destructive in the risk table, with the reason recorded beside it.
- Author the locale leaves for all four catalogues through the locales CLI.
- Add four proofs driven through the CLI runner.

## Outcome

The crashed-and-never-exports-again case now has an operator-reachable answer. That case
is the one the pre-flight trigger structurally cannot reach, because the trigger only
fires on a subsequent export.

Placement under the app root is a contention decision made explicit rather than hidden:
the profile family is the semantic home, but that subtree is under active concurrent
work, and the verb is operational recovery over local state, which the app root owns. A
new family rather than an existing one, because the diagnostics family is declared
read-only, and mounting a mutating verb there would have widened the mutability
classification of all five of its existing read-only verbs.

The notice design follows from what the operator needs to decide. An isolated failure is
a warning rather than a refusal, because the rest of the sweep did succeed and the
journal is kept for a retry, but it is loud because each kept journal may still describe
cleartext bundle bytes. A clean sweep reports explicitly, so that nothing-to-recover
cannot be misread as the command not having run.

The destructive declaration follows the act rather than the intent. Removing the
leftover cleartext file is the whole point of the verb, but it is still an unrecoverable
local delete, and classifying it on the benign motive behind it would be the kind of
judgement the risk table exists to stop being implicit.

All four proofs drive the real command through the CLI runner and none calls the
reconciliation directly, so what is proved is that the operator's own invocation clears
the file. Severity is proved to track state rather than being constant: the same command
warns while the unreadable journal is present and goes quiet once it is removed.

## Notes

The curated operator help surface was deliberately not extended. That surface is a
hand-picked shortlist rather than an index -- the sibling diagnostics family is absent
from it too -- and a rarely-needed recovery verb does not belong on it.

The contract declaration was swept into a concurrent campaign's commit while it sat
uncommitted in the shared working tree. The content is intact and correct at the
committed state; the attribution is not, and it is recorded here so the history is
readable.

Two repository-wide gates are red at this commit and neither is owner surface. The
operator-surface drift gate reports a censo sub-verb absent from the profile family's
contract declaration, which is red at the base commit and belongs to the censo surface.
The command-tree cold-start budget test overruns on a loaded machine; the new module was
proved absent from the import graph after the CLI app is constructed, so it contributes
no import cost to that measurement.
