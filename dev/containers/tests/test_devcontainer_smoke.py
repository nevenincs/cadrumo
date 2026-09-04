"""Tests for the devcontainer smoke checks' refusals.

`dev.quality.module_test_reach` listed `dev/containers/devcontainer_smoke.py` as
unreached. It runs INSIDE the built image, and each of its checks maps
one-to-one onto a defect that shipped in that image, so the checks themselves
cannot be exercised from this host - the venv is not ``/workspace/.venv``, there
is no baked source tree, and no Chromium is provisioned here.

What can be exercised, and is worth pinning, is what a check says when its
precondition does not hold. These run in CI where the only artefact is a log,
so a refusal that fails to name the missing thing costs a rebuild to diagnose.
Two of the checks pass on this host because the tooling genuinely is present,
which the cases below assert rather than assume - a refusal that fired
everywhere would prove nothing about the image.
"""

from __future__ import annotations

import pytest

from ..devcontainer_smoke import (
    _check_interpreter,
    _check_just,
    _check_project_import,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_a_wrong_virtualenv_is_refused_by_name(capsys: pytest.CaptureFixture[str]) -> None:
    """The image pins one venv path; anything else means PATH was reset.

    The check exists because ``bash -lc`` re-runs ``/etc/profile`` and discarded
    the virtualenv, so ``python`` resolved to the system interpreter. Off the
    image this host's venv stands in for that mismatch, and the refusal has to
    name both what it found and what it expected or the reader cannot tell
    which of the two moved.
    """
    with pytest.raises(SystemExit) as refusal:
        _check_interpreter()

    message = str(refusal.value)
    assert "virtualenv is" in message
    assert ".venv" in message
    capsys.readouterr()


def test_the_project_import_check_reports_where_it_imported_from(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A passing import must say WHICH cadrumo it found.

    The check exists to prove the pre-warmed editable install resolves, and an
    unqualified "ok" would pass equally for a stray copy on ``sys.path``.
    """
    _check_project_import()

    out = capsys.readouterr().out
    assert "ok  import cadrumo" in out
    assert "__init__.py" in out


def test_the_just_check_reports_the_version_it_resolved(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Presence is not enough; the check runs it and prints what answered.

    ``postCreateCommand`` is ``just install && just env-setup``, so a ``just``
    that resolves but cannot run fails container creation rather than the build,
    which is the confusing failure this check exists to pre-empt.
    """
    _check_just()

    assert "ok  just" in capsys.readouterr().out


def test_every_check_is_named_for_what_it_proves() -> None:
    """The module is run as one script; its function names are the report's index.

    A check named for its mechanism rather than its subject would leave a CI
    log naming a step nobody can map back to a defect.
    """
    from .. import devcontainer_smoke

    checks = [name for name in vars(devcontainer_smoke) if name.startswith("_check_")]

    assert set(checks) == {
        "_check_interpreter",
        "_check_project_import",
        "_check_just",
        "_check_unit_collection",
        "_check_chromium_launches",
    }
