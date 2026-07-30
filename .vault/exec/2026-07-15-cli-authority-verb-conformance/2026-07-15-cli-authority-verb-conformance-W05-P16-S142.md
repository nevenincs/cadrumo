---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S142'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Replace removed command, option, help, risk, and error nodes with accepted Hungarian grammar

## Scope

- `src/cadrumo/locales/hu.yml`

## Description

- Run the locale CLI drift check and confirm the Hungarian catalogue matches the codebase key set.
- Sweep the Hungarian catalogue for citations of the retired command grammar.
- Run the locale gates and the translation-honesty ratchet.

## Outcome

The Hungarian catalogue carries the accepted grammar. Its command, option, help, risk, and error nodes cite only live commands, and `hu.yml` reports `ok` under the CLI drift check.

The catalogue was verified through the locale CLI rather than by reading the file: `scaffold --check` reports `ok`, so no key drifted against the codebase, and the four-way parity and placeholder gates pass. A targeted sweep for the retired grammar finds no surviving citation of the lock, rekey, show-recovery, verify-recovery, sandbox-use, or flat scoped-reset doors.

The citations are also under CI enforcement rather than resting on that sweep: the suggestion-conformance gate walks every string leaf of every catalogue through the live command tree, so a dead command cited in translated text fails a gate. That gate previously caught three real locale-divergent dead citations, so it is proven to bite rather than merely pass.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
