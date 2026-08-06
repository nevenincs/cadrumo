# Testimonial — docs/explanation/reviewing-and-exporting.md

- **Doc path:** `docs/explanation/reviewing-and-exporting.md`
- **Persona:** A curious autónomo reading the EXPLANATION of why review and the
  upload file are two separate things — fact-checking every claim against the
  real CLI rather than running a tutorial.
- **Date:** 2026-06-18

This is an explanation page, not a command walkthrough, so the "Walkthrough"
below is a claim-by-claim verification of the factual assertions the prose
makes, each checked against the live CLI and the source.

---

## Walkthrough (claim-by-claim verification)

### Claim 1 — "Review and export are worth doing only once the tool is satisfied the modelo is complete" (export refuses unverified drafts) — line 43

- **Command run:**
  `uv run --no-sync aeat app modelo export --help`
  and source inspection of `src/aeat/application/modelo/_export.py`.
- **Expected:** Export should only operate on a verified/filed calculation.
- **Actually happened:** The verb help reads "Exporta una revisión de modelo
  **verificada o presentada** a un fichero local compatible con AEAT
  (fichero-BOE). Local; nunca contacta con AEAT." The source
  `_load_revision_for_export` (`_export.py:279-287`) raises
  `CalculationRevisionStateError` (`export_revision_state_refused`) unless the
  revision state is one of `VERIFICADO_COMPLETO`, `PRESENTADO`,
  `PRESENTADO_SUPERSEDIDO`. The companion how-to `file-at-aeat.md:32` states the
  export "command refuses - run verification first." Fully grounded.
- **Verdict:** OK.

### Claim 2 — "AEAT accepts uploads only in one precise text format … a fixed-position layout, character for character" (the official upload file / fichero-BOE) — lines 11, 26-29

- **Command run:** Source inspection of `_export.py` (`ModeloExportResult.format`)
  and `file-at-aeat.md`.
- **Expected:** A fixed-width text artefact, not a spreadsheet.
- **Actually happened:** `ModeloExportResult.format` is documented as
  "currently always `"fichero-boe"`" (`_export.py:189`); `file-at-aeat.md:44`
  describes "a fixed-width text file in the official BOE layout." Accurate. The
  page wisely never names the file extension `.boe` itself — the `--output` path
  is operator-chosen — so it avoids over-specifying. Matches behaviour.
- **Verdict:** OK.

### Claim 3 — "Nothing is sent anywhere as part of producing it … the tool never submits for you" — line 29

- **Command run:** Source inspection (`_export.py` module docstring, lines 8-11).
- **Expected:** Export is offline-only.
- **Actually happened:** Docstring: "The service is local-only: it never
  contacts AEAT and never invokes `require_live_read`. Export is fundamentally
  an offline operation that produces a file the operator presents through
  sede.agenciatributaria.gob.es themselves." Confirmed.
- **Verdict:** OK.

### Claim 4 — "it reports a fingerprint of the file's exact contents, along with the file's size … re-derive the fingerprint from the file on disk and compare" — lines 34-37

- **Command run:** Source inspection of `_export.py` and
  `src/aeat/entrypoints/cli/_modelo_export_cli.py`.
- **Expected:** Export output reports a content hash and a byte size.
- **Actually happened:** `ModeloExportResult` carries `byte_size: int` and
  `file_sha256` (a 64-char SHA-256 hex, `_export.py:207-208`). The CLI text
  surface emits both: `_modelo_export_cli.py:199-200` prints
  `byte_size\t<n>` and `file_sha256\t<hash>`. SHA-256 is exactly the
  "change a single digit and the code changes completely" property described.
  The "re-derive and compare" workflow is sound (`sha256sum file`).
  Accurate, though the page says "a short code" — a 64-hex-char SHA-256 is not
  especially short; minor cosmetic looseness, not an error.
- **Verdict:** OK (NIT on "short code").

### Claim 5 — "The tool can also produce an offline spreadsheet file (an `.xlsx`) … It doesn't recompute, and there's no documented way to edit it and feed your changes back" — line 23

- **Command run:** Source inspection
  (`src/aeat/application/storage/calc_sheets/_workbook_export.py`,
  `build_offline_workbook`); review of `review-with-google-sheets.md` verbs.
- **Expected:** An offline static workbook exists; only the Google Sheets path
  supports pull-back of edits.
- **Actually happened:** `build_offline_workbook` (openpyxl) exists and is a
  static artefact. The only pull-back verb is
  `aeat config google sync calc pull` against a Google Sheets spreadsheet id
  (`review-with-google-sheets.md:67`); there is no offline-xlsx pull-back verb.
  The page's framing ("keepsake … use Google Sheets when you want to review and
  adjust") matches the actual capability split exactly. Honest and correct.
