"""The bundled reference reads, answered by the service the command line calls.

Each read takes the same coordinates its command takes and returns the same
typed result, under one pinned generation of the published authority. Nothing
here reads a profile, holds a session or contacts a network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from pydantic import BaseModel

from ....application import reference_catalogue as catalogue
from ....application.modelo.registry_discovery import (
    registry_bindings,
    registry_bindings_for_scope,
    registry_bindings_for_year,
)
from ....application.operator_output.result_document import printed_result_document
from ....core.errors.error_codes import resolve_error_message
from ....core.errors.hierarchy import CadrumoError, CoreValidationError
from ....core.modelo import Modelo
from ....core.period import Period, PeriodError
from ....core.tax_domain import TaxDomain
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.errors import RegistryError
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.portals.categories import PortalCategory
from ....domain.portals.errors import PortalRegistryError


class ReferenceRead(StrEnum):
    """Every reference read the interface offers."""

    MODELOS = "modelos"
    SUPPORT_MATRIX = "support_matrix"
    DESCRIBE = "describe"
    CASILLAS = "casillas"
    CASILLA = "casilla"
    FORMULAS = "formulas"
    BINDINGS = "bindings"
    CATEGORIES = "categories"
    PORTALS = "portals"
    PORTAL = "portal"
    AUTH_PROVIDERS = "auth_providers"
    APODERADO_SCOPES = "apoderado_scopes"


@dataclass(frozen=True, slots=True)
class ReferenceQuery:
    """One read and the coordinates its command accepts."""

    read: ReferenceRead
    modelo: str | None = None
    year: int | None = None
    period: str | None = None
    as_of: date | None = None
    domain: str | None = None
    input_kind: str | None = None
    required: bool = False
    form_number: str | None = None
    casilla_number: str | None = None
    casilla: str | None = None
    category: str | None = None
    portal: str | None = None


class ReferenceReadRefusedError(CadrumoError):
    """A read whose coordinates the person must correct; the message is the one the command prints."""


class ReferenceCoordinateMissingError(ReferenceReadRefusedError):
    """A read was asked for without a coordinate it cannot do without."""

    def __init__(self, coordinate: str) -> None:
        """Name the coordinate that was left empty."""
        super().__init__(coordinate)
        self.coordinate = coordinate


_PINNED_READS = frozenset(
    {
        ReferenceRead.MODELOS,
        ReferenceRead.SUPPORT_MATRIX,
        ReferenceRead.DESCRIBE,
        ReferenceRead.CASILLAS,
        ReferenceRead.CASILLA,
        ReferenceRead.FORMULAS,
        ReferenceRead.BINDINGS,
        ReferenceRead.CATEGORIES,
        ReferenceRead.APODERADO_SCOPES,
    }
)
"""Reads answered from the published authority, which is pinned for the length of the read."""

_COORDINATE_ERRORS = (RegistryError, PortalRegistryError, CoreValidationError, PeriodError)
"""Registered refusals that mean the coordinates name nothing the reference holds."""


def _required(value: str | None, coordinate: str) -> str:
    if value is None or not value.strip():
        raise ReferenceCoordinateMissingError(coordinate)
    return value.strip()


def _bindings(query: ReferenceQuery, operation: PinnedAuthorityOperation) -> BaseModel:
    """Read the bindings of one modelo revision, scoped as every other registry read is scoped."""
    modelo = _required(query.modelo, "modelo")
    if query.year is None:
        return registry_bindings(modelo, period=query.period, as_of=query.as_of, operation=operation)
    if query.period is None or not query.period.strip():
        return registry_bindings_for_year(modelo, filing_year=query.year, as_of=query.as_of, operation=operation)
    return registry_bindings_for_scope(
        modelo,
        period=Period.from_year_and_code(query.year, query.period.strip()),
        as_of=query.as_of,
        operation=operation,
    )


def _pinned(query: ReferenceQuery, operation: PinnedAuthorityOperation) -> BaseModel:
    read = query.read
    if read is ReferenceRead.MODELOS:
        domain = TaxDomain(query.domain) if query.domain else None
        return catalogue.list_modelos(year=query.year, domain=domain, operation=operation)
    if read is ReferenceRead.SUPPORT_MATRIX:
        return catalogue.read_support_matrix(operation=operation)
    if read is ReferenceRead.APODERADO_SCOPES:
        return catalogue.list_apoderado_scopes(operation=operation)
    if read is ReferenceRead.CATEGORIES:
        # The category vocabularies are governed facts, read under the pin.
        return catalogue.read_ledger_categories()
    if read is ReferenceRead.BINDINGS:
        return _bindings(query, operation)
    modelo = _required(query.modelo, "modelo")
    year, period, as_of = query.year, query.period, query.as_of
    if read is ReferenceRead.DESCRIBE:
        return catalogue.describe_modelo(modelo, year=year, period=period, as_of=as_of, operation=operation)
    if read is ReferenceRead.CASILLAS:
        return catalogue.list_casillas(
            modelo,
            year=year,
            period=period,
            as_of=as_of,
            input_kind=InputKind(query.input_kind) if query.input_kind else None,
            required=query.required,
            form_number=query.form_number,
            casilla_number=query.casilla_number,
            operation=operation,
        )
    if read is ReferenceRead.CASILLA:
        return catalogue.describe_casilla(
            modelo, _required(query.casilla, "casilla"), year=year, period=period, as_of=as_of, operation=operation
        )
    return catalogue.list_formulas(modelo, year=year, period=period, as_of=as_of, operation=operation)


def _unpinned(query: ReferenceQuery) -> BaseModel:
    read = query.read
    if read is ReferenceRead.PORTALS:
        return catalogue.list_portals(
            category=PortalCategory(query.category) if query.category else None,
            modelo=Modelo(query.modelo) if query.modelo else None,
        )
    if read is ReferenceRead.PORTAL:
        return catalogue.view_portal(_required(query.portal, "portal"))
    return catalogue.list_auth_providers()


def _as_printed[ResultT: BaseModel](result: ResultT) -> ResultT:
    """Return a result with the values its command prints.

    A command writes its result through one output pass that shortens or
    withholds some values, a portal's address among them. The same pass is
    applied here, so this interface shows what the command shows and no more.
    """
    return type(result).model_validate_json(json.dumps(printed_result_document(result)))


def read_reference(query: ReferenceQuery) -> BaseModel:
    """Answer one reference read with the result its command prints.

    Raises:
        ReferenceReadRefusedError: The coordinates do not name something the
            reference holds. Its message is what the command line prints for
            the same coordinates.
    """
    try:
        if query.read not in _PINNED_READS:
            return _as_printed(_unpinned(query))
        with bundled_indexed_authority().operation() as operation:
            return _as_printed(_pinned(query, operation))
    except ReferenceReadRefusedError:
        raise
    except catalogue.ReferenceQueryError as error:
        raise ReferenceReadRefusedError(str(error)) from error
    except _COORDINATE_ERRORS as error:
        raise ReferenceReadRefusedError(resolve_error_message(error)) from error


__all__ = [
    "ReferenceCoordinateMissingError",
    "ReferenceQuery",
    "ReferenceRead",
    "ReferenceReadRefusedError",
    "read_reference",
]
