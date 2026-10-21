---
tags:
  - '#reference'
  - '#modelo-100-legal-attestation-review-batch-b'
date: '2026-08-14'
modified: '2026-10-14'
body_schema: 'body-v1'
body_hash: 'sha256:36892ef353f7a934cb5beb76d80773392c76193a80f8ee7f630c60d170c1a092'
related:
  - "[[2026-08-14-registry-campaign-sequencing-operator-attestation-ledger-audit]]"
  - "[[2026-08-14-legal-attestation-packet-methodology-audit]]"
---
# `modelo-100-legal-attestation-review-batch-b` reference: `Modelo 100 legal-reference attestation review packet, Batch B (numeric rate/bracket/threshold tranche)`

## Summary

This packet contains 41 registry references used by Modelo 100. It preserves each registry key, the operative
rule and effective-year distinction needed to select the right version, relevant model links, and the historical
review stamp.

Structural result: all 41 keys resolve in the bundled corpus and every declared required-text phrase passes the
production normalizer. This is registry-integrity evidence, not legal-content certification. The agent_reviewed
entries are agent-authored; no operator independently checked the live BOE/AEAT source in this packet. Bundled
text is useful evidence, not an infallible authority for rates or amounts.

The batch grew from 31 to 37 after a whole-corpus scan found six references, then to 41 after a table-shape scan
found four more scale references. The wider M100 worklist has 119 distinct IDs across six revisions (2020–2025);
batches A, B and C contain 49, 41 and 39 records. No modelo definition was changed.

## Use and limits

Use the full registry key below as the source selector and choose its effective-year version before applying a
rule. Summaries retain the implementation-relevant rule, not the full quoted statutory text; the key points to
the corpus article and registry entry. Check current BOE/AEAT wording before changing a live calculation. Review
dates below are historical agent-review stamps, not current legal approval.

## Datos identificativos y familia

1. ley-35-2006:art-75 — Court-ordered child support where the taxpayer cannot claim the descendant minimum uses
   the separate art. 64 scale; subtract personal/family minimum and €1,980, floor at zero. M100 2025: 34 boxes,
   3 constructs, 4 formulas. agent_reviewed, 2026-06-28.
2. ley-35-2006:art-75-2015 — Earlier wording for the same support-scale treatment; use for the 2020–2024 years
   in this historical registry version. agent_reviewed, 2026-08-02.

## Rendimientos del trabajo

3. ley-35-2006:art-17 — Defines employment income, including specified employer-paid insurance (up to €50/year
   per person) and securities/benefits. M100 2020–2025: 36 boxes, 10 constructs, 18 formulas. agent_reviewed,
   2026-06-28.
4. ley-35-2006:art-18 — Qualifying irregular employment income generally gets a 30% reduction, subject to the
   €300,000 annual base cap and high-income phase-out/extinction rules. M100: 20 boxes, 10 constructs, 12
   formulas. agent_reviewed, 2026-06-28.
5. ley-35-2006:art-19 — Employment expenses include the €2,000 general amount, qualifying relocation, disability
   amounts (€3,500/€7,750), and legal defence up to €300. M100: 29 boxes, 10 constructs, 29 formulas.
   agent_reviewed, 2026-06-28.
6. ley-35-2006:art-20 — Employment-income reduction for qualifying net income below €19,747.50, with statutory
   income/disability tiers and declining formula. M100 linked. agent_reviewed, 2026-06-28.
7. ley-35-2006:art-42.3.f — Employer shares: exemption up to €12,000/year, or €50,000 for qualifying start-ups,
   subject to statutory conditions. M100 2023–2025: one box. agent_reviewed, 2026-06-30.

## Capital, economic activity and quota

8. ley-35-2006:art-23 — Rental-income expense/depreciation rules (including 3%) and post-2023 reduction tiers;
   select the year-specific regime. M100 linked. agent_reviewed, 2026-06-28.
9. ley-35-2006:art-25 — Movable-capital income definitions and annuity valuation. M100: 45 boxes, 17 constructs,
   78 formulas; also modelos 123, 126, 128 and 193. agent_reviewed, 2026-06-28.
10. ley-35-2006:art-26 — Movable-capital expenses and 30% irregular-income reduction, capped at €300,000. M100:
    28 boxes, 11 constructs, 42 formulas. agent_reviewed, 2026-06-28.
