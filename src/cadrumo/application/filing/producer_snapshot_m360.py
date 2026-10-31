"""Typed Modelo 360 producer facts: the solicitud header, the parties and the account holder.

Modelo 360 is the solicitud de devolución del IVA of an empresario establecido en el
territorio de aplicación del Impuesto for IVA borne in another Member State, and of one
established in Canarias, Ceuta o Melilla for IVA borne in that territorio (Orden
EHA/789/2010 art. 1.2). Its record design (DR360, página 1) asks the
header facts below in its own fixed positions; every width and code set here is the one
DR360 prints for that position.

The solicitante's NIF and name are not repeated here: the solicitante is the filing's
taxpayer, whose identity the snapshot already carries. The refund IBAN and BIC are not here
either: they travel only as the snapshot's encrypted, selected refund account. What remains
is what no other fact can answer.

The operator declares these facts once per solicitud, and they persist in the encrypted
:class:`Modelo360SolicitudRegister` beside the refund account DR360 campos 115 and 116 pay
into. That account is the solicitud's own rather than the profile's IVA refund account,
because DR360 campo 114 lets it belong to the representante.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, override

from pydantic import BaseModel, Field, StringConstraints, ValidationInfo, field_validator, model_validator

from cadrumo.domain.calculations.registry.tax_id_format import SubjectTaxId

from ...core.country_code import COUNTRY_CODE_ALPHA2_PATTERN, CountryCodeAlpha2
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.parsing.codes import IsoCurrencyCodeText
from ...core.period import Period
from ...domain.calculations.registry.form_codes import RegistryCodedEnum, require_form_fit, require_form_width
from ...domain.deadlines.models import RefundAccount
from ...domain.transactions.own_accounts import OwnAccountId

#: A field's design length comes from the registry through its model's validator; these bound the wire.
_Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
#: DR360 types the numero de casa and the codigos postales ``Num``, and the published layout
#: renders them as full-width digit identifiers, so the fact carries every digit.
_Digits = Annotated[str, StringConstraints(pattern=r"^\d+$", max_length=16)]
_Email = Annotated[str, StringConstraints(strip_whitespace=True, max_length=128, pattern=r"^[^@\s]+@[^@\s]+$")]
_CurrencyCode = IsoCurrencyCodeText

#: Each field and the design length the registry declares for it.
_ADDRESS_FITS = {
    "tipo_via": "m360.address.street_type_max",
    "nombre_via": "m360.address.street_name_max",
    "tipo_numeracion": "m360.address.number_type_max",
    "calificador_numero": "m360.address.number_qualifier_max",
    "bloque": "m360.address.block_max",
    "portal": "m360.address.portal_max",
    "escalera": "m360.address.staircase_max",
    "planta": "m360.address.floor_max",
    "puerta": "m360.address.door_max",
    "datos_complementarios": "m360.address.complement_max",
    "localidad": "m360.address.locality_max",
    "nombre_municipio": "m360.address.municipality_max",
    "provincia": "m360.address.province_max",
}
_PO_BOX_FITS = {key: _ADDRESS_FITS[key] for key in ("localidad", "nombre_municipio", "provincia")}
_FOREIGN_ADDRESS_FITS = {
    "street": "m360.foreign_address.street_max",
    "city": "m360.foreign_address.city_max",
    "postal_code": "m360.foreign_address.postal_code_max",
    "region": "m360.foreign_address.region_max",
}
_REPRESENTANTE_FITS = {"full_name": "m360.full_name_max", "phone": "m360.phone_max"}


def _fit(value: str | None, info: ValidationInfo, fits: dict[str, str]) -> str | None:
    return require_form_fit(value, fits[str(info.field_name)])


#: DR360 Nota 3: Greece is written ``EL`` in these positions, never its ISO ``GR``.
_GREECE_ISO_CODE = "GR"
_SPAIN = "ES"


_M360_FORM_CODES_FACT = "modelo-360-page-one-form-codes"


class M360NivelCalidadDatos(RegistryCodedEnum):
    """DR360 página 1 campo 5, Nota 2."""

    MEDIA = "media"
    MAXIMA = "maxima"

    @classmethod
    @override
    def _form_code_source(cls) -> tuple[str, str]:
        return _M360_FORM_CODES_FACT, "nivel_calidad"


class M360CausaPresentacion(RegistryCodedEnum):
    """DR360 página 1 campo 8, Nota 4.

    The design's third value, a blank for a communication of the prorrata definitiva on
    its own, is absent: the published layout requires this position, so a blank could not
    be emitted, and a contract admitting it would only refuse later.
    """

    INICIAL = "inicial"
    MODIFICACION = "modificacion"

    @classmethod
    @override
    def _form_code_source(cls) -> tuple[str, str]:
        return _M360_FORM_CODES_FACT, "causa"


class M360AmbitoEstablecimiento(StrEnum):
    """Where the solicitante is established, which decides DR360 página 1 campos 41-43."""

    TERRITORIO_COMUN = "territorio_comun"
    HACIENDA_FORAL = "hacienda_foral"
    CANARIAS_CEUTA_MELILLA = "canarias_ceuta_melilla"


class M360HaciendaForal(RegistryCodedEnum):
    """DR360 página 1 campo 42, Nota 7."""

    ALAVA = "alava"
    GIPUZKOA = "gipuzkoa"
    NAVARRA = "navarra"
    BIZKAIA = "bizkaia"

    @classmethod
    @override
    def _form_code_source(cls) -> tuple[str, str]:
        return _M360_FORM_CODES_FACT, "hacienda_foral"


class M360DelegacionCanariasCeutaMelilla(RegistryCodedEnum):
    """DR360 página 1 campo 43, Nota 8."""

    LAS_PALMAS = "las_palmas"
    TENERIFE = "tenerife"
    CEUTA = "ceuta"
    MELILLA = "melilla"

    @classmethod
    @override
    def _form_code_source(cls) -> tuple[str, str]:
        return _M360_FORM_CODES_FACT, "delegacion"


class M360TitularEnCalidadDe(RegistryCodedEnum):
    """DR360 página 1 campo 114: whose account the refund is paid into."""

    SOLICITANTE = "solicitante"
    REPRESENTANTE = "representante"

    @classmethod
    @override
    def _form_code_source(cls) -> tuple[str, str]:
        return _M360_FORM_CODES_FACT, "titular"


class Modelo360SolicitudFacts(BaseModel):
    """The header of the solicitud itself, DR360 página 1 campos 4-10."""

    model_config = STRICT_FROZEN_CONFIG

    nivel_calidad_datos: M360NivelCalidadDatos
    #: ISO 3166-1 alpha-2 of the Member State the solicitud is addressed to.
    pais_destino: CountryCodeAlpha2 = Field(pattern=f"^{COUNTRY_CODE_ALPHA2_PATTERN}$")
    causa_presentacion: M360CausaPresentacion
    #: Required exactly when the solicitud modifies an earlier one (Nota 4).
    numero_registro_declaracion_anterior: _Text | None = None
    #: Nota 5. Absent writes a blank; ``False`` is the design's explicit "0".
    comunicacion_prorrata_definitiva: bool | None = None
    #: Nota 1. ``True`` asks AEAT only to validate the file; absent writes a blank.
    presentacion_en_pruebas: bool | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _refuse_inconsistent_header(self) -> Modelo360SolicitudFacts:
        if self.pais_destino == _GREECE_ISO_CODE:
            raise ValueError('modelo 360 writes Greece as "EL", never "GR" (DR360 Nota 3)')
        modifies = self.causa_presentacion is M360CausaPresentacion.MODIFICACION
        if modifies and self.numero_registro_declaracion_anterior is None:
            raise ValueError("a modelo 360 modificacion requires the registro number of the solicitud it modifies")
        if not modifies and self.numero_registro_declaracion_anterior is not None:
            raise ValueError("an initial modelo 360 solicitud carries no earlier registro number")
        # Nota 5 admits the communication only beside a blank or a "1" causa; the blank is
        # outside this contract, so only a modificacion may carry it.
        if self.comunicacion_prorrata_definitiva is True and not modifies:
            raise ValueError("DR360 Nota 5 admits the prorrata definitiva communication only with causa 1")
        return self

    @field_validator("numero_registro_declaracion_anterior")
    @classmethod
    @pydantic_validation_boundary
    def _previous_number_fits_the_design(cls, value: str | None) -> str | None:
        return require_form_fit(value, "m360.numero_registro_anterior_max")


class Modelo360DomicilioEspana(BaseModel):
    """A Spanish street address in DR360's shape: página 1 campos 16-30, and 78-92."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    tipo_via: _Text | None = None
    nombre_via: _Text | None = None
    tipo_numeracion: _Text | None = None
    numero_casa: _Digits | None = None
    calificador_numero: _Text | None = None
    bloque: _Text | None = None
    portal: _Text | None = None
    escalera: _Text | None = None
    planta: _Text | None = None
    puerta: _Text | None = None
    datos_complementarios: _Text | None = None
    #: Only when it differs from the municipio, as the design says.
    localidad: _Text | None = None
    codigo_postal: _Digits | None = None
    nombre_municipio: _Text | None = None
    provincia: _Text | None = None

    @field_validator(*_ADDRESS_FITS)
    @classmethod
    @pydantic_validation_boundary
    def _fits_the_design(cls, value: str | None, info: ValidationInfo) -> str | None:
        return _fit(value, info, _ADDRESS_FITS)

    @field_validator("numero_casa")
    @classmethod
    @pydantic_validation_boundary
    def _house_number_has_the_declared_width(cls, value: str | None) -> str | None:
        return require_form_width(value, "m360.address.house_number_digits")

    @field_validator("codigo_postal")
    @classmethod
    @pydantic_validation_boundary
    def _postal_code_has_the_declared_width(cls, value: str | None) -> str | None:
        return require_form_width(value, "m360.address.postal_code_digits")


