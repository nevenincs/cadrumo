"""Shared private helpers for AEAT sede browser drivers.

Hosts the small text-normalisation, error-formatting, and selector-probe
helpers consumed by every sede driver. Drivers (``_groi_check``,
``_nif_iva_check``, future siblings) inject their own surface label and
shape-change suggestion so the helper output remains diagnostic without
re-implementing the same logic per driver.

:func:`make_locate_helper` and :func:`assert_query_browser_action_for` factor
out the two private helper shapes that each checker driver used to duplicate.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping
from re import compile
from typing import TYPE_CHECKING, Any, Literal, Protocol
from unicodedata import category, normalize
from urllib.parse import urlsplit

from .....core import STRICT_FROZEN_CONFIG
from .....core import is_aeat_csv as _core_is_aeat_csv
from .....core.config import Settings
from .....core.external_constants import PDF_MIME_TYPE

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

from pydantic import BaseModel

from .....core.logging import get_logger
from .....domain.calculations.registry import RemoteOperation, RemoteStateGuardPolicy, assert_remote_operation_allowed
from .._playwright import PlaywrightError, PlaywrightTimeoutError
from ._errors import BrowserAdapterTypeError, JustificanteFetchError, SedeFailureMode, SedeParseError

_log = get_logger(__name__)
_WHITESPACE_RE = compile(r"\s+")
_EXTERNAL = Settings.external_constants()


def is_aeat_csv(value: str) -> bool:
    """Return whether ``value`` is one complete AEAT CSV identifier.

    Delegates to the canonical :func:`core.is_aeat_csv` contract so the sede
    adapters, the inbound justificante extractor, and the public verifier
    cannot drift on what width AEAT actually issues. Re-exported here because
    the sede modules already import their shape helpers from this module.
    """
    return _core_is_aeat_csv(value)


def is_aeat_auth_gate_redirect(current_url: str) -> bool:
    """Return whether ``current_url`` is AEAT's configured auth-gate landing.

    The detector accepts the configured AEAT host or a real subdomain, but not
    a user-info or port-shaped authority that merely ends in that suffix.
    Callers retain responsibility for translating an affirmative result into
    their surface-specific navigation error.
    """
    if not current_url:
        return False
    try:
        parsed = urlsplit(current_url)
        if parsed.username is not None or parsed.password is not None or parsed.port is not None:
            return False
    except ValueError:
        return False
    host = parsed.hostname
    if host is None:
        return False
    host_suffix = _EXTERNAL.aeat.domains.host_suffix.casefold()
    if host.casefold() != host_suffix and not host.casefold().endswith(f".{host_suffix}"):
        return False
    return _EXTERNAL.aeat.sede_paths.auth_gate_4033.casefold() in parsed.path.casefold()


class _LocateHelper(Protocol):
    """Callable protocol for the ``_locate`` helper produced by :func:`make_locate_helper`.

    Both ``_groi_check`` and ``_nif_iva_check`` previously defined this Protocol
    locally; it is canonical here so drivers import one shared definition.

    Parameters are positional-only to match the
    ``Callable[[Page, tuple[str, ...], str, str, int], Coroutine[Any, Any, Locator]]``
    return annotation on :func:`make_locate_helper`.
    """

    def __call__(
        self,
        page: Page,
        selectors: tuple[str, ...],
        stage: str,
        description: str,
        timeout_ms: int,
        /,
    ) -> Coroutine[Any, Any, Locator]: ...


class _SedeCheckerModel(BaseModel):
    """Strict frozen base for sede checker observation and result models.

    Every per-NIF observation type and aggregate result type in the sede
    browser drivers (``_groi_check``, ``_nif_iva_check``, future siblings)
    inherits this base to guarantee a consistent strict-frozen-forbid Pydantic
    config across all checker surfaces without repeating the ``model_config``
    declaration in each module.
    """

    model_config = STRICT_FROZEN_CONFIG


def assert_query_browser_action_for(policy: RemoteStateGuardPolicy, action: str) -> None:
    """Assert that ``action`` is permitted under ``policy``.

    Raises :class:`~domain.calculations.registry.RegistryValidationError`
    via :func:`~domain.calculations.registry.assert_remote_operation_allowed`
    if the action pattern is not allowed. Both the GROI and NIF-IVA drivers close
    over their own :class:`~domain.calculations.registry.RemoteStateGuardPolicy`
    objects; this shared helper removes the duplicate ``_assert_query_browser_action``
    bodies they used to carry.

    Args:
        policy: The guard policy the driver was initialised with.
        action: Browser action label to validate (e.g. ``"open-groi-form"``).
    """
    assert_remote_operation_allowed(policy, RemoteOperation(kind="browser_action", action=action))


def require_playwright_page(raw_page: object) -> Page:
    """Return ``raw_page`` as a Playwright ``Page`` or raise a typed adapter error."""
    from playwright.async_api import Page as _Page

    if not isinstance(raw_page, _Page):
        raise BrowserAdapterTypeError(
            f"BrowserContext.new_page() did not return a Playwright Page; got {type(raw_page)}",
            context={"actual_type": type(raw_page).__name__},
        )
    return raw_page


def make_locate_helper(
    surface_label: str,
    shape_suggestion: str,
) -> Callable[[Page, tuple[str, ...], str, str, int], Coroutine[Any, Any, Locator]]:
    """Return a ``_locate`` coroutine pre-bound to ``surface_label`` and ``shape_suggestion``.

    Both the GROI and NIF-IVA drivers wrap :func:`first_visible_locator` with the
    same body, differing only in the ``surface_label`` and ``shape_suggestion``
    strings they inject. This factory eliminates that duplicate; each driver calls::

        _locate = make_locate_helper("GROI", _groi_shape_suggestion())

    and then uses ``_locate(page, selectors, stage=..., description=..., timeout_ms=...)``
    directly.

    Args:
        surface_label: Sede surface name for log and error messages.
        shape_suggestion: Localised guidance string appended to
            :class:`~._errors.SedeParseError` when all selectors fail.

    Returns:
        An async callable with the same signature as the internal ``_locate``
        helpers the drivers previously defined individually.
    """
    from ._browser_constants import selector_probe_timeout_ms  # local import to avoid circular

    async def _locate(
        page: Page,
        selectors: tuple[str, ...],
        stage: str,
        description: str,
        timeout_ms: int,
    ) -> Locator:
        return await first_visible_locator(
            page,
            selectors,
            stage=stage,
            description=description,
            timeout_ms=timeout_ms,
            probe_timeout_ms=selector_probe_timeout_ms(),
            surface_label=surface_label,
            shape_suggestion=shape_suggestion,
        )

    return _locate


def response_media_type(content_type: str) -> str:
    """Return the bare media type from a ``Content-Type`` header value.

    Strips any parameter tail (``; charset=binary``), surrounding whitespace,
    and case, so a header may carry parameters without changing what media
    type it names.
    """
    return content_type.split(";", 1)[0].strip().lower()


def assert_pdf_response(
    *,
    status: int,
    content_type: str,
    body: bytes,
    subject: str,
) -> None:
    """Validate one AEAT PDF download response, or raise.

    The single contract every sede PDF capture path shares: a 2xx status, a
    non-empty body, and a ``Content-Type`` whose media type IS
    :data:`~core.external_constants.PDF_MIME_TYPE`.

    The media-type comparison is equality on the parameter-stripped header
    rather than a substring test. A substring test admits any type that merely
    CONTAINS the token: ``application/notpdf`` and ``text/pdf`` satisfy
    ``"pdf" in ...``, and ``x-application/pdf-trap`` satisfies even
    ``"application/pdf" in ...``. None of those is a PDF, and a captured
    artefact is stored as filing evidence, so admitting one records a non-PDF
    body under a PDF ``kind``. Equality on the media type still admits the
    parameterised ``application/pdf; charset=binary`` AEAT actually sends.

    Args:
        status: HTTP status code of the PDF response.
        content_type: Raw ``Content-Type`` header value, possibly parameterised.
        body: Raw response body bytes.
        subject: Caller-supplied identification of what was fetched, embedded
            verbatim in the failure message (e.g. ``"CSV='ABC123'"``) so each
            capture path keeps its own diagnostic handle.

    Raises:
        JustificanteFetchError: On a non-2xx status, an empty body, or a
            content type whose media type is not ``application/pdf``.
    """
    if not (200 <= status < 300):
        raise JustificanteFetchError(f"pdf fetch for {subject} returned HTTP {status}")
    if not body:
        raise JustificanteFetchError(f"empty PDF body for {subject}")
    if response_media_type(content_type) != PDF_MIME_TYPE:
        raise JustificanteFetchError(f"unexpected content-type {content_type!r} for {subject}")


def normalize_response_text(text: str) -> str:
    """Casefold + strip diacritics + collapse whitespace for marker matching."""
    if not text:
        return ""
    decomposed = normalize("NFKD", text)
    without_accents = "".join(ch for ch in decomposed if category(ch) != "Mn")
    return _WHITESPACE_RE.sub(" ", without_accents.casefold()).strip()


SPANISH_NEGATIVE_VERDICT_MARKERS: tuple[str, ...] = (
    "no consta",
    "no valido",
    "no es valido",
    "no es un nif valido",
    "el campo nif no es un nif valido",
    "no identificado",
    "no esta identificado",
    "no se encuentra identificado",
    "operador no identificado",
    "invalid",
)
"""Normalised AEAT phrases that reject an identity, shared by every checker.

