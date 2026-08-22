---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:d5461bac1dd2a1f3aaca437ed31813f55035ce537df7875b8114bb7a28f62ef2'
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

# `secure-storage-performance-hardening` audit: `W01.P01.S48 config execution-policy review`

## Scope

Reviewed the S48 config enrollment against the accepted command-scoped loading
decision, live census contract, CLI behavior, import-light metadata boundary,
and the destructive/handoff safety judgments that the later consumer migration
must preserve.

## Findings

### config-risk-retirement-order | high | Removing config rows before consumer migration breaks HITL safety

The initial Step combined callback enrollment with removal of config rows from
the legacy risk table. Direct execution proved the current operator consumers
and their destructive-versus-archive gate still read those rows. The plan was
revised canonically: S48 owns enrollment only, while S52 explicitly migrates the
consumers before removing all legacy rows and deleting the table. The new config
test does not import or preserve the legacy path table as an oracle.

### specialised-authority-underdeclaration | high | Coarse custody presets hid registry, calculation, browser, and network entry

The first pass classified registry integrity, profile preflight, browser
connectivity, live censal pull, runtime-model pull, and Google calculation sync
through broad custody or Google presets. Specialised immutable declarations now
carry the actual authorities and effects, and representative live-census tests
assert registry/calculation, browser/network, and Google/calculation/filing
closure.

### locale-dependent-parity-assertion | medium | English error prose made the focused gate locale-sensitive

The first group-semantic test required an English missing-command fragment even
though the active locale renders other prose. The gate now asserts stable exit
status and usage shape, alongside successful help and leaf-help dispatch.

## Recommendations

Keep S52 ordered as declared: migrate all risk consumers to live-node metadata,
prove destructive/handoff/live-write parity, then remove all legacy rows and
the keyed table in the same Step. Later import-family gates should use the
specialised authority specimens added here as minimum coverage and expand from
the live exact set rather than a fixed verb count.
