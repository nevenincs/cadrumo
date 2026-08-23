---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:6ed2c1473f04a5c44835dd3a3e7d6e9b57583d2069a58189953bb4b225ac6001'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
  - "[[2026-08-23-secure-storage-performance-hardening-command-spec-authority-adr]]"
---

# `secure-storage-performance-hardening` audit: `s57 distribution command spec review`

## Scope

Audit S57's direct-wheel, direct-sdist, and sdist-to-wheel content and installed-runtime gate for clean source provenance, ambient-environment isolation, complete distributed specification enrollment, retired artifact exclusion, localized live-tree parity, and role-correct public deferred targets.

## Findings

### s57-distribution-command-spec-review | high | Installed targets were validated without role semantics

The first proof flattened every deferred target and verified only public importability. A handler could resolve to a non-callable or a result-schema target to a non-schema object and still pass; parser, completion, callback, default factory, annotation, click type, and machine-secret model contracts had the same blind spot.

### s57-distribution-command-spec-review | medium | Bare distributed export names escaped discovery

The first module census recognized suffixed `*_COMMAND_SPEC` and `*_COMMAND_SPECS` assignments but not exports named exactly `COMMAND_SPEC` or `COMMAND_SPECS`. A future enrolled module using the bare canonical name could therefore be omitted from an artifact without entering the expected set.

### s57-distribution-command-spec-review | medium | Unknown future deferred-target roles passed silently

After the first remediation, recognized current target roles were validated correctly, but an unrecognized future dataclass field path fell through after public import resolution. That would permit a new role to evade its semantic contract.

### s57-distribution-command-spec-review | medium | Cross-lane parity compared cardinality instead of identities

The remediated lanes initially compared only node and node-kind counts. Independently self-consistent artifacts with equal-sized but different command keys or paths could pass, contrary to the required single command identity set.

## Recommendations

Retain the owning dataclass field path while recursively enumerating installed targets and validate each resolved object by its role: canonical output schema, callable behavior target, concrete type, or Click converter.

Recognize both bare and suffixed CommandSpec export names and prove the archive detector refuses an independently planted omitted module.

Fail closed for every unrecognized deferred-target field path and prove the detector with an independently planted unknown role.

Compare exact sorted spec-key and derived-path projections across all artifact installs and plant equal-cardinality differing identities.

All recommendations were implemented. The final independent convergence review recorded critical 0, high 0, medium 0, and low 0.
