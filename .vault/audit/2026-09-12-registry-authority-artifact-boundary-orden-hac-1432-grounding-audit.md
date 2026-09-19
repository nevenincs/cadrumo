---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:ff0b3a60a173c98e978473d7b7a008969e0ed9a84c80b3862845ea6e07bb26cd'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
# `registry-authority-artifact-boundary` audit: `Orden HAC/1432/2024 grounding repair`

## Scope

Reviewed only the Orden HAC/1432/2024 entries in `src/cadrumo/_data/registry/aeat/legal/irpf.toml`: the `#art-unico` and `#df-unica` corpus fragments and the article reference's required-text scope. The review independently exercised the production legal-grounding resolver, compared each returned normalized unit with the two-unit extracted sidecar, checked cross-unit exclusion, inspected the bundled BOE temporal metadata, and confirmed the HTML and extracted sidecars have no working-tree diff.

The real resolver accepted both references. `#art-unico` returned a 6,946-character normalized unit containing the amendment title and `EXCESOS ENTREGA ACCIONES EMPRESAS EMERGENTES`, while excluding both `Disposicion final unica` and its `No obstante` carve-out. `#df-unica` returned a distinct 1,449-character normalized unit containing the entry-into-force heading and the 2025 apartado-uno carve-out, while excluding the article's excess-share-delivery field. No `forbidden_text` is declared on either reference; the observed cross-unit exclusions demonstrate that the new anchors do not silently widen required-text matching. `git diff --check` passed for the catalogue file, and `git diff` plus `git status --short` reported no mutation of the HTML, JSON sidecar, or Markdown sidecar.

## Findings

### orden-hac-1432-temporal-metadata | medium | Publication and effective dates precede the official BOE dates by seven days

Both `orden-hac-1432-2024:art-unico` and `orden-hac-1432-2024:df-unica` declared `published_at = 2024-12-12` and `effective_from = 2024-12-13`. The bundled official BOE document identifies 19 December 2024 as its publication date and 20 December 2024 as its entry-into-force date, and the disposition itself says it enters into force the day after publication. The same dates are carried in the extracted unit's official analysis metadata. Those declarations made this authority appear available seven days before publication and legal effect. This did not invalidate the repaired unit anchors, but it violated exact temporal grounding and could admit the references for an `as_of` coordinate in the unsupported interval.

Resolution (2026-09-12): resolved. Both legal references now declare `published_at = 2024-12-19` and `effective_from = 2024-12-20`. Independent re-review loaded the live catalogue, asserted both dates, reran `verify_legal_reference_grounding`, and repeated the cross-unit inclusion and exclusion assertions. Both references passed, with the article and disposition resolving to the same distinct 6,946- and 1,449-character units. No open finding remains in this review scope.

## Recommendations

The legal-reference correction is complete. Reconcile the matching `boe-modelo-190-2024-amendment` source metadata under its owning review because it still repeats the prior publication date; that broader source-record repair remains outside this narrowly scoped audit. No change is recommended for the two repaired fragments or the article required-text phrases: their exact-unit resolution and scope passed.

Associated source-record resolution (2026-09-12): resolved. `boe-modelo-190-2024-amendment` now declares `published_at = 2024-12-19`. Independent re-review loaded the live catalogue, asserted that date, and ran `verify_source_file` against the bundled HTML. Validation passed with 45,812 bytes and SHA-256 `d8f0ced803da91403c8a474d698a047153a6e948a69e2b2cb896093f1239524b`; the corpus and both extracted sidecars remain unmodified.
