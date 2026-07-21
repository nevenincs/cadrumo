---
tags:
  - '#research'
  - '#locale-key-resolution'
date: '2026-07-21'
modified: '2026-07-21'
related:
  - "[[2026-06-11-modelo-locales-cli-adr]]"
  - "[[2026-05-31-locale-scaffold-fstring-adr]]"
---

# `locale-key-resolution` research: `registry category locale keys never resolve`

Question: why do category display labels surface as raw or half-translated key text
(`'Home office luz'`) in every locale, and what is the full inventory of affected keys?
Conclusion of the evidence pass: 167 registry-declared locale keys resolve in zero of
the four catalogues, the failure is masked by two independent mechanisms (a mandated
type alias that shadows the renderer, and a silent humanize fallback), and the existing
parity/honesty gates are structurally blind to it. The evidence favors keeping keys in
the registry and closing the discovery + gate gap; the ADR settles that ruling.

## Findings

### Inventory: 167 dangling keys, never present in any catalogue

167 locale keys matching `categories.registry.*` are declared across
`src/cadrumo/_data/registry/aeat/categories/profiles/2024.toml`,
`src/cadrumo/_data/registry/aeat/categories/profiles/2025.toml`, and
`src/cadrumo/_data/registry/aeat/categories/profiles/trabajador_del_mar.toml`. None
resolve in any of `src/cadrumo/locales/{en,es,ca,hu}.yml`: the `categories:` root of
each catalogue contains exactly one leaf, the test fixture
`categories.test_profile.display_label_851219`. Git history shows the keys were never
present in any catalogue — this is never-implemented, not a regression.

Partition of the 167: 81 are `.citations.*.quote` keys (verbatim AEAT excerpts), 41
`notes`, 41 `display_label`, 4 cap-variant labels. Verified: 86 in-scope prose keys,
81 quote keys, zero overlap.

### Root cause 1: renderer shadowed by a mandated type alias

`src/cadrumo/domain/categories/_registry.py:21` and
`src/cadrumo/domain/transactions/_llm.py:44` both import
`from ...core.i18n import Translatable as tr`. The `tr(...)` call at
`src/cadrumo/domain/categories/_registry.py:147` therefore invokes the `Translatable`
TYPE — a no-op string wrap — not the renderer. The renderer is never invoked on the
categories path; `resolve_category_profiles(2025)` returns
`display_label='categories.registry.cuotas_colegiales'`, the raw key. The aliasing is
itself mandated by `src/cadrumo/core/i18n/tests/test_translatable_contract.py:73-78`,
which fails any `Translatable` import without `as tr`.

### Root cause 2: silent humanize fallback makes dangling keys invisible

The real renderer `tr()` (`src/cadrumo/core/i18n/_render.py:212`) answers ANY missing
key by humanizing its final segment: `tr('zzz.nonexistent.namespace.foo_bar_baz')`
returns `'Foo bar baz'`. The fallback is owned by `_lookup_translation`
(`src/cadrumo/core/i18n/_render.py:401-416`) via `_humanise_key`
(`src/cadrumo/core/i18n/_render.py:419-434`). The output is plausible enough to
survive review; `categories.registry.home_office_luz` renders as `'Home office luz'` —
half English, half Spanish — identically in all four locales.

### Why the gates never fired

`src/cadrumo/tests/test_parity.py` and `test_locale_translation_honesty.py` pass 34/34
with all 167 keys dangling: parity compares the catalogues against each other and
against codebase-scanned keys, and the registry TOML is not one of the discovery
sources in `LocaleManager.get_codebase_keys()`
(`src/cadrumo/locales/manager.py:130-164` — regex, AST, and f-string sources only).
Any check of the form "did `tr()` return something?" passes trivially against the
humanize fallback.

### Membership is a false-green gate; resolution is the real predicate

A first gate attempt (commit `3997e39cdf`) asserted catalogue MEMBERSHIP. `scaffold`
inserts a missing key with its own dotted path as the value
(`src/cadrumo/locales/manager.py:455`:
`resolved[key] = leaf if leaf is not None else key`), so running scaffold would make
all 86 keys members and turn all 344 test cases green while
`src/cadrumo/core/i18n/_render.py:414-416` still treats `value == key` as a miss and
operators still receive the humanized fallback. Proven on live data:
`aggregation.source_mesh.errors.ambiguous_source_disposition` has MEMBERSHIP=True,
RESOLUTION=UNRESOLVED, and renders as `'Ambiguous source disposition'`; 36 such
key-echo members exist in `en.yml` alone, 167 fleet-wide. The proven idiom for
asserting resolution through the real renderer is a sentinel `default`
(`src/cadrumo/application/wizard/_translations.py:69`).

### The 81 quote keys have no Spanish source text anywhere in git

