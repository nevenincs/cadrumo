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

- no raw N26 statement PDF was available in the local operator environment
- the user still required the feature to be grounded in a real, existing N26
  statement template
- the upstream corpus provides sanitized text extracted from real N26 PDFs plus
  manually asserted expected transactions

How these fixtures are built:

- `src/aeat/tests/fixtures/financial/n26/_generate.py` renders committed PDFs with
  `reportlab`
- the PDFs preserve the real template family at the line-structure level:
  statement header, transaction block, summary block, fees/interest block, and
  notes page
- personal names, IBANs, and addresses remain synthetic / sanitized

How the goldens are maintained:

- each `*.expected.json` file is hand-written from the fixture content
- the parser tests compare PDF-derived `RawTransaction` rows against those
  hand-maintained expectations
- expected payloads are not generated from parser output

Regeneration:

```powershell
uv run python src/aeat/tests/fixtures/financial/n26/_generate.py
```