class Modelo360ApartadoCorreos(BaseModel):
    """A Spanish apartado de correos: página 1 campos 36-40, and 98-102."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    numero: _Digits
    localidad: _Text | None = None
    codigo_postal: _Digits | None = None
    nombre_municipio: _Text | None = None
    provincia: _Text | None = None

    @field_validator(*_PO_BOX_FITS)
    @classmethod
    @pydantic_validation_boundary
    def _fits_the_design(cls, value: str | None, info: ValidationInfo) -> str | None:
        return _fit(value, info, _PO_BOX_FITS)

    @field_validator("numero")
    @classmethod
    @pydantic_validation_boundary
    def _number_has_the_declared_width(cls, value: str | None) -> str | None:
        return require_form_width(value, "m360.po_box.number_digits")

    @field_validator("codigo_postal")
    @classmethod
    @pydantic_validation_boundary
    def _postal_code_has_the_declared_width(cls, value: str | None) -> str | None:
        return require_form_width(value, "m360.address.postal_code_digits")


class Modelo360DireccionExtranjero(BaseModel):
    """The representante's foreign address, página 1 campos 93-97.

    The solicitante has no such block to fill: DR360 prescribes spaces for its campos 31-35.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    street: _Text | None = None
    city: _Text | None = None
    postal_code: _Text | None = None
    region: _Text | None = None
    country_code: CountryCodeAlpha2 | None = Field(default=None, pattern=f"^{COUNTRY_CODE_ALPHA2_PATTERN}$")

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _refuse_greece_iso_code(self) -> Modelo360DireccionExtranjero:
        if self.country_code == _GREECE_ISO_CODE:
            raise ValueError('modelo 360 writes Greece as "EL", never "GR" (DR360 Nota 3)')
        return self

    @field_validator(*_FOREIGN_ADDRESS_FITS)
    @classmethod
    @pydantic_validation_boundary
    def _fits_the_design(cls, value: str | None, info: ValidationInfo) -> str | None:
        return _fit(value, info, _FOREIGN_ADDRESS_FITS)


