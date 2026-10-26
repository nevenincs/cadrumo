"""Dedicated hosted-agent service entrypoint; no taxpayer command-line doors."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from threading import Event, Lock, Thread
from time import monotonic, time
from uuid import UUID

import psutil

from cadrumo.core.diagnostic_log import diagnostic_process
from cadrumo.core.logging import configure_logging, get_logger, register_first_party_logger
from cadrumo.core.paths import effective_storage_root
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from .admin import AdminServer
from .contracts import ServiceStartupFrame
from .host.credential_frame import wipe
from .host.model_run_relay import ModelRunRelay
from .installed_client import SERVICE_ID, open_service_client
from .service import AgentService, service_failure

_LOGGER = get_logger(__name__)
_OUTPUT_GUARD = Lock()
_MAX_STARTUP_FRAME_BYTES = 64 * 1024
_CLAIM_RETRY_SECONDS = 1.0


def _process_uptime() -> float:
    """Diagnostic only: failure to inspect this process cannot refuse service."""
    try:
        return max(0.0, time() - float(psutil.Process().create_time()))
    except psutil.Error:
        return -1.0


def _read_startup_frame(stdin_fd: int) -> bytearray:
    """Read one bounded startup line without buffering past its newline."""
    line = bytearray()
    while len(line) <= _MAX_STARTUP_FRAME_BYTES:
        part = os.read(stdin_fd, 1)
        if not part:
            break
        line.extend(part)
        if part == b"\n":
            break
    return line


def _publish(document: dict[str, object]) -> None:
    with _OUTPUT_GUARD:
        sys.stdout.write(json.dumps(document, separators=(",", ":")) + "\n")
        sys.stdout.flush()


def main() -> None:
    """Serve provider administration and a person-approved hosted agent until EOF."""
    register_first_party_logger("cadrumo_agent_service")
    register_first_party_logger("cadrumo_agent")
    configure_logging()
    with diagnostic_process("extension_service"):
        _serve()


def _serve() -> None:
    entered = monotonic()
    parser = argparse.ArgumentParser(prog=SERVICE_ID, description=__doc__)
    parser.add_argument("command", choices=("serve",))
    parser.add_argument("--profile-id", required=True, type=UUID)
    args = parser.parse_args()
    bearer = bytearray()
    gateway_bearer = bytearray()
    service = None
    server = None
    client = None
    relay = None
    stop = Event()
    wake = Event()
    try:
        stdin_fd = sys.stdin.fileno()
        line = _read_startup_frame(stdin_fd)
        try:
            if len(line) > _MAX_STARTUP_FRAME_BYTES or not line.endswith(b"\n"):
                raise ValueError("invalid_startup_frame")
            frame = ServiceStartupFrame.model_validate_json(line)
            bearer = bytearray(frame.bearer, "ascii")
            gateway_bearer = bytearray(frame.gateway_bearer, "ascii")
            del frame
        finally:
            wipe(line)
        connecting = monotonic()
        client = asyncio.run(open_service_client(profile_id=args.profile_id, storage_root=effective_storage_root()))
        connected_at = monotonic()
        service = AgentService(
            client=client,
            storage_root=effective_storage_root(),
            gateway_bearer=gateway_bearer,
            emit=_publish,
            wake=wake.set,
        )
        server = AdminServer(service, bearer=bearer)
        # The runtime pushes a frame on this connection for every lease issue or
        # withdrawal and every retired session. Auth-helper settlement also wakes
        # this owner, which reclaims authority before resuming the hosted agent.

        def runtime_changed() -> None:
            service.runtime_changed()
            wake.set()

        client.subscribe_changes(runtime_changed)
        relay = ModelRunRelay(client=client, runs=service.model_runs)
        client.subscribe_model_runs(relay.announce)

        # Native keeps stdin open and owns the complete service/agent process tree.
        def lifetime_ended() -> None:
            try:
                # Do not use BufferedReader in this daemon: it may stay blocked
                # after runtime revocation exits the service, and Python then
                # cannot acquire its stdin lock during interpreter shutdown.
                os.read(stdin_fd, 1)
            except OSError:
                # A closed or invalid parent pipe has the same lifetime meaning
                # as EOF. The final cleanup path still owns service teardown.
                pass
            finally:
                try:
                    service.request_close()
                finally:
                    stop.set()
                    wake.set()

        Thread(target=lifetime_ended, name="agent-service-lifetime", daemon=True).start()
        connected = client.connected
        if connected is None:
            raise RuntimeError("service_connection_unavailable")
        _LOGGER.info(
            "agent service ready startup_frame_seconds=%.3f runtime_connection_seconds=%.3f "
            "since_entry_seconds=%.3f process_uptime_seconds=%.3f",
            connecting - entered,
            connected_at - connecting,
            monotonic() - entered,
            _process_uptime(),
        )
        _publish(
            {
                "event": "service_ready",
                "protocol": 1,
                "admin_port": server.port,
                "runtime_boot_id": str(connected.runtime_boot_id),
                "connection_id": str(connected.connection_id),
                "profile_id": str(connected.profile_id),
                "service_id": SERVICE_ID,
            }
        )
        admitted = False
        started = False
        while not stop.is_set():
            # Clear before claiming, so a push that lands during the claim wakes the next turn.
            wake.clear()
            try:
                lease = client.claim()
            except RefusalError as error:
                # A claim that ran out of time while the connection stayed open
                # was queued behind another exchange: the admission stands and
                # the tree keeps running. One that closed the connection ended
                # the admission with it.
                if error.reason is not RefusalCode.DEADLINE_EXCEEDED or client.connection.closed:
                    raise
                _LOGGER.warning("agent service lease claim overran; claiming again")
                wake.wait(_CLAIM_RETRY_SECONDS)
                continue
            if lease is None:
                if admitted:
                    break
            else:
                admitted = True
                if not started:
                    try:
                        result = service.start()
                        if result["event"] != "agent_ready":
                            _publish(result)
                    except Exception as error:
                        _publish(service_failure(error))
                    started = True
                elif not service.observe():
                    service.stop()
            wake.wait()
    except Exception as error:
        _publish(service_failure(error))
    finally:
        cleanup_failed = False
        if relay is not None:
            relay.close()
        if service is not None:
            try:
                service.request_close()
            except Exception:
                cleanup_failed = True
        if server is not None:
            try:
                server.close()
            except Exception:
                cleanup_failed = True
        if service is not None:
            try:
                service.close()
            except Exception:
                cleanup_failed = True
        try:
            if client is not None:
                asyncio.run(client.close())
        except Exception:
            cleanup_failed = True
        finally:
            wipe(bearer)
            wipe(gateway_bearer)
        if cleanup_failed:
            _publish({"event": "refused", "code": "cleanup_unconfirmed"})
            raise SystemExit(1)
        _publish({"event": "stopped"})


if __name__ == "__main__":
    main()
