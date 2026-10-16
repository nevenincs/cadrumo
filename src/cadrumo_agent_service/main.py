"""Dedicated hosted-agent service entrypoint; no taxpayer command-line doors."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from threading import Event, Lock, Thread
from uuid import UUID

from cadrumo.core.diagnostic_log import diagnostic_process
from cadrumo.core.logging import configure_logging, register_first_party_logger
from cadrumo.core.paths import effective_storage_root

from .admin import AdminServer
from .contracts import ServiceStartupFrame
from .host.credential_frame import wipe
from .installed_client import SERVICE_ID, open_service_client
from .service import AgentService, service_failure

_OUTPUT_GUARD = Lock()
_MAX_STARTUP_FRAME_BYTES = 64 * 1024


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
    parser = argparse.ArgumentParser(prog=SERVICE_ID, description=__doc__)
    parser.add_argument("command", choices=("serve",))
    parser.add_argument("--profile-id", required=True, type=UUID)
    parser.add_argument("--agent-source")
    args = parser.parse_args()
    bearer = bytearray()
    gateway_bearer = bytearray()
    service = None
    server = None
    client = None
    stop = Event()
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
        client = asyncio.run(open_service_client(profile_id=args.profile_id, storage_root=effective_storage_root()))
        service = AgentService(
            client=client,
            storage_root=effective_storage_root(),
            agent_source=args.agent_source,
            gateway_bearer=gateway_bearer,
            emit=_publish,
        )
        server = AdminServer(service, bearer=bearer)
        # The runtime pushes a frame on this connection for every lease issue or
        # withdrawal and every retired session; nothing else changes what a claim
        # answers, so each push, or the connection's loss, is the only reason to
        # claim again.
        wake = Event()

        def runtime_changed() -> None:
            service.runtime_changed()
            wake.set()

        client.subscribe_changes(runtime_changed)

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
            lease = client.claim()
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
