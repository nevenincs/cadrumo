---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:0f2906ddd1797eaffb95dc1be5d1cdf7d44c89447abd5d4ef0acdf7bfdadb9c2'
step_id: 'S25'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Escalate the stale ley-35-2006 art-81 corpus excerpt for operator refresh, because its apartado 1 carries the post-2023 widened supuestos while its apartado 2 still carries the cotizaciones ceiling the bundled AEAT manual states was removed from 2023, and the 150 euro post-alta increment is absent entirely, so the excerpt is a two-vintage hybrid that cannot gate the required_text for any clause S15 or S23 implement

## Scope

- `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-81.html`

## Description

- Read the per-article excerpt in full and compare it clause by clause against the bundled authoritative consolidated text this repository already ships at block `#a81`.
- Read the four `ley-35-2006` art-81 entries in the IRPF legal catalogue and record which corpus file each cites, what each pins in `required_text`, and how each is review-stamped.
- Confirm which clause each of the two dependent Steps implements and whether the excerpt contains the text that establishes it.
- Author no legal content: the excerpt, the catalogue entry, its `required_text` and its review stamp were all left exactly as found.

## Outcome

The row's premise is confirmed and is narrower than what the excerpt actually costs. Six defects were measured, four of which the row does not name. The escalation was relayed to the operator through the team lead. No legal content was authored, edited or re-stamped by an agent, which is the whole point of the row.

**One: apartado 1 is the post-2023 vintage but truncated, and the missing sentence is the one Step S15 implements.** The excerpt's first paragraph carries the widened supuestos - recipients of contributory or assistance unemployment protection, or alta in the corresponding Seguridad Social regime or mutualidad with a minimum 30 contributed days - which is the shape in force from filing year 2023. It then stops at the 1.200 euro annual cap. The bundled consolidated apartado 1 continues with three further sentences the excerpt does not contain: the adopcion and acogimiento clause granting the deduction irrespective of the child's age during the three years following the Registro Civil inscription date, the companion sentence for cases where inscription is not required, running three years from the judicial or administrative resolution, and the clause transferring the pending deduction on the mother's death or where guarda y custodia is attributed exclusively to the father or a tutor. Step S15 gives the adopcion clause its own date-scoped three-year window. The text establishing that window is not in the excerpt at all, so the excerpt cannot anchor it under any `required_text` phrase.

**Two: the apartado numbering is the pre-2023 shape, and it contradicts this catalogue's own sibling entries.** The excerpt presents the guarderia increment as a second paragraph of apartado 1 and labels the proration clause apartado 2. The consolidated text numbers the guarderia increment apartado 2 and the proration apartado 3. Both files ship in this tree, so a citation of the form art. 81.2 resolves to different content depending on which one is read. The catalogue already encodes the consolidated numbering: the entry for the 1.000 euro guarderia figure declares article 81.2 and the entry for its proration and gasto-efectivo limit declares article 81.3, and both deliberately cite the consolidated file rather than this excerpt. The notes on the first of those two say so outright, calling the excerpt a two-vintage hybrid tracked as its own open defect and declining to inherit the problem. The excerpt is therefore already isolated by its neighbours while remaining the corpus reference of the parent entry.

**Three: apartado 2 states a repealed limit as current law, and the repository already ships the replacement.** The excerpt's final paragraph ends by limiting the deduction for each child to the total Seguridad Social and alternative mutualidad contributions accrued in the tax period after the birth or adoption. The consolidated apartado 3 first paragraph replaces that rule with a month basis conditioned on entitlement to the minimo por descendientes for that child and on neither parent receiving, for that descendant, the complemento de ayuda para la infancia of Ley 19/2021, and it carries no contributions ceiling of any kind. The bundled consolidated text therefore corroborates the AEAT manual independently: the ceiling is absent from the law in force. Two things follow. The excerpt asserts a repealed limit with no year scoping, and the correct replacement text is already in the tree, so remediating this needs no new material.

