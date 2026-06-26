# Testimonial — docs/how-to/ledger-evidence.md

- **Doc path:** `docs/how-to/ledger-evidence.md`
- **Persona:** A first-time user attaching supporting documents (invoices, receipts) to ledger entries, working in a non-interactive shell.
- **Date:** 2026-06-18

---

## Walkthrough

### Prerequisite setup (NOT on the page — inferred by a naive reader)

The page's "Before you start" says I need transactions in my ledger and points to
[Work with transactions](import-bank-statements.md). It does **not** mention I must
first create a taxpayer profile, nor that a master-key passphrase is required.

- **Commands run:**
  - `aeat config profile create TESTER --entity-type natural_person --tax-id 12345678Z --irpf-income-categories actividad_economica --quiet --accept-defaults`
  - `aeat app ledger import "$BASE/stmt.csv" --provider csv` (CSV: `date,amount,description` / `2026-03-10,-121.00,Papeleria Sol office supplies`)
- **Expected:** Be able to get a transaction id to attach to.
- **Actually:** Both succeeded. `import` reported `Entradas importadas 1`. `ledger list` gave transaction `1e267814...`. A profile had to be created first (the page never says so), and the harness pre-supplied the passphrase (the page never warns one is needed).
- **Verdict:** DOC-ISSUE / MINOR (missing profile + passphrase prerequisite).

### 1. `aeat app ledger evidence add`

- **Command:** `aeat app ledger evidence add "$BASE/inv.pdf" --supplier "Papelería Sol SL" --invoice-number "2026-0142" --invoice-date 2026-03-10 --taxable-base 100.00 --iva-rate 21 --iva-amount 21.00 --notes "Office supplies, March"`
- **Expected:** Stores the file's bytes + metadata, prints an evidence ID.
- **Actually:** OK. Printed `evidence_id  b8b1cdb0e1ec4bc0`, `media_kind pdf`, `source_sha256 ...`. One oddity: a literal placeholder leaked into output — `bucket_id  <bucket-id>`.
- **Verdict:** OK (APP-ISSUE / NIT for the `<bucket-id>` placeholder in real output).

### 2. `aeat app ledger attach <txn> --purchase-invoice-evidence-id <evidence-id>`

- **Command:** `aeat app ledger attach 1e267814 --purchase-invoice-evidence-id b8b1cdb0e1ec4bc0`
- **Expected:** Attaches the evidence to the transaction.
- **Actually:** Exit 0, printed the transaction detail (ID, Fecha, Importe, Estado de revisión). It does **not** confirm the evidence link in the output — the user can't tell from the result that the attach took effect (only the later `export` proved it did).
- **Verdict:** OK / NIT (no explicit "evidence linked" confirmation in output).

### 3. Refusal claims — "at most one purchase-invoice evidence; refuses a second; refuses re-attaching the same one"

- **Command A (re-attach same):** `aeat app ledger attach 1e267814 --purchase-invoice-evidence-id b8b1cdb0e1ec4bc0`
  - **Actually:** `Error. manual ledger update must change at least one ledger field`
  - This is a confusing generic message — it does NOT say "this evidence is already attached." A naive user can't connect it to the documented "refuses re-attaching the same one."
- **Command B (attach a second, different evidence):** `aeat app ledger attach 1e267814 --purchase-invoice-evidence-id 8f87ac0e3f1a4a38`
  - **Actually:** `Error. La transacción del libro mayor ya tiene un purchase_invoice_evidence_id; elimine o reemplace a través del flujo de adjuntos.` — clear and correct.
- **Verdict:** Command A: BOTH / MINOR (the re-attach refusal is opaque). Command B: OK. Also both errors exit 0 (see Finding 4).

### 4. `aeat app ledger doclink ... --source GOOGLE_DRIVE` (expected to refuse)

- **Command:** `aeat app ledger doclink 1e267814 --source GOOGLE_DRIVE --reference some-drive-file-id --note "Supplier invoice"`
- **Expected (per page):** Refuses because evidence must carry bytes, and tells me to download + attach instead.
- **Actually:** Refused gracefully and instructively (Spanish):
  `Invalid value: No se puede descargar el documento de GOOGLE_DRIVE para some-drive-file-id: la evidencia debe contener los bytes cifrados del documento, y un enlace nunca se guarda por sí solo. Descarga el documento y adjúntalo con 'aeat app ledger attach --attachment-id ...', o concede el permiso de Google requerido e inténtalo de nuevo.`
