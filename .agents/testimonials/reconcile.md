# Testimonial — `docs/how-to/reconcile.md`

- **Doc path:** `docs/how-to/reconcile.md`
- **Persona:** A first-time user reconciling a filed Modelo 303 against its AEAT justificante — trying both the live `reconcile pull` (from sede) and the local `reconcile file --file` paths.
- **Date:** 2026-06-18

---

## Walkthrough

### 0. Prerequisite discovery (page "Before you start")

The page lists prerequisites (active profile, locally filed work unit, AEAT auth for pull, a PDF for file) but the **first documented command is `reconcile pull`** — so a literal reader runs it before having any of the prerequisites. I did exactly that.

**Command:** `aeat app modelo reconcile pull --modelo 303 --year 2026 --period 1T`
**Expected (from doc):** Fetch the receipt and reconcile in one step.
**Actual:**
```
Refused. No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.
EXIT=2
```
**Verdict:** OK (graceful refusal, names the exact next command) — but the refusal is in Spanish to an English-doc reader. The page never warns the chained prerequisites must be built first.

---

### 1. Build the prerequisites (not on the page — followed CLI hints)

The page does not walk through profile/work-unit creation; it links out to `profile-setup.md` and `quickstart.md`. Following the refusal's own hint:

**Command:** `aeat config profile create persona-rec --tax-id 12345678Z`
**Actual:**
```
Refused. El asistente guiado necesita una terminal interactiva, y esta ejecución no la tiene.
... aeat config profile create NAME --quiet --tax-id NIF/CIF/DNI/NIE
EXIT=2
```
Re-ran with `--quiet` → `estado=creado, active_profile=persona-rec`. (The refusal the page's *own hint command* produces is itself missing `--quiet` — a cross-page nit, not on the reconcile page.)

**Command:** `aeat app modelo work create --modelo 303 --year 2026 --period 1T`
**Actual:** `status=created, state=borrador` — work unit created (NOT filed; page prerequisite says "locally **filed** work unit").

---

### 2. `reconcile pull` with active profile + work unit (live AEAT path)

**Command:** `aeat app modelo reconcile pull --modelo 303 --year 2026 --period 1T`
**Expected (from doc):** "The pull is read-only at AEAT." It fetches and stores an encrypted copy.
**Actual:**
```
Refused. La identidad de Cl@ve Móvil no coincide con la identidad fiscal del perfil activo; cambia al perfil que coincida o actualiza el perfil antes de la autenticación AEAT en directo.
  -> Run `aeat config switch NAME`
EXIT=2
```
**Verdict:** OK — refuses gracefully with a remediation command. The page DID set the expectation (it lists "working AEAT authentication" as a pull-only prerequisite and links `authenticate-with-aeat.md`). Refusal is instructive, not a crash. Note: refusal is auth-identity, not "work unit not filed" — so the page's "locally filed work unit" prerequisite is not actually enforced on the pull path I hit.

---

### 3. `reconcile file` — verbatim doc path (missing file)

**Command:** `aeat app modelo reconcile file --modelo 303 --year 2026 --period 1T --file ./justificante.pdf`
**Expected (from doc):** Reads the PDF you supply; local only.
**Actual:**
```
Refused. justificante at justificante.pdf could not be parsed: justificante PDF not found: <input-pdf>
EXIT=2
```
**Verdict:** OK (graceful) / NIT — the doc uses `./justificante.pdf` as the literal example with no note that you must supply your own downloaded file; a literal reader hits "not found". `<input-pdf>` is a redaction placeholder leaking into the user message (cosmetic).

---

### 4. `reconcile file` — synthetic non-AEAT PDF (tests the `evidence_invalid` promise)

**Command:** `aeat app modelo reconcile file --modelo 303 --year 2026 --period 1T --file <minimal .pdf>`
**Expected (from doc):** "Both transports report one of three verdicts: ... **evidence_invalid** — the PDF could not be read. Check that the file is the AEAT justificante and not a different document."
**Actual:**
```
Refused. justificante at ...\justificante.pdf could not be parsed: justificante PDF parse failed: <input-pdf>
EXIT=2
```
**Verdict:** DOC-ISSUE / MAJOR — the page presents `evidence_invalid` as a **verdict the command reports** (alongside matches/mismatches). In reality an unreadable PDF raises a hard **refusal (exit 2)**, prints no verdict row, and the actual message does NOT contain the page's promised guidance ("Check that the file is the AEAT justificante and not a different document"). Confirmed in source: `_reconcile.py` maps a parse failure to `ReconciliationEvidenceInvalidError` (a refusal), while `evidence_invalid` exists only as an enum member that the parse-fail path never emits as a verdict.

---

### 5. `reconcile file` — real AEAT justificante fixture (happy path)

Synthesized by copying the repo's real `modelo_303_2026Q1.pdf` fixture (a naive user would download their own from the portal).

**Command:** `aeat app modelo reconcile file --modelo 303 --year 2026 --period 1T --file <real_just.pdf>`
**Expected (from doc):** A verdict; on mismatch "names each field and shows the local value next to the value found in the PDF."
**Actual:**
```
verdict	mismatches
diffs	1
diff	tax_id	work_unit=sha256:1c9f9632	evidence=sha256:22b94d56
EXIT=0
```
**Verdict:** OK (delivers a real `mismatches` verdict naming `tax_id`, one of the four documented header fields) / MINOR — the page promises the report "shows the local value next to the value in the PDF", but `tax_id` is shown as **opaque SHA-256 hashes**, not the literal NIF values. A naive user cannot read which NIF differs from which. (Sensible for privacy, but the doc over-promises legible side-by-side values.)

---

### 6. `reconcile history` (plain + filtered)

**Command:** `aeat app modelo reconcile history`
**Expected (from doc):** Rows showing when it ran, the work unit, the evidence source, the verdict, how many fields differed.
**Actual:**
```
reconciliation_count	1
reconciled_at  work_unit_id  source_kind  verdict  diff_count  actor
2026-06-18T19:54:...  af8fb7fd...  justificante  mismatches  1  persona-rec
```
**Command:** `aeat app modelo reconcile history --work-unit-id af8fb7fd...` → same row (filter accepted).
**Verdict:** OK — matches the documented columns exactly (plus an undocumented `actor` column, harmless).

---

### 7. Link integrity

All six linked how-to targets resolve: `authenticate-with-aeat.md`, `profile-setup.md`, `quickstart.md`, `justificante-receipts.md`, `review-calculation-values.md`, `troubleshooting.md`, plus `../cli/index.rst`. Clean.

---

## Findings

1. **[MAJOR] [BOTH] `evidence_invalid` is documented as a verdict but is actually a hard refusal.**
   Repro: `reconcile file` against any non-AEAT/malformed PDF → `Refused. ... could not be parsed: ... parse failed` (exit 2), no verdict row, and none of the page's promised "Check that the file is the AEAT justificante" guidance appears. Source: `src/aeat/application/modelo/_reconcile.py` maps `JustificanteParseError` → `ReconciliationEvidenceInvalidError` (a refusal); `evidence_invalid` is only an unused-on-this-path enum member.
   Fix (doc): describe `evidence_invalid` as a **refusal** ("the command refuses with exit 2 and a parse error"), not a third verdict row; OR (app) emit it as an actual verdict line carrying the guidance text the page promises. Pick one and make doc + app agree.

2. **[MINOR] [DOC] Mismatch report does not show legible local-vs-PDF values for `tax_id`.**
   Repro: real-fixture run printed `diff tax_id work_unit=sha256:1c9f9632 evidence=sha256:22b94d56`. The page says the report "shows the local value next to the value found in the PDF" — for the taxpayer identifier these are SHA-256 hashes, unreadable to a user trying to spot which NIF is wrong.
   Fix: note that the taxpayer identifier is compared as a redacted hash (the value is not displayed in clear), so a `tax_id` mismatch means "confirm the active profile's NIF matches the receipt" rather than "read the two values".

3. **[MINOR] [DOC] First documented command (`reconcile pull`) runs before the prerequisite chain the page itself lists.**
   Repro: following the page top-to-bottom, the very first command refuses with "No hay un perfil activo". A naive reader must detour through two other pages (profile + work unit) before any command on this page succeeds.
   Fix: add a one-line pointer right above the first command block — e.g. "If you have not yet created a profile and a filed work unit, do that first (see quickstart) — these commands assume both exist."

4. **[NIT] [DOC] `./justificante.pdf` literal example reads as a real path.**
   Repro: copy-pasting the documented `reconcile file ... --file ./justificante.pdf` → `Refused ... PDF not found`. Fix: render the path as an obvious placeholder (e.g. `--file PATH/TO/justificante.pdf`) or note "replace with the path to your downloaded receipt".

5. **[NIT] [APP] Redaction placeholder `<input-pdf>` leaks into the user-facing refusal message.**
   Repro: both not-found and parse-fail refusals end with `: <input-pdf>`, which is meaningless to a user. Fix: drop the trailing redacted token from the operator message or replace with the (already-shown) path.

6. **[NIT] [BOTH] English doc, Spanish refusals.** Every refusal/help string renders in Spanish (`Refused. No hay...`, `La identidad de Cl@ve Móvil...`). Consistent with the whole CLI, but an English-only reader of this English page gets Spanish errors with no warning. Out of scope to fix per-page, noted for completeness.

7. **Observation (not a defect): passphrase.** The page never mentions a master-key passphrase is needed, but in this run the harness pre-set `AEAT_SECRET_PASSPHRASE` and no command prompted for it — the encrypted-capture/profile operations proceeded. So the passphrase gap did not bite on the reconcile surface; flagging only that the page is silent on it.

---

## Testimonial (first person)

Reconciliation mostly did what the page promised: `reconcile file` against a real justificante gave me a genuine `mismatches` verdict that correctly fingered the taxpayer identifier, and `history` listed exactly the columns the page described. The live `pull` path refused cleanly with a remediation command, and the page had honestly warned me that pull needs AEAT authentication — so that refusal felt expected, not a crash. Where I tripped was the `evidence_invalid` promise: the page sells it as a third verdict with friendly "is this the right document?" guidance, but feeding a wrong PDF just threw a bare Spanish "Refused ... parse failed" at me with none of that guidance. And on the real mismatch, the page told me I'd see my value next to the PDF's value — instead I got two SHA-256 hashes, which told me *that* the NIF differed but not *what* either one was.

---

## Scorecard

- **Doc clarity:** 3.5 / 5 (well-structured and link-clean, but the `evidence_invalid`-as-verdict and "shows the value next to" promises don't match real output)
- **App capability:** 4 / 5 (file path, mismatch detection, history all work; pull refusal is graceful; only the parse-fail UX and hashed diff values are rough)
- **Findings by severity:** BLOCKER 0 · MAJOR 1 · MINOR 2 · NIT 3 (+1 observation)
