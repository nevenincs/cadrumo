---
tags:
  - '#exec'
  - '#legal-corpus-vintage'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:483ff9810ae4e84ccf3514bc27897a095a4153cc8cd48fc8df5711f1c580cf42'
step_id: 'S03'
related:
  - "[[2026-08-10-legal-corpus-vintage-plan]]"
---

# Author the forbidden-text clause for ley-35-2006 art-81 in the same change as the corpus_ref repoint the sibling audit prepared, naming the repealed cotizaciones ceiling as text the cited document must not contain. This is the operator-stamped entry, so the authoring is prepared and the stamp is not an agent act

## Scope

- `src/cadrumo/_data/registry/aeat/legal/irpf.toml`

## Description

- Re-measured the entry's three candidate present-clauses and its one candidate absent-clause through the SAME code path registry build uses, so a presence reported here is the presence the gate will compute: the anchored-unit resolver with `include_title=True` and the candidate `required_text` fed into unit selection, then the shared corpus normaliser.
- Cross-checked every clause against the LIVE BOE consolidated article endpoint, selecting the redaction by maximum `fecha_vigencia` rather than by position, and recorded the amending norm identifier of the redaction in force.
- Confirmed the candidate `required_text` still resolves the intended unit. This is load-bearing and easy to miss: `required_text` is an input to unit selection and part of the corpus-text cache key, so replacing the phrases can in principle select a different unit than the one the phrases were read from.
- Re-confirmed the blast radius at the current tree rather than trusting the sibling audit's figure: exactly one `corpus_ref` cites the excerpt. The only other occurrence of the excerpt filename is prose inside a sibling entry's `notes`.
- Wrote the candidate diff out below. **No registry file was modified.**

## Outcome

The change is prepared, not applied. Nothing under `src/cadrumo/_data/registry/` was written by this Step.

### What three independent sources now say

The excerpt `ley-35-2006-art-81.html#a81` is a two-vintage hybrid. The bundled consolidated `ley-35-2006.html#a81` and the live BOE text in force agree with each other on every probe, and the excerpt disagrees with both in two directions at once.

| clause | live text in force | bundled consolidated | excerpt |
| --- | --- | --- | --- |
| `complemento de ayuda para la infancia` | present | present | **absent** |
| `durante los tres años siguientes a la fecha de la inscripción en el Registro Civil` | present | present | **absent** |
| `se incrementará en 150 euros` | present | present | **absent** |
| `las cotizaciones y cuotas totales a la Seguridad Social` | **absent** | **absent** | present |
| `Deducción por maternidad` | present | present | present |
| `hijos menores de tres años` | present | present | present |
| `1.200 euros anuales` | present | present | present |

The last three rows are the current gate. Every one of them is present in all three documents, which is why the gate has never discriminated: it passes on the correct text and on the hybrid alike.

The live endpoint returns three redactions for this article, with vigencias `20070101`, `20180705` and `20230101`. The text in force is the last, produced by norm `BOE-A-2022-22128`. The entry currently declares `effective_from = 2007-01-01`.

### The candidate diff

```toml
[legal."ley-35-2006:art-81"]
evidence_tier = "legal_authority"
authority = "boe"
kind = "ley"
-corpus_ref = "corpus/normatives/html/ley-35-2006-art-81.html#a81"
+corpus_ref = "corpus/normatives/html/ley-35-2006.html#a81"
document_id = "BOE-A-2006-20764"
article = "81"
permalink = "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a81"
published_at = 2006-11-29
-effective_from = 2007-01-01
+effective_from = 2023-01-01
review_status = "reviewed"
-reviewed_at = 2026-05-15
+reviewed_at = <the date the operator applies this>
reviewed_by = "operator"
-required_text = [
-    "Deducción por maternidad",
-    "hijos menores de tres años",
-    "1.200 euros anuales",
-]
+required_text = [
+    "complemento de ayuda para la infancia",
+    "durante los tres años siguientes a la fecha de la inscripción en el Registro Civil",
+    "se incrementará en 150 euros",
+]
+forbidden_text = [
+    "las cotizaciones y cuotas totales a la Seguridad Social",
+]
```

The `notes` field also needs the redaction recorded. Candidate addition, to be appended to the existing prose: the text in force dates from 2023-01-01 and was produced by `BOE-A-2022-22128`; the entry cites the bundled consolidated file rather than the per-article excerpt, matching what the sibling `art-81-2` and `art-81-3` entries already do and say.

