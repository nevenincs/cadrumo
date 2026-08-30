"""Pins the user-profile domain refusals to a registered key plus machine facts.

Two halves that fail for different reasons on purpose.

The RUNTIME half drives each reachable refusal through real behaviour and
requires the rendered exception text to equal its registered key exactly. That
is an ABSENCE assertion, and the distinction matters: a key-and-context
assertion stays green when an English sentence is passed positionally beside
the key, because resolution prefers the key while ``str(exc)`` prefers the
positional. Only equality against the key is false for that construction.

The STRUCTURAL half parses the two modules that declare and build these
refusals and refuses the three shapes that survive a raise-site sweep: a
positional argument beside a key, a ``message=`` keyword a ``node.args`` scan
cannot see at all, and prose authored INSIDE the constructor as a default or an
f-string, where every call site looks clean while ``args`` still carries the
sentence. It walks constructions rather than raises, because these refusals are
built by a factory and returned before anything raises them.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Final

import pytest
from pydantic import BaseModel, ValidationError

from ....core.errors.error_codes import get_registered_error_code
from ....core.json_contract import Notice, NoticeSeverity
from ..errors import (
    SCHEMA_LOAD_MESSAGE_KEY,
    STORED_PROFILE_DRIFT_MESSAGE_KEY,
    StoredProfileDriftError,
    UserProfileSchemaLoadError,
)
from ..loader import (
    CONDITION_DERIVED_SELECTORS_ARRAY,
    CONDITION_SCHEMA_MODEL_VALID,
    CONDITION_SCHEMA_TOML_PARSE,
    CONDITION_SECTIONS_TABLE_PRESENT,
    load_user_profile_schema,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The refusal classes this module owns. Named explicitly so a rename cannot
#: make the sweep pass by matching nothing.
_PINNED_ERROR_NAMES: Final[frozenset[str]] = frozenset(
    {"UserProfileSchemaLoadError", "StoredProfileDriftError"},
)

#: The only translated-message values these refusals may carry.
_PINNED_MESSAGE_KEYS: Final[frozenset[str]] = frozenset(
    {SCHEMA_LOAD_MESSAGE_KEY, STORED_PROFILE_DRIFT_MESSAGE_KEY},
)

#: Context keys reserved for the typed action projection at the CLI boundary.
#: A domain refusal that carried one would be a second action authority, and
#: the envelope's own notice contract already refuses them by name.
_RESERVED_ACTION_KEYS: Final[frozenset[str]] = frozenset(
    {
        "action",
        "command",
        "fix_command",
        "next_action",
        "next_command",
        "recovery",
        "recovery_hint",
        "remediation",
        "suggestion",
    },
)

_PACKAGE_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
_SCANNED_MODULES: Final[tuple[str, ...]] = ("errors.py", "loader.py")

#: Structurally well-formed TOML whose values do not satisfy the strict schema
#: model: the ``[schema]`` table declares only an id, so title, version and both
#: policies are absent and the section carries no fields.
_CONTRACT_VIOLATING_SCHEMA: Final[str] = '[schema]\nid = "cadrumo.user_profile"\n\n[[sections]]\nkey = "a"\n'

#: The same document with a top-level scalar where an array of tables belongs.
#: The scalar precedes every table header because TOML binds a bare key to the
#: table most recently opened.
_SCALAR_DERIVED_SELECTORS_SCHEMA: Final[str] = (
    'derived_selectors = 3\n\n[schema]\nid = "cadrumo.user_profile"\n\n[[sections]]\nkey = "a"\n'
)

#: A quote that is never closed, so the parser refuses before any table exists.
_UNPARSEABLE_SCHEMA: Final[str] = "id = 'unterminated\n"

#: A valid document declaring no sections at all.
_SECTIONLESS_SCHEMA: Final[str] = '[schema]\nid = "cadrumo.user_profile"\n'


class _DriftProbe(BaseModel):
    """A record whose validation failure stands in for a drifted stored payload."""

    profile_id: str
    version: int


def _drift_error() -> ValidationError:
    """Return a real pydantic failure by validating a genuinely invalid payload."""
    with pytest.raises(ValidationError) as exc_info:
        _DriftProbe.model_validate({"profile_id": 17, "version": "not-an-integer"})
    return exc_info.value


def _module_tree(name: str) -> ast.Module:
    source = (_PACKAGE_ROOT / name).read_text(encoding="utf-8")
    return ast.parse(source, filename=name)


def _direct_constructions(tree: ast.Module) -> list[ast.Call]:
    """Return every call that builds a pinned refusal by name."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _PINNED_ERROR_NAMES
    ]


