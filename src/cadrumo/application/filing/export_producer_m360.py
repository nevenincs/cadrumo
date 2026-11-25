"""Modelo 360 producer values for declaration export."""

from __future__ import annotations

from ...core.filing_producer_key import FilingProducerKey
from .producer_snapshot import FilingProducerSnapshot, TaxpayerIdentityFacts
from .producer_snapshot_m360 import Modelo360ProfileFacts

_M360_SOLICITANTE_DOMICILIO_FIELD_BY_KEY: dict[FilingProducerKey, str] = {
    FilingProducerKey.M360_SOLICITANTE_DOMICILIO_TIPO_VIA: "tipo_via",
    FilingProducerKey.M360_SOLICITANTE_DOMICILIO_NOMBRE_VIA: "nombre_via",
    FilingProducerKey.M360_SOLICITANTE_DOMICILIO_TIPO_NUMERACION: "tipo_numeracion",
    FilingProducerKey.M360_SOLICITANTE_DOMICILIO_NUMERO_CASA: "numero_casa",
    FilingProducerKey.M360_SOLICITANTE_DOMICILIO_CALIFICADOR_NUMERO: "calificador_numero",
    FilingProducerKey.M360_SOLICITANTE_DOMICILIO_BLOQUE: "bloque",
    FilingProducerKey.M360_SOLICITANTE_DOMICILIO_PORTAL: "portal",
    FilingProducerKey.M360_SOLICITANTE_DOMICILIO_ESCALERA: "escalera",
    FilingProducerKey.M360_SOLICITANTE_DOMICILIO_PLANTA: "planta",
    FilingProducerKey.M360_SOLICITANTE_DOMICILIO_PUERTA: "puerta",
    FilingProducerKey.M360_SOLICITANTE_DOMICILIO_DATOS_COMPLEMENTARIOS: "datos_complementarios",
    FilingProducerKey.M360_SOLICITANTE_DOMICILIO_LOCALIDAD: "localidad",
    FilingProducerKey.M360_SOLICITANTE_DOMICILIO_CODIGO_POSTAL: "codigo_postal",
    FilingProducerKey.M360_SOLICITANTE_DOMICILIO_NOMBRE_MUNICIPIO: "nombre_municipio",
    FilingProducerKey.M360_SOLICITANTE_DOMICILIO_PROVINCIA: "provincia",
}
_M360_REPRESENTANTE_DOMICILIO_FIELD_BY_KEY: dict[FilingProducerKey, str] = {
    FilingProducerKey.M360_REPRESENTANTE_DOMICILIO_TIPO_VIA: "tipo_via",
    FilingProducerKey.M360_REPRESENTANTE_DOMICILIO_NOMBRE_VIA: "nombre_via",
    FilingProducerKey.M360_REPRESENTANTE_DOMICILIO_TIPO_NUMERACION: "tipo_numeracion",
    FilingProducerKey.M360_REPRESENTANTE_DOMICILIO_NUMERO_CASA: "numero_casa",
    FilingProducerKey.M360_REPRESENTANTE_DOMICILIO_CALIFICADOR_NUMERO: "calificador_numero",
    FilingProducerKey.M360_REPRESENTANTE_DOMICILIO_BLOQUE: "bloque",
    FilingProducerKey.M360_REPRESENTANTE_DOMICILIO_PORTAL: "portal",
    FilingProducerKey.M360_REPRESENTANTE_DOMICILIO_ESCALERA: "escalera",
    FilingProducerKey.M360_REPRESENTANTE_DOMICILIO_PLANTA: "planta",
    FilingProducerKey.M360_REPRESENTANTE_DOMICILIO_PUERTA: "puerta",
    FilingProducerKey.M360_REPRESENTANTE_DOMICILIO_DATOS_COMPLEMENTARIOS: "datos_complementarios",
    FilingProducerKey.M360_REPRESENTANTE_DOMICILIO_LOCALIDAD: "localidad",
    FilingProducerKey.M360_REPRESENTANTE_DOMICILIO_CODIGO_POSTAL: "codigo_postal",
    FilingProducerKey.M360_REPRESENTANTE_DOMICILIO_NOMBRE_MUNICIPIO: "nombre_municipio",
    FilingProducerKey.M360_REPRESENTANTE_DOMICILIO_PROVINCIA: "provincia",
}
_M360_SOLICITANTE_APARTADO_FIELD_BY_KEY: dict[FilingProducerKey, str] = {
    FilingProducerKey.M360_SOLICITANTE_APARTADO_CORREOS_NUMERO: "numero",
    FilingProducerKey.M360_SOLICITANTE_APARTADO_CORREOS_LOCALIDAD: "localidad",
    FilingProducerKey.M360_SOLICITANTE_APARTADO_CORREOS_CODIGO_POSTAL: "codigo_postal",
    FilingProducerKey.M360_SOLICITANTE_APARTADO_CORREOS_NOMBRE_MUNICIPIO: "nombre_municipio",
    FilingProducerKey.M360_SOLICITANTE_APARTADO_CORREOS_PROVINCIA: "provincia",
}
_M360_REPRESENTANTE_APARTADO_FIELD_BY_KEY: dict[FilingProducerKey, str] = {
    FilingProducerKey.M360_REPRESENTANTE_APARTADO_CORREOS_NUMERO: "numero",
    FilingProducerKey.M360_REPRESENTANTE_APARTADO_CORREOS_LOCALIDAD: "localidad",
    FilingProducerKey.M360_REPRESENTANTE_APARTADO_CORREOS_CODIGO_POSTAL: "codigo_postal",
    FilingProducerKey.M360_REPRESENTANTE_APARTADO_CORREOS_NOMBRE_MUNICIPIO: "nombre_municipio",
    FilingProducerKey.M360_REPRESENTANTE_APARTADO_CORREOS_PROVINCIA: "provincia",
}
_M360_REPRESENTANTE_FOREIGN_ADDRESS_FIELD_BY_KEY: dict[FilingProducerKey, str] = {
    FilingProducerKey.M360_REPRESENTANTE_FOREIGN_ADDRESS_STREET: "street",
    FilingProducerKey.M360_REPRESENTANTE_FOREIGN_ADDRESS_CITY: "city",
    FilingProducerKey.M360_REPRESENTANTE_FOREIGN_ADDRESS_POSTAL_CODE: "postal_code",
    FilingProducerKey.M360_REPRESENTANTE_FOREIGN_ADDRESS_REGION: "region",
    FilingProducerKey.M360_REPRESENTANTE_FOREIGN_ADDRESS_COUNTRY_CODE: "country_code",
}
#: DR360 página 1 campos 31-35 read "espacios": a solicitante established in Spain, or in
#: Canarias, Ceuta o Melilla, has no foreign address to declare, so these always resolve blank.
_M360_SOLICITANTE_FOREIGN_ADDRESS_KEYS: tuple[FilingProducerKey, ...] = (
    FilingProducerKey.M360_SOLICITANTE_FOREIGN_ADDRESS_STREET,
    FilingProducerKey.M360_SOLICITANTE_FOREIGN_ADDRESS_CITY,
    FilingProducerKey.M360_SOLICITANTE_FOREIGN_ADDRESS_POSTAL_CODE,
    FilingProducerKey.M360_SOLICITANTE_FOREIGN_ADDRESS_REGION,
    FilingProducerKey.M360_SOLICITANTE_FOREIGN_ADDRESS_COUNTRY_CODE,
)
_M360_SCALAR_KEYS: tuple[FilingProducerKey, ...] = (
    FilingProducerKey.M360_PRESENTACION_EN_PRUEBAS,
    FilingProducerKey.M360_NIVEL_CALIDAD_DATOS,
    FilingProducerKey.M360_PAIS_DESTINO_SOLICITUD,
    FilingProducerKey.M360_CAUSA_PRESENTACION,
    FilingProducerKey.M360_COMUNICACION_PRORRATA_DEFINITIVA,
    FilingProducerKey.M360_NUMERO_REGISTRO_DECLARACION_ANTERIOR,
    FilingProducerKey.M360_SOLICITANTE_TAX_ID,
    FilingProducerKey.M360_SOLICITANTE_FULL_NAME,
    FilingProducerKey.M360_SOLICITANTE_EMAIL,
    FilingProducerKey.M360_SOLICITANTE_PHONE,
    FilingProducerKey.M360_SOLICITANTE_ESTABLECIDO_EN_TAI,
    FilingProducerKey.M360_SOLICITANTE_HACIENDA_FORAL,
    FilingProducerKey.M360_SOLICITANTE_DELEGACION_CANARIAS_CEUTA_MELILLA,
    FilingProducerKey.M360_REPRESENTANTE_TAX_ID,
    FilingProducerKey.M360_REPRESENTANTE_FULL_NAME,
    FilingProducerKey.M360_REPRESENTANTE_EMAIL,
    FilingProducerKey.M360_REPRESENTANTE_PHONE,
    FilingProducerKey.M360_CUENTA_TITULAR_NOMBRE,
    FilingProducerKey.M360_CUENTA_TITULAR_EN_CALIDAD_DE,
    FilingProducerKey.M360_CUENTA_DIVISA,
)
M360_PRODUCER_KEYS: frozenset[FilingProducerKey] = frozenset(
    {
        *_M360_SCALAR_KEYS,
        *_M360_SOLICITANTE_FOREIGN_ADDRESS_KEYS,
        *_M360_SOLICITANTE_DOMICILIO_FIELD_BY_KEY,
        *_M360_REPRESENTANTE_DOMICILIO_FIELD_BY_KEY,
        *_M360_SOLICITANTE_APARTADO_FIELD_BY_KEY,
        *_M360_REPRESENTANTE_APARTADO_FIELD_BY_KEY,
        *_M360_REPRESENTANTE_FOREIGN_ADDRESS_FIELD_BY_KEY,
    }
)


