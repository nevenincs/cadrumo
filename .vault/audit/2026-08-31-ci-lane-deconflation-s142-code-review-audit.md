---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:f7724e87c4b8036b132884ec3247b5c819f4c5ecf0dbb3f19291d7ba95d26c47'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `ci-lane-deconflation` audit: `P05 S142 independent code review`

## Scope

Independent review of P05.S142 at `35c1721dd88e13402506b7e56863821cced75c8f`, with current HEAD confirmed at that revision. Reviewed the CI-lane plan, applicable rules and audit template, S142 execution record, and all nine changed paths. Checked the envelope and verification relocations, direct consumers, old-module routes, peer-hunk exclusion, literal evidence, size, and policy/baseline scope.

## Findings

### s142-code-review | high | The former export module remains a live forwarding facade for moved envelope and verification contracts

`_export.py` imports the moved contracts from `_export_envelope.py` and `_export_verification.py` under their public names. Independent runtime inspection found thirteen old-module bindings, including `FilingEnvelopeOccurrence`, `FilingEnvelopeRenderRequest`, `FilingEnvelopeRenderResult`, `envelope_closer_bytes`, `render_declared_prefix`, `DeclaracionExportFormat`, `DeclaracionExportResult`, `FilingExportConsumedResult`, `FilingExportPayloadConsumer`, `FilingExportValidatedPayload`, `assert_export_artifact_matches_receipt`, `exported_casilla_provenance`, and `verify_written_export`. The execution record's identity smoke proves this forwarding relationship rather than direct canonical ownership. Bind implementation dependencies privately in `_export.py`, update its internal uses, and replace the smoke with assertions that old-module attributes are absent while package/proof/tests import the defining siblings directly.

The envelope and verification modules otherwise contain the extracted definitions and direct consumer updates are present. Diff inspection confirms the separate peer-owned 8-plus/8-minus import-order hunk is not included: S142's import change is confined to removal of moved dependencies and addition of the two siblings. The literal record correctly reports ruff, format, import smoke, marker-free collection of 39 with zero deselection, and three Modelo 200 filing-authority snapshot failures before verifier execution with 36 other tests passing. Module dimensions of 817, 310, and 384 are under the unchanged 1,250 cap; no policy or baseline path changed.

## Recommendations

Resolve the HIGH by retaining only private local aliases for moved definitions in `_export.py`, changing its local use sites, and proving each old public moved route is absent at runtime. Preserve direct imports from `_export_envelope.py` and `_export_verification.py` for all external consumers.
