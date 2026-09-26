---
tags:
  - '#adr'
  - '#export-parity'
date: '2026-09-26'
modified: '2026-09-26'
body_schema: 'body-v2'
body_hash: 'sha256:de1c024449682ba0994e02d68288174bc6b0827b3ffb0441209b19a1899b10c8'
related:
  - "[[2026-09-26-export-parity-calculation-report-adr]]"
  - "[[2026-09-07-tuimodelo-export-destinations-adr]]"
  - "[[2026-09-26-export-parity-calculation-summary-pdf-research]]"
  - "[[2026-09-26-export-parity-adr]]"
  - "[[2026-07-12-license-posture-adr]]"
  - "[[2026-06-03-modelo-export-visual-design-adr]]"
---

# `export-parity` adr: `calculation summary pdf` | (**status:** `proposed`)

## Problem Statement

The accepted calculation-report decision (`2026-09-26-export-parity-calculation-report-adr`) settles only that the PDF renders the one typed report with ReportLab behind an optional extra. On 2026-09-26 the operator raised the bar for the PDF: an autonomo or accountant must be able to read it, a machine must recover the same content without OCR, the structured data must travel inside it, the calculation must be certified, and hash identifiers must trace the document back to the encrypted store and prove it still matches. Meeting that means choosing a container standard, an authoritative machine carrier, an embedding and metadata-privacy policy, a signing key and message, and a verification flow. Each becomes costly to reverse once documents are in the hands of accountants, because every PDF already issued must keep verifying. This record proposes those choices as an amendment to the calculation-report decision for the PDF destination; the CSV destination and the single-builder rule are unchanged apart from the builder requirements under Constraints.

## Considerations

- Standards, library, validator and repository evidence, and the spike results, are in `2026-09-26-export-parity-calculation-summary-pdf-research`.
- One builder produces the report and serialisers add no content (`2026-09-26-export-parity-calculation-report-adr`); destinations are typed, capability-gated, no-clobber and shared by CLI and TUI (`2026-09-07-tuimodelo-export-destinations-adr`, `src/cadrumo/application/modelo/export_sink.py:53`).
- The development mock software identity must be disclosed on every artefact that depends on it (`2026-09-26-export-parity-adr`).
- The core dependency closure stays free of strong copyleft; new runtime reliance goes through a disclosed extra (`2026-07-12-license-posture-adr`).
- The artefact family shares one visual language with the workbook and the TUI (`2026-06-03-modelo-export-visual-design-adr`, `src/cadrumo/entrypoints/tui/components/theme.py:29`).
- Private data leaves the encrypted store only by explicit operator direction and in the minimum necessary form; document metadata is copied by indexers, mail previews and document stores well beyond the page itself.
- Absent, zero and not-applicable remain distinct, and a local calculation is never presented as an official AEAT value.
- A recipient usually has no Cadrumo; only the installation holding the store can prove the document matches its data.

## Considered options

**Container.**

- Plain PDF with separate JSON and CSV files: rejected; the carriers drift apart from the page and the operator asked for embedding.
- PDF/A-3a plus PDF/UA-1 with associated files: chosen; archival, accessible and validator-checkable on the PDF 1.7 base, as Factur-X does for invoices.
- PDF/A-4f on PDF 2.0: deferred; only a PAdES Ed25519 signature needs it, and the spike shows it validates if a later amendment wants it.

**Authoritative machine carrier.**

- XMP as the data carrier: rejected; tools re-serialise it and it holds only strings.
- Extracted page text: rejected; it is locale-formatted presentation.
- The canonical report JSON attachment, with CSV as a supplement, XMP as a mirror of a signed statement and the tagged text for people and assistive technology: chosen.

**Certification.**

- PAdES/CMS with the profile Ed25519 key and a self-signed certificate: rejected for now; it adds pyHanko and its certificate-validation tree, needs a PDF 2.0 base, has no verified viewer support for EdDSA, shows as untrusted in every viewer, breaks on a benign re-save and carries no trace to the store.
- PAdES with the taxpayer's AEAT authentication certificate: rejected; it would turn a local calculation into a document signed by the taxpayer and use an authentication credential for document signing.
- A detached Ed25519 signature over a domain-separated certification statement, made with the existing profile key: chosen.

