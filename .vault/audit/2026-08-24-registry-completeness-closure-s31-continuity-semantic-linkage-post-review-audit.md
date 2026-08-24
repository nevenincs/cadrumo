---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:a381d9ecf484bf3a47c15ec564e1df9aa547460b1b5f20baeb43cec970c23df8'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# `registry-completeness-closure` audit: `S31 continuity semantic-linkage post-review`

## Scope

Independent post-review of W03.P05.S31 across `5362ab65399` and its tracking
commit `5e077face7f`. Reviewed the production registry build, continuity
validator, mutation coverage, loaded Modelo 303 and Modelo 390 surfaces, and
the enrolled AEAT record-design evidence. Discovery used semantic search first,
then whole-file and exact-symbol confirmation.

## Findings

### semantic-linkage-build-enrollment | high | The new continuity semantic-linkage check was test-only

`declared_cross_revision_continuity_semantic_linkage_failures` had no production
consumer, so a normal registry build accepted the malformed chain that its unit
test rejected. The correction enrolls the existing canonical check in
`validate_registry_scope` and changes both negative tests to exercise the
registry-build entry point.

### m390-false-repurposed-boundary | high | The 2021 to 2022 Modelo 390 compensation concepts were falsely marked repurposed

The hash-pinned AEAT 2021 and 2022 designs each identify the same annual
compensation concepts at positions 97 and 662. The product changes from an
informational parser observation to a bound filing field. That justified the
existing versioned product roles because the role-consistency gate must refuse
constraint substitution, but it is not a legal-concept change.
`repurposed` would create an unjustified inheritance and translation barrier.
The correction removes the two false evolution records; the existing section
drift remains advisory, because the current evolution vocabulary cannot describe
a same-concept section move without asserting the false barrier.

### m390-own-source-scope | low | The temporal test confused selection authority with cross-boundary evidence

The exact-year selection assertion searched the complete serialized revision,
which also includes family-disposition provenance. That rejected the necessary
2021 source citation in the 2022 continuity disposition despite the revision's
own selection source remaining exactly 2022. The correction asserts exact
record-design ownership on the revision-level `source_refs` surface instead.

### m303-cnae-width-boundary | info | The 2026 barrier has source support

The enrolled 2025 design gives each of the five CNAE cells a width of three and
the reviewed 2026 design gives the same cells width four. The distinct 2026
roles and all 25 non-overlapping `repurposed` edges are therefore retained.

## Recommendations

- Keep semantic-linkage validation at the registry-build boundary; do not add a
  second scanner in an application or export consumer.
- Keep Modelo 390 2021 parsing distinct from filing capability through its
  versioned product role, `authority_grade`, `input_kind`, bindings, and export
  ownership rather than a fabricated legal-concept barrier.
- If future evidence requires same-concept section evolution to become strict,
  obtain an ADR for a new evolution kind; do not reuse `repurposed`.
