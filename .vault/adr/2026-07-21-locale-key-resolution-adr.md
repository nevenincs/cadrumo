---
tags:
  - '#adr'
  - '#locale-key-resolution'
date: '2026-07-21'
modified: '2026-07-21'
related:
  - "[[2026-07-21-locale-key-resolution-research]]"
  - "[[2026-06-11-modelo-locales-cli-adr]]"
  - "[[2026-05-31-locale-scaffold-fstring-adr]]"
---

# `locale-key-resolution` adr: `registry category locale key resolution` | (**status:** `accepted`)

## Problem Statement

167 registry-declared `categories.registry.*` locale keys resolve in none of the four
locale catalogues, and two independent mechanisms (a mandated renderer-shadowing type
alias and a silent humanize fallback) make the failure invisible to operators, review,
and the existing parity/honesty gates; evidence in
`2026-07-21-locale-key-resolution-research`. A decision is needed on where the display
text lives, when it is resolved, how the discovery and gate gap is closed, and how the
81 verbatim-quote keys — whose source text does not exist anywhere in git — are
handled without fabricating legal evidence.

## Considerations

- Load-time resolution poisons the `lru_cache`d shared profile across operator
  locales (research: shared-cache finding).
- The humanize fallback is a production safety property (a missing string must never
  abort a filing) but a dev/test honesty hole (research: root cause 2).
- The `CasillaDefinition.label` precedent does not transfer: casilla labels are
  legally binding filing text, category display labels are operator convenience
  (research: alternative-considered finding; `modelo-locales-cli-authority`).
- The transaction classifier reasons over Spanish AEAT invoices (research: LLM-hint
  finding).
- Membership-based gating is false-green against the scaffold key-echo placeholder
  (research: membership-vs-resolution finding, commit `3997e39cdf`).
- A translated verbatim quote is a paraphrase presented as authoritative legal
  evidence (`legal-grounding-verifies-bundled-authoritative-corpus` C1;
  `aeat-safety-legal-gates`).
- No CLI verb writes `_intentional_identical.json` while hand-editing it is forbidden
  (`aeat-locales-cli`; research: precedent findings).

## Considered options

- **A. Registry keeps locale keys; catalogues carry the text; read-time resolution
  (chosen).** One display-text mechanism, cache-safe, aligns with the existing locale
  toolchain.
- **B. Move Spanish text into the categories registry TOML (casilla-label analogy).**
  Rejected: forks a second display-text mechanism; the legal-authority rationale that
  justifies it for casillas does not apply to convenience labels.
- **C. Resolve labels at profile load time.** Rejected: bakes one operator's locale
  into the shared cached profile — a cross-locale data bug worse than the defect.
- **D. Gate on catalogue membership.** Rejected: proven false-green — scaffold
  placeholders satisfy membership while operators still receive the humanized
  fallback.
- **E. Include the 81 quote keys in the translation scope.** Rejected: their Spanish
  source text does not exist in git; filling them in under a translation mandate would
  fabricate legal evidence.

## Constraints

- The `as tr` aliasing of `Translatable` is itself contract-mandated
  (`test_translatable_contract`), so the fix must route the categories path onto the
  real renderer without breaking that contract.
- The production humanize fallback must remain: strictness is scoped to dev/test only.
- The 81 quote keys are excluded from translation permanently; they require an
  evidence-sourcing pass with a legal reviewer and are out of this decision's
  execution scope.
- Depends on stable parent surfaces: the locale manager's discovery-source
  architecture, the `_I18N_STRICT_PLACEHOLDERS` ContextVar pattern, and the
  `cadrumo.locales` CLI — all shipped and exercised.

## Implementation

- **Text home and resolution point.** The registry keeps storing locale KEYS; all four
  catalogues carry the text. Consumers resolve through the real renderer at READ time,
  never at load time. The `_category_hint` classifier call site is pinned to
  `locale='es'` regardless of operator locale.
- **Registry key discovery.** A new sibling module
  `src/cadrumo/locales/_registry_scanner.py` exposing `scan_registry_keys()`, wired
  into `LocaleManager.get_codebase_keys()` as a fourth discovery source beside the
  regex, AST, and f-string sources — deliberately not folded into `_ast_scanner.py`
  (per `registry-resolver-family-extraction`). It reads through the domain package's
  public facade on the `_modelo_manager` dev-tooling precedent.
- **Strict missing-key mode.** An `_I18N_STRICT_MISSING_KEYS` ContextVar plus
  `MissingTranslationError`, mirroring the `_I18N_STRICT_PLACEHOLDERS` precedent,
  enabled by the package-scoped autouse fixture. Production keeps the humanizing
  fallback; dev/test refuses loudly.
- **Allowlist verb.** `cadrumo.locales allow-identical <locale> <key> <reason>` writes
  `_intentional_identical.json` through the CLI; `reason` is mandatory and non-empty
  so the allowlist cannot become a mute button.
- **Resolution gate.** The gate asserts resolution through the real renderer using a
  sentinel `default` (the wizard-translations idiom), never catalogue membership.
- **Quote carve-out.** The 81 `.citations.*.quote` keys are excluded from the
  translation scope and routed to a separate evidence-sourcing pass requiring a legal
  reviewer.

## Rationale

Option A is the only shape that keeps one display-text mechanism while being
cache-safe: B forks the mechanism the locale toolchain exists to centralize, and C is
knocked out by the shared-cache cross-locale bug
(`2026-07-21-locale-key-resolution-research`). The strict-mode split (production
fallback, dev/test refusal) preserves the filing-safety property while removing the
exact silence that let 167 keys dangle undetected. The resolution-not-membership gate
is forced by the demonstrated false green of the first gate attempt: membership is
satisfiable by the scaffolder alone, resolution only by an authored value. The quote
carve-out is binding, not advisory — with no source text in git, "translating" the
quotes can only mean fabricating authoritative excerpts, which
`aeat-safety-legal-gates` forbids.

## Consequences

- The acceptance criterion is deliberately inverted from the naive one: 344 red gate
  cases before scaffold remain 344 red immediately after scaffold, because key-echo
  placeholders do not count as resolution; the gate reaches zero only when localizers
  author real values. This is what makes the gate meaningful rather than a check that
  the scaffolder ran.
- Remains open after this decision: the 86 in-scope translations are still to be
  authored (four locales); the 81 quotes await an evidence-sourcing pass with a legal
  reviewer; 167 key-echo placeholder values exist fleet-wide in the catalogues beyond
  the categories namespace and will surface as red gate cases under the resolution
  predicate.
- The strict dev/test mode will expose any OTHER dangling keys the humanize fallback
  currently hides; expect an initial red wave outside the categories namespace that
  must be triaged, not silenced.
- Pinning `_category_hint` to Spanish means classifier prompts never localize; this is
  an accepted trade for classification accuracy on Spanish invoices, and any future
  multilingual-invoice support would need to revisit it by amending this record.
- The new registry scanner adds a TOML-reading discovery source to the locale manager;
  registry schema changes to the categories profiles now have a locale-toolchain
  consumer to keep in step.
