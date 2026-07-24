"""Test-support projection: a scripted prompter from a canonical-token dict.

The production wizard drives every non-interactive walk through the flow
substrate's scripted intent driver. The one-shot line-mode runner
(``_runner.run_flow``) and its :class:`CanonicalAnswerPrompter` remain in
service only for the runner's own unit coverage; this helper rebuilds the
answer queue those tests feed the runner, evaluating visibility with the
same :func:`_condition_satisfied` predicate the runner uses — including the
same ``force_visible`` set — so an intra-section gate sees the earlier
answer and the queue never desyncs from the runner's question sequence.
"""

from __future__ import annotations

from collections import deque

from .._models import WizardFlow
from .._prompter import CanonicalAnswerPrompter
from .._runner import _condition_satisfied


def scripted_from_canonical(
    flow: WizardFlow,
    canonical: dict[str, str],
    *,
    force_visible: frozenset[str] = frozenset(),
) -> CanonicalAnswerPrompter:
    """Build a non-interactive prompter driven by the canonical-token dict."""
    answers: deque[str] = deque()
    running: dict[str, str] = {}
    for section in flow.sections:
        for question in section.questions:
            if not _condition_satisfied(question, running, force_visible=force_visible):
                continue
            value = canonical.get(question.id, question.default or "")
            answers.append(value)
            running[question.id] = value
    return CanonicalAnswerPrompter(answers)


__all__ = ["scripted_from_canonical"]
