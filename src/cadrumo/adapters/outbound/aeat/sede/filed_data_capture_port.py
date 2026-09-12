"""Concrete Sede binding for the application filed-data acquisition port."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TypeVar

from .....application.auth.certificate_secret_backend import CertificateSecretBackendFactory
from .....application.auth.operator_scope_ports import OperatorScopePorts
from .....application.live.errors import LiveApplicationError
from .....application.live.filed_data_ports import (
    FiledArtefactSink,
    FiledDataCapturePort,
    FiledDataRegisterPort,
    FiledRegisterDeclarationProtocol,
)
from .....application.live.filed_observation_ports import FiledObservationProtocol
from .....application.live.session import active_verified_session
from .....core.config import Settings, load_settings
from .....core.period import Period
from .....domain.calculations.registry.schema import ModeloRevision
from .declarations import (
    DeclaracionesRegisterSession,
    discover_filed_declaration_availability,
    open_declarations_register,
    shared_playwright,
)
from .declarations_capture import (
    capture_previous_filing_observations,
    capture_relation_source_observations,
)

_T = TypeVar("_T")
_DEFAULT_FAILURE_KEY = "application.live.filed_observations.errors.registry_enrollment_failed"


def _translate_adapter_error(operation: str, exc: Exception) -> LiveApplicationError:
    """Translate a concrete Sede refusal into the application error vocabulary."""
    translated_message = getattr(exc, "translated_message", None) or _DEFAULT_FAILURE_KEY
    return LiveApplicationError(
        translated_message=translated_message,
        context={"operation": operation, "cause_type": type(exc).__name__},
    )


async def _call_adapter(operation: str, callback: Callable[[], Awaitable[_T]]) -> _T:
    """Invoke one Sede capability and translate its exception at this boundary."""
    try:
        return await callback()
    except LiveApplicationError:
        raise
    except Exception as exc:
        raise _translate_adapter_error(operation, exc) from exc


class _SedeFiledDataRegisterPort(FiledDataRegisterPort):
    """Adapt one concrete register session to the application register port."""

    def __init__(self, register: DeclaracionesRegisterSession, *, walk_timeout_ms: int) -> None:
        """Bind one already-open Sede register and its configured timeout."""
        self._register = register
        self._walk_timeout_ms = walk_timeout_ms

    @property
    def walk_timeout_ms(self) -> int:
        """Return the timeout resolved by the outer Sede composition."""
        return self._walk_timeout_ms

    async def walk(self, *, modelo: str, ejercicio: int) -> tuple[FiledRegisterDeclarationProtocol, ...]:
        """Read one register pair and expose its structural application view."""
        return await _call_adapter(
            "filed_register_walk",
            lambda: self._register.walk(modelo=modelo, ejercicio=ejercicio),
        )

    async def capture_observation(
        self,
        declaration: FiledRegisterDeclarationProtocol,
        *,
        artefact_sink: FiledArtefactSink | None = None,
    ) -> FiledObservationProtocol:
        """Capture one register row through the concrete Sede reader."""
        return await _call_adapter(
            "filed_declaration_capture",
            lambda: self._register.capture_observation(declaration, artefact_sink=artefact_sink),
        )


class SedeFiledDataCapturePort(FiledDataCapturePort):
    """Compose authenticated Sede register and source-capture capabilities."""

    def __init__(
        self,
        *,
        certificate_secret_backend_factory: CertificateSecretBackendFactory,
        operator_scope_ports: OperatorScopePorts,
    ) -> None:
        """Bind the required certificate-secret capability for live reads."""
        self._certificate_secret_backend_factory = certificate_secret_backend_factory
        self._operator_scope_ports = operator_scope_ports

    @asynccontextmanager
    async def open_register(self, *, operation: str) -> AsyncIterator[FiledDataRegisterPort]:
        """Open one browser-backed register for the complete operation scope."""
        try:
            session, settings = await _call_adapter(
                "filed_register_session",
                lambda: active_verified_session(
                    certificate_secret_backend_factory=self._certificate_secret_backend_factory,
                    operation=operation,
                    operator_scope_ports=self._operator_scope_ports,
                ),
            )
            async with (
                shared_playwright(session) as playwright,
                open_declarations_register(session, settings=settings, playwright=playwright) as register,
            ):
                yield _SedeFiledDataRegisterPort(
                    register,
                    walk_timeout_ms=settings.cadrumo_live_filed_register_walk_timeout_ms,
                )
        except LiveApplicationError:
            raise
        except Exception as exc:
            raise _translate_adapter_error("filed_register_open", exc) from exc

    async def discover_availability(
        self,
        *,
        operation: str,
    ):
        """Read the register option lists through the application port."""
        session, settings = await _call_adapter(
            "filed_register_session",
            lambda: active_verified_session(
                certificate_secret_backend_factory=self._certificate_secret_backend_factory,
                operation=operation,
                operator_scope_ports=self._operator_scope_ports,
            ),
        )
        try:
            async with shared_playwright(session) as playwright:
                return await _call_adapter(
                    "filed_register_discovery",
                    lambda: discover_filed_declaration_availability(
                        session,
                        settings=settings,
                        playwright=playwright,
                    ),
                )
        except LiveApplicationError:
            raise
        except Exception as exc:
            raise _translate_adapter_error("filed_register_discovery", exc) from exc

    async def capture_source_observations(
        self,
        revision: ModeloRevision,
        *,
        filing_year: int,
        period: Period,
        artefact_sink: FiledArtefactSink | None = None,
        operation: str,
    ) -> tuple[FiledObservationProtocol, ...]:
        """Capture registry-selected source rows in one authenticated browser."""
        session, settings = await _call_adapter(
            "filed_register_session",
            lambda: active_verified_session(
                certificate_secret_backend_factory=self._certificate_secret_backend_factory,
                operation=operation,
                operator_scope_ports=self._operator_scope_ports,
            ),
        )

        async def _capture() -> tuple[FiledObservationProtocol, ...]:
            async with shared_playwright(session) as playwright:
                previous = await capture_previous_filing_observations(
                    session,
                    revision,
                    filing_year=filing_year,
                    period=period,
                    settings=settings,
                    playwright=playwright,
                    artefact_sink=artefact_sink,
                )
                related = await capture_relation_source_observations(
                    session,
                    revision,
                    filing_year=filing_year,
                    period=period,
                    settings=settings,
                    playwright=playwright,
                    artefact_sink=artefact_sink,
                )
                return previous + related

        return await _call_adapter("filed_source_capture", _capture)


__all__ = ["SedeFiledDataCapturePort"]
