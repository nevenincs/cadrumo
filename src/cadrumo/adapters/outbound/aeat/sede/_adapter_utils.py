"""Shared private helpers for AEAT sede browser drivers.

Hosts the small text-normalisation, error-formatting, and selector-probe
helpers consumed by every sede driver. Drivers (``_groi_check``,
``_nif_iva_check``, future siblings) inject their own surface label and
share one factual shape-change failure without re-implementing the same
logic per driver.

:func:`make_locate_helper` and :func:`assert_query_browser_action_for` factor
out the two private helper shapes that each checker driver used to duplicate.

:func:`assert_read_landing` is the package's landing refusal: the one wall
that sees where AEAT actually dispatched a read, rather than where the driver
asked to go. Every driver that fills a form and clicks a control needs it,
because the click issues a browser form POST that the first-party HTTP guard
never sees and that the forbidden-verb source scan deliberately permits.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping
from re import compile
from typing import TYPE_CHECKING, Any, Literal, Protocol
from urllib.parse import urlsplit

from .....core.config import Settings
from .....core.external_constants import PDF_MIME_TYPE
from .....core.i18n import tr
from .....core.identity import tax_id_identity_token
from .....core.models import STRICT_FROZEN_CONFIG
from .....core.text_fold import fold_diacritics

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

from pydantic import AnyUrl, BaseModel
from pydantic import ValidationError as PydanticValidationError

from .....core.logging import get_logger
from .....core.type_guards import is_str_keyed_dict
from .....domain.calculations.registry.errors import RegistryValidationError
from .....domain.calculations.registry.remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
)
from .._playwright import PlaywrightError, PlaywrightTimeoutError
from .errors import (
    BrowserAdapterTypeError,
    JustificanteFetchError,
    SedeFailureMode,
    SedeNavigationError,
    SedeParseError,
)

_log = get_logger(__name__)
_WHITESPACE_RE = compile(r"\s+")
EXTERNAL = Settings.external_constants()


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
    host_suffix = EXTERNAL.aeat.domains.host_suffix.casefold()
    if host.casefold() != host_suffix and not host.casefold().endswith(f".{host_suffix}"):
        return False
    return EXTERNAL.aeat.sede_paths.auth_gate_4033.casefold() in parsed.path.casefold()


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


def assert_read_http_for(policy: RemoteStateGuardPolicy, method: str, url: str) -> None:
    """Assert that a wire-crossing read of ``url`` is permitted under ``policy``.

    The ``http`` counterpart of :func:`assert_query_browser_action_for`, and the
    one body behind every sede reader's fail-closed no-write guard. The censal,
    notifications and expedientes-walker readers each carried an identical copy
    differing only in the module-level policy it named; each still declares its
    OWN policy — the surfaces genuinely differ in which hosts they admit — and
    passes it here, so the refusal RULE has one home while the per-surface
    posture stays local.

    A guard that refuses writes is the wrong thing to hold three copies of: a
    correction applied to one leaves the other two admitting what it now
    refuses, and nothing fails until a write reaches AEAT.

    Args:
        policy: The read policy the calling surface declared.
        method: HTTP method of the navigation about to be made.
        url: Absolute target URL.

    Raises:
        RegistryValidationError: The navigation is not a permitted read.
    """
    assert_remote_operation_allowed(policy, RemoteOperation(kind="http", method=method, url=AnyUrl(url)))


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
) -> Callable[[Page, tuple[str, ...], str, str, int], Coroutine[Any, Any, Locator]]:
    """Return a ``_locate`` coroutine pre-bound to ``surface_label``.

    Both the GROI and NIF-IVA drivers wrap :func:`first_visible_locator` with the
    same body, differing only in the ``surface_label`` they inject. This factory
    eliminates that duplicate; each driver calls::

        _locate = make_locate_helper("GROI")

    and then uses ``_locate(page, selectors, stage=..., description=..., timeout_ms=...)``
    directly.

    Args:
        surface_label: Sede surface name for log and error messages.

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
        )

    return _locate


def landed_origin(landed_url: str | None) -> str | None:
    """Return the ``scheme://host`` a read actually landed on, or ``None``.

    The single extraction every sede reader uses to answer "which host
    answered this read". Returns ``None`` when the landing carries no usable
    scheme and host -- an empty or absent ``page.url``, ``about:blank``, or a
    relative path -- leaving the REFUSAL to the caller, which is the only
    layer that knows what its surface is allowed to do with the absence.

    Callers must not substitute a constructed origin for a ``None`` result.
    A recorded URL is a claim about where a read happened, and a read whose
    host cannot be established has no such claim to make.
    """
    if not landed_url:
        return None
    landed = urlsplit(landed_url)
    if not landed.scheme or not landed.netloc:
        return None
    return f"{landed.scheme}://{landed.netloc}"


