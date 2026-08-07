---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:14540df4431de1c5a135a5c230e39b26b48046d1690b4436957301e16a2cc8a2'
step_id: 'S28'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Consume the mapping lane from the invoice-book importer including a retencion role, gated by the libro registro fixture importing fully with unknown columns reported rather than refused

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Add `_bulk_import_columns.py`: exact-name resolution first, the mapping lane
  for what is left, and a per-column report of everything that resolved to no
  importer field.
- Replace the two refuse-whole header checks in the bulk-import reader with that
  resolution, and read a mapped book under its own detected dialect.
- Carry a retención column end to end, under the Spanish stem `retencion_amount`.
- Bind the mapper at the command boundary and surface unmapped columns, and the
  reasons a proposed role was not applied, on the typed notice channel.
- Correct two tests that had encoded the refuse-whole defect as the contract.

## Outcome

A real libro registro is read under its own Spanish column names. Every required
importer field is supplied by a column whose name matches nothing the product
knew, and **no refusal names a column** — the file is no longer rejected entire
for vocabulary it does not recognise.

Resolution is deterministic first. A header that already names a canonical
importer column binds to it outright, and the mapping lane is consulted **only
when exact matching cannot supply a required field**. That ordering is the same
control the statement lane uses, and it also keeps a model out of the path of
every ordinary import: a canonical file carrying one extra column is read with
no judgement at all, and the extra column simply reports.

Retención now has somewhere to land. The domain record and the catalogue writer
already carried a retención amount; the importer had no column for it, so a
book's withheld IRPF vanished even once its column names were understood.

Two refusals deliberately survive. A file that supplies no column for a required
field still refuses, because there is no row to create — that is not the
refuse-whole this Step removed, and it is pinned by its own test so removing the
one did not quietly remove the other. And a book written in the product's own
column names keeps the strict euro grammar, so a bare `1.234` there still
refuses rather than being read as one euro twenty-three; only a book the mapping
lane had to interpret is read under its detected separator, where the whole
file's evidence settles what a comma means.

### The column is `retencion_amount`

Landed first under the English `retention_amount`, which reddened the
importer-coverage gate: the role vocabulary carries the Spanish stem, and the
member values are byte-identical to importer column tokens by design so a role
resolves against a column with no second translation table. Renamed to
`retencion_amount` per the naming rule, which names this exact word. The writer
parameter it feeds keeps its existing name; only the importer's own column token
was this Step's to choose.

### The layering edge

The reader consumes the dialect normalizer, which is an inbound adapter, so the
contract broke on application reaching adapters. Pinned per origin rather than
redesigned, matching the two existing pins whose stated rationale is exactly this
case: reading an externally-authored format is inbound-adapter work and the
application module consumes the answer. Recorded alongside the pin, rather than
claimed as ideal: this module already reads workbooks through `openpyxl`
directly, so its file-reading half is arguably misplaced and the whole module is
a relocation candidate — a larger move than this Step.

## Verification

    uv run --no-sync pytest src/cadrumo/application/invoices/ src/cadrumo/application/tests/test_field_role_importer_coverage.py src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_bulk_import.py src/cadrumo/adapters/inbound/financial/ -p no:randomly -n0 -m "integration or unit"
    359 passed in 42.50s

The layering contract, after the pin:

    uv run --no-sync lint-imports --config .importlinter
    Contracts: 6 kept, 0 broken.

The locale drift gate, after both new keys:

    uv run --no-sync python -m cadrumo.locales scaffold --check
    ca.yml: ok / en.yml: ok / es.yml: ok / hu.yml: ok

Five mutations, each applied from a throwaway plugin outside the repository so
no tracked file changed. Restoring the refuse-whole on unknown columns reddened
**five** tests including the libro gate; dropping the retención before the writer
reddened **one**; letting the mapping displace an exact column name reddened
**two**; consulting the mapping lane when exact names already suffice reddened
**one**; and reverting the column token to the English spelling reddened
**two** — precisely the two the importer-coverage gate reported. All restored
and re-run green.

## Notes

### The libro imports four of its eight rows, and why that is the honest number

Every row is read, and not one refusal concerns a column. Four rows are refused
by domain rules that sit upstream of column mapping and were not this Step's to
change: a rectificativa's negative total, **two EU VAT identifiers held to the
nine-character Spanish NIF shape**, and a factura simplificada to a consumidor
final carrying no NIF. The second of those is the population the governing
decision record itself names as unreadable, and it is a live under-coverage
defect rather than a quirk of the fixture. The four are pinned by row number and
reason so the gate states which failures it accepts and would break rather than
absorb a fifth silently.

### One thing wired but not covered by a test

The reasons a proposed column role was not applied — an allow-list refusal, a
duplicate claim, a claim about a column the table does not carry — are collected
at the command boundary and emitted as notices. Producing one requires a live
mapping call, which this environment must not make, so the notice path itself is
exercised only by the measured lane and not by a test here. The resolution
behaviour behind it *is* covered: a column left unmapped, and a column
understood but carrying a role the importer has no slot for, are distinguishable
and both reported.

### Incidents

An early cut consulted the mapping lane whenever any column was unresolved, so a
canonical file with one extra column issued a real model request. Caught from a
log line in a test run rather than by design. The required-field condition closed
it; the run now issues none, and a test asserts the mapper is never called for a
fully canonical header.

Passing the working directory as a test temporary path wrote a bucket store and
a master key into the repository root. They were untracked and, at that moment,
unignored. A peer added both paths to the ignore file shortly after, so they can
no longer be committed; the directories were left in place rather than removed.

The scope of this Step is recorded as the CLI, but the refuse-whole lived in the
application-layer reader. Implementing the mapping at the command boundary would
have forked the file reader into a second authority, so the resolution landed at
the reader and only the mapper binding and the notices landed in the CLI.
