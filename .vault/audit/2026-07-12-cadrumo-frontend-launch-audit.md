---
tags:
  - '#audit'
  - '#cadrumo-frontend-launch'
date: '2026-07-12'
modified: '2026-07-17'
related: []
---

# `cadrumo-frontend-launch` audit: `campaign close honesty review`

## Scope

Campaign-close honesty review, mandated by the campaign-close-honesty-review
rule, over the Cadrumo marketing-frontend campaign: the `frontend/` landing
page (Figma-derived, responsive, en/es/ca localization, legal page, animated
404), the static-site deploy surface (`dev/deploy/frontend_static_site.py`,
`infra/docs-static-site.yaml`, justfile targets), the docs rebrand and the new
agent-connection how-to, and the live delivery at `cadrumo.neve.md`. The
review ran in fresh context via an independent read-only reviewer over the
campaign commit range (`4e588a493d`..`2c31ea7cb5`); the coordinator then
network-verified the externally-dependent findings (PyPI state, marketplace
repository, docs sitemap).

## Findings

### honesty-review | high | Packaging maturity classifier contradicts every human-facing beta claim

`pyproject.toml` declares `Development Status :: 3 - Alpha` (confirmed live on
the published PyPI page) while the landing page locales, `docs/index.md`, the
legal disclaimer, and `README.md` all state beta. The campaign claim
"maturity aligned to beta" did not reach the canonical package metadata.

### honesty-review | high | Published version chain is coherent but behind source

PyPI's latest `aeat-cli` is 0.1.1; source is at 0.2.0 (unreleased). The
`nevenincs/neve-marketplace` repository exists (HTTP 200) and its served
plugin pins `aeat-cli[agent]==0.1.1`, which matches the actual PyPI latest,
so the documented install chain works today. The risk is procedural: nothing
gates the pin, the proof doc, and the release version to move in lockstep.

### honesty-review | high | LSSI-CE art. 10 identification is incomplete and mislabels a natural person

The legal page invokes Article 10 of Ley 34/2002 while omitting the
provider's registered address and NIF, and calls an individual "the legal
entity". Blocked on operator-supplied personal data; the interim fix is to
soften the completeness assertion and correct the entity wording.

### honesty-review | high | The frontend deploy script has zero tests

`dev/deploy/frontend_static_site.py` writes to the shared docs bucket with
`--delete`; the `docs/*` protection guard, artifact validation, and
invalidation parsing are untested, while the sibling docs publisher is
tested. A guard regression would silently destroy the deployed docs.

### honesty-review | medium | "No access logging" legal claim is true at HEAD but unprovable from the template

The CloudFormation template configures no CloudFront or S3 logging, so the
claim is consistent, but account-level toggles outside infra-as-code could
falsify it. Requires a pre-publish operator re-verification note.

### honesty-review | medium | Shipped interactive features lack behavioral tests

Scroll effects (progress bar, header elevation, parallax), the 404 page's
inline cookie localizer, and the JSON-LD/sitemap/robots content have no
regression tests.

### honesty-review | medium | Crawler-visible metadata is English-only

Single-URL cookie switching means es/ca copy is invisible to indexers;
hreflang honestly declares only `en`/`x-default`. Known limitation of the
chosen architecture; path-prefixed locales would be the structural fix.

### honesty-review | low | Shared distribution serves the marketing 404 for docs errors and masks 403 as 404

Deliberate for a private origin; recorded here as a conscious sign-off.

### honesty-review | low | Uniform 300s cache-control on content-hashed assets; redundant assets invalidation

Fingerprinted `/assets/*` could carry immutable long cache; the `/assets/*`
invalidation line is then unnecessary.

### honesty-review | low | Ignore-rule and error-string drift around the deploy build directory

The deploy builds to `frontend/build/`, ignored only via the generic Python
`build/` rule rather than the dedicated frontend block, and the artifact
validation error message still says `dist/assets/`.

### honesty-review | low | robots.txt docs-sitemap reference verified live

`https://cadrumo.neve.md/docs/sitemap.xml` returns 200; the reference is
correct. Closed at review time.

### honesty-review | low | Figma parity claims are out-of-band

The Figma file is external to the repository; parity claims were exercised
during the campaign with screenshot validation but cannot be re-verified
from HEAD. Inherent to the medium.

### honesty-review | closure | Operator disposition and closures

Operator ruling: NIF and address stay private; every other recommendation
approved. Closed accordingly: the packaging classifier moved to Beta; the
legal identity paragraphs (three locales, plus the Figma legal frame) now
name a natural person and assert Article 10 only "to the extent it applies
to a non-commercial project", offering further identification on request;
behavioral tests landed for the scroll effects (header elevation, progress
bar, parallax), the 404 inline localizer (en/es/ca via real script
execution in jsdom), and the landing head metadata (JSON-LD, canonical,
hreflang); the `packaging/mcpb/manifest.json` version was aligned to the
package version with a lockstep gate in `test_build.py`. Deferred to the
tree-settling pass because the owning files are under a concurrent
session's live edit: the cache-control split for hashed assets, the
`dist/assets` error-string and gitignore hardening (already fixed in the
working tree), and the docs copyright footer (watcher armed). The es/ca
indexability limitation is accepted as a documented consequence of
single-URL cookie switching.

## Recommendations

Close in-repo now: bump the trove classifier to Beta (or downgrade the copy),
add `/frontend/build/` to the frontend ignore block and fix the stale
`dist/assets/` error string, and add a unit test module for
`frontend_static_site.py` covering the docs-prefix guard and artifact
validation. Blocked on operator input: LSSI art. 10 NIF and address (and the
"legal entity" wording), and a decision on path-prefixed locales for
indexable es/ca content. Procedural: re-verify the no-logging claim against
the live distribution before each publish, and regenerate the marketplace pin
plus proof doc in lockstep with every version release. The campaign is not
structurally complete until the in-repo items land and the operator-gated
items are answered or formally deferred.
