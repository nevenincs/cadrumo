# Testimonial — Classify transactions with an LLM

- **Doc path:** `docs/how-to/classify-with-llm.md`
- **Persona:** First-time user trying LLM-assisted classification of ledger rows; no
  assumed LLM provider, judging provider setup, data flow, preview-vs-apply, and refusal grace.
- **Date:** 2026-06-18
- **Environment:** `BASE=/tmp/persona-cllm-fg`, `uv run --no-sync aeat ...`, passphrase pre-set.

## Pre-work the page does not document (FINDINGS in their own right)

The page's first command is `aeat app ledger classify <transaction-id> --llm claude`,
but to reach it a naive user must already (a) have a profile and (b) have an
unclassified ledger row. The page only cross-links these; it never states the
prerequisites inline.

- Created a profile (not on this page; flag is `--tax-id`, not `--nif`):
  `aeat config profile create persona-cllm --entity-type natural_person --tax-id 12345678Z --irpf-income-categories actividad_economica --quiet --accept-defaults` → `EXIT=0`, `estado=creado`.
- Added two unclassified rows via `aeat app ledger add ... --direction OUTGOING` (Adobe €121, Renfe €54.50) → both `EXIT=0`, `Estado de revisión = pending`.

## Walkthrough

### `aeat app ledger providers` (not on page, but decisive for this persona)
- **Expected (from page):** Page implies a provider may not be installed/authenticated and to start at setup.
- **Actual:** `claude available`, `antigravity available`, `codex available` (all CLIs on PATH); `ollama-vision unavailable`. So "provider not available" is the wrong mental model here — the CLIs are present but **authentication state differs per provider**.
- **Verdict:** OK (app) / DOC-ISSUE MINOR — page never mentions `ledger providers` as the diagnostic to learn which providers are usable.

### `aeat app ledger list --filter classification=NOT_YET_PROCESSED`
- **Expected:** List rows still needing classification.
- **Actual:** `EXIT=0`; both rows listed with short+full id, date, amount, description, `pending`.
- **Verdict:** OK.

### `aeat app ledger view <transaction-id>`
- **Expected:** Row detail to judge the suggestion.
- **Actual:** `EXIT=0`; full field table, `Clasificación = NOT_YET_PROCESSED`.
- **Verdict:** OK.

### `aeat app ledger classify <id> --llm claude` (the headline command)
- **Expected (page lines 7-13):** "asks the `claude` provider for a suggestion and previews the result. It does not save anything."
- **Actual:** `EXIT=2`
  ```
  ┌─ Error ─
  │ Invalid value: La clasificacion por LLM fallo: claude CLI exited with 1:
  │ 'Not logged in · Please run /login\n'
  └─
  ```
- **Verdict:** APP-ISSUE MINOR — the provider's own message is surfaced (good), but a runtime provider failure is wrapped as `Invalid value` with click exit code 2 (parse-error class). It is reasonably instructive but does not point the user back to `setup-llm-classification.md`.

### Same command with `--llm codex`
- **Expected:** Preview with id, provider, classification, category, confidence, reason, **provenance**, and **whether persisted** (page lines 25-28).
- **Actual:** `EXIT=0`
  ```
  ID            d25add12...
  sugerencia-llm BUSINESS
  Categoría      software_suscripcion
  confianza      0.93
  motivo         Adobe Creative Cloud is a professional software subscription...
  Revisa la sugerencia anterior. Vuelve a ejecutar con --apply...
  ```
- **Verdict:** BOTH MINOR — the app **does** deliver a real preview (codex was logged in), but the output has **no "provenance" field and no "persisted: no" field** that the page explicitly promises. The next-step line implies non-persistence rather than stating it.

### `aeat app ledger classify <id> --llm antigravity`
- **Actual:** `EXIT=2` `Invalid value: La clasificacion por LLM fallo: no JSON object in LLM output: ''`.
- **Verdict:** APP-ISSUE MINOR — same exit-2 wrap; an empty/garbled provider response yields a cryptic message a naive user can't act on.

### `aeat app ledger categories` (step 2)
- **Actual:** `EXIT=0`; grouped `category-id`/`familia` table (e.g. `software_suscripcion office`).
- **Verdict:** OK.

### `aeat app ledger classify <id2> --llm codex --reject --reason "this is personal"` (step 3)
- **Expected:** Records proposal + reason as audit event; row left unclassified; later `view` flags it.
- **Actual:** `EXIT=0` `rechazada classification ... La transacción no cambia`. `view` later shows `Sugerencia del modelo  rechazada: this is personal`, `Clasificación NOT_YET_PROCESSED`.
- **Verdict:** OK — exactly as documented.

### `aeat app ledger classify <id> --llm codex --apply`
- **Expected:** Saves classification + category; records LLM used, confidence, reason.
- **Actual:** `EXIT=0` `clasificado-por llm:codex; Estado de revisión reviewed`. `view`: `Clasificación BUSINESS`, `Categoría software_suscripcion`. `history` shows `ledger.transaction.classified`.
- **Verdict:** OK (mostly) / DOC NIT — the saved record surfaces `llm:codex` provenance, but the **confidence and reason** the page says are recorded are not shown in `view` or `history` output.

### `aeat app ledger classify <id> --llm codex --saturate` (preview)
- **Expected:** Adds IVA category + derived base/rate/amount summing to the total.
- **Actual:** `EXIT=0` — `Categoria de IVA domestic_general_21`, `Base 200.00`, `Tipo 0.21`, `IVA 42.00` (200+42 = 242 total). Exactly as promised.
- **Verdict:** OK — strong delivery.

