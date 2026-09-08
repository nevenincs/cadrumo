---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:5a26eb4cbd8f8998133b3c4c872e563a049432d7df98926a7d2068090a42051a'
related: []
---

# `reachability-burndown` audit: `s185 cotejo view residue`

## Scope

Independent closure review of Step S185 against the active reachability plan and accepted zero-target decision. The review compared the pre-change and current trees for `cotejo_view_url` and `_COTEJO_QUERY_PATH`, traced the remaining listing/document builders into their production consumers, and exercised recorded-origin, cotejo-landing/read-guard, and PDF-response behavior.

## Findings

No findings. In the current tree, exact search finds neither deleted identity. Historical-tree inspection shows that `_COTEJO_QUERY_PATH` existed only to construct `cotejo_view_url`; its last production consumer was the raw declaration-capture path removed by S184, leaving the builder reachable only from its own recorded-origin test before S185. The retained `COTEJO_PATH_PREFIX` independently owns cotejo landing validation, while `cotejo_document_url` remains called by `capture_row_pdf_artefact` after landed-origin extraction and before the HTTP read guard and PDF-response validator. `listing_url_for` remains called by the live declarations capture flow.

The recorded-origin tests now exercise the two live URL builders across the configured dispatch-origin pool and include a discriminating foreign-origin case. Removing `TestDeclarationsUrlPrimitiveAuthority` deletes the exact-name implementation census without replacing it with another census; the surviving tests assert observable origin behavior. Focused verification of recorded-origin, landing refusal/read guard, and PDF response behavior completed with 81 passing tests.

## Recommendations

Approve Step S185 for closure. No follow-up repair is required by this review.
