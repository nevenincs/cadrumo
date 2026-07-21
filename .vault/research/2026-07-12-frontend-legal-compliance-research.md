---
tags:
  - '#research'
  - '#frontend-legal-compliance'
date: '2026-07-12'
modified: '2026-07-17'
related: []
---

# `frontend-legal-compliance` research: `frontend legal, licence, and GDPR compliance review`

A legal pass over the user-facing landing page (`frontend/`, deployed to
cadrumo.neve.md), the GitHub README, and repository legal health. The review
establishes (a) strict, in-code and user-facing notices that the product has
no relation to the AEAT and is not official or affiliated software, (b) GDPR /
ePrivacy / LSSI-CE conformance of the site including cookie and data-handling
notices, (c) a licence review of everything the frontend ships and links, and
(d) shipped user-data policy documents naming Gergely Wootsch as the legal
entity behind neve.md. Every finding below was remediated in the same pass;
residual items are listed at the end.

## Findings

### F1 — Service-provider identification (LSSI-CE art. 10) was absent

Spain's Ley 34/2002 (LSSI-CE) art. 10 obliges an information-society service
operator to identify itself permanently, easily, directly and free of charge.
The site previously identified no operator ("© the cadrumo authors").
**Remediated:** a localized legal page (EN/ES/CA) at the `#/legal` hash route
names Gergely Wootsch as the publisher of cadrumo.neve.md and the neve.md
domain, states the identification is provided for art. 10 LSSI-CE purposes,
and points contact at the canonical repository `github.com/nevenincs/aeat`.
The footer copyright now reads "© 2026 Gergely Wootsch and the cadrumo
contributors" in all three locales.

*Residual:* art. 10.1.a expects an effective direct contact channel;
case practice treats an email address as the safe harbour. The page currently
points to the GitHub issue tracker and `SECURITY.md`. Recommend adding a
dedicated contact mailbox (e.g. on the neve.md domain) when one exists.

### F2 — AEAT non-affiliation: nominative use is sound, but the qualifier was dangling

Using "AEAT", modelo numbers, and casilla names to describe what the software
computes against is classic descriptive/nominative use: Ley 17/2001 (Ley de
Marcas) art. 37.1.c and EUTMR 2017/1001 art. 14.1.c permit third-party use of
a sign to identify or refer to the mark holder's goods or services where use
follows honest practices — which requires not suggesting endorsement or
official status. Two weaknesses existed:

- The hero claim "AEAT compatible*" carried an asterisk with **no footnote
  anywhere on the page** — a dangling qualifier that a regulator or the mark
  holder could read as an unqualified compatibility/endorsement claim.
  **Remediated:** a localized hero footnote now resolves the asterisk
  ("describes only that Cadrumo computes against the published forms and
  rules... an independent project with no relation to the AEAT") and links to
  the legal page.
- Machine-readable surfaces carried no disclaimer. **Remediated:** the shipped
  `index.html` now embeds (i) a top-of-file HTML comment legal notice, (ii) a
  `meta name="disclaimer"` tag, and (iii) JSON-LD `author` / `publisher` /
  `copyrightHolder` entities naming Gergely Wootsch, with the software
  description extended to "Independent software with no relation to the
  AEAT." The README gained a top-of-page non-affiliation callout; the root
  `NOTICE` file states it for every distribution channel.

The pre-existing footer pill disclaimer and download-card disclaimer (all
three locales) already stated non-affiliation, no-filing, and no-advice; they
were retained unchanged.

### F3 — Cookies: inventory is one functional cookie; consent is not required, disclosure now ships

Complete storage inventory of the site: a single first-party cookie
`cadrumo_lang` (1-year max-age, SameSite=Lax) written **only** when the
visitor explicitly picks a language in the picker, plus (new) a
`cadrumo_notice_ack` localStorage flag when the visitor dismisses the notice
bar. There are no analytics, advertising, or third-party cookies, and no
other client-side storage.

Legal analysis: ePrivacy Directive 2002/58/EC art. 5(3) (as amended by
2009/136/EC), transposed as LSSI-CE art. 22.2, requires consent for
terminal-equipment storage **except** for storage strictly necessary to
provide a service explicitly requested by the user. The AEPD's Guía sobre el
uso de cookies (in line with the former WP29 Opinion 04/2012 on cookie
consent exemptions) treats user-interface customisation cookies — a language
choice set by the user's own action — as exempt from prior consent, with the
information duty remaining. Consequence: **no consent banner is legally
required** for this site as shipped. What ships instead:

- an informational (not consent-gating) dismissible notice bar, localized in
  EN/ES/CA — "no trackers, no data collection; one functional cookie stores
  your language, only if you pick one" — linking to the legal page; and
- a cookies section on the legal page naming both storage keys, their
  purpose, lifetime, first-party scope, the exemption basis (art. 22.2
  LSSI-CE, AEPD guidance), and how to delete them.

This deliberately avoids a dark-pattern "accept" wall for storage that needs
no consent — the AEPD guidance warns against presenting exempt cookies as if
consent were required.

### F4 — Google Fonts CDN embedding was a live GDPR exposure; fonts are now self-hosted

`src/styles.css` imported three families from `fonts.googleapis.com`, and
`public/404.html` linked the same CDN. Every page view therefore transmitted
each visitor's IP address to Google. An IP address is personal data (GDPR
art. 4(1), Recital 30; CJEU C-582/14 *Breyer*), and LG München I (judgment of
20 Jan 2022, 3 O 17493/20) held precisely this remote-embedding of Google
Fonts unlawful absent consent, awarding damages. This directly contradicted
the intended "we never collect / no third-party requests" posture.