- **Verdict:** OK — the page set this expectation well and the refusal is graceful + points to the documented fallback. (Exit code 0 on a refusal — see Finding 4.)

### 5. `--attachment-id` generic-attachment fallback

- **Command:** `aeat app ledger attach 1e267814 --attachment-id nonexistent-file-id`
- **Expected:** Attach a stored file by its file-id.
- **Actually:** `Error. attachment_ids must reference existing secure attachment manifests and blobs`. The page says "Use `--attachment-id <file-id>` to attach stored files" and the doclink refusal also recommends this path — but **nowhere does the page (or the doclink error) tell you how to STORE a generic file and obtain a `<file-id>`**. There is no `evidence add`-equivalent for non-invoice attachments documented. A naive user following the refusal's advice is stuck.
- **Verdict:** DOC-ISSUE / MAJOR (dangling capability: no path to obtain a `<file-id>`).

### 6. Invoice tracking — `invoice add`

- **Command (received):** `aeat app ledger invoice add --kind received --counterparty-nif B12345678 --invoice-number "2026-0142" --invoice-date 2026-03-10 --taxable-base 100.00 --iva-rate 21 --iva-amount 21.00 --total-amount 121.00`
  - **Actually:** OK. `invoice_id d9d2557492074e1c`, `source_kind payable_invoice`, `counterparty_nif B12345678`. Placeholder leaked: `bucket  <profile-id>`.
- **Command (issued, EU):** `aeat app ledger invoice add --kind issued --counterparty-nif X1234567X --invoice-number "2026-0007" --invoice-date 2026-03-12 --country-code DE --eu-iva-id DE345678901 --operation-type S`
  - **Actually:** OK. `invoice_id 0be8ffa12d3145c2`, `source_kind collectible_invoice`. Note `counterparty_nif sha256:b20dcb16` (hashed), whereas the received invoice showed the NIF in plaintext — inconsistent redaction the page never mentions.
- **Verdict:** OK (APP-ISSUE / NIT: `<profile-id>` placeholder; inconsistent NIF display received-vs-issued).

### 7. Invoice list / view / update

- **Commands:** `invoice list`; `invoice view d9d2557 --kind received`; `invoice update d9d2557 --kind received --total-amount 121.00`
- **Actually:** All OK. `list` showed both kinds with prefix ids; prefix addressing worked for view/update.
- **Verdict:** OK.

### 8. `aeat app ledger link <txn> --invoice-id <invoice-id>` — **FAILS the documented workflow**

- **Command:** `aeat app ledger link 1e267814 --invoice-id d9d2557`
- **Expected (per page):** "Link an invoice record to the bank movement that settles it" — i.e. link the invoice I just created with `invoice add`.
- **Actually:** REFUSED:
  `Invalid value: Este id no existe en el catálogo de facturas de reconciliación, que se rellena con los flujos de importación y reconciliación de facturas. Los id generados por 'aeat app ledger invoice add' son registros de factura del operador y no se pueden vincular aquí. Para adjuntar evidencia de factura de compra, ejecuta 'aeat app ledger link <tx> --evidence-id <id>' (o 'aeat app ledger attach') con un id de 'aeat app ledger evidence add'.`
- `link --help` confirms it: `--invoice-id` is "Id del catálogo de facturas enriquecido, procedente de una factura importada o reconciliada... **NO es un id de 'aeat app ledger invoice add'.**"
- **Verdict:** BOTH / MAJOR. The page places `link --invoice-id <invoice-id>` directly under the `invoice add` section, strongly implying you link the invoice you just registered. The app categorically rejects that. The documented end-to-end flow (register an invoice → link it to the settling bank movement) is broken on this page.

### 9. Evidence list / view / update / remove

- **Commands:** `evidence list`; `evidence view b8b1cdb0e1ec4bc0`; `evidence update b8b1cdb0e1ec4bc0 --supplier "..."`; `evidence remove 8f87ac0e3f1a4a38 --yes`
- **Actually:** All OK. `list` showed both stored records; view/update/remove worked, `updated_at` advanced on update.
- **Verdict:** OK.

### 10. "Where evidence shows up" — exports include the evidence link

- **Command:** `aeat app ledger export --output "$BASE/export.jsonl" --export-format jsonl`
- **Actually:** OK. The exported row carried `"purchase_invoice_evidence_id":"b8b1cdb0e1ec4bc0"` and `"created_source_command":"aeat app ledger attach"`. This also retroactively proves command 2's attach succeeded.
- **Verdict:** OK — the claim holds.

---

## Findings

