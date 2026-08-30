"""CLI surface tests for the `aeat app modelo reconcile` group.

`reconcile import --file PATH` reconciles a local justificante (the default
`--kind`) or a filed declaración (`--kind declaration`, casilla-level compare,
enrolled modelos only); `reconcile list` lists past runs. `reconcile pull`
fetches from AEAT (a live read) and is covered by the application-layer
orchestrator + reconcile_capture tests, not here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....application.workflow.persistence import workflow_state_repository
from ....core import Period
from ....core.casilla_id import validated_casilla_id
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....tests import FIXTURES_DIR
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import set_active_test_profile_facts
from ....tests.registry_observations import registry_grounded_observations

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"

# The committed justificante fixtures all print the canonical AEAT demo NIF
# ``00000000T``. The active profile's ``identity.tax_id`` is what the reconciler
# compares against the parsed evidence ``tax_id``; aligning the seeded operator
# profile to the fixture's printed NIF lets the happy-path reconcile genuinely
# resolve to ``matches`` (instead of a tax_id mismatch against the auto-derived
# per-profile NIF ``register_minimal_profile`` would otherwise assign).
_FIXTURE_PROFILE_TAX_ID = "00000000T"
_WORK_UNIT_TIMESTAMP = datetime(2026, 5, 28, 15, 40, tzinfo=UTC)


_isolated_backend = active_profile_isolated_backend_fixture(
    profile_overrides={"identity.tax_id": _FIXTURE_PROFILE_TAX_ID},
)


def _seed_work_unit(*, modelo: str, filing_year: int, period: str) -> str:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = "r" + "0" * 63
    filing_period = Period.from_year_and_code(filing_year, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period}",
        created_at=_WORK_UNIT_TIMESTAMP,
        updated_at=_WORK_UNIT_TIMESTAMP,
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def test_reconcile_file_happy_path() -> None:
    """`reconcile import --file` matches when the work unit and the committed
    modelo_130 fixture align on modelo and ejercicio."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")

    result = invoke_cached_cli(
        ["app", "modelo", "reconcile", "import", work_unit_id, "--file", str(MODELO_130_FIXTURE)],
    )
    assert result.exit_code == 0, result.output
    assert f"work_unit_id\t{work_unit_id}" in result.output
    assert "source_kind\tjustificante" in result.output
    assert "verdict\tmatches" in result.output
    assert "diffs\t0" in result.output


def test_reconcile_file_mismatch_renders_diff_rows() -> None:
    """A modelo=303 work unit against the modelo_130 fixture mismatches with a modelo diff."""
    work_unit_id = _seed_work_unit(modelo="303", filing_year=2026, period="1T")

    result = invoke_cached_cli(
        ["app", "modelo", "reconcile", "import", work_unit_id, "--file", str(MODELO_130_FIXTURE)],
    )
    assert result.exit_code == 0, result.output
    assert "verdict\tmismatches" in result.output
    assert "diff\tmodelo\twork_unit=303\tevidence=130" in result.output


def test_reconcile_file_requires_the_file_option() -> None:
    """`reconcile import` without `--file` is a usage error, not a silent default."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    result = invoke_cached_cli(["app", "modelo", "reconcile", "import", work_unit_id])
    assert result.exit_code != 0, result.output


def test_reconcile_file_refuses_unknown_work_unit() -> None:
    """A work unit id absent from the active bucket catalogue refuses at the exit code."""
    result = invoke_cached_cli(
        ["app", "modelo", "reconcile", "import", "0" * 64, "--file", str(MODELO_130_FIXTURE)],
    )
    assert result.exit_code != 0, result.output


def test_reconcile_file_by_flag_lands_in_modelo_reconciled_event() -> None:
    """The --by override attaches to the MODELO_RECONCILED event's actor field."""
    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ....domain.buckets.event import BucketEventType

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "reconcile",
            "import",
            work_unit_id,
            "--file",
            str(MODELO_130_FIXTURE),
            "--by",
            "auditor@team",
        ],
    )
    assert result.exit_code == 0, result.output
    catalogue = BucketEventHistoryRepository().load()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.MODELO_RECONCILED and event.object_id == work_unit_id
    ]
    assert matching, "MODELO_RECONCILED event must land on the catalogue"
    assert matching[-1].actor == "auditor@team"


def test_reconcile_list_empty_is_instructive() -> None:
    """With no reconciliations recorded, `reconcile list` lists a clean empty."""
    result = invoke_cached_cli(["--language", "en", "app", "modelo", "reconcile", "list"])
    assert result.exit_code == 0, result.output
    assert "reconciliation_count\t0" in result.output
    assert "No reconciliations recorded yet" in result.output