def _m360_zero_one(value: bool | None) -> str | None:
    """DR360 writes these answers "1"/"0"; absent stays absent, never a "0"."""
    if value is None:
        return None
    return "1" if value else "0"


def _m360_solicitante_name(identity: TaxpayerIdentityFacts) -> str | None:
    """DR360 campo 13, "Apellidos y nombre o denominación social".

    An entity's legal name, or a person's surnames before the given name as the label
    orders them. ``full_name`` is not used: its order is not part of the identity
    contract, and guessing it would print a name AEAT cannot match to the NIF.
    """
    if identity.legal_name is not None:
        return identity.legal_name
    if identity.surnames is not None and identity.given_name is not None:
        return f"{identity.surnames} {identity.given_name}"
    return None


def _m360_scope_values(
    field_by_key: dict[FilingProducerKey, str], scope: object | None
) -> dict[FilingProducerKey, object]:
    return {key: (getattr(scope, field) if scope is not None else None) for key, field in field_by_key.items()}


def m360_producer_values(snapshot: FilingProducerSnapshot) -> dict[FilingProducerKey, object]:
    """Resolve the solicitud, parties and account holder Modelo 360's página 1 cites.

    The solicitante is the filing's taxpayer, so its NIF and name come from the snapshot's
    identity rather than a second copy in the profile. Every other value comes from
    :class:`Modelo360ProfileFacts`, whose types already enforce DR360's widths and code
    sets; a field the profile leaves absent resolves to ``None`` and the renderer decides,
    from the layout's own ``required`` flag, whether that blank is legal.

    A profile of the wrong type yields every key as ``None`` rather than raising: this
    resolver runs for every modelo, and only Modelo 360's snapshot validator may decide
    that a 360 filing without these facts is invalid.
    """
    profile = snapshot.model_profile
    values: dict[FilingProducerKey, object] = {key: None for key in M360_PRODUCER_KEYS}
    if not isinstance(profile, Modelo360ProfileFacts):
        return values
    solicitud = profile.solicitud
    solicitante = profile.solicitante
    establecimiento = solicitante.establecimiento
    representante = profile.representante
    values.update(
        {
            FilingProducerKey.M360_PRESENTACION_EN_PRUEBAS: _m360_zero_one(solicitud.presentacion_en_pruebas),
            FilingProducerKey.M360_NIVEL_CALIDAD_DATOS: solicitud.nivel_calidad_datos.code,
            FilingProducerKey.M360_PAIS_DESTINO_SOLICITUD: solicitud.pais_destino,
            FilingProducerKey.M360_CAUSA_PRESENTACION: solicitud.causa_presentacion.code,
            FilingProducerKey.M360_COMUNICACION_PRORRATA_DEFINITIVA: _m360_zero_one(
                solicitud.comunicacion_prorrata_definitiva
            ),
            FilingProducerKey.M360_NUMERO_REGISTRO_DECLARACION_ANTERIOR: (
                solicitud.numero_registro_declaracion_anterior
            ),
            FilingProducerKey.M360_SOLICITANTE_TAX_ID: snapshot.taxpayer_tax_id,
            FilingProducerKey.M360_SOLICITANTE_FULL_NAME: _m360_solicitante_name(snapshot.taxpayer_identity),
            FilingProducerKey.M360_SOLICITANTE_EMAIL: solicitante.email,
            FilingProducerKey.M360_SOLICITANTE_PHONE: solicitante.phone,
            FilingProducerKey.M360_SOLICITANTE_ESTABLECIDO_EN_TAI: _m360_zero_one(
                establecimiento.establecido_en_territorio_de_aplicacion
            ),
            FilingProducerKey.M360_SOLICITANTE_HACIENDA_FORAL: (
                establecimiento.hacienda_foral.code if establecimiento.hacienda_foral is not None else None
            ),
            FilingProducerKey.M360_SOLICITANTE_DELEGACION_CANARIAS_CEUTA_MELILLA: (
                establecimiento.delegacion_canarias_ceuta_melilla.code
                if establecimiento.delegacion_canarias_ceuta_melilla is not None
                else None
            ),
            FilingProducerKey.M360_CUENTA_TITULAR_NOMBRE: profile.cuenta.titular_nombre,
            FilingProducerKey.M360_CUENTA_TITULAR_EN_CALIDAD_DE: profile.cuenta.titular_en_calidad_de.code,
            FilingProducerKey.M360_CUENTA_DIVISA: profile.cuenta.divisa,
        }
    )
    values.update(_m360_representative_values(representante))
    values.update(_m360_scope_values(_M360_SOLICITANTE_DOMICILIO_FIELD_BY_KEY, solicitante.domicilio))
    values.update(_m360_scope_values(_M360_SOLICITANTE_APARTADO_FIELD_BY_KEY, solicitante.apartado_correos))
    values.update(
        _m360_scope_values(
            _M360_REPRESENTANTE_DOMICILIO_FIELD_BY_KEY,
            representante.domicilio if representante is not None else None,
        )
    )
    values.update(
        _m360_scope_values(
            _M360_REPRESENTANTE_APARTADO_FIELD_BY_KEY,
            representante.apartado_correos if representante is not None else None,
        )
    )
    values.update(
        _m360_scope_values(
            _M360_REPRESENTANTE_FOREIGN_ADDRESS_FIELD_BY_KEY,
            representante.foreign_address if representante is not None else None,
        )
    )
    return values


def _m360_representative_values(representante: object | None) -> dict[FilingProducerKey, object]:
    return {
        FilingProducerKey.M360_REPRESENTANTE_TAX_ID: getattr(representante, "tax_id", None),
        FilingProducerKey.M360_REPRESENTANTE_FULL_NAME: getattr(representante, "full_name", None),
        FilingProducerKey.M360_REPRESENTANTE_EMAIL: getattr(representante, "email", None),
        FilingProducerKey.M360_REPRESENTANTE_PHONE: getattr(representante, "phone", None),
    }
