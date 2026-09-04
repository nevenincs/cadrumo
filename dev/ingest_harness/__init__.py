"""The document-ingestion measurement harness: the instrument, not the measurement.

Builds the runner the measured lane uses to score the ingestion pipeline against
the external corpus. This package deliberately measures nothing on its own; the
measurement Steps supply the engines that drive real product entry points, and
this package supplies the shapes those results must take.

What it makes impossible, each because it already happened once:

* A figure quoted without the key it was scored against. The key is pinned by
  content hash, refused if it is not the pinned one, and printed before any
  number. The key's internal ``schema_version`` is permanently stale and is
  printed only as a labelled do-not-cite.
* A figure quoted without the model tier that produced it. The tier is required
  and closed, and it states whether the row may set an acceptance floor at all.
* An accuracy over documents with no authored truth. A scored outcome and an
  emitted-only outcome are different types, and the latter has no rate to quote.
* A Spanish figure stripped of its optimism-bias caveat. The caveat is derived
  from the document's own language and stamped automatically.
* A denominator inherited from prose. Every count is re-derived from the key.

**Reachability finding, recorded rather than worked around.** The deterministic
stage-1 producers (``transcribe_text_layer``, ``text_layer_transcriber_identity``,
``extract_evidence_pages``) and the evidence resolver
(``resolve_attachment_evidence_input``) are NOT on the ledger package's public
facade; only the data types are. A harness driving the real deterministic S1
entry point therefore cannot reach it without importing a private module, which
the architecture forbids. This package does not clone those surfaces and does not
reach into the private module: the runner takes measured rows from an injected
engine instead. Promoting those four symbols is a precondition of the measurement
Steps, not of this one.

Every symbol this package defines is imported from the module that defines it;
this initialiser is an inert namespace marker and forwards nothing.
"""
