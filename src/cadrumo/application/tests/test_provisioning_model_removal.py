"""Real-behavior tests for model removal and the partial-provisioning doctor row.

No mock, patch or stub reaches the code under test. Runtime interaction runs
against a real :class:`~http.server.ThreadingHTTPServer` speaking the runtime's
``/api/tags`` and ``/api/delete`` wire shape over real ``httpx``, and the stub
holds a MUTABLE inventory that the delete handler actually mutates -- so the
confirming re-read inside
:func:`~application.provisioning.remove_runtime_model` observes a store that
genuinely changed, rather than a canned second answer that would make the
confirmation tautological.

The optional-extra half of the doctor row is exercised through the real
:func:`~cadrumo.core.optional_extra_available` spec probe against a real
``sys.path`` entry, so both directions of the partial-install detection run the
production predicate.

Every refusal case carries a positive control asserting the permitting case
passes through the same call, so a refusal cannot pass for the wrong reason.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Sequence
from http import HTTPStatus
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from queue import Queue
from types import ModuleType
from typing import ClassVar, override

import pytest

from ...core.optional_extras import LLM_EXTRA
from ...core.config import override_settings
from ...tests.loopback_llm import (
    SilentLoopbackHandler,
    read_text_body,
    serving_loopback,
    write_json_response,
)
from ..provisioning import (
    LOCAL_MODEL_PROVISIONING_SERVICE,
    InstalledModel,
    probe_local_model_provisioning,
    read_installed_models,
    remove_runtime_model,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

GIB = 1024**3

VISION = "qwen2.5vl:3b"
TEXT = "qwen2.5:3b"
MAPPING = "qwen2.5:1.5b"


class _ModelStoreLoopbackHandler(SilentLoopbackHandler):
    """A real endpoint speaking the runtime's ``/api/tags`` and ``/api/delete`` wire shape.

    ``models`` is the store, and ``do_DELETE`` removes from it. That mutation is
    what makes the production re-read meaningful: a handler answering the same
    inventory twice would let a removal that changed nothing report as confirmed.

    The inventory rows carry a ``size`` the shared well-formed tags envelope does
    not model, and ``/api/delete`` is a management verb rather than an inference
    one, so the bodies stay local here while the plumbing is shared.
    """

    models: ClassVar[list[dict[str, object]]] = []
    events: ClassVar[Queue[dict[str, object]]]
    delete_status: ClassVar[HTTPStatus] = HTTPStatus.OK
    #: When true, the delete is accepted but the store is left untouched.
    delete_is_a_lie: ClassVar[bool] = False

    @override
    def do_GET(self) -> None:
        self.events.put({"method": "GET", "path": self.path})
        write_json_response(self, {"models": list(self.models)}, status=HTTPStatus.OK)

    @override
    def do_DELETE(self) -> None:
        raw = read_text_body(self)
        payload: dict[str, object] = {}
        if raw:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                payload = {str(key): value for key, value in parsed.items()}
        self.events.put({"method": "DELETE", "path": self.path, "body": payload})
        if self.delete_status is not HTTPStatus.OK:
            write_json_response(self, {"error": "refused"}, status=self.delete_status)
            return
        if not self.delete_is_a_lie:
            target = payload.get("model")
            type(self).models = [row for row in self.models if row.get("name") != target]
        write_json_response(self, {"done": True}, status=HTTPStatus.OK)


@pytest.fixture
def store() -> Iterator[tuple[str, Queue[dict[str, object]]]]:
    """Serve a real runtime store on a loopback port; yield its chat URL and event queue."""
    events: Queue[dict[str, object]] = Queue()
    _ModelStoreLoopbackHandler.events = events
    _ModelStoreLoopbackHandler.models = []
    _ModelStoreLoopbackHandler.delete_status = HTTPStatus.OK
    _ModelStoreLoopbackHandler.delete_is_a_lie = False
    with serving_loopback(_ModelStoreLoopbackHandler, path="/api/chat") as chat_url:
        yield (chat_url, events)


def _selected(chat_url: str) -> dict[str, str]:
    """Return the settings overrides binding the three roles and the runtime endpoint."""
    return {
        "cadrumo_llm_ollama_chat_url": chat_url,
        "cadrumo_llm_ollama_vision_model": VISION,
        "cadrumo_llm_ollama_text_model": TEXT,
        "cadrumo_llm_ollama_mapping_model": MAPPING,
    }


# ---------------------------------------------------------------------------
# the on-disk inventory read
# ---------------------------------------------------------------------------


def test_installed_inventory_is_read_from_the_tags_endpoint(store: tuple[str, Queue[dict[str, object]]]) -> None:
    """Installed models come from ``/api/tags``, the on-disk inventory, not ``/api/ps``."""
    chat_url, events = store
    _ModelStoreLoopbackHandler.models = [{"name": VISION, "size": 4 * GIB}]
    with override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        installed = read_installed_models()
    assert installed == (InstalledModel(name=VISION, size_bytes=4 * GIB),)
    assert events.get(timeout=5) == {"method": "GET", "path": "/api/tags"}


def test_an_unreachable_runtime_reads_as_unmeasured_not_as_empty() -> None:
    """``None`` and ``()`` are different states; an empty store is a fact, an unreachable one is not."""
    with override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat"):
        assert read_installed_models() is None


# ---------------------------------------------------------------------------
# removal, and the measured freed figure
# ---------------------------------------------------------------------------


def test_removal_reports_the_runtimes_own_size_only_after_the_store_confirms_the_loss(
    store: tuple[str, Queue[dict[str, object]]],
) -> None:
    """The positive control: a real delete, a real re-read, and a measured figure."""
    chat_url, events = store
    _ModelStoreLoopbackHandler.models = [{"name": VISION, "size": 4 * GIB}, {"name": TEXT, "size": 2 * GIB}]
    with override_settings(**_selected(chat_url)):
        outcome = remove_runtime_model(VISION)
    assert outcome.removed is True
    assert outcome.was_installed is True
    assert outcome.freed_bytes == 4 * GIB
    # The figure is the removed model's size, never the store total: a report of
    # 6 GiB would be an aggregate the operator cannot reconcile against what left.
    assert outcome.freed_bytes != 6 * GIB
    assert [row["name"] for row in _ModelStoreLoopbackHandler.models] == [TEXT]

    methods = []
    while not events.empty():
        methods.append(events.get_nowait()["method"])
    # Read, delete, confirm -- the trailing read is the confirmation, and its
    # absence would mean the figure was never measured across the action.
    assert methods == ["GET", "DELETE", "GET"]


def test_removal_refuses_a_model_cadrumo_did_not_select_and_sends_nothing(
    store: tuple[str, Queue[dict[str, object]]],
) -> None:
    """Deleting a peer's model costs a re-download; the guard is proven by silence on the wire."""
    chat_url, events = store
    _ModelStoreLoopbackHandler.models = [{"name": "llama3:70b", "size": 40 * GIB}]
    with override_settings(**_selected(chat_url)):
        outcome = remove_runtime_model("llama3:70b")
    assert outcome.removed is False
    assert outcome.freed_bytes is None
    assert outcome.facts["selected_by_cadrumo"] is False
    assert outcome.precondition_verdict is not None
    assert events.empty(), "a refused removal must not reach the runtime at all"
    assert [row["name"] for row in _ModelStoreLoopbackHandler.models] == ["llama3:70b"]


