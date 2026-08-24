"""The envelope spine and the one diagnostic channel, gated against the spec kernel.

`aeat-cli-contract` names this file as one of its gates. The previous
implementation walked a `SCHEMA_REGISTRY` mapping in `core.json_contract`; that
registry was retired and schema identity now lives on the command specs as
``ResultSchemaSpec(state=TARGET, target=..., identity=...)``. The registry and
the gate went in the same commit, so the contract below lost its enforcement
while the rule kept naming it.

Two properties are held here, and they are the ones that were lost:

- the success envelope exposes exactly the shared outer spine, so a later edit
  cannot quietly drop ``status`` / ``notices`` or reintroduce a free-form
  ``warnings`` list beside them; and
- no command's result schema re-implements the notice channel with a bespoke
  ``next`` / ``suggestion`` / ``*_advisory`` field.

The second is not hypothetical. This campaign found a notice whose message
carried raw ``aeat …`` command prose (which crashed the whole calculation at the
outbound boundary) and a refusal whose context carried a raw ``ValidationError``
class name. Both were the same mistake in the other direction: pushing
diagnostics through a surface that is not the diagnostic channel.
"""

from __future__ import annotations

import importlib
from typing import Final

import pytest

from ....core.json_contract import SchemaEnvelope
from .._command_spec import SchemaState
from .._command_specs import COMMAND_SPECS

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: The success envelope's outer spine, shared (minus ``result`` vs ``error``)
#: with the stderr error document so one shape describes success, warning and
#: error outcomes.
_EXPECTED_SUCCESS_SPINE_KEYS: Final = frozenset(
    {"schema_version", "command", "active_profile", "status", "result", "notices"},
)

#: Result-schema field names that must never reappear. ``next_due`` /
#: ``next_action`` / ``next_label`` are legitimate structured data -- a due date,
#: a per-finding action, a label -- and are intentionally NOT forbidden; only the
#: bare ``next`` hint and the ``*_advisory`` smuggling are.
_FORBIDDEN_NOTICE_FIELD_NAMES: Final = frozenset(
    {"next", "suggestion", "suggestions", "hint", "hints", "advisory", "advisories", "source_advisories"},
)


def _is_forbidden_notice_field(name: str) -> bool:
    """Return True when ``name`` is a bespoke notice/advisory result field."""
    return name in _FORBIDDEN_NOTICE_FIELD_NAMES or name.endswith("_advisory") or name.endswith("_advisories")


def _schema_targets() -> list[tuple[str, object]]:
    """Resolve every command spec that declares a result-schema target.

    Specs declaring NOT_SUPPORTED or UNAVAILABLE are skipped: they are explicit
    statements that a command has no result payload, which is a different
    contract from having one that misbehaves.
    """
    resolved: list[tuple[str, object]] = []
    for spec in COMMAND_SPECS:
        schema = getattr(spec, "result_schema", None)
        if schema is None or schema.state is not SchemaState.TARGET or schema.target is None:
            continue
        module = importlib.import_module(schema.target.module)
        model: object = module
        for part in schema.target.qualname.split("."):
            model = getattr(model, part)
        resolved.append((schema.identity or spec.key, model))
    return resolved


def test_success_envelope_carries_shared_spine() -> None:
    """The envelope exposes exactly the shared outer spine, no more and no less."""
    assert set(SchemaEnvelope.model_fields) == set(_EXPECTED_SUCCESS_SPINE_KEYS)


def test_the_gate_sees_a_non_empty_population() -> None:
    """A detector that inspects nothing passes for the wrong reason.

    Asserted as a floor rather than a count: the spec tree grows, and a pinned
    tally would only record the day it was written.
    """
    targets = _schema_targets()
    assert len(targets) > 100, f"only {len(targets)} result schemas resolved; the walk has stopped seeing the tree"


def test_no_result_schema_carries_a_bespoke_notice_field() -> None:
    """No command may re-implement the notice channel inside its result payload."""
    offenders: list[str] = []
    for identity, model in _schema_targets():
        fields = getattr(model, "model_fields", {})
        bespoke = sorted(name for name in fields if _is_forbidden_notice_field(name))
        if bespoke:
            offenders.append(f"{identity} ({getattr(model, '__name__', model)}): {bespoke}")
    assert not offenders, (
        "result schemas carrying a bespoke notice/advisory field: "
        + "; ".join(sorted(offenders))
        + ". Emit these on the envelope `notices` channel instead."
    )
