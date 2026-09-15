"""Application-owned Modelo 100 borrador binding resolution tests."""

from __future__ import annotations

import hashlib
from collections.abc import Generator, Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority
from pydantic import ValidationError

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.errors.error_codes import ErrorCategory, get_registered_error_code
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.modelos.calculation_revision import derive_calculation_revision_id
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from ...aggregation.source_mesh import CalculationSourceContext
from ...live.borrador_100 import (
    Borrador100Snapshot,
    Borrador100SnapshotRepository,
    BorradorSnapshotNotFoundError,
)
from ...live.snapshot_base import SnapshotLifecycleState
from .._registry_helpers import validate_casilla_input_ids
from ..borrador_binding import (
    Modelo100BorradorBindingCommand,
    Modelo100BorradorBindingError,
    Modelo100BorradorSourceResolver,
    _decimal_value,
    resolve_modelo_100_borrador_bindings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_YEAR = 2025
_PERIOD = "0A"
_DECIMAL_BINDING: BindingId = "renta-modelo-111-retenciones-periodicas"
_ENUM_BINDING: BindingId = "renta-profile-tax-residence-ccaa"
_UNMARKED_BINDING: BindingId = "renta-ledger-expense-0186-deductible"
_R210_SIMULATOR_URL = aeat_url("www2", configured_path("sede_paths", "r210_simulator_open_ajax"))
_BORRADOR_IDENTITY_CASILLA: CasillaId = validated_casilla_id("0100", surface="_BORRADOR_IDENTITY_CASILLA")
_M100_TEXT_CASILLA: CasillaId = validated_casilla_id("0001", surface="_M100_TEXT_CASILLA")
_M100_NUMERIC_CASILLA: CasillaId = validated_casilla_id("0003", surface="_M100_NUMERIC_CASILLA")
_M303_RESULT_CASILLA: CasillaId = validated_casilla_id("iva.resultado", surface="_M303_RESULT_CASILLA")
_M200_AMBIGUOUS_PRINTED_NUMBER: CasillaId = validated_casilla_id(
    "00562",
    surface="_M200_AMBIGUOUS_PRINTED_NUMBER",
)
_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA: CasillaId = validated_casilla_id(
    "DP200010:00562",
    surface="_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA",
)
_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00562",
    surface="_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA",
)


class _InMemoryBorradorSnapshotRepository:
    """Inward fake for resolver tests; no storage layout or adapter is involved."""

    def __init__(self, *, bucket_id: str) -> None:
        self._bucket_id = bucket_id
        self._snapshots: dict[str, Borrador100Snapshot] = {}

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self, snapshot_id: str) -> bool:
        return snapshot_id in self._snapshots

    def load(self, snapshot_id: str) -> Borrador100Snapshot:
        try:
            return self._snapshots[snapshot_id]
        except KeyError as exc:
            raise BorradorSnapshotNotFoundError(
                translated_message="application.live.borrador.errors.snapshot_not_found",
                context={"snapshot_id": snapshot_id},
            ) from exc

    def list_snapshots(self) -> tuple[Borrador100Snapshot, ...]:
        return tuple(self._snapshots[snapshot_id] for snapshot_id in sorted(self._snapshots))

    def resolve(self, snapshot_id: str) -> Borrador100Snapshot:
        trimmed_snapshot_id = snapshot_id.strip()
        matches = tuple(
            snapshot
            for snapshot in self.list_snapshots()
            if snapshot.snapshot_id == trimmed_snapshot_id or snapshot.snapshot_id.startswith(trimmed_snapshot_id)
        )
        if not matches:
            raise BorradorSnapshotNotFoundError(
                translated_message="application.live.borrador.errors.snapshot_not_found",
                context={"snapshot_id": snapshot_id},
            )
        if len(matches) > 1:
            raise BorradorSnapshotNotFoundError(
                translated_message="application.live.borrador.errors.snapshot_prefix_ambiguous",
                context={"snapshot_id": snapshot_id, "match_count": len(matches)},
            )
        return matches[0]

    def save(self, snapshot: Borrador100Snapshot) -> None:
        self._snapshots[snapshot.snapshot_id] = snapshot


@pytest.fixture
def snapshot_repository() -> Generator[Borrador100SnapshotRepository]:
    yield _InMemoryBorradorSnapshotRepository(bucket_id=_BUCKET_ID)


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease one indexed authority generation for each binding-resolution test."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _modelo_100_registry_snapshot() -> RegistrySnapshot:
    return compiled_bundled_authority().snapshot("100", filing_year=_YEAR, period=_PERIOD)


