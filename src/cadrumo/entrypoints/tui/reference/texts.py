"""The wording of the reference area, in the language now on screen."""

from __future__ import annotations

from ....core.i18n.render import tr
from .reads import ReferenceRead


def read_label(read: ReferenceRead) -> str:
    """Name one reference read."""
    match read:
        case ReferenceRead.MODELOS:
            return tr("tui.reference.read.modelos")
        case ReferenceRead.SUPPORT_MATRIX:
            return tr("tui.reference.read.support_matrix")
        case ReferenceRead.DESCRIBE:
            return tr("tui.reference.read.describe")
        case ReferenceRead.CASILLAS:
            return tr("tui.reference.read.casillas")
        case ReferenceRead.CASILLA:
            return tr("tui.reference.read.casilla")
        case ReferenceRead.FORMULAS:
            return tr("tui.reference.read.formulas")
        case ReferenceRead.BINDINGS:
            return tr("tui.reference.read.bindings")
        case ReferenceRead.CATEGORIES:
            return tr("tui.reference.read.categories")
        case ReferenceRead.PORTALS:
            return tr("tui.reference.read.portals")
        case ReferenceRead.PORTAL:
            return tr("tui.reference.read.portal")
        case ReferenceRead.AUTH_PROVIDERS:
            return tr("tui.reference.read.auth_providers")
        case ReferenceRead.APODERADO_SCOPES:
            return tr("tui.reference.read.apoderado_scopes")


def read_summary(read: ReferenceRead) -> str:
    """Say in one sentence what one reference read shows."""
    match read:
        case ReferenceRead.MODELOS:
            return tr("tui.reference.summary.modelos")
        case ReferenceRead.SUPPORT_MATRIX:
            return tr("tui.reference.summary.support_matrix")
        case ReferenceRead.DESCRIBE:
            return tr("tui.reference.summary.describe")
        case ReferenceRead.CASILLAS:
            return tr("tui.reference.summary.casillas")
        case ReferenceRead.CASILLA:
            return tr("tui.reference.summary.casilla")
        case ReferenceRead.FORMULAS:
            return tr("tui.reference.summary.formulas")
        case ReferenceRead.BINDINGS:
            return tr("tui.reference.summary.bindings")
        case ReferenceRead.CATEGORIES:
            return tr("tui.reference.summary.categories")
        case ReferenceRead.PORTALS:
            return tr("tui.reference.summary.portals")
        case ReferenceRead.PORTAL:
            return tr("tui.reference.summary.portal")
        case ReferenceRead.AUTH_PROVIDERS:
            return tr("tui.reference.summary.auth_providers")
        case ReferenceRead.APODERADO_SCOPES:
            return tr("tui.reference.summary.apoderado_scopes")


def filter_label(name: str) -> str:
    """Name one coordinate of a read."""
    labels = {
        "modelo": tr("tui.reference.filter.modelo"),
        "year": tr("tui.reference.filter.year"),
        "period": tr("tui.reference.filter.period"),
        "as_of": tr("tui.reference.filter.as_of"),
        "domain": tr("tui.reference.filter.domain"),
        "input_kind": tr("tui.reference.filter.input_kind"),
        "required": tr("tui.reference.filter.required"),
        "form_number": tr("tui.reference.filter.form_number"),
        "casilla_number": tr("tui.reference.filter.casilla_number"),
        "casilla": tr("tui.reference.filter.casilla"),
        "category": tr("tui.reference.filter.category"),
        "portal": tr("tui.reference.filter.portal"),
    }
    return labels.get(name, name)


__all__ = ["filter_label", "read_label", "read_summary"]
