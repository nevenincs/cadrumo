"""Build the wizard.* locale block per language and merge it into existing files.

Run as ``uv run --no-sync python scripts/generate_wizard_locale_block.py``.
The script loads each ``src/aeat/locales/{lang}.yml`` file, merges the
generated ``wizard`` subtree into the existing dict, and rewrites the
file. The wizard subtree carries one entry per Translatable referenced
by ``WIZARD_FLOWS`` plus the fixed ``errors.missing_required_flags``
key.

This script is run once per change to the descriptor catalogue; it is
NOT imported by production code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_LANG_ORDER = ("en", "es", "ca", "hu")

_FLOW_TITLE = (
    "Setup wizard",
    "Asistente de configuración",
    "Auxiliar de configuració",
    "Beállítás varázsló",
)
_FLOW_DESCRIPTION = (
    "Operator-facing setup wizard for tax filing readiness",
    "Asistente de configuración para preparar las declaraciones",
    "Auxiliar de configuració per preparar les declaracions",
    "Operátorbarát beállítás varázsló a bevallások előkészítéséhez",
)
_MISSING_FLAGS = (
    "Missing required flags for --quiet wizard run: %{missing}",
    "Faltan banderas requeridas para --quiet: %{missing}",
    "Falten paràmetres requerits per a --quiet: %{missing}",
    "Hiányzó kötelező zászlók --quiet futtatáshoz: %{missing}",
)

_SECTION_TITLES = {
    "profile": (
        "Profile identity",
        "Identidad del perfil",
        "Identitat del perfil",
        "Profil azonosítása",
    ),
    "taxpayer": (
        "First taxpayer",
        "Primer declarante",
        "Primer declarant",
        "Az első adózó",
    ),
    "spouse": ("Spouse", "Cónyuge", "Cònjuge", "Házastárs"),
    "family": ("Family unit", "Unidad familiar", "Unitat familiar", "Családi egység"),
    "iva": ("IVA", "IVA", "IVA", "ÁFA"),
    "enrollment": (
        "Enrollment",
        "Inscripción",
        "Inscripció",
        "Bejelentés",
    ),
    "obligations": (
        "Filing obligations",
        "Obligaciones",
        "Obligacions",
        "Bevallási kötelezettségek",
    ),
    "residence": (
        "Tax residence",
        "Residencia fiscal",
        "Residència fiscal",
        "Adóügyi rezidencia",
    ),
    "notes": (
        "Operator notes",
        "Notas del operador",
        "Notes de l'operador",
        "Operátori jegyzetek",
    ),
}

_PROMPTS: dict[str, tuple[str, str, str, str]] = {
    "tax-id": (
        "Tax identifier (NIF/NIE) for declarations",
        "Identificador fiscal (NIF/NIE) para declaraciones",
        "Identificador fiscal (NIF/NIE) per a declaracions",
        "Adóazonosító (NIF/NIE) bevallásokhoz",
    ),
    "name": (
        "Display name shown in local reviews",
        "Nombre visible mostrado en revisiones locales",
        "Nom visible mostrat en revisions locals",
        "A helyi áttekintésben megjelenő név",
    ),
    "surnames": (
        "Surnames or company name for export headers",
        "Apellidos o razón social para cabeceras de exportación",
        "Cognoms o raó social per a capçaleres d'exportació",
        "Vezetéknév vagy cégnév az exportfejlécekhez",
    ),
    "activity": (
        "Business activity label or controlled key",
        "Etiqueta de actividad o clave controlada",
        "Etiqueta d'activitat o clau controlada",
        "Tevékenységcímke vagy ellenőrzött kulcs",
    ),
    "address-postcode": (
        "Tax address postcode",
        "Código postal del domicilio fiscal",
        "Codi postal del domicili fiscal",
        "Adózási cím irányítószáma",
    ),
    "declaration-type": (
        "Declaration type code",
        "Código del tipo de declaración",
        "Codi del tipus de declaració",
        "Bevallás-típus kódja",
    ),
    "taxpayer-sex": (
        "First taxpayer sex code",
        "Sexo del primer declarante",
        "Sexe del primer declarant",
        "Az első adózó neme",
    ),
    "taxpayer-marital-status": (
        "First taxpayer marital status",
        "Estado civil del primer declarante",
        "Estat civil del primer declarant",
        "Az első adózó családi állapota",
    ),
    "taxpayer-birth-date": (
        "First taxpayer birth date",
        "Fecha de nacimiento del primer declarante",
        "Data de naixement del primer declarant",
        "Az első adózó születési dátuma",
    ),
    "taxpayer-disability-grade": (
        "First taxpayer disability code",
        "Clave de discapacidad del primer declarante",
        "Clau de discapacitat del primer declarant",
        "Az első adózó fogyatékossági kódja",
    ),
    "taxpayer-death-date": (
        "First taxpayer death date",
        "Fecha de fallecimiento del primer declarante",
        "Data de defunció del primer declarant",
        "Az első adózó halálozási dátuma",
    ),
    "spouse-tax-id": (
        "Spouse NIF/NIE",
        "NIF/NIE del cónyuge",
        "NIF/NIE del cònjuge",
        "A házastárs NIF/NIE azonosítója",
    ),
    "spouse-name": (
        "Spouse given name",
        "Nombre del cónyuge",
        "Nom del cònjuge",
        "A házastárs keresztneve",
    ),
    "spouse-surnames": (
        "Spouse surnames",
        "Apellidos del cónyuge",
        "Cognoms del cònjuge",
        "A házastárs vezetéknevei",
    ),
    "spouse-birth-date": (
        "Spouse birth date",
        "Fecha de nacimiento del cónyuge",
        "Data de naixement del cònjuge",
        "A házastárs születési dátuma",
    ),
    "spouse-sex": (
        "Spouse sex code",
        "Sexo del cónyuge",
        "Sexe del cònjuge",
        "A házastárs neme",
    ),
    "spouse-disability-grade": (
        "Spouse disability code",
        "Clave de discapacidad del cónyuge",
        "Clau de discapacitat del cònjuge",
        "A házastárs fogyatékossági kódja",
    ),
    "spouse-non-resident-irpf": (
        "Spouse is non-resident IRPF",
        "Cónyuge no residente IRPF",
        "Cònjuge no resident IRPF",
        "Házastárs nem rezidens IRPF",
    ),
    "spouse-eu-eea-resident": (
        "Spouse is EU/EEA resident",
        "Cónyuge residente UE/EEE",
        "Cònjuge resident UE/EEE",
        "Házastárs EU/EGT rezidens",
    ),
    "spouse-eu-eea-country": (
        "Spouse EU/EEA country",
        "País UE/EEE del cónyuge",
        "País UE/EEE del cònjuge",
        "A házastárs EU/EGT országa",
    ),
    "family-descendants-eu-eea-deduction": (
        "EU/EEA descendants in family-unit deduction",
        "Descendientes UE/EEE en deducción de unidad familiar",
        "Descendents UE/EEE en deducció d'unitat familiar",
        "EU/EGT leszármazottak családi egység kedvezményében",
    ),
    "family-minor-children-in-unit": (
        "Minor children in family unit",
        "Hijos menores en unidad familiar",
        "Fills menors en unitat familiar",
        "Kiskorú gyermekek a családi egységben",
    ),
    "iva-regime": (
        "IVA regime",
        "Régimen IVA",
        "Règim IVA",
        "ÁFA-rezsim",
    ),
    "iva-roi-enrolled": (
        "Enrolled in ROI",
        "Alta en ROI",
        "Alta en ROI",
        "ROI bejegyzés",
    ),
    "iva-oss-enrolled": (
        "Enrolled in OSS",
        "Alta en OSS",
        "Alta en OSS",
        "OSS bejegyzés",
    ),
    "iva-intracommunity-operations-exceed-50000-eur": (
        "Intra-community operations exceed 50,000 EUR",
        "Operaciones intracomunitarias superan 50.000 EUR",
        "Operacions intracomunitàries superen 50.000 EUR",
        "Közösségi műveletek meghaladják az 50 000 EUR küszöböt",
    ),
    "enrollment-large-company": (
        "Large-company enrollment",
        "Empresa de gran volumen",
        "Empresa de gran volum",
        "Nagyvállalat besorolás",
    ),
    "enrollment-public-administration-budget-gt-6000000": (
        "Public administration budget over 6,000,000",
        "Presupuesto administración pública superior a 6.000.000",
        "Pressupost administració pública superior a 6.000.000",
        "Közigazgatási költségvetés 6 000 000 felett",
    ),
    "has-employees": (
        "Has employees and pays salaries with retención",
        "Tiene empleados y paga salarios con retención",
        "Té empleats i paga salaris amb retenció",
        "Van alkalmazottja és bérleti adóelőleget von",
    ),
    "pays-professionals-with-retencion": (
        "Pays professionals with retención",
        "Paga a profesionales con retención",
        "Paga a professionals amb retenció",
        "Szakembereket adóelőleggel fizet",
    ),
    "professional-income-withholding-ge-70pct": (
        "At least 70% of professional income with prior retención",
        "Al menos 70% de los ingresos profesionales con retención previa",
        "Almenys 70% dels ingressos professionals amb retenció prèvia",
        "A szakmai jövedelem legalább 70%-a előzetes adólevonás alatt",
    ),
    "pays-rent-with-retencion": (
        "Pays local rent with retención",
        "Paga alquiler de local con retención",
        "Paga lloguer de local amb retenció",
        "Helyiségbérletet adóelőleggel fizet",
    ),
    "pays-capital-income-with-retencion": (
        "Pays capital income with retención",
        "Paga rentas de capital con retención",
        "Paga rendes de capital amb retenció",
        "Tőkejövedelmeket adóelőleggel fizet",
    ),
    "uses-objective-estimation-irpf": (
        "Files IRPF under objective estimation",
        "Tributa IRPF en estimación objetiva",
        "Tributa IRPF en estimació objectiva",
        "IRPF-et becsült rendszerben adózza",
    ),
    "does-intracomunitario": (
        "Conducts intracomunitario operations",
        "Realiza operaciones intracomunitarias",
        "Realitza operacions intracomunitàries",
        "Közösségi műveleteket végez",
    ),
    "third-party-transactions-above-347-threshold": (
        "Third-party transactions exceed Modelo 347 threshold",
        "Operaciones con terceros superan el umbral del Modelo 347",
        "Operacions amb tercers superen el llindar del Modelo 347",
        "Harmadik felekkel folytatott műveletek meghaladják a Modelo 347 küszöböt",
    ),
    "bienes-extranjero-above-threshold": (
        "Foreign-held assets above legal threshold",
        "Bienes en el extranjero superan el umbral legal",
        "Béns a l'estranger superen el llindar legal",
        "Külföldön tartott eszközök a törvényi küszöb felett",
    ),
    "tax-residence-ccaa": (
        "Tax-residence autonomous community",
        "Comunidad autónoma de residencia fiscal",
        "Comunitat autònoma de residència fiscal",
        "Adóügyi rezidens autonóm közösség",
    ),
    "notes": (
        "Operator notes (not consumed by the engine)",
        "Notas del operador (no consumidas por el motor)",
        "Notes de l'operador (no consumides pel motor)",
        "Operátori jegyzetek (a motor nem dolgozza fel)",
    ),
}

_SECTION_QUESTIONS: dict[str, tuple[str, ...]] = {
    "profile": ("tax-id", "name", "surnames", "activity", "address-postcode", "declaration-type"),
    "taxpayer": (
        "taxpayer-sex",
        "taxpayer-marital-status",
        "taxpayer-birth-date",
        "taxpayer-disability-grade",
        "taxpayer-death-date",
    ),
    "spouse": (
        "spouse-tax-id",
        "spouse-name",
        "spouse-surnames",
        "spouse-birth-date",
        "spouse-sex",
        "spouse-disability-grade",
        "spouse-non-resident-irpf",
        "spouse-eu-eea-resident",
        "spouse-eu-eea-country",
    ),
    "family": ("family-descendants-eu-eea-deduction", "family-minor-children-in-unit"),
    "iva": (
        "iva-regime",
        "iva-roi-enrolled",
        "iva-oss-enrolled",
        "iva-intracommunity-operations-exceed-50000-eur",
    ),
    "enrollment": (
        "enrollment-large-company",
        "enrollment-public-administration-budget-gt-6000000",
    ),
    "obligations": (
        "has-employees",
        "pays-professionals-with-retencion",
        "professional-income-withholding-ge-70pct",
        "pays-rent-with-retencion",
        "pays-capital-income-with-retencion",
        "uses-objective-estimation-irpf",
        "does-intracomunitario",
        "third-party-transactions-above-347-threshold",
        "bienes-extranjero-above-threshold",
    ),
    "residence": ("tax-residence-ccaa",),
    "notes": ("notes",),
}

_IVA_LABELS: dict[str, tuple[str, str, str, str]] = {
    "general": ("General regime", "Régimen general", "Règim general", "Általános rendszer"),
    "simplificado": (
        "Simplified regime",
        "Régimen simplificado",
        "Règim simplificat",
        "Egyszerűsített rendszer",
    ),
    "recargo-equivalencia": (
        "Equivalence surcharge",
        "Recargo de equivalencia",
        "Recàrrec d'equivalència",
        "Egyenértékűségi pótdíj",
    ),
    "exento": ("Exempt", "Exento", "Exempt", "Mentes"),
}

_CCAA_LABELS: dict[str, tuple[str, str, str, str]] = {
    "andalucia": ("Andalusia", "Andalucía", "Andalusia", "Andalúzia"),
    "aragon": ("Aragon", "Aragón", "Aragó", "Aragónia"),
    "asturias": ("Asturias", "Asturias", "Astúries", "Asztúria"),
    "baleares": ("Balearic Islands", "Islas Baleares", "Illes Balears", "Baleár-szigetek"),
    "canarias": ("Canary Islands", "Islas Canarias", "Illes Canàries", "Kanári-szigetek"),
    "cantabria": ("Cantabria", "Cantabria", "Cantàbria", "Kantábria"),
    "castilla_la_mancha": (
        "Castile-La Mancha",
        "Castilla-La Mancha",
        "Castella-la Manxa",
        "Kasztília-La Mancha",
    ),
    "castilla_y_leon": (
        "Castile and León",
        "Castilla y León",
        "Castella i Lleó",
        "Kasztília és León",
    ),
    "cataluna": ("Catalonia", "Cataluña", "Catalunya", "Katalónia"),
    "comunidad_valenciana": (
        "Valencian Community",
        "Comunidad Valenciana",
        "Comunitat Valenciana",
        "Valenciai közösség",
    ),
    "extremadura": ("Extremadura", "Extremadura", "Extremadura", "Extremadura"),
    "galicia": ("Galicia", "Galicia", "Galícia", "Galícia"),
    "la_rioja": ("La Rioja", "La Rioja", "La Rioja", "La Rioja"),
    "madrid": ("Madrid", "Madrid", "Madrid", "Madrid"),
    "murcia": ("Murcia", "Murcia", "Múrcia", "Murcia"),
}


def _build_wizard_subtree(lang_index: int) -> dict[str, Any]:
    setup: dict[str, Any] = {
        "title": _FLOW_TITLE[lang_index],
        "description": _FLOW_DESCRIPTION[lang_index],
        "errors": {"missing_required_flags": _MISSING_FLAGS[lang_index]},
    }

    for section_id, question_ids in _SECTION_QUESTIONS.items():
        section_block: dict[str, Any] = {"title": _SECTION_TITLES[section_id][lang_index]}
        for qid in question_ids:
            section_block[qid] = {"prompt": _PROMPTS[qid][lang_index]}
        setup[section_id] = section_block

    # Descriptor uses wizard.setup.profile.iva-regime.choices.*.label
    setup["profile"].setdefault("iva-regime", {})
    setup["profile"]["iva-regime"]["choices"] = {
        value: {"label": labels[lang_index]} for value, labels in _IVA_LABELS.items()
    }

    # Descriptor uses wizard.setup.residence.ccaa.choices.*.label
    setup["residence"]["ccaa"] = {
        "choices": {value: {"label": labels[lang_index]} for value, labels in _CCAA_LABELS.items()}
    }
    return {"wizard": {"setup": setup}}


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


def main() -> None:
    root = Path("src/aeat/locales")
    for idx, lang in enumerate(_LANG_ORDER):
        path = root / f"{lang}.yml"
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        wizard_block = _build_wizard_subtree(idx)
        _deep_merge(data, wizard_block)
        with path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=True, default_flow_style=False)
        print(f"updated {path}")


if __name__ == "__main__":
    main()
