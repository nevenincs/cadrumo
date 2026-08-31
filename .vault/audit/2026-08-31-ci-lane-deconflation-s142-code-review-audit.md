---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:807c249ae841607d8cc8c7762a7a13d5059374e2a68f4ead089d3bbff1838bc8'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# `ci-lane-deconflation` audit: `P05 S142 independent code review`

## Scope

Independent review of P05.S142 at `35c1721dd88e13402506b7e56863821cced75c8f`, with current HEAD confirmed at that revision. Reviewed the CI-lane plan, applicable rules and audit template, S142 execution record, and all nine changed paths. Checked the envelope and verification relocations, direct consumers, old-module routes, peer-hunk exclusion, literal evidence, size, and policy/baseline scope.

## Findings

### s142-code-review | high | The former export module remains a live forwarding facade for moved envelope and verification contracts

`_export.py` imports the moved contracts from `_export_envelope.py` and `_export_verification.py` under their public names. Independent runtime inspection found thirteen old-module bindings, including `FilingEnvelopeOccurrence`, `FilingEnvelopeRenderRequest`, `FilingEnvelopeRenderResult`, `envelope_closer_bytes`, `render_declared_prefix`, `DeclaracionExportFormat`, `DeclaracionExportResult`, `FilingExportConsumedResult`, `FilingExportPayloadConsumer`, `FilingExportValidatedPayload`, `assert_export_artifact_matches_receipt`, `exported_casilla_provenance`, and `verify_written_export`. The execution record's identity smoke proves this forwarding relationship rather than direct canonical ownership. Bind implementation dependencies privately in `_export.py`, update its internal uses, and replace the smoke with assertions that old-module attributes are absent while package/proof/tests import the defining siblings directly.

The envelope and verification modules otherwise contain the extracted definitions and direct consumer updates are present. Diff inspection confirms the separate peer-owned 8-plus/8-minus import-order hunk is not included: S142's import change is confined to removal of moved dependencies and addition of the two siblings. The literal record correctly reports ruff, format, import smoke, marker-free collection of 39 with zero deselection, and three Modelo 200 filing-authority snapshot failures before verifier execution with 36 other tests passing. Module dimensions of 817, 310, and 384 are under the unchanged 1,250 cap; no policy or baseline path changed.

## Recommendations

Resolve the HIGH by retaining only private local aliases for moved definitions in `_export.py`, changing its local use sites, and proving each old public moved route is absent at runtime. Preserve direct imports from `_export_envelope.py` and `_export_verification.py` for all external consumers.
