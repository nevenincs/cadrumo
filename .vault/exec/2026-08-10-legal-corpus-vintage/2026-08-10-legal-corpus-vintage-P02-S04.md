---
tags:
  - '#exec'
  - '#legal-corpus-vintage'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:f5c9ff21f0f001ca93a06bbee043982ecd03e1b193ed20f9ce73e4723a732fb1'
step_id: 'S04'
related:
  - "[[2026-08-10-legal-corpus-vintage-plan]]"
---

# AUTHORING ONLY, and the two halves diverge. Prepare the forbidden-text clause for ley-37-1992 art-122 as a candidate diff in the exec record and do NOT write it into the live registry file

## Scope

- `src/cadrumo/_data/registry/aeat/legal/`

## Description

- Measured both entries through the same path registry build uses — anchored-unit resolver with `include_title=True`, candidate `required_text` fed into unit selection, shared corpus normaliser — then cross-checked against the LIVE BOE consolidated article endpoint, selecting the redaction in force by maximum `fecha_vigencia` and recording its amending norm.
- Confirmed the row's standing warning about art-122 by measurement rather than carrying it as an assumption.
- Found that art-124 is not the same kind of defect as art-122 and cannot be expressed as a negative clause at all. Escalated rather than authored, and edited the Step row to say so before closing it.
- Wrote the art-122 candidate diff out below. **No registry file was modified.**

## Outcome

Art-122 is prepared. Art-124 is escalated. Nothing under `src/cadrumo/_data/registry/` was written by this Step.

### Art-122: the row's warning is now measured

The live endpoint returns four redactions for art. 122 with vigencias `19930101`, `19980101`, `20030101` and `20160101`. The text in force is the last, produced by norm `BOE-A-2014-12329`. The bundled consolidated `ley-37-1992.html#a122` agrees with it.

The entry's two gate phrases behave in opposite directions.

| clause | live text in force | bundled consolidated | excerpt |
| --- | --- | --- | --- |
| `régimen simplificado` | present | present | present |
| `volumen de operaciones` | **absent** | **absent** | present |
| `El régimen simplificado se aplicará a las personas físicas y a las entidades en régimen de atribución de rentas en el Impuesto sobre la Renta de las Personas Físicas` | present | present | **absent** |
| `los sujetos pasivos del Impuesto sobre el Valor Añadido que reúnan los siguientes requisitos` | **absent** | **absent** | present |

So `volumen de operaciones` exists only in the superseded formulation, exactly as the row warned. It is not a stale-but-harmless phrase: it is a gate actively pinning the entry to text the law no longer carries, which is why removing it is the fix rather than collateral. The current article expresses the same threshold concept as `volumen de ingresos` with explicit figures, and the eligibility set itself changed — the superseded text applies the regime to `sujetos pasivos del IVA que reúnan los siguientes requisitos`, the text in force applies it to `personas físicas` and `entidades en régimen de atribución de rentas`. A different population, not a rewording.

### The art-122 candidate diff

```toml
[legal."ley-37-1992:art-122"]
evidence_tier = "legal_authority"
authority = "boe"
kind = "ley"
-corpus_ref = "corpus/normatives/html/ley-37-1992-art-122.html#a122"
+corpus_ref = "corpus/normatives/html/ley-37-1992.html#a122"
document_id = "BOE-A-1992-28740"
article = "122"
permalink = "https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a122"
published_at = 1992-12-29
-effective_from = 1993-01-01
+effective_from = 2016-01-01
review_status = "reviewed"
-reviewed_at = 2026-05-21
+reviewed_at = <the date the operator applies this>
reviewed_by = "operator"
-required_text = [
-    "régimen simplificado",
-    "volumen de operaciones",
-]
+required_text = [
+    "El régimen simplificado se aplicará a las personas físicas y a las entidades en régimen de atribución de rentas en el Impuesto sobre la Renta de las Personas Físicas",
+    "Quedarán excluidos del régimen simplificado",
+    "La renuncia al régimen simplificado tendrá efecto para un período mínimo de tres años",
+]
+forbidden_text = [
+    "los sujetos pasivos del Impuesto sobre el Valor Añadido que reúnan los siguientes requisitos",
+]
```

The `notes` field currently paraphrases the superseded rule — it says the regime applies to `los sujetos pasivos que reglamentariamente se determinen en atencion al volumen de operaciones`, which is the formulation the text in force replaced. It needs rewriting alongside the fields, or the entry keeps asserting the superseded eligibility set in prose after the gate stops asserting it in phrases.

The candidate phrase set was verified to resolve the intended unit of the consolidated file, which matters because `required_text` is an input to unit selection and part of the corpus-text cache key.

Two deliberate choices, both open to the operator's judgement. The forbidden phrase names the superseded ELIGIBILITY SENTENCE rather than the bare `volumen de operaciones` token: the token is a common phrase that a future redaction could legitimately reintroduce in an unrelated apartado, whereas the full sentence can only be the superseded formulation. And no numeric threshold appears in the candidate phrases at all, so no money amount is encoded by this change; if the operator prefers to gate on the `150.000` or `250.000 euros` figures, those are amounts and need their own live cross-check before they go in.

### Art-124: escalated, and it is not a wording defect

