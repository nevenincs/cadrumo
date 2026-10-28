"""The runtime host's side of a running view, for tests that drive a view across its legs.

A view's worker leg is bound the way the runtime binds it on the first
attach: the host connects to the worker's view endpoint, checks the worker
and reads the view's bind, and hands the leg to the relay. The worker here
is this process, as in the relay's own tests.
"""

from __future__ import annotations

import time
from pathlib import Path
from uuid import uuid4

from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.view_stream import ViewWorkerBind
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity

from ..view_stream_relay import ViewStreamRelay, open_worker_view_leg
from .test_view_stream_relay import _same_process_worker

_LISTEN_SECONDS = 30.0


def synthetic_worker_identity() -> ProfileWorkerIdentity:
    """A profile worker's identity for a profile no store holds."""
    return ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="synthetic-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
    )


def bind_worker_leg(
    relay: ViewStreamRelay, *, storage_root: Path, identity: ProfileWorkerIdentity, product_version: str
) -> ViewWorkerBind:
    """Open the worker leg of the view the worker listens for and bind it to ``relay``.

    The worker's endpoint listens from the moment its view opens its stream;
    until then the host is told no view runs, and it asks again.
    """
    deadline = time.monotonic() + _LISTEN_SECONDS
    while True:
        try:
            bind, channel = open_worker_view_leg(
                storage_root=storage_root,
                identity=identity,
                verify=_same_process_worker,
                product_version=product_version,
            )
        except ProfileAccessRefusedError as refused:
            if refused.reason is not AccessDenialCode.OPERATION_UNAVAILABLE or time.monotonic() >= deadline:
                raise
            time.sleep(0.05)
            continue
        relay.bind_worker(profile_id=identity.binding.profile_id, bind=bind, channel=channel)
        return bind


__all__ = ["bind_worker_leg", "synthetic_worker_identity"]