def test_validate_casilla_input_ids_rejects_non_string_keys_without_coercion() -> None:
    snapshot = _modelo_100_registry_snapshot()

    with pytest.raises(RegistryValidationError):
        validate_casilla_input_ids(snapshot.revision, {1: Decimal("1")})


def test_validate_casilla_input_ids_keeps_unknown_only_context() -> None:
    """A syntactically canonical but undeclared id retains its precise context."""
    snapshot = _modelo_100_registry_snapshot()
    unknown_casilla_id = "modelo-100-not-declared-test"

    with pytest.raises(RegistryValidationError) as raised:
        validate_casilla_input_ids(snapshot.revision, {unknown_casilla_id: Decimal("1")})

    assert raised.value.context == {
        "casilla_ids": unknown_casilla_id,
        "revision_id": snapshot.revision.id,
    }


def test_validate_casilla_input_ids_keeps_malformed_key_precedence_over_other_failures() -> None:
    """Malformed keys refuse before unknown ids or invalid values are considered."""
    snapshot = _modelo_100_registry_snapshot()

    with pytest.raises(RegistryValidationError) as raised:
        validate_casilla_input_ids(
            snapshot.revision,
            {
                1: Decimal("1"),
                "modelo-100-not-declared-test": "not-a-decimal",
                _M100_NUMERIC_CASILLA: "also-not-a-decimal",
            },
        )

    assert raised.value.context == {
        "casilla_ids": "1",
        "revision_id": snapshot.revision.id,
    }


def test_validate_casilla_input_ids_rejects_printed_number_for_semantic_id() -> None:
    snapshot = compiled_bundled_authority().snapshot("303", filing_year=2025, period="1T")
    result_casilla = next(casilla for casilla in snapshot.revision.casillas if casilla.id == _M303_RESULT_CASILLA)
    assert result_casilla.number == "69"
    assert result_casilla.id != result_casilla.number
    assert result_casilla.number not in {casilla.id for casilla in snapshot.revision.casillas}

    with pytest.raises(RegistryValidationError) as raised:
        validate_casilla_input_ids(snapshot.revision, {result_casilla.number: Decimal("1")})

    # The alias-to-target mapping is a machine fact now, not a rendered sentence.
    assert raised.value.context == {
        "casilla_ids": result_casilla.number,
        "revision_id": snapshot.revision.id,
        "noncanonical_reference_targets": f"{result_casilla.number!r} -> {result_casilla.id}",
    }


def test_validate_casilla_input_ids_rejects_ambiguous_reused_printed_number() -> None:
    snapshot = compiled_bundled_authority().snapshot("200", filing_year=2025, period="0A")

    with pytest.raises(RegistryValidationError) as raised:
        validate_casilla_input_ids(snapshot.revision, {_M200_AMBIGUOUS_PRINTED_NUMBER: Decimal("1")})

    assert raised.value.context == {
        "casilla_ids": _M200_AMBIGUOUS_PRINTED_NUMBER,
        "revision_id": snapshot.revision.id,
        "noncanonical_reference_targets": (
            f"{_M200_AMBIGUOUS_PRINTED_NUMBER!r} is ambiguous; candidate casilla.id values: "
            f"{_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA}, {_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA}"
        ),
    }


def test_validate_casilla_input_ids_rejects_decimal_value_for_non_numeric_casilla() -> None:
    snapshot = _modelo_100_registry_snapshot()
    text_casilla = next(casilla for casilla in snapshot.revision.casillas if casilla.id == _M100_TEXT_CASILLA)
    assert text_casilla.data_type == "text"

    with pytest.raises(RegistryValidationError) as raised:
        validate_casilla_input_ids(snapshot.revision, {_M100_TEXT_CASILLA: Decimal("1")})

    assert raised.value.context == {
        "casilla_ids": _M100_TEXT_CASILLA,
        "revision_id": snapshot.revision.id,
        "data_types": "text",
    }


def test_validate_casilla_input_ids_rejects_non_decimal_numeric_value() -> None:
    snapshot = _modelo_100_registry_snapshot()
    numeric_casilla = next(casilla for casilla in snapshot.revision.casillas if casilla.id == _M100_NUMERIC_CASILLA)
    assert numeric_casilla.data_type in {"decimal", "money", "integer", "ratio"}

    with pytest.raises(RegistryValidationError) as raised:
        validate_casilla_input_ids(snapshot.revision, {_M100_NUMERIC_CASILLA: 1})

    assert raised.value.context == {
        "casilla_ids": _M100_NUMERIC_CASILLA,
        "revision_id": snapshot.revision.id,
        "value_types": "int",
    }


