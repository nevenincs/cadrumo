"""Filed-declaration observation and registry interpretation helpers.

Use of :class:`CasillaObservation`, :class:`ModeloRevision`, :class:`RegistrySnapshot`,
and :class:`ValidatedRegistryAuthority` for compliance.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl

from .....core import Modelo, Period
from .....core.config import Settings
from .....core.external_constants import JSON_MIME_TYPE as _JSON_MIME_TYPE
from .....core.hashing import sha256_hex
from .....core.i18n import tr
from .....core.resources import bundled_path, resources
from .....core.time import now
from .....domain.calculations.registry import (
    BindingId,
    CasillaFieldKind,
    CasillaId,
    CasillaObservation,
    ExportFieldDefinition,
    ParsedExportFieldValue,
    RegistryModeloObservation,
    RegistrySnapshot,
    RegistrySnapshotError,
    RegistryValidationError,
    RelationId,
    RemoteStateGuardPolicy,
    casillas_by_id,
    expression_casilla_refs,
    parse_export_payload,
    remote_state_policy_from_cross_reference,
    resolve_export_layout,
    resolve_previous_filing_binding_values,
    resolve_relation_values_from_observations,
    validated_casilla_id,
)
from .....domain.iva_compensation._carry_forward import derive_303_compensation_available
from ....inbound.declaracion import DeclaracionParseError, parse_declaracion_bytes
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
    "_verify_submitted_file_context",
    "_with_derived_303_compensation_available_observation",
    "registry_observation_from_filed_declaration",
    "resolve_previous_filing_bindings_from_filed_declarations",
    "resolve_relation_values_from_filed_declarations",
]

_EXTERNAL = Settings.external_constants()
_SEDE_BASE = _EXTERNAL.aeat.domains.www6


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="Sede declaration observation casilla constant")
    except ValueError as exc:
        raise RuntimeError(f"Sede declaration observation casilla constant {value!r} is not a CasillaId") from exc


_M303_DISPONIBLE_CASILLA: Final[CasillaId] = _casilla_id("iva.compensacion-disponible-fin-periodo")
_M303_POSTERIOR_CASILLA: Final[CasillaId] = _casilla_id("iva.compensacion-pendiente-periodos-posteriores")
_M303_RESULTADO_CASILLA: Final[CasillaId] = _casilla_id("iva.resultado")
_M303_GENERADA_CASILLA: Final[CasillaId] = _casilla_id("iva.compensacion-generada-periodo")
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
            sha256=sha256_hex(payload),
            captured_at=captured_at,
        ),
        payload,
    )


def _store_artefact(
    artefact_sink: FiledDeclaracionArtefactSink | None,
    *,
    observation_key: tuple[str, int, Period, str],
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
            period=declaration.period.registry_token,
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
            return _observed_modelo_303_casillas_from_submitted_file(
                snapshot=snapshot,
                declaration=declaration,
                body=body,
            )
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
            return _observed_modelo_303_casillas_from_submitted_file(
                snapshot=snapshot,
                declaration=declaration,
                body=body,
            )
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
    observed_casillas: frozenset[CasillaId],
    fields_by_casilla: Mapping[CasillaId, tuple[ExportFieldDefinition, ...]],
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
    "modelo-303-page-03-casilla-110": (255, 17),
    "modelo-303-page-03-casilla-78": (272, 17),
    "modelo-303-page-03-casilla-87": (289, 17),
    "modelo-303-page-03-casilla-69": (323, 17),
    "modelo-303-page-03-casilla-71": (374, 17),
}
_MODELO_303_PAGE_03_MONEY_FIELDS_BY_YEAR: Final[Mapping[int, Mapping[str, tuple[int, int]]]] = {
    2022: {
        "modelo-303-page-03-casilla-110": (255, 17),
        "modelo-303-page-03-casilla-78": (272, 17),
        "modelo-303-page-03-casilla-87": (289, 17),
        "modelo-303-page-03-casilla-69": (323, 17),
        "modelo-303-page-03-casilla-71": (357, 17),
    },
}


def _observed_modelo_303_casillas_from_submitted_file(
    *,
    snapshot: RegistrySnapshot,
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
    canonical_ids_by_export_ref = _modelo_303_page_03_casilla_ids(snapshot, tuple(money_fields))
    for export_ref, (position, width) in money_fields.items():
        raw = page[position - 1 : position - 1 + width]
        if len(raw) != width:
            raise SedeParseError(
                f"submitted Modelo 303 file for {declaration.expediente_id!r} has truncated field {export_ref}",
            )
        value = _parse_modelo_303_money(raw, field_ref=export_ref)
        observations.append(
            ObservedCasillaValue(
                casilla_id=canonical_ids_by_export_ref[export_ref],
                value=str(value),
                source_artefact_kind="submitted_file",
                source_locator=f"record:T30303:pos:{position}:width:{width}",
                confidence=1.0,
            ),
        )
    return tuple(observations)


def _modelo_303_page_03_casilla_ids(
    snapshot: RegistrySnapshot,
    export_refs: tuple[str, ...],
) -> dict[str, CasillaId]:
    casilla_ids_by_export_ref: dict[str, CasillaId] = {}
    for export_ref in export_refs:
        owners = tuple(casilla.id for casilla in snapshot.revision.casillas if export_ref in casilla.export_refs)
        if len(owners) != 1:
            raise SedeParseError(
                f"Modelo 303 page-03 export reference {export_ref!r} resolves to {len(owners)} casillas "
                f"for revision {snapshot.revision.id}; expected exactly one canonical casilla.id",
            )
        casilla_ids_by_export_ref[export_ref] = owners[0]
    return casilla_ids_by_export_ref


def _parse_modelo_303_money(raw: str, *, field_ref: str) -> Decimal:
    """Parse AEAT fixed-width 15+2 money, with leading ``N`` for negatives."""
    value = raw.strip()
    if not value:
        return Decimal("0.00")
    sign = Decimal("-1") if value.startswith("N") else Decimal("1")
    digits = value[1:] if value.startswith("N") else value
    if not digits.isdigit():
        raise SedeParseError(f"submitted Modelo 303 field {field_ref} is not numeric: {raw!r}")
    return sign * (Decimal(digits) / Decimal("100"))


def _observed_casillas_from_declaration_pdf(
    *,
    snapshot: RegistrySnapshot,
    declaration: Declaracion,
    body: bytes,
) -> tuple[ObservedCasillaValue, ...]:
    parse_failed = False
    try:
        declaration_period = declaration.period.registry_token
        # The decrypted declaration bytes are parsed entirely in memory, including
        # bbox-anchored word-position extraction; they are never written to a
        # plaintext scratch file (sensitive-financial-data-secure-storage-only).
        filing = parse_declaracion_bytes(
            body,
            source_label="secure declaration PDF",
            modelo_override=declaration.modelo,
            año_override=declaration.ejercicio,
            period_override=declaration_period,
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
                "period": declaration.period.registry_token,
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
                "period": declaration.period.registry_token,
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
        "period_code": declaration.period.registry_token,
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
    snapshot = _registry_authority().snapshot(
        observation.modelo,
        filing_year=observation.ejercicio,
        period=period_token,
    )
    revision_casillas_by_id = casillas_by_id(snapshot.revision)
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
    casilla_values: dict[CasillaId, Decimal] = {}
    for casilla in observation.casillas:
        if casilla.source_artefact_kind == "justificante_pdf":
            raise SedeParseError("justificante metadata cannot populate registry casilla values")
        registry_casilla = revision_casillas_by_id.get(casilla.casilla_id)
        if registry_casilla is None:
            raise SedeParseError(
                f"observed casilla {casilla.casilla_id!r} is not a canonical casilla.id for "
                f"modelo {observation.modelo} revision {snapshot.revision.id}",
            )
        if not registry_casilla.legal_refs or not registry_casilla.source_refs:
            raise SedeParseError(
                f"observed casilla {casilla.casilla_id!r} in modelo {observation.modelo} "
                f"revision {snapshot.revision.id} has incomplete registry legal_refs/source_refs",
            )
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
        observations=tuple(
            CasillaObservation(
                casilla_id=cid,
                value=val,
                legal_refs=revision_casillas_by_id[cid].legal_refs,
                source_refs=revision_casillas_by_id[cid].source_refs,
            )
            for cid, val in casilla_values.items()
        ),
    )


def _with_derived_303_compensation_available_observation(
    observation: FiledDeclaracionObservation,
) -> FiledDeclaracionObservation:
    """Add Modelo 303 carry-forward availability derived from canonical filed casillas."""
    target_id = _M303_DISPONIBLE_CASILLA
    if observation.modelo != Modelo.M303 or any(casilla.casilla_id == target_id for casilla in observation.casillas):
        return observation
    values: dict[CasillaId, Decimal] = {}
    for casilla in observation.casillas:
        if (
            casilla.casilla_id
            not in {
                _M303_POSTERIOR_CASILLA,
                _M303_RESULTADO_CASILLA,
                _M303_GENERADA_CASILLA,
            }
            or casilla.source_artefact_kind == "justificante_pdf"
        ):
            continue
        try:
            values[casilla.casilla_id] = Decimal(casilla.value)
        except InvalidOperation as exc:
            raise SedeParseError(f"observed casilla {casilla.casilla_id!r} is not decimal-valued") from exc
    posterior = values.get(_M303_POSTERIOR_CASILLA)
    generated = values.get(_M303_GENERADA_CASILLA)
    resultado = values.get(_M303_RESULTADO_CASILLA)
    if posterior is None:
        return observation
    if generated is not None:
        snapshot = resources().modelos.authority.snapshot(
            Modelo.M303.value,
            filing_year=observation.ejercicio,
            period=observation.period.registry_token,
        )
        formula = next(item for item in snapshot.revision.formulas if item.target_casilla_id == target_id)
        operand_refs = (_M303_POSTERIOR_CASILLA, _M303_GENERADA_CASILLA)
        expected_operand_refs = expression_casilla_refs(formula.expression)
        if operand_refs != expected_operand_refs:
            raise SedeParseError(
                f"Modelo 303 derived compensation available operands {operand_refs!r} do not match "
                f"registry formula {formula.id!r} projection {expected_operand_refs!r}",
            )
        available = posterior + generated
        source_artefact_kind = "derived_registry_formula"
        source_locator = f"formula:{_M303_POSTERIOR_CASILLA}+{_M303_GENERADA_CASILLA}"
    elif resultado is not None:
        available = derive_303_compensation_available(posterior=posterior, resultado=resultado)
        source_artefact_kind = "derived_carry_policy"
        source_locator = f"carry-policy:{_M303_POSTERIOR_CASILLA}+max(0,-{_M303_RESULTADO_CASILLA})"
    else:
        return observation
    derived = ObservedCasillaValue(
        casilla_id=target_id,
        value=str(available),
        source_artefact_kind=source_artefact_kind,
        source_locator=source_locator,
        confidence=1.0,
    )
    return observation.model_copy(update={"casillas": (*observation.casillas, derived)})


def resolve_previous_filing_bindings_from_filed_declarations(
    revision: ModeloRevision,
    observations: tuple[FiledDeclaracionObservation, ...],
    *,
    filing_year: int,
    period: Period,
) -> dict[BindingId, Decimal]:
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
) -> dict[RelationId, Decimal]:
    """Resolve registry cross-model relation values from filed AEAT observations.

    Use of :class:`ModeloRevision` for compliance.
    """
    return resolve_relation_values_from_observations(
        revision,
        (registry_observation_from_filed_declaration(observation) for observation in observations),
        filing_year=filing_year,
        period=period.registry_token,
    )
