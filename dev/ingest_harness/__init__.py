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
"""

from __future__ import annotations

from ._caveats import (
    SPANISH_OPTIMISM_BIAS_CAVEAT,
    TWIN_LINK_IS_PROSE,
    caveats_for_document,
    normalise_whitespace,
)
from ._colocation_ceiling import (
    AUTHORED_LABEL_PAIRS,
    CeilingOutcome,
    CeilingReport,
    CeilingRow,
    colocation_ceiling,
    documents_with_authored_transcription,
)
from ._colocation_geometry_size import (
    ColumnSegmentationSize,
    column_aware_rendering_partitions,
    geometry_payload_ratio,
    render_page_text,
)
from ._key import (
    CORPUS_ROOT,
    EXPECTED_KEY_BYTES,
    EXPECTED_KEY_SHA256,
    CorpusDocument,
    CorpusKey,
    CorpusKeyError,
    Denominators,
    ProvenanceClass,
    TwinPair,
    load_corpus_key,
)
from ._reference_points import (
    SONNET_4_6_REC_DOM_IMG_008,
    ReferencePoint,
    reference_points_with_key_context,
)
from ._result import (
    EmittedOnly,
    EngineRoute,
    HarnessRefusalError,
    ModelTier,
    PipelineStage,
    ResultRow,
    Scored,
    amounts_match,
    build_result_row,
)
from ._runner import (
    HarnessReport,
    emitted_or_scored,
    format_report,
    require_model_tier,
    sorted_rows_by_document,
    verify_decimal_comparison_path,
)
from ._scoring import (
    ABSTENTION_SENTINELS,
    FieldOutcome,
    FieldScoring,
    FieldVerdict,
    score_emission,
)
from ._tabular_truth import (
    TABULAR_COLUMN_ROLE_TRUTH,
    ColumnExpectation,
    TabularTruthError,
    column_role_truth_document,
    defensible_alternate_fields,
    emission_from_roles,
    slot_name,
)

__all__ = [
    "ABSTENTION_SENTINELS",
    "AUTHORED_LABEL_PAIRS",
    "CORPUS_ROOT",
    "EXPECTED_KEY_BYTES",
    "EXPECTED_KEY_SHA256",
    "SONNET_4_6_REC_DOM_IMG_008",
    "SPANISH_OPTIMISM_BIAS_CAVEAT",
    "TWIN_LINK_IS_PROSE",
    "CeilingOutcome",
    "CeilingReport",
    "CeilingRow",
    "ColumnExpectation",
    "ColumnSegmentationSize",
    "CorpusDocument",
    "CorpusKey",
    "CorpusKeyError",
    "Denominators",
    "EmittedOnly",
    "EngineRoute",
    "FieldOutcome",
    "FieldScoring",
    "FieldVerdict",
    "HarnessRefusalError",
    "HarnessReport",
    "ModelTier",
    "PipelineStage",
    "ProvenanceClass",
    "ReferencePoint",
    "ResultRow",
    "Scored",
    "TABULAR_COLUMN_ROLE_TRUTH",
    "TabularTruthError",
    "TwinPair",
    "amounts_match",
    "build_result_row",
    "caveats_for_document",
    "colocation_ceiling",
    "column_aware_rendering_partitions",
    "column_role_truth_document",
    "defensible_alternate_fields",
    "documents_with_authored_transcription",
    "emission_from_roles",
    "emitted_or_scored",
    "format_report",
    "geometry_payload_ratio",
    "load_corpus_key",
    "normalise_whitespace",
    "reference_points_with_key_context",
    "render_page_text",
    "require_model_tier",
    "score_emission",
    "slot_name",
    "sorted_rows_by_document",
    "verify_decimal_comparison_path",
]
