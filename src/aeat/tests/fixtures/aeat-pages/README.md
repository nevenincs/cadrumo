# AEAT status-reader fixtures

Hand-curated, PII-scrubbed snapshots of live AEAT *Sede Electrónica*
status pages. Used by unit tests colocated under
`src/aeat/status/_parsers/`.

## Trimming procedure (mirrors the ADR)

1. Capture `page.content()` from a live authenticated session (or
   the AEAT anónimo demo page if available).
2. Strip all `<script>`, `<style>`, `<link>`, `<meta>` and every
   `<div>` not ancestor to the target `<table>`.
3. Scrub PII: replace the tax id with `X1234567L`, employer tax ids
   with `A12345678`, amounts with round numbers, and any URL query
   tokens with stable placeholders.
4. Save under `src/aeat/tests/fixtures/aeat-pages/<surface>/<name>.html`.
5. Assert in the parser unit test that the fixture round-trips
   through the parser and through the pydantic model.