def _base_initialisations(tree: ast.Module) -> list[ast.Call]:
    """Return every ``super().__init__`` call inside a pinned refusal's body.

    The delegating call is where a sentence actually enters ``args``, and it is
    invisible to a scan keyed on the class name: the callee is an attribute of
    a ``super()`` result, not the class. Both defect shapes reach the base the
    same way, so both are checked here as well as at the call sites.
    """
    calls: list[ast.Call] = []
    for class_def in _pinned_class_defs(tree):
        for node in ast.walk(class_def):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "__init__"
                and isinstance(node.func.value, ast.Call)
                and isinstance(node.func.value.func, ast.Name)
                and node.func.value.func.id == "super"
            ):
                calls.append(node)
    return calls


def _pinned_constructions(tree: ast.Module) -> list[ast.Call]:
    return [*_direct_constructions(tree), *_base_initialisations(tree)]


def _pinned_class_defs(tree: ast.Module) -> list[ast.ClassDef]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name in _PINNED_ERROR_NAMES]


def test_declared_keys_equal_the_code_registry_message_keys() -> None:
    """Hold the module constants equal to the registry's own key for each class.

    Two spellings of one key drift silently: the refusal would resolve through
    the registry while every assertion here compared against a stale constant.
    """
    schema_code = get_registered_error_code(UserProfileSchemaLoadError)
    drift_code = get_registered_error_code(StoredProfileDriftError)

    assert schema_code is not None
    assert drift_code is not None
    assert schema_code.message_key == SCHEMA_LOAD_MESSAGE_KEY
    assert drift_code.message_key == STORED_PROFILE_DRIFT_MESSAGE_KEY


def test_stored_profile_drift_renders_only_its_registered_key() -> None:
    """The drift refusal carries facts and the key, and no sentence at all."""
    error = StoredProfileDriftError(profile_id="9f0b6b2e-0f7f-4a1e-9f4a-2c1d8b7a6e55", error=_drift_error())

    assert str(error) == STORED_PROFILE_DRIFT_MESSAGE_KEY
    assert error.translated_message == STORED_PROFILE_DRIFT_MESSAGE_KEY
    assert error.context == {
        "profile_id": "9f0b6b2e-0f7f-4a1e-9f4a-2c1d8b7a6e55",
        "failing_record": "_DriftProbe",
        "violation_count": 2,
    }


def test_stored_profile_drift_facts_name_the_contract_not_the_values() -> None:
    """No fact reproduces a value that failed, and none is a violation path.

    A violation location reproduces mapping KEYS as well as field names, so a
    record keyed by a tax identifier would put that identifier into a fact. The
    typed detail stays on the exception for a consumer entitled to project it.
    """
    validation_error = _drift_error()
    error = StoredProfileDriftError(profile_id="9f0b6b2e-0f7f-4a1e-9f4a-2c1d8b7a6e55", error=validation_error)

    assert error.context is not None
    rendered = " ".join(str(value) for value in error.context.values())
    assert "not-an-integer" not in rendered
    assert "17" not in rendered.split()
    assert error.original_exception is validation_error


