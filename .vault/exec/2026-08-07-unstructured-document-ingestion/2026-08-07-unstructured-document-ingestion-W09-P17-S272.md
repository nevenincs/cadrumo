---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:23fcf34b84112d00689b6c38a7264452c5d10fd87b108fe5a9c0645da88113c3'
step_id: 'S272'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Stop a blank CSV country column becoming Spain on invoice bulk import, since _bulk_import defaults country_code to ES and _source_resolver routes IVA on counterparty_country not equal to ES, so an EU supplier whose export left the column empty is silently reclassified as domestic and its intra-community treatment is never applied - this is the recordable-but-blank class rather than the unrecorded one so the honest treatment is to refuse the row and name the column, and the change carries operator-facing blast radius on existing CSVs which is why it is rowed separately rather than swept

## Scope

- `src/cadrumo/adapters/inbound/invoices/_bulk_import.py`

## Description

- Make `country_code` required on `BulkInvoiceImportRow` and stop the row parser
  substituting `"ES"` for an absent counterparty country in
  `src/cadrumo/application/invoices/_bulk_import.py`.
- Add `_assert_country_is_answerable`, refusing once and up front a book that carries
  no country column and for which no country was declared, rather than emitting one
  identical refusal per row.
- Accept `declared_country` on `import_invoices_from_rows` and the row parser, applied
  only where the row states nothing, and expose it as `--country` on
  `aeat app ledger invoice import`.
- Add the refusal message and the option help to all four locale catalogues.
- Cover the three cases plus their controls, and state a country explicitly in the
  fixtures that previously had Spain inferred for them.

## Outcome

The counterparty country decides whether an invoice is treated as domestic or as an
intra-community operation, and the invoice source resolver routes on exactly that
comparison. Inferring Spain for a row that stated nothing silently reclassified a
foreign supplier as domestic and dropped the treatment that classification carries.

The remedy splits by what the source can express, because the two absences are
different defects. A book that HAS the column and left one cell empty is a per-row
omission: that row is refused, naming the column, and every row that did state a
country still imports under the existing partial-success semantics. A book that has
no column at all cannot answer the question for any row, so it is refused once,
before any row is read, with the recourse named -- add the column, or declare one
country for the import.

The declared country is deliberately a fallback and never an override. If it won over
a stated cell, declaring one country to get a legacy book moving would rewrite every
foreign counterparty in a book that already had them right, which is the same
reclassification the default caused, reintroduced through the recourse.

## The trade, stated rather than defaulted to strict

Refusing costs the operator one flag. Inferring costs a misclassified filing. But the
refusal is not free and the cost is larger than it first looked: the bundled libro
registro fixtures -- the real Spanish accounting book format, both facturas expedidas
and facturas recibidas -- carry no country column in either dialect. So the commonest
real import an operator has does not answer the question, and every existing fixture
in both test suites omitted the column too.

That is why the whole-import declaration exists rather than a bare refusal. What it
does NOT do is recover the foreign counterparties in such a book: declaring `ES` for
a libro registro asserts Spain for every row, which is the same inference, now made
explicitly by the operator instead of silently by the importer. That is an
improvement in honesty and not in accuracy, and a book that genuinely mixes domestic
and EU counterparties still needs the column. The option help says the value applies
to the whole import for that reason.

## Verification

    uv run --no-sync pytest src/cadrumo/application/invoices src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_bulk_import.py -m integration -q -p no:randomly
    78 passed in 37.04s

Each changed component was then restored independently at runtime, from a script
outside the repository, each scenario in its own process. The reported value is the
country actually PERSISTED, read back through the real encrypted repository rather
than taken from the parser's return:

    all-fixed        no_column=REFUSED_FILE   blank_cell=REFUSED_ROWS(country_code)
    model-default    no_column=REFUSED_FILE   blank_cell=REFUSED_ROWS(country_code)
    parser-fallback  no_column=REFUSED_FILE   blank_cell=ES
    file-guard       no_column=REFUSED_ROWS   blank_cell=REFUSED_ROWS(country_code)
    all-restored     no_column=ES             blank_cell=ES

`all-restored` reproduces the original defect on both cases, so the window is
demonstrably open before anything is claimed about the gates.

Three findings, two of which are against the change's own framing:

The **parser fallback was the load-bearing half**. Restoring it alone returns a blank
cell to Spain while everything else stays fixed.

The **model requirement is a pure backstop and is not load-bearing**. Restoring it
alone changes nothing observable, because the parser now refuses first. It is worth
keeping as a boundary invariant, but this change would have worked without it and the
record should not imply otherwise.

The **up-front file guard is about message quality, not safety**. Without it the
no-column book still refuses -- it simply degrades to one identical per-row refusal
instead of one statement of the single fact the operator needs. It should not be
described as preventing the defect.

## Notes

**An instrument fault caught mid-measurement, and worth recording.** The first run of
the matrix reported that the parser fallback changed nothing, which would have been
the wrong conclusion. The blank-cell fixture used a German VAT number, so the
NIF-to-country consistency check refused the row before the country guard was ever
reached and every scenario looked identical. Re-running with a Spanish CIF -- a value
the identity check accepts alongside `ES` -- made the row discriminate. A masking
downstream check is indistinguishable from a fix that works.

**A silent no-op sweep, caught by an assertion rather than by review.** A scripted
edit intended for the pre-existing fixtures matched zero sites because the file uses
CRLF and the pattern anchored on a newline. It printed its success line and wrote
nothing. Only an explicit count assertion surfaced it; the same script had earlier
swept two of the new tests into declaring a country, which would have destroyed
exactly the two cases they exist to prove.

**No commit of its own.** As with the sibling country Step, every source and locale
edit was taken into HEAD by a peer's bare sweeping commit, `feat(cadrumo): land the
in-flight source work`, before it could be committed with a pathspec. Verified
present in HEAD by reading the code and by confirming both locale keys in all four
catalogues.

**Left alone deliberately.** The invoice source resolver's own domestic comparison is
correct given a populated country and was not touched; the defect was upstream of it.
