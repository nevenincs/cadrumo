"""Live sync runner orchestrating fetch, validate, classify, dispatch, and persist.

The runner composes a small set of collaborators (certificate
preloader, local catalogue loader, live fetcher, validator, classifier,
dispatcher, and repository). It orchestrates
a single run and returns a :class:`SyncRunResult` describing what
happened.

The runner is **read-only** against AEAT. No form submissions, no
server-side mutation, no retries beyond transient navigation errors —
healing always targets local state.

The live-payload fetch contract is abstracted behind
:class:`LivePayloadFetcher` so the runner can be driven by a concrete
in-test fetcher or by a production fetcher that drives a Playwright
session.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from ...adapters.outbound.aeat.browser import BrowserSession
from ...core.logging import get_logger
from ...domain.sync import (
    CertificateContextPreloader,
    DivergenceClassifier,
    DivergenceRecord,
    LocalCatalogueLoader,
    ModeloIdentifier,
    SyncError,
    WireFilingHistory,
    WireModeloDefinition,
    WirePortalManifest,
    WireValidationError,
    WireValidator,
)
from ._dispatcher import HealingDispatcher, HealingPlan
from ._repository import DivergenceRecordRepository
from ._strategies import HealingStrategy, StrategyOutcome

_LOGGER = get_logger(__name__)


class SyncRunResult(BaseModel):
    """Frozen summary of one :meth:`LiveSyncRunner.run` invocation.

    Attributes:
        started_at: UTC timestamp when the run began.
        finished_at: UTC timestamp when the run returned.
        modelo: Optional :class:`ModeloIdentifier` the run scoped to.
        period: Optional filing period filter for the run.
        auto_heal: Whether the dispatcher was allowed to apply
            allowlisted additive healing.
        plan: The :class:`HealingPlan` produced by the dispatcher.
        outcomes: Per-record :class:`StrategyOutcome` tuple.
        divergence_records: The persisted divergence records this run
            produced.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    started_at: datetime
    finished_at: datetime
    modelo: ModeloIdentifier | None
    period: str | None
    auto_heal: bool
    plan: HealingPlan
    outcomes: tuple[StrategyOutcome, ...]
    divergence_records: tuple[DivergenceRecord, ...]


@runtime_checkable
class LivePayloadFetcher(Protocol):
    """Fetches live AEAT payloads against the validated browser session.

    Concrete implementations drive a Playwright session against the
    AEAT portal. The runner accepts any object conforming to this
    Protocol so in-test fetchers (real concrete Python classes, no
    mocks) can supply synthetic payloads.
    """

    async def fetch_modelo_raw(
        self,
        *,
        session: BrowserSession,
        modelo: ModeloIdentifier,
    ) -> bytes:
        """Return the raw payload bytes for the live modelo definition."""

    async def fetch_portal_manifest_raw(
        self,
        *,
        session: BrowserSession,
    ) -> bytes:
        """Return the raw payload bytes for the live portal link manifest."""

    async def fetch_filing_history_raw(
        self,
        *,
        session: BrowserSession,
        modelo: ModeloIdentifier,
    ) -> bytes:
        """Return the raw payload bytes for the live filing history."""


