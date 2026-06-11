"""Filed-declaration observation and registry interpretation helpers.

Use of :class:`CasillaObservation`, :class:`ModeloRevision`, :class:`RegistrySnapshot`,
and :class:`ValidatedRegistryAuthority` for compliance.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl

from .....core import Modelo, Period
from .....core.config import Settings
from .....core.external_constants import JSON_MIME_TYPE as _JSON_MIME_TYPE
from .....core.i18n import tr
from .....core.resources import bundled_path
from .....core.time import now
from .....domain.calculations.registry import (
    CasillaFieldKind,
    CasillaObservation,
    ExportFieldDefinition,
    ParsedExportFieldValue,
    RegistryModeloObservation,
    RegistrySnapshot,
    RegistrySnapshotError,
    RegistryValidationError,
    RemoteStateGuardPolicy,
    parse_export_payload,
    remote_state_policy_from_cross_reference,
    resolve_export_layout,
    resolve_previous_filing_binding_values,
    resolve_relation_values_from_observations,
)
from .....domain.iva_compensation._carry_forward import derive_303_compensation_available
from ....inbound.declaracion import DeclaracionParseError, parse_declaracion, parse_declaracion_bytes
from ._browser_constants import SEDE_BODY_ENCODING as _SEDE_BODY_ENCODING
from ._declarations_schema import Declaracion
from ._errors import SedeParseError
from ._schema import FiledDeclaracionArtefact, FiledDeclaracionObservation, ObservedCasillaValue

if TYPE_CHECKING:
    from .....domain.calculations.registry import ModeloRevision, ValidatedRegistryAuthority

__all__ = [
    "FiledDeclaracionArtefactSink",
    "_is_modelo_303_page_03_fallback",
    "_observed_casillas_from_declaration_pdf",
    "_observed_casillas_from_submitted_file",
    "_read_guard_policy_from_snapshot",
    "_register_row_artefact",
    "_registry_snapshot_for_declaration",
    "_store_artefact",
    "_submitted_file_coverage_for_casillas",
    "_submitted_file_extraction_coverage",
    "_temporary_sensitive_pdf_path",
    "_verify_submitted_file_context",
    "_with_derived_303_compensation_available_observation",
    "registry_observation_from_filed_declaration",
    "resolve_previous_filing_bindings_from_filed_declarations",
    "resolve_relation_values_from_filed_declarations",
]

_EXTERNAL = Settings.external_constants()
_SEDE_BASE = _EXTERNAL.aeat.domains.www6
_LISTING_URL = f"{_SEDE_BASE}{_EXTERNAL.aeat.sede_paths.declarations_listing}"

type FiledDeclaracionArtefactSink = Callable[
    [tuple[str, int, Period, str], FiledDeclaracionArtefact, bytes],
    FiledDeclaracionArtefact,
]


def _register_row_artefact(
    declaration: Declaracion,
    *,
    source_url: AnyHttpUrl,
) -> tuple[FiledDeclaracionArtefact, bytes]:
    payload = json.dumps(
        declaration.model_dump(mode="json"),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    captured_at = now()
    return (
        FiledDeclaracionArtefact(
            kind="register_row",
            source_url=source_url,
            content_type=_JSON_MIME_TYPE,
            byte_count=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            captured_at=captured_at,
        ),
        payload,
    )


def _store_artefact(
    artefact_sink: FiledDeclaracionArtefactSink | None,
    *,
    observation_key: tuple[str, int, str, str],
    artefact: FiledDeclaracionArtefact,
    body: bytes,
) -> FiledDeclaracionArtefact:
    if artefact_sink is None:
        return artefact
    return artefact_sink(observation_key, artefact, body)


def _registry_snapshot_for_declaration(declaration: Declaracion) -> RegistrySnapshot:
    authority = _registry_authority()
    try:
        return authority.snapshot(
            declaration.modelo,
            filing_year=declaration.ejercicio,
            period=declaration.period,
        )
    except RegistrySnapshotError as exc:
        raise SedeParseError(f"registry has no snapshot for AEAT declaration {declaration.modelo!r}") from exc


def _registry_authority() -> ValidatedRegistryAuthority:
    from .....domain.calculations.registry import ValidatedRegistryAuthority

    return ValidatedRegistryAuthority.load(bundled_path("registry", "aeat"), source_root=bundled_path())


def _read_guard_policy_from_snapshot(snapshot: RegistrySnapshot) -> RemoteStateGuardPolicy:
    listing_host = urlsplit(_LISTING_URL).hostname
    if listing_host is None:
        raise RegistryValidationError(f"invalid declarations listing URL: {_LISTING_URL!r}")
    matching_decisions = tuple(
        decision
        for decision in snapshot.live_cross_references.values()
        if decision.surface == "authenticated_read_surface"
        and listing_host.lower() in {host.lower() for host in decision.allowed_hosts}
    )
    if len(matching_decisions) != 1:
        decision_ids = ", ".join(sorted(decision.id for decision in matching_decisions)) or "none"
        raise RegistryValidationError(
            f"expected exactly one authenticated declarations read surface for modelo "
            f"{snapshot.modelo.id} revision {snapshot.revision.id}; found {decision_ids}",
        )
    return remote_state_policy_from_cross_reference(matching_decisions[0]).model_copy(
        update={"allowed_browser_action_patterns": _EXTERNAL.aeat.live_safety.declarations_browser_action_patterns},
    )


def _observed_casillas_from_submitted_file(
    *,
    snapshot: RegistrySnapshot,
    declaration: Declaracion,
    body: bytes,
    artefact: FiledDeclaracionArtefact,
) -> tuple[ObservedCasillaValue, ...]:
    try:
        resolved = resolve_export_layout(snapshot)
    except RegistryValidationError as exc:
        if snapshot.modelo.id == Modelo.M303 and "has no exports" in str(exc):
            return _observed_modelo_303_casillas_from_submitted_file(declaration=declaration, body=body)
        raise
    try:
        parsed = parse_export_payload(
            resolved.layout,
            body,
            source_root=bundled_path(),
            sources=snapshot.sources,
        )
    except RegistryValidationError:
        if snapshot.modelo.id == Modelo.M303:
            return _observed_modelo_303_casillas_from_submitted_file(declaration=declaration, body=body)
        raise
    _verify_submitted_file_context(resolved.fields_by_id, parsed.fields, declaration=declaration)
    observations: list[ObservedCasillaValue] = []
    for casilla in parsed.casillas:
        if casilla.casilla_id is None or casilla.value is None:
            continue
        observations.append(
            ObservedCasillaValue(
                casilla_id=casilla.casilla_id,
                value=str(casilla.value),
                source_artefact_kind="submitted_file",
                source_locator=casilla.source_locator,
                confidence=1.0,
            ),
        )
    if not observations:
        raise SedeParseError(f"submitted-file artefact {artefact.sha256[:16]} did not yield casilla observations")
    return tuple(observations)


def _is_modelo_303_page_03_fallback(casillas: tuple[ObservedCasillaValue, ...]) -> bool:
    return bool(casillas) and all(casilla.source_locator.startswith("record:T30303:pos:") for casilla in casillas)


def _submitted_file_extraction_coverage(
    *,
    parsed_field_ids: frozenset[str],
    observed_casillas: frozenset[str],
    fields_by_casilla: Mapping[str, tuple[ExportFieldDefinition, ...]],
) -> float:
    expected = {
        casilla_id
        for casilla_id, fields in fields_by_casilla.items()
        if any(field.id in parsed_field_ids for field in fields)
    }
    return len(observed_casillas.intersection(expected)) / len(expected) if expected else 0.0


def _submitted_file_coverage_for_casillas(
    *,
    snapshot: RegistrySnapshot,
    body: bytes,
    casillas: tuple[ObservedCasillaValue, ...],
) -> float:
    """Compute the submitted-file extraction coverage for observed ``casillas``.

    Resolves the export layout for the snapshot and derives the fraction of
    registry-expected casillas that the parsed submitted file actually yielded.
    Mirrors the inline derivation that previously lived in the live capture
    routine: a Modelo 303 snapshot without exports, an ``xml_dictionary`` layout,
    and a Modelo 303 page-03 fallback are each treated as fully covered (1.0);
    otherwise the parsed export fields are scored against the resolved layout's
    ``fields_by_casilla`` map. Raises :class:`RegistryValidationError` for any
    layout-resolution failure other than the Modelo 303 "no exports" case.
    """
    try:
        resolved_layout = resolve_export_layout(snapshot)
    except RegistryValidationError as exc:
        if snapshot.modelo.id == Modelo.M303 and "has no exports" in str(exc):
            return 1.0
        raise
    if resolved_layout.layout.format == "xml_dictionary" or _is_modelo_303_page_03_fallback(casillas):
        return 1.0
    parsed = parse_export_payload(
        resolved_layout.layout,
        body,
        source_root=bundled_path(),
        sources=snapshot.sources,
    )
    return _submitted_file_extraction_coverage(
        parsed_field_ids=frozenset(field.field_id for field in parsed.fields),
        observed_casillas=frozenset(casilla.casilla_id for casilla in casillas),
        fields_by_casilla=resolved_layout.fields_by_casilla,
    )


_MODELO_303_PAGE_03_TAG = "<T30303000>"
_MODELO_303_PAGE_03_END_TAG = "</T30303000>"
_MODELO_303_PAGE_03_MONEY_FIELDS: Final[Mapping[str, tuple[int, int]]] = {
    "110": (255, 17),
    "78": (272, 17),
    "87": (289, 17),
    "69": (323, 17),
    "71": (374, 17),
}
_MODELO_303_PAGE_03_MONEY_FIELDS_BY_YEAR: Final[Mapping[int, Mapping[str, tuple[int, int]]]] = {
    2022: {
        "110": (255, 17),
        "78": (272, 17),
        "87": (289, 17),
        "69": (323, 17),
        "71": (357, 17),
    },
}


def _observed_modelo_303_casillas_from_submitted_file(
    *,
    declaration: Declaracion,
    body: bytes,
) -> tuple[ObservedCasillaValue, ...]:
    """Parse official Modelo 303 page-03 fixed-width result fields."""
    text = body.decode(_SEDE_BODY_ENCODING, errors="replace")
    page_start = text.find(_MODELO_303_PAGE_03_TAG)
    if page_start < 0:
        raise SedeParseError(f"submitted Modelo 303 file for {declaration.expediente_id!r} has no page-03 record")
    page_end = text.find(_MODELO_303_PAGE_03_END_TAG, page_start + len(_MODELO_303_PAGE_03_TAG))
    if page_end < 0:
        raise SedeParseError(f"submitted Modelo 303 file for {declaration.expediente_id!r} has invalid page-03 footer")
    page = text[page_start : page_end + len(_MODELO_303_PAGE_03_END_TAG)]
    if not page.startswith(_MODELO_303_PAGE_03_TAG):
        raise SedeParseError(f"submitted Modelo 303 file for {declaration.expediente_id!r} has invalid page-03 header")
    observations: list[ObservedCasillaValue] = []
    money_fields = _MODELO_303_PAGE_03_MONEY_FIELDS_BY_YEAR.get(
        declaration.ejercicio,
        _MODELO_303_PAGE_03_MONEY_FIELDS,
    )
    for casilla_id, (position, width) in money_fields.items():
        raw = page[position - 1 : position - 1 + width]
        if len(raw) != width:
            raise SedeParseError(
                f"submitted Modelo 303 file for {declaration.expediente_id!r} has truncated casilla {casilla_id}",
            )
        value = _parse_modelo_303_money(raw, casilla_id=casilla_id)
        observations.append(
            ObservedCasillaValue(
                casilla_id=casilla_id,
                value=str(value),
                source_artefact_kind="submitted_file",
                source_locator=f"record:T30303:pos:{position}:width:{width}",
                confidence=1.0,
            ),
        )
    return tuple(observations)


def _parse_modelo_303_money(raw: str, *, casilla_id: str) -> Decimal:
    """Parse AEAT fixed-width 15+2 money, with leading ``N`` for negatives."""
    value = raw.strip()
    if not value:
        return Decimal("0.00")
    sign = Decimal("-1") if value.startswith("N") else Decimal("1")
    digits = value[1:] if value.startswith("N") else value
    if not digits.isdigit():
        raise SedeParseError(f"submitted Modelo 303 casilla {casilla_id} is not numeric: {raw!r}")
    return sign * (Decimal(digits) / Decimal("100"))


def _write_all_fd(fd: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        write_failed = False
        try:
            written = os.write(fd, remaining)
        except OSError:
            write_failed = True
            written = 0
        if write_failed:
            raise SedeParseError(
                "failed to write declaration PDF parser scratch file",
                context={"operation": "declaration_pdf_scratch_write"},
                translated_message=tr("adapters.sede.errors.parse_failed"),
            )
        if written == 0:
            raise SedeParseError(
                "declaration PDF parser scratch write made no progress",
                translated_message=tr("adapters.sede.errors.parse_failed"),
            )
        remaining = remaining[written:]


@contextmanager
def _temporary_sensitive_pdf_path(body: bytes) -> Iterator[Path]:
    create_failed = False
    try:
        fd, tmp_path_str = tempfile.mkstemp(prefix="aeat-declaration-pdf-", suffix=".pdf")
    except OSError:
        create_failed = True
        fd = -1
        tmp_path_str = ""
    if create_failed:
        raise SedeParseError(
            "failed to create declaration PDF parser scratch file",
            context={"operation": "declaration_pdf_scratch_create"},
            translated_message=tr("adapters.sede.errors.parse_failed"),
        )
    tmp_path = Path(tmp_path_str)
    try:
        try:
            _write_all_fd(fd, body)
        finally:
            close_failed = False
            try:
                os.close(fd)
            except OSError:
                close_failed = True
            if close_failed:
                raise SedeParseError(
                    "failed to close declaration PDF parser scratch file",
                    context={"operation": "declaration_pdf_scratch_close"},
                    translated_message=tr("adapters.sede.errors.parse_failed"),
                )
        yield tmp_path
    finally:
        unlink_failed = False
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            unlink_failed = True
        if unlink_failed:
            raise SedeParseError(
                "failed to remove declaration PDF parser scratch file",
                context={"operation": "declaration_pdf_scratch_unlink"},
                translated_message=tr("adapters.sede.errors.parse_failed"),
            )


def _observed_casillas_from_declaration_pdf(
    *,
    snapshot: RegistrySnapshot,
    declaration: Declaracion,
    body: bytes,
) -> tuple[ObservedCasillaValue, ...]:
    needs_word_positions = any(
        any(target.match_strategy == "bbox_anchored" for target in profile.target_casillas)
        for profile in snapshot.extraction_profiles.values()
        if profile.surface == "declaracion_pdf"
    )
    parse_failed = False
    try:
        if needs_word_positions:
            with _temporary_sensitive_pdf_path(body) as tmp_path:
                filing = parse_declaracion(
                    tmp_path,
                    modelo_override=declaration.modelo,
                    año_override=declaration.ejercicio,
                    period_override=declaration.period,
                    registry_snapshot=snapshot,
                )
        else:
            filing = parse_declaracion_bytes(
                body,
                source_label="secure declaration PDF",
                modelo_override=declaration.modelo,
                año_override=declaration.ejercicio,
                period_override=declaration.period,
                registry_snapshot=snapshot,
            )
    except DeclaracionParseError:
        parse_failed = True
        filing = None
    if parse_failed:
        raise SedeParseError(
            "declaration PDF did not yield registry casilla observations",
            context={
                "operation": "declaration_pdf_parse",
                "modelo": declaration.modelo,
                "ejercicio": str(declaration.ejercicio),
                "period": declaration.period,
            },
            translated_message=tr("adapters.sede.errors.parse_failed"),
        )

    assert filing is not None  # parse_failed branch raises; filing is set in the try block
    observations: list[ObservedCasillaValue] = []
    for casilla in filing.values:
        if casilla.printed_value is None:
            continue
        observations.append(
            ObservedCasillaValue(
                casilla_id=casilla.casilla_id,
                value=str(casilla.printed_value),
                source_artefact_kind="declaration_pdf",
                source_locator=f"page:{casilla.source_page}:casilla:{casilla.casilla_id}",
                confidence=casilla.extraction_confidence,
            ),
        )
    if not observations:
        raise SedeParseError(
            "declaration PDF did not yield casilla observations",
            context={
                "operation": "declaration_pdf_extract_observations",
                "modelo": declaration.modelo,
                "ejercicio": str(declaration.ejercicio),
                "period": declaration.period,
            },
            translated_message=tr("adapters.sede.errors.parse_failed"),
        )
    return tuple(observations)


def _verify_submitted_file_context(
    fields_by_id: Mapping[str, ExportFieldDefinition],
    parsed_fields: tuple[ParsedExportFieldValue, ...],
    *,
    declaration: Declaracion,
) -> None:
    expected = {
        "modelo": declaration.modelo,
        "filing_year": str(declaration.ejercicio),
        "period_code": declaration.period,
    }
    for parsed in parsed_fields:
        field = fields_by_id.get(parsed.field_id)
        if field is None or field.kind != CasillaFieldKind.DRAFT or field.draft_attribute not in expected:
            continue
        observed = "" if parsed.value is None else str(parsed.value)
        if observed != expected[field.draft_attribute]:
            raise SedeParseError(
                f"submitted-file field {parsed.field_id!r} does not match declaration {declaration.expediente_id!r}",
            )


def registry_observation_from_filed_declaration(
    observation: FiledDeclaracionObservation,
) -> RegistryModeloObservation:
    """Convert a filed-declaration observation into a :class:`RegistryModeloObservation`."""
    period_token = observation.period.registry_token
    if not observation.extraction_coverage:
        raise SedeParseError(
            f"filed declaration {observation.modelo!r}/{observation.ejercicio}/{period_token!r} "
            "has no extraction coverage",
        )
    incomplete = {
        artefact_kind: coverage for artefact_kind, coverage in observation.extraction_coverage.items() if coverage < 1.0
    }
    if incomplete:
        raise SedeParseError(
            f"filed declaration {observation.modelo!r}/{observation.ejercicio}/{period_token!r} "
            "has incomplete extraction coverage",
        )
    casilla_values: dict[str, Decimal] = {}
    for casilla in observation.casillas:
        if casilla.source_artefact_kind == "justificante_pdf":
            raise SedeParseError("justificante metadata cannot populate registry casilla values")
        try:
            value = Decimal(casilla.value)
        except InvalidOperation as exc:
            raise SedeParseError(f"observed casilla {casilla.casilla_id!r} is not decimal-valued") from exc
        previous = casilla_values.get(casilla.casilla_id)
        if previous is not None and previous != value:
            raise SedeParseError(f"observed casilla {casilla.casilla_id!r} has contradictory values")
        casilla_values[casilla.casilla_id] = value
    if not casilla_values:
        raise SedeParseError(
            f"filed declaration {observation.modelo!r}/{observation.ejercicio}/{period_token!r} "
            "has no registry casilla observations",
        )
    return RegistryModeloObservation(
        modelo=observation.modelo,
        filing_year=observation.ejercicio,
        period=period_token,
        observations=tuple(CasillaObservation(casilla_id=cid, value=val) for cid, val in casilla_values.items()),
    )


def _with_derived_303_compensation_available_observation(
    observation: FiledDeclaracionObservation,
) -> FiledDeclaracionObservation:
    """Add Modelo 303 carry-forward availability derived from filed casillas 87 and 69."""
    target_id = "iva.compensacion-disponible-fin-periodo"
    if observation.modelo != Modelo.M303 or any(casilla.casilla_id == target_id for casilla in observation.casillas):
        return observation
    values: dict[str, Decimal] = {}
    for casilla in observation.casillas:
        if (
            casilla.casilla_id
            not in {
                "87",
                "69",
                "iva.compensacion-pendiente-periodos-posteriores",
                "iva.resultado",
            }
            or casilla.source_artefact_kind == "justificante_pdf"
        ):
            continue
        try:
            values[casilla.casilla_id] = Decimal(casilla.value)
        except InvalidOperation as exc:
            raise SedeParseError(f"observed casilla {casilla.casilla_id!r} is not decimal-valued") from exc
    posterior = _observed_decimal(
        values,
        "87",
        "iva.compensacion-pendiente-periodos-posteriores",
    )
    resultado = _observed_decimal(values, "69", "iva.resultado")
    if posterior is None or resultado is None:
        return observation
    available = derive_303_compensation_available(posterior=posterior, resultado=resultado)
    derived = ObservedCasillaValue(
        casilla_id=target_id,
        value=str(available),
        source_artefact_kind="derived_registry_formula",
        source_locator="formula:87+max(0,-69)",
        confidence=1.0,
    )
    return observation.model_copy(update={"casillas": (*observation.casillas, derived)})


def _observed_decimal(values: dict[str, Decimal], *casilla_ids: str) -> Decimal | None:
    for casilla_id in casilla_ids:
        value = values.get(casilla_id)
        if value is not None:
            return value
    return None


def resolve_previous_filing_bindings_from_filed_declarations(
    revision: ModeloRevision,
    observations: tuple[FiledDeclaracionObservation, ...],
    *,
    filing_year: int,
    period: Period,
) -> dict[str, Decimal]:
    """Resolve registry previous-filing bindings from filed AEAT observations.

    Use of :class:`ModeloRevision` for compliance.
    """
    return resolve_previous_filing_binding_values(
        revision,
        (registry_observation_from_filed_declaration(observation) for observation in observations),
        filing_year=filing_year,
        period=period.registry_token,
    )


def resolve_relation_values_from_filed_declarations(
    revision: ModeloRevision,
    observations: tuple[FiledDeclaracionObservation, ...],
    *,
    filing_year: int,
    period: Period,
) -> dict[str, Decimal]:
    """Resolve registry cross-model relation values from filed AEAT observations.

    Use of :class:`ModeloRevision` for compliance.
    """
    return resolve_relation_values_from_observations(
        revision,
        (registry_observation_from_filed_declaration(observation) for observation in observations),
        filing_year=filing_year,
        period=period.registry_token,
    )
