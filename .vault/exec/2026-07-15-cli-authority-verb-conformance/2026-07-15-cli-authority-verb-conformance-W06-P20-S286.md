---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S286'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S286 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Return the operator-output test probe and the wizard results schemas to their owning campaigns, since a test module registering a production schema key breaks 128 assertions and 19 setup errors while untracked and ## Scope

- `src/cadrumo/application/operator_output/`
- `src/cadrumo/application/wizard/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Return the operator-output test probe and the wizard results schemas to their owning campaigns, since a test module registering a production schema key breaks 128 assertions and 19 setup errors while untracked

## Scope

- `src/cadrumo/application/operator_output/`
- `src/cadrumo/application/wizard/`

## Description

- Check whether the two untracked peer modules still exist as described.
- Verify the schema-key leak is closed at the live registry rather than in
  prose.

## Outcome

SATISFIED, by the owning campaigns rather than here, and verified rather than
assumed.

Both modules are now tracked. The wizard results module - whose absence made
the committed wizard package initialiser unimportable from a clean checkout
while importing perfectly for every agent that had the file - is in the index.
I confirmed the consequence directly rather than by file presence: a HEAD-only
tree extracted with `git archive`, containing no untracked files at all,
imports the wizard package, the config-reset and user-profile packages, the
extracted journal repository, and the CLI entrypoint. The shipped CLI is not
broken on a clean checkout.

The operator-output test probe is tracked AND its defect is closed at the
source. The probe result class is now deliberately NOT bound with
`register_schema`, and its docstring states the mechanism exactly: the emit
funnel takes the command path as an opaque string and never consults the schema
registry, so registration contributed nothing to what the tests assert - while
the decorator ran at import time and left a key naming no CLI command in a
process-global registry permanently. The MCP input-schema builder resolves every
registered key against the Typer tree and refuses an unresolvable one, so
importing that module poisoned the build for the whole session.

Verified at the registry rather than by reading the fix: an exact search finds
the probe key only inside that test module's own prose and assertions, and the
live schema registry does not contain it.

Gates at HEAD `ce9df7380ca9e1000d3b977b2c7674869d96438d`:

- Clean-checkout import of the affected packages from a `git archive`
  extraction with zero untracked files: succeeds.
- Probe key present in the live schema registry: False.

## Notes

The referral this row asked for was overtaken by the owners fixing both. Worth
recording how the operator-output half was fixed, because it is the better
remedy: the campaign did not allowlist the key or teach the builder to tolerate
it. It removed the registration, on the reasoning that the registration never
did anything for the test in the first place. A test double reaching into a
production registry is the shape this project forbids, and the fix respects that
rather than negotiating with it.