**The cited article is about a different special regime.** The live text in force for art. 124 has vigencia `20150101`, norm `BOE-A-2014-12329`, and is titled `Ámbito subjetivo de aplicación`. It governs the régimen especial de la agricultura, ganadería y pesca. `Obligaciones formales del régimen simplificado` and `libro registro` are both absent from it, live and in the bundled consolidated file alike.

The excerpt the entry cites carries `Artículo 124. Obligaciones formales del régimen simplificado`, with the two libro-registro obligations. The entry's `notes` describe that same superseded content, and its `required_text` gates on `libro registro`, which the text in force does not contain.

| clause | live text in force | bundled consolidated | excerpt |
| --- | --- | --- | --- |
| `Ámbito subjetivo de aplicación` | present | present | **absent** |
| `Obligaciones formales del régimen simplificado` | **absent** | **absent** | present |
| `libro registro` | **absent** | **absent** | present |
| `El régimen especial de la agricultura, ganadería y pesca será de aplicación a los titulares de explotaciones agrícolas` | present | present | **absent** |

**Why a forbidden-text clause cannot express this.** The negative clause says "the document this entry cites must not contain X". Here the document is not the right document and the entry's own subject is what would have to be forbidden. Writing a clause naming `libro registro` as forbidden would red registry build without stating the defect, and it would leave an entry that still declares `article = "124"` and a `#a124` permalink pointing any operator who follows it at the agricultura regime. The coherent repair is a decision about WHICH provision now carries the obligación formal — a repoint, a renumber, or a retirement — and that is a tax review against official sources plus an edit to an operator-stamped entry. Both are outside what an agent may do here, and the governing decision record is explicit that it rules on what the gate must be able to express and does NOT rule that any particular excerpt is stale.

**What was checked so the operator does not repeat it.** `libro registro` is also absent from the consolidated art. 123 unit, so the content did not simply move one article along; art. 123 in force is titled `Contenido del régimen simplificado`. The most likely present home is the reglamento rather than the ley, and that is stated as the next place to look, NOT as a finding — it has not been verified and must not be treated as though it had been.

**Blast radius, and why this one is not like art-81.** The art-81 excerpt had a single citing `corpus_ref`. The two IVA entries are cited far more widely: `ley-37-1992:art-122` and `ley-37-1992:art-124` appear in Modelo 303 and Modelo 390 registry data across formulas, bindings, constructs, completeness manifests, extraction profiles, dependency classifications and a relation, and in the user-profile schema and IVA topic data. A repoint or retirement therefore touches what those surfaces cite as grounding, which is an argument for deciding it deliberately rather than folding it into a phrase-level change.

### What the operator must verify, and against which source

Items 1 to 4 are the art-122 change. Item 5 is a determination, not a verification, and cannot be signed the same way.

**1. `El régimen simplificado se aplicará a las personas físicas y a las entidades en régimen de atribución de rentas en el Impuesto sobre la Renta de las Personas Físicas` — must be PRESENT.** Read apartado Uno of the article in force at the BOE permalink on the entry. Falsifier: the sentence reads with a different eligibility set, which would mean a redaction landed after this measurement.

**2. `Quedarán excluidos del régimen simplificado` — must be PRESENT.** Apartado Dos, the exclusion list. Falsifier: the exclusions are expressed without this heading sentence, in which case the phrase gates on wording rather than on the rule.

**3. `La renuncia al régimen simplificado tendrá efecto para un período mínimo de tres años` — must be PRESENT.** Apartado Tres. Falsifier: any period other than three years.

**4. `los sujetos pasivos del Impuesto sobre el Valor Añadido que reúnan los siguientes requisitos` — must be ABSENT.** The single assertion of absence in this change. Read the article in force and satisfy yourself the superseded eligibility sentence is genuinely gone rather than displaced into another apartado. Falsifier: the sentence survives anywhere in the article in force, in which case the forbidden clause would red the build against correct text and must not ship.

**5. The vintage claim.** The entry moves from `effective_from = 1993-01-01` to `2016-01-01`. Confirm the redaction in force is the one produced by `BOE-A-2014-12329`. This one deserves care beyond the mechanical check: that norm modified apartados 2 and 3, and the amending-norm notes on the article list three separate modifying laws, so the date at which apartado Uno reached its current wording is not self-evident from the footer and is a determination rather than a lookup. If the operator concludes apartado Uno's wording predates 2016, the correct `effective_from` is that earlier vigencia, and the candidate date above is wrong.

**6. Art-124 — a determination the operator owns entirely.** Decide which provision now carries the obligación formal the entry is meant to ground, then decide whether the entry is repointed, renumbered or retired, and sweep the Modelo 303 and Modelo 390 surfaces citing it to match. No candidate diff is offered for this deliberately: writing one would present a provision choice as though it had been made.

## Notes

**The row was edited before this record closed it.** The Step's original text asked for a forbidden-text clause for both articles and implied both would land. It now states the authoring-only scope explicitly and records that art-124 is escalated rather than authored, so the row describes what was delivered instead of what was hoped for. The edit went through the owning plan verb.

**Registry build cannot be exercised in this worktree right now.** A peer's in-flight Modelo 130 relation migration leaves a bindings fragment with no revision table, so registry load fails before legal-catalogue validation is reached. The measurements here bypass that load — they run the resolver and normaliser directly and query the live endpoint — but a full green build over an applied change cannot be demonstrated until the peer's work lands.

**Nothing was stamped.** No catalogue entry was authored, edited or re-stamped, and no corpus excerpt was authored for adoption.
