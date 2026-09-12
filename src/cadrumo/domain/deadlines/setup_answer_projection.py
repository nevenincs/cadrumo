"""Registry-aware projection of persisted profile values into setup answers.

The generic typed answer model lives in core.  This domain module owns the
projection-specific field specification and composes registry declarations
into the projection consumed by deadline profile construction.  Core therefore
remains independent of registry authority while the registry catalogue remains
the one source of these facts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ...core.setup_answers import SetupAnswers


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


class _RegistrySetupAnswerFields(Mapping[str, SetupFieldSpec]):
    """Lazy view of the registry-owned setup-field declarations."""

    def __init__(self) -> None:
        self._resolved: dict[str, SetupFieldSpec] | None = None

    def _values(self) -> dict[str, SetupFieldSpec]:
        if self._resolved is None:
            from ..calculations.registry.setup_profile_bindings import setup_answer_declarations

            self._resolved = {
                field: SetupFieldSpec(path, answer_type, default)
                for field, (path, answer_type, default) in setup_answer_declarations().items()
            }
        return self._resolved

    def __getitem__(self, key: str) -> SetupFieldSpec:
        return self._values()[key]

    def __iter__(self):
        return iter(self._values())

    def __len__(self) -> int:
        return len(self._values())


SETUP_ANSWER_FIELDS: Mapping[str, SetupFieldSpec] = _RegistrySetupAnswerFields()
"""Every setup-answer field that a persisted profile record can fill."""


def project_setup_answers(values: Mapping[str, str]) -> SetupAnswers:
    """Build :class:`SetupAnswers` from canonical profile-record values.

    A present path wins even when its value is blank; only an absent path uses
    the registry declaration's default.  Blank boolean tokens stay undeclared
    rather than being collapsed to ``False``.
    """
    typed: dict[str, object] = {}
    for field, spec in SETUP_ANSWER_FIELDS.items():
        raw = values.get(spec.path)
        if raw is None:
            raw = spec.default
        if raw is None:
            continue
        typed[field] = (raw == "true" if raw else "") if spec.answer_type is bool else raw
    return SetupAnswers.model_validate(typed)

__all__ = [
    "SETUP_ANSWER_FIELDS",
    "SetupFieldSpec",
    "project_setup_answers",
]