def test_reconcile_list_lists_recorded_reconciliation() -> None:
    """After a reconcile, `reconcile list` lists the recorded verdict row."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    reconcile = invoke_cached_cli(
        ["app", "modelo", "reconcile", "import", work_unit_id, "--file", str(MODELO_130_FIXTURE)],
    )
    assert reconcile.exit_code == 0, reconcile.output

    result = invoke_cached_cli(["app", "modelo", "reconcile", "list"])
    assert result.exit_code == 0, result.output
    assert "reconciliation_count\t1" in result.output


# --- `--kind declaration`: casilla-level declaración reconcile (#317-#327) --

MODELO_303_DECLARACION_FIXTURE = FIXTURES_DIR / "justificantes" / "303" / "2024-1T.pdf"
"""Synthetic-generated (declared ``synthetic_generated`` in its sidecar), AEAT
Modelo 303 layout-faithful declaración PDF for ejercicio 2024, 1T. Its
extraction has been independently confirmed by
``test_parser_extracts_modelo_303_targets_from_real_redacted_declaration_copy``
(``adapters/inbound/declaracion/tests/test_parser_boundary_m303.py``); the
values asserted below are read straight from that confirmed parse, not
hand-guessed."""

_DECLARACION_FIXTURE_TAX_ID = "Y0000001S"
"""Tax id every committed synthetic declaración fixture under
``fixtures/justificantes/{111,130,190,303,390}/`` prints; must match the active
profile's ``identity.tax_id`` for the reconcile's header identity compare to
pass."""

_M303_2024_1T_REVISION_ID = "2024-hasta-08-y-2t"
"""Law-determined registry revision for M303 filing_year=2024, period=1T
(confirmed via ``authority.snapshot("303", filing_year=2024, period="1T").revision.id``);
required by ``aeat-registry-authority-flow`` so the seeded work unit's
pinned ``revision_id`` matches the resolver's answer."""

# The 9 `computed_casilla_ids` the registry's verification policy actually
# reconciles for this revision AND that the 2024-1T fixture prints; the other
# 4 declared computed ids (`iva.compensacion-disponible-fin-periodo`,
# `iva.compensacion-generada-periodo`, `iva.cuota-deducible-total`,
# `iva.cuota-devengada-total`) are absent from this older fixture's printed
# layout and are deliberately left un-persisted below so both sides are
# `None` for them (a legitimate skip, not a divergence) rather than seeding a
# fabricated value for a casilla the fixture never prints.
_M303_2024_1T_MATCHING_CASILLA_VALUES: dict[str, Decimal] = {
    "27": Decimal("13200.00"),
    "45": Decimal("8400.00"),
    "64": Decimal("4800.00"),
    "66": Decimal("4800.00"),
    "71": Decimal("4800.00"),
    "iva.compensacion-aplicada-periodo": Decimal("0.00"),
    "iva.compensacion-pendiente-periodos-posteriores": Decimal("0.00"),
    "iva.resultado": Decimal("4800.00"),
    "iva.resultado-regimen-general": Decimal("4800.00"),
}


@pytest.fixture
def _declaracion_fixture_profile() -> None:
    """Retarget the module-level autouse profile's `identity.tax_id` to the
    committed declaración fixtures' printed NIF (`Y0000001S`), distinct from
    the module's justificante-fixture NIF (`00000000T`). Reuses the same
    isolated backend `_isolated_backend` already opened for the test rather
    than nesting a second storage root, which `SecureObjectRepository`
    per-bucket session handling does not support."""
    from ....domain.user_profile.values import UserProfileFact

    set_active_test_profile_facts(
        [UserProfileFact(path="identity.tax_id", value=_DECLARACION_FIXTURE_TAX_ID)],
    )


