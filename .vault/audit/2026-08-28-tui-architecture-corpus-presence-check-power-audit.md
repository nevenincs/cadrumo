---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:63f12fc5b8fddc72c8010fbe3d2c43352c0ab7aac0777502ef70364d8cb30679'
related:
  - "[[2026-08-28-tui-architecture-corpus-anchor-resolvability-audit]]"
---

# `tui-architecture` audit: `Presence-checking power is measurable, saturates, and my earlier counts overstated it`

## Scope

## Findings

## Recommendations

## The measurement this campaign should have made first

Every grounding sweep here has asked "does the cited corpus state the encoded
value?" and treated a yes as evidence. That question has a power, and the power is
measurable: take a set of plausible **wrong** values and count how many the same
document would also confirm.

Against 36 plausible small coefficients and rates:

| document | bytes | distinct numeric tokens | wrong values that pass |
|---|---|---|---|
| `real-decreto-ley-20-2022-art-72` | 2.918 | 11 | 6/36 — **16 %** |
| `ley-27-2014-dt-44` | 3.738 | 19 | 12/36 — 33 % |
| `trlirnr-rdleg-5-2004` (snippet) | 6.034 | 29 | 14/36 — 38 % |
| `orden-hac-1347-2024` | 483.374 | 1.083 | 36/36 — **100 %** |
| `ley-35-2006` | 1.921.157 | 1.128 | 36/36 — **100 %** |
| `ley-37-1992` | 1.760.893 | 987 | 36/36 — **100 %** |

## Size was the wrong discriminator

The tiering used throughout this campaign keys on a 200 KB floor. That is a poor
proxy: the módulos orden is **four times smaller** than LIRPF and has the **same
power — none**. Distinct numeric token count is the real variable, and it
saturates: 1.083 tokens and 1.128 tokens are equally useless, so once a document
carries roughly a thousand distinct numbers, presence proves nothing at all.

## This corrects the previous audit's reasoning, not just its conclusion

The companion anchor audit argued that a módulos orden is *topically narrow*, so a
numeric check against it should carry real information. **That is backwards.**
Topical narrowness means the document is dense in exactly the class of number
being looked for — a 483 KB table of módulos coefficients contains essentially
every small coefficient — so narrowness destroys discriminating power for that
class rather than improving it.

Acting on the earlier reasoning, this sweep ran the check anyway: 12 parameters
cite a módulos orden and all 12 have every encoded value present. **That result is
worthless and must not be quoted as grounding.** A parameter encoding any of the
36 wrong values tested would have produced the same clean report.

## And it qualifies this campaign's headline numbers

The excerpt-tier sweep reported 181 rows judged, 169 with every value stated. That
was presented as strong evidence. At a 16–38 % false-pass rate it is **moderate**
evidence: a wrong value has roughly a two-in-three to five-in-six chance of being
caught, not a certainty. The 169 should be read as "no contradiction found by a
check of measured, partial power", not as "verified".

The finding it produced — M200's missing DT 44ª citations — stands, because a
**failure** of a presence check is informative regardless of its power. Only the
passes are weakened. That asymmetry is worth stating plainly: this method can
convict, but it cannot acquit.

## Consequence

Do not extend presence-checking to any family whose citations resolve to a
document carrying hundreds of distinct numbers; the answer is known in advance.
For those families the options are provision excerpts, an independently sourced
oracle, or leaving the row explicitly unverified — never a clean report from a
powerless check.

No production code, registry data or test was changed by this audit.
