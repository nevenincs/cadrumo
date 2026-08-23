---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:408a3f5598d7bc24584429a8537812b4fc253cf1f656029b702839c21b0e0d92'
step_id: 'S10'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace secure-storage-performance-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S10 and 2026-08-22-secure-storage-performance-hardening-plan placeholders are machine-filled by
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
     The Preserve root help, completion, version, error-envelope, and suggestion contracts through metadata-only traversal and ## Scope

- `src/cadrumo/entrypoints/cli/_common.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Preserve root help, completion, version, error-envelope, and suggestion contracts through metadata-only traversal

## Scope

- `src/cadrumo/entrypoints/cli/_common.py`

## Description

- Carry immutable help, visibility, short-help, and deprecation metadata on the
  S09 lazy registration that already owns each deferred node.
- Render parent help and shell completion directly from registration metadata,
  while retaining eager-node precedence, deterministic ordering, hidden-node
  filtering, and selected-path dependency classification.
- Recover metadata posture from eager callback parameters after Click consumes
  `--help` and `--version` from the invocation remainder.
- Keep parse-time JSON failures off active-profile, sandbox, storage, custody,
  and cryptographic discovery while retaining the shared nullable envelope
  field and resolved command identity.
- Add fresh-process and real-behaviour gates across English and Spanish help,
  version, completion, text and JSON errors, suggestions, materialized-target
  parity, hidden nodes, eager/lazy collisions, and callback error identity.

## Outcome

Root and `app` metadata surfaces now enumerate deferred commands without
materializing their handler siblings. Fresh-process gates observe no registry,
persistence-storage, custody, cryptography, or keyring imports for root help,
`app` help, version, root completion, unknown-command errors, or synonym
suggestions. Lazy metadata is immutable and parity-checked against every
current materialized root and `app` target, so help and visibility drift fail.

Parse-time JSON failures preserve the shared schema, command, status, localized
error, context, and notices shape while reporting the already-nullable
`active_profile` as null. A real callback refusal over a persisted profile still
reports the label `operator`, proving runtime identity was not removed.

Scoped Ruff and `ty` checks passed. The final S10 metadata suite passed 29
tests; the common, lazy-loader, census, and import-contract lane passed another
24. Independent review approved the current implementation with no open
findings after one transient in-flight local-variable defect was corrected and
covered by an eager-shadow regression test.

## Notes

Selected `config --help` still imports its selected eager subtree. That is not
represented as metadata-only here: nested config conversion remains assigned
to `W02.P04.S13`. S10 removes sibling materialization only at boundaries already
registered through the S09 kernel.

A broader concurrent JSON-error run exposed legacy `suggestion`-field and
locale-dependent transaction-refusal expectations outside the S10 diff. Those
failures were not counted as approval evidence; S10's fresh-process envelope
and callback/runtime identity lanes pass directly.