1. **[MAJOR][BOTH] Documented `link --invoice-id` does not accept `invoice add` ids.**
   Repro: `invoice add --kind received ... ` → `link <txn> --invoice-id <that-id>` →
   `Invalid value: ... Los id generados por 'aeat app ledger invoice add' ... no se pueden vincular aquí.`
   The page presents `link --invoice-id <invoice-id>` immediately after the invoice-add
   section, leading the user to expect they can link the invoice they just created. They
   cannot — `--invoice-id` only accepts reconciliation-catalog ids from import/reconcile flows.
   *Fix:* Either correct the page to state that `link --invoice-id` consumes **import/reconciliation**
   invoice ids (not `invoice add` ids), and remove/relabel the misleading example; or, if
   operator-added invoices are meant to be linkable, expose that path and document it. Mention
   the alternative the error gives: `link <tx> --evidence-id <id>`.

2. **[MAJOR][DOC] `--attachment-id <file-id>` has no documented way to obtain a `<file-id>`.**
   Repro: `attach <txn> --attachment-id nonexistent-file-id` →
   `attachment_ids must reference existing secure attachment manifests and blobs`.
   The page tells users to attach generic files via `--attachment-id <file-id>`, and the
   doclink refusal recommends the same path, but no command on the page stores a generic
   (non-invoice) file or produces a file-id. A naive user following the refusal's advice is stuck.
   *Fix:* Document the command that stores a generic attachment and yields a file-id, or
   drop the `--attachment-id` recommendation if no user-facing path exists.

3. **[MINOR][DOC] Missing prerequisites: taxpayer profile + master-key passphrase.**
   "Before you start" lists transactions and the invoice file, but not that a profile must
   exist first (`config profile create ...`) nor that a passphrase is required (a
   non-interactive shell is blocked without `AEAT_SECRET_PASSPHRASE` / the interactive prompt).
   *Fix:* Add a one-line prerequisite linking to profile setup and noting the passphrase prompt.

4. **[MINOR][APP] Refusals exit 0.** Every refused command above (`re-attach`, second
   evidence, `doclink` Drive refusal, bad `--attachment-id`, `link` rejection) printed an
   `Error.`/`Invalid value:` message but returned exit code 0. Scripting around these
   commands cannot detect failure. *Fix:* Return a non-zero exit code on refusal.

5. **[MINOR][BOTH] Re-attaching the same evidence gives an opaque error.** The page promises
   it "refuses re-attaching the same one," but the actual message is the generic
   `manual ledger update must change at least one ledger field` — it never says the evidence
   is already attached. *Fix:* Emit a specific "this evidence is already attached" message;
   the second-evidence refusal message is the good template.

6. **[NIT][APP] Placeholder tokens leak into real output.** `evidence add` printed
   `bucket_id  <bucket-id>` and `invoice add`/`invoice list` printed `bucket  <profile-id>` —
   literal angle-bracket placeholders instead of real values (or instead of being omitted).

7. **[NIT][APP] Inconsistent counterparty-NIF display.** `invoice add --kind received`
   showed `counterparty_nif B12345678` in plaintext; the EU `--kind issued` invoice showed
   `counterparty_nif sha256:b20dcb16`. The page doesn't explain when a NIF is hashed vs shown.

8. **[NIT][DOC] `attach` success gives no evidence-link confirmation.** After
   `attach ... --purchase-invoice-evidence-id`, the output is just the transaction row with
   no indication the evidence was linked; only the JSONL export revealed it. A short
   confirmation line would reassure the user the documented action took effect.

---

## Testimonial

Most of the page worked smoothly and honestly: adding evidence, attaching it, the
Google Drive refusal (which the page predicted and which redirected me helpfully), and
the promise that "exports include the evidence link" — the JSONL export really did carry
`purchase_invoice_evidence_id`, so the page delivered on its core claim. I tripped hard
on two things. First, the invoice-tracking finale: I dutifully ran
`invoice add` then `link --invoice-id <that id>` exactly as printed, and the app flatly
refused because that id "no se puede vincular aquí" — the documented end-to-end flow on
the page is broken. Second, the page (and the Drive refusal itself) kept pointing me at
`--attachment-id <file-id>` to attach a non-invoice document, but never told me how to
get a file-id, so that escape hatch was a dead end. As an English-only reader I also had
to puzzle through Spanish error text the page never warns about.

---

## Scorecard

- **Doc clarity:** 3 / 5
- **App capability:** 4 / 5
- **Findings by severity:** BLOCKER 0 · MAJOR 2 · MINOR 3 · NIT 3