def _save_snapshot(
    repository: Borrador100SnapshotRepository,
    values: dict[str, Decimal | str],
    *,
    state: SnapshotLifecycleState = SnapshotLifecycleState.ACTIVE,
    superseded_by_snapshot_id: str | None = None,
    discarded_by: str = "",
) -> str:
    snapshot = Borrador100Snapshot(
        snapshot_id="a" * 64,
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _PERIOD),
        registry_snapshot_ref=_modelo_100_registry_snapshot().snapshot_ref,
        captured_at=datetime(2026, 4, 3, 10, 0, tzinfo=UTC),
        source_url=_R210_SIMULATOR_URL,
        state=state,
        binding_values=values,
        superseded_by_snapshot_id=superseded_by_snapshot_id,
        discarded_at=datetime(2026, 4, 4, 10, 0, tzinfo=UTC) if state is SnapshotLifecycleState.DISCARDED else None,
        discarded_by=discarded_by,
        discard_reason="refetched" if state is SnapshotLifecycleState.DISCARDED else "",
    )
    repository.save(snapshot)
    return snapshot.snapshot_id


def _command(
    *,
    borrador_snapshot_id: str | None,
    modelo: str = "100",
    bucket_id: str = _BUCKET_ID,
    caller_binding_values: dict[BindingId, Decimal] | None = None,
    caller_enum_binding_values: dict[BindingId, str] | None = None,
    filing_year: int = _YEAR,
    period: str = _PERIOD,
) -> Modelo100BorradorBindingCommand:
    typed_period = Period.from_year_and_code(filing_year, period)
    return Modelo100BorradorBindingCommand(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=typed_period,
        borrador_snapshot_id=borrador_snapshot_id,
        caller_binding_values=caller_binding_values or {},
        caller_enum_binding_values=caller_enum_binding_values or {},
    )


def test_borrador_binding_command_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        Modelo100BorradorBindingCommand.model_validate(
            {
                "bucket_id": _BUCKET_ID,
                "modelo": "100",
                "filing_year": _YEAR,
                "period": {"filing_year": _YEAR, "code": _PERIOD},
                "borrador_snapshot_id": None,
                "unknown": "field",
            },
        )


def test_borrador_binding_command_rejects_bare_period_string() -> None:
    with pytest.raises(ValidationError):
        Modelo100BorradorBindingCommand.model_validate(
            {
                "bucket_id": _BUCKET_ID,
                "modelo": "100",
                "filing_year": _YEAR,
                "period": _PERIOD,
                "borrador_snapshot_id": None,
            },
        )


def test_borrador_binding_command_carries_structured_period() -> None:
    command = _command(borrador_snapshot_id=None)

    assert command.period == Period.from_year_and_code(_YEAR, _PERIOD)
    assert command.model_dump(mode="json")["period"] == {"filing_year": _YEAR, "code": _PERIOD}


def test_borrador_binding_command_rejects_noncanonical_caller_binding_keys() -> None:
    with pytest.raises(ValidationError) as decimal_exc:
        _command(borrador_snapshot_id="snap-1", caller_binding_values={"Bad Binding": Decimal("1")})
    assert decimal_exc.value.errors()[0]["loc"][0] == "caller_binding_values"

    with pytest.raises(ValidationError) as enum_exc:
        _command(borrador_snapshot_id="snap-1", caller_enum_binding_values={"Bad Binding": "madrid"})
    assert enum_exc.value.errors()[0]["loc"][0] == "caller_enum_binding_values"

    with pytest.raises(ValidationError) as blank_exc:
        _command(borrador_snapshot_id="snap-1", caller_binding_values={" ": Decimal("1")})
    assert blank_exc.value.errors()[0]["loc"][0] == "caller_binding_values"


