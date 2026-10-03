---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:29abf1b4d3b949e209eb877c8e4790b344899ac4a7157dd0c8ec6a804929978e'
related: []
---

# `registry-authority-artifact-boundary` audit: `runtime projection`

## Scope

The signed runtime source and provenance projection was audited before closing the artifact-only source-root replacement.

## Findings

### runtime-projection | high | Projection copies the full raw corpus into the artifact

The publisher currently projects every catalogued source, including manuals, PDFs, spreadsheets, and authoring-only designs. The resulting base64 JSON artifact would exceed 500MB and retain the corpus burden the architecture removes.

### runtime-projection | medium | XML and Sede artifact-only gates are missing

Tests do not yet stage only signed XML dictionary/XSD data, remove corpus files, and execute a real XML render/verify or Sede parsing path. They also do not prove a missing required signed payload refuses before output or observation.

## Recommendations

- Publish a minimal typed evidence projection and only source bytes required by actual runtime XML/XSD workflows.
- Add staged XML/Sede success and missing-payload fail-closed behavior gates.

## Review update

### runtime-projection | high | Resolved: minimal signed XML closure now has real source-free workflow coverage

The publisher derives source entries only from every declared XML-dictionary layout: its dictionary plus declared XSD references. The staged behavioral gate signs and rereads an authority whose declared corpus paths do not exist, then renders XML, verifies a matching and a drifted file, and parses Sede observations. Separate gates omit the dictionary and XSD payloads and observe refusal before output or observation. The test uses typed data and live renderer, verifier, and Sede parser paths; it does not inspect implementation text or ASTs.

### runtime-projection | high | Resolved: artifact codec and runtime trust boundary retain behavioral refusal coverage

They exercise authentic signed reads, independent later reads, alternate publisher refusal, recomputed-frame tampering refusal, malformed and type-invalid signed payload refusal, missing/corrupt publication refusal in the presence of malformed nearby authoring inputs, and release-anchor sidecar substitution refusal.

### runtime-projection | high | Open: development publication behavioral gate is broken after authoring-test relocation

The two publish-success cases now stop at development validation because the minimal candidate does not author the migrated legal-parameter facts demanded by the active validator. The four preservation/refusal cases then fail while constructing their prior artifact because relocated `_referential_integrity_support.py` still resolves `..schema_references` relative to `dev.registry.tests`. Until the relocation owner restores a valid minimal candidate and canonical support imports, the publisher’s authenticated publication and previous-artifact preservation claims lack a passing behavioral release gate.

## Current outcome

No unresolved critical finding was found. One unresolved high finding remains: the developer publication gate above. The signed artifact codec and artifact-only XML/Sede runtime workflows are behaviorally verified, but S09/S10 cannot be treated as fully release-gated while the publisher suite is failing.
