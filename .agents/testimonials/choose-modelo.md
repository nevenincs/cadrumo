# Testimonial — docs/how-to/choose-modelo.md

- **Doc:** `docs/how-to/choose-modelo.md` ("Find out which modelos apply to you")
- **Persona:** A confused new filer who doesn't know which modelo applies and is using this page to decide.
- **Date:** 2026-06-18

---

## Walkthrough

### 1. `aeat config profile status`
- **Expected (per doc):** Confirms the profile exists and carries the basics; "the explain output lists the facts that drive each applicability answer. If a fact is missing, the verdict says so."
- **Actual:**
  ```
  profile	persona
  profile_id	<profile-id>
  identity.tax_id	sha256:1c9f9632
  activities.description	consultoria
  iva.regime	GENERAL
  tax_residence.ccaa	madrid
  Próximo paso: `aeat app overview status`
  ```
- **Verdict:** OK (mostly) — the command works. But the prose in §"Before you start" mixes `status` and `explain` behavior in one paragraph (it describes "the explain output" while talking about the status check), and the footer points me to `aeat app overview status`, a command this page never documents. **DOC-ISSUE / NIT.**

### 2. `aeat app overview explain 303 --year 2026`
- **Expected:** A four-part answer (verdict, rationale, legal references, profile facts used). The page uses 303 as the teaching example, implying a clean verdict.
- **Actual:**
  ```
  modelo	303
  year	2026
  applicable	false
  verdict	incomplete
  rationale	No se puede determinar la aplicabilidad: el tipo de contribuyente no está declarado. Declare primero el tipo de entidad y, en su caso, las categorías de renta del IRPF con 'aeat config profile edit'.
  legal_refs	ley-35-2006:art-99, ley-27-2014:art-124
  scheduling_rationale	Aplica segun la ventana registral del modelo.
  profile_fact	entity_type	
  profile_fact	iva_regime	GENERAL
  ... (18 facts total)
  ```
- **Verdict:** BOTH / MAJOR. The flagship example lands me straight in the "incomplete" edge case, and crucially the **rationale and scheduling note are entirely in Spanish** — the one piece the page calls "a plain-language explanation" I cannot read as an English-only user. The verdict is honest and the facts table is useful, but as a naive English reader I'm stuck.

### 3. `aeat config profile preflight --modelo 303 --filing-year 2026 --period 1T`
- **Expected:** "reports the profile facts still missing for that specific filing context… preflight answers whether you're ready to work on it."
- **Actual:**
  ```
  readiness	ready	missing=0
  profile_id	<profile-id>
  modelo	303
  revision_id	2023-y-siguientes
  filing_year	2026
  period	1T
  ```
- **Verdict:** BOTH / MAJOR. Direct contradiction with step 2 on the **same profile + same modelo**: `overview explain` says it *can't even tell if 303 applies* because my taxpayer type is undeclared, while `preflight` reports `ready, missing=0`. The page's "applies vs. ready to work on" framing does not prepare a confused user for "applicability is incomplete, but readiness is fully ready." I'd reasonably conclude these two commands disagree.

### 4. `aeat app modelo list` and `aeat app modelo list --year 2026`
- **Expected:** Code, official Spanish title, cadence, tax domain, revision count; domains "IVA, IRPF, IS (corporate income tax), censo, and informative."
- **Actual:** Table rendered correctly. Cadences matched the doc. But domains in the real output include `cross_tax` (123, 193), `irnr` (210), `patrimonio` (714), and `iae` (840) — none of which the page's domain list mentions.
- **Verdict:** DOC-ISSUE / MINOR. A user scanning by tax type for "non-resident" (irnr) or "wealth tax" (patrimonio) won't find them in the page's domain enumeration.

### 5. `aeat app modelo describe 303`
- **Expected:** "official name, domain, cadence, active revision ID, and valid period tokens."
- **Actual:**
  ```
  Modelo	303
  Título	IVA. Autoliquidación (trimestral)
  Nombre oficial	Modelo 303. Impuesto sobre el Valor Añadido. Autoliquidación.
  Ámbito fiscal	iva
  Periodicidad	quarterly
  Revisión	2023-y-siguientes
  Ids de revisión	2009-y-siguientes, 2023-y-siguientes
  Períodos	1T, 2T, 3T, 4T, 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12
  Casillas	120
  Vinculaciones	15
  Fórmulas	23
  ```
