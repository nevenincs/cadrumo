---
tags:
  - '#audit'
  - '#legal-corpus-vintage'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:1ae566f5373b53552d9a4bb694b6dbbaf9050565ce1c65a2fd3923cc87dfd194'
related:
  - "[[2026-08-10-legal-corpus-vintage-plan]]"
  - "[[2026-08-10-legal-corpus-vintage-adr]]"
  - "[[2026-08-10-legal-corpus-vintage-reference]]"
---

# `legal-corpus-vintage` audit: `excerpt vintage screen and redaction-history acquisition`

## Scope

## Findings

## Recommendations

## Context

Code review of commits `e51e894c99` (the screen and its tests), `6cbfd0bb8b` (the S06 extension), `dad2887a38` (58 BOE article payloads plus 116 sidecars) and the vault corrections `d2c94cacf1` / `09c41a290a`. Verdict: REVISION REQUIRED on two HIGH findings; the derivation itself is sound and general, the tests bite, the screen is not wired as a gate, and every acquired payload's sidecar `source_sha256` matches its committed blob with no CR bytes anywhere.

Findings are recorded here and tracked as plan rows `P03.S13` (the one-directional verdict), `P03.S14` (the version pile) and `P03.S15` (the three smaller findings). Two of the review's original findings were already closed by the S06 extension before this document was written and are not carried: the tautological `len(findings) == population` assertion no longer exists, and the population boundary that silently shed 97 entries is now counted and printed.

## What verified clean

**Generality.** No entry id, norm stem or ordinal-scoped branch appears in the screen's logic; the only `ley-*` occurrences are docstring prose. Unit selection is never forked — every lookup goes through `resolve_anchored_extracted_unit`. The rejected widening is documented, and the entry it would have bought is reported `misresolved` rather than smoothed.

**The tests bite.** No mocks, patches, monkeypatches, skips or xfail. The corpus-pinned controls resolve opposite ways against the real bundled corpus: `ley-37-1992:art-163-octiesdecies` matches at `#a163octiesdecies`, `ley-35-2006:art-81` diverges at 15/15, `art-122` diverges with the gate firing.

**Screen, not gate.** No justfile target, CI lane or health-report reference; nothing outside the module and its test file names it.

**Corpus data.** All 58 payloads: each sidecar's `source_sha256` equals `sha256(git show HEAD:<path>)`, 58 of 58, zero mismatches. Zero committed blobs and zero working-copy files carry a CR byte. The commit touched only `.html`/`.json`/`.md` under the corpus directory and zero `.toml` or `.py` — acquisition-only confirmed, no adjudication.

**Vault-correction honesty.** The wrong denominator is stated beside its replacement rather than overwritten; the 3-of-72 rate is flagged UNAFFECTED in both documents with its reason; the `art-163-*` triage candidate is retired under an explicit withdrawal marker; the opening-sentence limit survives and no entry is described as clean.
