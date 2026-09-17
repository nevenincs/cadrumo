"""Registry-aware projection of persisted profile values into setup answers.

The typed answer model lives in the user-profile domain.  This domain module owns the
projection-specific field specification and composes registry declarations
into the projection consumed by deadline profile construction.  Core therefore
remains independent of registry authority while the registry catalogue remains
the one source of these facts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..user_profile.setup_answers import SetupAnswers


@dataclass(frozen=True, slots=True)
class SetupFieldSpec:
    """Describe how one setup answer is projected from persisted profile data."""

    path: str
    """Dotted profile-record path, e.g. ``identity.tax_id``."""

    answer_type: type[str] | type[bool]
    """The stored token's type; only string and boolean answers are supported."""

    default: str | None = None
    """Token to assume when the profile record has no value for ``path``.

    ``None`` leaves the answer to the model's own default.  An empty string is
    a present, declared blank and remains distinct from an absent path.
    """


def setup_answer_fields() -> dict[str, SetupFieldSpec]:
    """Return every setup-answer field that a persisted profile record can fill.

    The declarations are resolved from the registry authority in scope on each
    call, so a republished generation is never answered from a stale copy.
    """
    from ..calculations.registry.setup_profile_bindings import setup_answer_declarations

    return {
        field: SetupFieldSpec(path, answer_type, default)
        for field, (path, answer_type, default) in setup_answer_declarations().items()
    }


def project_setup_answers(values: Mapping[str, str]) -> SetupAnswers:
    """Build :class:`SetupAnswers` from canonical profile-record values.

    A present path wins even when its value is blank; only an absent path uses
    the registry declaration's default.  Blank boolean tokens stay undeclared
    rather than being collapsed to ``False``.
    """
    typed: dict[str, object] = {}
    for field, spec in setup_answer_fields().items():
        raw = values.get(spec.path)
        if raw is None:
            raw = spec.default
        if raw is None:
            continue
        typed[field] = (raw == "true" if raw else "") if spec.answer_type is bool else raw
    return SetupAnswers.model_validate(typed)


__all__ = [
    "SetupFieldSpec",
    "project_setup_answers",
    "setup_answer_fields",
]
