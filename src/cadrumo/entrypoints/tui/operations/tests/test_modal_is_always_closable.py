"""An operation modal can always be left, even before any observation succeeds.

``action_request_close`` handled two cases and silently fell through a third.
Both live branches were guarded on ``view_model is not None``, so while
``_view_model`` was unset the method did nothing at all — and that is exactly
the state the modal sits in when observation refuses from the very first poll.

Escape is bound to ``request_close``, and the Close button keeps the enabled
state it was composed with until a render disables it, so both routes out led
to the same no-op. The operator was left holding a modal screen with no way
back.

``None`` is the screen's own declared result type (``ModalScreen[
OperationModalOutcomeV1 | None]``) and the sign-out caller in ``app.py`` already
reads a ``None`` dismissal as "backed out" rather than as a failure, so leaving
without an outcome needs no new vocabulary.

Asserted structurally: a behavioural proof drives a registered operation
through the composed production services (real journal, leases and custody),
which is what the two sibling suites in this directory do and what a
"nothing was ever observed" case cannot easily reach. The check below is
therefore paired with a proof that it rejects the shape that shipped.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from ..modal import OperationModal

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _branch_tests(source: str) -> list[str]:
    """Return the dumped test expression of each top-level ``if`` in the body."""
    body = ast.parse(source.lstrip()).body[0]
    return [ast.dump(node.test) for node in getattr(body, "body", []) if isinstance(node, ast.If)]


def _dismisses_when_view_model_is_absent(source: str) -> bool:
    """Whether the absent-view-model branch reaches a ``dismiss`` call."""
    body = ast.parse(source.lstrip()).body[0]
    for node in getattr(body, "body", []):
        if not isinstance(node, ast.If):
            continue
        test = ast.dump(node.test)
        if "view_model" not in test or "None" not in test or "IsNot" in test:
            continue
        return any(
            isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "dismiss"
            for call in ast.walk(node)
        )
    return False


def test_the_modal_can_be_left_before_anything_is_observed() -> None:
    """The trap: no view model meant no way out."""
    source = inspect.getsource(OperationModal.action_request_close)

    assert _dismisses_when_view_model_is_absent(source), (
        "action_request_close must dismiss when no view model has been observed; "
        "otherwise Escape and the Close button are both inert"
    )


def test_the_check_rejects_the_shape_that_shipped() -> None:
    """Proof the assertion can fail, against the real prior code.

    The shipped version guarded both branches on ``is not None`` and simply
    ended, so nothing handled the absent case.
    """
    shipped = (
        "async def action_request_close(self) -> None:\n"
        "    view_model = self._view_model\n"
        "    if view_model is not None and view_model.detach_control_enabled:\n"
        "        await self._request_detach()\n"
        "    elif view_model is not None and not view_model.spinner_visible:\n"
        "        await self._stop_poll_worker()\n"
        "        self.dismiss(OperationModalSettledOutcomeV1(view_model=view_model))\n"
    )

    assert not _dismisses_when_view_model_is_absent(shipped)


def test_the_check_is_not_satisfied_by_a_bare_early_return() -> None:
    """Returning early is the other way to write the same trap."""
    early_return = (
        "async def action_request_close(self) -> None:\n"
        "    view_model = self._view_model\n"
        "    if view_model is None:\n"
        "        return\n"
        "    self.dismiss(None)\n"
    )

    assert not _dismisses_when_view_model_is_absent(early_return)


def test_the_poll_worker_is_reaped_before_leaving() -> None:
    """Dismissing alone pops the screen while the worker may still be parked.

    The detach and settled paths both stop the worker first and say why; the
    new path must not be the one that races teardown against a live poller.
    """
    source = inspect.getsource(OperationModal.action_request_close)
    body = ast.parse(source.lstrip()).body[0]
    absent_branch = next(
        node
        for node in getattr(body, "body", [])
        if isinstance(node, ast.If) and "view_model" in ast.dump(node.test) and "IsNot" not in ast.dump(node.test)
    )
    called = {
        call.func.attr
        for call in ast.walk(absent_branch)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
    }

    assert "_stop_poll_worker" in called
