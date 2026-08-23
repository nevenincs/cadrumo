---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:8f1076e12bc6729a7c388e8bb903281bec4749e9c9922f59bdd5899630367170'
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

# `secure-storage-performance-hardening` audit: `s58 sealed command spec cohort review`

## Scope

Audited the effective S58 release-cohort change against the accepted command-spec authority decision: installed
projection, provenance, deferred targets, localization, selected-path imports, downstream consumers, forbidden
artifacts, and the build-output-only boundary.

## Findings

### s58-sealed-command-spec-cohort-review | high | attestation replay was not bound to source and artifacts

Remediated by binding the lowercase Git commit, exact Git-archive digest, root wheel and sdist digests, normalized
member projection, and complete envelope. The loader independently rehashes and refuses every mismatch.

### s58-sealed-command-spec-cohort-review | high | deferred targets lacked executable role proof

Remediated by recursively resolving public targets and validating schema subclasses, callables, annotations, models,
Click types, and unknown-role refusal. Missing, private, wrong-kind, and unknown-role plantings fail.

### s58-sealed-command-spec-cohort-review | high | locale projection omitted localized values

Remediated by hashing stable serialized localized values for every graph translation field and locale. A same-key
changed-value planting changes the digest.

### s58-sealed-command-spec-cohort-review | high | downstream enrollment was hand-maintained and bypassable

Remediated by canonical verification in Scoop host and container routes, canonical loading in readiness, dynamic
Python consumer discovery, import and assignment alias propagation, and a planted alias bypass detector.

### s58-sealed-command-spec-cohort-review | medium | selected-path budgets did not execute installed help

Remediated with separate isolated `python -S` processes for projection and each selected installed help path. Exact
named module deltas, declared performance classes, the root assembler baseline, and zero foreign handlers are sealed.

### s58-sealed-command-spec-cohort-review | medium | forbidden artifacts omitted the source distribution

Remediated by inventorying and binding normalized wheel and sdist members and refusing both former JSON authorities
and deleted generator names. A clean-wheel and dirty-sdist planting proves the sdist detector.

## Recommendations

Retain the strict schema without compatibility parsing. Keep the attestation exclusively as untracked release/build
output. Require new release consumers and deferred target roles to enroll dynamically or fail closed.