**Four: the 150 euro post-alta increment is absent, and it is the clause Step S23 implements.** The consolidated apartado 3 second paragraph states that where entitlement arises from alta in Seguridad Social or a mutualidad after the child's birth, the deduction corresponding to the month in which the 30-day contribution period of apartado 1 is completed is increased by 150 euros. Nothing resembling that sentence appears anywhere in the excerpt. Step S23 landed the increment grounded on the bundled AEAT manual, and its own record states plainly that it did so because the per-article excerpt carries no mention of the figure and that authoring the missing statutory text to satisfy a corpus gate would be fabricating evidence. That judgement was correct and this record endorses it.

**Five: the required_text gate cannot detect any of the above, and the entry currently carries an operator review stamp.** The parent entry pins three phrases - the article heading, the under-three children phrase, and the 1.200 euro annual figure. Every one of the three appears in both the pre-2023 and the post-2023 vintage, so not one of them discriminates between them, and the gate passes on either. Meanwhile the entry declares effectiveness from 1 January 2007 and is stamped as reviewed by the operator on 15 May 2026. Text carrying the 2023 widened supuestos cannot have been in force in 2007, so an operator review stamp presently sits on a document that is internally impossible. The two sibling entries by contrast are stamped as agent-authored pending an operator re-stamp. The asymmetry is the wrong way round: the entry with the strongest stamp is the one with the weakest text.

**Six: the excerpt is not a verbatim extract of the bundled consolidated file.** Where the consolidated apartado 1 says the deduction runs until the child reaches three years of age, the excerpt uses a different formulation of the same idea. A phrase-level divergence in a hand-made excerpt means `required_text` matching is being performed against text whose provenance is unestablished, which is exactly the failure mode the bundled-corpus-first discipline exists to prevent.

**Why this is not simply a stale file to overwrite.** The pre-2023 wording is not wrong in the abstract - it is current law for filing years through 2022, and this campaign depends on that being expressible. Step S26 has to apply the contributions ceiling for filing years 2020 to 2022 only, and Step S23 has to apply the 150 euro increment for filing years from 2023 only. Both are year-scoped clauses, and each needs a vintage-scoped grounding source. One undated file that silently interleaves both vintages can ground neither, and it is worse than either vintage alone because a reader cannot tell which year any given paragraph speaks for.

## Notes

What an agent must not do here, and did not do: author or re-author the excerpt, correct the apartado numbering, add the missing sentences, delete the repealed ceiling, adjust the effective-from date, widen or narrow `required_text`, or alter the review stamp. The legal catalogue is a human-reviewed filing-grade surface and its provenance is the part that cannot be reconstructed after the fact.

What the operator must verify against the live BOE consolidated text before anything is changed. First, the current apartado structure, so the numbering divergence is settled from the authority rather than from either bundled file. Second, that apartado 1 continues with the adopcion and acogimiento three-year window from the inscription date and with the transfer-on-death clause, which is what Step S15 needs. Third, that the current apartado 3 first paragraph carries the minimo por descendientes month basis and the Ley 19/2021 complemento exclusion and carries no contributions ceiling. Fourth, the exact 150 euro sentence and the filing year from which it applies, which is what Step S23 needs. Fifth, the amending norm and effective date of the widened supuestos, so the entry's 2007 effective-from can be corrected and the pre-2023 and post-2023 clauses can each be grounded for the years they actually govern. Sixth, and this is a decision rather than a verification, whether the per-article excerpt should be retired in favour of pointing the parent entry's corpus reference at the bundled consolidated file, which is already what both sibling entries do and what their notes recommend.

A caution that applies to the amounts specifically. The bundled corpus is preferred but not infallible on numbers, so the 1.200, 1.000 and 150 euro figures and the 30-day period should be read from the live consolidated text even though the bundled file states them, and the amending norm's identifier asserted rather than assumed. A consolidated-legislation payload carries every historical version oldest first, so the last version is the one to take.

No tests, gates or linters were run for this record; this fleet has a single test-run authority and nothing here required it. No source file, corpus file, registry file or catalogue entry was modified. The only artefact produced is this record and the escalation text relayed from it.