**Renderer.**

- WeasyPrint: rejected; tagging and PDF/A are built in, but it needs the Pango native stack on every Windows install.
- fpdf2 or PyMuPDF: rejected on licence (LGPL-3.0, AGPL-3.0).
- Open-source ReportLab for layout plus a pikepdf pass for tags, attachments, XMP and output intent: chosen; the spike reaches veraPDF `3a`, `3u` and `ua1` with no new dependency beyond ReportLab.

## Constraints

- Requirements on the calculation-report builder, which the PDF cannot meet by adding content of its own:
  - The report digest's preimage is exactly the canonical record encoding of the report body without its own digest (`src/cadrumo/core/hashing.py:80`); the PDF embeds those bytes verbatim.
  - The report carries its language, a row role (line, subtotal, result) so totals can be emphasised, labels in the report language, and the header facts listed under traceability below.
  - Per-row source provenance is carried as a keyed digest of each `source_provenance` row, never the raw `source_ref`, because a reference can embed a third party's NIF (`src/cadrumo/application/aggregation/modelo_bindings_retenciones.py:213`) and an unkeyed hash of a NIF is enumerable. This applies to the CSV now being built as well.
  - Evidence is carried as pairs of evidence-reference digest and content SHA-256, never as bytes or file names.
  - The builder is deterministic: the stored revision, its pinned registry snapshot and authority generation, the language, the export instant and the taxpayer disclosure mode reproduce identical bytes. The store trace depends on it.
  - When the builder cannot state a fact the PDF shows, the PDF shows that absence; it never computes a substitute.
- ReportLab emitting one text object per draw call, and pikepdf re-serialising XMP on save, are library behaviours of `reportlab@5.0.1` and `pikepdf@10.13.0`; both are pinned by tests, and the verifier never compares XMP bytes.
- Every shipped font must pass a glyph-width consistency gate; ReportLab mis-subsets fonts with a compact horizontal-metrics table (`2026-09-26-export-parity-calculation-summary-pdf-research`).
- Matterhorn human-judgement conditions cannot be proven by a validator; they need a recorded review of the layout per modelo family.
- The signing key is the per-profile key in encrypted custody (`src/cadrumo/application/modelo/review_package_signing_ports.py:18`, `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py:943`); its private half never leaves the process.

## Implementation

**Artefact.** A4 portrait on a white ground in the brand light palette with AA-contrast inks. Page one carries a brand rule; the H1 `Resumen del cálculo · Modelo NNN` in the report language; a subtitle with year, period and registry revision; a notice panel, always present, stating that this is a local calculation and not AEAT evidence, that the AEAT receipt, lookup or CSV check is the official proof, and the software-identity grade (for the development mock: program `0000`, developer NIF `00000000T`, not presentable at AEAT); a facts table (revision state, verification outcome, filing status, export instant, taxpayer per the disclosure policy); and a legend for the three value states. One H2 per registry section follows in registry order, each a three-column table (casilla, concepto, importe) whose header repeats as an artifact on continuation pages. Amounts, casilla numbers and identifiers are set in a tabular monospace and right-aligned; a proven zero prints as a formatted zero, an absent value as `— sin dato` in warning ink, not applicable as `n/a · no aplicable` in muted ink, so the states differ in text and not only in colour; subtotals are bold and the result row carries the success wash. A closing section `Trazabilidad e integridad` prints every identifier in full, the report and CSV digests, the signing-key fingerprint and one sentence on what the signature does and does not mean. Every footer, marked as an artifact, repeats the local-calculation notice, page `n de N` and a revision-id prefix. Text is set in Hanken Grotesk; the monospace is JetBrains Mono if its static TrueType instance passes the width gate, otherwise Liberation Mono; both ship as static TTF package data with their SIL OFL notices. Chrome strings come from the locale catalogue in es, en, ca and hu with real translations; numbers follow the locale; the document `Lang` is the report language. The file is PDF/A-3a and PDF/UA-1: every text object tagged (Document, H1, H2, P, Div, Table, TR, TH with Scope, TD) or marked as an artifact, `MarkInfo`, `Lang`, `DisplayDocTitle`, a fixed sRGB output intent, no document information dictionary, embedded font subsets.

