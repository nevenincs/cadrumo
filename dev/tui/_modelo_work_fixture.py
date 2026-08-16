"""A real M130 work unit the harness owns, for the live modelo wizard surface.

Every other harness surface renders over the shared ``profile`` root
:mod:`._fixture` provisions -- a minimal profile carrying only its output
language. The live modelo-work wizard needs more: entity type, activity and
an IRPF income category are what let the registry resolve a real, calculable
work unit rather than a bare stub with zero outstanding questions, and a
persisted work unit is itself a durable record. Mutating the shared root to
carry those facts would change what a concurrent reviewer sees on
``login``/``manager``/``status`` mid-review, so this surface gets its own
dedicated storage root instead -- purely additive, nothing shared changes.

The fixture shape mirrors the one the oracle-grounded wizard CLI test suite
(``entrypoints/cli/tests/test_modelo_work_wizard.py``,
``_modelo_work_ux_support.py``) already proves against for Modelo 130: the
same profile facts, the same ``resolve_registry_revision_for_work_target`` +
``ensure_modelo_work_unit_for_active_target`` pair the CLI's own
``work create`` command calls, and the same
:func:`~cadrumo.application.user_profile.open_test_profile_session` binding an
application-layer call outside a CLI command's own bootstrap needs.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from cadrumo.tests.profile_capsule import open_test_profile_session

from ._fixture import workspace

MODELO = "130"
FILING_YEAR = 2025
PERIOD_CODE = "1T"
"""The addressed work unit: Modelo 130 (pago fraccionado IRPF, estimación
directa), 2025 1T. Chosen because it is the exact fixture the wizard CLI
test suite's oracle already exercises, so a real, previously-verified
registry revision resolves rather than a coordinate invented for this
harness alone."""

_PROFILE_NAME = "operator"

_PROFILE_ARGS = (
    "config",
    "profile",
    "create",
    _PROFILE_NAME,
    "--quiet",
    "--accept-defaults",
    "--entity-type",
    "natural_person",
    "--irpf-income-categories",
    "actividad_economica",
    "--tax-id",
    "12345678Z",
    "--name",
    "Operator",
    "--surnames",
    "Readiness",
    "--activity",
    "design",
)
"""Verbatim the fixture ``_modelo_work_ux_support._create_profile()`` uses
for the M130 wizard's own oracle-grounded test suite -- reused rather than
re-derived so this harness profile is provably the shape a real IRPF
actividad económica filer's profile takes, not a guess."""


@contextmanager
def harness_modelo_work_storage() -> Iterator[str]:
    """Enter a dedicated storage root, provisioning a real M130 profile.

    Creates the profile through the real ``config profile create`` CLI
    door on first use (idempotent: a profile already on disk is reused,
    never re-created), then holds a real
    :func:`~cadrumo.application.user_profile.open_test_profile_session` open
    for the block -- the same binding
    :func:`~cadrumo.entrypoints.cli._modelo.run_modelo_work_wizard` gets for
    free from the CLI's own command bootstrap, and which an in-process
    caller outside that bootstrap must open explicitly or every
    profile-bound registry/storage read refuses with "no active bucket
    session".

    Yields the active bucket id.
    """
    from cadrumo.core import resolve_active_bucket_id
    from cadrumo.tests.cli_runner import invoke_cached_cli
    from cadrumo.tests.secure_sql import isolated_profile_storage_root

    root = workspace() / "modelo-work-wizard"
    root.mkdir(parents=True, exist_ok=True)
    with isolated_profile_storage_root(tmp_path=root):
        from cadrumo.application.workflow import list_profile_buckets

        if not list_profile_buckets():
            result = invoke_cached_cli(list(_PROFILE_ARGS))
            if result.exit_code != 0:
                message = f"the harness modelo-work-wizard profile could not be created: {result.output}"
                raise RuntimeError(message)

        bucket_id = resolve_active_bucket_id()
        if bucket_id is None:
            message = "the harness modelo-work-wizard profile did not activate after creation"
            raise RuntimeError(message)

        with open_test_profile_session(bucket_id):
            yield bucket_id


def ensure_modelo_work_unit(bucket_id: str) -> str:
    """Return the real M130 1T work-unit id, creating it if absent.

    Calls the exact two application functions
    ``aeat app modelo work create`` calls --
    :func:`~cadrumo.application.modelo.resolve_registry_revision_for_work_target`
    then
    :func:`~cadrumo.application.modelo.ensure_modelo_work_unit_for_active_target`
    -- rather than hand-building a :class:`~cadrumo.domain.modelos.WorkUnit`,
    so the unit this surface renders is addressed exactly as an operator's
    ``work create`` or the wizard's own resolution would address it.
    Idempotent on the four-axis key (``bucket_id``, modelo, filing year,
    period): a re-run across harness sessions resumes the same unit rather
    than erroring or duplicating it.
    """
    from cadrumo.application.modelo import (
        ensure_modelo_work_unit_for_active_target,
        resolve_registry_revision_for_work_target,
    )
    from cadrumo.core import Period

    period = Period.from_year_and_code(FILING_YEAR, PERIOD_CODE)
    revision_id = resolve_registry_revision_for_work_target(
        modelo=MODELO,
        filing_year=FILING_YEAR,
        period=period,
        registry_revision_id=None,
    )
    ensure_result = ensure_modelo_work_unit_for_active_target(
        bucket_id=bucket_id,
        modelo=MODELO,
        filing_year=FILING_YEAR,
        period=period,
        registry_revision_id=revision_id,
        actor="harness",
    )
    return ensure_result.work_unit.work_unit_id


__all__ = [
    "FILING_YEAR",
    "MODELO",
    "PERIOD_CODE",
    "ensure_modelo_work_unit",
    "harness_modelo_work_storage",
]