class Modelo360EstablecimientoFacts(BaseModel):
    """Where the solicitante is established, DR360 página 1 campos 41-43 (Notas 6-8).

    The three positions are one fact written three ways, so they are declared once and
    derived: the code of a foral hacienda or a Canarias, Ceuta o Melilla delegación exists
    exactly when that is where the solicitante is established.
    """

    model_config = STRICT_FROZEN_CONFIG

    ambito: M360AmbitoEstablecimiento
    hacienda_foral: M360HaciendaForal | None = None
    delegacion_canarias_ceuta_melilla: M360DelegacionCanariasCeutaMelilla | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _codes_follow_the_ambito(self) -> Modelo360EstablecimientoFacts:
        foral = self.ambito is M360AmbitoEstablecimiento.HACIENDA_FORAL
        ccm = self.ambito is M360AmbitoEstablecimiento.CANARIAS_CEUTA_MELILLA
        if foral != (self.hacienda_foral is not None):
            raise ValueError("a modelo 360 hacienda foral code is present exactly when established in one")
        if ccm != (self.delegacion_canarias_ceuta_melilla is not None):
            raise ValueError(
                "a modelo 360 delegacion code is present exactly when established in Canarias, Ceuta o Melilla"
            )
        return self

    @property
    def establecido_en_territorio_de_aplicacion(self) -> bool:
        """Nota 6: only the territorio comun reads "1"; foral and Canarias/Ceuta/Melilla read "0"."""
        return self.ambito is M360AmbitoEstablecimiento.TERRITORIO_COMUN


