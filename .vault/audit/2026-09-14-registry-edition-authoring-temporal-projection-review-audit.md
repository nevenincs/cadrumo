---
tags:
  - '#audit'
  - '#registry-edition-authoring'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:6fa81e96e40d9fbb5bcccbaf8e5e4b63a110817bd8ffbdc1203e9e8a766ff0e1'
related: []
---

# `registry-edition-authoring` audit: `temporal projection review`

## Scope

The canonical revision selector, snapshot provenance projection, source and indexed consumers, migration diagnostics, and focused temporal behavior matrix were reviewed against the approved registry-edition-authoring work.

## Findings

### authored-anchor-domain | high | Candidate discovery excludes authored anchors outside the support enumeration

The selector enumerates only `support.years` when an exact edition is absent. A supported request can therefore report no eligible source even though the modelo has a compatible authored revision before the global floor. Candidate discovery must inspect the revision selector's own authored coordinates while using the global envelope only to admit or refuse the requested coordinate.

Resolved during review: candidate discovery now derives coordinates from each authored revision selector, and a focused fixture projects a supported 2022 request from an eligible 2020-only source.

### full-authority-parity | medium | Indexed parity remains blocked by an independent strict-lineage failure

The complete temporary authority cannot currently compile because Modelo 100 reports 26 missing strict-continuity retirements on the 2024 to 2025 edge. Focused source-versus-directory selection agrees, but artifact-level parity is not established until that separate lineage-gate work is clean.

## Recommendations

Resolve authored-anchor-domain before closeout and add a below-floor authored-anchor fixture. Re-run temporary source and indexed authority parity after the independent lineage gate is green.
