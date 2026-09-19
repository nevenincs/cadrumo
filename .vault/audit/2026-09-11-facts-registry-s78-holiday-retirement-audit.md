---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:cec8ddc807c609719d23438fc762de903690c3de31e708d6d90a8d84f4b115b8'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` audit: `S78 holiday calendar adapter retirement review`

## Scope

Reviewed S78 retirement of the legal-holiday calendar adapter against the accepted governed-facts decision, campaign plan, discovery research, and adapted-family normalization reference. The review covered authored publication and holiday event facts, raw-source/compiler/provider retirement, the retained deadline facade, focused test coverage, and direct typed parity against the retired 2024 and 2025 sources.

## Findings

### direct-event-parity-gate | medium | The committed direct-facts test does not retain a semantic master for every event

The audit independently confirmed exact typed parity for two publication variants and 34 event variants: identifiers, selectors, temporal windows, dates, names, BOE reference and URL, legal reference, source reference and citation, review state, and ownership all match the retired 2024 and 2025 sources. However, the committed positive test checks a frozen total and resolves most variants against their own authored payload; except for one Madrid event, it has no independent expected master for each event. A same-count substitution or broad value rewrite could therefore pass the normal-path test. The mutation proves one deletion fails, but does not close this semantic-preservation gap.

### s78-retirement-verdict | medium | Not clear pending semantic-master coverage

The raw calendar files, compiler, cache hooks, provider registration, provider constants, and adapter-only tests are removed. The retained deadline facade resolves publication then event facts exclusively through the validated authority. The retired 2026 stub had no BOE URL and the prior compiler explicitly excluded it, so deleting it without authoring an invented fact is correct. The focused suite passed. Clearance is withheld only for the medium direct-event-parity gate finding above.

### direct-event-parity-gate | resolved | Complete direct semantic master and same-count mutation now prove preservation

The replacement direct-facts test declares independent masters for both publication variants and all 34 event variants. It asserts event date and temporal window, jurisdiction and CCAA selectors, name, legal reference, source reference and citation, BOE reference and URL, review state, and authored ownership. Its isolated same-count mutation changes a holiday name while retaining the row total, and the master comparison fails as required. Focused test and lint runs pass.

### s78-retirement-verdict | clear | Holiday adapter retirement is complete and regression-protected

The resolved direct master closes the only medium finding. The adapter/compiler/provider/raw data deletion and direct validated-authority facade remain intact. No compatibility path or unevidenced 2026 calendar was introduced.

## Recommendations

- No further S78 remediation is required. Future holiday publications should be added as source-grounded authored variants and accompanied by their corresponding direct-master entries.
