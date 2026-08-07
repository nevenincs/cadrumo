"""Real-behaviour tests for the pre-artifact Rung-2 acceptance boundary."""

from __future__ import annotations

import math
from hashlib import sha256
from typing import cast

import pytest
from pydantic import ValidationError

from cadrumo.core.external_constants import OutputLanguage
from dev.docs.terminology._jcs import canonical_json_bytes
from dev.docs.terminology._model2vec_provider import (
    POTION_MODEL_DIMENSION,
    POTION_MODEL_LICENSE,
    POTION_MODEL_REPOSITORY,
    POTION_MODEL_REVISION,
)
from dev.docs.terminology._rung2_acceptance import (
    POTION_MODEL_SNAPSHOT_SHA256,
    POTION_PROVIDER_PACKAGE,
    POTION_PROVIDER_SOURCE_SHA256,
    POTION_PROVIDER_VERSION,
    POTION_TOKENIZER_CONFIG_SHA256,
    POTION_TOKENIZER_PACKAGE,
    POTION_TOKENIZER_VERSION,
    POTION_TOKENIZER_VOCABULARY_SHA256,
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
        repository=POTION_MODEL_REPOSITORY,
        revision=POTION_MODEL_REVISION,
        spdx_license=POTION_MODEL_LICENSE,
        dimension=POTION_MODEL_DIMENSION,
        model_snapshot_sha256=POTION_MODEL_SNAPSHOT_SHA256,
        provider=ProviderProvenance(
            package=POTION_PROVIDER_PACKAGE,
            version=POTION_PROVIDER_VERSION,
            source_sha256=POTION_PROVIDER_SOURCE_SHA256,
        ),
        tokenizer=TokenizerProvenance(
            package=POTION_TOKENIZER_PACKAGE,
            version=POTION_TOKENIZER_VERSION,
            repository=POTION_MODEL_REPOSITORY,
            revision=POTION_MODEL_REVISION,
            vocabulary_sha256=POTION_TOKENIZER_VOCABULARY_SHA256,
            config_sha256=POTION_TOKENIZER_CONFIG_SHA256,
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
        dimension=POTION_MODEL_DIMENSION,
        quantization_algorithm=INT8_QUANTIZATION_ALGORITHM,
        row_order=ROW_ORDER,
        token_inventory=(TokenInventoryEntry(term=query_term, token_ids=(17,), token_count=1),),
        rows=(QuantizedEmbeddingRow(term=query_term, scale=1.0, values=(1,) + (0,) * (POTION_MODEL_DIMENSION - 1)),),
        query_token_rows=(
            QuantizedQueryTokenRow(
                token=query_term,
                model_token_ids=(17,),
                token_count=1,
                scale=1.0,
                values=(1,) + (0,) * (POTION_MODEL_DIMENSION - 1),
            ),
        ),
        serialized_bytes=2653,
        artifact_sha256="e47aae7337b68c2746939cc76f038582b6ad89d852d1adb36cf359d7ab2b2cce",
    )


def _matrix_with_model(matrix: StaticEmbeddingMatrix, model: ModelMetadata) -> StaticEmbeddingMatrix:
    """Revalidate one fixture matrix after changing its provenance metadata."""
    data = matrix.model_dump()
    data["model"] = model.model_dump()
    unsigned = {key: value for key, value in data.items() if key not in {"artifact_sha256", "serialized_bytes"}}
    data["artifact_sha256"] = sha256(canonical_json_bytes(unsigned)).hexdigest()
    data["serialized_bytes"] = 0
    for _ in range(8):
        serialized_bytes = len(canonical_json_bytes(data))
        if serialized_bytes == data["serialized_bytes"]:
            break
        data["serialized_bytes"] = serialized_bytes
    return StaticEmbeddingMatrix.model_validate(data)


def _validated_test_bundle(matrix: StaticEmbeddingMatrix | None = None) -> Rung2SearchBundle:
    """Build one fully linked bundle through the production bridge contract."""
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

    return build_rung2_search_bundle(
        _validated_test_matrix() if matrix is None else matrix,
        sweep,
        (legal, concept),
        provenance=provenance,
    )


def _browser_config_for_bundle(bundle: Rung2SearchBundle) -> Rung2BrowserConfig:
    """Bind config evidence to the production bundle's canonical bytes."""
    payload = bundle.to_json_bytes()
    evidence = _acceptance_evidence_data()
    evidence["payload_bytes"] = len(payload)
    data = _browser_config_data()
    data["bundle_sha256"] = sha256(payload).hexdigest()
    data["acceptance"] = evidence
    return Rung2BrowserConfig.model_validate(data)


def test_build_rung2_search_bundle_validates_projected_mapping_tuple_contract() -> None:
    """A projected concept/legal mapping compiles into validated tuple fields."""
    bundle = _validated_test_bundle()
    revalidated = Rung2SearchBundle.model_validate_json(bundle.to_json_bytes())

    assert isinstance(bundle.bridge, SemanticBridge)
    assert isinstance(bundle.bridge.entries, tuple)
    assert isinstance(bundle.bridge.entries[0].targets, tuple)
    assert tuple(entry.term for entry in bundle.bridge.entries) == ("prorrata",)
    assert tuple(target.record_id for target in bundle.bridge.entries[0].targets) == (
        "concept:prorrata",
        "legal:ley-37-1992:art-102",
    )
    assert revalidated == bundle


def test_validate_browser_config_accepts_canonical_bundle_evidence() -> None:
    """Acceptance succeeds only when config evidence names the exact bundle bytes."""
    bundle = _validated_test_bundle()
    config = _browser_config_for_bundle(bundle)

    assert validate_rung2_browser_config(config, bundle) == config


@pytest.mark.parametrize(
    ("field_name", "value"),
    [("bundle_sha256", "f" * 64), ("payload_bytes", 1)],
)
def test_validate_browser_config_rejects_noncanonical_payload_evidence(field_name: str, value: object) -> None:
    """A stale hash or byte count cannot authorize a bundle."""
    bundle = _validated_test_bundle()
    data = _browser_config_for_bundle(bundle).model_dump(mode="json")
    if field_name == "payload_bytes":
        data["acceptance"][field_name] = value
    else:
        data[field_name] = value

    with pytest.raises(Rung2AcceptanceError, match=r"(?:sha256|byte evidence)"):
        validate_rung2_browser_config(data, bundle)


def test_bundle_rejects_tampered_matrix_self_attestation() -> None:
    """A matrix hash mutation is rejected before browser acceptance can run."""
    data = _validated_test_bundle().model_dump()
    data["matrix"]["artifact_sha256"] = "f" * 64

    with pytest.raises(ValidationError, match="artifact_sha256"):
        Rung2SearchBundle.model_validate(data)


@pytest.mark.parametrize(
    "model_update",
    [
        {"spdx_license": "Apache-2.0"},
        {"model_snapshot_sha256": "0" * 64},
        {"provider": {"package": "unapproved-provider"}},
        {"provider": {"version": "9.9.9"}},
        {"provider": {"source_sha256": "0" * 64}},
        {"tokenizer": {"package": "unapproved-tokenizer"}},
        {"tokenizer": {"version": "9.9.9"}},
        {"tokenizer": {"repository": "unapproved/tokenizer"}},
        {"tokenizer": {"revision": "f" * 40}},
        {"tokenizer": {"vocabulary_sha256": "0" * 64}},
        {"tokenizer": {"config_sha256": "0" * 64}},
    ],
    ids=[
        "licence",
        "model-snapshot-root",
        "provider-package",
        "provider-version",
        "provider-source-root",
        "tokenizer-package",
        "tokenizer-version",
        "tokenizer-repository",
        "tokenizer-revision",
        "tokenizer-vocabulary-root",
        "tokenizer-config-root",
    ],
)
def test_validate_browser_config_rejects_unapproved_model_or_tokenizer_identity(
    model_update: dict[str, object],
) -> None:
    """A schema-valid but unapproved provenance stamp remains fail-closed."""
    matrix = _validated_test_matrix()
    provider = matrix.model.provider
    tokenizer = matrix.model.tokenizer
    updated_model = matrix.model.model_copy(
        update={
            **{key: value for key, value in model_update.items() if key not in {"provider", "tokenizer"}},
            "provider": provider.model_copy(update=model_update.get("provider", {})),
            "tokenizer": tokenizer.model_copy(update=model_update.get("tokenizer", {})),
        },
    )
    bundle = _validated_test_bundle(_matrix_with_model(matrix, updated_model))

    with pytest.raises(Rung2AcceptanceError, match=r"(?:model identity|provider/tokenizer identity)"):
        validate_rung2_browser_config(_browser_config_for_bundle(bundle), bundle)
