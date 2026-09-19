---
tags:
  - '#audit'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:e2927447d2c98fb73a141f00cea4e4760afa2e353da785faba26d07473a36fa6'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
  - "[[2026-08-04-modelo-localization-cascade-adr]]"
---

# `modelo-localization-cascade` audit: `execution closeout`

## Scope

This audit reconciles the historical W02-W04 execution rows against the
already-landed root-only Modelo localization cutover. It checks the live
loader/key contracts, the current locale source-aware equality gate, the
absence of revision-local Modelo locale storage, and the retained execution
evidence. It does not reopen a disposable migration application or claim a
new unscoped full-suite run.

## Findings

### execution closeout | low | cutover superseded the temporary emitter

Commit `ced27b5a59` landed the root-only shared-catalogue outcome and removed
the disposable `dev/registry/migration` application and revision-local locale
storage. The live tree has no Modelo `locales` directory under the registry
Modelo corpus, and the new-Modelo scaffold test explicitly refuses to recreate
that layout in `dev/registry/newmodelo/tests/test_manager.py:52-53`. W02-W04
therefore describe a historical application that must not be resurrected just
to satisfy unchecked plan rows.

### execution closeout | low | canonical identity and fallback are live

The production loader derives Modelo, revision, exact Casilla, continuidad,
and alias localization identities without copying natural-language values;
see `src/cadrumo/domain/calculations/registry/_modelo_localization.py:19-119`
and `src/cadrumo/domain/calculations/registry/_loader.py:250-329`. The resolver
tries the requested locale and then the Spanish source across the ordered
identity chain. This satisfies the runtime part of the historical S11 boundary
without retaining an isolated second resolver.

### execution closeout | low | equality adjudication is complete under source semantics

The live status/audit gates report zero pending identical-source values. The
current inventory is 30 Catalan generic allowlisted values, 51 Spanish generic
allowlisted values, 64 Spanish Modelo source values, and 63 Hungarian
allowlisted values, including 33 M100 `Index` entries recorded through the
locale CLI. The explicit adjudication pass returned `UNRESOLVED []`; the
source-aware contracts are in `src/cadrumo/locales/_status.py:93-215` and
`src/cadrumo/tests/test_locale_translation_honesty.py:255-313`.

### execution closeout | low | focused verification is retained

The focused locale translation-honesty, allow-identical, and status tests
passed 15 tests with `-n 0`; the locale audit was healthy for `ca`, `en`, `es`,
and `hu`. A prior bounded Modelo/loader/export/CLI campaign recorded 424
passing tests. The latter is retained as historical evidence and is not
presented as a full-suite claim after concurrent worktree changes.

### execution closeout | low | historical rows require reconciliation, not fake execution

The original W02-W04 rows required an emitter, artifact bundle, isolated
parity resolver, certification gate, refusal handoff, and disposal tests. The
emitter was intentionally discarded by the final cutover, so no post-cutover
artifact bundle or temporary-reader rerun exists. W01 records, the cutover
commit, the live source-aware gates, and this audit preserve the evidence
needed to close those rows as superseded/resolved. This is an explicit
historical reconciliation boundary, not a claim that deleted code still ran.

## Recommendations

1. Mark W02.P03.S06 through W04.P08.S17 resolved by reconciliation to
   `ced27b5a59`, with one Step Record per row and no restoration of
   `dev/registry/migration`.
2. Keep the locale CLI as the only writer for catalogue and intentional-
   identical changes; retain the source-aware equality gate as the ratchet for
   future Modelo enrollment.
3. Treat any future continuity or wording conflict as a bounded manual review
   item in the registry/grounding workflow rather than as duplicated
   revision-local localization data.