def assert_read_landing(
    landing_url: str | None,
    *,
    surface: str,
    policy: RemoteStateGuardPolicy,
    allowed_path_prefixes: tuple[str, ...],
) -> None:
    """Refuse a landing that is not one of a read surface's declared read pages.

    The landing refusal is the only wall that sees where AEAT actually
    DISPATCHED. The sibling walls each miss a browser-driven navigation by
    construction: the package's forbidden-verb source scan deliberately
    permits ``click`` / ``fill`` / ``press``, and the HTTP guard is consulted
    only for a first-party request, never for the form POST a click issues.
    A driver that fills a form and clicks a control therefore has no
    mechanism telling it where it ended up unless it calls this.

    The rule is an ALLOW-list, not a denylist, and it fails closed at every
    step: a landing with no readable origin is refused, a landing the
    surface's own guard policy does not admit is refused, a surface that
    declares no read pages refuses everything, and a landing outside the
    declared pages is refused. An unrecognised landing is a refusal — the
    guard never has to enumerate the write surfaces it has not seen, which
    is what a denylist has to get exhaustively right.

    Routing the landed URL through ``policy`` is deliberate rather than
    redundant: that evaluation carries the canonical AEAT write-verb token
    scan (``presentar``, ``firmar``, ``pagar``, ``submit`` and the rest) and
    the authority checks that refuse a credentialed, off-port or off-host
    landing. What it CANNOT see is an AEAT write path whose URL contains no
    write verb at all — ``BUGC-JDIT/ModifDomiDual`` and
    ``BU36-ASIS/M036/index.zul`` are both writes and neither carries a token
    the scan knows. The path allow-list is what closes that half, so the two
    checks are complementary and both are required.

    The censal reader (:mod:`._censal_datos`) keeps its own marker-keyed
    refusal in addition to this one. Its consulta page and its modification
    siblings are reached through the same launcher, so it names the write
    paths outright; that predicate is exported for conformance gates and is
    not superseded here.

    Args:
        landing_url: The URL AEAT actually served, after redirects — read
            off the page, never the URL that was requested.
        surface: Sede surface label used in the refusal message and context
            (e.g. ``"GROI"``), so a refusal names which driver refused.
        policy: The surface's own remote-state guard policy.
        allowed_path_prefixes: Absolute path prefixes this surface is
            allowed to land on. Empty refuses every landing.

    Raises:
        SedeNavigationError: When the landing is unreadable, off-policy, or
            outside the surface's declared read pages.
    """
    origin = landed_origin(landing_url)
    if origin is None:
        raise SedeNavigationError(
            f"{surface} landed on no usable origin, so where AEAT dispatched this read cannot be "
            "established; the read is refused rather than assumed to have stayed on a read page",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            translated_message=tr("adapters.sede.errors.landing_unreadable"),
            context={"surface": surface, "landing_url": landing_url or "<empty>"},
        )
    raw_landing = landing_url or ""
    try:
        assert_remote_operation_allowed(
            policy,
            RemoteOperation(kind="http", method="GET", url=raw_landing),
        )
    except (RegistryValidationError, PydanticValidationError) as exc:
        # A landing that is not a well-formed absolute URL is refused here
        # rather than allowed to leak a pydantic error out of the adapter
        # boundary. The origin gate above already rejects every relative and
        # authority-less form, so this arm is insurance against a shape it
        # does not anticipate -- and insurance that REFUSES, not one that
        # degrades to a pass.
        raise SedeNavigationError(
            f"{surface} landing was refused by its own read guard policy: {exc}",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            translated_message=tr("adapters.sede.errors.landing_off_policy"),
            context={"surface": surface, "landing_url": raw_landing, "policy_id": policy.id},
        ) from exc
    landed_path = urlsplit(raw_landing).path
    folded_path = landed_path.casefold()
    if not any(folded_path.startswith(prefix.casefold()) for prefix in allowed_path_prefixes):
        raise SedeNavigationError(
            f"{surface} landed outside its declared read pages and was refused; this driver reads "
            f"only and never reaches an AEAT write path. landed_path={landed_path!r}",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            translated_message=tr("adapters.sede.errors.landing_off_read_pages"),
            context={
                "surface": surface,
                "landing_url": raw_landing,
                "landed_path": landed_path,
                "allowed_path_prefixes": allowed_path_prefixes,
            },
        )


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
    CONTAINS the token: ``application/notpdf`` and ``text/pdf`` satisfy a
    ``pdf in ...`` substring check, and ``x-application/pdf-trap`` satisfies
    even a substring check against :data:`~core.external_constants.PDF_MIME_TYPE`
    itself. None of those is a PDF, and a captured artefact is stored as
    filing evidence, so admitting one records a non-PDF body under a PDF
    ``kind``. Equality on the media type still admits the parameterised
    ``application/pdf; charset=binary`` AEAT actually sends.

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
    without_accents = fold_diacritics(text)
    return _WHITESPACE_RE.sub(" ", without_accents.casefold()).strip()


