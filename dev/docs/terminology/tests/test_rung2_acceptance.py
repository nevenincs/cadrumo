"""Real-behaviour tests for the pre-artifact Rung-2 acceptance boundary."""

from __future__ import annotations

import math
from typing import cast

import pytest
from pydantic import ValidationError

from cadrumo.core.external_constants import OutputLanguage
from dev.docs.terminology._rung2_acceptance import (
    RUNG2_CONFIG_SCHEMA_VERSION,
    Rung2AcceptanceError,
    Rung2AcceptanceEvidence,
    Rung2BrowserConfig,
    validate_rung2_browser_config,
)
from dev.docs.terminology._rung2_bridge import (
    Rung2SearchBundle,
    SemanticBridge,
    build_record_manifest,
    build_rung2_search_bundle,
)
from dev.docs.terminology._rung2_provenance import build_rung2_input_provenance
from dev.docs.terminology._rung2_query_authority import build_query_alias_authority_provenance
from dev.docs.terminology._search_record import SearchRecordKind
from dev.docs.terminology._static_matrix import (
    EMBEDDING_MATRIX_SCHEMA_VERSION,
    INT8_QUANTIZATION_ALGORITHM,
    NORMALIZATION_CONTRACT_VERSION,
    ROW_ORDER,
    ModelMetadata,
    NormalizationContract,
    ProviderProvenance,
    QuantizedEmbeddingRow,
    QuantizedQueryTokenRow,
    StaticEmbeddingMatrix,
    TokenInventoryEntry,
    TokenizerProvenance,
    query_token_fingerprint,
    vocabulary_fingerprint,
)
from dev.docs.terminology._sweep import SweepResult, TermRelevanceMapping, TermTargetRef
from dev.docs.terminology._unified_record import RankingTier, SearchRecord, SearchRecordMetadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _acceptance_evidence_data() -> dict[str, object]:
    """Return schema-shaped evidence values for validation-only cases."""
    return {
        "approved": True,
        "minimum_coverage_ratio": 0.8,
        "cosine_floor": 0.75,
        "runner_up_margin": 0.05,
        "maximum_quantization_drift": 0.02,
        "measured_quantization_drift": 0.01,
        "payload_bytes": 1024,
        "quantization_accepted": True,
        "held_out_top_five_loss": False,
        "held_out_miss_rate": 0.0,
        "no_locale_or_kind_regression": True,
    }


def _browser_config_data() -> dict[str, object]:
    """Return a config-only payload without creating or loading an artifact."""
    return {
        "schema_version": RUNG2_CONFIG_SCHEMA_VERSION,
        "enabled": True,
        "normalization_version": NORMALIZATION_CONTRACT_VERSION,
        "bundle_url": "bundle.json",
        # This digest is shape-valid evidence only; no bundle is created or read.
        "bundle_sha256": "0" * 64,
        "acceptance": _acceptance_evidence_data(),
    }


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("minimum_coverage_ratio", math.nan),
        ("cosine_floor", math.inf),
        ("runner_up_margin", -math.inf),
        ("maximum_quantization_drift", math.nan),
        ("measured_quantization_drift", math.inf),
        ("held_out_miss_rate", math.nan),
    ],
)
def test_acceptance_evidence_rejects_non_finite_measurements(field_name: str, value: float) -> None:
    """Non-finite measurements cannot cross the acceptance boundary."""
    data = _acceptance_evidence_data()
    data[field_name] = value

    with pytest.raises(ValidationError) as exc_info:
        Rung2AcceptanceEvidence.model_validate(data)

    assert field_name in str(exc_info.value)


def test_acceptance_evidence_rejects_drift_above_supplied_bound() -> None:
    """Measured quantization drift must not exceed its declared maximum."""
    data = _acceptance_evidence_data()
    data["maximum_quantization_drift"] = 0.01
    data["measured_quantization_drift"] = 0.011

    with pytest.raises(ValidationError, match="drift exceeds acceptance"):
        Rung2AcceptanceEvidence.model_validate(data)