def test_removal_of_a_model_that_is_not_installed_frees_nothing_and_deletes_nothing(
    store: tuple[str, Queue[dict[str, object]]],
) -> None:
    """Zero freed is a measurement here, distinct from the unmeasured ``None`` below."""
    chat_url, events = store
    _ModelStoreLoopbackHandler.models = [{"name": TEXT, "size": 2 * GIB}]
    with override_settings(**_selected(chat_url)):
        outcome = remove_runtime_model(VISION)
    assert outcome.removed is False
    assert outcome.was_installed is False
    assert outcome.freed_bytes == 0
    assert events.get(timeout=5)["method"] == "GET"
    assert events.empty(), "nothing beyond the inventory read may be sent"


def test_removal_with_an_unreadable_inventory_does_nothing_and_reports_no_figure() -> None:
    """Unknown contents are not permission to delete, and yield no reclaimed figure."""
    with override_settings(
        cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat",
        cadrumo_llm_ollama_vision_model=VISION,
    ):
        outcome = remove_runtime_model(VISION, installed=None, installed_measured=False)
    assert outcome.removed is False
    assert outcome.freed_bytes is None


def test_a_delete_the_runtime_accepted_but_did_not_perform_reports_no_freed_bytes(
    store: tuple[str, Queue[dict[str, object]]],
) -> None:
    """An estimate is worse than no figure: an unconfirmed removal must report neither."""
    chat_url, _events = store
    _ModelStoreLoopbackHandler.models = [{"name": VISION, "size": 4 * GIB}]
    _ModelStoreLoopbackHandler.delete_is_a_lie = True
    with override_settings(**_selected(chat_url)):
        outcome = remove_runtime_model(VISION)
    assert outcome.removed is False
    assert outcome.was_installed is True
    assert outcome.freed_bytes is None
    assert outcome.facts["model_installed"] is True
    assert outcome.precondition_verdict is not None