**Remediated:** all three families (Hanken Grotesk, Instrument Serif,
JetBrains Mono — each SIL OFL 1.1) are now self-hosted as subset WOFF2 under
`frontend/public/fonts/` (~200 KB total; Hanken Grotesk deduplicated to one
variable file per subset serving weights 400–700), declared in
`public/fonts/fonts.css`, linked from `index.html` and `404.html`. The CDN
`@import` and `<link>` were removed. The production page now makes **zero
third-party requests** — verified by inventorying every URL in the built
page.

### F5 — Hosting posture supports the never-collect claim

The site deploys as static files to AWS S3 behind CloudFront
(`infra/docs-static-site.yaml`); the template configures **no access
logging**, so the operator neither enables, receives, nor stores access
logs. Connection data (IP addresses) is processed transiently by AWS as
strictly necessary to deliver the page — a delivery necessity reading under
GDPR art. 6(1)(f) with AWS acting under its standard customer DPA. The
privacy texts state exactly this rather than over-claiming "no processing
anywhere". This honest framing is load-bearing: a flat "no data is processed"
claim would be falsifiable and worse than the accurate one.

### F6 — Licence review: what the frontend ships and links

Shipped in the production bundle:

- React 19.2.7 and ReactDOM 19.2.7 — MIT (© Meta Platforms, Inc. and
  affiliates). Only runtime dependencies in `package.json`; the MIT notice
  obligation is discharged by `frontend/THIRD_PARTY_NOTICES.md` (new).
- Typefaces Hanken Grotesk, Instrument Serif, JetBrains Mono — SIL OFL 1.1.
  OFL condition 2 requires the copyright notice and licence to accompany
  redistributed copies: the full OFL 1.1 text plus per-family copyright lines
  now ship in `frontend/THIRD_PARTY_NOTICES.md`.
- Site-original assets (banner, harness illustration, logo, step icons under
  `src/assets/cadrumo/`) — original project works, © 2026 Gergely Wootsch and
  the cadrumo contributors, Apache-2.0 with the repository.
- Dev-only tooling (Vite, TypeScript, Vitest, Testing Library, jsdom) is not
  distributed to visitors; their licences ride their own package metadata.

Outbound link inventory (all navigational, none tracking/affiliate):
`cadrumo.neve.md/docs/...` (first-party docs), `github.com/nevenincs/aeat`
(canonical repository), `pypi.org/project/aeat-cli` (distribution), internal
anchors, and (new) `#/legal` plus `PRIVACY.md` on the repository. External
step links open with `rel="noreferrer"`. The repository root licence is
Apache-2.0; the site's JSON-LD `license` field already pointed at it.

### F7 — Repository legal health

Present before this pass: `LICENSE` (Apache-2.0), `SECURITY.md`,
`CODE_OF_CONDUCT.md`, `THIRD_PARTY_NOTICES.md` (engine-side, including the
potion/Model2Vec/C4 lineage and ODC-BY attribution), `docs/disclaimer.md`.
Added in this pass: root `NOTICE` (Apache §4(d) attribution file naming
Gergely Wootsch / neve.md and restating non-affiliation for every
distribution channel), `PRIVACY.md` (the never-collect policy covering
software, website, and repository, naming the responsible party),
`frontend/THIRD_PARTY_NOTICES.md`. README fixes: the stale
"web home at aeat.neve.md is under construction" note now points at the live
cadrumo.neve.md; a "License and legal" section links LICENSE, NOTICE, both
third-party notices, PRIVACY.md, and the site legal page; the Disclaimer
section states the descriptive-use basis for AEAT references.

### F8 — Copyright and legal-entity identity

Gergely Wootsch (neve.md) is now named consistently as the legal entity and
copyright holder across: root `NOTICE`, `PRIVACY.md`, README "License and
legal", the site footer copyright (EN/ES/CA), the JSON-LD
author/publisher/copyrightHolder entities, the `index.html` legal comment,
and the aviso legal section of the legal page in all three locales.

## Authorities relied on

- Regulation (EU) 2016/679 (GDPR): arts. 4(1), 6(1)(f), 13, 15–22; Recital 30.
- CJEU C-582/14 *Breyer v Bundesrepublik Deutschland* (dynamic IPs as
  personal data).
- Directive 2002/58/EC (ePrivacy) art. 5(3), as amended by Directive
  2009/136/EC.
- Ley 34/2002 (LSSI-CE) arts. 10 (provider identification) and 22.2
  (cookies).
- AEPD, Guía sobre el uso de cookies (user-interface customisation
  exemption; information duty); WP29 Opinion 04/2012 on cookie consent
  exemption.
- LG München I, 20.01.2022, 3 O 17493/20 (remote Google Fonts embedding
  unlawful without consent).
- Ley 17/2001 de Marcas art. 37.1.c and Regulation (EU) 2017/1001 (EUTMR)
  art. 14.1.c (descriptive / referential use of third-party marks under
  honest practices).
- Apache License 2.0 §§4 (redistribution/NOTICE), 7–8 (warranty/liability
  disclaimers); MIT License notice condition; SIL Open Font License 1.1
  condition 2.

## Residual items

1. LSSI art. 10 contact channel: add a direct email address on neve.md when
   available; GitHub-only contact is workable but not the safe harbour.
2. The docs subsite deployed under `cadrumo.neve.md/docs` is built from the
   engine repository's Sphinx tree; audit that build for third-party font or
   asset CDN references with the same standard applied here.
3. If CloudFront access logging or any analytics is ever enabled, the privacy
   texts (site legal page ×3 locales, `PRIVACY.md`) must be updated in the
   same change — they currently state that no access logs exist.
4. The claim "no third-party requests" is enforced only by review; a small
   frontend test asserting the built `index.html` and CSS contain no
   `http(s)://` references outside cadrumo.neve.md / github.com / pypi.org
   would make the posture regression-proof.
