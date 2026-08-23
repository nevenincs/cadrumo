---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:75453e3b6328344c40551371542a7d96473d553e2a57b4415636fa16b391de2a'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
  - "[[2026-08-23-secure-storage-performance-hardening-command-spec-authority-adr]]"
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

# `secure-storage-performance-hardening` audit: `s57 distribution command spec review`

## Scope

Audit S57's direct-wheel, direct-sdist, and sdist-to-wheel content and installed-runtime gate for clean source provenance, ambient-environment isolation, complete distributed specification enrollment, retired artifact exclusion, localized live-tree parity, and role-correct public deferred targets.

## Findings

### s57-distribution-command-spec-review | high | Installed targets were validated without role semantics

The first proof flattened every deferred target and verified only public importability. A handler could resolve to a non-callable or a result-schema target to a non-schema object and still pass; parser, completion, callback, default factory, annotation, click type, and machine-secret model contracts had the same blind spot.

### s57-distribution-command-spec-review | medium | Bare distributed export names escaped discovery

The first module census recognized suffixed `*_COMMAND_SPEC` and `*_COMMAND_SPECS` assignments but not exports named exactly `COMMAND_SPEC` or `COMMAND_SPECS`. A future enrolled module using the bare canonical name could therefore be omitted from an artifact without entering the expected set.

## Recommendations

Retain the owning dataclass field path while recursively enumerating installed targets and validate each resolved object by its role: canonical output schema, callable behavior target, concrete type, or Click converter.

Recognize both bare and suffixed CommandSpec export names and prove the archive detector refuses an independently planted omitted module.

Both recommendations were implemented. Final acceptance remains contingent on the full remediated artifact matrix and independent re-review.
