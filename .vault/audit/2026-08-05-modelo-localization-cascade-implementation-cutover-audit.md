---
tags:
  - '#audit'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:efc908fa7e3e3ffbbe586d00e01a5de7c3ca5e5f8e2f7fcae8478b96a9c9b018'
related:
  - "[[2026-08-04-modelo-localization-cascade-adr]]"
  - "[[2026-08-04-modelo-localization-cascade-research]]"
---



# `modelo-localization-cascade` audit: `Implementation cutover review`

## Scope

Review the accepted root-only Modelo localization cutover against the
localization cascade ADR and its migration research. The review covers the
shared key builders and resolver, revision loader enrollment, source schema
models, construct and alias presentation surfaces, shared locale catalogues,
old-layout removal, and the live loader, export, CLI, and parity gates. The
audit deliberately excludes unrelated concurrent calculation, documentation,
and Vault work.

## Findings

### source-schema-cutover | low | Revision Modelo data no longer carries localizable natural-language fields

The source TOML tree contains no remaining `title`, `official_name`, or
`label` assignments in the Modelo catalogue, and no Modelo-local `locales`
directories remain. `ConstructDefinition`, `CasillaAlias`, `CasillaDefinition`,
`ModeloRevision`, and `ModeloDefinition` retain localization identities rather
than authored text. Spanish and non-Spanish resolution happens at the shared
catalogue boundary, so the source schema remains language-independent.

### identity-and-fallback | low | Derived keys and fallback ordering are deterministic

The loader derives Modelo, revision, construct, casilla, continuity, and alias
occurrence identities from structural coordinates. `resolve_modelo_localization`
exhausts the requested locale's ordered identity candidates before falling back
to the official Spanish source; a present `null` leaf does not silently select
another identity at the same locale, but does permit the documented Spanish
fallback. Encoded identity segments are reversible and prevent collisions.

### construct-alias-enrollment | low | The final residual presentation fields use the same cascade

Construct titles and alias labels were enrolled after the initial casilla and
revision cutover. Construct identity uses the construct id within its revision;
alias identity uses the containing casilla and alias occurrence. The loader
does not depend on source text being present, and validators report localization
identities rather than resolving natural language in arbitrary validation
contexts.

### output-boundary | low | Source dumps remain localization-key based while projections resolve text

Localization identity fields are excluded from source-schema dumps and are
re-injected by the loader's structural enrollment path when a fragment is
round-tripped. Runtime properties such as `get_label`, `get_help`, `get_title`,
and `ResolvedConstruct.get_title` resolve through the shared manager. No direct
consumer search found a remaining Modelo-local reader or a legacy Modelo locale
manager/CLI path. The focused export and CLI integrations passed.

### absent-leaf-honesty | medium | Optional non-Spanish leaves are now classified correctly but translation debt remains

The honesty gate was corrected so `null` leaves—valid absent optional
translations in the collapsed Modelo catalogue—are not counted as authored
English echoes. With that correction, the gate reports 14 Catalan, 64 Spanish,
and 44 Hungarian non-null values identical to English outside the current
allowlist. The Spanish set includes the Modelo 232 related-party labels that
are authored in English. These are not safe for automatic allowlisting: they
require manual/official translation adjudication, while Spanish remains the
verbatim regulatory source. No translation values were invented in this
cutover.

### focused-verification | low | Live behavior gates pass within the migration-owned boundary

The loader fragment, construct closure, locale CLI, locale parity, Modelo
export, query-consumer, and registry schema/data-type tests passed in focused
runs. Ruff and targeted basedpyright passed for the null-aware honesty gate.
The full repository suite was not used as a completion claim because the
shared worktree contains active peer changes and the honesty gate still
reports the manual translation boundary above.

## Recommendations

Resolve the 14/64/44 non-null identical values through a separate locale
adjudication pass, prioritizing the English-labelled Spanish Modelo 232 keys;
allowlist only values with an explicit semantic reason. Keep optional missing
translations as `null` and preserve the Spanish-source fallback contract.

Keep the source-schema deletion gate in place: new natural-language fields in
Modelo revision data must be rejected unless they are localization identities
enrolled in the shared catalogue. Once concurrent peer work settles, rerun the
full locale parity and end-to-end export/CLI gates and close the remaining
manual translation findings before declaring the campaign complete.
