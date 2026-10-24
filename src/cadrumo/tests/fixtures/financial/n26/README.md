# N26 PDF Fixtures

These fixtures are deterministic synthetic PDFs modeled on sanitized text dumps
from real N26 savings-account statements published in the
`portfolio-performance/portfolio` test corpus.

Reference source material:

- `Kontoauszug01.txt`
- `Kontoauszug06.txt`
- `Kontoauszug07.txt`
- `N26BankAGPDFExtractorTest.java`

Upstream location:

- <https://github.com/portfolio-performance/portfolio/tree/master/name.abuchen.portfolio.tests/src/name/abuchen/portfolio/datatransfer/pdf/n26bankag>

Why this exists:

- the product reads PDF bank statements of any bank through one bank-agnostic
  reader: a local model proposes the movements and deterministic anchoring and
  balance checks decide what is imported
- these statements are its test data, one real template family with a
  movement page, a summary page that prints balances and totals, and a notes
  page, which is exactly the shape that tempts a model into listing balances
  as movements
- no raw operator statement PDF is held; the upstream corpus provides
  sanitized text extracted from real statements plus manually asserted
  expected transactions

How these fixtures are built:

- `src/cadrumo/tests/fixtures/financial/n26/_generate.py` renders committed PDFs with
  `reportlab`
- the PDFs preserve the real template family at the line-structure level:
  statement header, transaction block, summary block, fees/interest block, and
  notes page
- personal names, IBANs, and addresses remain synthetic / sanitized

How the goldens are maintained:

- each `*.expected.json` file is hand-written from the fixture content
- the PDF statement provider tests compare the imported rows' dates, signed
  amounts and currency against those hand-maintained expectations
- expected payloads are not generated from provider or model output

Regeneration:

```powershell
uv run python src/cadrumo/tests/fixtures/financial/n26/_generate.py
```