def _seed_declaracion_work_unit_with_revision(
    *,
    modelo: str,
    filing_year: int,
    period_code: str,
    revision_id: str,
    casilla_values: dict[str, Decimal],
) -> str:
    """Seed a work unit plus a persisted, filed `CalculationRevision` carrying
    `casilla_values` — the persisted "computed" side a declaración reconcile
    compares the fixture's "filed" side against. Modelo-agnostic: used by the
    M303, M111 (and, as further modelos are enrolled, M130/M190/M390)
    declaración-kind reconcile tests."""
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    period = Period.from_year_and_code(filing_year, period_code)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period_code}",
        created_at=datetime(2026, 5, 1, tzinfo=UTC),
        updated_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    WorkUnitCatalogueRepository().save(upsert_work_unit(WorkUnitCatalogueRepository().load(), work_unit))

    validated_values = {validated_casilla_id(k, surface="test"): v for k, v in casilla_values.items()}
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=validated_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    repo = CalculationRevisionCatalogueRepository()
    repo.save(
        upsert_calculation_revision(
            repo.load(),
            CalculationRevision(
                calculation_revision_id=calculation_revision_id,
                work_unit_id=work_unit_id,
                state=CalculationRevisionState.PRESENTADO,
                casilla_values=validated_values,
                observations=registry_grounded_observations(
                    modelo=modelo,
                    filing_year=filing_year,
                    period=period_code,
                    casilla_values=validated_values,
                ),
                created_at=datetime(2026, 5, 1, tzinfo=UTC),
                updated_at=datetime(2026, 5, 1, tzinfo=UTC),
                verified_at=datetime(2026, 5, 1, tzinfo=UTC),
                verified_by="test",
                filed_at=datetime(2026, 5, 1, tzinfo=UTC),
                filed_by="test",
                filing_instance_evidence=None,
                source_provenance=(),
            ),
        ),
    )
    return work_unit_id


def _seed_m303_work_unit_with_revision(*, casilla_values: dict[str, Decimal]) -> str:
    return _seed_declaracion_work_unit_with_revision(
        modelo="303",
        filing_year=2024,
        period_code="1T",
        revision_id=_M303_2024_1T_REVISION_ID,
        casilla_values=casilla_values,
    )


def test_reconcile_file_kind_declaration_matches_when_computed_agrees(
    _declaracion_fixture_profile: None,
) -> None:
    """`reconcile import --file --kind declaration` reports a clean `matches` when
    the persisted revision's computed casilla values agree with the filed
    declaración the fixture prints -- the calc-verify-roundtrip claim behind
    acceptance wall #326 (Modelo 303), proven end-to-end through the real CLI
    against a real (synthetic-declared) declaración PDF, not a hand-computed
    in-memory observation."""
    work_unit_id = _seed_m303_work_unit_with_revision(casilla_values=_M303_2024_1T_MATCHING_CASILLA_VALUES)

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "reconcile",
            "import",
            work_unit_id,
            "--file",
            str(MODELO_303_DECLARACION_FIXTURE),
            "--kind",
            "declaration",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "source_kind\tdeclaration" in result.output
    assert "verdict\tmatches" in result.output
    assert "diffs\t0" in result.output


def test_reconcile_file_kind_declaration_catches_casilla_divergence(
    _declaracion_fixture_profile: None,
) -> None:
    """A computed revision that disagrees with the filed declaración on one
    casilla is CAUGHT as a typed `casilla` diff naming both values -- not a
    silent identity `matches` (`no-silent-under-declaration`). Proves the
    engine actually re-derives and compares the casilla, rather than the
    reconcile trivially passing regardless of the persisted value."""
    mismatched = dict(_M303_2024_1T_MATCHING_CASILLA_VALUES)
    mismatched["iva.resultado"] = Decimal("5300.00")  # fixture prints 4800.00
    work_unit_id = _seed_m303_work_unit_with_revision(casilla_values=mismatched)

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "reconcile",
            "import",
            work_unit_id,
            "--file",
            str(MODELO_303_DECLARACION_FIXTURE),
            "--kind",
            "declaration",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "source_kind\tdeclaration" in result.output
    assert "verdict\tmismatches" in result.output
    assert "diff\tiva.resultado\twork_unit=5300.00\tevidence=4800.00" in result.output


# --- Modelo 130 (pagos fraccionados IRPF): printed AEAT box numbers --------
#
# M130's fixture, like M303's, self-detects its own modelo/año/período header
# cleanly with no overrides needed. Modelo 111's, 190's, and 390's real-corpus
# declaración fixtures do NOT carry a detectable "Ejercicio: YYYY" header
# stamp (a real AEAT filing can print the field label as a blank
# dots-placeholder template on the receipt copy, not a filled value); those
# three modelos are enrolled further below in this file, unblocked by the
# work-unit-context override forwarding now landed in `modelo_reconcile`'s
# declaración branch (`application/modelo/reconciliation.py`).

MODELO_130_DECLARACION_FIXTURE = FIXTURES_DIR / "justificantes" / "130" / "2024-1T.pdf"
"""Synthetic-generated M130 declaración PDF for ejercicio 2024, 1T. Extraction
confirmed by ``test_real_redacted_modelo_130_declaration_copy_extracts_partial_casillas``
(``adapters/inbound/declaracion/tests/test_parser_boundary_m130.py``): prints
casillas `03`=5600.00 and `19`=1020.00."""

