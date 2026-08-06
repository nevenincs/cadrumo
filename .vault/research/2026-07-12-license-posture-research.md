---
tags:
  - '#research'
  - '#license-posture'
date: '2026-07-12'
modified: '2026-07-17'
body_hash: 'sha256:6f860dfd2a3fb11cda7ce0a1b555e1fcd3361ecb515fa8ecde02c401630e68a6'
related: []
---

# `license-posture` research: `dependency-chain licence sweep and licence posture reassessment`

A sweep of the complete dependency chain — the Python engine's core and
optional-extra closure, the frontend bundle, the bundled AEAT/BOE corpus, and
every distribution/deployment channel — to reassess what licence the project
can legally apply, and to tighten the posture accordingly. Operator directive:
"Apache 2 or stricter that we can legally apply." Method: metadata walk
(License-Expression, License classifiers, License field) over the installed
closure resolved from the declared direct set in `pyproject.toml` (core plus
the google, browser, anthropic, agent, search, and workbook-windows extras) —
111 distributions inventoried.

## Findings

### Current posture

The engine already declares SPDX `license = "Apache-2.0"` with the matching
classifier in `pyproject.toml`, as do both corpus data companions
(`aeat-data-manuals`, `aeat-data-official`). The repository ships the Apache
LICENSE and, since the frontend legal pass, a `NOTICE` attribution file naming
Gergely Wootsch. There is no "MIT posture" to tighten at the project level;
MIT dominates only the *dependency* chain (which imposes nothing on our
outbound licence). The reassessment question is therefore: does anything in
the chain make Apache-2.0 inapplicable, and could a stricter licence be
applied instead?

### Copyleft inventory (the only constraints in the chain)

- `ofxtools` — **GPL-3.0-only**, a CORE dependency, eagerly imported by the
  OFX/QFX financial-import provider
  (`adapters/inbound/financial/providers/_ofx.py`). Apache-2.0 is one-way
  compatible with GPL-3.0, so (a) our own code may stay Apache-2.0 and (b) a
  combined installation on the user's machine is lawful. The obligation bites
  only when someone distributes the CLI *together with* its installed
  dependencies (container image, frozen binary, vendored bundle): that
  combined work is governed by GPL-3.0. The project itself ships no such
  artifact — the PyPI wheels contain only first-party code and the MCP bundle
  (`packaging/mcpb`) launches via `uvx`, resolving dependencies on the user's
  machine. Disclosed in `THIRD_PARTY_NOTICES.md`. Follow-up recommended:
  gate `ofxtools` behind an `ofx` capability extra (the established
  dependency-provisioning pattern) so the CORE closure is copyleft-free and a
  downstream image builder can exclude it.
- `formulas` — **EUPL-1.1** (pulling `schedula`, also EUPL-1.1): declared in
  core dependencies but with ZERO import sites in tracked code (confirmed by
  `git grep`; the deptry ignore even recorded "production imports do not
  reference it directly yet"). A dead runtime dependency dragging copyleft
  into every install. **Removed** from `dependencies` and the deptry ignore
  in this pass; `uv lock` dropped `formulas`, `schedula`, `numpy-financial`,
  and their tail from the resolution.
- `pikepdf` — **MPL-2.0** (PDF sanitiser) and `certifi` — MPL-2.0
  (transitive via httpx): file-level weak copyleft; obligations attach only
  to modified MPL-covered files, none of which the project modifies or
  ships. No action needed beyond disclosure.

Every other distribution in the closure is permissive (MIT / BSD / Apache-2.0
/ ISC / PSF / Zlib / MIT-CMU / CC0 build files). Conditional platform deps
not installed on this machine are permissive by their upstream metadata:
`jeepney` (MIT), `SecretStorage` (BSD-3), `importlib-metadata` (Apache-2.0),
`exceptiongroup` (MIT), `backports-tarfile` (MIT), `model2vec` (MIT).

### Bundled non-code content

- AEAT/BOE corpus (in-tree derived surfaces plus the two data companions
  shipping the source binaries): official Spanish public-sector documents.
  Legal texts are outside copyright per art. 13 TRLPI (RDL 1/1996); AEAT/BOE
  publications are reused as public-sector information under Ley 37/2007 and
  the publishers' general reuse terms (source identified, content unaltered,
  no endorsement implied). Defect found: the data companions stamped
  `Apache-2.0` over the wheels with no statement that the licence covers
  packaging/derived works only — an over-claim we cannot make for official
  documents. **Remediated:** a "Licence and reuse of official content"
  section now ships in both companions' READMEs and in the root
  `THIRD_PARTY_NOTICES.md`.