class Modelo360SolicitanteFacts(BaseModel):
    """The solicitante's contact, address and establishment, página 1 campos 14-43."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    email: _Email
    establecimiento: Modelo360EstablecimientoFacts
    phone: _Text | None = None
    domicilio: Modelo360DomicilioEspana | None = None
    apartado_correos: Modelo360ApartadoCorreos | None = None

    @field_validator("phone")
    @classmethod
    @pydantic_validation_boundary
    def _phone_fits_the_design(cls, value: str | None) -> str | None:
        return require_form_fit(value, "m360.phone_max")


class Modelo360RepresentanteFacts(BaseModel):
    """The representante acting for the solicitante (Orden EHA/789/2010 art. 2.1), campos 74-102.

    A representante who is declared at all is identified: the NIF and the name are what the
    block exists for, so neither may be absent once the block is present.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    tax_id: SubjectTaxId
    full_name: _Text
    email: _Email | None = None
    phone: _Text | None = None
    domicilio: Modelo360DomicilioEspana | None = None
    foreign_address: Modelo360DireccionExtranjero | None = None
    apartado_correos: Modelo360ApartadoCorreos | None = None

    @field_validator(*_REPRESENTANTE_FITS)
    @classmethod
    @pydantic_validation_boundary
    def _fits_the_design(cls, value: str | None, info: ValidationInfo) -> str | None:
        return _fit(value, info, _REPRESENTANTE_FITS)