class LiveSyncRunner:
    """Orchestrates a single live-to-local sync cycle.

    The runner is composed of small, narrow Protocol-typed
    collaborators (cf. :class:`CertificateContextPreloader`,
    :class:`LocalCatalogueLoader`, :class:`LivePayloadFetcher`) plus the :class:`WireValidator`,
    :class:`DivergenceClassifier`, :class:`HealingDispatcher` and
    :class:`DivergenceRecordRepository` concrete sub-systems.
    """

    def __init__(
        self,
        *,
        browser_session: BrowserSession,
        certificate_backend: CertificateContextPreloader,
        local_loader: LocalCatalogueLoader,
        fetcher: LivePayloadFetcher,
        validator: WireValidator,
        classifier: DivergenceClassifier,
        dispatcher: HealingDispatcher,
        repository: DivergenceRecordRepository,
        strategies: tuple[HealingStrategy, ...],
        retry_max: int,
        retry_backoff_s: float,
    ) -> None:
        self._session = browser_session
        self._cert = certificate_backend
        self._local = local_loader
        self._fetcher = fetcher
        self._validator = validator
        self._classifier = classifier
        self._dispatcher = dispatcher
        self._repository = repository
        self._strategies = strategies
        self._retry_max = retry_max
        self._retry_backoff_s = retry_backoff_s

    async def run(
        self,
        *,
        modelo: ModeloIdentifier | None = None,
        period: str | None = None,
        auto_heal: bool = False,
    ) -> SyncRunResult:
        """Run one sync cycle.

        Args:
            modelo: Optional modelo to scope the run. If ``None`` the
                runner walks the portal manifest only.
            period: Optional filing period filter.
            auto_heal: Whether to let the dispatcher apply
                allowlisted additive healing. The bounded-policy
                invariant means BREAKING and SUSPICIOUS records never
                auto-apply even when ``True``.

        Returns:
            A :class:`SyncRunResult` summarising the run.

        Raises:
            SyncError: On unrecoverable failures (cert preload, fetch
                exhaustion, wire validation).
        """
        started_at = datetime.now(tz=UTC)
        _LOGGER.info(
            "sync run starting modelo=%s period=%s auto_heal=%s",
            modelo,
            period,
            auto_heal,
        )

        try:
            await self._cert.preload_into_browser_context(self._session)
        except Exception as exc:
            raise SyncError(f"Failed to preload certificate: {exc}") from exc

        records: list[DivergenceRecord] = []

        if modelo is not None:
            records.extend(await self._run_modelo(modelo=modelo))
        records.extend(await self._run_portal_manifest())
        if modelo is not None:
            records.extend(await self._run_filing_history(modelo=modelo))

        plan, outcomes = await self._dispatcher.dispatch(
            tuple(records),
            auto_heal=auto_heal,
        )
        persisted: list[DivergenceRecord] = []
        for outcome in outcomes:
            self._repository.save(outcome.record)
            persisted.append(outcome.record)

        finished_at = datetime.now(tz=UTC)
        _LOGGER.info(
            "sync run finished modelo=%s auto_heal=%d escalate=%d benign=%d",
            modelo,
            len(plan.auto_heal),
            len(plan.escalate),
            len(plan.benign),
        )
        return SyncRunResult(
            started_at=started_at,
            finished_at=finished_at,
            modelo=modelo,
            period=period,
            auto_heal=auto_heal,
            plan=plan,
            outcomes=outcomes,
            divergence_records=tuple(persisted),
        )

    async def _run_modelo(
        self,
        *,
        modelo: ModeloIdentifier,
    ) -> tuple[DivergenceRecord, ...]:
        raw = await self._fetch_with_retry(lambda: self._fetcher.fetch_modelo_raw(session=self._session, modelo=modelo))
        live = self._validator.validate(raw, WireModeloDefinition)
        local_obj = self._local.load_modelo(modelo)
        if not isinstance(local_obj, WireModeloDefinition):
            raise WireValidationError(f"Local modelo snapshot for {modelo} is not a WireModeloDefinition")
        return self._classifier.diff_modelo(local=local_obj, live=live)

    async def _run_portal_manifest(self) -> tuple[DivergenceRecord, ...]:
        raw = await self._fetch_with_retry(lambda: self._fetcher.fetch_portal_manifest_raw(session=self._session))
        live = self._validator.validate(raw, WirePortalManifest)
        local_obj = self._local.load_portal_manifest()
        if not isinstance(local_obj, WirePortalManifest):
            raise WireValidationError("Local portal manifest is not a WirePortalManifest")
        return self._classifier.diff_portal_manifest(local=local_obj, live=live)

    async def _run_filing_history(
        self,
        *,
        modelo: ModeloIdentifier,
    ) -> tuple[DivergenceRecord, ...]:
        raw = await self._fetch_with_retry(
            lambda: self._fetcher.fetch_filing_history_raw(session=self._session, modelo=modelo)
        )
        live = self._validator.validate(raw, WireFilingHistory)
        local_obj = self._local.load_filing_history(modelo)
        if not isinstance(local_obj, WireFilingHistory):
            raise WireValidationError(f"Local filing history for {modelo} is not a WireFilingHistory")
        return self._classifier.diff_filing_history(local=local_obj, live=live)

    async def _fetch_with_retry[T](self, operation: Callable[[], Awaitable[T]]) -> T:
        """Retry an async fetch with exponential backoff up to ``retry_max``.

        Only transient exceptions are retried; validation errors bubble
        up immediately.
        """
        last_exc: Exception | None = None
        delay = self._retry_backoff_s
        for attempt in range(1, self._retry_max + 1):
            try:
                return await operation()
            except WireValidationError:
                raise
            except Exception as exc:
                last_exc = exc
                _LOGGER.warning(
                    "fetch attempt %d/%d failed: %s",
                    attempt,
                    self._retry_max,
                    exc,
                )
                if attempt == self._retry_max:
                    break
                await asyncio.sleep(delay)
                delay *= 2.0
        raise SyncError(f"Exhausted {self._retry_max} fetch attempts: {last_exc}") from last_exc