- **Verdict:** DOC-ISSUE / MINOR. Field labels are all Spanish (Título/Ámbito fiscal/Periodicidad…), and the output adds three undocumented technical fields — Casillas (120), Vinculaciones (15), Fórmulas (23) — that the page never explains. Harmless but unexplained to a naive reader.

### 6. (Isolation probe) `aeat app overview explain 303 --year 2026` with no passphrase set
- **Expected (per doc):** Nothing — the page never mentions a master-key passphrase.
- **Actual:**
  ```
  Failed. AEAT_SECRET_PASSPHRASE is not set and stdin is not interactive; re-run the command from an interactive terminal (the CLI prompts for the passphrase) or provide AEAT_SECRET_PASSPHRASE through the Settings environment.
  ```
- **Verdict:** DOC-ISSUE / MAJOR. The refusal is graceful and instructive (good app behavior), but "Before you start" lists only "an active profile." Every command on this page reads the encrypted profile and therefore needs the passphrase; a naive user in a fresh shell is blocked at command one with no warning from the page.

---

## Findings

1. **[MAJOR] [DOC] Spanish output in an English guide.** The `overview explain` rationale + scheduling note and every `modelo describe` field label render in Spanish. The page literally sells the rationale as "a plain-language explanation derived from the official rules," but an English-only reader can't read it. *Repro:* steps 2 and 5 above. *Fix:* either translate operator-facing rationale/labels for English locale, or warn on the page that verdict rationales render in Spanish and gloss the key field labels (Título, Ámbito fiscal, Periodicidad, Casillas, Vinculaciones, Fórmulas).

2. **[MAJOR] [BOTH] `overview explain` and `preflight` disagree for the same profile+modelo.** `explain 303` → `verdict incomplete` ("el tipo de contribuyente no está declarado"); `preflight --modelo 303` → `readiness ready missing=0`. *Repro:* steps 2 vs 3. *Fix:* clarify on the page why "ready to work on it" can be `missing=0` while applicability is still `incomplete` (preflight checks filing-context facts, not the taxpayer-type facts applicability needs) — and ideally have preflight surface the same undeclared taxpayer type, or the contradiction reads as a bug.

3. **[MAJOR] [DOC] No master-key passphrase warning.** "Before you start" lists only an active profile, yet every command needs `AEAT_SECRET_PASSPHRASE` (or an interactive prompt). *Repro:* step 6. *Fix:* add a "Before you start" bullet that the CLI requires your master-key passphrase, prompts for it interactively, and reads `AEAT_SECRET_PASSPHRASE` in non-interactive shells.

4. **[MINOR] [DOC] Incomplete domain list.** Page: "Domains include IVA, IRPF, IS, censo, and informative." Real catalogue also shows `cross_tax`, `irnr`, `patrimonio`, `iae`. *Repro:* step 4. *Fix:* extend the domain enumeration (or say "include, among others").

5. **[MINOR] [DOC] `modelo describe` promises fewer fields than it prints.** Output adds Casillas/Vinculaciones/Fórmulas, undocumented. *Repro:* step 5. *Fix:* either list these in the page's description of the command, or note that extra technical fields appear and can be ignored.

6. **[NIT] [DOC] Off-page "Próximo paso" + status/explain prose blur.** `profile status` ends by recommending `aeat app overview status` (never documented here), and §"Before you start" describes "the explain output" inside the status check paragraph. *Repro:* step 1. *Fix:* split the status description from the explain description; either document or drop the `overview status` pointer.

---

## Testimonial

I came in not knowing which form I needed, and the page's structure (ask about one modelo, read the four-part answer, fall back to preflight or the catalogue) is genuinely a good map. But the very first thing I tried — `overview explain 303`, the page's own example — answered me in Spanish and told me it couldn't decide, while `preflight 303` cheerfully said I was fully ready; as a confused beginner those two felt like the tool contradicting itself. The app is solid underneath (honest "incomplete" verdicts, a graceful passphrase refusal, a clean catalogue), but the page leaves an English-only newcomer reading Spanish rationales and never warns me I'd need a passphrase to run anything at all.

## Scorecard

- **Doc clarity:** 3/5
- **App capability:** 4/5
- **Findings by severity:** BLOCKER 0 · MAJOR 3 · MINOR 2 · NIT 1
