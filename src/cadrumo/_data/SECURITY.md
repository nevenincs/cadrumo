# Security disposition for bundled data

`src/aeat/_data` contains bundled data, not application code. The tree has two
main classes:

- `corpus/`: mirrored or captured official-source artefacts used as legal,
  layout, parser, and replay evidence.
- `registry/`, `fx/`, and `audit/`: curated project data derived from official
  sources or from project verification runs.

The production Semgrep lane excludes this tree through `.semgrepignore` because
stock security rules treat mirrored HTML, XML, PDF text, URLs, and fixture
strings as executable-source findings. That exclusion is a scan-scope policy,
not a safety waiver.

## Required controls

- Do not commit credentials, authentication cookies, taxpayer identifiers, live
  taxpayer filings, browser session state, or other private user data.
- Treat mirrored files as untrusted input when application code reads them.
  They must be parsed through explicit readers or resource-boundary helpers,
  never imported or executed as code.
- Preserve provenance for official-source captures. A corpus directory that
  stores files from AEAT, BOE, or another external authority must carry source,
  capture-date, and document-inventory evidence in its local provenance record.
- Preserve integrity metadata when registry entries cite a corpus artefact:
  source references should declare the authority, evidence kind, corpus path,
  checksum, byte count, and applicable date range when those fields are
  available.
- Keep synthetic or replay fixtures marked as fixtures. Sanitised parser
  fixtures must stay paired with their sidecar provenance and must not be
  treated as proof of live taxpayer data support.

## Review rule

Changes under this tree are legally sensitive data changes. Reviewers should
ask what official source or project verification artefact justifies the change,
which provenance record tracks it, and whether the change belongs in bundled
data rather than production code.
