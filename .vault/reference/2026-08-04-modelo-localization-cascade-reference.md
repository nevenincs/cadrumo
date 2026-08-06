---
tags:
  - '#reference'
  - '#modelo-localization-cascade'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:a821651f731bda288089d46906a2564d8c63182b6d48350e183c1dccb17128ff'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
---

# `modelo-localization-cascade` reference: `resolved localization extraction contract`

This reference grounds the disposable migration application's resolved
localization extraction in the shipped registry compiler and the accepted
root-only cascade decision.

## Summary

The canonical read path is `load_registry_tree` through the public registry
facade. Directory-mode loading merges revision fragments before
`apply_locales` injects the current locale maps. `CasillaDefinition.get_label`
returns the requested localized label or the official Spanish `label`, while
`get_help` returns the requested localized help or `None`. The locale compiler
first applies Modelo-root keys by `continuidad_id`, then revision-local keys by
`casilla.id`, so the materialized maps are the current resolved behavior rather
than a migration-side reconstruction.

The supported output locale authority is the closed `OutputLanguage` set
`es`, `en`, `ca`, and `hu`. The migration matrix must therefore contain every
supported Modelo/revision/casilla/locale/field coordinate, including explicit
Spanish label fallback and absent help values. Rows are immutable, strictly
validated, sorted by canonical identity, and bound to the S01 corpus
fingerprint. Extraction captures the fingerprint before and after loading and
refuses a mixed snapshot; it performs no writes to the registry or migration
output.

S03 canonical candidates serialize the existing identity contract only:
`modelo/<modelo-id>/casilla/continuidad/<continuidad-id>/<field>` when the
selected occurrence declares a grounded `continuidad_id`, otherwise
`modelo/<modelo-id>/revision/<revision-id>/casilla/<casilla-id>/<field>`.
Locale remains a catalogue dimension on the candidate row, not part of the
semantic key. Repeated ids, printed numbers, labels, and normalized text must
not create provisional continuity identities; that decision belongs to the
later classification step.

S04 classification is structural triage, not semantic promotion. A declared
continuity id is `grounded`; an ungrounded `casilla.id` seen in only one
revision remains `revision_exact`; an ungrounded id repeated across revisions
is `continuity_candidate` with a migration-only provisional group token. The
candidate's S03 exact address remains unchanged in the last case. Values,
labels, printed numbers, and normalized text cannot upgrade a candidate into a
production continuity identity.

S05 binds the classified candidates back to the same corpus fingerprint and uses the
real schema and locale source ownership to seal every observation. A manifest row carries
the raw source value, old resolved value, official-Spanish fallback flag, source scope and
path, source hash, normalized value hash, the existing locale leaf state, measured drift
fields, review status, and an intentionally empty emitted target. Schema fallbacks retain
their exact schema source; absent help has no fabricated source or value. The unresolved
register is a strict subset of continuity candidates and retains only migration-only
provisional group ids.

The current bundled evidence is 126,192 observations: 144 grounded, 32,008
revision-exact, and 94,040 continuity candidates across 2,354 groups. The manifest binds
12,944 distinct source files. Existing leaf classification remains visible: 9,453
mirrored-help values and 48 key echoes are not silently treated as authored translations.
The pre-emission review gate must adjudicate those placeholder classes as delete-versus-
migrate and decide whether year-embedded label families need an explicit parameterized-
label ADR amendment before any emitter hardens their representation.

The governing ADR requires Spanish to remain source-authoritative, forbids
non-Spanish locale fallthrough, and keeps migration-only extraction on the old
reader until parity is proved. The feasibility research records the measured
15,774 casilla occurrences and identifies the current loader as the deterministic
extraction oracle. Later candidate classification and emission stages must
consume this matrix without inferring continuity from repeated identifiers,
labels, or numbers.
