"""Strict roundtrip across the encrypted CalculationRevisionCatalogueRepository.

Persists :class:`CalculationRevisionCatalogue` under
``cadrumo.domain.modelos.calculation_revisions`` at
``SensitivityClass.FINANCIAL``.

The calculation-revision catalogue is the FINANCIAL-class encrypted
boundary that carries formula provenance. ``CalculationRevision.observations``
defaults to ``()``; a save-drops-field regression on that typed envelope
is invisible unless a roundtrip fixture populates it with real
:class:`CasillaObservation` entries carrying ``legal_refs`` / ``source_refs``.

The fixture below populates EVERY defaultable field with a non-default
value: a non-default lifecycle state (``VERIFICADO_COMPLETO`` with the
required audit triple), populated ``input_values_by_casilla_id`` / ``binding_overrides``
/ ``casilla_values``, populated ``source_transaction_ids``, and a populated
``observations`` tuple. The anti-tautology proof mutates the on-disk
encrypted JSON to drop the ``observations`` field and asserts the boundary
surfaces the regression rather than silently re-defaulting to ``()``.
"""

from __future__ import annotations

import json as _json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.classification.policies import SensitivityClass
from .....core.period import Period
from .....domain.calculations.registry.authority import bundled_authority
from .....domain.calculations.registry.bindings import CasillaObservation
from .....domain.calculations.registry.formula_runtime import RegistryCalculationUnresolvedOutcome
from .....domain.calculations.registry.formula_runtime_ops import RegistryUnresolvedOutcomeReason
from .....domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from .....domain.filing_evidence import FilingEvidenceReference
from .....domain.iva.regimen_simplificado_rows import (
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from .....domain.modelos.calculation_repository import CalculationRevisionPersistenceError
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    FilingInstanceEvidence,
    derive_calculation_revision_id,
)
from .....domain.modelos.calculation_revision_m303_evidence import M303Exonerado390FilingEvidence
from .....domain.modelos.calculation_revision_m303_handoff import M303FilingInstanceEvidence
from .....tests.filing_evidence import regimen_simplificado_filing_evidence
from .....tests.secure_sql import isolated_runtime_profile
from ..modelos_calculation import (
    _CALCULATION_CATALOGUE_VERSION,
    _CALCULATION_NAMESPACE,
    _CALCULATION_OBJECT_KEY,
    CalculationRevisionCatalogueRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "df5dd25a-ff53-4086-9cc4-a13e61538a09"  # was 'modelo-runtime'
_CORRUPT_ENVELOPE_WRITTEN_AT = datetime(2026, 5, 28, 10, 45, 0, tzinfo=UTC)
_FUTURE_ENVELOPE_WRITTEN_AT = datetime(2026, 5, 28, 10, 50, 0, tzinfo=UTC)
_IVA_BASE_IMPONIBLE_CASILLA: CasillaId = validated_casilla_id(
    "iva.base-imponible",
    surface="_IVA_BASE_IMPONIBLE_CASILLA",
)
_CASILLA_01: CasillaId = validated_casilla_id("casilla-01", surface="_CASILLA_01")
_CASILLA_12: CasillaId = validated_casilla_id("casilla-12", surface="_CASILLA_12")
_DECL_PERIODO_CASILLA: CasillaId = validated_casilla_id("decl.periodo", surface="_DECL_PERIODO_CASILLA")
_DECL_PERIODO_CODE = "1T"


def _hex(seed: str) -> str:
    """Return a stable 64-char hex blob for typed-id fixture values."""

    base = seed * 64
    return base[:64]


def _filing_instance_evidence() -> FilingInstanceEvidence:
    period = Period.from_year_and_code(2026, "1T")
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )
    snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=bundled_authority().snapshot("303", filing_year=2026, period="1T"),
        scope_decision=scope,
    )
    return FilingInstanceEvidence(
        m303=M303FilingInstanceEvidence(
            period=period,
            joint_return_elected=True,
            annual_volume_nonzero=False,
            insolvency=None,
            exonerado_390=M303Exonerado390FilingEvidence(
                applicable=False,
                applicability_reference=FilingEvidenceReference(reference="test:persistence:exonerado-390"),
                endpoints=(),
                activity_rows=(),
                operaciones_terceros_declarables=None,
                operaciones_terceros_reference=None,
            ),
            regimen_simplificado=regimen_simplificado_filing_evidence(
                period=period,
                scope_decision=scope,
                rows=RegimenSimplificadoFilingRows(ejercicio=2026, activities=()),
                regimen_snapshot=snapshot,
                dana_2024_eligibility=None,
            ),
        ),
    )