_M130_2024_1T_REVISION_ID = "2019-y-siguientes"
"""Law-determined registry revision for M130 filing_year=2024, period=1T
(confirmed via ``authority.snapshot("130", filing_year=2024, period="1T").revision.id``)."""

# `computed_casilla_ids` for this revision has 10 entries; only `03` and `19`
# are printed by this fixture. The other 8 are deliberately left un-persisted
# below so both sides are `None` for them (a legitimate skip), matching the
# same pattern the M303 section documents above.
_M130_2024_1T_MATCHING_CASILLA_VALUES: dict[str, Decimal] = {
    "03": Decimal("5600.00"),
    "19": Decimal("1020.00"),
}


def _seed_m130_work_unit_with_revision(*, casilla_values: dict[str, Decimal]) -> str:
    return _seed_declaracion_work_unit_with_revision(
        modelo="130",
        filing_year=2024,
        period_code="1T",
        revision_id=_M130_2024_1T_REVISION_ID,
        casilla_values=casilla_values,
    )


def test_reconcile_file_kind_declaration_m130_matches_when_computed_agrees(
    _declaracion_fixture_profile: None,
) -> None:
    """Acceptance wall #321 (Modelo 130): the persisted revision's computed `03`/`19`
    agree with the filed declaración the fixture prints -- a clean `matches`
    through the real CLI against a real declaración PDF."""
    work_unit_id = _seed_m130_work_unit_with_revision(casilla_values=_M130_2024_1T_MATCHING_CASILLA_VALUES)

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "reconcile",
            "import",
            work_unit_id,
            "--file",
            str(MODELO_130_DECLARACION_FIXTURE),
            "--kind",
            "declaration",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "source_kind\tdeclaration" in result.output
    assert "verdict\tmatches" in result.output
    assert "diffs\t0" in result.output


def test_reconcile_file_kind_declaration_m130_catches_casilla_divergence(
    _declaracion_fixture_profile: None,
) -> None:
    """Acceptance wall #321 (Modelo 130): a computed `19` that disagrees with the
    filed declaración is CAUGHT as a typed `casilla` diff, not a silent
    identity `matches`."""
    mismatched = dict(_M130_2024_1T_MATCHING_CASILLA_VALUES)
    mismatched["19"] = Decimal("1500.00")  # fixture prints 1020.00
    work_unit_id = _seed_m130_work_unit_with_revision(casilla_values=mismatched)

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "reconcile",
            "import",
            work_unit_id,
            "--file",
            str(MODELO_130_DECLARACION_FIXTURE),
            "--kind",
            "declaration",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "source_kind\tdeclaration" in result.output
    assert "verdict\tmismatches" in result.output
    assert "diff\t19\twork_unit=1500.00\tevidence=1020.00" in result.output


# --- Modelo 111 (retenciones trimestrales): printed AEAT box numbers -------
#
# M111's committed declaración fixture lacks an "Ejercicio: YYYY" header
# stamp `parse_declaracion`'s auto-detector requires. `modelo_reconcile`'s
# declaración branch now forwards the addressed work unit's own known
# modelo/filing_year/period as `parse_declaracion` overrides (see
# `application/modelo/reconciliation.py`), which lets this fixture parse without
# requiring a detectable header -- while a genuinely wrong-modelo PDF (a
# detectable template that conflicts with the override) still refuses; see
# `test_reconcile_file_kind_declaration_override_still_catches_wrong_modelo_pdf`.

MODELO_111_DECLARACION_FIXTURE = FIXTURES_DIR / "justificantes" / "111" / "2024-1T.pdf"
"""Synthetic-generated M111 declaración PDF for ejercicio 2024, 1T. Extraction
confirmed by ``test_parser_extracts_modelo_111_casillas_from_corpus``
(``adapters/inbound/declaracion/tests/test_parser_boundary_m111.py``): prints
casillas 07/08/09/28/30.

Its perceptor count, base and retención are distinct values, and each quarter
carries different amounts. While this was a redacted real render every money box
held the same ``1000.00``, so the mismatch assertion below could have been
reading any of them."""

_M111_2024_1T_REVISION_ID = "2019-y-siguientes"
"""Law-determined registry revision for M111 filing_year=2024, period=1T."""

# `computed_casilla_ids` for this revision is exactly {28, 30}. Both are printed
# at 2371.20, which is the form's own arithmetic rather than a repeat: with only
# epígrafe 3 filled and no prior autoliquidación, `28 = 03+06+...+27` reduces to
# `09` and `30 = 28 - 29` reduces to `28`.
_M111_2024_1T_MATCHING_CASILLA_VALUES: dict[str, Decimal] = {
    "28": Decimal("2371.20"),
    "30": Decimal("2371.20"),
}


