---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:7c7c239a096c552f29358fcca78f8508e4c91587b879838c318b388b31a43699'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace secure-storage-performance-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `secure-storage-performance-hardening` audit: `W02.P03.S10 metadata traversal review`

## Scope

Independent read-only review of `W02.P03.S10` against the accepted
command-scoped-loading ADR, the live-census reference, the S09 lazy-node
kernel, and the CLI and quality-gate rules. The review covered
`_command_suggestions.py`, `_common.py`, `_terminal_errors.py`, the root
registration in `__init__.py`, and the focused metadata traversal tests.

The audit exercised root and `app` help, version, unknown-command and synonym
resolution, text and JSON parse failures, direct shell completion, hidden lazy
nodes, eager/lazy name collisions, materialized-target metadata parity, and
fresh-process import observations. It specifically checked that metadata
enumeration does not materialize sibling handlers or import registry,
persistence storage, custody, cryptography, or keyring authorities. Selected
`config` traversal remains an explicit dependency of `W02.P04.S13`; S10 does
not represent it as already converted.

## Findings

No open findings. An in-flight review run exposed an undefined
`eager_names` local in `CadrumoTyperGroup.format_commands`; the implementation
owner corrected it before this audit closed, added eager-shadow parity
coverage, and the current focused lane passes. The final implementation gives
eager registrations the same precedence in help, completion, and dispatch;
preserves Click short-help, hidden, and deprecation semantics from immutable
lazy metadata; and retains deterministic command ordering without duplicates.

Parse-time JSON failures now intentionally emit `active_profile: null` rather
than entering profile/storage discovery to decorate an error produced before a
handler executes. Callback and runtime refusals retain real active-profile and
resolved-command identity. This is an honest capability reduction rather than
an envelope-shape change: the field remains present and nullable, while the
shared schema, status, error code, localized message and suggestion path remain
on the canonical error spine.

Current verification evidence: 24 focused suggestion/metadata tests passed;
17 fresh-process metadata/envelope tests passed; the four targeted root/app
help-shape tests passed under the English locale; scoped Ruff and `ty` passed;
and direct fresh processes for root and `app` help imported none of the lazy
config, ledger, modelo, or registry handler modules. The broader error-contract
lane has concurrent failures unrelated to this diff (legacy `suggestion`
expectations and locale-dependent text assertions); those failures were not
used as evidence for S10 approval.

## Recommendations

Approve `W02.P03.S10`. Keep `W02.P04.S13` open until selected `config` paths use
nested registration metadata; S10 proves metadata-only traversal at the
already-lazy root and `app` boundary and does not narrow that later obligation.
