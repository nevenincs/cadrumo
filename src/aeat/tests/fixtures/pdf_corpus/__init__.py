"""PDF corpus fixture scaffolding.

Three layers:

- ``l1_public_anchors/`` — AEAT / BOE PDFs cited from public sources;
  hash-pinned via ``_manifest.json`` and fetched on demand to
  ``.cache/l1_anchors/``.
- ``l2_scrubbed_private/`` — deterministically PII-scrubbed derivatives
  of users' real filings; each file pairs with a sidecar JSON recording
  provenance + consent.
- ``synthetic/`` — reportlab-rendered parametrised test PDFs the
  extractor tests run against. Source-only; PDFs generated at test time.
"""