11. ley-35-2006:art-30 — Simplified direct estimation: €600,000 eligibility boundary; 5%
    provision/difficult-to-justify expense capped at €2,000. M100: 190 boxes, 15 constructs, 66 formulas, 12
    parameters; Modelo 130. agent_reviewed, 2026-06-28.
12. ley-35-2006:art-31 — Objective-estimation limits: €150,000 general; €75,000 for specified
    professional-customer invoices; €250,000 agriculture/forestry/fishing; €150,000 purchases. Related-party
    aggregation and election rules apply. M100: 189 boxes, 11 constructs, 52 formulas, 2 parameters; Modelo 131.
    agent_reviewed, 2026-06-28.
13. ley-35-2006:art-32 — Objective-estimation reductions: qualifying irregular income 30% (base cap €300,000),
    low-income €2,000, disability/start-up rules including 20% and €100,000 cap where applicable. M100 linked.
    agent_reviewed, 2026-06-28.
14. rd-439-2007:art-100 — Withholding on urban-property rent generally 19%, with statutory Ceuta/Melilla
    treatment. M100: 2 boxes, 4 constructs, 2 formulas; modelos 115/180. agent_reviewed, 2026-06-28.
15. rd-439-2007:art-30 — Simplified direct-estimation provision: 5%, capped at €2,000. M100: one box, 6
    constructs, 11 formulas, 12 parameters; Modelo 130. agent_reviewed, 2026-06-28.
16. ley-35-2006:art-77 — Regional liquid-quota calculation and statutory proportion/floor. M100: 2 bindings, 799
    boxes, 9 constructs, 85 formulas, 4 parameters. agent_reviewed, 2026-06-28.
17. ley-35-2006:art-49 — Savings-base offset buckets, cross-offset capped at 25%, with four-year carry-forward.
    M100: 46 boxes, 19 constructs, 78 formulas; Modelo 714. agent_reviewed, 2026-06-28.

## Reductions, joint filing and transparency

18. ley-35-2006:art-52 — Current pension-system limits (2023+): generally 30%/€1,500; employer increment up to
    €8,500; self-employed increment €4,250; qualifying dependency increment €5,000; five-year carry-forward.
    M100 2023–2025: 83 boxes, 1 construct, 4 formulas. agent_reviewed, 2026-06-28.
19. ley-35-2006:art-52-2015 — Historical 2015–2020 limits, generally 30%/€8,000 plus €5,000 for
    disability-related systems. M100 2020. agent_reviewed, 2026-08-02.
20. ley-35-2006:art-52-2021 — 2021 limits: €2,000 base, employer increment up to €8,000, and €5,000 dependency
    increase. M100 2021. agent_reviewed, 2026-08-02.
21. ley-35-2006:art-52-2022 — 2022 version from 2022-07-02: €1,500 base, employer increment up to €8,500, €4,250
    self-employed and €5,000 dependency. M100 2022. agent_reviewed, 2026-08-02.
22. ley-35-2006:art-84 — Joint-filing limits do not multiply personal amounts; reductions are €3,400 for the
    first family type and €2,150 for the second, with a cohabiting-parent exclusion. M100 2024–2025: one box,
    one construct, two formulas. agent_reviewed, 2026-06-28.
23. ley-35-2006:art-91 — Current international tax transparency: ≥50% participation and tax below 75% of
    comparable tax; without substance attribute total entity income, otherwise apply listed categories. Preserve
    the 15% minimum, double-inclusion limits, foreign-credit cap, year-end FX conversion and reporting duties.
    M100 2021–2025: 3 boxes, 1 construct, 1 formula. agent_reviewed, 2026-06-28.
24. ley-35-2006:art-91-2015 — Earlier transparency text through 2021-07-10; broad thresholds remain, but
    categories and exceptions differ. M100 2020. agent_reviewed, 2026-08-02.
25. ley-35-2006:art-37 — Valuation rules for specified transfers, securities and exchanges. M100 2020–2025: 5
    boxes, 23 constructs, 305 formulas. agent_reviewed, 2026-06-28.

## Tax scales and liquid quota

