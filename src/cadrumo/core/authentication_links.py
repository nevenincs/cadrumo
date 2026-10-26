"""Public authentication entry points with no session or identity material."""

from urllib.parse import quote


def aeat_authentication_url() -> str:
    """Return the bundled public Cl@ve entry point, without operator overrides."""
    from .config import Settings

    external = Settings.external_constants().aeat
    return external.clave_movil.selector_access_url_template.format(
        target=quote(external.sede_paths.expedientes_resumen, safe="")
    )
