---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:f776f2cf846f3b78ee80fe9be12b0226bb4ff0898ec33ee3fa283eb5ef831352'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---



# `facts-registry` audit: `S72 Article 161 recargo review`

## Scope

Reviewed W03.P13.S72 only: the three Article 161 BOE captures, pinned source metadata, authored scalar facts, adapter retirement, focused tests, and retained raw legal data. Excluded concurrent S64/S71/S73 and unrelated worktree changes.

## Findings

### art161-2012-rates-start-six-weeks-too-early | high | The authored facts mistake redaction availability for legal effect

The 2012 capture's wrapper date is 2012-07-15, but its own final blockquote says the Article 161 update takes effect on 2012-09-01. The source row and all four authored facts instead use 2012-07-15; the general and reduced values therefore resolve as 5.2 and 1.4 percent during 15 July through 31 August despite the cited official text saying otherwise. The focused test embeds this incorrect boundary. Existing IVA temporal tests independently recognize 2012-09-01 as the legal-effect date. A hash-pinned redaction is valid evidence, but it does not authorize a fact window contrary to an explicit deferred-effect clause in that redaction.

## Recommendations

Resolve `art161-2012-rates-start-six-weeks-too-early` before accepting S72. Model the legal effect of the new 5.2 and 1.4 percent values from 2012-09-01, preserve the previous values through 2012-08-31, and make source provenance distinguish the captured redaction date from the rate-effective window. Add both sides of the 2012-09-01 boundary to the focused facts test.
