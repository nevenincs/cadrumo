---
tags:
  - '#research'
  - '#export-parity'
date: '2026-09-26'
modified: '2026-09-26'
body_schema: 'body-v2'
body_hash: 'sha256:2d7c0751c1917b40c72aa43b111a6c1437b470aa39e060f658de24658e862a54'
related: []
---

# `export-parity` research: `calculation summary pdf`

The operator asked for a calculation-summary PDF that people can read, machines can read without OCR, carries its own structured data, is certified, and carries hash identifiers that trace it back to the encrypted store. This record collects the standards, library, validator and repository evidence the design depends on, and the results of a synthetic feasibility spike. The evidence favours a PDF/A-3 container with tagged PDF/UA-1 pages, the canonical report JSON as the authoritative associated file, a declared XMP extension schema that mirrors a signed statement, and a detached Ed25519 statement signature made with the existing profile key; PAdES is technically reachable only on a PDF 2.0 base and is not needed for any requirement the operator stated. The decision itself belongs to the ADR.

## Findings

### PDF/A-3 associated files are the container for a human page plus authoritative data

- PDF/A-3 (ISO 19005-3:2012) differs from PDF/A-2 by permitting embedded files of any format; every embedded file must be an associated file with a MIME subtype, an `AFRelationship` of `Source`, `Data`, `Alternative`, `Supplement` or `Unspecified`, and an `AF` association from the document or one of its parts (LoC format description, https://www.loc.gov/preservation/digital/formats/fdd/fdd000360.shtml).
- Conformance levels: `b` preserves appearance, `u` adds Unicode mappings for all text, `a` adds logical structure and reading order (same source). Level `a` is the only level that coincides with tagged, accessible output.
- PDF 2.0 (ISO 32000-2 Table 43) defines `Data` as information used to derive a visual presentation such as a table, `Supplement` as a more consumable representation of the source or data, and `Unspecified` for relationships the other values cannot describe (paraphrased from the transcription at https://github.com/pdf-raku/PDF-ISO_32000_2-raku/blob/main/lib/ISO_32000_2/Table_43-Entries_in_a_file_specification_dictionary.rakumod). The canonical report JSON fits `Data`; the CSV fits `Supplement`; a signature statement fits none and takes `Unspecified`.
- veraPDF enforces this: removing `AFRelationship` from one attachment of a compliant spike file fails rule 6.8-3 (spike negative control, below).

### Factur-X/ZUGFeRD is direct prior art for human-plus-machine PDFs

- Factur-X embeds its XML invoice in a PDF/A-3 file, names it with a fixed filename, and declares its presence in XMP through its own namespace with document type, filename, version and conformance-level properties, all described in a PDF/A extension schema (https://github.com/akretion/factur-x/blob/master/facturx/xmp/Factur-X_extension_schema.xmp; LoC notes Factur-X/ZUGFeRD as a principal PDF/A-3 adopter at the fdd000360 URL above).
- The transferable pattern is: fixed attachment names, a product namespace that points at them, and validation with veraPDF. Factur-X does not sign its XML; authenticity is out of its scope, so it offers no precedent for certification.

### Custom XMP properties are legal in PDF/A only when declared

- PDF/A accepts XMP properties outside the predefined schemas only when an extension schema description (`pdfaExtension:schemas` with schema, namespace URI, prefix and typed property list) is present. The spike's negative control that deletes the extension-schema block fails rules 6.6.2.3.1-1 and 6.6.2.3.1-2 once per undeclared property.
- Combining PDF/A-3 with PDF/UA-1 needs the `pdfuaid` namespace declared the same way; the spike declares it and passes both profiles.
- pikepdf re-serialises the XMP packet on save (attribute order changes), so any verifier must parse XMP with a namespace-aware parser rather than compare packet bytes (observed on `pikepdf@10.13.0`).

### PDF/UA-1 tagging is reachable with open-source ReportLab plus a pikepdf pass

- PDF/UA-1 (ISO 14289-1) requires all real content tagged with standard structure types in logical order, artifacts marked, fonts embedded and languages declared (https://www.loc.gov/preservation/digital/formats/fdd/fdd000350.shtml). The Matterhorn Protocol splits its 136 failure conditions into 87 machine-checkable and 47 needing human judgement (https://pdfa.org/wp-content/uploads/2021/04/Matterhorn-Protocol-1-1.pdf), so a validator pass proves only the machine-checkable part.
- Open-source ReportLab does not tag; tagging is a feature of the commercial ReportLab PLUS (https://docs.reportlab.com/pdf-accessibility/).
- The spike closes that gap without a new dependency: the renderer records, for every text draw, either a structure path (Document, H1, H2, P, Div, Table, TR, TH with Scope, TD) or an artifact marker; a pikepdf pass wraps each text object in `BDC`/`EMC` with an MCID, wraps every path in an `/Artifact` sequence, builds the structure tree and parent tree, and sets `MarkInfo`, `Lang` and `DisplayDocTitle`. veraPDF `ua1` and `3a` pass on es and hu output; untagging one heading fails rule 7.1-3.
- The pairing depends on ReportLab emitting exactly one text object per draw call and on ignoring the empty text objects its `setFont` emits; this is an implementation contract of `reportlab@5.0.1` that a production renderer must pin with a test.

### Library capability and licence landscape

| Library | Licence | Relevant capability | Runtime fit |
| --- | --- | --- | --- |
| `reportlab@5.0.1` | BSD | layout, TrueType subsetting with ToUnicode; no tagging, no PDF/A mode | dev-only today (`pyproject.toml:525`); depends on Pillow and charset-normalizer, both already in the runtime closure |
| `pikepdf@10.13.0` (qpdf 12.3.2) | MPL-2.0 | attachments with `relationship`, content-stream parse/unparse, raw XMP stream, deterministic `/ID` | already runtime (`pyproject.toml:80`), disclosed in `THIRD_PARTY_NOTICES.md:38` |
| `pypdfium2@5.13.0` | BSD-3/Apache-2.0 | text extraction and rendering | already runtime (`pyproject.toml:78`) |
| `cryptography@50.0.1` | Apache-2.0 or BSD-3 | Ed25519 | already runtime (`pyproject.toml:60`) |
| `pyHanko@0.37.0` | MIT | PAdES B-B to B-LTA, DocMDP, Ed25519/Ed448 per RFC 8419, validation | absent; pulls asn1crypto, tzlocal, aiohttp, pyhanko-certvalidator (with oscrypto, uritools) |
| `weasyprint@70.0` | BSD | HTML to PDF with `pdf/a-3a`, `pdf/ua-1`, attachments, custom XMP | absent; needs Pango and Fontconfig system libraries |
| `fpdf2@2.8.8` | LGPL-3.0 | layout | copyleft |
| `pymupdf@1.28.2` | AGPL-3.0 or commercial | full toolkit | strong copyleft |
| `pypdf@6.19.0` | BSD-3 | attachments, metadata; no layout | redundant with pikepdf |

Licences and dependency lists are from PyPI JSON metadata fetched 2026-09-26 (https://pypi.org/pypi/pyHanko/json and siblings). The accepted licence posture keeps the core closure free of strong copyleft and gates copyleft behind extras (`2026-07-12-license-posture-adr`); fpdf2 and PyMuPDF would contradict it, and WeasyPrint's native stack is a poor fit for a Windows-first command line. WeasyPrint's feature list is from https://doc.courtbouillon.org/weasyprint/stable/api_reference.html; pyHanko's from https://github.com/MatthiasValvekens/pyHanko.

### Fonts: embedding works, one subsetting defect, brand fonts need static TrueType

- ReportLab embeds TrueType subsets with a ToUnicode map, and Hungarian `ő`/`ű` extract as Unicode through pypdfium2 in the spike.
- `reportlab@5.0.1` writes glyph widths that veraPDF rejects (6.2.11.5-1, 87 glyph checks) when subsetting DejaVu Sans Mono, whose `hhea.numberOfHMetrics` is 4 against 3377 glyphs; Liberation Mono (2423 of 2423) and DejaVu Sans (6238 of 6253) subset cleanly. Monospaced fonts commonly use the compact metrics form, so each shipped font needs a width-consistency gate.
- The brand faces are Hanken Grotesk (text), Newsreader (display) and JetBrains Mono (code), self-hosted under SIL OFL 1.1 as WOFF2 subsets (`docs/_static/cadrumo-docs.css:14`). ReportLab reads neither WOFF2 nor variable-font instances, and the runtime has no fontTools or Brotli, so the PDF needs static TTF instances shipped as package data with their OFL notices. The workbook design uses Roboto Mono (`2026-06-03-modelo-export-visual-design-adr`); JetBrains Mono's metrics layout was not checked.
- The TUI light palette (`src/cadrumo/entrypoints/tui/components/theme.py:29`) and the docs' AA-corrected semantic inks (`docs/_static/cadrumo-docs.css:131`) give print colours that clear 4.5:1 on white and on the panel tint (spike contrast checks: 4.98:1 to 7.11:1).

### Deterministic bytes are achievable, with one trap

- With `rl_config.invariant`, a fixed-seed key, fixed attachment dates and pikepdf `deterministic_id`, two builds in one process and a build in a second process are byte-identical.
- A freshly generated LittleCMS sRGB profile embeds its creation second in the ICC header and broke cross-process determinism until the profile was frozen; production needs one fixed ICC profile shipped as data. The Pillow-generated profile is ICC v4.4 device class `mntr` and veraPDF accepted it as a PDF/A-3 output intent.

### Detached Ed25519 statement signature versus PAdES/CMS

- PAdES (ETSI EN 319 142-1) defines baseline levels B-B, B-T, B-LT and B-LTA over a CMS signature covering the file's byte range (https://www.etsi.org/deliver/etsi_en/319100_319199/31914201/01.02.01_60/en_31914201v010201p.pdf). A certification signature with DocMDP seals the file against later change and is what viewers display.
- EdDSA (Ed25519, Ed448) became usable in PDF signatures only through ISO/TS 32002:2022, an extension of PDF 2.0 (https://www.iso.org/standard/45875.html; https://mvalvekens.be/blog/2022/iso-dsig-extensions-published.html). A PAdES Ed25519 signature therefore needs a PDF 2.0 file, which means PDF/A-4f rather than PDF/A-3; the spike's PDF/A-4f variant passes veraPDF `4f`, so the base is available if ever wanted.
- No evidence was found that Adobe Acrobat validates EdDSA signatures; searches returned nothing either way, so viewer support is unverified. CMS also needs an X.509 certificate; a self-signed certificate over the profile key would show as untrusted in every viewer and add no trust beyond the raw key fingerprint.
- A detached statement signature needs no new dependency: the product's primitive signs the raw 32 bytes of a hex digest (`src/cadrumo/core/ed25519_signing.py:85`) with no domain separation, which the review-package signer applies to a manifest digest (`src/cadrumo/application/modelo/review_package_signing.py:181`). Prefixing a fixed context string inside the digest preimage separates a report signature from a review-package signature under the same key without changing the primitive.
- What each approach does not cover: a detached statement leaves the page layer unsigned unless the statement carries a digest of it; PAdES seals bytes but breaks under any benign re-save and carries no semantic trace to the store.

### Verification without Cadrumo is possible with stock tools

- The spike verifies the statement signature using only OpenSSL 3.0.13: SHA-256 over the context prefix plus the statement attachment, then `openssl pkeyutl -verify -rawin` with a DER public key formed from the fixed Ed25519 SubjectPublicKeyInfo prefix (RFC 8410) and the raw key. A flipped signature byte is rejected. Attachments were extracted with pikepdf, standing in for `qpdf --show-attachment` or poppler `pdfdetach`.
- A recipient without Cadrumo can also hash the JSON and CSV attachments and compare them with the statement. Checking the page layer against the statement needs the documented digest recipe, which is not a stock tool.

### What a document-only check can and cannot prove

- The spike's document verifier detects: an edited CSV attachment, an edited JSON attachment even when the XMP digest is updated to match, an edited XMP identifier, two visible amounts swapped in the content stream (visible-layer digest over decoded page content, boxes and font programs), a FreeText annotation laid over a value (the pages must carry no annotations or non-font resources), and a flipped signature. A re-save with object streams and linearisation, which changes every byte, still verifies.
- A consistent forgery (someone with their own key rebuilding a changed report) is self-consistent at the document layer; only a pinned trusted key or the store trace refuses it (`signing_key_untrusted`; `signing_key_not_this_profile` plus `report_rebuild_mismatch` in the simulated trace).
- pypdfium2 extracts a no-break space as a plain space, so a semantic text check must normalise whitespace on both sides.

### Repository facts the design must respect

- The profile signing key is minted once per bucket, persisted only as ciphertext through a capability, and only its public half leaves the process (`src/cadrumo/application/modelo/review_package_signing.py:19`, `src/cadrumo/application/modelo/review_package_signing_ports.py:18`); its namespace is `SECRET`, profile-local (`src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py:943`). Signature verification takes the trusted public key explicitly rather than reading it off the envelope (`src/cadrumo/application/modelo/review_package_signing.py:251`).
- The canonical record encoding (sorted keys, compact, UTF-8 unescaped, no NaN) and strict decoders already exist (`src/cadrumo/core/hashing.py:80`, `src/cadrumo/core/hashing.py:180`); the spike imports them unchanged.
- Local publication is no-clobber and returns the published file's SHA-256 (`src/cadrumo/application/modelo/export_sink.py:53`, `src/cadrumo/application/modelo/export_sink.py:129`).
- The software-identity grade is derived from the values, so the mock cannot be relabelled (`src/cadrumo/domain/filing/software_identity.py:61`, `src/cadrumo/domain/filing/software_identity.py:130`).
- Optional extras are one registry with a spec-only probe whose import name must be exclusive to the extra (`src/cadrumo/core/optional_extras.py:77`, `src/cadrumo/core/optional_extras.py:91`). No runtime distribution requires ReportLab today, so a `reportlab` probe would be exclusive in an installed product.
- Traceability inputs: the revision's registry coordinate (`src/cadrumo/domain/calculations/registry/schema_references.py:159`), the authority logical generation as a 64-hex digest (`src/cadrumo/domain/calculations/registry/authority_artifact.py:106`), the per-revision `source_provenance` rows (`src/cadrumo/domain/modelos/calculation_revision.py:880`), and evidence records keyed by content digest (`src/cadrumo/application/evidence/models.py:121`).
- Privacy hazards in plaintext identifiers: a withholding source reference embeds the perceptor NIF (`src/cadrumo/application/aggregation/modelo_bindings_retenciones.py:213`); the filing-record id is an unkeyed hash over work unit, revision, actor label and, for group filings, a member NIF (`src/cadrumo/domain/modelos/filing_record.py:430`); the verification-report id includes the actor label (`src/cadrumo/domain/modelos/verification_report.py:262`); the filing record can hold AEAT's CSV code, which opens the official receipt at AEAT's verification service (`src/cadrumo/domain/modelos/filing_record.py:417`). The CLI masks tax identities as the first 8 hex of an unsalted SHA-256 (`src/cadrumo/core/redaction/rules.py:387`), which hides a NIF from a casual reader but not from enumeration of the roughly 10^8 DNI space, and the reveal opt-in never reveals tax identities (`src/cadrumo/core/output_rendering.py:122`).
- Precedent for plaintext handoffs: the review package already ships the fichero-BOE draft and an evidence descriptor in a plaintext archive the operator asked for (`src/cadrumo/application/modelo/review_package.py:78`).
- The export command already tells the operator that official proof is the AEAT receipt, the filed-declarations lookup or the CSV check (`aeat app modelo export --help`, live output 2026-09-26).

### Validator availability

- veraPDF 1.28.2 (GPL-3.0 or MPL-2.0) runs here on OpenJDK 21 from the `org.verapdf.apps:greenfield-apps` jar on Maven Central, downloaded with its published SHA-256 into the spike's scratch `tools/` folder; no system package was installed. It offers PDF/A 1a to 4e, PDF/UA-1, PDF/UA-2 and WTPDF profiles. It is a development and CI oracle, never a shipped dependency.

### Spike

Synthetic only, outside the repository (session scratchpad `pdf-spike/`), run with `uv run --no-sync python <scratchpad>/pdf-spike/spike.py` from the repository root; 51 of 51 checks pass, exit 0, about 25 seconds. Proven: veraPDF `3a`, `3u` and `ua1` compliance for es and hu, `4f` for the PDF 2.0 variant, three validator negative controls refused; JSON and CSV attachments byte-identical to builder output and matching the XMP digests; every font embedded; Hungarian text extractable; byte determinism in and across processes; six tamper cases detected with typed reasons; a benign re-save accepted; a consistent forgery refused only with a pinned key or the store trace; OpenSSL-only signature verification; AA contrast for every text colour. Not proven: Matterhorn human-judgement conditions (reading order sense, table header association beyond Scope, language of parts); rendering in Acrobat, macOS Preview or browser viewers; the brand fonts; the real report builder, store and key capability (all simulated); viewer behaviour for the attachments pane.

### Not investigated

PDF/UA-2 and WTPDF profiles; long-term timestamping (RFC 3161) of the statement; accessibility of the attached CSV itself; Windows font discovery; performance for the largest modelo (Modelo 100 carries roughly 9k value cells per the workbook design record).

## Sources

- https://www.loc.gov/preservation/digital/formats/fdd/fdd000360.shtml
- https://www.loc.gov/preservation/digital/formats/fdd/fdd000350.shtml
- https://github.com/pdf-raku/PDF-ISO_32000_2-raku/blob/main/lib/ISO_32000_2/Table_43-Entries_in_a_file_specification_dictionary.rakumod
- https://github.com/akretion/factur-x/blob/master/facturx/xmp/Factur-X_extension_schema.xmp
- https://pdfa.org/wp-content/uploads/2021/04/Matterhorn-Protocol-1-1.pdf
- https://docs.reportlab.com/pdf-accessibility/
- https://doc.courtbouillon.org/weasyprint/stable/api_reference.html
- https://github.com/MatthiasValvekens/pyHanko
- https://www.etsi.org/deliver/etsi_en/319100_319199/31914201/01.02.01_60/en_31914201v010201p.pdf
- https://www.iso.org/standard/45875.html (ISO/TS 32002:2022)
- https://mvalvekens.be/blog/2022/iso-dsig-extensions-published.html
- https://pypi.org/pypi/pyHanko/json, https://pypi.org/pypi/weasyprint/json, https://pypi.org/pypi/fpdf2/json, https://pypi.org/pypi/pymupdf/json, https://pypi.org/pypi/pypdf/json, https://pypi.org/pypi/reportlab/json, https://pypi.org/pypi/pikepdf/json
- https://repo1.maven.org/maven2/org/verapdf/apps/greenfield-apps/1.28.2/
- RFC 8032 (EdDSA), RFC 8410 (Ed25519 keys in X.509), RFC 8419 (EdDSA in CMS)
- `src/cadrumo/application/modelo/review_package_signing.py:19`, `src/cadrumo/application/modelo/review_package_signing.py:181`, `src/cadrumo/application/modelo/review_package_signing.py:251`, `src/cadrumo/application/modelo/review_package_signing_ports.py:18`
- `src/cadrumo/core/ed25519_signing.py:85`, `src/cadrumo/core/hashing.py:80`, `src/cadrumo/core/hashing.py:180`
- `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py:943`
- `src/cadrumo/application/modelo/export_sink.py:53`, `src/cadrumo/application/modelo/export_sink.py:129`
- `src/cadrumo/domain/filing/software_identity.py:61`, `src/cadrumo/domain/filing/software_identity.py:130`
- `src/cadrumo/core/optional_extras.py:77`, `src/cadrumo/core/optional_extras.py:91`
- `src/cadrumo/domain/calculations/registry/schema_references.py:159`, `src/cadrumo/domain/calculations/registry/authority_artifact.py:106`
- `src/cadrumo/domain/modelos/calculation_revision.py:880`, `src/cadrumo/application/evidence/models.py:121`
- `src/cadrumo/application/aggregation/modelo_bindings_retenciones.py:213`, `src/cadrumo/domain/modelos/filing_record.py:417`, `src/cadrumo/domain/modelos/filing_record.py:430`, `src/cadrumo/domain/modelos/verification_report.py:262`
- `src/cadrumo/core/redaction/rules.py:387`, `src/cadrumo/core/output_rendering.py:122`
- `src/cadrumo/application/modelo/review_package.py:78`
- `src/cadrumo/entrypoints/tui/components/theme.py:29`, `docs/_static/cadrumo-docs.css:14`, `docs/_static/cadrumo-docs.css:131`
- `pyproject.toml:60`, `pyproject.toml:78`, `pyproject.toml:80`, `pyproject.toml:525`, `THIRD_PARTY_NOTICES.md:38`
