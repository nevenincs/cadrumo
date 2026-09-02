"""Diagnostics helpers for the declarations register walker."""

from __future__ import annotations

from .....core.hashing import sha256_hex
from .._html import parse_html
from .._playwright import Page, PlaywrightError
from ._adapter_utils import bounded_text, normalize_response_text, redacted_url
from ._declarations_listbox import NO_RESULTS_TEXT, _has_class


async def declarations_page_shape_context_from_page(
    page: Page,
    *,
    stage: str,
    modelo: str | None = None,
    ejercicio: int | None = None,
) -> dict[str, object]:
    try:
        html = await page.content()
    except PlaywrightError:
        html = ""
    return declarations_page_shape_context(
        html,
        landing_url=getattr(page, "url", "") or "",
        stage=stage,
        modelo=modelo,
        ejercicio=ejercicio,
    )


def declarations_page_shape_context(
    html: str,
    *,
    landing_url: str,
    stage: str,
    modelo: str | None = None,
    ejercicio: int | None = None,
) -> dict[str, object]:
    """Project one register page's observable shape into a diagnostic context.

    ``modelo`` and ``ejercicio`` are optional because the availability reader
    navigates the same form with no pair in hand. They are reported as ``None``
    rather than as a placeholder, so a diagnostic never states a pair the caller
    was not querying.
    """
    from bs4 import Tag

    soup = parse_html(html)
    normalized_text = normalize_response_text(soup.get_text(" ", strip=True))
    buttons = tuple(bounded_text(button.get_text(" ", strip=True)) for button in soup.find_all("button")[:12])
    headers = tuple(
        bounded_text(header.get_text(" ", strip=True))
        for header in soup.find_all(class_=_has_class("z-listheader"))[:12]
    )
    _title_tag = soup.find("title")
    _title_text = bounded_text(_title_tag.get_text(" ", strip=True)) if isinstance(_title_tag, Tag) else ""
    return {
        "stage": stage,
        "modelo": modelo,
        "ejercicio": ejercicio,
        "landing_url": redacted_url(landing_url),
        "title": _title_text,
        "has_modelo_label": "modelo (*)" in normalized_text,
        "has_ejercicio_label": "ejercicio (*)" in normalized_text,
        "has_buscar_button": any(button.casefold() == "buscar" for button in buttons),
        "has_no_results_text": normalize_response_text(NO_RESULTS_TEXT) in normalized_text,
        "listbox_count": len(soup.find_all(class_=_has_class("z-listbox"))),
        "listitem_count": len(soup.find_all(class_=_has_class("z-listitem"))),
        "comboitem_count": len(soup.find_all(class_=_has_class("z-comboitem"))),
        "table_count": len(soup.find_all("table")),
        "form_count": len(soup.find_all("form")),
        "buttons": buttons,
        "list_headers": headers,
        "raw_sha256": sha256_hex(html.encode("utf-8")),
    }


__all__ = [
    "declarations_page_shape_context",
    "declarations_page_shape_context_from_page",
]
