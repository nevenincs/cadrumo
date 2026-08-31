"""Filed-declaration observation and registry interpretation helpers.

The Sede capture path resolves a
:class:`RegistrySnapshot` through
:class:`ValidatedRegistryAuthority`,
interprets its :class:`ModeloRevision`, and
materialises filed rows as provenance-bearing
:class:`CasillaObservation` records.

See Also:
    :func:`~adapters.outbound.aeat.sede.declarations_capture.capture_filed_declaration_observation`
        Browser capture surface that produces filed-declaration observations.
    :func:`registry_observation_from_filed_declaration`
        Conversion boundary from Sede observations to registry observations.
    :func:`resolve_previous_filing_bindings_from_filed_declarations`
        Resolver that folds filed observations into previous-filing bindings.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl

from .....core import CasillaValueKind, ExportLayoutFormat, ObservedHeaderFact
from .....core.casilla_id import CasillaId
from .....core.config import Settings
from .....core.external_constants import JSON_MIME_TYPE as _JSON_MIME_TYPE
from .....core.hashing import canonical_json_bytes, sha256_hex
from .....core.i18n import tr
from .....core.modelo import Modelo
from .....core.period import Period
from .....core.resources import bundled_path
from .....core.time import now
from .....domain.calculations.export_field_kind import CasillaFieldKind
from .....domain.calculations.registry.authority import bundled_authority
from .....domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from .....domain.calculations.registry.bindings_previous_filing import resolve_previous_filing_binding_values
from .....domain.calculations.registry.casilla_membership import casillas_by_id
from .....domain.calculations.registry.errors import (
    RegistrySnapshotError,
    RegistryValidationError,
)
from .....domain.calculations.registry.export import resolve_export_layout
from .....domain.calculations.registry.export_parse import (
    ParsedExportFieldValue,
    parse_export_payload,
)
from .....domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from .....domain.calculations.registry.relations import resolve_relation_values_from_observations
from .....domain.calculations.registry.remote_state_guard import (
    RemoteStateGuardPolicy,
    remote_state_policy_from_cross_reference,
)
from .....domain.calculations.registry.runtime_graph import expression_casilla_refs
from .....domain.calculations.registry.schema import RegistrySnapshot
from .....domain.calculations.registry.schema_exports import ExportFieldDefinition
from .....domain.calculations.registry.schema_surfaces import CasillaDefinition
from .....domain.iva_compensation.filed_derivation import (
    M303_COMPENSATION_AVAILABLE_CASILLA,
    M303_COMPENSATION_GENERADA_CASILLA,
    M303_COMPENSATION_POSTERIOR_CASILLA,
    M303_COMPENSATION_RESULTADO_CASILLA,
    M303CompensationAvailableDerivation,
    derive_m303_compensation_available_from_casillas,
)
from ....inbound.declaracion import DeclaracionParseError, parse_declaracion_bytes
from .declarations_schema import Declaracion
from .errors import SedeParseError, SedeValidationError
from .schema import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    ObservedCasillaSkip,
    ObservedCasillaValue,
)

if TYPE_CHECKING:
    from .....domain.calculations.registry.authority import ValidatedRegistryAuthority
    from .....domain.calculations.registry.schema import ModeloRevision

__all__ = [
    "FiledDeclaracionArtefactSink",
    "_declaration_pdf_extraction_profile_provisional",
    "_observed_casillas_from_declaration_pdf",
    "_read_guard_policy_from_snapshot",
    "_register_row_artefact",
    "_registry_snapshot_for_declaration",
    "_store_artefact",
    "_submitted_file_coverage_for_casillas",
    "_submitted_file_extraction_coverage",
    "_verify_submitted_file_context",
    "_with_derived_303_compensation_available_observation",
    "non_numeric_observed_casillas",
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
    payload = canonical_json_bytes(declaration.model_dump(mode="json"))
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
    from .....domain.calculations.registry.authority import ValidatedRegistryAuthority

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


def _observed_value_kind(value: object) -> CasillaValueKind:
    """Classify an already-parsed casilla value by how a reader should treat it.

    This is the same dispatch :func:`_observed_value_token` makes when it decides
    whether to keep the artefact's spelling, and the two MUST agree: the token
    rule and the kind are two answers to one question the parser already settled.
    Splitting them would let a value be spelled as a boolean while being labelled
    numeric, which is precisely the disagreement the kind exists to prevent.

    The ``bool`` test comes first and must stay first, because ``bool`` is a
    subclass of ``int``: testing for a number first would classify every yes/no
    marker as an amount, which is the defect in its purest form.

    Accepts ``object`` because it serves both artefact readers, whose parsed
    types differ -- the export parser yields ``Decimal | str | bool``, while the
    declaration-PDF extractor can also yield ``int`` and ``date``. A ``date`` is
    text: it is a token that identifies a day, never a quantity.
    """
    if isinstance(value, bool):
        return CasillaValueKind.BOOLEAN
    if isinstance(value, Decimal | int):
        return CasillaValueKind.NUMERIC
    return CasillaValueKind.TEXT


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
    if _observed_value_kind(casilla.value) is CasillaValueKind.BOOLEAN:
        return casilla.raw
    return str(casilla.value)


def _observed_header_facts_from_submitted_file(
    *,
    snapshot: RegistrySnapshot,
    body: bytes,
) -> tuple[ObservedHeaderFact, ...]:
    """Return the header facts AEAT states in the submitted fichero, with provenance.

    The disposition is one of these. AEAT models the tipo de declaración as a
    header field in its diseño de registro, the export layout models it as a
    header, and the parser returns it as a header -- the only place it stopped
    being a header was this module, which read ``parsed.casillas`` and discarded
    ``parsed.fields`` entirely. The code was already in the bytes and already
    decoded before being dropped.

    Deliberately NOT projected as an :class:`ObservedCasillaValue`. A header is
    not a casilla, and the boxes AEAT prints for these elections are absent from
    the record design precisely because AEAT encodes them here instead; giving
    them a synthetic casilla id would put this registry and the official
    structure in disagreement about the concept's kind.

    This is the canonical projection and it is TYPED. Each fact carries the
    export parser's own ``source_locator`` alongside the token, because a bare
    ``key -> value`` pair cannot answer where the value was read from, and a
    header fact that reaches persisted evidence without its record-design
    position is not auditable back to the bytes.
    Returns an empty tuple rather than raising when the payload cannot be parsed
    against the layout. The casilla projection is the caller's primary result and
    reports its own failure loudly; a header read that fails must not take the
    casillas down with it.
    """
    try:
        resolved = resolve_export_layout(snapshot)
        parsed = parse_export_payload(
            resolved.layout,
            body,
            source_root=bundled_path(),
            sources=snapshot.sources,
        )
    except RegistryValidationError:
        return ()

    facts: list[ObservedHeaderFact] = []
    for field_value in parsed.fields:
        definition = resolved.fields_by_id.get(field_value.field_id)
        if definition is None or definition.kind is not CasillaFieldKind.HEADER:
            continue
        producer_key = definition.producer_key
        if producer_key is None or field_value.value is None:
            continue
        token = str(field_value.value).strip()
        if not token:
            # An unset one-byte flag is blank. Recording it empty would be
            # indistinguishable from AEAT stating a value, so it is omitted --
            # the same honesty the register's request-type projection applies.
            continue
        facts.append(
            ObservedHeaderFact(
                header_key=producer_key.value,
                value=token,
                source_artefact_kind="submitted_file",
                source_locator=field_value.source_locator,
            ),
        )
    return tuple(facts)


def observed_casillas_from_submitted_file(
    *,
    snapshot: RegistrySnapshot,
    declaration: Declaracion,
    body: bytes,
    artefact: FiledDeclaracionArtefact,
) -> tuple[ObservedCasillaValue, ...]:
    """Read the casilla values a submitted fichero actually carries."""
    try:
        resolved = resolve_export_layout(snapshot)
        parsed = parse_export_payload(
            resolved.layout,
            body,
            source_root=bundled_path(),
            sources=snapshot.sources,
        )
    except RegistryValidationError as exc:
        raise _submitted_file_layout_refusal(
            snapshot=snapshot,
            declaration=declaration,
            artefact=artefact,
            reason=str(exc),
        ) from exc
    _verify_submitted_file_context(resolved.fields_by_id, parsed.fields, declaration=declaration)
    observations: list[ObservedCasillaValue] = []
    for casilla in parsed.casillas:
        if casilla.casilla_id is None or casilla.value is None:
            continue
        observations.append(
            ObservedCasillaValue(
                casilla_id=casilla.casilla_id,
                value=_observed_value_token(casilla),
                value_kind=_observed_value_kind(casilla.value),
                source_artefact_kind="submitted_file",
                source_locator=casilla.source_locator,
                confidence=1.0,
            ),
        )
    if not observations:
        raise SedeParseError(f"submitted-file artefact {artefact.sha256[:16]} did not yield casilla observations")
    return tuple(observations)


def _submitted_file_layout_refusal(
    *,
    snapshot: RegistrySnapshot,
    declaration: Declaracion,
    artefact: FiledDeclaracionArtefact,
    reason: str,
) -> SedeParseError:
    """Build the refusal for a submitted fichero the export layout cannot read.

    This path used to degrade to a positional Modelo 303 page-03 reader, which
    guessed five result casillas from hardcoded byte offsets and returned them
    with no signal that the layout had refused the payload. That silence hid a
    real defect for as long as it existed: the layout declared the refund-only
    DID record required, so for the compensacion, ingreso and negativa
    dispositions NO field of a real fichero parsed, and every casilla an
    operator saw came from the positional guess. A reader cannot tell a guessed
    value from a read one, so the failure is surfaced instead of absorbed.

    The refusal names the modelo, the resolved revision and the parser's own
    reason -- which identifies the record the parse stopped on -- so the next
    reader can act on it rather than rediscover it.
    """
    return SedeParseError(
        f"submitted-file artefact {artefact.sha256[:16]} for modelo {snapshot.modelo.id} "
        f"revision {snapshot.revision.id} ({declaration.ejercicio} {declaration.period.registry_token}) "
        f"could not be read through its export layout: {reason}",
        context={
            "operation": "submitted_file_layout_parse",
            "modelo": snapshot.modelo.id,
            "revision": snapshot.revision.id,
            "ejercicio": str(declaration.ejercicio),
            "period": declaration.period.registry_token,
            "expediente_id": declaration.expediente_id,
            "raw_sha256": artefact.sha256,
            "reason": reason,
        },
        translated_message=tr("adapters.sede.errors.submitted_file_layout_parse_failed"),
    )


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
    An ``xml_dictionary`` layout is treated as fully covered (1.0), because it
    omits an absent optional element rather than reserving a slot for it;
    otherwise the parsed export fields are scored against the resolved layout's
    ``fields_by_casilla`` map. A layout that will not resolve raises rather than
    scoring, so a modelo whose layout is missing cannot report full coverage.
    """
    resolved_layout = resolve_export_layout(snapshot)
    if resolved_layout.layout.format is ExportLayoutFormat.XML_DICTIONARY:
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