@pytest.mark.parametrize(
    ("filename", "payload", "condition"),
    [
        ("unparseable.toml", _UNPARSEABLE_SCHEMA, CONDITION_SCHEMA_TOML_PARSE),
        ("sectionless.toml", _SECTIONLESS_SCHEMA, CONDITION_SECTIONS_TABLE_PRESENT),
        ("scalar-selectors.toml", _SCALAR_DERIVED_SELECTORS_SCHEMA, CONDITION_DERIVED_SELECTORS_ARRAY),
        ("contract-violating.toml", _CONTRACT_VIOLATING_SCHEMA, CONDITION_SCHEMA_MODEL_VALID),
    ],
)
def test_schema_load_refusals_render_only_their_registered_key(
    tmp_path: Path,
    filename: str,
    payload: str,
    condition: str,
) -> None:
    """Every reachable schema-load refusal renders the key and reports a condition.

    Driven by real files on disk: an unterminated quote the parser refuses, a
    document declaring no sections, a scalar where an array of tables belongs,
    and a well-formed document whose values violate the strict model. No patch,
    stub or monkeypatch participates.
    """
    schema_path = tmp_path / filename
    schema_path.write_text(payload, encoding="utf-8")

    with pytest.raises(UserProfileSchemaLoadError) as exc_info:
        load_user_profile_schema(schema_path)

    assert str(exc_info.value) == SCHEMA_LOAD_MESSAGE_KEY
    assert exc_info.value.translated_message == SCHEMA_LOAD_MESSAGE_KEY
    assert exc_info.value.context is not None
    assert exc_info.value.context["condition"] == condition
    assert exc_info.value.context["path"] == str(schema_path)
    assert exc_info.value.context["schema"] == "user_profile"


def test_schema_model_validation_refusal_counts_violations_without_restating_them(tmp_path: Path) -> None:
    """The strict-model failure reports how many constraints failed, not which values.

    The count is the fact; the typed detail survives as the exception's cause
    rather than being flattened into the refusal, which is what the previous
    shape did with an interpolated ``{exc}``.
    """
    schema_path = tmp_path / "contract-violating.toml"
    schema_path.write_text(_CONTRACT_VIOLATING_SCHEMA, encoding="utf-8")

    with pytest.raises(UserProfileSchemaLoadError) as exc_info:
        load_user_profile_schema(schema_path)

    context = exc_info.value.context
    assert context is not None
    violation_count = context["violation_count"]
    assert isinstance(violation_count, int)
    assert violation_count >= 1
    assert isinstance(exc_info.value.__cause__, ValidationError)
    assert len(exc_info.value.__cause__.errors()) == violation_count


def test_no_refusal_construction_passes_a_positional_argument() -> None:
    """Defect shape one: an authored sentence positioned beside a registered key."""
    offenders = [
        f"{module}:{node.lineno}"
        for module in _SCANNED_MODULES
        for node in _pinned_constructions(_module_tree(module))
        if node.args
    ]

    assert offenders == []


def test_no_refusal_construction_passes_a_message_keyword() -> None:
    """Defect shape two: the same sentence as a keyword a positional scan misses."""
    offenders = [
        f"{module}:{node.lineno}"
        for module in _SCANNED_MODULES
        for node in _pinned_constructions(_module_tree(module))
        for keyword in node.keywords
        if keyword.arg == "message"
    ]

    assert offenders == []


def test_no_refusal_class_declares_a_message_parameter() -> None:
    """Defect shape three, first half: no constructor slot an English default fits.

    A ``message`` parameter with a prose default puts the sentence into
    ``args`` while every call site reads clean, so no raise-site scan can see
    it. Removing the slot removes the shape.
    """
    offenders: list[str] = []
    for module in _SCANNED_MODULES:
        for class_def in _pinned_class_defs(_module_tree(module)):
            for node in ast.walk(class_def):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != "__init__":
                    continue
                arguments = node.args
                named = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
                offenders.extend(
                    f"{module}:{class_def.name}.{argument.arg}" for argument in named if argument.arg == "message"
                )

    assert offenders == []