def _seed_m111_work_unit_with_revision(*, casilla_values: dict[str, Decimal]) -> str:
    return _seed_declaracion_work_unit_with_revision(
        modelo="111",
        filing_year=2024,
        period_code="1T",
        revision_id=_M111_2024_1T_REVISION_ID,
        casilla_values=casilla_values,
    )


def test_reconcile_file_kind_declaration_m111_matches_when_computed_agrees(
    _declaracion_fixture_profile: None,
) -> None:
    """Acceptance wall #318 (Modelo 111): the persisted revision's computed `28`/`30`
    agree with the filed declaración the fixture prints -- a clean `matches`
    through the real CLI against a real declaración PDF whose header lacks a
    detectable ejercicio stamp, proving the work-unit-context override
    forwarding actually lets the parse succeed."""
    work_unit_id = _seed_m111_work_unit_with_revision(casilla_values=_M111_2024_1T_MATCHING_CASILLA_VALUES)

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "reconcile",
            "import",
            work_unit_id,
            "--file",
            str(MODELO_111_DECLARACION_FIXTURE),
            "--kind",
            "declaration",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "source_kind\tdeclaration" in result.output
    assert "verdict\tmatches" in result.output
    assert "diffs\t0" in result.output


def test_reconcile_file_kind_declaration_m111_catches_casilla_divergence(
    _declaracion_fixture_profile: None,
) -> None:
    """Acceptance wall #318 (Modelo 111): a computed `30` that disagrees with the
    filed declaración is CAUGHT as a typed `casilla` diff, not a silent
    identity `matches`."""
    mismatched = dict(_M111_2024_1T_MATCHING_CASILLA_VALUES)
    mismatched["30"] = Decimal("1250.00")  # fixture prints 2371.20
    work_unit_id = _seed_m111_work_unit_with_revision(casilla_values=mismatched)

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "reconcile",
            "import",
            work_unit_id,
            "--file",
            str(MODELO_111_DECLARACION_FIXTURE),
            "--kind",
            "declaration",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "source_kind\tdeclaration" in result.output
    assert "verdict\tmismatches" in result.output
    assert "diff\t30\twork_unit=1250.00\tevidence=2371.20" in result.output


# --- Modelo 390 (IVA resumen anual): compound iva.anual.* casilla ids -------

MODELO_390_DECLARACION_FIXTURE = FIXTURES_DIR / "justificantes" / "390" / "2022-0A.pdf"
"""Synthetic-generated M390 declaración PDF for ejercicio 2022, 0A.

Chosen for its VALUES, not its render. The sibling `2021-0A.pdf` is a real
sanitised specimen whose sanitiser rewrote all thirteen printed amounts to
the same ``1.000,00`` placeholder, so every compound ``iva.anual.*`` casilla
reads alike and a casilla-crossing mismatch would be invisible. The
synthetic `2022-0A.pdf` and `2023-0A.pdf` carry distinct per-casilla
amounts, which is what makes the diff this section asserts observable.

Render language is not a factor in that choice: the parser anchors on
AEAT's Spanish and English presentador-NIF labels alike (the shared
``PRESENTADOR_NIF_LABEL`` fragment in ``adapters/inbound/pdf``), so the
English-render `2021-0A.pdf` parses cleanly too."""

# Modelo 390 ships revisions 2021 through 2025; there is no
# `2010-y-siguientes`. Same defect as the Modelo 190 constant below: a work
# unit seeded with a revision the registry does not carry fails snapshot
# resolution, and reconcile falls back to receipt identity alone.
_M390_2022_0A_REVISION_ID = "2022"
"""Law-determined registry revision for M390 filing_year=2022, period=0A."""

# `computed_casilla_ids` for this revision has 3 entries, all printed by the
# fixture: cuota-devengada-total=10500.00, cuota-deducible-total=8400.00,
# resultado-regimen-general=2100.00.
_M390_2022_0A_MATCHING_CASILLA_VALUES: dict[str, Decimal] = {
    "iva.anual.cuota-devengada-total": Decimal("10500.00"),
    "iva.anual.cuota-deducible-total": Decimal("8400.00"),
    "iva.anual.resultado-regimen-general": Decimal("2100.00"),
}


def _seed_m390_work_unit_with_revision(*, casilla_values: dict[str, Decimal]) -> str:
    return _seed_declaracion_work_unit_with_revision(
        modelo="390",
        filing_year=2022,
        period_code="0A",
        revision_id=_M390_2022_0A_REVISION_ID,
        casilla_values=casilla_values,
    )