**Machine carriers, in order of authority.** `cadrumo-calculation-report.json` (`Data`, `application/json`) is authoritative: the builder's canonical bytes. `cadrumo-calculation-report.csv` (`Supplement`, `text/csv`) is byte-identical to the CSV destination's output for the same report. `cadrumo-report-certification.json` (`Unspecified`) is the canonical certification statement and `cadrumo-report-certification.sig` (`Unspecified`) its 64-byte signature. XMP carries `pdfaid`, `pdfuaid`, title, language, a description stating the local-calculation status, dates equal to the export instant, and a product namespace `https://github.com/nevenincs/cadrumo/ns/calculation-report/1/` that mirrors the statement field by field, with extension schemas declared for it and for `pdfuaid`. A null identifier is an omitted property, never a spelled `none`. XMP is never authoritative: any disagreement with the statement is a refusal. The tagged text layer serves people and assistive technology, and the verifier checks it semantically.

**Embedding policy.** Embedded: font subsets, the output intent, the report JSON, the CSV, the statement and the signature. The fichero-BOE is not embedded: the review package remains its channel, embedding it would make a summary a second carrier of a presentable-looking file stamped with the mock identity, and a PDF recipient cannot validate it; if the builder records the fichero digest, the statement carries it so a separately received file can be matched. Evidence bytes (invoices, justificantes, third-party documents) are never embedded; the report carries only evidence-reference digests and content SHA-256, which a store holder can prove. AEAT's CSV verification code is neither printed nor put in metadata, because it opens the official receipt at AEAT to anyone holding it; the summary states only whether an AEAT receipt is recorded.

**Certification.** The signed message is the canonical statement: statement schema, render profile, report schema, report SHA-256, CSV SHA-256, visible-layer SHA-256, every traceability identifier, software-identity grade, export instant, `aeat_official: false`, and the signing key's algorithm, public key and fingerprint. The signature is Ed25519 over SHA-256 of a fixed context string `cadrumo/calculation-report-certification/v1`, a NUL byte and the statement bytes, produced by the existing digest primitive (`src/cadrumo/core/ed25519_signing.py:85`) with the profile keypair obtained through `ReviewPackageSigningKeypairCapability`; the context prefix keeps a report signature from ever verifying as a review-package signature under the same key. The visible-layer digest is SHA-256 over the canonical list of each page's media box, the SHA-256 of its decoded content streams and the SHA-256 of each font program; pages must carry no annotations and no resources other than fonts. The signature asserts that this profile's key attests that, at the export instant by this installation's clock, the named calculation revision in the named state, verification report, registry snapshot and authority generation produced exactly this report, CSV and page layer. It does not assert AEAT acceptance or filing, legal correctness, the truth of the inputs, the taxpayer's identity or consent, a trusted time, or that the key belongs to a named person. Surfaces call it the Cadrumo integrity signature, never a certificate, so nothing suggests an AEAT or qualified signature.

**Traceability identifiers.** In the statement, the report header, the XMP mirror and the trace section of the page: calculation revision id and state, work unit id, verification report id and completeness, filing record id or its absence, registry snapshot (modelo, registry revision id, year, period), authority logical generation, software-identity grade, export instant, report SHA-256, CSV SHA-256, visible-layer SHA-256, statement SHA-256 and signing-key fingerprint. In the report JSON only: per-row keyed source-provenance digests, evidence-reference digests with content SHA-256, and the ledger filing snapshot fingerprint when the revision has one.