def _populated_catalogue() -> CalculationRevisionCatalogue:
    """Build a catalogue whose every defaultable field is non-default.

    The single revision is in ``VERIFICADO_COMPLETO`` state (not the
    default ``BORRADOR``), carries populated inputs / overrides /
    casilla values / source transactions, and a populated
    ``observations`` tuple with two :class:`CasillaObservation`
    entries carrying real ``legal_refs`` / ``source_refs`` provenance.
    """

    work_unit_id = _hex("a")
    created_at = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)
    verified_at = created_at + timedelta(hours=3)

    # ``decl.periodo`` is a ``period_code`` casilla: its AEAT token rides the
    # string-valued ``input_values_by_casilla_id`` channel, never the strictly
    # Decimal ``casilla_values``. A non-decimal-shaped entry is the only fixture
    # value that would surface a boundary regression coercing this map's values
    # through a numeric parser.
    input_values_by_casilla_id = {
        _IVA_BASE_IMPONIBLE_CASILLA: "1000.00",
        _DECL_PERIODO_CASILLA: _DECL_PERIODO_CODE,
    }
    binding_overrides = {"modelo-303-compensacion-pendiente-anteriores": "50.00"}
    casilla_values = {_CASILLA_01: Decimal("1000.00"), _CASILLA_12: Decimal("210.00")}
    source_transaction_ids = (_hex("d"), _hex("e"))
    filing_instance_evidence = _filing_instance_evidence()

    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        source_transaction_ids=source_transaction_ids,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )

    observations = (
        CasillaObservation(
            casilla_id=_CASILLA_01,
            value=Decimal("1000.00"),
            formula_id=None,
            operand_refs=(),
            operand_casilla_refs=(),
            operand_values=(),
            legal_refs=("ley-37-1992:art-78",),
            source_refs=("aeat-modelo-303-instrucciones-2024",),
        ),
        CasillaObservation(
            casilla_id=_CASILLA_12,
            value=Decimal("210.00"),
            formula_id="iva-cuota-devengada-general",
            operand_refs=(_CASILLA_01,),
            operand_casilla_refs=(_CASILLA_01,),
            operand_values=(Decimal("1000.00"),),
            legal_refs=("ley-37-1992:art-90",),
            source_refs=("aeat-modelo-303-instrucciones-2024",),
        ),
    )

    unresolved_outcomes = (
        RegistryCalculationUnresolvedOutcome(
            casilla_id=_CASILLA_12,
            reason=RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING,
            formula_id="iva-cuota-devengada-general",
            op="irnr_resolve_tipo_gravamen",
            operand_refs=(_CASILLA_01,),
            operand_casilla_refs=(_CASILLA_01,),
            operand_values=(Decimal("1000.00"),),
            legal_refs=("ley-37-1992:art-90",),
            source_refs=("aeat-modelo-303-instrucciones-2024",),
            context={"tipo_renta": "interest", "country": "ZW"},
        ),
    )

    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        source_transaction_ids=source_transaction_ids,
        casilla_values=casilla_values,
        filing_instance_evidence=filing_instance_evidence,
        observations=observations,
        unresolved_outcomes=unresolved_outcomes,
        created_at=created_at,
        updated_at=verified_at,
        verified_at=verified_at,
        verified_by="aeat.cli.modelo.verify",
        source_provenance=(),
    )
    return CalculationRevisionCatalogue(revisions={revision_id: revision})


