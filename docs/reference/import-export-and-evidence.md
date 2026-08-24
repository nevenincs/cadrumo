# Import, export, and evidence

At a high level, the architecture turns source documents and operator inputs
into a traceable tax position. It deliberately separates “data we received,”
“values we calculated,” “a file prepared for the Agencia Estatal de
Administración Tributaria (AEAT),” and “evidence that AEAT actually received
it.”

`source documents → typed financial facts → registry-grounded calculation → AEAT upload file → official filing evidence`

## What the data actually represents

| Layer | Actual data | Meaning for you |
| --- | --- | --- |
| Source evidence | Taxpayer document bytes, provenance, and content digests; separately, official source material grounds the registry | The original material supporting the tax position and the sources governing its interpretation |
| Ledger facts | Typed transactions, direction, category, amount, dates, and linked evidence | The economic events that may participate in a return; the filing period is derived from their dates |
| Other business inputs | Typed invoice catalogues and stock-inventory ledgers in encrypted repositories; typed foreign-asset observations supplied by the caller | Reusable business facts that remain separate from a filing until an enrolled resolver projects them |
| Registry | {term}`modelo` revision, numbered {term}`casilla` fields, formulas, bindings, legal references, and export layout | The versioned rulebook used to interpret the facts |
| Calculation revision | Inputs, observations, overrides, calculated casillas, and provenance | A reproducible attempt at calculating one return |
| Filing record | Current or superseded filing state linked to a calculation revision and optionally carrying external AEAT evidence | What the application records as filed, and the history behind it |
| Official evidence | {term}`justificante`, AEAT verification record, or captured filed declaration | Evidence originating from AEAT after submission |

Every calculated casilla can carry formula, legal, and source provenance. Ledger
evidence records which financial facts contributed to it. Review the values in
[Review calculation values](../how-to/review-calculation-values.md), then follow
the full revision workflow in [Prepare and manage filings](../how-to/filing-spine.md).

A registry binding is a typed projection contract, not a place to attach a
source record. Binary documents follow the encrypted attachment path.
Transactions, invoice catalogues, and stock inventory remain in their owning
typed repositories. Modelo 720 instead accepts typed foreign-asset observations
from the caller. An enrolled resolver projects only the scalar or repeating-row
fields requested by the registry. Stock `InventoryLedger` records are encrypted
and usable for valuation, but they are not currently enrolled as a calculation
source and do not flow into a calculation revision.

## What can be imported

- **Bank and financial transactions:**

  - CSV or TXT containing supported delimited bank data
  - XLSX, but not legacy XLS
  - OFX or QFX when the optional OFX dependency is installed
  - Recognized German-language N26 monthly statement PDFs

  These become normalized ledger transactions, not tax-return values directly.
  File detection also uses content signatures to avoid trusting misleading
  extensions. Importing a row does not infer business use, category, taxable
  base, Impuesto sobre el Valor Añadido (IVA), or Impuesto sobre la Renta de
  las Personas Físicas (IRPF) treatment. See
  [Import and manage transactions](../how-to/import-bank-statements.md).

- **Purchase invoices and receipts:**

  - PDF
  - PNG or JPEG image evidence
  - CSV or XLSX for structured invoice-catalogue rows

  Document bytes are stored as evidence and can then be linked to ledger facts.
  Structured invoice rows, document evidence, and bank transactions remain
  separate records until you link them. These records can substantiate a
  transaction or IVA treatment. Importing an invoice does not automatically
  make it deductible. See
  [Attach invoices and receipts](../how-to/ledger-evidence.md) and
  [Manage business invoices](../how-to/manage-invoices.md).

- **AEAT declaration copies:**

  - PDF, but only where the relevant Modelo and revision have an exact extraction
    profile

  These produce observed casilla values with document digest and registry
  revision provenance. They are observations, not automatically trusted
  calculation authority. Casilla reconciliation currently covers modelos 100,
  111, 130, 190, 303, and 390.

- **AEAT submitted-data files:**

  - Fixed-width “Diseño de Registros” files
  - XML-dictionary layouts

  These can be parsed into casilla observations where a complete registry layout
  exists. Support is revision-specific, not universal. This surface parses AEAT
  archive bytes; the submitted-data importer is not a general CSV importer.

- **AEAT justificantes:**

  - Justificante PDF or a receipt read from AEAT

  The parser extracts receipt metadata such as Modelo, period, taxpayer,
  submission time, verification code, and totals. A justificante supports the
  claim that AEAT returned specific receipt information. It is not necessarily a
  complete representation of every filed casilla, and it does not prove that the
  tax answer is correct. See [Reconcile a filing](../how-to/reconcile.md).

- **Google Drive and Sheets:**

  - Drive links and folder pulls acquire supported PDF, PNG, and JPEG bytes through
    the normal encrypted attachment path.
  - Sheets can provide typed operator, binding, and relation edits for
    calculation. Pull can also assemble row-set observations in its output.
  - Sheet-based computation uses the canonical local calculation engine and is
    explicitly non-persistent until another canonical workflow accepts the
    result.

  Google is an optional acquisition and review adapter, not the tax database,
  ledger authority, calculation authority, or recovery system. See
  [Review calculations with Google Sheets](../how-to/review-with-google-sheets.md).

## What each export actually means