def test_borrador_resolution_is_inert_without_named_snapshot(
    snapshot_repository: Borrador100SnapshotRepository,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    result = resolve_modelo_100_borrador_bindings(
        _command(borrador_snapshot_id=None),
        registry_snapshot=_modelo_100_registry_snapshot(),
        snapshot_repository=snapshot_repository,
        operation=authority_operation,
    )

    assert result.borrador_provenance is None
    assert result.binding_values == {}
    assert result.enum_binding_values == {}


def test_committed_modelo_100_registry_declares_borrador_prefilled_bindings() -> None:
    bindings = {binding.id: binding for binding in _modelo_100_registry_snapshot().revision.bindings}

    assert bindings[_DECIMAL_BINDING].aeat_prefilled is True
    assert bindings[_ENUM_BINDING].aeat_prefilled is True


def test_borrador_resolution_rejects_registry_without_borrador_capability(
    snapshot_repository: Borrador100SnapshotRepository,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    registry_snapshot = compiled_bundled_authority().snapshot("303", filing_year=2026, period="2T")

    with pytest.raises(Modelo100BorradorBindingError) as exc_info:
        resolve_modelo_100_borrador_bindings(
            _command(
                borrador_snapshot_id="snapshot-does-not-need-loading",
                modelo="303",
                filing_year=2026,
                period="2T",
            ),
            registry_snapshot=registry_snapshot,
            snapshot_repository=snapshot_repository,
            operation=authority_operation,
        )

    assert exc_info.value.translated_message == "application.modelo.borrador_binding.errors.unsupported_modelo"
    assert exc_info.value.context == {"modelo": "303"}


def test_borrador_resolution_consumes_only_registry_prefilled_bindings(
    snapshot_repository: Borrador100SnapshotRepository,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    snapshot_id = _save_snapshot(
        snapshot_repository,
        {
            _DECIMAL_BINDING: Decimal("125.50"),
            _ENUM_BINDING: "madrid",
        },
    )

    result = resolve_modelo_100_borrador_bindings(
        _command(borrador_snapshot_id=snapshot_id),
        registry_snapshot=_modelo_100_registry_snapshot(),
        snapshot_repository=snapshot_repository,
        operation=authority_operation,
    )

    assert result.borrador_provenance is not None
    assert result.borrador_provenance.snapshot_id == snapshot_id
    assert result.binding_values == {_DECIMAL_BINDING: Decimal("125.50")}
    assert result.enum_binding_values == {_ENUM_BINDING: "madrid"}
    assert result.borrador_provenance.bindings_sourced == (_DECIMAL_BINDING, _ENUM_BINDING)


def test_borrador_source_resolver_matches_application_binding_resolution(
    snapshot_repository: Borrador100SnapshotRepository,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    snapshot_id = _save_snapshot(
        snapshot_repository,
        {
            _DECIMAL_BINDING: Decimal("125.50"),
            _ENUM_BINDING: "madrid",
        },
    )
    registry_snapshot = _modelo_100_registry_snapshot()
    expected = resolve_modelo_100_borrador_bindings(
        _command(borrador_snapshot_id=snapshot_id),
        registry_snapshot=registry_snapshot,
        snapshot_repository=snapshot_repository,
        operation=authority_operation,
    )

    resolution = Modelo100BorradorSourceResolver(
        borrador_snapshot_id=snapshot_id,
        caller_binding_values={},
        caller_enum_binding_values={},
        registry_snapshot=registry_snapshot,
        snapshot_repository=snapshot_repository,
        operation=authority_operation,
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, _PERIOD),
            revision=registry_snapshot.revision,
        ),
    )

    assert resolution.binding_values == expected.binding_values
    assert resolution.enum_binding_values == expected.enum_binding_values
    assert resolution.owned_sources == (BindingSourceKind.BORRADOR,)
    assert {item.contributor_source_kind for item in resolution.provenance} == {"borrador"}
    assert {item.source_ref for item in resolution.provenance} == {
        f"borrador:{snapshot_id}:binding:{_DECIMAL_BINDING}",
        f"borrador:{snapshot_id}:binding:{_ENUM_BINDING}",
    }
    expected_fingerprint = f"sha256:{hashlib.sha256(snapshot_id.encode('utf-8')).hexdigest()}"
    assert {item.fingerprint for item in resolution.provenance} == {expected_fingerprint}


def test_borrador_binding_error_has_stable_service_error_code() -> None:
    code = get_registered_error_code(Modelo100BorradorBindingError)

    assert code.code == "REFUSED_MODELO_100_BORRADOR_BINDING"
    assert code.category is ErrorCategory.REFUSED
    assert code.message_key == "errors.refused.refused_modelo_100_borrador_binding"


def test_borrador_snapshot_id_participates_in_calculation_revision_identity() -> None:
    first = derive_calculation_revision_id(
        work_unit_id="1" * 64,
        input_values_by_casilla_id={},
        binding_overrides={_DECIMAL_BINDING: "125.50"},
        casilla_values={_BORRADOR_IDENTITY_CASILLA: Decimal("125.50")},
        borrador_snapshot_id="borrador-one",
        bindings_sourced_from_borrador=(_DECIMAL_BINDING,),
        filing_instance_evidence=None,
        source_provenance=(),
    )
    second = derive_calculation_revision_id(
        work_unit_id="1" * 64,
        input_values_by_casilla_id={},
        binding_overrides={_DECIMAL_BINDING: "125.50"},
        casilla_values={_BORRADOR_IDENTITY_CASILLA: Decimal("125.50")},
        borrador_snapshot_id="borrador-two",
        bindings_sourced_from_borrador=(_DECIMAL_BINDING,),
        filing_instance_evidence=None,
        source_provenance=(),
    )

    assert first != second


def test_borrador_resolution_leaves_explicit_caller_binding_in_control(
    snapshot_repository: Borrador100SnapshotRepository,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    snapshot_id = _save_snapshot(
        snapshot_repository,
        {
            _DECIMAL_BINDING: Decimal("1"),
            _ENUM_BINDING: "madrid",
        },
    )

    result = resolve_modelo_100_borrador_bindings(
        _command(
            borrador_snapshot_id=snapshot_id,
            caller_binding_values={_DECIMAL_BINDING: Decimal("0")},
            caller_enum_binding_values={_ENUM_BINDING: "cataluna"},
        ),
        registry_snapshot=_modelo_100_registry_snapshot(),
        snapshot_repository=snapshot_repository,
        operation=authority_operation,
    )

    assert result.binding_values == {}
    assert result.enum_binding_values == {}
    assert result.borrador_provenance is not None
    assert result.borrador_provenance.bindings_sourced == ()


def test_borrador_resolution_rejects_registry_unmarked_binding_values(
    snapshot_repository: Borrador100SnapshotRepository,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    snapshot_id = _save_snapshot(snapshot_repository, {_UNMARKED_BINDING: Decimal("1")})

    with pytest.raises(Modelo100BorradorBindingError) as exc_info:
        resolve_modelo_100_borrador_bindings(
            _command(borrador_snapshot_id=snapshot_id),
            registry_snapshot=_modelo_100_registry_snapshot(),
            snapshot_repository=snapshot_repository,
            operation=authority_operation,
        )

    assert exc_info.value.translated_message == "application.modelo.borrador_binding.errors.forbidden_bindings"
    assert exc_info.value.context == {"bindings": [_UNMARKED_BINDING]}


def test_borrador_resolution_rejects_non_decimal_value_for_numeric_binding(
    snapshot_repository: Borrador100SnapshotRepository,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    snapshot_id = _save_snapshot(snapshot_repository, {_DECIMAL_BINDING: "not-a-decimal"})

    with pytest.raises(Modelo100BorradorBindingError) as exc_info:
        resolve_modelo_100_borrador_bindings(
            _command(borrador_snapshot_id=snapshot_id),
            registry_snapshot=_modelo_100_registry_snapshot(),
            snapshot_repository=snapshot_repository,
            operation=authority_operation,
        )

    assert exc_info.value.translated_message == "application.modelo.borrador_binding.errors.decimal_value_invalid"
    assert exc_info.value.context == {"binding_id": _DECIMAL_BINDING}


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("125.50", Decimal("125.50")),
        (Decimal("125.50"), Decimal("125.50")),
    ],
)
def test_borrador_resolution_accepts_finite_string_and_decimal_values(
    raw_value: Decimal | str,
    expected: Decimal,
) -> None:
    assert _decimal_value(_DECIMAL_BINDING, raw_value) == expected


@pytest.mark.parametrize(
    "raw_value",
    [
        "NaN",
        "Infinity",
        "-Infinity",
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_borrador_resolution_rejects_non_finite_string_and_decimal_values(
    raw_value: Decimal | str,
) -> None:
    with pytest.raises(Modelo100BorradorBindingError) as exc_info:
        _decimal_value(_DECIMAL_BINDING, raw_value)

    assert exc_info.value.translated_message == "application.modelo.borrador_binding.errors.decimal_value_invalid"
    assert exc_info.value.context == {"binding_id": _DECIMAL_BINDING}


def test_borrador_resolution_rejects_missing_snapshot_with_live_list_pointer(
    snapshot_repository: Borrador100SnapshotRepository,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with pytest.raises(Modelo100BorradorBindingError) as exc_info:
        resolve_modelo_100_borrador_bindings(
            _command(borrador_snapshot_id="missing-snapshot"),
            registry_snapshot=_modelo_100_registry_snapshot(),
            snapshot_repository=snapshot_repository,
            operation=authority_operation,
        )

    assert exc_info.value.translated_message == "application.modelo.borrador_binding.errors.snapshot_load_failed"
    assert exc_info.value.context == {"borrador_snapshot_id": "missing-snapshot"}
    failure = exc_info.value.precondition_failure
    assert failure is not None
    assert failure.scenario_id == "modelo.work.calculate.borrador_snapshot.load_failed"


def test_borrador_resolution_rejects_non_modelo_100_consumers(
    snapshot_repository: Borrador100SnapshotRepository,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with pytest.raises(Modelo100BorradorBindingError) as exc_info:
        resolve_modelo_100_borrador_bindings(
            _command(borrador_snapshot_id="snapshot-does-not-need-loading", modelo="303"),
            registry_snapshot=_modelo_100_registry_snapshot(),
            snapshot_repository=snapshot_repository,
            operation=authority_operation,
        )

    assert (
        exc_info.value.translated_message
        == "application.modelo.borrador_binding.errors.registry_snapshot_modelo_mismatch"
    )
    assert exc_info.value.context == {"snapshot_modelo": "100", "command_modelo": "303"}


def test_borrador_resolution_rejects_registry_snapshot_axis_mismatch(
    snapshot_repository: Borrador100SnapshotRepository,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with pytest.raises(Modelo100BorradorBindingError) as exc_info:
        resolve_modelo_100_borrador_bindings(
            _command(borrador_snapshot_id="snapshot-does-not-need-loading", filing_year=2024),
            registry_snapshot=_modelo_100_registry_snapshot(),
            snapshot_repository=snapshot_repository,
            operation=authority_operation,
        )

    assert (
        exc_info.value.translated_message
        == "application.modelo.borrador_binding.errors.registry_snapshot_axis_mismatch"
    )
    assert exc_info.value.context == {
        "snapshot_year": _YEAR,
        "snapshot_period": _PERIOD,
        "filing_year": 2024,
        "period": _PERIOD,
    }


def test_borrador_resolution_rejects_superseded_snapshot_with_list_pointer(
    snapshot_repository: Borrador100SnapshotRepository,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    snapshot_id = _save_snapshot(
        snapshot_repository,
        {_DECIMAL_BINDING: Decimal("1")},
        state=SnapshotLifecycleState.SUPERSEDED,
        superseded_by_snapshot_id="b" * 64,
    )

    with pytest.raises(Modelo100BorradorBindingError) as exc_info:
        resolve_modelo_100_borrador_bindings(
            _command(borrador_snapshot_id=snapshot_id),
            registry_snapshot=_modelo_100_registry_snapshot(),
            snapshot_repository=snapshot_repository,
            operation=authority_operation,
        )

    failure = exc_info.value.precondition_failure
    assert failure is not None
    assert failure.scenario_id == "modelo.work.calculate.borrador_snapshot.inactive"


def test_borrador_resolution_rejects_discarded_snapshot_with_list_pointer(
    snapshot_repository: Borrador100SnapshotRepository,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    snapshot_id = _save_snapshot(
        snapshot_repository,
        {_DECIMAL_BINDING: Decimal("1")},
        state=SnapshotLifecycleState.DISCARDED,
        discarded_by="operator",
    )

    with pytest.raises(Modelo100BorradorBindingError) as exc_info:
        resolve_modelo_100_borrador_bindings(
            _command(borrador_snapshot_id=snapshot_id),
            registry_snapshot=_modelo_100_registry_snapshot(),
            snapshot_repository=snapshot_repository,
            operation=authority_operation,
        )

    failure = exc_info.value.precondition_failure
    assert failure is not None
    assert failure.scenario_id == "modelo.work.calculate.borrador_snapshot.inactive"


def test_borrador_resolution_rejects_bucket_or_axis_mismatch(
    snapshot_repository: Borrador100SnapshotRepository,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    snapshot_id = _save_snapshot(snapshot_repository, {_DECIMAL_BINDING: Decimal("1")})

    with pytest.raises(Modelo100BorradorBindingError) as exc_info:
        resolve_modelo_100_borrador_bindings(
            _command(borrador_snapshot_id=snapshot_id, bucket_id="other-bucket"),
            registry_snapshot=_modelo_100_registry_snapshot(),
            snapshot_repository=snapshot_repository,
            operation=authority_operation,
        )

    assert exc_info.value.translated_message == "application.modelo.borrador_binding.errors.snapshot_bucket_mismatch"
    assert exc_info.value.context is None
