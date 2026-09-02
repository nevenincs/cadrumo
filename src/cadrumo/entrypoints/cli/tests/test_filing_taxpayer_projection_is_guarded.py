"""Filing-grade CLI modules must not reach the placeholder-substituting projection.

``profile_to_taxpayer`` substitutes a checksum-valid synthetic NIF when the
operator has declared none. On a read-only surface that is deliberate: the
calendar must not drop a taxpayer's filed evidence merely because their identity
is undeclared. On a filing surface it is the opposite of what is wanted, because
the value is written into the exported declaration as the declarant -- so an
operator who never entered their NIF receives a file identifying them as
somebody else, and nothing downstream can tell that apart from a real identity.

The defect this guards was not the absence of a check. It was that the two
populations shared one constructor, so the filing commands and the read-only
commands were indistinguishable at the call site. ``filing_taxpayer_or_refuse``
is the filing boundary they were missing.

This is a source-level gate rather than a behavioural one on purpose. The
failure mode is a NEW filing command calling the raw projection -- a site that
does not exist yet and therefore has no test of its own. A behavioural test can
only cover the commands someone remembered to write it for; this covers the ones
nobody has written yet, which is where the class actually returns.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLI_ROOT = Path(__file__).resolve().parents[1]

#: Modules that build, verify, package or export a declaration. Every one writes
#: or transmits the declarant identity, so each must refuse an undeclared NIF
#: rather than file under a placeholder.
_FILING_MODULES: frozenset[str] = frozenset(
    {
        "_modelo_export_cli.py",
        "_app_quickfile.py",
        "_modelo_review_package_cli.py",
        "_modelo_work_verification_cli.py",
    },
)

_PLACEHOLDER_PROJECTION = "profile_to_taxpayer"
_GUARDED_PROJECTION = "filing_taxpayer_or_refuse"


def _called_names(module_path: Path) -> set[str]:
    """Return every bare function name called in ``module_path``."""
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    return {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}


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


@pytest.mark.parametrize("module_name", sorted(_FILING_MODULES))
def test_a_filing_module_does_not_call_the_placeholder_projection(module_name: str) -> None:
    """A filing command must route through the refusing helper, not the raw projection."""
    called = _called_names(_CLI_ROOT / module_name)

    assert _PLACEHOLDER_PROJECTION not in called, (
        f"{module_name} calls {_PLACEHOLDER_PROJECTION}, which substitutes a checksum-valid "
        f"placeholder NIF for an undeclared identity and would file under it. "
        f"Call {_GUARDED_PROJECTION} instead, which refuses naming the missing fact."
    )


@pytest.mark.parametrize("module_name", sorted(_FILING_MODULES))
def test_a_filing_module_actually_reaches_the_guarded_helper(module_name: str) -> None:
    """The positive half: absence of the bad call is not evidence of the good one.

    A module that stopped projecting a taxpayer altogether would pass the
    assertion above while quietly dropping the identity requirement. Requiring
    the guarded call keeps "does not use the unsafe helper" from being satisfied
    by using neither.
    """
    called = _called_names(_CLI_ROOT / module_name)

    assert _GUARDED_PROJECTION in called, (
        f"{module_name} no longer calls {_GUARDED_PROJECTION}. If it genuinely stopped "
        "needing a taxpayer projection, remove it from this gate's module list with a "
        "stated reason; otherwise the identity refusal is no longer reached."
    )


def test_the_read_only_surface_still_uses_the_unguarded_projection() -> None:
    """The two populations must stay distinguishable, or this gate proves nothing.

    ``_overview`` is the canonical read-only caller, and its use of the
    placeholder-substituting projection is deliberate -- a shipped test
    (``test_calendar_evidence_survives_undeclared_nif``) depends on it. If the
    overview surface were ever swept onto the refusing helper, the distinction
    this gate enforces would have collapsed and every assertion above would be
    describing a codebase with only one population.
    """
    called = _called_names(_CLI_ROOT / "_overview.py")

    assert _PLACEHOLDER_PROJECTION in called, (
        "_overview.py no longer calls the unguarded projection. Either the read-only "
        "surface was wrongly swept onto the filing helper -- which would refuse the "
        "calendar for an undeclared NIF -- or the projection was renamed and this gate "
        "now watches a name nothing uses."
    )
