# GROI response samples

Verbatim text fragments captured from live AEAT GROI servlet responses.

These samples are the **authority** for the GROI verdict parser at
`src/cadrumo/adapters/outbound/aeat/sede/groi_check.py`, which classifies a
scraped AEAT page as `valid` / `invalid` / `unknown` by matching Spanish
certification phrases. That parser gates live modelo 349 counterparty ROI
checks, so a phrasing regression here turns "not registered" into "registered"
— a false pass on an intracomunitario declaration.

Each filename encodes the expected verdict, so the parametrised gate
(`test_groi_response_samples_parse_to_expected_verdict` in
`src/cadrumo/adapters/outbound/aeat/sede/tests/test_groi_check.py`) reads the
file, runs the parser, and asserts the result matches the prefix. If AEAT
changes the response phrasing, that suite breaks immediately — that is the
whole point.

Do not edit the `.txt` bodies. They are byte-exact evidence, not fixtures to
tune; `.gitattributes` marks this tree `-text` to keep them so. If the parser
disagrees with a sample, the parser is wrong.

**Source, capture dates, per-file hashes, the filename contract, the
chrome-stripping rule, and the known coverage gaps live in
[`PROVENANCE.md`](PROVENANCE.md).** Read it before adding or refreshing a
sample.
