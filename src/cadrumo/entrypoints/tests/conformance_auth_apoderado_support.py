"""Registered-executor conformance scenarios for the four apoderado operations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from ...adapters.persistence.profile.apoderado import build_apoderado_config_repository
from ...application.auth.apoderado_contracts import (
    APODERADO_CHECK_OPERATION_DEFINITION_ID,
    APODERADO_CLEAR_OPERATION_DEFINITION_ID,
    APODERADO_CONFIGURE_OPERATION_DEFINITION_ID,
    APODERADO_STATUS_OPERATION_DEFINITION_ID,
    ApoderadoCheckRequest,
    ApoderadoClearRequest,
    ApoderadoConfigurationSnapshot,
    ApoderadoConfigureRequest,
    ApoderadoOperationProjection,
    ApoderadoStatusRequest,
    ApoderadoStatusSnapshot,
)
from ...application.auth.apoderado_repository import ApoderadoConfigurationRepository
from ...application.auth.apoderado_service import ApoderadoConfiguration
from ...core.config import load_settings
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.runtime_catalogues import ApoderamientoScopeRecord
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

# A well-formed NIF: 87654321 mod 23 = 10, which selects check letter X.
_REPRESENTED_NIF = "87654321X"
_NOTES = "Conformance delegation"
_SEEDED_AT = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)

# The live verification path is sealed (`ApoderadoService.check` always raises),
# so the executor settles the documented prewrite refusal.
_LIVE_CHECK_UNAVAILABLE = "REFUSED_APODERADO_LIVE_CHECK_UNAVAILABLE"


def _repository(context: ConformanceFamilyContext) -> ApoderadoConfigurationRepository:
    return build_apoderado_config_repository(bucket_id=str(context.profile_id), settings=load_settings())


def _published_scopes(context: ConformanceFamilyContext) -> tuple[str, str, str]:
    """Return two published scope codes in code order and the published catalogue version."""
    scopes = context.operation.runtime_catalogue("apoderamientos_scopes")
    assert isinstance(scopes, Mapping)
    codes = sorted(record.code for record in scopes.values() if isinstance(record, ApoderamientoScopeRecord))
    assert len(codes) >= 2
    version = context.operation.runtime_catalogue("apoderamientos_version")
    assert isinstance(version, str)
    return codes[0], codes[1], version


def _seeded_configuration(context: ConformanceFamilyContext) -> ApoderadoConfiguration:
    first, second, version = _published_scopes(context)
    configuration = ApoderadoConfiguration(
        bucket_id=str(context.profile_id),
        represented_nif=_REPRESENTED_NIF,
        granted_scopes=(first, second),
        catalogue_version=version,
        configured_at=_SEEDED_AT,
        notes=_NOTES,
    )
    _repository(context).save(configuration)
    return configuration


def _subject(context: ConformanceFamilyContext) -> str:
    return profile_operation_subject(str(context.profile_id))


def _prepare_status(context: ConformanceFamilyContext) -> ConformancePreparation:
    seeded = _seeded_configuration(context)
    return ConformancePreparation(
        subject_ref=_subject(context),
        request=ApoderadoStatusRequest(profile_id=context.profile_id),
        expected_result=ApoderadoOperationProjection(
            profile_id=context.profile_id,
            operation_id=APODERADO_STATUS_OPERATION_DEFINITION_ID,
            outcome="completed",
            effect=OperationEffect.NONE,
            # Status shows the stored delegation but not its free-text notes.
            status=ApoderadoStatusSnapshot(
                bucket_id=context.profile_id,
                configured=True,
                represented_nif=seeded.represented_nif,
                granted_scopes=seeded.granted_scopes,
                catalogue_version=seeded.catalogue_version,
                configured_at=seeded.configured_at,
            ),
        ),
        verify=lambda _outcome: _require_stored(context, seeded),
    )


def _require_stored(context: ConformanceFamilyContext, expected: ApoderadoConfiguration | None) -> None:
    assert _repository(context).load() == expected


def _prepare_configure(context: ConformanceFamilyContext) -> ConformancePreparation:
    first, second, version = _published_scopes(context)
    assert _repository(context).load() is None
    started_at = now()

    def verify(outcome: ConformanceOutcome) -> None:
        projection = outcome.resolve_result(ApoderadoOperationProjection)
        assert projection.configuration is not None
        configured_at = projection.configuration.configured_at
        assert started_at <= configured_at <= now()
        # Duplicate tokens collapse, keeping the order of first appearance.
        expected_scopes = (second, first)
        assert projection == ApoderadoOperationProjection(
            profile_id=context.profile_id,
            operation_id=APODERADO_CONFIGURE_OPERATION_DEFINITION_ID,
            outcome="completed",
            effect=OperationEffect.UPDATED,
            configuration=ApoderadoConfigurationSnapshot(
                bucket_id=context.profile_id,
                represented_nif=_REPRESENTED_NIF,
                granted_scopes=expected_scopes,
                catalogue_version=version,
                configured_at=configured_at,
                notes=_NOTES,
            ),
        )
        _require_stored(
            context,
            ApoderadoConfiguration(
                bucket_id=str(context.profile_id),
                represented_nif=_REPRESENTED_NIF,
                granted_scopes=expected_scopes,
                catalogue_version=version,
                configured_at=configured_at,
                notes=_NOTES,
            ),
        )

    return ConformancePreparation(
        subject_ref=_subject(context),
        request=ApoderadoConfigureRequest(
            profile_id=context.profile_id, scope_tokens=(second, first, second), notes=_NOTES
        ),
        # The represented tax identity travels only through the one-use secret slot.
        secret=_REPRESENTED_NIF.encode("utf-8"),
        verify=verify,
    )


def _prepare_clear(context: ConformanceFamilyContext) -> ConformancePreparation:
    _seeded_configuration(context)
    return ConformancePreparation(
        subject_ref=_subject(context),
        request=ApoderadoClearRequest(profile_id=context.profile_id),
        expected_result=ApoderadoOperationProjection(
            profile_id=context.profile_id,
            operation_id=APODERADO_CLEAR_OPERATION_DEFINITION_ID,
            outcome="completed",
            effect=OperationEffect.UPDATED,
            cleared=True,
        ),
        verify=lambda _outcome: _require_stored(context, None),
    )


def _prepare_check(context: ConformanceFamilyContext) -> ConformancePreparation:
    seeded = _seeded_configuration(context)
    return ConformancePreparation(
        subject_ref=_subject(context),
        request=ApoderadoCheckRequest(profile_id=context.profile_id),
        expected_result=ApoderadoOperationProjection(
            profile_id=context.profile_id,
            operation_id=APODERADO_CHECK_OPERATION_DEFINITION_ID,
            outcome="prewrite_refusal",
            effect=OperationEffect.NONE,
            refusal_code=_LIVE_CHECK_UNAVAILABLE,
        ),
        # The refused live check never touches the stored delegation.
        verify=lambda _outcome: _require_stored(context, seeded),
    )


_PREPARERS = {
    APODERADO_STATUS_OPERATION_DEFINITION_ID: _prepare_status,
    APODERADO_CONFIGURE_OPERATION_DEFINITION_ID: _prepare_configure,
    APODERADO_CLEAR_OPERATION_DEFINITION_ID: _prepare_clear,
    APODERADO_CHECK_OPERATION_DEFINITION_ID: _prepare_check,
}


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    preparer = _PREPARERS.get(context.definition.definition_id)
    if preparer is None:
        raise AssertionError(f"no apoderado conformance scenario for {context.definition.definition_id}")
    return preparer(context)


AUTH_APODERADO_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            APODERADO_STATUS_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (APODERADO_STATUS_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            APODERADO_CONFIGURE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (APODERADO_CONFIGURE_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            APODERADO_CLEAR_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            # A delegation was seeded, so clearing removes a record.
            OperationEffect.UPDATED,
            (APODERADO_CLEAR_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            APODERADO_CHECK_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (APODERADO_CHECK_OPERATION_DEFINITION_ID,),
            expected_refusal_ref=_LIVE_CHECK_UNAVAILABLE,
        ),
    ),
    prepare=_prepare,
)