### Derive-yourself path (no `--llm`)
- `classify <id> --classification BUSINESS --category-id mobiliario_amortizable` then `classify <id> --iva-category domestic_general_21 --saturate`.
- **Actual:** `EXIT=0`; second command yields `clasificado-por derived:iva-category`, base/rate/amount derived. Matches "Derive the IVA fields yourself".
- **Verdict:** OK.

### Manual override by hand
- `classify <id> --classification BUSINESS --iva-category domestic_reduced_10 --taxable-base 110.00 --iva-rate 0.10 --iva-amount 11.00` → `EXIT=0`, `reviewed`.
- **Verdict:** OK.

### Documented combined-flag refusals
- `--llm codex --from-csv ...` → `EXIT=2` `Invalid value: --llm no puede combinarse con --classification ni --from-csv...` (matches "Current limits").
- `--llm codex --apply --reject` → `EXIT=2` `Invalid value: --reject no se puede combinar con --apply...` (matches step 3).
- **Verdict:** OK — both guardrails fire with clear messages.

### Batch CSV `aeat app ledger classify --from-csv ./classifications.csv`
- CSV `transaction_id,classification,category_id` with one PERSONAL row → `EXIT=0` `clasificación masiva: 1 filas, 1 aplicadas, 0 omitidas, 0 fallidas`.
- **Verdict:** OK.

### `aeat app ledger preflight --year 2026 --period 1T`
- **Actual:** `EXIT=0`; `ready false`, flags the plain-applied Adobe row as `missing_taxable_base / missing_iva_amount / missing_iva_rate`, confirming the page's note that a plain applied suggestion does not fill regulated tax fields.
- **Verdict:** OK — good corroboration of the doc's "Current limits".

### `rule add` / `rule apply --dry-run`
- `rule add --description-pattern "software" --classification BUSINESS --category-id software_suscripcion` → `EXIT=0`.
- `rule apply --dry-run` → `EXIT=0` `simulacro: 0 transacción(es) se clasificarían` (matching row already classified).
- **Verdict:** OK.

### `--read-evidence` / `--auto-split` with no attachment
- `classify <id> --read-evidence --saturate` (no attachment, no `--llm`) → `EXIT=1`
  ```
  Error. classifying this transaction needs a cloud provider: pass --llm with
  claude, antigravity, or codex. (--read-evidence reads a scanned or image
  invoice on-host with no provider, but this transaction has no readable image
  evidence to route there.)
  ```
- **Verdict:** OK — graceful, instructive, and explains the on-host-vs-cloud routing. Note exit code **1** with clean `Error.` here vs **2** `Invalid value` on the provider-not-logged-in path — inconsistent error class for "this won't work right now".

## Findings

1. **[MINOR][DOC]** Missing inline prerequisites. The page jumps straight to `classify <id> --llm claude` but a naive user has no profile and no rows. The profile flag is `--tax-id` (the obvious `--nif` is silently ignored — `profile create persona-cllm --nif ...` exits 0 with no profile created). *Fix:* one sentence "you need an active profile and at least one unclassified row" + link, and mention `aeat app ledger providers` as the way to learn which providers are usable.

2. **[MINOR][BOTH]** Preview output contract overstated. Page (lines 25-28) promises the preview shows "provenance, and whether the result was persisted." The real preview shows `ID, sugerencia-llm, Categoría, confianza, motivo` and a next-step line — **no provenance field, no persisted flag**. *Fix:* align the prose with the actual fields, or have the app emit an explicit `persisted: no` / provenance line.

3. **[MINOR][DOC/APP]** Applied-suggestion record claims unverifiable confidence/reason. Page says apply "records that an LLM was used, along with the confidence and reason," but `view`/`history` only surface `clasificado-por llm:codex` — confidence and reason are not visible. *Fix:* either surface them in `view`/`history`, or soften the claim.

4. **[MINOR][APP]** Inconsistent failure surface for unusable providers. A logged-out provider yields `Invalid value: ... 'Not logged in · Please run /login'` (click **exit 2**, parse-error class) and a garbled response yields `Invalid value: no JSON object in LLM output: ''`, while a missing-evidence routing failure yields a clean `Error.` (**exit 1**) that names the fix. *Fix:* route provider runtime failures through the same `Error.`/exit-1 channel and point the user to `setup-llm-classification.md`.

5. **[NIT][DOC]** Page never warns that a master-key passphrase is required. (Pre-set by the harness here; a naive user in a non-interactive shell would be blocked.) Common to all ledger pages — worth a shared note.

6. **[NIT][DOC]** English docs, Spanish CLI output. All preview/error text renders in Spanish (`sugerencia-llm`, `confianza`, `Invalid value: La clasificacion por LLM fallo`). An English-only reader following an English page sees only Spanish responses; the page never sets this expectation.

## Testimonial

Following the page literally, I tripped immediately because nothing told me I needed a
profile or a row first, and the natural `--nif` flag silently does nothing. Once I had
rows, the page delivered well: with a logged-in provider the preview, reject, apply,
saturate, self-derive, manual override, combined-flag refusals, CSV batch, and preflight
all behaved exactly as described — saturate even derived base 200 + IVA 42 = 242 on the
nose. The rough edges were honesty gaps, not capability gaps: the preview lacks the
"provenance / persisted" fields the page promises, applied confidence/reason aren't
visible anywhere, and a logged-out provider fails as a cryptic `Invalid value` (exit 2)
instead of pointing me at the setup page. The refusals I could trigger were graceful;
the only ungraceful one was the provider-auth path.

## Scorecard

- **Doc clarity:** 3.5 / 5
- **App capability:** 4.5 / 5
- **Findings by severity:** BLOCKER 0, MAJOR 0, MINOR 4, NIT 2
