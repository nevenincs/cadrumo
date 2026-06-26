# Testimonial — Upload your exported modelo at the AEAT portal

- **Doc path:** `docs/how-to/file-at-aeat.md`
- **Persona:** A user with an exported `.boe` file following the manual AEAT-portal upload handoff checklist, then recording the local filing marker.
- **Date:** 2026-06-18

---

## Walkthrough

### Step 1 — confirm the draft is verified
**Command (verbatim):**
```
aeat app modelo work revision --modelo 303 --year 2026 --period 1T --select latest-verified
```
**Expected (from doc):** "If a verified calculation exists, the command shows it. If none exists, the command refuses."

**Actually happened:** First, before any setup, the command refused with:
```
Refused. No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.
```
The page never says you need an active profile. After I created a profile (`config profile create faatest --quiet --tax-id 12345678Z`), the command refused again because no work unit existed:
```
Invalid value: Ninguna unidad de trabajo activa coincide con este modelo, ano y periodo. Ejecute primero aeat app modelo work create.
```
After I ran `work create`, the selector refused (English message) because the unit was unverified:
```
Invalid value: "no calculation revision in state 'verificado_completo'"
```
**Verdict:** DOC-ISSUE, MAJOR — the command exists and refuses cleanly, but the page assumes an active profile AND an existing work unit, neither of which it states as a prerequisite.

### Step 2 — export the filing file
**Command (verbatim):**
```
aeat app modelo export --modelo 303 --year 2026 --period 1T --output ./modelo-303.boe
```
**Expected (from doc):** Writes a fixed-width `.boe` file and prints path, size, and SHA-256 checksum; "the export refuses an unverified draft."

**Actually happened:** With no work unit it refused with the same "ejecute work create" message. With an unverified unit present it refused exactly as promised:
```
Invalid value: 'no exportable verified or filed revision exists'
```
Help text confirms the safety claim: "Exporta una revisión de modelo verificada o presentada a un fichero local compatible con AEAT (fichero-BOE). Local; nunca contacta con AEAT." The `--output` flag exists as documented. I could not reach a successful export (would require a fully verified calculation, which is outside this page's scope and several un-cited steps away).
**Verdict:** OK (refusal path) / partially unverified (success path not reachable in this environment) — the documented "refuses an unverified draft" promise holds; the checksum/size output could not be observed.

### Step 3 — upload at the AEAT portal
Manual, browser-only, outside the tool. The page is explicit and safe: "do not expect the tool to do any part of this step for you." Nothing to run.
**Verdict:** OK.

### Step 4 — save the justificante
Manual portal download. Nothing to run.
**Verdict:** OK.

### Step 5 — record the filing locally
**Command (verbatim):**
```
aeat app modelo work file --modelo 303 --year 2026 --period 1T
```
**Expected (from doc):** Records a local "filed" marker only; "does not and cannot submit anything to AEAT"; optional `--notes`/`--by`; may refuse on filing-window gate or verification state.

**Actually happened:** Refused (no verified revision to mark):
```
Invalid value: 'work unit has no selectable current_calculation_revision_id'
```
Help confirms `--notes` and `--by` exist as documented. The command exists and is correctly scoped.
**Verdict:** OK (refusal path). Note: the page lists "filing window gate" as a refusal cause; my 2026-1T window is in fact already closed (`plazo_closes_on 2026-04-20`, 59 days overdue, recargo band shown at `work create`), so this is a realistic gate the page correctly warns about.

### Step 6 — reconcile the justificante
**Command (verbatim):**
```
aeat app modelo reconcile file --modelo 303 --year 2026 --period 1T --file ./justificante.pdf
```
**Expected (from doc):** Reports matches/mismatches; "refuses a PDF it cannot read as invalid evidence."

**Actually happened:** Missing file:
```
Refused. justificante at ...\justificante.pdf could not be parsed: justificante PDF not found: <input-pdf>
```
With a non-PDF text file at that path:
```
Refused. justificante at ...\justificante.pdf could not be parsed: pdfplumber failed to open <input-pdf>: PdfminerException
```
The command exists, takes `--file` as documented, and refuses unreadable evidence as promised. The `reconcile pull` alternative also exists and is correctly marked "Contacta con AEAT (solo lectura)."
**Verdict:** OK, but the invalid-PDF refusal leaks internal library names (`pdfplumber`, `PdfminerException`) instead of a plain "this isn't a readable PDF" message — MINOR.

---

## Findings

1. **[MAJOR] [DOC]** The page lists prerequisites (a verified saved calculation, AEAT portal credentials) but omits two hard blockers a real user hits at Step 1: there must be an **active `aeat` profile** and an **existing work unit** for the modelo/period. Step 1 refuses with `No hay un perfil activo` and then `Ejecute primero aeat app modelo work create`. *Repro:* run Step 1 on a fresh install. *Fix:* in "Before you start," note that you need an active profile and a created work unit (link quickstart), or that the verified-calculation prerequisite implies both.

2. **[MAJOR] [DOC]** No mention of the **master-key passphrase**. Every command here touches the encrypted profile; a non-interactive user without `AEAT_SECRET_PASSPHRASE` set (or the interactive prompt) is blocked. The page never warns of this. *Fix:* add a one-line note that commands require unlocking your profile (passphrase prompt / `AEAT_SECRET_PASSPHRASE`), or link the page that covers it.

3. **[MINOR] [APP]** Several refusal messages are emitted in **English** (`'no exportable verified or filed revision exists'`, `"no calculation revision in state 'verificado_completo'"`, `'work unit has no selectable current_calculation_revision_id'`) while the surrounding CLI is Spanish. An English-only or Spanish-only reader gets mixed-language output. *Fix:* route these refusals through the locale catalogue.

4. **[MINOR] [APP]** The invalid-PDF refusal in Step 6 leaks internal implementation detail: `pdfplumber failed to open <input-pdf>: PdfminerException`. The page promises it "refuses a PDF it cannot read as invalid evidence" — true, but the message isn't instructive to a naive user. *Fix:* surface a plain "the file is not a readable PDF" message; keep the library trace for `--verbose`.

5. **[NIT] [DOC]** Step 1 uses `--select latest-verified`; the flag default is `current` and the doc never explains the selector vocabulary. A reader can't tell what other values exist. *Fix:* one sentence, or link the revision-selector reference.

6. **[NIT] [DOC]** Safety framing is excellent and consistent — the page repeatedly and correctly states the tool never submits to AEAT, and the CLI help corroborates it (`Local; nunca contacta con AEAT`; `reconcile pull` = `solo lectura`). No safety finding. Logged as a positive.

---

## Testimonial

The page reads as a calm, honest checklist, and its single most important promise — that the tool never files for you — is true and reinforced everywhere I looked, including the CLI's own help text. Where I tripped was the very first command: it assumed I already had a profile and a work unit, so I bounced off two refusals before I could even reach "confirm the draft is verified." Once past setup, every documented command existed, took the documented flags, and refused gracefully and predictably for an unverified draft, a missing marker, and an unreadable PDF — the app behaved exactly as the page described on the refusal paths. I never saw a crash, and I was never able to make the tool do anything that touched AEAT, which is exactly what the page promised.

## Scorecard

- **Doc clarity:** 3.5 / 5 (clear, safe, well-linked prose; loses points for missing profile/work-unit and passphrase prerequisites)
- **App capability:** 4.5 / 5 (every cited command exists and refuses cleanly and safely; minor i18n/message leaks)
- **Findings by severity:** BLOCKER 0 · MAJOR 2 · MINOR 2 · NIT 2