| Export | Purpose | What it does not prove |
| --- | --- | --- |
| AEAT fichero or XML export | Produces the local payload you can upload through AEAT’s official interface where the selected Modelo revision has a complete registry export layout | It does not prove submission or acceptance |
| Google Sheet export | Human review, reconciliation, parity checking, and what-if editing | It is not a filing artefact or authoritative calculation record |
| Accountant review package | Shares the draft, calculation revision, provenance, and ledger evidence when present in a checksum-verifiable ZIP | Checksums alone do not identify who created or approved it |
| Evidence bundle | Forensic package containing referenced record bytes and a content-addressed manifest | It is not itself AEAT-issued evidence |
| Sealed custody archive | Backup and full recovery of the secured profile | It is not the same thing as an audit or accountant package |

The filing exporter explicitly writes a local file and never contacts AEAT. It
can reread the output and detect drift from the approved draft for
parser-covered casillas. It reports any unchecked casillas separately. This
remains pre-filing verification. Follow
[File your modelo at the AEAT portal](../how-to/file-at-aeat.md) to
complete the operator-controlled filing steps.

The application labels local exports as
`local_export_not_official_aeat_filing_evidence`. Official proof must come back
from AEAT as a justificante, filed-declaration history, verification record, or
captured filed copy.

The base accountant review ZIP is plaintext and checksum-verifiable. Separate
operations can add an Ed25519 signature envelope or encrypt the package for a
registered recipient. Verify signatures against a trusted public key. Signing,
counter-signing, receipt verification, and recipient encryption are distinct
operations. A review-only handoff carries no filing authority.

Signing and counter-signing leave the ZIP plaintext. Creating a
counter-signature does not verify the operator signature or archive;
receipt verification performs those checks. Recipient encryption encrypts the
bytes supplied to it, but does not first require checksum or signature
verification. After decryption, verify the recovered package and signatures
separately.

No command writes a portable profile bundle or a data-subject right-of-access
response in this version. The commands that produced them were withdrawn when
profile storage moved to the sealed capsule.

The profile manager can still write a portable bundle: run `aeat config profile
edit` with no other arguments to open it, then choose the export action. Do not
use it to move a profile between machines or storage roots. Nothing in this
version reads such a bundle back, because the import half was withdrawn
alongside the command-line verbs, so a bundle written today cannot be loaded by
this version. Treat the file as opaque until an import surface returns.

This is a portability gap, not a recovery one. Backup and recovery are
unaffected and run through `aeat config profile archive export` and
`aeat config profile restore`, which operate on the sealed profile capsule.

The sealed custody archive is an encrypted profile backup, not a structured,
readable copy of one profile's records. It excludes recovery material,
process-local state, and rebuildable derivatives. Restore it with the profile
passphrase. Recovery restore requires an externally provisioned matching
artifact, its 24-word phrase, and the source capsule; the CLI does not currently
export that artifact. The proof restores the data path only; it does not reset
the passphrase or enroll recovery in the restored profile.

## What an audit export is for

When an audit or professional review is requested, the audit evidence bundle is
intended to let the recipient establish:

- Which original records supported the return.
- Whether those bytes still match their recorded SHA-256 digests.
- Which ledger facts contributed to which casillas.
- Which registry and legal references governed the calculation.
- Which calculation revision and filing record were involved.
- Whether later revisions superseded the original position.

The audit evidence bundle ZIP file contains reachable record bytes followed by `manifest.json`.
Failed verification prevents export; incomplete packages require an explicit
override. `audit check` reruns the bundle checks but never contacts AEAT or
recalculates the tax result. Through the current command-line interface,
`check` cannot verify referenced record bytes because no payload loader is
supplied.

The current audit commands do not yet provide a complete one-command audit
handoff. The command-line audit surface has no payload-loader registry or
bundle-build command. Every
non-empty audit evidence bundle therefore appears incomplete through the command-line
interface. A forced incomplete export may omit records and may contain only the
manifest. Do not treat that output as a complete evidence package.

## What a complete audit handoff means

A genuinely complete audit handoff would normally combine:

1. Official AEAT evidence proving submission.
2. The exact submitted-file digest or captured filed copy.
3. A verified audit evidence bundle containing every referenced supporting record.
4. The calculation or review package explaining how those records produced the
   declared casillas.

That combination supports both halves of the audit question: “Was this actually
filed?” and “What facts, rules, and calculations produced it?”

The audit evidence bundle does not currently include every item listed above.
Assemble and verify the missing items separately; a bundle is complete only
when every referenced supporting record and payload is present.

## Important limitations

Support is limited to Modelo and revision combinations backed by registered,
authoritative layouts and real evidence. Consequently:

- Import and export support must not be described as universal across all
  Modelos and periods.
- Filed declaración-PDF extraction requires an exact registered profile.
- An operator-supplied local observation, local export, checksum, Google Sheet,
  or review ZIP cannot prove AEAT acceptance. A locally held AEAT justificante
  can become official evidence. Import it through the external-evidence
  workflow.
- Integrity proves that bytes have not changed; it does not establish signer
  identity or independent legal authenticity. Use the separate review-package
  signing workflow when author identity matters.
- Evidence is encrypted in normal custody. Base review and audit ZIPs are
  deliberate plaintext exports, so secure delivery becomes your responsibility.
- A forced incomplete audit evidence bundle export is not a complete handoff.
- `audit check` reruns bundle checks. Through the current command-line
  interface, it cannot verify referenced bytes, and it does not reproduce or
  recalculate the tax decision.

For storage, recovery, and external-access boundaries, see
[Protect access to taxpayer data](../how-to/protect-data-access.md) and
[Filesystem, state, and safety](filesystem-state-and-safety.md).
