"""Resolve the events a workflow JOB can actually run on.

A workflow's ``on:`` block says when the RUN starts. It does not say which jobs
execute inside it, and a job-level ``if:`` can remove events the workflow
declares. Reading the workflow block alone therefore attributes every trigger to
every job, and a lane that only a gated job reaches inherits reach it does not
have.

That divergence is live. ``runner-fleet-health.yml`` fires on push and on
dispatch, and its ``dev-image`` job is guarded by
``github.event_name == 'workflow_dispatch' && inputs.include_dev_image``. The
job runs on NO push, and ``just devcontainer-test`` -- the only thing that
builds and probes the contributor image -- is reached from nowhere else. A
workflow-level reading calls that lane push-triggered, which is the reassuring
answer and the wrong one.

TWO INDEPENDENT WEAKENINGS, and the second is the one a trigger model normally
cannot see. Narrowing to ``workflow_dispatch`` is a restriction on the EVENT.
Requiring ``inputs.include_dev_image``, whose declared default is ``false``, is
a restriction on the DISPATCH ITSELF: the button exists, and pressing it in the
ordinary way still does not run the job. Reporting only the first would say
"manual" about a job that a manual run does not reach either, so the two are
reported separately and neither stands in for the other.

NARROWING IS ONLY EVER DONE WHEN IT IS PROVABLE. A condition containing ``||``
is left alone entirely, because a disjunct this module does not model could
re-admit any event -- and the repository's most common job guard is exactly that
shape (``github.event_name != 'pull_request' || <same-repo head>``, the fork
guard, which is TRUE on every push and excludes only forked pull requests). A
model that narrowed it would report ten per-push jobs as unreachable on push and
bury the one real finding in noise. Refusing to narrow what it cannot prove is
what keeps the single true case legible.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Final
__all__ = ['JobGate', 'dispatch_input_defaults', 'job_gate', 'narrowed_events', 'opt_in_conjuncts']
_INTERPOLATION: Final = re.compile('\\$\\{\\{(?P<body>.*?)\\}\\}', re.DOTALL)
_EVENT_IS: Final = re.compile('github\\.event_name\\s*==\\s*[\'\\"](?P<event>[A-Za-z_]+)[\'\\"]')
_EVENT_IS_NOT: Final = re.compile('github\\.event_name\\s*!=\\s*[\'\\"](?P<event>[A-Za-z_]+)[\'\\"]')
_BARE_INPUT: Final = re.compile('^inputs\\.(?P<name>[A-Za-z_][A-Za-z0-9_-]*)$')
_FALSY_DEFAULTS: Final = (None, False, '', 'false', 'False', 0)

@dataclass(frozen=True, slots=True)
class JobGate:
    """What a job's ``if:`` proves about the events that reach the job.

    ``events`` is the workflow's event set after every restriction this module
    can prove, so it equals the input set for an ungated job and for a guard too
    complex to model. ``opt_in`` is the separate fact: the job additionally
    requires a ``workflow_dispatch`` input whose declared default is falsy, so
    even a plain press of the button does not reach it.
    """
    events: tuple[str, ...]
    opt_in: tuple[str, ...] = ()

    @property
    def is_opt_in(self) -> bool:
        """Return whether an ordinary run of a reaching event still skips this job."""
        return bool(self.opt_in)

def _condition_text(condition: object) -> str:
    """Return a job ``if:`` as bare expression text, or the empty string."""
    if condition is None:
        return ''
    text = str(condition).strip()
    match = _INTERPOLATION.fullmatch(text)
    return (match.group('body') if match is not None else text).strip()

def narrowed_events(condition: object, events: tuple[str, ...]) -> tuple[str, ...]:
    """Return ``events`` minus what ``condition`` provably excludes.

    ``==`` comparisons intersect and ``!=`` comparisons subtract, but only in a
    condition with no ``||``: a disjunction can re-admit any event through a
    branch this module does not model, so an unprovable guard narrows nothing
    rather than narrowing wrongly.
    """
    text = _condition_text(condition)
    if not text or '||' in text:
        return events
    required = {match.group('event') for match in _EVENT_IS.finditer(text)}
    forbidden = {match.group('event') for match in _EVENT_IS_NOT.finditer(text)}
    kept = set(events)
    if required:
        kept &= required
    kept -= forbidden
    return tuple(sorted(kept))

def opt_in_conjuncts(condition: object) -> tuple[str, ...]:
    """Return the input names a condition requires as bare truthiness.

    Only a conjunct that is EXACTLY ``inputs.<name>`` counts. An input compared
    against a value (``inputs.mode == 'full'``) is a gate too, but its default
    may well satisfy it, so calling it opt-in would claim a weakening that is
    not proven -- the same refusal :func:`narrowed_events` makes about ``||``.
    """
    text = _condition_text(condition)
    if not text or '||' in text:
        return ()
    names = []
    for conjunct in text.split('&&'):
        match = _BARE_INPUT.match(conjunct.strip().strip('()').strip())
        if match is not None:
            names.append(match.group('name'))
    return tuple(names)

def dispatch_input_defaults(document: dict[str, Any]) -> dict[str, Any]:
    """Return the ``workflow_dispatch`` input defaults declared by a workflow.

    ``on`` is a YAML 1.1 boolean, so a safe-loaded workflow carries its trigger
    block under the key ``True`` and never under the string ``"on"``. Reading
    ``document["on"]`` returns nothing for every workflow in this repository,
    and an empty default map would report every gated job as reachable by an
    ordinary dispatch -- the silently-empty answer this module exists to refuse.
    """
    block = _dp_get('dev/ci/workflow_job_gates.py:139:get', document, 'on', document.get(True))
    if not isinstance(block, dict):
        return {}
    dispatch = block.get('workflow_dispatch')
    if not isinstance(dispatch, dict):
        return {}
    inputs = dispatch.get('inputs')
    if not isinstance(inputs, dict):
        return {}
    return {str(name): spec.get('default') if isinstance(spec, dict) else None for name, spec in inputs.items()}

def job_gate(document: dict[str, Any], job_name: str, events: tuple[str, ...]) -> JobGate:
    """Return the events reaching ``job_name`` and the opt-in inputs it requires.

    A job the document does not declare reaches nothing, which is distinct from
    a declared job whose guard narrows to nothing: both yield an empty event
    tuple, and the caller that cares reads ``job_name in document["jobs"]``.
    """
    job = (document.get('jobs') or {}).get(job_name)
    if not isinstance(job, dict):
        return JobGate(events=())
    condition = job.get('if')
    defaults = dispatch_input_defaults(document)
    opt_in = tuple((name for name in opt_in_conjuncts(condition) if _dp_get('dev/ci/workflow_job_gates.py:163:get', defaults, name, None) in _FALSY_DEFAULTS))
    return JobGate(events=narrowed_events(condition, events), opt_in=opt_in)