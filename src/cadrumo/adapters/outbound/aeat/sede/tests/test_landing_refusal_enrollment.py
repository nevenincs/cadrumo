"""Enrollment gate: a sede module that drives a form must refuse its landing.

The package's other no-write walls each miss a browser-driven navigation
by construction. The forbidden-verb source scan deliberately PERMITS
``click`` / ``fill`` / ``press`` / ``check`` / ``select_option``, because
reads here are driven by opening selectors and submitting consulta forms.
The first-party HTTP guard refuses a non-GET method but is never
consulted for the form POST a click issues. And the boundary records'
``mode: Literal["read"]`` marker has no production reader at all.

So a ``page.click`` on a filing control added to a module with no landing
refusal would pass every one of them. Before this gate, what prevented
that was review. This gate makes it a mechanism: a module that drives a
form control and does not refuse its landing fails here, and the failure
names the module.

The gate is a source scan and is therefore the WEAKER half of each
module's proof -- a static scan cannot see where a redirect chain ends.
The runtime rules the individual driver proofs exercise are the primary
wall. This one answers a question those cannot: is every driver wired to
one at all.

Because a scan that matches nothing passes vacuously, the gate verifies
its own detectors before it judges anything: it asserts that the modules
known to drive forms are actually detected as such, and that the modules
known to carry a landing rule are actually detected as enrolled. Either
detector silently ceasing to match reds the gate rather than greening it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ......core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SEDE_ROOT = Path(__file__).resolve().parent.parent

#: Playwright methods that drive a control on an AEAT page. Each one can
#: cause AEAT to dispatch the browser somewhere the driver did not choose,
#: which is precisely what a landing rule exists to check.
_FORM_DRIVING_METHODS: frozenset[str] = frozenset(
    {
        "click",
        "dblclick",
        "fill",
        "press",
        "select_option",
        "set_input_files",
        "tap",
    },
)

#: Modules exempt from enrollment, each with the reason it does not need a
#: landing rule of its own. An exemption is a statement about the module's
#: behaviour, not a mute button: a module that starts driving AEAT controls
#: must be removed from here rather than left with a stale reason.
_EXEMPT_MODULES: dict[str, str] = {
    "_renta_web_open_safety.py": (
        "Drives no AEAT control. It is the click-time guard the Renta WEB Open "
        "driver routes its clicks through, plus the page-level dialog and "
        "navigation safety net; the driver it guards carries the landing rule."
    ),
}

#: Modules that must be DETECTED as form-driving, asserted before the gate
#: judges anything. If the detector stops matching these, it stops matching
#: everything, and a scan that matches nothing passes vacuously.
_KNOWN_FORM_DRIVING: frozenset[str] = frozenset(
    {
        "_censal_datos.py",
        "_declarations.py",
        "_declarations_fetch.py",
        "_groi_check.py",
        "_iva_compensation_wallet.py",
        "_nif_iva_check.py",
        "_renta_web_open.py",
    },
)

#: Modules that must be DETECTED as landing-enrolled, for the same reason
#: in the other direction: an enrollment detector that matches nothing
#: would report every module unenrolled, which is loud, but one that
#: matches everything would report every module enrolled, which is silent.
_KNOWN_ENROLLED: frozenset[str] = frozenset(
    {
        "_censal_datos.py",
        "_declarations.py",
        "_declarations_fetch.py",
        "_groi_check.py",
        "_iva_compensation_wallet.py",
        "_nif_iva_check.py",
        "_renta_web_open.py",
        "_walker.py",
    },
)


def _production_modules() -> tuple[Path, ...]:
    """Every production .py in the sede package, tests and caches excluded."""
    return tuple(
        path
        for path in scan_directory(_SEDE_ROOT, pattern="*.py", recursive=True)
        if "__pycache__" not in path.parts and "tests" not in path.parts
    )


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _drives_a_form_control(tree: ast.Module) -> bool:
    """Return whether the module calls a Playwright control-driving method."""
    return any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _FORM_DRIVING_METHODS
        for node in ast.walk(tree)
    )


def _is_landing_refusal(name: str) -> bool:
    """Return whether ``name`` names a landing refusal.

    Matches the shared rule and any module-local rule named for what it
    does, which is the shape every enrolled driver uses: a public
    ``assert_<surface>_read_landing`` exercised by that driver's proof,
    plus a private reader that lifts the URL off the page.
    """
    return name.endswith("_landing") or name.endswith("_landing_url_readable")


def _refuses_a_landing(tree: ast.Module) -> bool:
    """Return whether a landing refusal is called from a NAVIGATION path.

    Deliberately not "does the module define or mention one". A module
    can carry a perfectly good landing rule that nothing on the live path
    ever calls, and that module is exactly as unguarded as one with no
    rule at all -- while reading, to a scan and to a reviewer, as
    enrolled.

    The discriminator is the enclosing function: every navigation in this
    package is ``async`` because it awaits Playwright, while the
    module-local rule definitions and their sync wrappers are not. So a
    refusal reached only from a sync helper -- the shape a rule left
    wired to nothing takes -- does not count.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) and _is_landing_refusal(inner.func.id):
                return True
    return False


