"""Concrete Sede binding for the application filed-data acquisition port."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager, nullcontext
from dataclasses import dataclass, field
from typing import cast, override

from .....application.auth.certificate_secret_backend import CertificateSecretBackendFactory
from .....application.auth.operator_scope_ports import OperatorScopePorts
from .....application.auth.protocols import BrowserSessionFactoryPort
from .....application.live.errors import LiveApplicationError
from .....application.live.filed_data_ports import (
    DeferredFiledObservation,
    DeferredFiledObservations,
    FiledArtefactSink,
    FiledDataCapturePort,
    FiledDataRegisterPort,
    FiledEffectGuard,
    FiledRegisterDeclarationProtocol,
)
from .....application.live.filed_observation_ports import FiledObservationProtocol
from .....application.live.session import SessionWriteReporter, active_verified_session
from .....application.runtime.contracts import RuntimeRefusalError
from .....application.user_profile.access_errors import ProfileAccessRefusedError
from .....application.user_profile.automation_custody_port import AutomationCustodyError
from .....core.period import Period
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
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
from .declarations_schema import Declaracion
from .schema import FiledDeclaracionArtefact, FiledDeclaracionObservation

_DEFAULT_FAILURE_KEY = "application.live.filed_observations.errors.registry_enrollment_failed"


def _translate_adapter_error(operation: str, exc: Exception) -> LiveApplicationError:
    """Translate a concrete Sede refusal into the application error vocabulary."""
    translated_message = getattr(exc, "translated_message", None) or _DEFAULT_FAILURE_KEY
    return LiveApplicationError(
        translated_message=translated_message,
        context={"operation": operation, "cause_type": type(exc).__name__},
    )


async def _call_adapter[T](operation: str, callback: Callable[[], Awaitable[T]]) -> T:
    """Invoke one Sede capability and translate its exception at this boundary."""
    try:
        return await callback()
    except (ProfileAccessRefusedError, AutomationCustodyError, RuntimeRefusalError):
        raise
    except LiveApplicationError:
        raise
    except Exception as exc:
        raise _translate_adapter_error(operation, exc) from exc


def _concrete_artefact_sink(
    artefact_sink: FiledArtefactSink | None,
) -> Callable[[tuple[str, int, Period, str], FiledDeclaracionArtefact, bytes], FiledDeclaracionArtefact] | None:
    """Keep the Sede capture sink at its concrete artefact boundary."""
    if artefact_sink is None:
        return None

    def persist(
        observation_key: tuple[str, int, Period, str],
        artefact: FiledDeclaracionArtefact,
        body: bytes,
    ) -> FiledDeclaracionArtefact:
        stored = artefact_sink(observation_key, artefact, body)
        if not isinstance(stored, FiledDeclaracionArtefact):
            raise TypeError("filed artefact sink returned a non-Sede artefact")
        return stored

    return persist


@dataclass(slots=True)
class _DeferredSedeObservation:
    observation: FiledDeclaracionObservation
    staged: list[tuple[tuple[str, int, Period, str], FiledDeclaracionArtefact, bytes]] = field(default_factory=list)
    consumed: bool = False

    def persist_artefacts(self, sink: FiledArtefactSink) -> FiledObservationProtocol:
        """Publish captured bytes only after the caller enters its local effect fence."""
        if self.consumed or len(self.staged) != len(self.observation.artefacts):
            raise ValueError("deferred filed artefacts cannot be persisted twice or incompletely")
        if any(
            original != observed
            for (_, original, _), observed in zip(self.staged, self.observation.artefacts, strict=True)
        ):
            raise ValueError("deferred filed artefacts differ from the captured observation")
        concrete_sink = _concrete_artefact_sink(sink)
        if concrete_sink is None:
            raise ValueError("deferred filed artefacts require a persistence sink")
        self.consumed = True
        staged, self.staged = self.staged, []
        stored = tuple(concrete_sink(key, artefact, body) for key, artefact, body in staged)
        return self.observation.model_copy(update={"artefacts": stored})


@dataclass(slots=True)
class _DeferredSedeObservations:
    observations: tuple[FiledDeclaracionObservation, ...]
    staged: list[tuple[tuple[str, int, Period, str], FiledDeclaracionArtefact, bytes]] = field(default_factory=list)
    consumed: bool = False

    def persist_artefacts(self, sink: FiledArtefactSink) -> tuple[FiledObservationProtocol, ...]:
        """Publish source artefacts together after the caller enters its fence."""
        if self.consumed:
            raise ValueError("deferred source artefacts cannot be persisted twice")
        expected = tuple(artefact for observation in self.observations for artefact in observation.artefacts)
        if expected != tuple(artefact for _, artefact, _ in self.staged):
            raise ValueError("deferred source artefacts differ from captured observations")
        concrete_sink = _concrete_artefact_sink(sink)
        if concrete_sink is None:
            raise ValueError("deferred source artefacts require a persistence sink")
        self.consumed = True
        staged, self.staged = self.staged, []
        stored = iter(concrete_sink(key, artefact, body) for key, artefact, body in staged)
        return tuple(
            observation.model_copy(update={"artefacts": tuple(next(stored) for _ in observation.artefacts)})
            for observation in self.observations
        )


async def capture_deferred_sede_observation(
    register: DeclaracionesRegisterSession, declaration: Declaracion
) -> DeferredFiledObservation:
    """Stage one remote declaration without invoking a local persistence callback."""
    staged: list[tuple[tuple[str, int, Period, str], FiledDeclaracionArtefact, bytes]] = []

    def stage(
        key: tuple[str, int, Period, str], artefact: FiledDeclaracionArtefact, body: bytes
    ) -> FiledDeclaracionArtefact:
        staged.append((key, artefact, body))
        return artefact

    observation = await register.capture_observation(declaration, artefact_sink=stage)
    if not isinstance(observation, FiledDeclaracionObservation):
        raise TypeError("filed register returned a non-Sede observation")
    return _DeferredSedeObservation(observation=observation, staged=staged)


class _SedeFiledDataRegisterPort(FiledDataRegisterPort):
    """Adapt one concrete register session to the application register port."""

    def __init__(self, register: DeclaracionesRegisterSession, *, walk_timeout_ms: int) -> None:
        """Bind one already-open Sede register and its configured timeout."""
        self._register = register
        self._walk_timeout_ms = walk_timeout_ms

    @property
    @override
    def walk_timeout_ms(self) -> int:
        """Return the timeout resolved by the outer Sede composition."""
        return self._walk_timeout_ms

    @override
    async def walk(self, *, modelo: str, ejercicio: int) -> tuple[FiledRegisterDeclarationProtocol, ...]:
        """Read one register pair and expose its structural application view."""
        return await _call_adapter(
            "filed_register_walk",
            lambda: self._register.walk(modelo=modelo, ejercicio=ejercicio),
        )

    @override
    async def capture_observation(
        self,
        declaration: FiledRegisterDeclarationProtocol,
        *,
        artefact_sink: FiledArtefactSink | None = None,
    ) -> FiledObservationProtocol:
        """Capture one register row through the concrete Sede reader."""
        if not isinstance(declaration, Declaracion):
            raise TypeError("filed register port returned a non-Sede declaration")
        concrete_sink = _concrete_artefact_sink(artefact_sink)
        return await _call_adapter(
            "filed_declaration_capture",
            lambda: self._register.capture_observation(declaration, artefact_sink=concrete_sink),
        )

    @override
    async def capture_observation_deferred(
        self, declaration: FiledRegisterDeclarationProtocol
    ) -> DeferredFiledObservation:
        """Return captured bytes for a later guarded local persistence section."""
        if not isinstance(declaration, Declaracion):
            raise TypeError("filed register port returned a non-Sede declaration")
        return await _call_adapter(
            "filed_declaration_capture", lambda: capture_deferred_sede_observation(self._register, declaration)
        )


class SedeFiledDataCapturePort(FiledDataCapturePort):
    """Compose authenticated Sede register and source-capture capabilities."""

    def __init__(
        self,
        *,
        certificate_secret_backend_factory: CertificateSecretBackendFactory,
        browser_session_factory: BrowserSessionFactoryPort,
        operator_scope_ports: OperatorScopePorts,
    ) -> None:
        """Bind the required certificate-secret capability for live reads."""
        self._certificate_secret_backend_factory = certificate_secret_backend_factory
        self._browser_session_factory = browser_session_factory
        self._operator_scope_ports = operator_scope_ports

    @asynccontextmanager
    @override
    async def open_register(
        self,
        *,
        operation: str,
        authority_operation: PinnedAuthorityOperation | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> AsyncGenerator[FiledDataRegisterPort]:
        """Open one browser-backed register for the complete operation scope."""
        try:
            authority_scope = (
                nullcontext(authority_operation)
                if authority_operation is not None
                else bundled_indexed_authority().operation()
            )
            with authority_scope as indexed_operation:
                session, settings = await _call_adapter(
                    "filed_register_session",
                    lambda: active_verified_session(
                        certificate_secret_backend_factory=self._certificate_secret_backend_factory,
                        browser_session_factory=self._browser_session_factory,
                        operation=operation,
                        operator_scope_ports=self._operator_scope_ports,
                        authority_operation=indexed_operation,
                        effect_guard=effect_guard,
                        on_session_write=on_session_write,
                    ),
                )
                async with (
                    shared_playwright(session) as playwright,
                    open_declarations_register(
                        session,
                        operation=indexed_operation,
                        settings=settings,
                        playwright=playwright,
                    ) as register,
                ):
                    yield _SedeFiledDataRegisterPort(
                        register,
                        walk_timeout_ms=settings.cadrumo_live_filed_register_walk_timeout_ms,
                    )
        except (LiveApplicationError, ProfileAccessRefusedError, AutomationCustodyError, RuntimeRefusalError):
            raise
        except Exception as exc:
            raise _translate_adapter_error("filed_register_open", exc) from exc

    @override
    async def discover_availability(
        self,
        *,
        operation: str,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ):
        """Read the register option lists through the application port."""
        session, settings = await _call_adapter(
            "filed_register_session",
            lambda: active_verified_session(
                certificate_secret_backend_factory=self._certificate_secret_backend_factory,
                browser_session_factory=self._browser_session_factory,
                operation=operation,
                operator_scope_ports=self._operator_scope_ports,
                effect_guard=effect_guard,
                on_session_write=on_session_write,
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
        except (LiveApplicationError, ProfileAccessRefusedError, AutomationCustodyError, RuntimeRefusalError):
            raise
        except Exception as exc:
            raise _translate_adapter_error("filed_register_discovery", exc) from exc

    @override
    async def capture_source_observations(
        self,
        revision: ModeloRevision,
        *,
        filing_year: int,
        period: Period,
        artefact_sink: FiledArtefactSink | None = None,
        operation: str,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> tuple[FiledObservationProtocol, ...]:
        """Capture registry-selected source rows in one authenticated browser.

        Core types:
        :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
        """
        with bundled_indexed_authority().operation() as indexed_operation:
            session, settings = await _call_adapter(
                "filed_register_session",
                lambda: active_verified_session(
                    certificate_secret_backend_factory=self._certificate_secret_backend_factory,
                    browser_session_factory=self._browser_session_factory,
                    operation=operation,
                    operator_scope_ports=self._operator_scope_ports,
                    effect_guard=effect_guard,
                    on_session_write=on_session_write,
                ),
            )
            concrete_sink = _concrete_artefact_sink(artefact_sink)

            async def _capture() -> tuple[FiledObservationProtocol, ...]:
                async with shared_playwright(session) as playwright:
                    previous = await capture_previous_filing_observations(
                        session,
                        revision,
                        filing_year=filing_year,
                        period=period,
                        operation=indexed_operation,
                        settings=settings,
                        playwright=playwright,
                        artefact_sink=concrete_sink,
                    )
                    related = await capture_relation_source_observations(
                        session,
                        revision,
                        filing_year=filing_year,
                        period=period,
                        operation=indexed_operation,
                        settings=settings,
                        playwright=playwright,
                        artefact_sink=concrete_sink,
                    )
                    return previous + related

            return await _call_adapter("filed_source_capture", _capture)

    @override
    async def capture_source_observations_deferred(
        self,
        revision: ModeloRevision,
        *,
        filing_year: int,
        period: Period,
        operation: str,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> DeferredFiledObservations:
        """Stage source artefacts during remote acquisition for a later commit fence."""
        staged: list[tuple[tuple[str, int, Period, str], FiledDeclaracionArtefact, bytes]] = []

        def stage(
            key: tuple[str, int, Period, str], artefact: FiledDeclaracionArtefact, body: bytes
        ) -> FiledDeclaracionArtefact:
            staged.append((key, artefact, body))
            return artefact

        observations = await self.capture_source_observations(
            revision,
            filing_year=filing_year,
            period=period,
            artefact_sink=stage,
            operation=operation,
            effect_guard=effect_guard,
            on_session_write=on_session_write,
        )
        if not all(isinstance(observation, FiledDeclaracionObservation) for observation in observations):
            raise TypeError("filed source capture returned a non-Sede observation")
        return _DeferredSedeObservations(
            observations=cast("tuple[FiledDeclaracionObservation, ...]", observations), staged=staged
        )


__all__ = ["SedeFiledDataCapturePort", "capture_deferred_sede_observation"]