def test_reconcile_file_kind_declaration_m390_matches_when_computed_agrees(
    _declaracion_fixture_profile: None,
) -> None:
    """Acceptance wall #327 (Modelo 390): the persisted revision's 3 computed IVA
    anual casillas agree with the filed declaración -- a clean `matches`
    through the real CLI against a real declaración PDF."""
    work_unit_id = _seed_m390_work_unit_with_revision(casilla_values=_M390_2022_0A_MATCHING_CASILLA_VALUES)

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "reconcile",
            "import",
            work_unit_id,
            "--file",
            str(MODELO_390_DECLARACION_FIXTURE),
            "--kind",
            "declaration",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "source_kind\tdeclaration" in result.output
    assert "verdict\tmatches" in result.output
    assert "diffs\t0" in result.output


def test_reconcile_file_kind_declaration_m390_catches_casilla_divergence(
    _declaracion_fixture_profile: None,
) -> None:
    """Acceptance wall #327 (Modelo 390): a computed `iva.anual.resultado-regimen-general`
    that disagrees with the filed declaración is CAUGHT as a typed `casilla`
    diff, not a silent identity `matches`."""
    mismatched = dict(_M390_2022_0A_MATCHING_CASILLA_VALUES)
    mismatched["iva.anual.resultado-regimen-general"] = Decimal("2600.00")  # fixture prints 2100.00
    work_unit_id = _seed_m390_work_unit_with_revision(casilla_values=mismatched)

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "reconcile",
            "import",
            work_unit_id,
            "--file",
            str(MODELO_390_DECLARACION_FIXTURE),
            "--kind",
            "declaration",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "source_kind\tdeclaration" in result.output
    assert "verdict\tmismatches" in result.output
    assert "diff\tiva.anual.resultado-regimen-general\twork_unit=2600.00\tevidence=2100.00" in result.output


# --- Modelo 190 (resumen anual de retenciones): compound decl.* ids ---------

MODELO_190_DECLARACION_FIXTURE = FIXTURES_DIR / "justificantes" / "190" / "2024-0A.pdf"
"""Synthetic-generated M190 declaración PDF for ejercicio 2024, 0A.

Its three printed casillas are DISTINCT values. They were all the sanitiser's
single ``1.000,00`` placeholder while this was a redacted real render, which
meant the mismatch assertion below could have been reading either money box and
would have passed either way."""

# Modelo 190 ships revisions `2024` and `2025-y-siguientes`; there is no
# `2024-y-siguientes`. Seeding a work unit with a revision the registry does
# not carry made snapshot resolution fail, and reconcile then degraded to
# "receipt identity only" -- which reports a clean match without comparing a
# single casilla, so the sibling matches-case passed vacuously.
_M190_2024_0A_REVISION_ID = "2024"
"""Law-determined registry revision for M190 filing_year=2024, period=0A."""

# `computed_casilla_ids` for this revision has 3 entries, all printed by the
# fixture: percepciones-total=12345.60, retenciones-total=1851.84,
# total-percepciones=1 (a headcount, still a Decimal-typed casilla).
_M190_2024_0A_MATCHING_CASILLA_VALUES: dict[str, Decimal] = {
    "decl.percepciones-total": Decimal("12345.60"),
    "decl.retenciones-total": Decimal("1851.84"),
    "decl.total-percepciones": Decimal("1"),
}


def _seed_m190_work_unit_with_revision(*, casilla_values: dict[str, Decimal]) -> str:
    return _seed_declaracion_work_unit_with_revision(
        modelo="190",
        filing_year=2024,
        period_code="0A",
        revision_id=_M190_2024_0A_REVISION_ID,
        casilla_values=casilla_values,
    )


def test_reconcile_file_kind_declaration_m190_matches_when_computed_agrees(
    _declaracion_fixture_profile: None,
) -> None:
    """Acceptance wall #328 (Modelo 190, Tier-S summary return): the persisted
    revision's 3 computed casillas agree with the filed declaración -- a
    clean `matches` through the real CLI against a real declaración PDF."""
    work_unit_id = _seed_m190_work_unit_with_revision(casilla_values=_M190_2024_0A_MATCHING_CASILLA_VALUES)

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "reconcile",
            "import",
            work_unit_id,
            "--file",
            str(MODELO_190_DECLARACION_FIXTURE),
            "--kind",
            "declaration",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "source_kind\tdeclaration" in result.output
    assert "verdict\tmatches" in result.output
    assert "diffs\t0" in result.output