class TestDetectorsAreNotVacuous:
    """The gate verifies its own instruments before judging anything."""

    def test_production_modules_are_found(self) -> None:
        assert len(_production_modules()) > 10

    def test_the_form_driving_detector_matches_the_modules_known_to_drive_forms(self) -> None:
        detected = {path.name for path in _production_modules() if _drives_a_form_control(_parse(path))}
        missing = _KNOWN_FORM_DRIVING - detected
        assert not missing, (
            "the form-driving detector no longer matches modules known to drive AEAT controls, "
            f"so this gate would pass vacuously: {sorted(missing)}"
        )

    def test_the_enrollment_detector_matches_the_modules_known_to_be_enrolled(self) -> None:
        detected = {path.name for path in _production_modules() if _refuses_a_landing(_parse(path))}
        missing = _KNOWN_ENROLLED - detected
        assert not missing, (
            "the enrollment detector no longer matches modules known to carry a landing rule, "
            f"so this gate reports enrollment it cannot see: {sorted(missing)}"
        )

    def test_the_enrollment_detector_does_not_match_everything(self) -> None:
        """A detector that matched every module would report universal enrollment."""
        detected = {path.name for path in _production_modules() if _refuses_a_landing(_parse(path))}
        assert detected != {path.name for path in _production_modules()}


class TestEveryFormDrivingModuleRefusesItsLanding:
    """The gate itself."""

    def test_no_form_driving_module_is_missing_a_landing_refusal(self) -> None:
        offenders: list[str] = []
        for path in _production_modules():
            if path.name in _EXEMPT_MODULES:
                continue
            tree = _parse(path)
            if _drives_a_form_control(tree) and not _refuses_a_landing(tree):
                offenders.append(path.relative_to(_SEDE_ROOT).as_posix())
        assert not offenders, (
            "these sede modules drive an AEAT form control but never refuse the landing that "
            "follows, so a click onto a filing control there would pass the forbidden-verb scan "
            "(which permits click), pass the first-party HTTP guard (never consulted for a browser "
            f"form POST) and pass the read-mode marker (never read): {offenders}"
        )

    def test_every_exemption_names_a_module_that_still_exists(self) -> None:
        """A stale exemption is a hole nobody can see."""
        present = {path.name for path in _production_modules()}
        assert set(_EXEMPT_MODULES) <= present

    def test_every_exemption_carries_a_reason(self) -> None:
        assert all(reason.strip() for reason in _EXEMPT_MODULES.values())

    def test_no_exempt_module_actually_drives_a_form_control(self) -> None:
        """An exemption claims the module drives nothing; hold it to that."""
        for path in _production_modules():
            if path.name not in _EXEMPT_MODULES:
                continue
            assert not _drives_a_form_control(_parse(path)), (
                f"{path.name} is exempt from the landing-refusal gate on the grounds that it "
                "drives no AEAT control, but it now drives one; remove the exemption and give "
                "it a landing rule"
            )