def _declaration_pdf_extraction_profile_provisional(snapshot: RegistrySnapshot) -> bool:
    """Report whether any ``declaracion_pdf`` profile in ``snapshot`` is unconfirmed.

    A profile with ``provisional_pending_specimen = true`` has its
    ``bbox_anchored`` anchor positions guessed from the bundled AEAT-published
    Diseño de Registro rather than confirmed against a real filed PDF (see
    ``aeat-quality-gates``). The parser's coverage gate
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
                value_kind=_observed_value_kind(casilla.printed_value),
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


def non_numeric_observed_casillas(
    observation: FiledDeclaracionObservation,
) -> tuple[ObservedCasillaSkip, ...]:
    """Return every casilla the Decimal-only registry channel cannot carry.

    Returns an empty tuple when every observed casilla is readable as an amount.
    A non-empty tuple enumerates the casillas that are not: a declared kind that
    is not numeric, or a numeric casilla whose token will not parse.

    Caller-opt-in, in the shape of
    :func:`~adapters.outbound.google.calc_sheets_pull.verify_pull_coverage`: this is a query, not
    a step in enrolment. It performs no side effects and can be called before or
    after
    :func:`registry_observation_from_filed_declaration`, so a caller with an
    operator surface can report the gap while a caller without one is unaffected
    and unchanged.

    Rows carry no value, deliberately -- see
    :class:`~adapters.outbound.aeat.sede.ObservedCasillaSkip`.
    """
    period_token = observation.period.registry_token
    snapshot = _registry_authority().snapshot(
        observation.modelo,
        filing_year=observation.ejercicio,
        period=period_token,
    )
    revision_casillas_by_id = casillas_by_id(snapshot.revision)
    skips: list[ObservedCasillaSkip] = []
    for casilla in observation.casillas:
        if casilla.source_artefact_kind == "justificante_pdf":
            continue
        registry_casilla = revision_casillas_by_id.get(casilla.casilla_id)
        if registry_casilla is None:
            continue
        if casilla.value_kind is not CasillaValueKind.NUMERIC:
            reason: Literal["not_numeric", "unreadable_numeric_token"] = "not_numeric"
        else:
            try:
                casilla.decimal_value()
            except InvalidOperation:
                reason = "unreadable_numeric_token"
            else:
                continue
        skips.append(
            ObservedCasillaSkip(
                casilla_id=casilla.casilla_id,
                label=registry_casilla.label,
                value_kind=casilla.value_kind,
                reason=reason,
            ),
        )
    return tuple(skips)


def _validate_filed_observation_extraction_coverage(
    observation: FiledDeclaracionObservation,
    *,
    period_token: str,
) -> None:
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


def _numeric_registry_observation_value(
    *,
    observation: FiledDeclaracionObservation,
    casilla: ObservedCasillaValue,
    snapshot: RegistrySnapshot,
    revision_casillas_by_id: Mapping[CasillaId, CasillaDefinition],
) -> tuple[CasillaId, Decimal] | None:
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
    # Ask what the casilla IS, never what its token parses as. A free-text
    # Modelo 100 casilla can hold a token that converts cleanly to a plausible
    # wrong number -- `0065` (clave) reads as 15, `0167` (epígrafe IAE) as 22 --
    # so a conversion attempt admits exactly the values it needed to reject.
    #
    # A casilla this channel cannot carry is skipped rather than fatal: a modelo
    # whose schema declares free-text or boolean casillas has them on EVERY
    # filing, so refusing here discarded a whole return's numeric evidence over
    # fields that were never destined for a Decimal map. The skipped set is not
    # lost -- non_numeric_observed_casillas enumerates it for the operator, and
    # a return with no numeric casilla at all still refuses below.
    if casilla.value_kind is not CasillaValueKind.NUMERIC:
        return None
    try:
        value = casilla.decimal_value()
    except InvalidOperation:
        return None
    return casilla.casilla_id, value


def _build_registry_observation(
    *,
    observation: FiledDeclaracionObservation,
    period_token: str,
    revision_casillas_by_id: Mapping[CasillaId, CasillaDefinition],
    casilla_values: Mapping[CasillaId, Decimal],
) -> RegistryModeloObservation:
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
    _validate_filed_observation_extraction_coverage(observation, period_token=period_token)
    casilla_values: dict[CasillaId, Decimal] = {}
    for casilla in observation.casillas:
        numeric_value = _numeric_registry_observation_value(
            observation=observation,
            casilla=casilla,
            snapshot=snapshot,
            revision_casillas_by_id=revision_casillas_by_id,
        )
        if numeric_value is None:
            continue
        casilla_id, value = numeric_value
        previous = casilla_values.get(casilla_id)
        if previous is not None and previous != value:
            raise SedeParseError(f"observed casilla {casilla_id!r} has contradictory values")
        casilla_values[casilla_id] = value
    return _build_registry_observation(
        observation=observation,
        period_token=period_token,
        revision_casillas_by_id=revision_casillas_by_id,
        casilla_values=casilla_values,
    )


def _m303_compensation_source_values(
    observation: FiledDeclaracionObservation,
) -> dict[CasillaId, Decimal]:
    source_casilla_ids = {
        M303_COMPENSATION_POSTERIOR_CASILLA,
        M303_COMPENSATION_RESULTADO_CASILLA,
        M303_COMPENSATION_GENERADA_CASILLA,
    }
    values: dict[CasillaId, Decimal] = {}
    for casilla in observation.casillas:
        if casilla.casilla_id not in source_casilla_ids or casilla.source_artefact_kind == "justificante_pdf":
            continue
        try:
            values[casilla.casilla_id] = casilla.decimal_value()
        except (InvalidOperation, SedeValidationError) as exc:
            raise SedeParseError(f"observed casilla {casilla.casilla_id!r} is not decimal-valued") from exc
    return values


def _m303_compensation_source_metadata(
    *,
    observation: FiledDeclaracionObservation,
    derivation: M303CompensationAvailableDerivation,
) -> tuple[Literal["derived_registry_formula", "derived_carry_policy"], str]:
    if derivation.basis == "generated":
        snapshot = bundled_authority().snapshot(
            Modelo.M303.value,
            filing_year=observation.ejercicio,
            period=observation.period.registry_token,
        )
        formula = next(
            item for item in snapshot.revision.formulas if item.target_casilla_id == M303_COMPENSATION_AVAILABLE_CASILLA
        )
        expected_operand_refs = expression_casilla_refs(formula.expression)
        if derivation.operand_refs != expected_operand_refs:
            raise SedeParseError(
                f"Modelo 303 derived compensation available operands {derivation.operand_refs!r} do not match "
                f"registry formula {formula.id!r} projection {expected_operand_refs!r}",
            )
        return (
            "derived_registry_formula",
            f"formula:{M303_COMPENSATION_POSTERIOR_CASILLA}+{M303_COMPENSATION_GENERADA_CASILLA}",
        )
    return (
        "derived_carry_policy",
        f"carry-policy:compensacion-assumed:{M303_COMPENSATION_POSTERIOR_CASILLA}+max(0,-{M303_COMPENSATION_RESULTADO_CASILLA})",
    )


def _with_derived_303_compensation_available_observation(
    observation: FiledDeclaracionObservation,
) -> FiledDeclaracionObservation:
    """Add Modelo 303 carry-forward availability derived from canonical filed casillas."""
    target_id = M303_COMPENSATION_AVAILABLE_CASILLA
    if observation.modelo != Modelo.M303 or any(casilla.casilla_id == target_id for casilla in observation.casillas):
        return observation
    values = _m303_compensation_source_values(observation)
    # A fetched AEAT filing carries casillas only, and the compensación /
    # devolución election is not one: Modelo 303 has no devolución casilla, so
    # the fichero header that records it is not in what we observe here. The
    # standard compensación disposition is therefore ASSUMED, which is right for
    # the common case and over-states the carry for a period the taxpayer had
    # refunded. Stated rather than defaulted, and stamped into the locator below
    # so an operator auditing the carry can see the assumption that produced it.
    derivation = derive_m303_compensation_available_from_casillas(values, refunded=False)
    if derivation is None:
        return observation
    source_artefact_kind, source_locator = _m303_compensation_source_metadata(
        observation=observation,
        derivation=derivation,
    )
    derived = ObservedCasillaValue(
        casilla_id=target_id,
        value=str(derivation.available),
        value_kind=_observed_value_kind(derivation.available),
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