def _docstring_node_ids(scope: ast.AST) -> frozenset[int]:
    """Return the identities of every docstring literal declared inside ``scope``.

    Docstrings are prose by definition and are never rendered to an operator.
    They are identified structurally -- the leading expression statement of a
    class, module or function body -- rather than by shape, so a genuine
    sentence assigned anywhere else cannot be mistaken for one.
    """
    identities: set[int] = set()
    for node in ast.walk(scope):
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            continue
        first = node.body[0] if node.body else None
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            identities.add(id(first.value))
    return frozenset(identities)


def test_no_refusal_class_body_authors_prose() -> None:
    """Defect shape three, second half: prose built inside the constructor.

    Every string literal in these class bodies must be a pinned message key or
    a fact key; an f-string is refused outright, because a sentence composed
    from the failure is exactly what this shape produces and no call site can
    see it. Docstrings are excluded structurally, by position in the body.
    """
    prose: list[str] = []
    interpolations: list[str] = []
    for module in _SCANNED_MODULES:
        for class_def in _pinned_class_defs(_module_tree(module)):
            docstrings = _docstring_node_ids(class_def)
            for node in ast.walk(class_def):
                if isinstance(node, ast.JoinedStr):
                    interpolations.append(f"{module}:{node.lineno}")
                if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                    continue
                if id(node) in docstrings or node.value in _PINNED_MESSAGE_KEYS:
                    continue
                if " " not in node.value:
                    continue
                prose.append(f"{module}:{node.lineno}:{node.value}")

    assert interpolations == []
    assert prose == []


def test_no_refusal_fact_carries_command_identity_or_a_reserved_action_key() -> None:
    """Command identity belongs to the typed action projection, never to a fact.

    Both halves are checked: a reserved key name, and a value that names the
    executable. The envelope's own notice contract refuses both, and this holds
    the producer to the same rule at the layer that builds it.
    """
    reserved: list[str] = []
    commands: list[str] = []
    for module in _SCANNED_MODULES:
        tree = _module_tree(module)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values, strict=True):
                if isinstance(key, ast.Constant) and key.value in _RESERVED_ACTION_KEYS:
                    reserved.append(f"{module}:{node.lineno}:{key.value}")
                if isinstance(value, ast.Constant) and isinstance(value.value, str) and "aeat" in value.value.split():
                    commands.append(f"{module}:{node.lineno}:{value.value}")

    assert reserved == []
    assert commands == []


def test_reserved_action_key_set_matches_the_envelope_contract() -> None:
    """Anchor the reserved set to the shipped contract rather than a local copy.

    Constructing a notice with each name proves the envelope refuses it, so
    this set cannot quietly fall behind the contract it mirrors.
    """
    for key in sorted(_RESERVED_ACTION_KEYS):
        with pytest.raises(ValidationError):
            Notice(severity=NoticeSeverity.INFO, code="probe", message="probe", context={key: "value"})


def test_the_scanned_modules_are_the_ones_that_declare_and_build_the_refusals() -> None:
    """Refuse a vacuous sweep: the pinned classes must actually live where scanned.

    A rename or a move would otherwise leave every structural assertion above
    matching nothing and passing. Only the schema-load refusal is BUILT inside
    this package; the drift refusal is declared here and constructed by the
    application repository that loads stored records, so the construction
    anchor names the one class this package builds.
    """
    declared = {class_def.name for module in _SCANNED_MODULES for class_def in _pinned_class_defs(_module_tree(module))}
    built = {
        node.func.id
        for module in _SCANNED_MODULES
        for node in _direct_constructions(_module_tree(module))
        if isinstance(node.func, ast.Name)
    }
    delegating = sum(len(_base_initialisations(_module_tree(module))) for module in _SCANNED_MODULES)

    assert declared == _PINNED_ERROR_NAMES
    assert built == {"UserProfileSchemaLoadError"}
    assert delegating == len(_PINNED_ERROR_NAMES)
    assert inspect.getsourcefile(UserProfileSchemaLoadError) == str(_PACKAGE_ROOT / "errors.py")
    assert inspect.getsourcefile(StoredProfileDriftError) == str(_PACKAGE_ROOT / "errors.py")
