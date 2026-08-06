---
tags:
  - '#research'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:ab2aa1a2662fd9634856bb1ae07378c57b7cb39c630390f5bb1a349a2e0bc613'
related:
  - "[[2026-08-04-modelo-localization-cascade-adr]]"
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
  - "[[2026-08-04-modelo-localization-cascade-migration-feasibility-research]]"
---

# `modelo-localization-cascade` research: `identical source adjudication`

## Findings

### Source authority | official Spanish is a source, not a translation target

The current contracts distinguish generic application translation from Modelo
presentation text. Generic leaves are compared with English, while Modelo
schema leaves are compared with the mandatory Spanish catalogue. The Spanish
value is therefore the authority-preserving source wording for Modelo and
Casilla labels, titles, and official names; another locale matching that
wording is not evidence that the Spanish source is untranslated. This is
implemented by the source selection and reference-locale classification in
`src/cadrumo/locales/_status.py:37-38, 93-107, 193-200` and asserted by
`src/cadrumo/tests/test_locale_translation_honesty.py:255-265, 270-313`.

### Current equality inventory | every equality has an explicit disposition

The live catalogue was flattened by dotted key and compared against its
appropriate source. The resulting inventory is:

| locale | equal to English | generic allowlisted | Modelo equal to English but Spanish-source | unresolved |
| --- | ---: | ---: | ---: | ---: |
| Catalan | 30 | 30 | 0 | 0 |
| Spanish | 115 | 51 | 64 | 0 |
| Hungarian | 63 | 63 | 0 | 0 |

The 64 Spanish Modelo equalities are source values, not translation debt. They
break down as M100: 10, M131: 3, M200: 1, and M232: 50. The 33 Hungarian
M100 `Index` entries are individually recorded through the locale CLI's
`allow-identical` operation: the established Hungarian loanword is used in
context, while the Spanish authority remains `Índice`. The generic Catalan,
Spanish, and Hungarian equalities retain per-key reasons in
`src/cadrumo/locales/_intentional_identical.json`; no equality is left without
either an allowlist disposition or the official Spanish-source classification.

### Fallback and identity | the runtime already exposes the required chain

The canonical identity functions derive Modelo, revision, exact Casilla,
continuidad, and alias keys from structured IDs in
`src/cadrumo/domain/calculations/registry/_modelo_localization.py:19-92`.
Resolution tries the requested locale across the ordered exact-to-continuidad
keys, then retries the same chain in Spanish, as documented by
`src/cadrumo/domain/calculations/registry/_modelo_localization.py:95-119`.
The loader attaches those identities without copying presentation values in
`src/cadrumo/domain/calculations/registry/_loader.py:250-329`. This means a
mechanical migration can compare identities and values independently; it must
not infer semantic sameness from English equality alone.

### Verification | bounded gates are green

The current locale status reports zero `identical_pending` entries for
`ca.yml`, `en.yml`, `es.yml`, and `hu.yml`, and the locale audit reports all
four catalogues as healthy. The focused locale gate covering translation
honesty, intentional-identical handling, and status contracts passed 15 tests
with `-n 0`. The explicit equality adjudication pass returned `UNRESOLVED []`.
These checks were run against the shared worktree on 2026-08-05; the broader
Modelo/loader/export/CLI campaign previously recorded 424 passing tests, but
that broader count is historical evidence rather than a claim about an
unscoped full-suite run after every concurrent worktree change.

### Migration boundary | extraction is mechanical; semantic review is narrow

The registry and locale-key scanners expose structured IDs and dotted leaves,
and the new-Modelo scaffold refuses to create revision-local locale storage;
see `src/cadrumo/locales/_registry_scanner.py:62-78`,
`src/cadrumo/locales/manager.py:266-399`, and
`dev/registry/newmodelo/tests/test_manager.py:52-53`. A disposable extractor
can therefore emit a deliberately reviewable register, detect duplicate
identity/value conflicts, derive revision overlays, and compare the proposed
resolution to the current loader. Manual review remains necessary only for
conflicting values that share an identity, missing or ambiguous continuidad
evidence, explicit retirements/tombstones, and wording decisions that cannot
be established from the structured source. Identical Spanish wording in a
non-Spanish locale is not itself a manual conflict when the locale has a
documented linguistic disposition.

The old audit's 14 Catalan, 64 Spanish, and 44 Hungarian equality counts are
not the current authority for this question: they predate source-aware Modelo
classification and were observed amid concurrent locale-key migration. The
source-aware status and explicit adjudication above are the re-fetchable
current evidence.

What was not investigated here is a fresh official AEAT/BOE semantic
adjudication of every continuity chain; this record evaluates the live schema
and the migration gates, not the legal identity of an ungrounded Casilla.

## Sources

* `src/cadrumo/locales/_status.py:37-38, 93-107, 153-215`
* `src/cadrumo/tests/test_locale_translation_honesty.py:255-313`
* `src/cadrumo/domain/calculations/registry/_modelo_localization.py:19-119`
* `src/cadrumo/domain/calculations/registry/_loader.py:250-329`
* `src/cadrumo/locales/_registry_scanner.py:62-78`
* `src/cadrumo/locales/manager.py:266-399`
* `dev/registry/newmodelo/tests/test_manager.py:52-53`
* `src/cadrumo/locales/_intentional_identical.json`
* `ced27b5a59` — root-only Modelo localization cutover and disposal of the
  temporary migration application.