26. ley-35-2006:art-63 — State general scale: 9.5% to €12,450; 12% to €20,200; 15% to €35,200; 18.5% to €60,000;
    22.5% to €300,000; 24.5% above. M100 2021–2025: 15 boxes, 6 constructs, 35 formulas, 5 parameters; Modelo
    714. agent_reviewed, 2026-06-28.
27. ley-35-2006:art-66 — State savings scale with 2025 effects: resident rates 9.5/10.5/11.5/13.5/15% at
    €6k/€50k/€200k/€300k bands; non-resident rates 19/21/23/27/30%. Change effective 2025-01-01. M100 2024–2025:
    24 boxes, 3 constructs, 12 formulas, 2 parameters. agent_reviewed, 2026-06-28.
28. ley-35-2006:art-66-2015 — Historical three-bracket savings scale 9.5/10.5/11.5%; non-resident 19/21/23%.
    M100 2020. agent_reviewed, 2026-08-02.
29. ley-35-2006:art-66-2021 — 2021–2022 four-bracket scale through €200,000; state top 13%, non-resident
    19/21/23/26%. M100 2021–2022. agent_reviewed, 2026-08-02.
30. ley-35-2006:art-66-2023 — 2023 five brackets; state 13.5% at €200k–€300k and 14% above; non-resident
    19/21/23/27/28%. M100 2023. agent_reviewed, 2026-08-02.
31. ley-35-2006:art-67 — State liquid quota subtracts specified new-business and 50% group deductions, with
    non-negative floor. M100 2020–2025: 30 boxes, 8 constructs, 47 formulas. agent_reviewed, 2026-06-28.
32. ley-35-2006:art-76 — Current regional savings scale: same brackets as current state scale, statutory
    regional rates and minimum adjustment; 2025 effects. M100 2024–2025: 2 boxes, 3 constructs, 12 formulas, 2
    parameters. agent_reviewed, 2026-06-28.
33. ley-35-2006:art-76-2015 — Historical regional savings brackets 9.5/10.5/11.5%. M100 2020. agent_reviewed,
    2026-08-02.
34. rd-439-2007:art-109 — Quarterly advance payments, including the 70% withholding test for specified
    activities and applicable professional/agricultural rules. M100 2020–2025: 2 boxes, 12 constructs, 5
    windows, 12 formulas; Modelo 130. agent_reviewed, 2026-06-27.

## Deductions, Canary regime and filing procedure

35. ley-19-1994:art-43 — Canary Islands special 4% corporate tax regime. M100 2025: one parameter.
    agent_reviewed, 2026-06-28.
36. ley-35-2006:art-68 — Current deduction catalogue: qualifying start-up investment 50%, base up to €100,000;
    economic activity, gifts, Ceuta/Melilla and heritage deductions. M100 2023–2025: 4 constructs, 3 formulas.
    agent_reviewed, 2026-06-28.
37. ley-35-2006:art-68-2018 — Historical start-up investment deduction 30%, base up to €60,000. M100 2020–2022.
    agent_reviewed, 2026-08-02.
38. ley-35-2006:art-76-2021 — 2021–2022 regional savings scale has four brackets through €200,000 and a 13% top
    rate. agent_reviewed, 2026-08-02.
39. ley-35-2006:art-76-2023 — 2023 regional scale adds 13.5% at €200k–€300k and 14% above. agent_reviewed,
    2026-08-02.
40. ley-35-2006:da-56 — 2023-only simplified direct-estimation reduction: 7% for difficult-to-justify
    expenses/provisions, capped at €2,000. M100 2023. agent_reviewed, 2026-06-29.
41. real-decreto-ley-7-2024:art-11 — DANA affected-municipality 2024 module reduction: 25% after other
    reductions, with Q4 instalment proration; M100 2024 and M131 2024. The registry locator was corrected to
    full consolidated corpus block a1-3 (as of 2026-08-13; SHA256 13615f…e6eb6). The operator reviewed an
    earlier cropped extract on 2026-05-05, not the present pointer/text; current record is
    agent-prepared-pending-operator and must be re-sealed. M100 one construct and one formula.

## Status

All 41 references pass the stated corpus-resolution and required-text checks. Every agent_reviewed date is
historical and agent-authored; no independent current BOE/AEAT comparison was performed. Numeric rules and
effective-date boundaries remain operator verification work. The corrected DANA source pointer is explicitly not
yet operator-resealed. This packet is not current legal certification.
