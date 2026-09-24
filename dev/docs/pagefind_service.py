"""A Pagefind service whose response reader does not sleep before each response.

The Pagefind Python client reads the indexer's responses in a loop that sleeps
0.1 s before every read. Its ``readuntil`` already waits for data, so the sleep
adds nothing but latency, and it caps the whole index at ten responses a second.
Injecting the search records costs one response each, so a root's injection
spent most of its time asleep.

This service reads responses as they arrive and dispatches them exactly as the
client does. It is used through the client's public ``create_index``, so every
request still goes through the client's own ``send``.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import cast, override

from pagefind.service import PagefindService
from pagefind.service.types import InternalResponsePayload, InternalResponseType

log = logging.getLogger(__name__)


class ResponsivePagefindService(PagefindService):
    """Pagefind's service with a reader that dispatches each response as it arrives."""

    @override
    async def _wait_for_responses(self) -> None:
        stdout = self._backend.stdout
        if stdout is None:
            raise RuntimeError("the Pagefind indexer was launched without a readable stdout")
        while True:
            output = await stdout.readuntil(b",")
            response = json.loads(base64.b64decode(output[:-1]))
            if response is None:
                continue
            message_id = response.get("message_id")
            original = response["payload"].get("original_message")
            # A request the indexer could not parse comes back without its id but
            # with the original message, which carries it.
            if message_id is None and original is not None and (sent := json.loads(original)) is not None:
                message_id = sent.get("message_id")
            if message_id is None:
                continue
            future = self._responses.get(message_id)
            if future is None:
                log.debug("no receiving future for Pagefind message %s", message_id)
                continue
            payload = response["payload"]
            if payload["type"] == InternalResponseType.ERROR.value:
                future.set_exception(Exception(payload["message"], payload.get("original_message")))
            else:
                future.set_result(cast(InternalResponsePayload, payload))
