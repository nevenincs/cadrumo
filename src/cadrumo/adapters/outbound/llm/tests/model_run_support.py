"""A recording stand-in for the agent service behind the model-run port.

Unit tests of the LLM client use it in place of the runtime and service, which
are exercised by their own integration tests. It records every lookup and run
it receives, so "the document reached the service" stays an observation, and
answers with scripted replies or a scripted refusal. It applies the service's
own consent rule, shared through the run header: a run on a lane that reads
off-host without consent for that lane is refused ``consent_missing``, as the
service refuses it before anything goes to the agent.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from queue import Queue

from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunHeader,
    ModelRunLane,
    ModelRunMediaKind,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
)

from .....application.operations.model_runs import bound_model_runs
from .....core.model_roles import ModelRole

DEFAULT_LANE = ModelRunLane(
    provider_id="example",
    transport="api",
    model="example-model-1",
    reads_off_host=True,
)


class RecordingModelRuns:
    """Answer lookups with one lane and runs with scripted replies, recording both."""

    def __init__(
        self,
        *,
        replies: Sequence[str] = ("{}",),
        lane: ModelRunLane = DEFAULT_LANE,
        lookup_refusal: ModelRunRefusalCode | None = None,
        run_refusal: ModelRunRefusalCode | None = None,
        served_lane: ModelRunLane | None = None,
        answer: Callable[[ModelRunBody], str] | None = None,
    ) -> None:
        self._replies = list(replies)
        self._answer = answer
        self._lane = lane
        self._served = served_lane or lane
        self._lookup_refusal = lookup_refusal
        self._run_refusal = run_refusal
        self.lookups: list[ModelRole] = []
        self.runs: list[tuple[ModelRunHeader, ModelRunBody]] = []
        self.bodies: Queue[str] = Queue()

    async def lookup(self, role: ModelRole) -> ModelRunLane | ModelRunRefusal:
        self.lookups.append(role)
        if self._lookup_refusal is not None:
            return ModelRunRefusal(code=self._lookup_refusal)
        return self._lane

    async def run(self, header: ModelRunHeader, body: ModelRunBody) -> ModelRunOutput | ModelRunRefusal:
        self.runs.append((header, body))
        self.bodies.put(body.model_dump_json())
        if not header.consent_admits(self._lane):
            # The service's own rule: nothing is sent on a lane the run's consent does not admit.
            return ModelRunRefusal(code=ModelRunRefusalCode.CONSENT_MISSING)
        if self._run_refusal is not None:
            return ModelRunRefusal(code=self._run_refusal)
        if self._answer is not None:
            text = self._answer(body)
        else:
            text = self._replies.pop(0) if len(self._replies) > 1 else self._replies[0]
        return ModelRunOutput(
            text=text,
            provider_id=self._served.provider_id,
            transport=self._served.transport,
            model=self._served.model,
            agent_version="0.0.0-test",
        )


@contextmanager
def serving_agent(
    *,
    replies: Sequence[str] = ("{}",),
    lane: ModelRunLane = DEFAULT_LANE,
    lookup_refusal: ModelRunRefusalCode | None = None,
    run_refusal: ModelRunRefusalCode | None = None,
    answer: Callable[[ModelRunBody], str] | None = None,
) -> Generator[RecordingModelRuns]:
    """Bind a recording service for the current context, as a running operation would.

    ``answer``, when given, authors each reply from the run body it answers,
    in place of the scripted ``replies``.
    """
    port = RecordingModelRuns(
        replies=replies, lane=lane, lookup_refusal=lookup_refusal, run_refusal=run_refusal, answer=answer
    )
    with bound_model_runs(port):
        yield port


IMAGE_LANE = ModelRunLane(
    provider_id="nearby",
    transport="api",
    model="synthetic-reader-1",
    reads_off_host=False,
    accepted_media=(ModelRunMediaKind.IMAGE,),
)
TEXT_ONLY_LANE = ModelRunLane(
    provider_id="nearby",
    transport="cli",
    model="synthetic-reader-1",
    reads_off_host=False,
    accepted_media=(),
)
ON_HOST_LANE = ModelRunLane(
    provider_id="nearby",
    transport="api",
    model="synthetic-reader-1",
    reads_off_host=False,
)
"""A lane whose catalogue entry declares it stays on this computer."""
