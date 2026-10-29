"""Service-owned provider administration and contained hosted-agent lifecycle."""

from __future__ import annotations

import asyncio
import contextlib
import json
from time import monotonic
from typing import Any, cast, override

import httpx

from cadrumo_client.contracts.deadline_budget import (
    DEFAULT_TIMEOUT_POLICY,
    TimeoutDeadline,
)

from .adapters.agent_background_runs import BackgroundRunEndpoint
from .adapters.provider_catalog_metadata import DECLARED_CATALOG_KIND
from .contracts import HostedCertificationStatus
from .host.controller import (
    AgentHostController,
    AgentHostError,
    AgentHostRefusal,
    AgentReady,
)
from .host.credential_frame import wipe
from .providers.application.model_runs import ModelRunService
from .providers.application.ports import ProviderCatalogUnavailableError, ProviderCatalogUnavailableReason
from .providers.domain.catalog import MAX_CATALOG_LANES
from .service_scheduling import AgentServiceScheduling
from .service_support import (
    HOSTED_CERTIFICATION_CACHE_SECONDS,
    controller_is_ready,
    without_lanes,
)


class AgentService(AgentServiceScheduling):
    """Own one profile's contained tree and masked provider administration."""

    @override
    def _picker_catalog(self, document: dict[str, Any]) -> dict[str, Any]:
        """Drop the lanes the signed-in profile turned off, so the picker never offers them.

        Only stored settings are read; no provider program is probed. Without a
        lease, or when the settings cannot be read, the catalog is returned
        unchanged: an off lane still resolves no credential for the agent.
        """
        if self.client.lease is None:
            return document
        turned_off = self._providers.turned_off_lanes()
        if turned_off is None or not turned_off:
            return document
        if document.get("kind") == DECLARED_CATALOG_KIND:
            declared: object = document.get("catalog")
            if not isinstance(declared, dict):
                return document
            # A declared lane names its provider identity ``provider``.
            return {
                **document,
                "catalog": without_lanes(cast(dict[str, object], declared), turned_off, provider_field="provider"),
            }
        return without_lanes(document, turned_off, provider_field="provider_id")

    @override
    def _served_catalog(self, ready: AgentReady) -> dict[str, Any]:
        """Read one bounded declaration under the current tree, waking on close or timeout."""
        deadline = DEFAULT_TIMEOUT_POLICY.deadline()
        if self._read_cancellation.is_set():
            raise AgentHostError(AgentHostRefusal.CANCELLED)
        try:
            document = asyncio.run(self._read_served_catalog(ready, deadline))
            if self._read_cancellation.is_set():
                raise AgentHostError(AgentHostRefusal.CANCELLED)
            if self._controller is None or self._controller.published() != ready:
                raise ValueError("catalog_generation_changed")
            return document
        except asyncio.CancelledError as error:
            raise AgentHostError(AgentHostRefusal.CANCELLED) from error
        except TimeoutError as error:
            raise AgentHostError(AgentHostRefusal.TIMEOUT) from error
        except (httpx.HTTPError, OSError, ValueError) as error:
            if self._read_cancellation.is_set():
                raise AgentHostError(AgentHostRefusal.CANCELLED) from error
            raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_FAILED) from error

    async def _read_served_catalog(self, ready: AgentReady, deadline: TimeoutDeadline) -> dict[str, Any]:
        """Own cancellable socket I/O; no blocked reader thread survives a closed service."""
        loop = asyncio.get_running_loop()
        task = asyncio.current_task()
        if task is None:
            raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_FAILED)

        def cancelled() -> None:
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(task.cancel)

        release = self._read_cancellation.subscribe(cancelled)
        try:
            if self._read_cancellation.is_set():
                raise asyncio.CancelledError
            async with asyncio.timeout(deadline.remaining_seconds()):
                # The public transport avoids client-level URL logging of the private workspace.
                async with httpx.AsyncHTTPTransport(trust_env=False, retries=0) as transport:
                    request = httpx.Request(
                        "GET",
                        f"http://127.0.0.1:{ready.gateway_port}/v1/provider-catalog",
                        params={"workspace_root": str(self._workspace)},
                        headers={
                            "Authorization": "Bearer " + self._gateway_bearer.decode("ascii"),
                            "Accept": "application/json",
                            "Accept-Encoding": "identity",
                        },
                        extensions={"timeout": {"connect": None, "read": None, "write": None, "pool": None}},
                    )
                    response = await transport.handle_async_request(request)
                    try:
                        if response.status_code != 200:
                            raise ValueError("catalog_unavailable")
                        payload = bytearray()
                        async for chunk in response.aiter_raw(chunk_size=4096):
                            payload += chunk
                            if len(payload) > 256 * 1024:
                                raise ValueError("catalog_unavailable")
                    finally:
                        await response.aclose()
                raw_document: object = json.loads(payload)
                if not isinstance(raw_document, dict):
                    raise ValueError("catalog_malformed")
                document = cast(dict[str, object], raw_document)
                if document.get("api_version") != "v1" or not isinstance(document.get("providers"), list):
                    raise ValueError("catalog_malformed")
                return document
        finally:
            release()

    @override
    def _live_catalog(self) -> dict[str, Any] | None:
        """Return the ready agent's served catalogue, or ``None`` when no agent is ready or it does not answer.

        A model list change and a lane lookup read it beside the declared
        catalogue; without it they read the declared catalogue alone. The read
        is bound to the generation it was asked of, as every served read is.
        """
        controller = self._controller
        if self._closing.is_set() or self.client.lease is None or controller is None or self._workspace is None:
            return None
        if not controller_is_ready(controller):
            return None
        ready = controller.published()
        if ready is None:
            return None
        try:
            return self._served_catalog(ready)
        except ProviderCatalogUnavailableError:
            return None

    def _certification_current(self, controller: AgentHostController, expected: AgentReady) -> bool:
        ready = controller.published()
        return not (
            ready is None
            or ready != expected
            or self._closing.is_set()
            or self._controller is not controller
            or not controller_is_ready(controller)
        )

    @override
    def _hosted_certifications(self) -> list[dict[str, str]]:
        """Return only a recently served snapshot bound to the controller's current generations."""
        controller = self._controller
        if self._closing.is_set() or controller is None or not controller_is_ready(controller):
            self._clear_hosted_certifications()
            return []
        with self._hosted_certification_lock:
            snapshot = self._hosted_certification_snapshot
            if (
                snapshot is None
                or snapshot[0] is not controller
                or monotonic() - snapshot[3] >= HOSTED_CERTIFICATION_CACHE_SECONDS
            ):
                self._hosted_certification_snapshot = None
                return []
            certifications = snapshot[2]
        if not self._certification_current(controller, snapshot[1]):
            self._clear_hosted_certifications()
            return []
        with self._hosted_certification_lock:
            if self._hosted_certification_snapshot is not snapshot:
                return []
        return [certification.model_dump(mode="json") for certification in certifications]

    @override
    def _remember_hosted_certifications(
        self, controller: AgentHostController, ready: AgentReady, document: dict[str, Any]
    ) -> None:
        """Cache bounded facts only after the existing authenticated catalog request succeeds."""
        lanes: object = document.get("providers")
        certifications: tuple[HostedCertificationStatus, ...] = ()
        if isinstance(lanes, list) and len(cast(list[object], lanes)) <= MAX_CATALOG_LANES:
            parsed: list[HostedCertificationStatus] = []
            seen: set[tuple[str, str]] = set()
            try:
                for raw_lane in cast(list[object], lanes):
                    certification = HostedCertificationStatus.model_validate(raw_lane, strict=True)
                    identity = (certification.provider, certification.transport)
                    if identity in seen:
                        return
                    seen.add(identity)
                    parsed.append(certification)
            except (TypeError, ValueError):
                parsed = []
            certifications = tuple(parsed)
        with self._hosted_certification_lock:
            if self._closing.is_set() or self._controller is not controller or not controller_is_ready(controller):
                self._hosted_certification_snapshot = None
                return
            self._hosted_certification_snapshot = (controller, ready, certifications, monotonic())

    @override
    def _clear_hosted_certifications(self) -> None:
        """Forget every cached hosted fact when its source may no longer be observed."""
        with self._hosted_certification_lock:
            self._hosted_certification_snapshot = None

    @override
    def _background_endpoint(self) -> BackgroundRunEndpoint | None:
        """Return the ready agent's gateway while this service holds a lease and is not closing."""
        controller = self._controller
        workspace = self._workspace
        if self._closing.is_set() or self.client.lease is None or controller is None or workspace is None:
            return None
        ready = controller.published()
        return None if ready is None else BackgroundRunEndpoint(port=ready.gateway_port, workspace_root=workspace)

    def model_runs(self) -> ModelRunService | None:
        """Return the profile's run service while this service holds a lease and is not closing."""
        if self._closing.is_set() or self.client.lease is None:
            return None
        return self._model_runs

    def runtime_changed(self) -> None:
        """Forget observed generations: a pushed frame may mean a new lease or a retired session."""
        self._store.invalidate_generations()
        self._forget_reads()

    def observe(self) -> bool:
        """Revalidate exact generations: replace a superseded tree, or answer ``False`` for the caller to retire it."""
        with self._guard:
            if self._auth_attempt is not None and not self._auth_attempt.active:
                resume_valid = self._auth_resume_valid
                self._auth_resume_valid = None
                if resume_valid is not None and resume_valid():
                    self._background_start()
            if self._controller is None:
                return self._store.observe_generations() is not None
            return self._controller.published() is not None or self._replace_superseded()

    @override
    def stop(self, *, deadline: TimeoutDeadline | None = None) -> None:
        """Confirm contained shutdown before releasing the tree's ownership."""
        with self._guard:
            preparation = self._preparation_runner
            if preparation is not None:
                preparation.settle()
                self._preparation_runner = None
            controller = self._controller
            if controller is not None:
                self._clear_hosted_certifications()
                if deadline is None:
                    controller.stop()
                else:
                    controller.stop(deadline=deadline)
                self._controller = None
                self._forget_reads()
                self._emit({"event": "stopped", "code": "agent_retired"})

    def close(self) -> None:
        """Settle process containment before releasing the exclusive reservation."""
        try:
            self.request_close()
        finally:
            try:
                failure: BaseException | None = None
                for settle in (self.stop, self._catalog.close, self._login_status.close):
                    try:
                        settle()
                    except BaseException as error:
                        failure = error if failure is None else failure
                if failure is not None:
                    raise failure
                if self._auth_attempt is not None:
                    self._auth_attempt.close()
                for thread in (self._start_thread, self._stop_thread):
                    if thread is not None:
                        thread.join()
                self._ownership.close()
                self._owned = False
            finally:
                wipe(self._gateway_bearer)
                wipe(self._host_token)

    def request_close(self) -> None:
        """Invalidate startup publication immediately without waiting on lifecycle work."""
        self._closing.set()
        cancellation = self._startup_cancellation
        if cancellation is not None:
            cancellation.cancel()
        self._catalog.request_close()
        self._read_cancellation.cancel()
        controller = self._controller
        if controller is not None:
            controller.cancel_start()
        if self._auth_attempt is not None:
            self._auth_attempt.cancel()
        self._clear_hosted_certifications()
        self.client.lease = None
        self.client.connection.close()