def test_a_runtime_that_refuses_the_delete_reports_no_freed_bytes(
    store: tuple[str, Queue[dict[str, object]]],
) -> None:
    """A transport failure is a refusal, never a silent success carrying a number."""
    chat_url, _events = store
    _ModelStoreLoopbackHandler.models = [{"name": VISION, "size": 4 * GIB}]
    _ModelStoreLoopbackHandler.delete_status = HTTPStatus.INTERNAL_SERVER_ERROR
    with override_settings(**_selected(chat_url)):
        outcome = remove_runtime_model(VISION)
    assert outcome.removed is False
    assert outcome.was_installed is True
    assert outcome.freed_bytes is None


def test_removal_reports_no_figure_when_the_size_was_never_measured(
    store: tuple[str, Queue[dict[str, object]]],
) -> None:
    """A runtime that omits ``size`` yields a removal with an honest absent figure, never a zero."""
    chat_url, _events = store
    _ModelStoreLoopbackHandler.models = [{"name": VISION}]
    with override_settings(**_selected(chat_url)):
        outcome = remove_runtime_model(VISION)
    assert outcome.removed is True
    assert outcome.freed_bytes is None, "an unmeasured size must not be reported as zero bytes reclaimed"


# ---------------------------------------------------------------------------
# the partial-provisioning doctor row, in BOTH directions
# ---------------------------------------------------------------------------


class _AbsentDistributionFinder(MetaPathFinder):
    """A real import-system finder that makes one distribution genuinely unimportable.

    Installed at the head of ``sys.meta_path``, so the production
    :func:`~cadrumo.core.optional_extra_available` call runs the real
    ``importlib.util.find_spec`` against the real import machinery and observes
    the same absence a core install produces. Nothing about the predicate, its
    exception handling, or its truthiness test is replaced -- the only thing
    changed is the environmental fact the two directions differ on, which cannot
    otherwise be produced without uninstalling a package mid-run.
    """

    def __init__(self, hidden: str) -> None:
        self._hidden = hidden

    @override
    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        """Raise the absence the import machinery raises for a package that is not installed."""
        if fullname.split(".")[0] == self._hidden:
            raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
        return None


@pytest.fixture
def extra_absent() -> Iterator[None]:
    """Make the llm extra genuinely unimportable for the duration of one test."""
    hidden = LLM_EXTRA.import_name
    removed = {key: sys.modules[key] for key in sys.modules if key.split(".")[0] == hidden}
    for name in removed:
        del sys.modules[name]
    original_meta_path = sys.meta_path
    sys.meta_path = [_AbsentDistributionFinder(hidden), *sys.meta_path]
    try:
        yield
    finally:
        sys.meta_path = original_meta_path
        sys.modules.update(removed)


def _installed_extra() -> bool:
    """Return the live availability of the llm extra in this environment."""
    from ...core.optional_extras import optional_extra_available

    return optional_extra_available(LLM_EXTRA)


