"""Filed-declaration observation and registry interpretation helpers.

The Sede capture path resolves a
:class:`RegistrySnapshot` through
:class:`ValidatedRegistryAuthority`,
interprets its :class:`ModeloRevision`, and
materialises filed rows as provenance-bearing
:class:`CasillaObservation` records.

See Also:
    :func:`~adapters.outbound.aeat.sede.capture_filed_declaration_observation`
        Browser capture surface that produces filed-declaration observations.
    :func:`registry_observation_from_filed_declaration`
        Conversion boundary from Sede observations to registry observations.
    :func:`resolve_previous_filing_bindings_from_filed_declarations`
        Resolver that folds filed observations into previous-filing bindings.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Final, NoReturn
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl

from .....core import ExportLayoutFormat, Modelo, Period
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
)
from .....domain.iva_compensation import (
    M303_COMPENSATION_AVAILABLE_CASILLA,
    M303_COMPENSATION_GENERADA_CASILLA,
    M303_COMPENSATION_POSTERIOR_CASILLA,
    M303_COMPENSATION_RESULTADO_CASILLA,
    derive_m303_compensation_available_from_casillas,
)
from ....inbound.declaracion import DeclaracionParseError, parse_declaracion_bytes
from ._browser_constants import SEDE_BODY_ENCODING as _SEDE_BODY_ENCODING
from ._declarations_schema import Declaracion
from ._errors import SedeParseError
from ._schema import FiledDeclaracionArtefact, FiledDeclaracionObservation, ObservedCasillaValue

if TYPE_CHECKING:
    from .....domain.calculations.registry import ModeloRevision, ValidatedRegistryAuthority

__all__ = [
    "FiledDeclaracionArtefactSink",
    "_declaration_pdf_extraction_profile_provisional",
    "_is_modelo_303_page_03_fallback",
    "_observed_casillas_from_declaration_pdf",
    "_read_guard_policy_from_snapshot",
    "_register_row_artefact",
    "_registry_snapshot_for_declaration",
    "_store_artefact",
    "_submitted_file_coverage_for_casillas",
    "_submitted_file_extraction_coverage",
    "_verify_submitted_file_context",
    "_with_derived_303_compensation_available_observation",
    "observed_casillas_from_submitted_file",
    "registry_observation_from_filed_declaration",
    "resolve_previous_filing_bindings_from_filed_declarations",
    "resolve_relation_values_from_filed_declarations",
]

_EXTERNAL = Settings.external_constants()
_SEDE_BASE = _EXTERNAL.aeat.domains.www6


# This URL is never requested. Only its HOSTNAME is read, and it is a LOOKUP
# KEY: _read_guard_policy_from_snapshot below matches it against the registry's
# declared allowed_hosts for the declarations read surface and requires exactly
# one match, so this constant selects the safety policy every capture runs
# under. Point it at a different host, or make it follow the host a navigation
# actually landed on, and the lookup matches zero declarations and raises --
# failing every capture at the guard's own resolution step rather than
# degrading. The reader in _declarations.py builds the same string from the
# same two constants for its navigation; that copy is the one that is merely a
# URL. Changing either alone silently separates where a read goes from which
# policy adjudicates it.
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


def _observed_value_token(casilla: ParsedExportFieldValue) -> str:
    """Return what the filed artefact said for ``casilla``, as a string.

    An :class:`ObservedCasillaValue` is evidence of the ARTEFACT, so a boolean
    field records the token AEAT actually wrote -- ``S`` / ``N`` for the XML
    dictionary's ``LGC`` rows -- rather than ``str(True)``. ``"True"`` is a
    Python repr that appears on no AEAT surface, and it was reaching the
    evidence boundary for every ``LGC`` row.

    Only the boolean case reads ``raw``, and that narrowness is load-bearing
    rather than timidity. ``raw`` and ``str(value)`` agree for XML-dictionary
    rows (measured: 75 of 77 on a real Modelo 100 artefact, the two exceptions
    being exactly the ``LGC`` bools), but they disagree for EVERY fixed-width
    casilla, because that format carries money zero-padded and scaled by 100:
    Modelo 130 casilla ``01`` is ``raw='00000000000010000'`` against
    ``str(value)='100'``. Since the registry-enrollment consumer reads these
    back through ``Decimal(...)``, recording ``raw`` for a fixed-width money
    field would enrol 10000 where the taxpayer filed 100. The typed value is
    the faithful reading there, and the raw token is the faithful reading only
    where the parser's own conversion discards the artefact's spelling.
    """
    if isinstance(casilla.value, bool):
        return casilla.raw
    return str(casilla.value)


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
                value=_observed_value_token(casilla),
                source_artefact_kind="submitted_file",
                source_locator=casilla.source_locator,
                confidence=1.0,
            ),
        )
    if not observations:
        raise SedeParseError(f"submitted-file artefact {artefact.sha256[:16]} did not yield casilla observations")
    return tuple(observations)


observed_casillas_from_submitted_file = _observed_casillas_from_submitted_file


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
    if resolved_layout.layout.format is ExportLayoutFormat.XML_DICTIONARY or _is_modelo_303_page_03_fallback(casillas):
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


#: Ceiling on the casillas named individually in the non-decimal refusal. A modelo
#: whose schema declares free-text casillas can breach this by hundreds, and the
#: count in the leading sentence already carries the magnitude.
_MAX_ENUMERATED_CASILLAS: Final[int] = 10

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


def _declaration_pdf_extraction_profile_provisional(snapshot: RegistrySnapshot) -> bool:
    """Report whether any ``declaracion_pdf`` profile in ``snapshot`` is unconfirmed.

    A profile with ``provisional_pending_specimen = true`` has its
    ``bbox_anchored`` anchor positions guessed from the bundled AEAT-published
    Diseño de Registro rather than confirmed against a real filed PDF (see
    ``fixture-provenance-declared-in-sidecar``). The parser's coverage gate
    (``min_coverage``) still fails hard when the anchor pattern matches nowhere
    on a real PDF's page, but a real PDF whose layout coincidentally matches the
    guessed anchor position at the wrong casilla would extract silently with no
    disclosure that the layout itself is unconfirmed. Callers stamp this signal
    into observation metadata (never silently) so an operator inspecting a live
    filed-declaration capture can see the extraction is not yet specimen-backed.
    """
    return any(
        profile.provisional_pending_specimen
        for profile in snapshot.extraction_profiles.values()
        if profile.surface == "declaracion_pdf"
    )


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
        draft_attribute = None if field is None else field.draft_attribute
        if (
            field is None
            or field.kind != CasillaFieldKind.DRAFT
            or draft_attribute is None
            or draft_attribute not in expected
        ):
            continue
        observed = "" if parsed.value is None else str(parsed.value)
        if observed != expected[draft_attribute]:
            raise SedeParseError(
                f"submitted-file field {parsed.field_id!r} does not match declaration {declaration.expediente_id!r}",
            )


def _refuse_non_decimal_casillas(
    affected: Sequence[tuple[CasillaId, str]],
    *,
    modelo: str,
    revision_id: str,
    filing_year: int,
    period_token: str,
) -> NoReturn:
    """Refuse enrolment, naming every casilla the Decimal-only channel cannot carry.

    NEVER interpolate the observed VALUE, here or in any future rewrite of this
    message. The tokens behind these casillas are taxpayer personal data -- Modelo
    100 ``0066`` is a referencia catastral and ``0069`` is the taxpayer's street
    address -- and this message is carried verbatim into the operator-facing
    capture failure row. The casilla id and its registry label say which field
    stopped the enrolment without putting the field's contents on that surface.

    The leading sentence carries the modelo, the count, and the cause because the
    failure row bounds the message well below the length of the full enumeration,
    so anything the operator must act on has to appear before the list.
    """
    shown = [f"{casilla_id} ({label})" for casilla_id, label in affected[:_MAX_ENUMERATED_CASILLAS]]
    remainder = len(affected) - len(shown)
    if remainder > 0:
        shown.append(f"and {remainder} more")
    raise SedeParseError(
        f"modelo {modelo} revision {revision_id} declares {len(affected)} filed casilla(s) that are not "
        f"decimal-valued, so filing {filing_year}/{period_token} cannot be enrolled as registry-grounded "
        f"calculation evidence: the registry observation channel carries Decimal values only. This is a "
        f"modelo-level limitation, not a defect in this return, and it recurs on every filing of this "
        f"modelo. Affected casillas: {', '.join(shown)}.",
        context={
            "modelo": modelo,
            "revision": revision_id,
            "filing_year": str(filing_year),
            "period": period_token,
            "non_decimal_casilla_count": str(len(affected)),
            "casilla_ids": [casilla_id for casilla_id, _label in affected],
        },
        translated_message=tr("adapters.sede.errors.casillas_not_decimal_valued"),
    )


def registry_observation_from_filed_declaration(
    observation: FiledDeclaracionObservation,
) -> RegistryModeloObservation:
    """Convert a filed-declaration observation into registry observation rows.

    The :class:`~adapters.outbound.aeat.sede.FiledDeclaracionObservation`
    is checked against the selected
    :class:`RegistrySnapshot`; each accepted
    :class:`~adapters.outbound.aeat.sede.ObservedCasillaValue` becomes a
    provenance-bearing :class:`CasillaObservation`
    inside the returned
    :class:`~domain.calculations.registry.RegistryModeloObservation`.
    """
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
    non_decimal: list[tuple[CasillaId, str]] = []
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
        except InvalidOperation:
            # Collect rather than raise on the first one: a modelo whose schema declares
            # free-text or boolean casillas fails on EVERY filing, so the operator needs
            # the whole affected set to see it is a modelo-wide gap, not a bad figure in
            # this return.
            non_decimal.append((casilla.casilla_id, registry_casilla.label))
            continue
        previous = casilla_values.get(casilla.casilla_id)
        if previous is not None and previous != value:
            raise SedeParseError(f"observed casilla {casilla.casilla_id!r} has contradictory values")
        casilla_values[casilla.casilla_id] = value
    if non_decimal:
        _refuse_non_decimal_casillas(
            non_decimal,
            modelo=observation.modelo,
            revision_id=snapshot.revision.id,
            filing_year=observation.ejercicio,
            period_token=period_token,
        )
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
    target_id = M303_COMPENSATION_AVAILABLE_CASILLA
    if observation.modelo != Modelo.M303 or any(casilla.casilla_id == target_id for casilla in observation.casillas):
        return observation
    values: dict[CasillaId, Decimal] = {}
    for casilla in observation.casillas:
        if (
            casilla.casilla_id
            not in {
                M303_COMPENSATION_POSTERIOR_CASILLA,
                M303_COMPENSATION_RESULTADO_CASILLA,
                M303_COMPENSATION_GENERADA_CASILLA,
            }
            or casilla.source_artefact_kind == "justificante_pdf"
        ):
            continue
        try:
            values[casilla.casilla_id] = Decimal(casilla.value)
        except InvalidOperation as exc:
            raise SedeParseError(f"observed casilla {casilla.casilla_id!r} is not decimal-valued") from exc
    derivation = derive_m303_compensation_available_from_casillas(values)
    if derivation is None:
        return observation
    if derivation.basis == "generated":
        snapshot = resources().modelos.authority.snapshot(
            Modelo.M303.value,
            filing_year=observation.ejercicio,
            period=observation.period.registry_token,
        )
        formula = next(item for item in snapshot.revision.formulas if item.target_casilla_id == target_id)
        expected_operand_refs = expression_casilla_refs(formula.expression)
        if derivation.operand_refs != expected_operand_refs:
            raise SedeParseError(
                f"Modelo 303 derived compensation available operands {derivation.operand_refs!r} do not match "
                f"registry formula {formula.id!r} projection {expected_operand_refs!r}",
            )
        source_artefact_kind = "derived_registry_formula"
        source_locator = f"formula:{M303_COMPENSATION_POSTERIOR_CASILLA}+{M303_COMPENSATION_GENERADA_CASILLA}"
    else:
        source_artefact_kind = "derived_carry_policy"
        source_locator = (
            f"carry-policy:{M303_COMPENSATION_POSTERIOR_CASILLA}+max(0,-{M303_COMPENSATION_RESULTADO_CASILLA})"
        )
    derived = ObservedCasillaValue(
        casilla_id=target_id,
        value=str(derivation.available),
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

    The :class:`ModeloRevision` supplies the
    previous-filing binding selectors and the :class:`~core.Period` selects
    the target filing period. Filed Sede
    :class:`~adapters.outbound.aeat.sede.FiledDeclaracionObservation` rows
    are converted to
    :class:`~domain.calculations.registry.RegistryModeloObservation` before
    :func:`~domain.calculations.registry.resolve_previous_filing_binding_values`
    folds their casilla values into :class:`~domain.calculations.registry.BindingId`
    outputs.
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

    The :class:`ModeloRevision` supplies the
    relation declarations and the :class:`~core.Period` selects the target
    filing period. Filed Sede
    :class:`~adapters.outbound.aeat.sede.FiledDeclaracionObservation` rows
    are converted to
    :class:`~domain.calculations.registry.RegistryModeloObservation` before
    :func:`~domain.calculations.registry.resolve_relation_values_from_observations`
    folds their casilla values into :class:`~domain.calculations.registry.RelationId`
    outputs.
    """
    return resolve_relation_values_from_observations(
        revision,
        (registry_observation_from_filed_declaration(observation) for observation in observations),
        filing_year=filing_year,
        period=period.registry_token,
    )