@pytest.mark.parametrize("field_name", ["maximum_quantization_drift", "measured_quantization_drift"])
def test_acceptance_evidence_rejects_drift_outside_absolute_bound(field_name: str) -> None:
    """Drift evidence cannot exceed the shared [0, 2] metric domain."""
    data = _acceptance_evidence_data()
    data[field_name] = 2.001

    with pytest.raises(ValidationError, match=field_name):
        Rung2AcceptanceEvidence.model_validate(data)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("approved", False),
        ("quantization_accepted", False),
        ("held_out_top_five_loss", True),
        ("no_locale_or_kind_regression", False),
    ],
)
def test_acceptance_evidence_rejects_wrong_approval_flags(field_name: str, value: bool) -> None:
    """Every approval flag must carry its exact ratified literal value."""
    data = _acceptance_evidence_data()
    data[field_name] = value

    with pytest.raises(ValidationError) as exc_info:
        Rung2AcceptanceEvidence.model_validate(data)

    assert field_name in str(exc_info.value)


def test_browser_config_rejects_disabled_config() -> None:
    """The browser tier cannot be enabled by a false or missing enablement flag."""
    data = _browser_config_data()
    data["enabled"] = False

    with pytest.raises(ValidationError):
        Rung2BrowserConfig.model_validate(data)


def test_browser_config_rejects_wrong_normalization_contract() -> None:
    """Browser tokenization must use the shared normalization contract."""
    data = _browser_config_data()
    data["normalization_version"] = "not-the-shared-normalization-contract"

    with pytest.raises(ValidationError, match="normalization version"):
        Rung2BrowserConfig.model_validate(data)


def test_browser_config_rejects_extra_fields() -> None:
    """Unknown config fields cannot silently widen the browser contract."""
    data = _browser_config_data()
    data["unexpected"] = True

    with pytest.raises(ValidationError):
        Rung2BrowserConfig.model_validate(data)


def test_validate_browser_config_rejects_non_bundle_without_mutating_config() -> None:
    """The bundle type guard runs before any bundle-dependent acceptance work."""
    config = Rung2BrowserConfig.model_validate(_browser_config_data())
    before = config.model_dump(mode="json")
    non_bundle = cast(Rung2SearchBundle, object())

    with pytest.raises(Rung2AcceptanceError, match="already validated Rung2SearchBundle"):
        validate_rung2_browser_config(config, non_bundle)

    assert config.model_dump(mode="json") == before


def test_build_record_manifest_accepts_canonical_json_record_array() -> None:
    """The JSON record array hydrates the strict tuple manifest field."""
    record = SearchRecord(
        id="page:how-to/rung2",
        kind=SearchRecordKind.PAGE,
        tier=RankingTier.FULLTEXT,
        title="Rung-2 search",
        descriptions={OutputLanguage.ES: "Busqueda Rung-2"},
        target="how-to/rung2.html",
        ranking_weight=0.5,
        metadata=SearchRecordMetadata(),
    )

    manifest = build_record_manifest([record])

    assert isinstance(manifest.records, tuple)
    assert manifest.records[0].record_id == record.id
    assert manifest.records[0].target == record.target


