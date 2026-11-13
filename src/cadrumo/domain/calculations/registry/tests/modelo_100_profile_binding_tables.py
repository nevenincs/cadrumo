"""Hand-stated Modelo 100 personal and family profile bindings, shared as one oracle.

The registry declares these bindings; the tests that check them keep this
table independent of the registry by stating it literally here, once.
"""

from __future__ import annotations

from collections.abc import Mapping

PERSONAL_FAMILY_CASILLA_TO_BINDING: Mapping[str, str] = {
    "DPNIF_D": "renta-profile-tax-id",
    "DP_APENOM_D": "renta-profile-display-name",
    "ZCCAD": "renta-profile-tax-residence-ccaa",
    "TIPOTRIBUTACION": "renta-profile-declaration-type",
    "SEXO_D": "renta-profile-taxpayer-sex",
    "ECIVIL": "renta-profile-marital-status",
    "DPFNAC_D": "renta-profile-taxpayer-birth-date",
    "DPNIF_C": "renta-profile-spouse-tax-id",
    "DP_APENOM_C": "renta-profile-spouse-display-name",
    "DPFNAC_C": "renta-profile-spouse-birth-date",
    "SEXO_C": "renta-profile-spouse-sex",
    "DPGMIN_D": "renta-profile-taxpayer-disability-grade",
    "DECFAL": "renta-profile-taxpayer-death-date",
    "DPGMIN_C": "renta-profile-spouse-disability-grade",
    "NORESIDENTE": "renta-profile-spouse-non-resident-irpf",
    "RESIDENTEUE": "renta-profile-spouse-eu-eea-resident",
    "ZRUE2": "renta-profile-spouse-eu-eea-country",
    "HIJOSUE": "renta-profile-family-descendants-eu-eea-deduction",
    "PH18": "renta-profile-family-minor-children-in-unit",
    "NIFDLG": "renta-family-descendant-tax-id",
    "APENOMDLG": "renta-family-descendant-display-name",
    "FNACDLG": "renta-family-descendant-birth-date",
    "MINUSDLG": "renta-family-descendant-disability-grade",
    "FALLDLG": "renta-family-descendant-death-date",
    "DNIASDLG": "renta-family-ascendant-tax-id",
    "APENOMDLG_ASC": "renta-family-ascendant-display-name",
    "ANOASDLG": "renta-family-ascendant-birth-date",
    "PCTMINASDLG": "renta-family-ascendant-disability-grade",
    "CONVASDLG": "renta-family-ascendant-cohabiting-descendant-count",
    "FALLASDLG": "renta-family-ascendant-death-date",
}

"""Casilla id -> id of the profile or family binding that must fill it."""

FAMILY_ROW_BINDINGS: Mapping[str, tuple[str, str, str]] = {
    "renta-family-descendant-tax-id": ("renta_family.descendiente", "nif", "renta_family.descendientes_count"),
    "renta-family-descendant-display-name": (
        "renta_family.descendiente",
        "apellidos_nombre",
        "renta_family.descendientes_count",
    ),
    "renta-family-descendant-birth-date": (
        "renta_family.descendiente",
        "birth_date",
        "renta_family.descendientes_count",
    ),
    "renta-family-descendant-disability-grade": (
        "renta_family.descendiente",
        "discapacidad_clave",
        "renta_family.descendientes_count",
    ),
    "renta-family-descendant-death-date": (
        "renta_family.descendiente",
        "fallecimiento",
        "renta_family.descendientes_count",
    ),
    "renta-family-ascendant-tax-id": ("renta_family.ascendiente", "nif", "renta_family.ascendientes_count"),
    "renta-family-ascendant-display-name": (
        "renta_family.ascendiente",
        "apellidos_nombre",
        "renta_family.ascendientes_count",
    ),
    "renta-family-ascendant-birth-date": ("renta_family.ascendiente", "birth_date", "renta_family.ascendientes_count"),
    "renta-family-ascendant-disability-grade": (
        "renta_family.ascendiente",
        "minimo_discapacidad_clave",
        "renta_family.ascendientes_count",
    ),
    "renta-family-ascendant-cohabiting-descendant-count": (
        "renta_family.ascendiente",
        "convivientes",
        "renta_family.ascendientes_count",
    ),
    "renta-family-ascendant-death-date": (
        "renta_family.ascendiente",
        "fallecimiento",
        "renta_family.ascendientes_count",
    ),
}
"""Family row binding id -> (stored row object, leaf read on each row, the object's stated count)."""