def test_calculation_revision_catalogue_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A fully-populated calculation revision round-trips through encrypted SQL."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID)
        original = _populated_catalogue()
        repo.save(original)
        loaded = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert loaded == original
    assert len(loaded.revisions) == 1
    (revision,) = loaded.values()
    assert revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert revision.created_at == datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)
    assert revision.updated_at == datetime(2024, 7, 1, 12, 0, 0, tzinfo=UTC)
    assert revision.verified_at == revision.updated_at
    assert revision.created_at.utcoffset() == UTC.utcoffset(revision.created_at)
    assert revision.updated_at.utcoffset() == UTC.utcoffset(revision.updated_at)
    assert revision.verified_at is not None
    assert revision.verified_at.utcoffset() == UTC.utcoffset(revision.verified_at)
    assert revision.filing_instance_evidence == _filing_instance_evidence()
    assert revision.filing_instance_evidence is not None
    assert revision.filing_instance_evidence.m303.regimen_simplificado.regimen_snapshot.orden.activity_refs
    # The non-decimal ``period_code`` entry must survive verbatim: the string
    # replay channel is where every text-family casilla persists.
    assert revision.input_values_by_casilla_id[_DECL_PERIODO_CASILLA] == _DECL_PERIODO_CODE
    # The typed observations envelope must survive the boundary
    # with its full formula provenance intact.
    assert len(revision.observations) == 2
    computed = next(o for o in revision.observations if o.formula_id is not None)
    assert computed.formula_id == "iva-cuota-devengada-general"
    assert computed.operand_refs == (_CASILLA_01,)
    assert computed.operand_casilla_refs == (_CASILLA_01,)
    assert computed.legal_refs == ("ley-37-1992:art-90",)
    assert computed.source_refs == ("aeat-modelo-303-instrucciones-2024",)
    # The typed unresolved-outcome envelope must survive the boundary with its
    # reason, grounding, and captured context intact.
    assert len(revision.unresolved_outcomes) == 1
    (outcome,) = revision.unresolved_outcomes
    assert outcome.reason is RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING
    assert outcome.legal_refs == ("ley-37-1992:art-90",)
    assert outcome.context == {"tipo_renta": "interest", "country": "ZW"}
    assert profile.paths.database_file.is_file()


def test_changed_filing_evidence_persists_as_a_distinct_revision_without_replacing_the_original(
    tmp_path: Path,
) -> None:
    """Editing filing evidence creates a new durable identity and preserves the old row."""

    original_catalogue = _populated_catalogue()
    original = next(iter(original_catalogue.values()))
    assert original.filing_instance_evidence is not None
    changed_evidence = FilingInstanceEvidence(
        m303=original.filing_instance_evidence.m303.model_copy(
            update={"joint_return_elected": not original.filing_instance_evidence.m303.joint_return_elected},
        ),
    )
    changed_revision_id = derive_calculation_revision_id(
        work_unit_id=original.work_unit_id,
        input_values_by_casilla_id=original.input_values_by_casilla_id,
        binding_overrides=original.binding_overrides,
        casilla_values=original.casilla_values,
        source_transaction_ids=original.source_transaction_ids,
        filing_instance_evidence=changed_evidence,
        source_provenance=(),
    )
    changed = original.model_copy(
        update={
            "calculation_revision_id": changed_revision_id,
            "filing_instance_evidence": changed_evidence,
        },
    )
    two_revisions = CalculationRevisionCatalogue(
        revisions={
            original.calculation_revision_id: original,
            changed.calculation_revision_id: changed,
        },
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        repo = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID)
        repo.save(original_catalogue)
        repo.save(two_revisions)
        loaded = repo.load()

    assert changed.calculation_revision_id != original.calculation_revision_id
    persisted_original = loaded.get(original.calculation_revision_id)
    assert persisted_original is not None
    assert persisted_original == original
    assert loaded.get(changed.calculation_revision_id) == changed
    assert persisted_original.filing_instance_evidence != changed_evidence


