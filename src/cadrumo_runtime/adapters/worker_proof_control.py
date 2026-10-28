"""Retained exact-attempt cancellation independent of the worker proof exchange."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from queue import Queue
from threading import Event, Thread
from typing import Literal
from uuid import UUID, uuid4

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frame_io import read_document, write_document
from cadrumo_runtime.contracts.profile_worker import ProfileWorkerProofAcknowledged
from cadrumo_runtime.contracts.profile_worker import ProfileWorkerProofControl as ProofControlRequest

from .profile_worker_operation_client import ProfileWorkerOperationClient


@dataclass
class _ProofCommand:
    request: ProofControlRequest
    deadline: float
    finished: Event = field(default_factory=Event)
    failure: BaseException | None = None


class ProfileWorkerProofControl(ProfileWorkerOperationClient):
    """One owned sender handles only identity-bound proof lifecycle messages."""

    _proof_failure: BaseException | None = None

    def _start_proof_dispatcher(self) -> None:
        self._proof_commands = Queue()
        thread = Thread(target=self._dispatch_proof_commands, name="profile-proof-control", daemon=True)
        thread.start()
        self._proof_dispatch_thread = thread

    def _dispatch_proof_commands(self) -> None:
        commands, channel = self._proof_commands, self._proof_channel
        if commands is None or channel is None:
            self._proof_failure = RefusalError(RefusalCode.CONNECTION_CLOSED)
            self._stopping.set()
            return
        failure: BaseException | None = None
        while True:
            command = commands.get()
            if command is None:
                return
            try:
                if failure is not None:
                    raise failure
                write_document(channel, command.request, deadline=command.deadline)
                reply = read_document(channel, ProfileWorkerProofAcknowledged, deadline=command.deadline)
                if (
                    reply.identity != self.identity
                    or reply.request_id != command.request.request_id
                    or reply.proof_attempt_id != command.request.proof_attempt_id
                ):
                    raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            except BaseException as error:
                command.failure = failure = self._proof_failure = error
                self._stopping.set()
                try:
                    self._retire_failed_exchange(error, command.deadline)
                except BaseException as retained:
                    command.failure = failure = self._proof_failure = retained
            finally:
                command.finished.set()

    def _proof_command(
        self, action: Literal["register", "cancel", "finish"], attempt_id: UUID, *, deadline: float, wait: bool = True
    ) -> None:
        commands = self._proof_commands
        if self._stopping.is_set() or commands is None or self._proof_failure is not None:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        command = _ProofCommand(
            ProofControlRequest(action=action, request_id=uuid4(), proof_attempt_id=attempt_id), deadline
        )
        commands.put_nowait(command)
        if not wait:
            return
        if not command.finished.wait(timeout=max(0.0, deadline - time.monotonic())):
            self._stopping.set()
            raise RefusalError(RefusalCode.TIMEOUT)
        if command.failure is not None:
            raise command.failure

    def _cancel_proof_attempt(self, attempt_id: UUID, *, deadline: float) -> None:
        """Queue a cancellation while the caller holds its admission fence."""
        if not self._stopping.is_set() and self._proof_commands is not None:
            try:
                self._proof_command("cancel", attempt_id, deadline=deadline, wait=False)
            except RefusalError:
                # A lost worker is already fenced; cancellation cannot revive it.
                return