def test_direction_one_extra_installed_with_no_selected_model_reds_and_names_the_pull(
    store: tuple[str, Queue[dict[str, object]]],
) -> None:
    """The live code path with nothing to load. Remedy is a pull, never an install."""
    if not _installed_extra():
        pytest.fail("this environment has no llm extra installed; the direction-one fixture cannot be built")
    chat_url, _events = store
    with override_settings(**_selected(chat_url)):
        status = probe_local_model_provisioning(installed=())
    assert status.service == LOCAL_MODEL_PROVISIONING_SERVICE
    assert status.available is False
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == "provisioning.local_model.extra_requires_model"


def test_direction_two_models_installed_without_the_extra_reds_and_names_the_install(
    store: tuple[str, Queue[dict[str, object]]],
    extra_absent: None,
) -> None:
    """Disk occupied by models nothing can use. Remedy is the install, never a pull."""
    chat_url, _events = store
    with override_settings(**_selected(chat_url)):
        status = probe_local_model_provisioning(
            installed=(InstalledModel(name=VISION, size_bytes=4 * GIB),),
        )
    assert status.service == LOCAL_MODEL_PROVISIONING_SERVICE
    assert status.available is False
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == "provisioning.local_model.model_requires_extra"
    assert status.facts["present_selected_model_count"] == 1


def test_neither_direction_is_satisfiable_by_the_others_evidence(
    store: tuple[str, Queue[dict[str, object]]],
    extra_absent: None,
) -> None:
    """The disjointness claim, run rather than asserted in prose.

    Direction one's model evidence (an empty inventory) paired with direction
    two's extra evidence (the extra absent) is the coherent unprovisioned state,
    not a partial one. If a single check stood in for both, this would red.
    """
    chat_url, _events = store
    with override_settings(**_selected(chat_url)):
        status = probe_local_model_provisioning(installed=())
    assert status.available is True
    assert status.precondition_verdict is None


def test_a_coherent_installed_posture_is_green(store: tuple[str, Queue[dict[str, object]]]) -> None:
    """Positive control for both directions: with both halves present, nothing reds."""
    if not _installed_extra():
        pytest.fail("this environment has no llm extra installed; the coherent-posture control cannot be built")
    chat_url, _events = store
    with override_settings(**_selected(chat_url)):
        status = probe_local_model_provisioning(
            installed=(InstalledModel(name=VISION, size_bytes=4 * GIB),),
        )
    assert status.available is True
    assert status.precondition_verdict is None


def test_a_model_cadrumo_did_not_select_does_not_satisfy_direction_one(
    store: tuple[str, Queue[dict[str, object]]],
) -> None:
    """A peer's model on disk is not Cadrumo's model being present."""
    if not _installed_extra():
        pytest.fail("this environment has no llm extra installed; this fixture cannot be built")
    chat_url, _events = store
    with override_settings(**_selected(chat_url)):
        status = probe_local_model_provisioning(
            installed=(InstalledModel(name="llama3:70b", size_bytes=40 * GIB),),
        )
    assert status.available is False
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == "provisioning.local_model.extra_requires_model"


def test_an_unreadable_inventory_with_the_extra_present_reds_rather_than_claiming_coherence(
    store: tuple[str, Queue[dict[str, object]]],
) -> None:
    """An opted-in operator who cannot be told what is installed gets a row, not a false all-clear."""
    if not _installed_extra():
        pytest.fail("this environment has no llm extra installed; this fixture cannot be built")
    chat_url, _events = store
    with override_settings(**_selected(chat_url)):
        status = probe_local_model_provisioning(installed=None, installed_measured=False)
    assert status.available is False
    assert status.facts["installed_model_inventory_readable"] is False
    assert status.precondition_verdict is not None


def test_an_unreadable_inventory_without_the_extra_says_what_it_could_not_rule_out(
    store: tuple[str, Queue[dict[str, object]]],
    extra_absent: None,
) -> None:
    """Green here is a stated limit, not a claim: the detail must say the gap out loud."""
    chat_url, _events = store
    with override_settings(**_selected(chat_url)):
        status = probe_local_model_provisioning(installed=None, installed_measured=False)
    assert status.available is True
    assert status.facts["installed_model_inventory_readable"] is False
    assert status.precondition_verdict is None