def _validated_test_matrix() -> StaticEmbeddingMatrix:
    """Return one fully validated production matrix row for bridge composition."""
    query_term = "prorrata"
    model = ModelMetadata(
        repository="test/model",
        revision="0" * 40,
        spdx_license="MIT",
        dimension=1,
        model_snapshot_sha256="0" * 64,
        provider=ProviderProvenance(
            package="test-provider",
            version="1.0.0",
            source_sha256="0" * 64,
        ),
        tokenizer=TokenizerProvenance(
            package="test-tokenizer",
            version="1.0.0",
            repository="test/tokenizer",
            revision="0" * 40,
            vocabulary_sha256="0" * 64,
            config_sha256="0" * 64,
            normalization=NormalizationContract(
                algorithm="unicode-word-runs-nfkc-lower-v1",
                unicode_form="NFKC",
                case_mapping="lower",
                accent_policy="preserve",
                token_boundaries="unicode-letter-number-runs-v1",  # noqa: S106 - schema contract literal
                separator_policy="collapse-to-boundary-v1",
            ),
        ),
    )
    return StaticEmbeddingMatrix(
        schema_version=EMBEDDING_MATRIX_SCHEMA_VERSION,
        model=model,
        vocabulary_sha256=vocabulary_fingerprint((query_term,)),
        vocabulary_count=1,
        query_token_sha256=query_token_fingerprint((query_term,)),
        query_token_count=1,
        dimension=1,
        quantization_algorithm=INT8_QUANTIZATION_ALGORITHM,
        row_order=ROW_ORDER,
        token_inventory=(TokenInventoryEntry(term=query_term, token_ids=(17,), token_count=1),),
        rows=(QuantizedEmbeddingRow(term=query_term, scale=1.0, values=(1,)),),
        query_token_rows=(
            QuantizedQueryTokenRow(
                token=query_term,
                model_token_ids=(17,),
                token_count=1,
                scale=1.0,
                values=(1,),
            ),
        ),
        serialized_bytes=1592,
        artifact_sha256="019c470853af2af42deaddc56514214694d553078059ee811dfd3ecbfff16b24",
    )


def test_build_rung2_search_bundle_validates_projected_mapping_tuple_contract() -> None:
    """A projected concept/legal mapping compiles into validated tuple fields."""
    concept = SearchRecord(
        id="concept:prorrata",
        kind=SearchRecordKind.CONCEPT,
        tier=RankingTier.TERM,
        title="Prorrata",
        descriptions={OutputLanguage.ES: "Regla de prorrata"},
        target="_generated/glossary.html#term-prorrata",
        ranking_weight=0.8,
        metadata=SearchRecordMetadata(concept_id="prorrata", domain="general"),
    )
    legal = SearchRecord(
        id="legal:ley-37-1992:art-102",
        kind=SearchRecordKind.LEGAL,
        tier=RankingTier.FULLTEXT,
        title="Ley 37/1992, artículo 102",
        descriptions={OutputLanguage.ES: "Artículo 102"},
        target="_generated/legal/boe-a-1992-28740.html#legal-ley-37-1992-art-102",
        ranking_weight=0.5,
        metadata=SearchRecordMetadata(legal_id="ley-37-1992:art-102"),
    )
    projected_targets = (
        TermTargetRef(
            record_id=legal.id,
            target=legal.target,
            kind=legal.kind,
            surface="legal",
            ranking_weight=legal.ranking_weight,
        ),
        TermTargetRef(
            record_id=concept.id,
            target=concept.target,
            kind=concept.kind,
            surface="concept",
            ranking_weight=concept.ranking_weight,
        ),
    )
    sweep = SweepResult(
        mappings=(
            TermRelevanceMapping(
                query="prorrata",
                concept_id="prorrata",
                language=OutputLanguage.ES,
                targets=projected_targets,
            ),
        ),
        query_count=1,
        concept_count=1,
        failed_query_count=0,
        reindex_note="test-fixture: no reindex",
        score_floor=0.5,
    )
    provenance = build_rung2_input_provenance(
        source_relpath="src/cadrumo/_data/terminology/relevance/relevance.json",
        source_bytes=b"projected relevance",
        vocabulary=("prorrata",),
        query_tokens=("prorrata",),
        query_alias_authority=build_query_alias_authority_provenance(),
    )

    bundle = build_rung2_search_bundle(
        _validated_test_matrix(),
        sweep,
        (legal, concept),
        provenance=provenance,
    )
    revalidated = Rung2SearchBundle.model_validate_json(bundle.to_json_bytes())

    assert isinstance(bundle.bridge, SemanticBridge)
    assert isinstance(bundle.bridge.entries, tuple)
    assert isinstance(bundle.bridge.entries[0].targets, tuple)
    assert tuple(entry.term for entry in bundle.bridge.entries) == ("prorrata",)
    assert tuple(target.record_id for target in bundle.bridge.entries[0].targets) == (concept.id, legal.id)
    assert revalidated == bundle
