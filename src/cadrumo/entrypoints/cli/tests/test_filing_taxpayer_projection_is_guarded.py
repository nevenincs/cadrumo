"""A filing path refuses an undeclared tax identity instead of substituting one.

``projection_for_taxpayer`` substitutes a checksum-valid synthetic NIF when the
operator has declared none. On a read-only surface that is deliberate: a
calendar must not drop filed evidence merely because an identity is
undeclared. On a filing surface it is the opposite of what is wanted, because
the value is written into the exported declaration as the declarant -- so an
operator who never entered their NIF receives a file identifying them as
somebody else, and nothing downstream can tell that apart from a real
identity.

**Where the boundary lives.** It used to be a CLI helper,
``filing_taxpayer_or_refuse``, that each filing command had to remember to
call. Routing the private entrypoints through the local runtime moved the
projection out of the command modules entirely: a filing command now submits a
request, and the executor resolves the taxpayer through
``resolve_active_workflow_profile`` -> ``load_active_taxpayer_profile`` ->
``taxpayer_profile_from_record``, which refuses an undeclared identity before
the placeholder projection can run. One owner, reached by every frontend,
replaces a per-command call site.

This gate therefore watches two things: that no CLI filing module reintroduces
a direct placeholder projection, and that the single application-layer owner
still refuses before it projects. Both halves are source-level on purpose. The
failure mode is a NEW filing command or a reordered guard -- sites that do not
exist yet and have no test of their own. The behaviour the gate protects is
exercised by ``application/wizard/tests/test_terminal_preconditions.py`` and
``entrypoints/tests/profile_persistence/test_profile_readiness_gate.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLI_ROOT = Path(__file__).resolve().parents[1]
_STATUS_MODULE = _CLI_ROOT.parents[1] / "application" / "wizard" / "status.py"

#: Modules that build, verify, package or export a declaration. Every one
#: writes or transmits the declarant identity, so none may name the declarant
#: itself: the identity comes from the guarded resolver the executor uses.
_FILING_MODULES: frozenset[str] = frozenset(
    {
        "_modelo_export_cli.py",
        "_app_quickfile.py",
        "_modelo_review_package_cli.py",
        "_modelo_work_verification_cli.py",
    },
)

_PLACEHOLDER_PROJECTIONS: frozenset[str] = frozenset({"profile_to_taxpayer", "projection_for_taxpayer"})
_GUARDED_OWNER = "taxpayer_profile_from_record"
_IDENTITY_REFUSAL = "_require_active_profile_tax_id"


def _called_names(module_path: Path) -> set[str]:
    """Return every bare function name called in ``module_path``."""
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    return {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}


def _function(module_path: Path, name: str) -> ast.FunctionDef:
    """Return the one top-level function definition named ``name``."""
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(matches) == 1, f"{module_path.name} does not define exactly one {name}: found {len(matches)}"
    return matches[0]


def test_every_filing_module_exists_where_this_gate_expects_it() -> None:
    """Anchor the module list, so a rename cannot make this gate pass vacuously.

    Without this, moving or renaming a filing module would silently empty the
    corpus below and every assertion would hold over nothing.
    """
    missing = sorted(name for name in _FILING_MODULES if not (_CLI_ROOT / name).is_file())
    assert not missing, (
        f"filing modules named by this gate no longer exist: {missing}. "
        "They were renamed or moved -- update this list rather than deleting the entry, "
        "or the guard stops covering a surface that still files."
    )
    assert _STATUS_MODULE.is_file(), (
        f"the guarded taxpayer resolver is no longer at {_STATUS_MODULE}. "
        "Point this gate at its new home; do not delete the assertion."
    )


@pytest.mark.parametrize("module_name", sorted(_FILING_MODULES))
@pytest.mark.parametrize("projection", sorted(_PLACEHOLDER_PROJECTIONS))
def test_a_filing_module_does_not_call_a_placeholder_projection(module_name: str, projection: str) -> None:
    """A filing command must not name the declarant at all, guarded or otherwise.

    Both spellings are refused: the CLI wrapper and the application projection
    it wrapped. Either one substitutes a checksum-valid placeholder NIF for an
    undeclared identity and would file under it.
    """
    called = _called_names(_CLI_ROOT / module_name)

    assert projection not in called, (
        f"{module_name} calls {projection}, which substitutes a checksum-valid placeholder "
        f"NIF for an undeclared identity and would file under it. The declarant comes from "
        f"the executor's guarded resolver, not from the command module."
    )


def test_the_guarded_owner_refuses_before_it_projects() -> None:
    """The positive half: absence of the bad call is not evidence of the good one.

    A codebase that stopped projecting a taxpayer anywhere would satisfy every
    assertion above while quietly dropping the identity requirement. The one
    owner must still refuse an undeclared identity, and must do so BEFORE it
    reaches the substituting projection -- a reordering that projected first
    would hand back a placeholder and never raise.
    """
    owner = _function(_STATUS_MODULE, _GUARDED_OWNER)
    # ``ast.walk`` yields breadth-first, which is not source order; the whole
    # point of this assertion is which call runs first, so sort by position.
    calls = sorted(
        (node for node in ast.walk(owner) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)),
        key=lambda node: (node.lineno, node.col_offset),
    )
    called = [node.func.id for node in calls if isinstance(node.func, ast.Name)]

    assert _IDENTITY_REFUSAL in called, (
        f"{_GUARDED_OWNER} no longer calls {_IDENTITY_REFUSAL}. Nothing else stands between a "
        "filing request and a placeholder declarant; restore the refusal rather than this gate."
    )
    assert "projection_for_taxpayer" in called, (
        f"{_GUARDED_OWNER} no longer projects a taxpayer. If the projection moved, point this "
        "gate at its new owner; otherwise the filing path has no declarant at all."
    )
    assert called.index(_IDENTITY_REFUSAL) < called.index("projection_for_taxpayer"), (
        "the identity refusal now runs after the substituting projection, so an undeclared "
        "identity is replaced by a placeholder before anything can refuse it."
    )