def test_reconcile_file_kind_declaration_m190_catches_casilla_divergence(
    _declaracion_fixture_profile: None,
) -> None:
    """Acceptance wall #328 (Modelo 190): a computed `decl.retenciones-total` that
    disagrees with the filed declaración is CAUGHT as a typed `casilla` diff,
    not a silent identity `matches`."""
    mismatched = dict(_M190_2024_0A_MATCHING_CASILLA_VALUES)
    mismatched["decl.retenciones-total"] = Decimal("1500.00")  # fixture prints 1851.84
    work_unit_id = _seed_m190_work_unit_with_revision(casilla_values=mismatched)

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "reconcile",
            "import",
            work_unit_id,
            "--file",
            str(MODELO_190_DECLARACION_FIXTURE),
            "--kind",
            "declaration",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "source_kind\tdeclaration" in result.output
    assert "verdict\tmismatches" in result.output
    assert "diff\tdecl.retenciones-total\twork_unit=1500.00\tevidence=1851.84" in result.output


# --- Modelo 100 (IRPF annual): printed Renta casilla ids ------------------
#
# M100 is enrolled in `_DECLARATION_CASILLA_RECONCILE_MODELOS` and declares the
# LARGEST reconcile scope of any modelo (168 `reconcile_when_present` plus 19
# computed for the 2024 revision), but until now had no CLI-level coverage at
# all -- every other enrolled modelo carried a matches/mismatch pair.
#
# The 2021-2023 specimens under `justificantes/100/` are generated layout
# replacements for withdrawn real renders. They reproduce the box-number-over-
# amount overlap those renders carried, and print distinct amounts rather than
# the single redaction constant, so their parser-boundary test now asserts the
# exact per-casilla map. They are still not seeded here: this section covers the
# 2024 revision's reconcile scope, not the 2021-2023 ones. The
# 2024/2025 fixtures are DR-faithful synthetic specimens built from the bundled
# AEAT Diseno de Registro field dictionaries, and they print clean stamped
# values -- the grounding tier the registry profile itself declares
# (`verification_source = "synthetic_from_aeat_published_text"`).

MODELO_100_DECLARACION_FIXTURE = FIXTURES_DIR / "justificantes" / "100" / "2024-0A.pdf"
"""DR-faithful synthetic M100 declaracion PDF for ejercicio 2024. Printed values
are established independently by
``test_parser_extracts_modelo_100_current_year_profile_targets``
(``adapters/inbound/declaracion/tests/test_parser_boundary_m100_current_year.py``),
whose expected map is mirrored from the fixture generator's stamped amounts."""

_M100_2024_REVISION_ID = "2024"
"""Law-determined registry revision for M100 filing_year=2024, period=0A
(confirmed via ``authority.snapshot("100", filing_year=2024, period="0A").revision.id``)."""

# The fixture prints 21 casillas; these are the ones the 2024 revision actually
# reconciles (printed set INTERSECT `reconcile_when_present_casilla_ids`, read
# from the snapshot's verification policy rather than assumed). The remaining
# printed casillas are deliberately left un-persisted so both sides are `None`
# for them -- a legitimate skip. Note both sets matter: a printed casilla that
# is `computed` but left un-persisted comes back as a `casilla_extra_in_filed`
# DIFF rather than a skip, so the seed is the union of the two intersections.
_M100_2024_MATCHING_CASILLA_VALUES: dict[str, Decimal] = {
    "0180": Decimal("1000.00"),
    "0218": Decimal("0.00"),
    "0223": Decimal("0.00"),
    "0226": Decimal("1000.00"),
    "0231": Decimal("1000.00"),
    "0235": Decimal("1000.00"),
    "0432": Decimal("1000.00"),
    "0500": Decimal("1000.00"),
    "0505": Decimal("1000.00"),
    "0510": Decimal("0.00"),
    "0545": Decimal("100.00"),
    "0546": Decimal("100.00"),
    "0585": Decimal("100.00"),
    "0586": Decimal("100.00"),
    "0587": Decimal("200.00"),
    "0595": Decimal("200.00"),
    "0604": Decimal("50.00"),
    "0610": Decimal("150.00"),
    "0670": Decimal("150.00"),
}


def _seed_m100_work_unit_with_revision(*, casilla_values: dict[str, Decimal]) -> str:
    return _seed_declaracion_work_unit_with_revision(
        modelo="100",
        filing_year=2024,
        period_code="0A",
        revision_id=_M100_2024_REVISION_ID,
        casilla_values=casilla_values,
    )


