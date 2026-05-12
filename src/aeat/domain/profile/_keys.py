"""Schema-backed registry of editable taxpayer-profile keys.

The operator can discover editable keys, set or unset values, and
validate completeness without bespoke per-command knowledge. The
registry lives in the domain layer so every consumer reads from the
same source of truth.

The registry is a tuple of strict :class:`ProfileKey` records. Each
entry carries the canonical key path (dot-separated), a requirement
flag (required vs optional for declaration export), and a short
multilingual description rendered in operator-facing surfaces.

Adding a new key means appending a :class:`ProfileKey` row here and
extending the validators that consume the value. Adding a new
language means extending :class:`aeat.core.i18n.str`; the
description fields fall back through
:func:`aeat.core.i18n.require_authoritative` when a per-language
slot is empty.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...core.i18n import Translatable as tr  # noqa: N813
from ._errors import ProfileValidationError


class ProfileKeyRequirement(StrEnum):
    """Whether a profile key is mandatory before declaration export."""

    REQUIRED = "required"
    OPTIONAL = "optional"


class ProfileKey(BaseModel):
    """Strict frozen record describing one editable profile key."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    key: str = Field(min_length=1, max_length=128)
    requirement: ProfileKeyRequirement
    description: tr
    required_when_key: str | None = None
    required_when_value: str | None = None

    @field_validator("key")
    @classmethod
    def _validate_key_shape(cls, value: str) -> str:
        """Reject blank or whitespace-padded keys; keep dot-separated paths intact."""
        if not value.strip():
            raise ProfileValidationError("key must not be empty or whitespace-only")
        if value.strip() != value:
            raise ProfileValidationError("key must not be padded with whitespace")
        return value

    @field_validator("description")
    @classmethod
    def _validate_description_key(cls, value: tr) -> tr:
        """Require profile-owned translation keys for authoritative descriptions."""
        if not value.strip():
            raise ProfileValidationError("description must not be empty")
        if not str(value).startswith("profile.keys."):
            raise ProfileValidationError("description must use a profile translation key")
        return value

    @field_validator("required_when_key", "required_when_value")
    @classmethod
    def _validate_conditional_requirement(cls, value: str | None) -> str | None:
        if value and value.strip() != value:
            raise ProfileValidationError("conditional requirement fields must not be padded")
        if value == "":
            raise ProfileValidationError("conditional requirement fields must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_conditional_requirement_pair(self) -> ProfileKey:
        if bool(self.required_when_key) != bool(self.required_when_value):
            raise ProfileValidationError("required_when_key and required_when_value must be set together")
        return self


def _key(
    *,
    key: str,
    requirement: ProfileKeyRequirement,
    es: str,
    en: str,
    ca: str,
    hu: str,
    required_when_key: str | None = None,
    required_when_value: str | None = None,
) -> ProfileKey:
    """Construct a :class:`ProfileKey` with a multilingual description."""
    return ProfileKey(
        key=key,
        requirement=requirement,
        description=tr(f"profile.keys.{key}"),
        required_when_key=required_when_key,
        required_when_value=required_when_value,
    )


PROFILE_KEYS: tuple[ProfileKey, ...] = (
    _key(
        key="tax.id",
        requirement=ProfileKeyRequirement.REQUIRED,
        es="Identificador fiscal usado en los borradores locales de declaración.",
        en="Tax identifier used for local declaration drafts.",
        ca="Identificador fiscal utilitzat en els esborranys locals de declaració.",
        hu="Helyi bevallás-tervezetekhez használt adóazonosító.",
    ),
    _key(
        key="name",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Nombre visible usado en la salida de revisión local.",
        en="Display name used in local review output.",
        ca="Nom visible utilitzat a la sortida de revisió local.",
        hu="A helyi áttekintés kimeneten megjelenő név.",
    ),
    _key(
        key="surnames",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Apellidos o razón social usados en las cabeceras de exportación.",
        en="Surnames or company name used in export headers.",
        ca="Cognoms o raó social utilitzats a les capçaleres d'exportació.",
        hu="Az exportfejlécekben használt vezetéknév vagy cégnév.",
    ),
    _key(
        key="activity",
        requirement=ProfileKeyRequirement.REQUIRED,
        es="Etiqueta de actividad económica o clave de actividad controlada.",
        en="Business activity label or controlled activity key.",
        ca="Etiqueta d'activitat econòmica o clau d'activitat controlada.",
        hu="Gazdasági tevékenység címke vagy ellenőrzött tevékenységkulcs.",
    ),
    _key(
        key="address.postcode",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Código postal del domicilio fiscal cuando un Modelo soportado lo requiere.",
        en="Tax address postcode when a supported Modelo needs it.",
        ca="Codi postal del domicili fiscal quan un Modelo suportat el necessita.",
        hu="Adózási cím irányítószáma, ha valamely támogatott Modelo igényli.",
    ),
    _key(
        key="declaration.type",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Tipo de declaración para las cabeceras de exportación.",
        en="Declaration type for export headers.",
        ca="Tipus de declaració per a les capçaleres d'exportació.",
        hu="Bevallás-típus az exportfejlécekhez.",
    ),
    _key(
        key="taxpayer.sex",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Sexo del primer declarante según el diseño oficial del Modelo 100.",
        en="First taxpayer sex according to the official Modelo 100 design.",
        ca="Sexe del primer declarant segons el disseny oficial del Modelo 100.",
        hu="Az első adózó neme a hivatalos Modelo 100 szerkezet szerint.",
    ),
    _key(
        key="taxpayer.marital_status",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Estado civil del primer declarante a 31 de diciembre del ejercicio.",
        en="First taxpayer marital status on 31 December of the tax year.",
        ca="Estat civil del primer declarant a 31 de desembre de l'exercici.",
        hu="Az első adózó családi állapota az adóév december 31-én.",
    ),
    _key(
        key="taxpayer.birth_date",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Fecha de nacimiento del primer declarante para Modelo 100.",
        en="First taxpayer birth date for Modelo 100.",
        ca="Data de naixement del primer declarant per al Modelo 100.",
        hu="Az első adózó születési dátuma a Modelo 100-hoz.",
    ),
    _key(
        key="taxpayer.disability_grade",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Clave de discapacidad del primer declarante según el diseño oficial del Modelo 100.",
        en="First taxpayer disability code according to the official Modelo 100 design.",
        ca="Clau de discapacitat del primer declarant segons el disseny oficial del Modelo 100.",
        hu="Az első adózó fogyatékossági kódja a hivatalos Modelo 100 szerkezet szerint.",
    ),
    _key(
        key="taxpayer.death_date",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Fecha de fallecimiento del primer declarante cuando deba declararse en Modelo 100.",
        en="First taxpayer death date when Modelo 100 must declare it.",
        ca="Data de defunció del primer declarant quan s'hagi de declarar al Modelo 100.",
        hu="Az első adózó halálozási dátuma, ha a Modelo 100-ban szerepelnie kell.",
    ),
    _key(
        key="spouse.tax.id",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="NIF/NIE del cónyuge cuando la declaración conjunta lo requiere.",
        en="Spouse NIF/NIE when joint taxation requires it.",
        ca="NIF/NIE del cònjuge quan la declaració conjunta ho requereix.",
        hu="A házastárs NIF/NIE azonosítója, ha a közös bevallás megköveteli.",
        required_when_key="declaration.type",
        required_when_value="2",
    ),
    _key(
        key="spouse.name",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Nombre del cónyuge para los datos identificativos de Modelo 100.",
        en="Spouse given name for Modelo 100 identity data.",
        ca="Nom del cònjuge per a les dades identificatives del Modelo 100.",
        hu="A házastárs keresztneve a Modelo 100 azonosító adataihoz.",
        required_when_key="declaration.type",
        required_when_value="2",
    ),
    _key(
        key="spouse.surnames",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Apellidos del cónyuge para los datos identificativos de Modelo 100.",
        en="Spouse surnames for Modelo 100 identity data.",
        ca="Cognoms del cònjuge per a les dades identificatives del Modelo 100.",
        hu="A házastárs vezetéknevei a Modelo 100 azonosító adataihoz.",
        required_when_key="declaration.type",
        required_when_value="2",
    ),
    _key(
        key="spouse.birth_date",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Fecha de nacimiento del cónyuge para Modelo 100.",
        en="Spouse birth date for Modelo 100.",
        ca="Data de naixement del cònjuge per al Modelo 100.",
        hu="A házastárs születési dátuma a Modelo 100-hoz.",
        required_when_key="declaration.type",
        required_when_value="2",
    ),
    _key(
        key="spouse.sex",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Sexo del cónyuge según el diseño oficial del Modelo 100.",
        en="Spouse sex according to the official Modelo 100 design.",
        ca="Sexe del cònjuge segons el disseny oficial del Modelo 100.",
        hu="A házastárs neme a hivatalos Modelo 100 szerkezet szerint.",
        required_when_key="declaration.type",
        required_when_value="2",
    ),
    _key(
        key="spouse.disability_grade",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Clave de discapacidad del cónyuge según el diseño oficial del Modelo 100.",
        en="Spouse disability code according to the official Modelo 100 design.",
        ca="Clau de discapacitat del cònjuge segons el disseny oficial del Modelo 100.",
        hu="A házastárs fogyatékossági kódja a hivatalos Modelo 100 szerkezet szerint.",
    ),
    _key(
        key="spouse.non_resident_irpf",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Marca oficial de cónyuge no residente y no contribuyente del IRPF.",
        en="Official flag for a spouse who is non-resident and not an IRPF taxpayer.",
        ca="Marca oficial de cònjuge no resident i no contribuent de l'IRPF.",
        hu="Hivatalos jelölés nem rezidens, IRPF-alanynak nem minősülő házastárshoz.",
    ),
    _key(
        key="spouse.eu_eea_resident",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Marca oficial de residencia del cónyuge en la Unión Europea o el Espacio Económico Europeo.",
        en="Official flag for spouse residence in the European Union or European Economic Area.",
        ca="Marca oficial de residència del cònjuge a la Unió Europea o l'Espai Econòmic Europeu.",
        hu="Hivatalos jelölés a házastárs Európai Uniós vagy EGT-beli rezidenciájához.",
        required_when_key="spouse.non_resident_irpf",
        required_when_value="true",
    ),
    _key(
        key="spouse.eu_eea_country",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="País de residencia UE o EEE del cónyuge para Modelo 100.",
        en="Spouse EU or EEA country of residence for Modelo 100.",
        ca="País de residència UE o EEE del cònjuge per al Modelo 100.",
        hu="A házastárs EU- vagy EGT-beli lakóhely szerinti országa a Modelo 100-hoz.",
        required_when_key="spouse.eu_eea_resident",
        required_when_value="true",
    ),
    _key(
        key="family.descendants_eu_eea_deduction",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Marca oficial para hijos o descendientes UE/EEE en la deducción de unidad familiar.",
        en="Official flag for EU/EEA children or descendants in the family-unit deduction.",
        ca="Marca oficial per a fills o descendents UE/EEE en la deducció d'unitat familiar.",
        hu="Hivatalos jelölés EU/EGT gyermekekhez vagy leszármazottakhoz a családi egység kedvezményében.",
    ),
    _key(
        key="family.minor_children_in_unit",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Marca oficial de hijos menores que forman parte de la unidad familiar.",
        en="Official flag for minor children who are part of the family unit.",
        ca="Marca oficial de fills menors que formen part de la unitat familiar.",
        hu="Hivatalos jelölés a családi egységhez tartozó kiskorú gyermekekhez.",
    ),
    _key(
        key="iva.regime",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Regimen IVA del autonomo: general | simplificado | recargo-equivalencia | exento.",
        en="IVA regime: general | simplificado | recargo-equivalencia | exento.",
        ca="Regim IVA de l'autonom: general | simplificado | recargo-equivalencia | exento.",
        hu="ÁFA rezsim: general | simplificado | recargo-equivalencia | exento.",
    ),
    _key(
        key="iva.roi_enrolled",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="ROI: alta en el Registro de Operadores Intracomunitarios (true/false).",
        en="ROI: enrolled in the Intracomunitario Operators Register (true/false).",
        ca="ROI: alta en el Registre d'Operadors Intracomunitaris (true/false).",
        hu="ROI: regisztrálva van az Intracomunitario operátorok regiszterében (true/false).",
    ),
    _key(
        key="iva.oss_enrolled",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="OSS: alta en el regimen de ventanilla unica (true/false).",
        en="OSS: enrolled in the One-Stop-Shop regime (true/false).",
        ca="OSS: alta en el regim de finestreta unica (true/false).",
        hu="OSS: regisztrálva van az egyablakos rendszerben (true/false).",
    ),
    _key(
        key="iva.intracommunity_operations_exceed_50000_eur",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Operaciones intracomunitarias superan el umbral de 50.000 euros (true/false).",
        en="Intra-community operations exceed the 50,000 euro threshold (true/false).",
        ca="Les operacions intracomunitaries superen el llindar de 50.000 euros (true/false).",
        hu="Közösségi műveletek meghaladják az 50 000 eurós küszöböt (true/false).",
    ),
    _key(
        key="enrollment.large_company",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Empresa de gran volumen segun la AEAT (true/false).",
        en="Large-company enrollment per AEAT (true/false).",
        ca="Empresa de gran volum segons l'AEAT (true/false).",
        hu="Nagyvállalat besorolás az AEAT szerint (true/false).",
    ),
    _key(
        key="enrollment.public_administration_budget_gt_6000000",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Administracion publica con presupuesto superior a 6.000.000 (true/false).",
        en="Public-administration budget exceeds 6,000,000 (true/false).",
        ca="Administracio publica amb pressupost superior a 6.000.000 (true/false).",
        hu="Közigazgatási költségvetés meghaladja a 6 000 000 küszöböt (true/false).",
    ),
    _key(
        key="has_employees",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="El autonomo paga salarios con retencion (true/false).",
        en="The autonomo pays salaries with retencion (true/false).",
        ca="L'autonom paga salaris amb retencio (true/false).",
        hu="Az önfoglalkoztató bérleti adóelőleget vonva fizet munkabért (true/false).",
    ),
    _key(
        key="pays_professionals_with_retencion",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Pago a profesionales con retencion (true/false).",
        en="Pays professionals with retencion (true/false).",
        ca="Paga a professionals amb retencio (true/false).",
        hu="Szakembereket adóelőleggel fizet (true/false).",
    ),
    _key(
        key="professional_income_withholding_ge_70pct",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Al menos 70 por ciento de los ingresos profesionales con retencion previa (true/false).",
        en="At least 70 percent of professional income previously subject to withholding (true/false).",
        ca="Almenys el 70 per cent dels ingressos professionals amb retencio previa (true/false).",
        hu="A szakmai jövedelem legalább 70 százaléka előzetes adólevonás alá esett (true/false).",
    ),
    _key(
        key="pays_rent_with_retencion",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Paga alquiler de local con retencion (true/false).",
        en="Pays local rent with retencion (true/false).",
        ca="Paga lloguer de local amb retencio (true/false).",
        hu="Helyiségbérletet adóelőleggel fizet (true/false).",
    ),
    _key(
        key="pays_capital_income_with_retencion",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Paga rentas de capital con retencion (true/false).",
        en="Pays capital-income rents with retencion (true/false).",
        ca="Paga rendes de capital amb retencio (true/false).",
        hu="Tőkejövedelmeket adóelőleggel fizet (true/false).",
    ),
    _key(
        key="uses_objective_estimation_irpf",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Tributa IRPF en estimacion objetiva (true/false).",
        en="Files IRPF under estimacion objetiva (true/false).",
        ca="Tributa IRPF en estimacio objectiva (true/false).",
        hu="IRPF-et becsült rendszerben adózza (true/false).",
    ),
    _key(
        key="does_intracomunitario",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Realiza operaciones intracomunitarias (true/false).",
        en="Conducts intracomunitario operations (true/false).",
        ca="Realitza operacions intracomunitaries (true/false).",
        hu="Közösségi (intracomunitario) műveleteket végez (true/false).",
    ),
    _key(
        key="third_party_transactions_above_347_threshold",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Operaciones con terceros superan el umbral del Modelo 347 (true/false).",
        en="Third-party transactions exceed the Modelo 347 threshold (true/false).",
        ca="Operacions amb tercers superen el llindar del Modelo 347 (true/false).",
        hu="Harmadik felekkel folytatott műveletek meghaladják a Modelo 347 küszöböt (true/false).",
    ),
    _key(
        key="bienes_extranjero_above_threshold",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Bienes en el extranjero por encima del umbral legal (true/false).",
        en="Foreign-held assets above the legal threshold (true/false).",
        ca="Bens a l'estranger per sobre del llindar legal (true/false).",
        hu="Külföldön tartott eszközök a törvényi küszöb felett (true/false).",
    ),
    _key(
        key="notes",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Notas libres del operador, no consumidas por el motor.",
        en="Free-form operator notes, not consumed by the engine.",
        ca="Notes lliures de l'operador, no consumides pel motor.",
        hu="Szabad operátori jegyzetek, nem fogyasztja a motor.",
    ),
)
"""Closed registry of editable taxpayer-profile keys."""


_BY_KEY: dict[str, ProfileKey] = {entry.key: entry for entry in PROFILE_KEYS}


def get_profile_key(key: str) -> ProfileKey:
    """Return the :class:`ProfileKey` for ``key``.

    Raises:
        KeyError: When ``key`` is not in the registry.
    """
    try:
        return _BY_KEY[key]
    except KeyError as exc:
        raise KeyError(f"unknown profile key: {key!r}") from exc


def required_profile_keys() -> tuple[ProfileKey, ...]:
    """Return only the keys whose :attr:`requirement` is ``REQUIRED``."""
    return tuple(entry for entry in PROFILE_KEYS if entry.requirement is ProfileKeyRequirement.REQUIRED)


def optional_profile_keys() -> tuple[ProfileKey, ...]:
    """Return only the keys whose :attr:`requirement` is ``OPTIONAL``."""
    return tuple(entry for entry in PROFILE_KEYS if entry.requirement is ProfileKeyRequirement.OPTIONAL)


__all__ = [
    "PROFILE_KEYS",
    "ProfileKey",
    "ProfileKeyRequirement",
    "get_profile_key",
    "optional_profile_keys",
    "required_profile_keys",
]
