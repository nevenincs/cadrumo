"""Unit tests for the LIRPF arts. 57-60 mínimo personal y familiar helper.

External-anchored to LIRPF arts. 57 / 58 / 59 / 60 + the canonical
amounts that have been stable since 2015 (no posterior law modification
at BOE consult 2026-04-28).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ._minimos import (
    GradoDiscapacidad,
    MinimosProfile,
    compute_minimo_personal_familiar,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


class TestMinimoContribuyente:
    """LIRPF art. 57 — mínimo del contribuyente.

    5.550 base + 1.150 si >65 + 1.400 adicional si >75.
    """

    def test_base_minimo_age_lt_65(self) -> None:
        profile = MinimosProfile()
        result = compute_minimo_personal_familiar(profile)
        assert result["0505"] == Decimal("5550.00")
        assert result["0500"] == Decimal("5550.00")

    def test_age_over_65(self) -> None:
        profile = MinimosProfile(contribuyente_over_65=True)
        result = compute_minimo_personal_familiar(profile)
        assert result["0505"] == Decimal("6700.00")  # 5550 + 1150

    def test_age_over_75(self) -> None:
        profile = MinimosProfile(contribuyente_over_65=True, contribuyente_over_75=True)
        result = compute_minimo_personal_familiar(profile)
        assert result["0505"] == Decimal("8100.00")  # 5550 + 1150 + 1400


class TestMinimoDescendientes:
    """LIRPF art. 58 — per-orden amounts + 2.800 € per <3 años.

    1º: 2.400; 2º: 2.700; 3º: 4.000; 4º+: 4.500.
    """

    @pytest.mark.parametrize(
        ("n_descendientes", "expected"),
        [
            (0, Decimal("0.00")),
            (1, Decimal("2400.00")),
            (2, Decimal("5100.00")),  # 2400+2700
            (3, Decimal("9100.00")),  # +4000
            (4, Decimal("13600.00")),  # +4500
            (5, Decimal("18100.00")),  # +4500
        ],
    )
    def test_descendientes_per_orden(self, n_descendientes: int, expected: Decimal) -> None:
        profile = MinimosProfile(n_descendientes=n_descendientes)
        result = compute_minimo_personal_familiar(profile)
        assert result["0510"] == expected

    def test_descendientes_under_3_bonus(self) -> None:
        """1 hijo (1º) + 1 menor de 3: 2400 + 2800 = 5200."""
        profile = MinimosProfile(n_descendientes=1, n_descendientes_under_3=1)
        result = compute_minimo_personal_familiar(profile)
        assert result["0510"] == Decimal("5200.00")

    def test_two_descendientes_one_under_3(self) -> None:
        """Worked example: 2 hijos (1 menor de 3 años):
        - 1er descendiente: 2.400 + 2.800 menor de 3 = 5.200
        - 2º descendiente: 2.700
        - Total 0510: 7.900
        """
        profile = MinimosProfile(n_descendientes=2, n_descendientes_under_3=1)
        result = compute_minimo_personal_familiar(profile)
        assert result["0510"] == Decimal("7900.00")


class TestMinimoAscendientes:
    """LIRPF art. 59 — 1.150 per ascendiente >=65 + 1.400 supplement per >75."""

    def test_no_ascendientes(self) -> None:
        profile = MinimosProfile()
        result = compute_minimo_personal_familiar(profile)
        assert result["0515"] == Decimal("0.00")

    def test_one_ascendiente_over_65(self) -> None:
        profile = MinimosProfile(n_ascendientes_over_65=1)
        result = compute_minimo_personal_familiar(profile)
        assert result["0515"] == Decimal("1150.00")

    def test_one_ascendiente_over_75(self) -> None:
        """Over-75 implies over-65; both supplements apply."""
        profile = MinimosProfile(n_ascendientes_over_65=1, n_ascendientes_over_75=1)
        result = compute_minimo_personal_familiar(profile)
        assert result["0515"] == Decimal("2550.00")  # 1150 + 1400

    def test_two_ascendientes_one_over_75(self) -> None:
        profile = MinimosProfile(n_ascendientes_over_65=2, n_ascendientes_over_75=1)
        result = compute_minimo_personal_familiar(profile)
        # 2 * 1150 + 1 * 1400 = 2300 + 1400 = 3700
        assert result["0515"] == Decimal("3700.00")


class TestMinimoDiscapacidad:
    """LIRPF art. 60 — 3.000 / 9.000 + 3.000 asistencia bonus."""

    def test_no_discapacidad(self) -> None:
        profile = MinimosProfile()
        result = compute_minimo_personal_familiar(profile)
        assert result["0520"] == Decimal("0.00")

    def test_grado_bajo(self) -> None:
        """grado 33-65%: 3.000 €."""
        profile = MinimosProfile(contribuyente_grado_discapacidad=GradoDiscapacidad.GRADO_BAJO)
        result = compute_minimo_personal_familiar(profile)
        assert result["0520"] == Decimal("3000.00")

    def test_grado_alto(self) -> None:
        """grado >=65%: 9.000 €."""
        profile = MinimosProfile(contribuyente_grado_discapacidad=GradoDiscapacidad.GRADO_ALTO)
        result = compute_minimo_personal_familiar(profile)
        assert result["0520"] == Decimal("9000.00")

    def test_grado_alto_with_asistencia(self) -> None:
        """grado >=65% + asistencia: 9.000 + 3.000 = 12.000."""
        profile = MinimosProfile(
            contribuyente_grado_discapacidad=GradoDiscapacidad.GRADO_ALTO,
            contribuyente_needs_ayuda_asistencia=True,
        )
        result = compute_minimo_personal_familiar(profile)
        assert result["0520"] == Decimal("12000.00")

    def test_grado_bajo_with_asistencia(self) -> None:
        """grado <65% + asistencia: 3.000 + 3.000 = 6.000."""
        profile = MinimosProfile(
            contribuyente_grado_discapacidad=GradoDiscapacidad.GRADO_BAJO,
            contribuyente_needs_ayuda_asistencia=True,
        )
        result = compute_minimo_personal_familiar(profile)
        assert result["0520"] == Decimal("6000.00")


class TestMinimoTotal:
    """End-to-end worked examples covering all 4 components."""

    def test_kent_baseline_single_no_dependents(self) -> None:
        """Kent <65 años, soltero, sin descendientes ni ascendientes ni
        discapacidad → only the 5.550 base mínimo del contribuyente.
        """
        profile = MinimosProfile()
        result = compute_minimo_personal_familiar(profile)
        assert result["0500"] == Decimal("5550.00")

    def test_typical_family_2_kids_one_under_3(self) -> None:
        """Worked example: contribuyente <65 años, 2 hijos (1 menor de
        3 años), 1 ascendiente >=65 conviviente, sin discapacidad:
          - 0505 = 5.550
          - 0510 = 2.400 + 2.700 + 2.800 = 7.900
          - 0515 = 1.150
          - 0520 = 0
          - 0500 = 14.600
        """
        profile = MinimosProfile(
            n_descendientes=2,
            n_descendientes_under_3=1,
            n_ascendientes_over_65=1,
        )
        result = compute_minimo_personal_familiar(profile)
        assert result["0505"] == Decimal("5550.00")
        assert result["0510"] == Decimal("7900.00")
        assert result["0515"] == Decimal("1150.00")
        assert result["0520"] == Decimal("0.00")
        assert result["0500"] == Decimal("14600.00")

    def test_complex_family_all_components(self) -> None:
        """Worked example combining all 4 components:
        - Contribuyente >75 años con discapacidad alto + asistencia
        - 4 descendientes (2 menores de 3 años)
        - 2 ascendientes (uno >75)

        0505 = 5.550 + 1.150 + 1.400 = 8.100
        0510 = 2.400 + 2.700 + 4.000 + 4.500 + 2 * 2.800 = 19.200
        0515 = 2 * 1.150 + 1 * 1.400 = 3.700
        0520 = 9.000 + 3.000 = 12.000
        0500 = 8.100 + 19.200 + 3.700 + 12.000 = 43.000
        """
        profile = MinimosProfile(
            contribuyente_over_65=True,
            contribuyente_over_75=True,
            n_descendientes=4,
            n_descendientes_under_3=2,
            n_ascendientes_over_65=2,
            n_ascendientes_over_75=1,
            contribuyente_grado_discapacidad=GradoDiscapacidad.GRADO_ALTO,
            contribuyente_needs_ayuda_asistencia=True,
        )
        result = compute_minimo_personal_familiar(profile)
        assert result["0505"] == Decimal("8100.00")
        assert result["0510"] == Decimal("19200.00")
        assert result["0515"] == Decimal("3700.00")
        assert result["0520"] == Decimal("12000.00")
        assert result["0500"] == Decimal("43000.00")


class TestPydanticDiscipline:
    """The MinimosProfile model enforces strict + frozen + extra=forbid."""

    def test_negative_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MinimosProfile(n_descendientes=-1)

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MinimosProfile.model_validate({"n_descendientes": 1, "unknown_extra": "bogus"})

    def test_frozen(self) -> None:
        profile = MinimosProfile(n_descendientes=1)
        with pytest.raises(ValidationError):
            profile.n_descendientes = 5  # type: ignore[misc]