def test_reconcile_file_kind_declaration_m100_matches_when_computed_agrees(
    _declaracion_fixture_profile: None,
) -> None:
    """Modelo 100: a persisted revision agreeing with the filed declaracion
    reports a clean `matches` through the real CLI.

    The first end-to-end clean verdict for M100 -- the modelo with the largest
    reconcile scope was previously proven only by a mismatch case at the
    application seam, so no run had ever shown the happy path closing.
    """
    work_unit_id = _seed_m100_work_unit_with_revision(casilla_values=_M100_2024_MATCHING_CASILLA_VALUES)

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "reconcile",
            "import",
            work_unit_id,
            "--file",
            str(MODELO_100_DECLARACION_FIXTURE),
            "--kind",
            "declaration",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "source_kind	declaration" in result.output
    assert "verdict	matches" in result.output
    assert "diffs	0" in result.output


def test_reconcile_file_kind_declaration_m100_catches_casilla_divergence(
    _declaracion_fixture_profile: None,
) -> None:
    """Modelo 100: a computed `0604` disagreeing with the filed declaracion is
    CAUGHT as a typed casilla diff, not a silent identity `matches`.

    Pairs with the clean-match case above so neither can pass vacuously: this
    one proves the comparison is live, that one proves it can close.
    """
    mismatched = dict(_M100_2024_MATCHING_CASILLA_VALUES)
    mismatched["0604"] = Decimal("75.00")  # fixture prints 50.00
    work_unit_id = _seed_m100_work_unit_with_revision(casilla_values=mismatched)

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "reconcile",
            "import",
            work_unit_id,
            "--file",
            str(MODELO_100_DECLARACION_FIXTURE),
            "--kind",
            "declaration",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "source_kind	declaration" in result.output
    assert "verdict	mismatches" in result.output
    assert "diff	0604	work_unit=75.00	evidence=50.00" in result.output


def test_reconcile_file_kind_declaration_override_still_catches_wrong_modelo_pdf(
    _declaracion_fixture_profile: None,
) -> None:
    """Anti-regression proof for the work-unit-context override forwarding
    fix: an M111 work unit reconciled against the M130 fixture (a real,
    cleanly-self-detecting PDF for a DIFFERENT modelo) must still be refused,
    not silently coerced into "matching" the wrong modelo via the override.
    `parse_declaracion`'s `_resolve_template` reconciles a successful
    detection against the passed `modelo_override` and raises on conflict --
    the override forwarding only rescues a fixture whose OWN header fails to
    self-detect; it never suppresses a genuine wrong-PDF mismatch."""
    work_unit_id = _seed_m111_work_unit_with_revision(casilla_values=_M111_2024_1T_MATCHING_CASILLA_VALUES)

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "reconcile",
            "import",
            work_unit_id,
            "--file",
            str(MODELO_130_DECLARACION_FIXTURE),
            "--kind",
            "declaration",
        ],
    )
    assert result.exit_code != 0, result.output


def test_reconcile_file_kind_declaration_refuses_unenrolled_modelo(
    _declaracion_fixture_profile: None,
) -> None:
    """A modelo outside `_DECLARATION_CASILLA_RECONCILE_MODELOS` refuses
    `--kind declaration` on ENROLMENT grounds rather than silently degrading
    to a header-only compare.

    Modelo 115 is genuinely unenrolled and its own fixture is supplied, so the
    refusal cannot come from a template or header mismatch. The assertion is
    the registered error code, not the exit status: this test previously named
    modelo 100 as the unenrolled example, which stopped being true when 100
    was enrolled, and it kept passing only because it fed a 303-shaped PDF to
    a 100 work unit and tripped the wrong-modelo guard instead. A bare
    non-zero exit cannot tell those two refusals apart.
    """
    work_unit_id = _seed_work_unit(modelo="115", filing_year=2024, period="1T")

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "reconcile",
            "import",
            work_unit_id,
            "--file",
            str(FIXTURES_DIR / "justificantes" / "115" / "2024-1T.pdf"),
            "--kind",
            "declaration",
        ],
    )
    assert result.exit_code != 0, result.output
    assert "REFUSED_RECONCILIATION_DECLARATION_SOURCE_UNSUPPORTED" in result.output, result.output


def test_reconcile_file_default_kind_is_justificante() -> None:
    """Omitting `--kind` preserves the pre-existing default behaviour
    (justificante), so no existing caller's behaviour changes."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")

    result = invoke_cached_cli(
        ["app", "modelo", "reconcile", "import", work_unit_id, "--file", str(MODELO_130_FIXTURE)],
    )
    assert result.exit_code == 0, result.output
    assert "source_kind\tjustificante" in result.output
