"""The Modelo 100 cross-domain snapshot gate must never silently skip.

The registry validator runs peer-domain referential-integrity checks
through the abstract ``CrossDomainSnapshotCheck`` Protocol. The concrete
renta first-slice routing check registers itself only as an import side
effect of the ``aeat.domain.renta`` package. A snapshot validated on an
import path that never imports ``renta`` would otherwise pass the BOE-
prescribed first-slice routing referential-integrity gate silently
absent.

``_check_cross_domain_snapshot_routing`` defends against that: when the
snapshot under validation is a Modelo 100 revision and zero cross-domain
checks are registered, the validator fails loudly instead of skipping a
known-required gate. The gate runs inside ``_check_all_id_references``,
which ``_build_validated_snapshot`` invokes for every snapshot it
constructs.

These tests run in fresh subprocesses so the registry's module-level
``_CROSS_DOMAIN_SNAPSHOT_CHECKS`` list reflects exactly the import path
under test -- a guarantee no in-process test can give once any sibling
test in the session has imported ``renta`` and populated that list.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _run_python(*fragments: str) -> subprocess.CompletedProcess[str]:
    """Run dedented ``fragments`` in a fresh interpreter as one script.

    Each fragment is dedented independently so fragments authored at
    different indentation levels compose into one valid top-level
    script.
    """

    source = "\n".join(textwrap.dedent(fragment) for fragment in fragments)
    return subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_m100_build_on_renta_free_import_path_fails_loudly() -> None:
    """Building an M100 snapshot without ``renta`` imported must raise.

    The subprocess imports only the registry (never ``aeat.domain.renta``)
    and builds a Modelo 100 snapshot from the bundled registry. With zero
    cross-domain checks registered the referential-integrity gate inside
    ``_build_validated_snapshot`` must raise ``RegistryValidationError``
    naming the missing renta first-slice routing check -- it must NOT
    build clean with the gate silently skipped.
    """

    result = _run_python(
        """
        import sys

        from aeat.core.resources import bundled_path
        from aeat.domain.calculations.registry import (
            RegistryValidationError,
            load_registry_tree,
        )
        from aeat.domain.calculations.registry._snapshot import _build_validated_snapshot
        from aeat.domain.calculations.registry._validate import _CROSS_DOMAIN_SNAPSHOT_CHECKS

        assert "aeat.domain.renta" not in sys.modules, (
            "renta must not be imported on this path"
        )
        assert _CROSS_DOMAIN_SNAPSHOT_CHECKS == [], (
            "no cross-domain checks must be registered without renta imported"
        )

        source_root = bundled_path("registry", "aeat")
        modelos, catalogues = load_registry_tree(source_root)
        modelo_100 = next(m for m in modelos if m.id == "100")
        revision = next(iter(modelo_100.revisions.values()))
        period = next(iter(revision.period_selector.periods))

        try:
            _build_validated_snapshot(
                modelo_100,
                catalogues,
                filing_year=int(revision.id),
                period=period,
                revision_id=revision.id,
            )
        except RegistryValidationError as exc:
            message = str(exc)
            assert "cross-domain snapshot check" in message, message
            assert "modelo 100" in message, message
            print("LOUD_FAILURE_RAISED")
        else:
            raise AssertionError(
                "M100 snapshot built with the renta first-slice routing "
                "gate silently skipped"
            )
        """
    )

    assert result.returncode == 0, (
        f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "LOUD_FAILURE_RAISED" in result.stdout, result.stdout


def test_m100_build_succeeds_when_renta_is_imported() -> None:
    """Importing ``renta`` registers the check; the M100 build then passes.

    Companion to the loud-failure case: it proves the guard is satisfied
    by the registration side effect rather than by a blanket refusal to
    build M100. The subprocess imports ``aeat.domain.renta`` before
    building, so the first-slice routing check is registered and the
    committed M100 snapshot passes the referential-integrity gate.
    """

    result = _run_python(
        """
        import aeat.domain.renta  # noqa: F401  -- registration side effect

        from aeat.core.resources import bundled_path
        from aeat.domain.calculations.registry import load_registry_tree
        from aeat.domain.calculations.registry._snapshot import _build_validated_snapshot
        from aeat.domain.calculations.registry._validate import _CROSS_DOMAIN_SNAPSHOT_CHECKS

        assert _CROSS_DOMAIN_SNAPSHOT_CHECKS, (
            "importing renta must register at least one cross-domain check"
        )

        source_root = bundled_path("registry", "aeat")
        modelos, catalogues = load_registry_tree(source_root)
        modelo_100 = next(m for m in modelos if m.id == "100")
        revision = next(iter(modelo_100.revisions.values()))
        period = next(iter(revision.period_selector.periods))

        snapshot = _build_validated_snapshot(
            modelo_100,
            catalogues,
            filing_year=int(revision.id),
            period=period,
            revision_id=revision.id,
        )
        assert snapshot.modelo.id == "100"
        print("M100_BUILD_OK")
        """
    )

    assert result.returncode == 0, (
        f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "M100_BUILD_OK" in result.stdout, result.stdout


def test_non_m100_build_on_renta_free_path_does_not_require_the_gate() -> None:
    """A non-M100 snapshot built without ``renta`` must not be blocked.

    The loud-failure guard is scoped to Modelo 100 -- the only modelo with
    a known-required renta cross-domain gate. A non-100 modelo (here
    Modelo 303) built on a renta-free import path must pass the
    referential-integrity gate without the cross-domain registration
    requirement firing.
    """

    result = _run_python(
        """
        import sys

        from aeat.core.resources import bundled_path
        from aeat.domain.calculations.registry import load_registry_tree
        from aeat.domain.calculations.registry._snapshot import _build_validated_snapshot
        from aeat.domain.calculations.registry._validate import _CROSS_DOMAIN_SNAPSHOT_CHECKS

        assert "aeat.domain.renta" not in sys.modules, (
            "renta must not be imported on this path"
        )
        assert _CROSS_DOMAIN_SNAPSHOT_CHECKS == [], (
            "no cross-domain checks must be registered without renta imported"
        )

        source_root = bundled_path("registry", "aeat")
        modelos, catalogues = load_registry_tree(source_root)
        modelo_303 = next(m for m in modelos if m.id == "303")
        revision = next(iter(modelo_303.revisions.values()))
        period = next(iter(revision.period_selector.periods))
        filing_year = revision.period_selector.year_from
        assert filing_year is not None, "modelo 303 revision must declare year_from"

        snapshot = _build_validated_snapshot(
            modelo_303,
            catalogues,
            filing_year=filing_year,
            period=period,
            revision_id=revision.id,
        )
        assert snapshot.modelo.id == "303"
        print("M303_BUILD_OK")
        """
    )

    assert result.returncode == 0, (
        f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "M303_BUILD_OK" in result.stdout, result.stdout