Every sede identity checker reads the same Spanish rejection vocabulary off
the same AEAT template family, so the negative table is one contract rather
than a per-driver table. It is deliberately the union of the phrases observed
across the checkers: a driver that omits one classifies an explicit rejection
as ``unknown`` at best, and -- when a generic ``valido`` substring survives in
its positive table -- as ``valid``, turning a refusal into a false pass.

Markers are matched against :func:`normalize_response_text` output, so they
are casefolded, unaccented, and whitespace-collapsed.
"""


type SedeVerdict = Literal["valid", "invalid", "unknown"]
"""Closed verdict vocabulary every sede identity checker reports."""


def extract_marker_verdict(
    body_text: str,
    *,
    positive_markers: tuple[str, ...],
    negative_markers: tuple[str, ...] = SPANISH_NEGATIVE_VERDICT_MARKERS,
) -> SedeVerdict:
    """Classify an AEAT response body as ``valid``, ``invalid``, or ``unknown``.

    Negative markers are tested first and win outright. AEAT phrases a
    rejection by negating the same word it uses to affirm (``no es un NIF
    válido``), so a positive-first or negative-incomplete parser reads an
    explicit refusal as a pass. Precedence, not marker richness, is what makes
    the classification safe.

    Args:
        body_text: Raw response body text scraped from the AEAT page.
        positive_markers: Driver-specific phrases that affirm the identity.
            Positive vocabulary is surface-specific (a GROI registration
            phrase does not affirm a VIES NIF-IVA), so it stays per driver.
        negative_markers: Rejection phrases; defaults to the shared
            :data:`SPANISH_NEGATIVE_VERDICT_MARKERS` contract.

    Returns:
        ``"invalid"`` on any negative marker, ``"valid"`` on any positive
        marker, ``"unknown"`` for empty or structurally unanswerable text.
    """
    normalized = normalize_response_text(body_text)
    if not normalized:
        return "unknown"
    if any(marker in normalized for marker in negative_markers):
        return "invalid"
    if any(marker in normalized for marker in positive_markers):
        return "valid"
    return "unknown"


def registry_failure_message(exc: BaseException) -> str:
    """Build a registry-facing error string enriched with the failure_mode context field.

    Sede driver exceptions carry a ``context`` mapping; this helper
    extracts ``failure_mode`` (falling back to a ``site_health:<state>``
    label when only a ``state`` key is present) and appends it to the
    base ``str(exc)`` so callers wrapping the exception into a
    :class:`RegistryValidationError` preserve the diagnostic context.
    Returns ``str(exc)`` unchanged when no ``failure_mode`` is derivable.
    """
    context = getattr(exc, "context", None)
    if not isinstance(context, Mapping) or not context:
        return str(exc)
    failure_mode = context.get("failure_mode")
    if failure_mode is None and "state" in context:
        failure_mode = f"site_health:{context['state']}"
    if failure_mode is None:
        return str(exc)
    return f"{exc} (failure_mode={failure_mode})"


async def first_visible_locator(
    page: Page,
    selectors: tuple[str, ...],
    *,
    stage: str,
    description: str,
    timeout_ms: int,
    probe_timeout_ms: int,
    surface_label: str,
    shape_suggestion: str,
) -> Locator:
    """Return the first selector in ``selectors`` that resolves to a visible element.

    Probes each selector in order using a short ``probe_timeout_ms``
    deadline. If a selector is not visible within that window,
    ``PlaywrightError`` / ``PlaywrightTimeoutError`` is caught and the
    next selector is tried. When no selector resolves,
    :class:`SedeParseError` is raised with
    ``SedeFailureMode.EXTERNAL_SHAPE_CHANGED`` so callers can distinguish
    "AEAT changed the page layout" from transient network timeouts.

    Args:
        page: Playwright ``Page`` on which to probe the selectors.
        selectors: CSS selector strings tried in declaration order.
        stage: Opaque label for the current driver stage, included in
            the error context.
        description: Human-readable description of the expected element,
            used in the error message.
        timeout_ms: Overall operation timeout (ms); ``probe_timeout_ms``
            is capped to this value.
        probe_timeout_ms: Per-selector visibility probe budget (ms).
        surface_label: Sede surface name included in log and error
            messages (e.g. ``"GROI"``).
        shape_suggestion: Localised guidance string appended to
            :class:`SedeParseError` when all selectors fail.

    Returns:
        The first ``Locator`` from ``selectors`` whose element was
        visible within ``probe_timeout_ms``.

    Raises:
        SedeParseError: When every selector probe timed out or failed.
    """
    probe_timeout = min(timeout_ms, probe_timeout_ms)
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=probe_timeout)
        except (PlaywrightError, PlaywrightTimeoutError) as probe_exc:
            _log.debug(
                "%s: selector %r not visible during probe (%s); trying next",
                surface_label,
                selector,
                probe_exc,
            )
            continue
        return locator
    raise SedeParseError(
        f"{surface_label} expected page element was not visible: {description}",
        failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
        context={"stage": stage, "expected": description, "timeout_ms": timeout_ms},
        suggestion=shape_suggestion,
    )


def nif_check_operation_tail(expected: Mapping[str, object]) -> tuple[RemoteOperation, ...]:
    """Build the shared per-NIF check + discard-session operation tail.

    Both the GROI and NIF/IVA sede drivers close their planned-operation
    sequence identically: one ``check-nif-<NIF>`` browser action per declared
    NIF (normalised to upper-case and sorted so the operation labels the
    remote-state guard pre-flight sees on the driverless oracle path match what
    the live driver emits), followed by one ``discard-session`` action. Each
    driver prepends its own URL/form prologue and appends this tail.
    """
    tail: list[RemoteOperation] = [
        RemoteOperation(kind="browser_action", action=f"check-nif-{nif}")
        for nif in sorted(str(key).strip().upper() for key in expected)
    ]
    tail.append(RemoteOperation(kind="browser_action", action="discard-session"))
    return tuple(tail)


__all__ = [
    "SPANISH_NEGATIVE_VERDICT_MARKERS",
    "SedeVerdict",
    "_LocateHelper",
    "_SedeCheckerModel",
    "assert_pdf_response",
    "assert_query_browser_action_for",
    "extract_marker_verdict",
    "first_visible_locator",
    "make_locate_helper",
    "nif_check_operation_tail",
    "normalize_response_text",
    "registry_failure_message",
    "require_playwright_page",
    "response_media_type",
]