class Modelo360CuentaTitularFacts(BaseModel):
    """The refund account's holder facts, página 1 campos 113, 114 and 117.

    Banking data: the IBAN and BIC beside them stay in the encrypted refund account.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    titular_nombre: _Text
    titular_en_calidad_de: M360TitularEnCalidadDe
    #: ISO 4217. The design's "por defecto EUR" is not applied here: the account's own
    #: currency is a fact about the account, so it is declared rather than assumed.
    divisa: _CurrencyCode

    @field_validator("titular_nombre")
    @classmethod
    @pydantic_validation_boundary
    def _holder_fits_the_design(cls, value: str | None) -> str | None:
        return require_form_fit(value, "m360.account.holder_name_max")


class Modelo360ProfileFacts(BaseModel):
    """Everything modelo 360's página 1 header cites that no other snapshot fact answers.

    A solicitante established in the territorio de aplicación del Impuesto -- común or
    foral -- asks for IVA borne in OTHER Member States (Orden EHA/789/2010 art. 1.2: "con
    excepción de las realizadas en dicho territorio"), so such a solicitud cannot be
    addressed to Spain. Canarias, Ceuta and Melilla claimants may address Spain.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    solicitud: Modelo360SolicitudFacts
    solicitante: Modelo360SolicitanteFacts
    cuenta: Modelo360CuentaTitularFacts
    representante: Modelo360RepresentanteFacts | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _refuse_inconsistent_parties(self) -> Modelo360ProfileFacts:
        if self.cuenta.titular_en_calidad_de is M360TitularEnCalidadDe.REPRESENTANTE and self.representante is None:
            raise ValueError("a modelo 360 account held by the representante requires a declared representante")
        in_territorio = self.solicitante.establecimiento.ambito is not M360AmbitoEstablecimiento.CANARIAS_CEUTA_MELILLA
        if in_territorio and self.solicitud.pais_destino == _SPAIN:
            raise ValueError(
                "a solicitante established in the territorio de aplicacion asks modelo 360 for IVA borne "
                "in another Member State, never in Spain",
            )
        return self


#: The persisted register's own document version, distinct from the secure-object envelope's.
MODELO_360_SOLICITUD_REGISTER_SCHEMA_VERSION = "1"


class Modelo360OwnAccountChoice(BaseModel):
    """The refund is paid into one of the solicitante's own accounts: DR360 campo 114 ``A``.

    Only the opaque own-account reference is held; the IBAN and BIC are read from the
    encrypted ledger own-account register when the solicitud is exported, and the
    export refuses a referenced account that carries no BIC (campo 116 is obligatorio).
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["own_account"] = "own_account"
    own_account_id: OwnAccountId


class Modelo360RepresentanteAccountChoice(BaseModel):
    """The refund is paid into the representante's account: DR360 campo 114 ``R``.

    A third party's account is not an own account, so it is embedded here, encrypted
    with the rest of the register, with the IBAN and BIC campos 115-116 require.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["representante"] = "representante"
    account: RefundAccount

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_iban_and_bic(self) -> Modelo360RepresentanteAccountChoice:
        if self.account.iban is None or not self.account.swift_bic.strip():
            raise ValueError("the representante's modelo 360 account needs its IBAN and banco-BIC")
        return self


type Modelo360AccountChoice = Annotated[
    Modelo360OwnAccountChoice | Modelo360RepresentanteAccountChoice,
    Field(discriminator="kind"),
]

#: Campo 114 each account choice states.
_HOLDER_BY_CHOICE: dict[str, M360TitularEnCalidadDe] = {
    "own_account": M360TitularEnCalidadDe.SOLICITANTE,
    "representante": M360TitularEnCalidadDe.REPRESENTANTE,
}


class Modelo360SolicitudEntry(BaseModel):
    """One solicitud's declared facts and the account its refund is paid into.

    ``account`` is ``None`` until the operator declares it. An absent account is not an
    empty one: the export refuses the solicitud rather than leave DR360 campos 115-116
    blank, so declaring the facts first and the account later is safe. Once declared,
    the choice decides campo 114: the facts' ``titular_en_calidad_de`` must state the
    holder the choice implies, so the page can never name one holder and pay another.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    period: Period
    facts: Modelo360ProfileFacts
    account: Modelo360AccountChoice | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _holder_follows_the_account_choice(self) -> Modelo360SolicitudEntry:
        if self.account is None:
            return self
        if self.facts.cuenta.titular_en_calidad_de is not _HOLDER_BY_CHOICE[self.account.kind]:
            raise ValueError("modelo 360 campo 114 must name the holder of the declared account")
        return self


class Modelo360SolicitudRegister(BaseModel):
    """Encrypted register document: every declared modelo 360 solicitud, one per period.

    The work unit addresses a solicitud by its filing year and the revision's single
    ``0A`` period, so the period is the entry's identity and a second declaration for
    it replaces the first. A period with no entry has declared nothing, which the export
    refuses; it never resolves to an empty or default solicitud.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    schema_version: str = MODELO_360_SOLICITUD_REGISTER_SCHEMA_VERSION
    entries: tuple[Modelo360SolicitudEntry, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _refuse_unsupported_or_repeated(self) -> Modelo360SolicitudRegister:
        if self.schema_version != MODELO_360_SOLICITUD_REGISTER_SCHEMA_VERSION:
            raise ValueError(f"unsupported modelo 360 solicitud register schema_version {self.schema_version!r}")
        periods = [entry.period for entry in self.entries]
        if len(periods) != len(set(periods)):
            raise ValueError("the modelo 360 solicitud register carries two entries for one period")
        return self

    def entry_for(self, period: Period) -> Modelo360SolicitudEntry | None:
        """Return the solicitud declared for ``period``, or ``None`` when none is."""
        return next((entry for entry in self.entries if entry.period == period), None)

    def with_entry(self, entry: Modelo360SolicitudEntry) -> Modelo360SolicitudRegister:
        """Return the register with ``entry`` declared, replacing any entry for its period."""
        kept = tuple(existing for existing in self.entries if existing.period != entry.period)
        ordered = sorted((*kept, entry), key=lambda item: (item.period.filing_year, item.period.registry_token))
        return Modelo360SolicitudRegister(entries=tuple(ordered))


__all__ = [
    "MODELO_360_SOLICITUD_REGISTER_SCHEMA_VERSION",
    "M360AmbitoEstablecimiento",
    "M360CausaPresentacion",
    "M360DelegacionCanariasCeutaMelilla",
    "M360HaciendaForal",
    "M360NivelCalidadDatos",
    "M360TitularEnCalidadDe",
    "Modelo360AccountChoice",
    "Modelo360ApartadoCorreos",
    "Modelo360CuentaTitularFacts",
    "Modelo360DireccionExtranjero",
    "Modelo360DomicilioEspana",
    "Modelo360EstablecimientoFacts",
    "Modelo360OwnAccountChoice",
    "Modelo360ProfileFacts",
    "Modelo360RepresentanteAccountChoice",
    "Modelo360RepresentanteFacts",
    "Modelo360SolicitanteFacts",
    "Modelo360SolicitudEntry",
    "Modelo360SolicitudFacts",
    "Modelo360SolicitudRegister",
]
