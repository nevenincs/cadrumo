"""An on-host lane's failure must never become an off-host read.

This is a confidentiality boundary, not a reliability one. Every other
degradation in this product may be answered by trying something else; this one
may not, because the something else removes a taxpayer's document from the
machine. An automatic fallback would do it at exactly the moment nobody is
watching -- a failure -- and without anyone choosing it.

The behavioural cases run a failing on-host lane behind a recording agent
service and assert on what the service received: the one refused run and
nothing after it. Asserting on the raised exception alone would not distinguish
"no fallback exists" from "a fallback exists and happened to fail too".
"""

from __future__ import annotations

import ast
import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest

from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

from .....core.config_support import LLMProvider
from .....core.directory_scan import scan_directory
from .....core.errors.error_codes import build_error_envelope
from .....core.model_roles import ModelRole
from .....tests.fixtures.settings import EnvFileFreeSettings
from ..client import LLMClient, LLMRetryPolicy
from ..consent import EvidenceConsentToken
from ..errors import LLMConsentError, LLMError
from ..models import LLMRequest
from ._client_process_state import _fresh_client_process_state
from .model_run_support import ON_HOST_LANE, RecordingModelRuns, serving_agent

__all__ = ["_fresh_client_process_state"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_NO_RETRY = LLMRetryPolicy(max_attempts=1)


@contextmanager
def _cloud_recorder() -> Generator[RecordingModelRuns]:
    """Stand in for the agent service on a lane that reads off-host, recording every run.

    The stand-in answers a permitted dispatch with a completion, so a request
    that legitimately reaches it COMPLETES; every case asserting it stayed
    empty would otherwise be satisfied by a route nothing could reach.
    """
    with serving_agent(replies=("cloud completion",)) as service:
        yield service


@contextmanager
def _failing_on_host_lane(code: ModelRunRefusalCode) -> Generator[RecordingModelRuns]:
    """Stand in for the agent service on a lane that stays on this computer and refuses its run."""
    with serving_agent(lane=ON_HOST_LANE, run_refusal=code) as service:
        yield service


def _client(tmp_path: Path, *, cloud_upload_permitted: bool = False) -> LLMClient:
    settings = EnvFileFreeSettings(
        cadrumo_evidence_cloud_upload_permitted=cloud_upload_permitted,
        cadrumo_storage_root=tmp_path,
    )
    return LLMClient(
        settings=settings,
        retry_policy=_NO_RETRY,
    )


def _request(**fields: object) -> LLMRequest:
    base: dict[str, object] = {"prompt": "read this", "model_role": ModelRole.TEXT_EXTRACTION}
    return LLMRequest.model_validate(base | fields)


@pytest.mark.parametrize("code", [ModelRunRefusalCode.LANE_UNAVAILABLE, ModelRunRefusalCode.RUN_FAILED])
def test_a_failing_on_host_lane_is_not_tried_again_elsewhere(tmp_path: Path, code: ModelRunRefusalCode) -> None:
    """The front door: the selected on-host lane fails, and nothing else is asked."""
    with _failing_on_host_lane(code) as service, pytest.raises(LLMError):
        asyncio.run(_client(tmp_path).complete(_request(evidence_derived=True)))

    assert service.lookups == [ModelRole.TEXT_EXTRACTION]
    assert len(service.runs) == 1


def test_an_unmarked_request_is_not_tried_again_elsewhere_either(tmp_path: Path) -> None:
    """The reach-around that matters most: a request the consent gate never sees.

    The consent gate only inspects a request MARKED as evidence-derived, so an
    unmarked request is the path where a fallback would run with no gate in
    front of it at all. Proving the absence of a fallback on the marked path
    only would leave the unwatched half untested -- and the unwatched half is
    where a silent fallback would actually live.
    """
    with _failing_on_host_lane(ModelRunRefusalCode.RUN_FAILED) as service, pytest.raises(LLMError):
        asyncio.run(_client(tmp_path).complete(_request(evidence_derived=False)))

    assert service.lookups == [ModelRole.TEXT_EXTRACTION]
    assert len(service.runs) == 1


def test_a_permitted_request_on_an_off_host_lane_does_reach_the_recorder(tmp_path: Path) -> None:
    """The recorder's own control: it CAN record, so an empty one is a fact about the client.

    The refusal case below asserts the recorder stayed empty, and an empty
    recorder is exactly what a recorder nothing could reach also produces.
    Asserting zero arrivals cannot distinguish "nothing was sent" from "nothing
    could have been recorded" without this case.

    Consented, so the request carries everything the off-host lane admits: the
    service refuses any run on an off-host lane that carries no consent for it.
    """
    with _cloud_recorder() as service:
        request = _request(
            prompt="a routine consented prompt",
            evidence_derived=True,
            consent_token=EvidenceConsentToken(
                surface="runtime:ledger.evidence.extract", evidence_content_address="d" * 64
            ),
            provider_override=LLMProvider.AGENT,
        )
        response = asyncio.run(_client(tmp_path, cloud_upload_permitted=True).complete(request))

        assert len(service.runs) == 1

    assert response.text == "cloud completion"


def test_an_evidence_request_on_an_off_host_lane_is_refused_before_dispatch(tmp_path: Path) -> None:
    """The consent gate refuses an evidence read off-host, and refuses it EARLY.

    Asserted at the recorder rather than only on the exception type, because
    "refused before dispatch" and "dispatched, then refused" are different
    facts and only one of them keeps the document on this host. The case above
    is what makes this empty recorder meaningful: the same lane, reached by a
    permitted request, does record.
    """
    with _cloud_recorder() as service:
        with pytest.raises(LLMConsentError):
            asyncio.run(_client(tmp_path).complete(_request(prompt="read this invoice", evidence_derived=True)))

        assert service.runs == []


def test_an_on_host_degradation_has_no_invented_action(tmp_path: Path) -> None:
    """A failed run remains a provider fact until an application boundary classifies it."""
    with _failing_on_host_lane(ModelRunRefusalCode.RUN_FAILED), pytest.raises(LLMError) as raised:
        asyncio.run(_client(tmp_path).complete(_request()))

    assert build_error_envelope(raised.value).action is None


def _llm_package_modules() -> list[Path]:
    """Return every production module in the LLM package."""
    root = Path(__file__).resolve().parent.parent
    return sorted(path for path in scan_directory(root, pattern="*.py", recursive=True) if "tests" not in path.parts)


_ADAPTER_CONSTRUCTORS = frozenset({"_build_adapter", "AgentAdapter"})


def _called_names(node: ast.AST) -> set[str]:
    """Return every simple callee name reachable inside ``node``."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _handlers_building_adapters(modules: list[Path]) -> list[str]:
    """Return every failure handler in ``modules`` that constructs a provider adapter."""
    offenders: list[str] = []
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            built = _called_names(node) & _ADAPTER_CONSTRUCTORS
            if built:
                offenders.append(f"{module.name}:{node.lineno} constructs {sorted(built)} while handling a failure")
    return offenders


def _handlers_re_resolving_provider(modules: list[Path]) -> list[str]:
    """Return every failure handler in ``modules`` that re-routes a request at another provider."""
    offenders: list[str] = []
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            for child in ast.walk(node):
                if isinstance(child, ast.keyword) and child.arg == "provider_override":
                    offenders.append(f"{module.name}:{node.lineno} passes provider_override while handling a failure")
                elif (
                    isinstance(child, ast.Attribute)
                    and child.attr == "provider_override"
                    and isinstance(child.ctx, ast.Store)
                ):
                    offenders.append(f"{module.name}:{child.lineno} assigns provider_override while handling a failure")
    return offenders


_FALLBACK_SPECIMEN = '''
"""A synthetic module carrying exactly the defect the detectors look for."""


def read(request):
    try:
        return first_adapter.complete(request)
    except LLMProviderError:
        adapter = AgentAdapter(port=port, role=role, lane=lane, consent=None, deadline_seconds=30, expects_json=False)
        return adapter.complete(request.model_copy(update={"provider_override": "AGENT"}))


def reroute(client, request):
    try:
        return client.complete(request)
    except LLMProviderError:
        return client.complete(LLMRequest(prompt=request.prompt, provider_override="AGENT"))
'''


def test_the_fallback_detectors_find_a_fallback_when_one_exists(tmp_path: Path) -> None:
    """The control the two structural cases below need to mean anything.

    A detector that returns an empty list over a clean tree returns an empty
    list over a broken one too if it is looking in the wrong place, and both
    readings are green. Running the same two detectors over a module written to
    carry the defect is what separates "there is no fallback" from "this
    measures nothing".
    """
    specimen = tmp_path / "specimen.py"
    specimen.write_text(_FALLBACK_SPECIMEN, encoding="utf-8")

    assert _handlers_building_adapters([specimen]), "the adapter-construction detector missed a planted fallback"
    assert _handlers_re_resolving_provider([specimen]), "the provider-reroute detector missed a planted reroute"


def test_no_failure_handler_in_the_package_builds_another_provider() -> None:
    """Structural: a fallback would live in an exception handler, so no handler may build one.

    Stated as a property over EVERY handler in the package rather than as a
    count of dispatch sites: a count encodes today's shape and trains the next
    author to update the constant, while this reds the moment a recovery path
    reaches for a second provider anywhere -- including in a module that does
    not exist yet.
    """
    offenders = _handlers_building_adapters(_llm_package_modules())

    assert not offenders, (
        "a failure handler builds a provider adapter, which is how an on-host failure becomes a "
        "cloud dispatch nobody chose:\n" + "\n".join(offenders)
    )


def test_no_failure_handler_in_the_package_re_resolves_the_provider() -> None:
    """Structural: nor may a handler re-decide WHICH provider the request runs at.

    The subtler half of the same defect. A handler need not construct an adapter
    to reroute a request -- rewriting the request's provider and re-entering the
    dispatch achieves it, and reads as a retry.
    """
    offenders = _handlers_re_resolving_provider(_llm_package_modules())

    assert not offenders, (
        "a failure handler sets a provider override, re-routing a failed request at another "
        "provider:\n" + "\n".join(offenders)
    )
