---
tags:
  - '#adr'
  - '#license-posture'
date: '2026-07-12'
modified: '2026-07-17'
body_hash: 'sha256:8112ab749d714d5438cc6234c4e82d4d16b40d103c2d80c66f99fe15fa6f72ac'
related:
  - "[[2026-07-12-license-posture-research]]"
---

# `license-posture` adr: `licence posture: retain Apache-2.0 with copyleft and corpus-reuse containment` | (**status:** `accepted`)

## Problem Statement

The distribution bundles other projects and content: a 111-distribution
Python dependency closure across core and capability extras, a frontend
bundle with self-hosted typefaces, and official AEAT/BOE public-sector
documents shipped as data companions. The operator directed a reassessment
of the legal posture and licence — "Apache 2 or stricter that we can legally
apply" — with the code open source but the brand held privately. Until this
pass the posture had three defects: a dead EUPL-1.1 core dependency
(`formulas`), an undisclosed GPL-3.0 core dependency (`ofxtools`), and data
companions stamping Apache-2.0 over official documents the project cannot
relicense.

## Considerations

- What each channel actually distributes determines where copyleft can
  attach: the PyPI wheels contain first-party code only, and the MCP bundle
  launches via `uvx`, vendoring nothing.
- Apache-2.0 section 6 grants no trademark rights — the mechanism that keeps
  "Cadrumo" and "neve.md" private in an open-source codebase.
- Authorship is concentrated in Gergely Wootsch (14,300 of ~14,314 commits;
  the remainder agent-generated under his direction), so relicensing is
  mechanically available; the question is desirability, not feasibility.
- Official Spanish public-sector content is governed by art. 13 TRLPI and
  Ley 37/2007 regardless of the licence the project chooses.

## Considered options

- **Retain Apache-2.0 with containment (chosen):** keep the outbound
  licence; strip or gate copyleft in the core closure; scope the corpus
  licence claim; disclose remaining copyleft. Zero migration cost; keeps the
  patent grant and trademark withholding.
- **Relicense to EUPL-1.2:** EU-native copyleft, GPL-interoperable.
  Rejected: burdens the target adopters (gestores, integrators, MCP-client
  vendors), desynchronises published metadata, no enforcement upside
  pre-beta.
- **Relicense to GPL-3.0 or AGPL-3.0:** strongest copyleft, compatible with
  the `ofxtools` dependency. Rejected for the same adoption cost; AGPL's
  network clause is moot for a local-only tool.
- **Dual licence / proprietary core:** rejected — contradicts the published
  open-source commitments (README, site, marketplace) and adds friction with
  no current commercial counterparty.

## Constraints

- The GPL-3.0 `ofxtools` dependency governs how third parties may
  redistribute a COMBINED artifact (container image, frozen bundle)
  regardless of our licence choice; only removal or extra-gating changes
  that.
- The official corpus can never be brought under Apache-2.0; every data
  artifact must carry the public-sector-reuse scoping.
- Published PyPI releases are already Apache-2.0; any future licence change
  operates prospectively only.

## Implementation

Landed with this ADR: the dead `formulas` (EUPL-1.1) dependency removed from
core dependencies and the deptry ignore, lockfile regenerated (dropping
`schedula` and its tail); a runtime copyleft disclosure (GPL-3.0 `ofxtools`,
MPL-2.0 `pikepdf`/`certifi`) and a corpus public-sector-reuse section added
to `THIRD_PARTY_NOTICES.md`; the same reuse scoping added to both data
companions' READMEs; the operator contact `hello@neve.md` published in
`PRIVACY.md` and the site legal page (EN/ES/CA). Landed as an immediate
follow-up: `ofxtools` gated behind the `ofx` capability extra per the
dependency-provisioning pattern (`OFX_EXTRA` in the core optional-extras
registry, lazy guarded import in the OFX provider, OFX-looking sources refuse
with the `pip install cadrumo[ofx]` hint while non-OFX detection candidates
degrade to a probe miss; real-import-blocker degradation tests). The CORE
dependency closure is now free of strong copyleft. Also landed: the Apache
4(d) attribution chain now ships inside every published artifact — explicit
PEP 639 `license-files = ["LICENSE", "NOTICE"]` on the root distribution and
on both corpus companions (each companion gained its own LICENSE copy and a
NOTICE that scopes Apache-2.0 to packaging/derived works, never the official
AEAT/BOE documents), verified in all six built artifacts
(`dist-info/licenses/` + `License-File` metadata in the wheels, sdist roots)
and pinned by the `test_license_attribution_chain` packaging gate. Remaining
deferred follow-up: optionally register "Cadrumo" as a trademark.

## Rationale

The dependency-chain sweep (related research) found nothing in the chain
that invalidates Apache-2.0, and every goal behind "stricter" — patent
protection, brand privacy, attribution — is already delivered by Apache-2.0
sections 3, 4(d), and 6 plus the NOTICE chain. Copyleft would tax exactly
the adopters the product targets without protecting anything the operator
cares about. The genuine legal exposures were containment problems (dead
EUPL dependency, undisclosed GPL dependency, over-claimed corpus licence),
all cheaper to fix than a licence migration.

## Consequences

- The core dependency closure is copyleft-free; only installations that opt
  into the `ofx` extra pull GPL-3.0 `ofxtools`, and third parties bundling
  that extra into combined artifacts must treat the combination as
  GPL-3.0-governed — disclosed rather than latent.
- The Apache-2.0 stamp on the data companions is scoped honestly, removing
  an over-claim a rights-holder could challenge.
- Retaining Apache-2.0 keeps the plugin/marketplace channel friction-free
  and published metadata consistent across PyPI, the site JSON-LD, and the
  marketplace listing.
- The licence sweep must be re-run at each release; dependency licences
  drift and the posture is only as current as the last sweep.