Retaining the three current phrases alongside the three new ones instead of replacing them is harmless — all three are present in the text in force — but adds nothing, because none of them discriminates between the correct document and the hybrid. The replacement is what the sibling audit prepared.

### What the operator must verify, and against which source

This is the part that is not mechanical. Each item below is a check with a stated falsifier, not a confirmation to countersign. The agent-run measurements above are DISCOVERY, and the signature covers the operator's own reading.

**1. `complemento de ayuda para la infancia` — must be PRESENT.** Read the article in force at the BOE permalink already on the entry. The clause sits in the apartado excluding months in which the complemento was received. Falsifier: if the phrase appears only in a preamble, a footnote or an amending-norm note rather than in the operative text of art. 81, it is not a clause of the article and must not be gated on.

**2. `durante los tres años siguientes a la fecha de la inscripción en el Registro Civil` — must be PRESENT.** Same source. This is the adoption and acogimiento window in apartado 1. Falsifier: the phrase reads with a different span (any number other than three years), which would mean the bundled file and the live text have diverged since this measurement.

**3. `se incrementará en 150 euros` — must be PRESENT, and this one carries a MONEY AMOUNT.** The standing grounding discipline says a numeric amount is cross-checked against live BOE or AEAT even when the bundled corpus agrees, because the bundle is preferred but not infallible. That cross-check has been run for this record and the amount is in the text in force, but it is the item most worth the operator's own eyes, since an amount that drifts is the failure the discipline exists for. Read the second paragraph of apartado 3, on the increment for the month in which the thirty-day cotización period is completed. Falsifier: any figure other than 150 euros, or the increment attaching to a different month than the one the alta rule names.

**4. `las cotizaciones y cuotas totales a la Seguridad Social` — must be ABSENT.** This is the whole point of the new clause and the only item where absence is the assertion. Read the article in force and satisfy yourself that no per-hijo Seguridad Social ceiling caps the guardería increment. Falsifier: if any such ceiling survives anywhere in the article in force, the forbidden clause is wrong and must not ship — a forbidden phrase that is genuinely in current law would red the build against correct text, which is the mirror image of the defect being fixed.

**5. The vintage claim itself.** The entry moves from `effective_from = 2007-01-01` to `2023-01-01`. Confirm the redaction in force is the one produced by `BOE-A-2022-22128` and that the article's apartado 1 as cited did not exist before it. Falsifier: a redaction later than `20230101` exists — in which case both the date and every phrase above must be re-read against that later text, not this one.

**6. What the signature will then cover.** The current stamp asserts a human confirmed a document that is internally impossible: its apartado 1 carries post-2023 qualifying conditions while its apartado 2 carries the pre-2023 structure including the repealed ceiling. No vintage of the article ever read that way, so the existing `reviewed_at` cannot be repaired by choosing a different date. Re-stamping is the act that makes the entry honest again, and it is the one element of this change no agent may perform.

## Notes

**Not carried, and deliberately.** The sibling audit's fourth recommendation — retiring the excerpt file and its two extracted sidecars once the repoint lands — is not in this candidate diff. The row's scope is the catalogue entry, retirement is a corpus-tree change with its own blast radius, and sequencing matters: retiring the file before the repoint is applied would break the entry that still cites it. Re-verified at the current tree that the excerpt has exactly one citing `corpus_ref`, so the retirement remains a single-consumer change whenever it is taken.

**A hazard worth stating for whoever applies this.** The corpus-text cache key includes the entry's `required_text`, and the anchor resolver takes `required_text` as an input to unit selection. Changing the phrases and the `corpus_ref` in the same edit is therefore not two independent edits — it was verified here that the candidate phrase set resolves the intended unit of the consolidated file, and any further phrase substitution needs that check re-run rather than assumed.

**Registry build cannot be exercised in this worktree right now.** A peer's in-flight Modelo 130 relation migration leaves a bindings fragment with no revision table, which fails registry load before any legal-catalogue validation is reached. The measurements in this record were taken through the resolver and normaliser directly and against the live endpoint, so none of them depends on that load; but a full green registry build over the applied change cannot be demonstrated until the peer's work lands, and the operator applying this should run it then.

**Nothing was stamped.** No catalogue entry was authored, edited or re-stamped by this Step, and no corpus excerpt was authored for adoption.