- **Verdict:** OK.

### Claim 6 — "Your calculation is laid out as a spreadsheet in Google Sheets … live formulas … pull your reviewed edits back" (Google Sheets export needs auth) — lines 17-21

- **Command run:**
  `uv run --no-sync aeat config google sync calc export --modelo 303 --year 2026 --period 1T`
  (no Google auth configured).
- **Expected:** A Google export should require authentication/an active profile.
- **Actually happened:**
  > `Refused. No hay ningun perfil activo. Ejecuta aeat config switch NAME o indica --profile.`
  > `  detail: No hay ningún perfil AEAT activo enlazado para Google OAuth.`
  Graceful refusal. The how-to `review-with-google-sheets.md` documents the
  prerequisite chain `aeat config google register` → `login` → `status` before
  `sync calc export`/`pull`/`verify`. The live-formula / pull-back narrative
  matches the documented verbs. The page correctly defers the mechanics to the
  linked how-to (this is an explanation page).
- **Verdict:** OK.

### Claim 7 — Cross-links and `{term}` references resolve — lines 17, 21, 31, 41, 43, 45

- **Command run:** `ls docs/explanation/ docs/how-to/`;
  `ls src/aeat/_data/terminology/concepts/`; `docs/conf.py` inspection.
- **Expected:** Every linked page and glossary term exists.
- **Actually happened:** All five linked Markdown files exist:
  `../how-to/review-with-google-sheets.md`, `../how-to/file-at-aeat.md`,
  `index.md`, `editing-and-verifying.md`,
  `recording-a-filing-and-the-boundary.md`. Glossary fragments `casilla.toml`
  and `modelo.toml` exist; `conf.py` registers `hoverxref_roles = ["term"]` and
  generates `docs/_generated/glossary.rst` at build, so `{term}`casilla`` and
  `{term}`modelo`` resolve. The same `{term}` syntax is used across sibling
  explanation pages. No broken link or dangling term found.
- **Verdict:** OK.

---

## Findings

1. **[NIT] [DOC]** Line 35 calls the SHA-256 fingerprint "a short code." The
   actual emitted value is a 64-character hex SHA-256 — accurate as a fingerprint
   but not "short." *Repro:* `aeat app modelo export` text output prints
   `file_sha256\t<64 hex chars>`. *Suggested fix:* "a fixed-length code" or "a
   long code" reads truer; or drop the size adjective.

2. **[NIT] [DOC]** The page never mentions that producing either output requires
   an active profile (and, in this non-interactive harness, a master-key
   passphrase). For an explanation page this is defensible — the prerequisites
   live in the linked how-tos and the pipeline overview — but a one-line "you'll
   need your profile set up first; see the pipeline overview" would close the
   loop for a reader who lands here directly. *Repro:* `aeat app modelo export …`
   with no profile returns `Refused. No hay un perfil activo. …`. *Suggested
   fix:* a single sentence pointing back to profile/pipeline setup.

3. **[NIT] [DOC]** Spanish/English friction: every refusal and all CLI help
   render in Spanish while the docs are English (e.g. `Refused. No hay un perfil
   activo. …`). This page never shows a command so it is not directly affected,
   but a reader who follows a link and runs a verb hits Spanish output with no
   forewarning anywhere on this page. Project-wide issue, noted for completeness.

No DOC-MAJOR/BLOCKER and no APP issues. Every load-bearing factual claim
(export refuses unverified drafts, fichero-BOE text format, never-submits,
fingerprint + byte size, static xlsx vs live Google Sheets, auth-gated Sheets
export, all cross-links/terms) verified true against the live CLI and source.

---

## Testimonial

As a curious reader I came in skeptical of an explanation page that promises a
clean two-outputs story, and it held up under fact-checking better than most
tutorials I've seen. The "review surface vs delivery format" framing maps exactly
onto what the tool does — the export verb really does refuse anything that isn't
verified or filed, it really is offline-only, and it really does hand back a
SHA-256 plus a byte size you can re-derive later. The single honest paragraph
admitting the offline `.xlsx` is a non-recomputing keepsake (not a review tool)
is the kind of candour that earns trust. Nothing here overstated the app; my
only nits are cosmetic (calling a 64-char hash "short") and a missing nod to the
profile/passphrase prerequisite for a reader who lands cold.

---

## Scorecard

- **Doc clarity:** 5/5
- **App capability:** 5/5 (every claim delivered)
- **Findings by severity:** BLOCKER 0 · MAJOR 0 · MINOR 0 · NIT 3