def test_calculation_revision_catalogue_dropped_observations_surfaces_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: dropping ``observations`` on disk must surface.

    Persists a revision carrying two :class:`CasillaObservation`
    entries, then surgically deletes the ``observations`` key from the
    encrypted JSON envelope. ``observations`` defaults to ``()`` on the
    model, so a naive load would silently re-default and return a
    catalogue that compares unequal to the original. The proof asserts
    the regression surfaces either as a ValidationError or as strict
    inequality on the loaded catalogue.

    If this test passes silently with the field dropped, the
    calculation-revision boundary is tautological and every roundtrip
    in the suite is suspect.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID)
        original = _populated_catalogue()
        repo.save(original)

        record = profile.repository.load(
            _CALCULATION_NAMESPACE,
            _CALCULATION_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_CALCULATION_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        revisions = envelope["payload"]["revisions"]
        ((_revision_id, persisted_revision),) = revisions.items()
        # Drop the typed provenance envelope from the on-disk
        # payload. A save-drops-field regression looks exactly
        # like this: the key is simply absent on reload.
        assert "observations" in persisted_revision, "fixture must persist observations for the proof to be meaningful"
        del persisted_revision["observations"]
        profile.repository.save(
            namespace=_CALCULATION_NAMESPACE,
            object_key=_CALCULATION_OBJECT_KEY,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        with pytest.raises(CalculationRevisionPersistenceError):
            CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID).load()


def test_calculation_revision_catalogue_dropped_filing_evidence_refuses_at_load(
    tmp_path: Path,
) -> None:
    """Dropping immutable M303 evidence must be observable at the encrypted boundary."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID)
        original = _populated_catalogue()
        repo.save(original)
        record = profile.repository.load(
            _CALCULATION_NAMESPACE,
            _CALCULATION_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_CALCULATION_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        ((_revision_id, persisted_revision),) = envelope["payload"]["revisions"].items()
        assert persisted_revision["filing_instance_evidence"] is not None
        del persisted_revision["filing_instance_evidence"]
        profile.repository.save(
            namespace=_CALCULATION_NAMESPACE,
            object_key=_CALCULATION_OBJECT_KEY,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        with pytest.raises(CalculationRevisionPersistenceError):
            CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID).load()


def test_calculation_revision_catalogue_wrong_inner_classification_is_localized(
    tmp_path: Path,
) -> None:
    """A corrupted envelope classification raises a translated persistence error."""

    from ...storage.envelope._envelope import Envelope

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        envelope = Envelope[CalculationRevisionCatalogue](
            schema_version=_CALCULATION_CATALOGUE_VERSION,
            written_at=_CORRUPT_ENVELOPE_WRITTEN_AT,
            classification=SensitivityClass.AUDIT,
            payload=CalculationRevisionCatalogue(),
        )
        profile.repository.save(
            namespace=_CALCULATION_NAMESPACE,
            object_key=_CALCULATION_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_CALCULATION_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

        with pytest.raises(CalculationRevisionPersistenceError) as raised:
            CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert raised.value.translated_message == "errors.fail.fail_modelo_calculation_revision_persistence"
    assert raised.value.context == {
        "reason": "classification_mismatch",
        "expected_classification": "financial",
        "actual_classification": "audit",
    }


def test_calculation_revision_catalogue_unsupported_storage_version_is_localized(
    tmp_path: Path,
) -> None:
    """A future inner envelope schema version raises a translated persistence error."""

    from ...storage.envelope._envelope import Envelope

    stored_schema_version = _CALCULATION_CATALOGUE_VERSION + 1
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        envelope = Envelope[CalculationRevisionCatalogue](
            schema_version=stored_schema_version,
            written_at=_FUTURE_ENVELOPE_WRITTEN_AT,
            classification=SensitivityClass.FINANCIAL,
            payload=CalculationRevisionCatalogue(),
        )
        profile.repository.save(
            namespace=_CALCULATION_NAMESPACE,
            object_key=_CALCULATION_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_CALCULATION_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

        with pytest.raises(CalculationRevisionPersistenceError) as raised:
            CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert raised.value.translated_message == "errors.fail.fail_modelo_calculation_revision_persistence"
    assert raised.value.context == {
        "reason": "unsupported_envelope_version",
        "stored_schema_version": stored_schema_version,
        "max_supported_version": _CALCULATION_CATALOGUE_VERSION,
    }


def test_pre_s58_evidence_less_catalogue_is_rejected_at_encrypted_load(
    tmp_path: Path,
) -> None:
    """The V2 cutover admits no evidence-less legacy calculation catalogue."""

    from ...storage.envelope._envelope import Envelope

    original = next(iter(_populated_catalogue().values()))
    legacy_revision_id = derive_calculation_revision_id(
        work_unit_id=original.work_unit_id,
        input_values_by_casilla_id=original.input_values_by_casilla_id,
        binding_overrides=original.binding_overrides,
        casilla_values=original.casilla_values,
        source_transaction_ids=original.source_transaction_ids,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    legacy_revision = original.model_copy(
        update={
            "calculation_revision_id": legacy_revision_id,
            "filing_instance_evidence": None,
        },
    )
    legacy_catalogue = CalculationRevisionCatalogue(revisions={legacy_revision_id: legacy_revision})

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        envelope = Envelope[CalculationRevisionCatalogue](
            schema_version=1,
            written_at=_FUTURE_ENVELOPE_WRITTEN_AT,
            classification=SensitivityClass.FINANCIAL,
            payload=legacy_catalogue,
        )
        profile.repository.save(
            namespace=_CALCULATION_NAMESPACE,
            object_key=_CALCULATION_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_CALCULATION_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

        with pytest.raises(CalculationRevisionPersistenceError) as raised:
            CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert raised.value.context == {
        "reason": "unsupported_envelope_version",
        "stored_schema_version": 1,
        "max_supported_version": _CALCULATION_CATALOGUE_VERSION,
    }


@pytest.mark.parametrize(
    "field",
    ("created_at", "updated_at", "verified_at"),
)
@pytest.mark.parametrize(
    "persisted_instant",
    ("2024-07-01T09:00:00", "2024-07-01T10:00:00+01:00"),
    ids=("naive", "offset"),
)
def test_calculation_revision_refuses_ambiguous_lifecycle_instants_at_encrypted_load(
    tmp_path: Path,
    field: str,
    persisted_instant: str,
) -> None:
    """Ambiguous lifecycle instants must not rehydrate out of durable storage.

    The model refuses naive and non-UTC instants at construction, but the
    persistence boundary is where a stored value re-enters the process, and
    chronological consumers mix these instants across revisions. Rewrites one
    lifecycle field in the encrypted envelope and asserts the read path refuses
    rather than returning a value whose wall-clock meaning depends on the
    machine that reads it.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID)
        repo.save(_populated_catalogue())

        record = profile.repository.load(
            _CALCULATION_NAMESPACE,
            _CALCULATION_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_CALCULATION_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        ((_revision_id, persisted_revision),) = envelope["payload"]["revisions"].items()
        assert persisted_revision.get(field), f"fixture must persist {field} for this proof to be meaningful"
        persisted_revision[field] = persisted_instant
        profile.repository.save(
            namespace=_CALCULATION_NAMESPACE,
            object_key=_CALCULATION_OBJECT_KEY,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        with pytest.raises(CalculationRevisionPersistenceError):
            CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID).load()
