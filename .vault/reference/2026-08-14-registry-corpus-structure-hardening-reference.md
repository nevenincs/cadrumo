---
tags:
  - '#reference'
  - '#registry-corpus-structure-hardening'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:54482cec9ed17b28233827239088fcf0f3646a4656459f23cd74b2d0eef0401f'
related: []
---

# `registry-corpus-structure-hardening` reference: fail-closed authoring topology

## Summary

The modelo corpus contains 73 modelo directories, 94 revision directories and
17,006 TOML files. All committed revisions use directory-mode fragmentation and
all parsed successfully before hardening.

The compiler validates a fragment's declared revision identity and merged schema,
but historically discovered only recognized globs. Plausible orphan modelo
directories, wrong extensions and nested legal catalogue files could therefore
remain outside validation. Revision fragments were also merged recursively without
checking that their first directory named the section they declared. A misspelled
folder could consequently compile successfully.

The hardened boundary is closed-world. Every filesystem entry below a registry
authoring root is either an explicitly recognized source or a load error. Every
revision fragment lives directly beneath the canonical directory whose name equals
its declared `ModeloRevision` section. Empty fragments are invalid. Legacy folder
aliases are removed from the committed corpus rather than retained as compatibility
surface.

Scalar revision metadata belongs in `revision.toml`. The five M303
`period_selector` fragments are placement drift and move inline without changing
the compiled `ModeloRevision` objects.

Filename ordering is a review aid, not a semantic identifier. Standard fragments use
one zero-padded numeric prefix and hyphenated slug with unique prefixes within a
directory. Source-native casilla identifiers remain valid where the filename reflects
official identity. Loader semantics continue to use deterministic complete-path order
and schema IDs as authority.

Production readiness state is typed. A provisional extraction profile backed only by
synthetic evidence is not a production profile. Legal references distinguish pending,
agent-reviewed and operator-reviewed states; filing-grade verification accepts only
operator-reviewed references and never infers approval from free-text reviewer prose.
Catalogue compilation checks grounding for the whole corpus; operator eligibility is
checked against the exact legal-reference slice selected by a requested snapshot, so
unrelated review backlog cannot disable the global registry authority.