**Verification and trace.** One application service verifies a file in two layers and returns a typed outcome, `verified`, `verified_with_later_changes` or `refused`, with one row per check and a closed set of reasons. The document layer needs no store: `pdf_unreadable`, `not_a_cadrumo_report`, `attachment_missing`, `statement_unreadable`, `statement_not_canonical`, `unsupported_statement_schema`, `signature_invalid`, `signing_key_untrusted` (the key differs from an explicitly trusted key, or from the profile key when the store layer runs), `report_digest_mismatch`, `csv_digest_mismatch`, `report_not_canonical`, `report_statement_mismatch`, `csv_not_derived_from_report`, `metadata_mismatch`, `visible_layer_mismatch`, `visible_layer_overlay` and `text_layer_mismatch`. With no trusted key and no store, a cryptographically valid file is reported as valid but unpinned, never as verified, because a consistent forgery under another key passes the document layer. The store layer runs when the active profile is unlocked: `signing_key_not_this_profile`, `calculation_revision_not_found`, `work_unit_mismatch`, `registry_snapshot_mismatch`, `verification_report_mismatch`, `filing_record_mismatch`, `authority_generation_unavailable` (the rebuild cannot run; the outcome is refused as unprovable, not verified), `report_rebuild_mismatch`, `source_provenance_mismatch`, `evidence_missing` and `evidence_digest_mismatch`; the informational `revision_state_changed` and `filed_since_export` yield `verified_with_later_changes`. The rebuild reruns the builder with the recorded language, export instant and disclosure mode and compares digests. Without Cadrumo, a recipient extracts the attachments in any viewer or with `qpdf`, hashes them, and verifies the signature with OpenSSL 3 over the prefixed statement digest; the user documentation carries that recipe. Key trust comes from the fingerprint printed on the page, compared with one received out of band; it is the same key a recipient already uses for the operator's review packages.

**Metadata privacy.** XMP, attachment names and descriptions carry only content-addressed identifiers, digests, modelo, year and period codes, the grade, the export instant and the public key. They never carry a NIF or name in any form, an actor label, a bucket or profile identifier, an AEAT CSV code or an amount; there is no document information dictionary. The page body, JSON and CSV carry exactly what the report carries; the taxpayer is shown masked by default in the CLI redaction's form, and an explicit `--disclose-taxpayer` shows NIF and name. The mode is recorded in the report and covered by the signature. The embedded public key links every summary from one profile, by design.

**Dependencies and gating.** ReportLab gains a runtime `pdf` extra (`reportlab>=5.0.1,<6`) while keeping its development entry; `PDF_EXTRA` joins the optional-extras registry with `reportlab` as its exclusive probe; notices add ReportLab (BSD) and the fonts (OFL). No pyHanko, WeasyPrint or fontTools. veraPDF is a development and CI oracle fetched as a checksum-pinned jar and run by a development recipe, never a Python dependency. Without the extra, the PDF destination reports itself unavailable with the install hint, and the CLI refuses `--document-format pdf` before reading the store. Verification needs no extra: pikepdf, pypdfium2 and cryptography are core, XMP is read through pikepdf's metadata interface rather than a new direct parser dependency, and the rebuild uses the builder, not the renderer.

**Surfaces.** The CLI produces a summary with `aeat app modelo work report --document-format pdf --output PATH` plus the existing `--output-language` option and `--disclose-taxpayer`, through the report verb the calculation-report work owns. It verifies with a sibling verb, `aeat app modelo work report-verify PATH [--trusted-key HEX] [--document-only]`, which mirrors `review-package verify` and adds no root. Both emit the standard JSON envelope, and the verify verb exits non-zero on refusal. The TUI offers the summary as a capability-gated destination in the existing export flow and a verify action on the work screen, both calling the same application service and rendering the same check rows.

**Steps**, each independently verifiable and committed on its own:

- `S1` Builder conformance: row role, language, keyed provenance digests with their per-profile key, evidence pairs, disclosure mode, deterministic rebuild. Tests: identical bytes across two builds and two processes; a synthetic perceptor NIF never appears in any provenance field (detector teeth: a raw-reference fixture is refused); absent, zero and not-applicable round-trip.
- `S2` Packaging: `pdf` extra and `PDF_EXTRA`, static font instances and one fixed sRGB profile as package data, notices, the doctor row. Tests: registry probe; the missing-extra refusal through the real import blocker; the packaging gate lists fonts, profile and notices; a width gate over every shipped font (detector teeth: a compact-metrics fixture font is refused).
- `S3` Renderer and tagging adapter: report to tagged PDF/A-3a and PDF/UA-1 with attachments and XMP. Tests: every text object tagged or an artifact, parent tree complete, TH scope, `Lang`, `DisplayDocTitle`, `AF` entries with MIME and relationship, every product XMP property declared, no information dictionary; all values and state labels extractable in es, en, ca and hu; byte determinism; detector teeth for a plan/draw mismatch and an untagged text object. Acceptance: the veraPDF recipe passes `3a`, `3u` and `ua1` on four-language fixtures and refuses three negative controls.
- `S4` Certification: statement model, domain-separated signing through the keypair capability, visible-layer digest. Tests: canonical statement round trip; a report signature fails as a review-package signature and the reverse; a tamper matrix (CSV, JSON with XMP updated, XMP identifier, swapped page amounts, annotation overlay, flipped signature, another key) each yields exactly its reason; a linearised re-save still verifies; the OpenSSL recipe succeeds and refuses a flipped signature.
- `S5` Verification service and store trace against a synthetic profile store. Tests: pristine file verified; each store-layer reason produced by a real store mutation, including an unavailable authority generation reported as unprovable; a forgery under another profile's key refused with both key and rebuild reasons.
- `S6` Destination enrolment and surfaces: PDF destination in the typed contract through the no-clobber sink, the `--document-format pdf` path, `report-verify`, the TUI destination and verify action, catalogue keys in four languages, regenerated CLI reference. Tests: live parser success and refusal, no-clobber, envelope shape and exit status, TUI availability and check-row rendering, locale coverage.
- `S7` User documentation: reading the summary, what the signature means and does not mean, verifying with and without Cadrumo; docs build.

On acceptance, the calculation-report decision's PDF sentence reads: the PDF destination renders the same report as a PDF/A-3a, PDF/UA-1 document embedding the report and CSV with a signed integrity statement, as decided in this record.

## Rationale

The operator's five requirements pull in different directions, and only the associated-file container satisfies readability, machine recovery and embedding at once, with Factur-X as working precedent and veraPDF as an independent oracle (`2026-09-26-export-parity-calculation-summary-pdf-research`). Making the canonical JSON authoritative keeps the single-builder rule intact: the PDF adds no content, and every other carrier is either derived from that JSON (CSV, page) or a checked mirror of the signed statement (XMP). The detached statement signature wins on the knockout criterion of traceability: it binds identifiers the store can re-derive, survives benign re-saves, reuses a key already in encrypted custody through an unchanged primitive, and can be checked with stock OpenSSL. PAdES would add a dependency tree and a PDF 2.0 base to buy a viewer badge that would read as untrusted. The visible-layer digest closes the gap a detached signature would otherwise leave on the page itself, and the spike shows ReportLab plus a pikepdf pass reaches tagged archival conformance without a native stack.

## Consequences

- An accountant receives one file that prints, reads aloud, opens its data in a spreadsheet and can be checked against the operator's key; the operator's own installation can prove the file still matches the encrypted store, or say exactly why it does not.
- No viewer shows a green signature badge. Verification means Cadrumo, or OpenSSL and the documented recipe; honest, but less familiar than PAdES. A later amendment can add PAdES on PDF/A-4f without changing the carriers.
- The document layer alone cannot catch a consistent forgery under another key, so recipients must pin the fingerprint; the surfaces say so rather than implying more.
- A new per-profile secret for keyed provenance digests enters encrypted custody; losing the profile loses the ability to recompute them, as it already loses the signing key.
- ReportLab becomes a runtime path in the `pdf` extra with its notice; tagging rests on two pinned library behaviours and needs its tests to move with every ReportLab or pikepdf upgrade.
- Brand fonts need static TrueType instances and a width gate; if JetBrains Mono fails the gate, amounts are set in Liberation Mono and the summary departs slightly from the documentation's code face.
- Filing-record and verification-report identifiers remain unkeyed hashes that include an actor label (and a member NIF for group filings), so a holder of the PDF can confirm a guessed label; this residual is accepted unless the operator chooses to keep those two identifiers out of the page and XMP.
- Matterhorn human-judgement checks become a recorded review per modelo family, since validators cannot prove them.