- Embedding vectors: project-computed outputs over the bundled corpus (no
  third-party weights); model lineage (potion-multilingual-128M, Model2Vec,
  BAAI/bge-m3 — all MIT; C4 — ODC-BY attribution) was already recorded.
- Frontend: React/ReactDOM (MIT) and three OFL-1.1 typefaces, self-hosted;
  notices ship in `frontend/THIRD_PARTY_NOTICES.md` with the full OFL text.

### Distribution and deployment channels

- PyPI `aeat-cli` wheel/sdist: first-party code only; PyPI terms require the
  uploader to have distribution rights — satisfied.
- PyPI data companions: covered by the reuse analysis above.
- MCP bundle (`packaging/mcpb`): a launcher manifest invoking `uvx`; vendors
  no third-party code, so no combined-work distribution occurs.
- Claude plugin marketplace (`nevenincs/neve-marketplace`): metadata pointing
  at the published package; same posture.
- Website + docs on AWS S3/CloudFront: static first-party assets; governed by
  the AWS customer agreement (AWS as processor of transient connection data;
  no access logging enabled — see the frontend-legal-compliance research).
- GitHub repository: GitHub ToS grant (view/fork) plus our Apache-2.0.

### Could a stricter licence be legally applied?

Yes, mechanically: authorship is concentrated (14,300 of ~14,314 commits by
Gergely Wootsch; the remainder are agent-generated under his direction, whose
output vests in the operator), so relicensing to EUPL-1.2 or (A)GPL-3.0 is
legally available, and the GPL-3.0 dependency is compatible with either.
It is NOT recommended:

- Apache-2.0 already delivers the goals behind "stricter": an express patent
  grant (§3) and — key to the operator's brand concern — §6 explicitly grants
  NO trademark rights, so "Cadrumo", "neve.md", and the project marks remain
  private even while the code is open source.
- Copyleft would burden exactly the adopters the product targets (gestores,
  integrators, MCP-client vendors) and complicate the Claude-plugin channel,
  with no enforcement upside for a solo pre-beta project.
- A licence switch would desynchronise published PyPI metadata, the website
  JSON-LD, the marketplace listing, and the shipped legal pages for no
  material gain.

Conclusion: **Apache-2.0 is the strictest licence it makes sense to apply and
is fully legal to apply**; the tightening this campaign delivers is
containment (copyleft out of the core closure, corpus reuse scoped, NOTICE
chain) rather than a licence change.

## Actions taken in this pass

- Removed the dead `formulas` (EUPL-1.1) core dependency and its deptry
  ignore; relocked `uv.lock`.
- Added a runtime dependency licence disclosure (GPL-3.0 `ofxtools`, MPL-2.0
  `pikepdf`/`certifi`) and a corpus public-sector-reuse section to
  `THIRD_PARTY_NOTICES.md`.
- Added the corpus reuse notice to both data companions' READMEs.
- Published the operator contact `hello@neve.md` in `PRIVACY.md` and the
  site legal page (EN/ES/CA), closing the LSSI art. 10 residual from the
  frontend-legal-compliance research.

## Residual items

1. DONE (same day): `ofxtools` gated behind the `ofx` extra — core registry
   entry, lazy guarded import, instructive refusal for OFX-looking sources,
   probe-miss degradation for auto-detection, dev-group pin for the test
   environment, and real-import-blocker degradation tests.
2. DONE (next day): explicit `license-files = ["LICENSE", "NOTICE"]` on all
   three distributions; the companions gained their own LICENSE + scoped
   NOTICE files; all six artifacts verified and the
   `test_license_attribution_chain` gate pins the declaration.
3. Consider registering "Cadrumo" as a trademark if the brand matters
   commercially; Apache-2.0 §6 withholds trademark rights but registration is
   what makes enforcement practical.
4. Re-run this sweep at each release (dependency licences drift); the sweep
   script is trivially re-runnable from the declared direct set.