The `.citations.*.quote` values were key-shaped at their introducing commit
`3dfd17a398` — born as keys, never carrying excerpt text. There is nothing to restore;
an executor told to "fill them in" could only fabricate legal evidence. The
`legal-grounding-verifies-bundled-authoritative-corpus` rule (finding C1: an excerpt
authored from a non-authoritative source, validated by a tautological self-written
cross-check) and `aeat-safety-legal-gates` (ground tax semantics in BOE/AEAT
publications) bear directly on how these keys may be populated.

### Load-time resolution would poison the shared cache

`_load_category_profile_file_cached` is `@lru_cache`
(`src/cadrumo/domain/categories/_registry.py:52`). Resolving labels at load time would
bake one operator's locale into the shared cached profile and serve it to the next
operator in a different locale — a cross-locale data bug worse than the missing
translations. This constrains any fix to read-time resolution.

### The LLM category hint deliberately reads Spanish

`_category_hint` in `src/cadrumo/domain/transactions/_llm.py` feeds the transaction
classifier, which reasons over Spanish AEAT invoices. Following the operator locale
would silently degrade classification accuracy for an operator working in en/ca/hu;
the evidence favors pinning that call site to `locale='es'`.

### Precedents bearing on mechanism placement

- Registry-key discovery as a NEW sibling scanner module rather than a fold-in:
  `_ast_scanner.py`'s contract is Python-AST walking; mixing TOML discovery in is the
  aggregator accretion the `registry-resolver-family-extraction` rule forbids.
- A dev-time locale tool importing a loader from the registry package facade has
  precedent at `src/cadrumo/locales/_modelo_manager.py:22-28`;
  `aeat-registry-authority-flow` governs PRODUCTION consumption, not dev tooling.
- A strict-mode ContextVar with a package-scoped autouse test fixture has precedent in
  `_I18N_STRICT_PLACEHOLDERS` (`src/cadrumo/core/i18n/_render.py:38`, fires at
  `src/cadrumo/core/i18n/_render.py:241`, enabled by
  `src/cadrumo/core/i18n/conftest.py:18-23`).
- No CLI verb writes `_intentional_identical.json` while the `aeat-locales-cli` rule
  forbids hand-editing it — a real tooling gap that strands localizers on the first
  legitimately-identical proper noun.

### Alternative considered by the evidence: Spanish text in registry TOML

The `CasillaDefinition.label` precedent stores legally authoritative Spanish in
registry TOML (per the `modelo-locales-cli-authority` rule). The analogy does not
transfer on the evidence: casilla labels are legally binding filing text; category
display labels are operator convenience. Moving Spanish text into the categories TOML
would fork a second display-text mechanism. The ADR settles the choice.

### Not investigated

The authoring of the 86 missing translations themselves, and the evidence-sourcing
workflow for the 81 quotes (requires a legal reviewer), were out of scope for this
pass.

## Sources

- `src/cadrumo/_data/registry/aeat/categories/profiles/2024.toml`,
  `src/cadrumo/_data/registry/aeat/categories/profiles/2025.toml`,
  `src/cadrumo/_data/registry/aeat/categories/profiles/trabajador_del_mar.toml`
- `src/cadrumo/locales/en.yml`, `src/cadrumo/locales/es.yml`,
  `src/cadrumo/locales/ca.yml`, `src/cadrumo/locales/hu.yml`
- `src/cadrumo/domain/categories/_registry.py:21`,
  `src/cadrumo/domain/categories/_registry.py:52`,
  `src/cadrumo/domain/categories/_registry.py:147`
- `src/cadrumo/domain/transactions/_llm.py:44`
- `src/cadrumo/core/i18n/_render.py:38`, `src/cadrumo/core/i18n/_render.py:212`,
  `src/cadrumo/core/i18n/_render.py:241`, `src/cadrumo/core/i18n/_render.py:401-416`,
  `src/cadrumo/core/i18n/_render.py:414-416`, `src/cadrumo/core/i18n/_render.py:419-434`
- `src/cadrumo/core/i18n/tests/test_translatable_contract.py:73-78`
- `src/cadrumo/core/i18n/conftest.py:18-23`
- `src/cadrumo/locales/manager.py:130-164`, `src/cadrumo/locales/manager.py:455`
- `src/cadrumo/locales/_modelo_manager.py:22-28`
- `src/cadrumo/application/wizard/_translations.py:69`
- `src/cadrumo/tests/test_parity.py`,
  `src/cadrumo/tests/test_locale_translation_honesty.py`
- commits `3dfd17a398` (quote keys born key-shaped), `3997e39cdf` (membership-only
  first gate)

Claims above were rg-confirmed or empirically executed against the live tree by the
coordinating agent on 2026-07-21; this document records that inventory.