def normalize_display_text(text: str) -> str:
    """Collapse a page value's whitespace while keeping it readable as printed.

    The sibling of :func:`normalize_response_text` for the other half of the
    job: that one casefolds and folds diacritics so a marker can be MATCHED,
    which makes its output unfit to show or store. This one only tidies the
    spacing — AEAT pages lay values out with non-breaking spaces and wrapped
    indentation — so ``"Cuota Disponible"`` survives as written rather than
    arriving as ``"cuota disponible"``.

    Reach for this whenever the normalised text is the VALUE; reach for
    :func:`normalize_response_text` only when it is a lookup key.
    """
    return " ".join(text.replace("\xa0", " ").split())


def cell_text(cells: list[str], index: int | None) -> str | None:
    """Return the cell at ``index``, or ``None`` when it is absent or empty.

    One concept that was implemented twice, five lines apart in shape: the
    declaraciones listbox parser's ``_cell_text`` and the notifications table
    parser's ``_safe_cell``. They read as divergent because one stripped and one
    did not, but both callers build their cell lists with
    ``get_text(" ", strip=True)``, so the strip was a no-op and the two were
    functionally identical on every real input.

    The strip is KEPT rather than dropped as dead. "Absent or empty" is this
    helper's contract, and an implementation that only satisfies it while every
    caller happens to pre-strip is coupled to an invariant stated nowhere. It
    costs nothing and it means the contract holds for a caller that arrives
    later without that habit.

    A missing index and an empty cell collapse to the same ``None`` on purpose:
    AEAT tables omit a column and blank it interchangeably, and no caller
    distinguishes them.
    """
    if index is None or index >= len(cells):
        return None
    return cells[index].strip() or None


def bounded_text(value: object, *, max_length: int = 120) -> str:
    """Return ``value`` as tidy text, truncated to at most ``max_length`` characters.

    What a page-shape diagnostic records for an attribute it does not interpret,
    so a pathological page cannot put an unbounded string into a dump file or an
    error context.

    The ellipsis is one character rather than three dots for an arithmetic
    reason: the truncation keeps ``max_length - 1`` characters, so a one-character
    marker lands exactly on the bound while ``"..."`` overshoots it by two. The
    wallet and declarations shape readers each carried a copy of this and had
    already drifted onto different markers, which is how the overshooting one
    survived.
    """
    text = normalize_display_text(str(value))
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1]}…"


def redacted_url(value: object) -> str | None:
    """Return ``value`` with its query string and fragment removed.

    Everything identifying rides in the query on a sede URL — the NIF, the
    expediente reference, the session token — so a URL bound for a log line, an
    error context or a diagnostic dump goes through here first. Scheme, host and
    path survive, which is what makes the record diagnosable.

    Distinct from ``application.auth`` ``_redacted_url_summary``, which keeps the
    query KEY names and drops the scheme; that one answers "which parameters did
    this request carry", not "where did it go".
    """
    if value is None:
        return None
    text = str(value)
    if not text:
        return ""
    try:
        parsed = urlsplit(text)
    except ValueError:
        return ""
    if not parsed.scheme and not parsed.netloc:
        return parsed.path
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


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
    if not is_str_keyed_dict(context) or not context:
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
        for nif in sorted(tax_id_identity_token(str(key)) for key in expected)
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
    "assert_read_http_for",
    "assert_read_landing",
    "bounded_text",
    "cell_text",
    "extract_marker_verdict",
    "first_visible_locator",
    "landed_origin",
    "make_locate_helper",
    "nif_check_operation_tail",
    "normalize_display_text",
    "normalize_response_text",
    "redacted_url",
    "registry_failure_message",
    "require_playwright_page",
    "response_media_type",
]
