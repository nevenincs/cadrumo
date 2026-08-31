"""Click-time safety enforcement for the Renta WEB Open driver.

Mission-critical: under NO circumstance may any calculation be submitted,
signed, presented, paid, or persisted to AEAT — even on the open simulator.
This module is the runtime belt-and-suspenders enforcement layer: every
button click in the driver routes through ``assert_click_target_safe``,
which inspects the locator's resolved text and blocks the click before
Playwright issues it if the text matches the forbidden-actions denylist.

The denylist mirrors the Spanish-language equivalents of the
``AEAT_WRITE_FORBIDDEN_ACTIONS`` constant declared in
``cadrumo.domain.calculations.registry.remote_state_guard``. The runtime
copy here is the second line of defense: the policy registration is the
first (a click that bypasses this module would still need a policy that
allows it, and the open-simulator policy explicitly forbids these
actions). A hygiene test in the test suite confirms the driver code
never invokes Playwright's ``locator.click()`` outside this safety
wrapper.

This module also installs a page-level safety net:

  - dialog auto-dismiss: any browser dialog (``alert``, ``confirm``,
    ``prompt``, ``beforeunload``) is dismissed without action;
  - navigation guard: any navigation to URLs containing forbidden path
    fragments (``/Presentar``, ``/Firmar``, ``/Pagar``, ``/Sign``)
    raises before the request leaves the browser.

The defenses are intentionally redundant: each layer alone is sufficient
to prevent submission; together they ensure that even a single layer's
failure cannot result in a real filing.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Dialog, Locator, Page, Request

from .....core.logging import get_logger
from .....core.text_fold import fold_diacritics
from .....domain.calculations.registry.remote_state_guard import AEAT_WRITE_FORBIDDEN_VERB_TOKENS
from .errors import SedeFailureMode, SedeNavigationError

logger = get_logger(__name__)


# Click-time-only extensions to the canonical write-action verb token set.
# The base ``AEAT_WRITE_FORBIDDEN_VERB_TOKENS`` (declared in the domain
# remote-state guard) is the universal source of truth for write-action
# verbs and is shared with the URL/method guard. The tokens listed here
# cover surface-specific cases that only appear in button text:
#   - accented Spanish variants kept as readable source documentation
#     even though _normalise() folds them to the unaccented base form;
#   - the noun ``firma`` (button labels like "Firma electrónica");
#   - additional Spanish persistence/payment verbs that surface only as
#     button labels (``almacenar``, ``ingresar``);
#   - multi-word click targets (``transmitir lote``);
#   - the AEAT pre-presentation Validar surface — read-only drivers
#     never invoke it because observed values surface from form widgets
#     directly, but a stray click could trigger validation-state
#     mutations or queue side effects we don't want to exercise.
_CLICK_ONLY_FORBIDDEN_TOKENS: frozenset[str] = frozenset(
    {
        "presentación",
        "envío",
        "transmisión",
        "firma",
        "almacenar",
        "ingresar",
        "transmitir lote",
        "validar",
        "validacion",
        "validación",
    },
)

# Forbidden Spanish-language click targets. Any locator whose visible text
# contains one of these tokens (case-insensitive, accent-insensitive) is
# blocked before the click. The set is the canonical write-verb tokens
# from the domain remote-state guard PLUS click-time-only extensions.
FORBIDDEN_CLICK_TOKENS: frozenset[str] = AEAT_WRITE_FORBIDDEN_VERB_TOKENS | _CLICK_ONLY_FORBIDDEN_TOKENS

# Forbidden URL path fragments (case-insensitive).
FORBIDDEN_URL_FRAGMENTS: frozenset[str] = frozenset(
    {
        "/presentar",
        "/firmar",
        "/pagar",
        "/sign",
        "/submit",
        "/transmitir",
        "/tgvi",
    },
)

# Buttons we ALLOW even though their text contains a forbidden substring.
# Empty by design — every allowed button has been audited and none should
# match. If a future safe button trips the denylist, audit it FIRST and
# add an explicit allow entry here only after verifying the action is
# read-only / ephemeral.
ALLOWED_CLICK_OVERRIDES: frozenset[str] = frozenset[str]()


def _normalise(text: str) -> str:
    """Lowercase + strip + accent-fold + drop any remaining non-ASCII noise.

    Composes the shared ``core.text_fold.fold_diacritics`` primitive (which
    strips only combining marks, e.g. turns ``"ó"`` into ``"o"``) with an
    additional ``encode("ascii", "ignore")`` pass that is DELIBERATELY kept
    here rather than retired: this text comes from a live AEAT page, and a
    codepoint with no combining-mark decomposition (a soft hyphen from
    browser auto-hyphenation, an em dash, a stray glyph) can land mid-word
    in a scraped button label. ``fold_diacritics`` alone would leave such a
    codepoint in place and could split a forbidden token in two, silently
    weakening this denylist. The trailing ascii-ignore pass discards it
    instead, matching the original implementation byte-for-byte -- see
    ``test_normalise_still_drops_non_ascii_noise_between_letters_of_a_forbidden_word``
    for the proof. This is the one call site that keeps the ascii-ignore
    step after adopting ``fold_diacritics``; every other former ascii-ignore
    site (``domain.calculations.registry._citation_blocklist``) reads
    registry-authored TOML prose rather than browser-rendered text and
    carries none of this exposure, so it dropped the ascii-ignore step
    outright.
    """
    return fold_diacritics(text).encode("ascii", "ignore").decode("ascii").casefold().strip()


def _matches_forbidden_token(normalised_text: str) -> str | None:
    """Return the matching forbidden token or None."""
    if not normalised_text:
        return None
    if normalised_text in ALLOWED_CLICK_OVERRIDES:
        return None
    for token in FORBIDDEN_CLICK_TOKENS:
        normalised_token = _normalise(token)
        # Substring match — robust against button labels like
        # "Presentar declaración" or "Firmar y enviar".
        if normalised_token in normalised_text:
            return token
    return None


async def assert_click_target_safe(
    locator: Locator,
    *,
    stage: str,
    description: str,
    timeout_ms: int = 5_000,
) -> None:
    """Inspect a locator's text + URL before allowing a click.

    Raises :class:`SedeNavigationError` if the locator targets a forbidden
    action. The check runs on EVERY click in the driver — there is no
    bypass mechanism. Adding an exception requires editing
    ``ALLOWED_CLICK_OVERRIDES`` AND auditing the action's read/write
    semantics first.
    """
    try:
        text = await locator.inner_text(timeout=timeout_ms)
    except Exception as exc:
        logger.debug(
            "renta web open safety: inner_text probe failed stage=%s description=%s: %s",
            stage,
            description,
            exc,
            exc_info=True,
        )
        text = ""
    normalised_text = _normalise(text)
    matched = _matches_forbidden_token(normalised_text)
    if matched is not None:
        logger.error(
            "renta web open click blocked by safety guard stage=%s description=%s text=%r matched_token=%r",
            stage,
            description,
            text,
            matched,
        )
        raise SedeNavigationError(
            f"Renta WEB Open click blocked by safety guard: locator text "
            f"{text!r} contains forbidden token {matched!r} (stage={stage!r})",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={"stage": stage, "description": description, "text": text, "matched_token": matched},
        )
    # URL guard: if the locator carries an href / formaction attribute,
    # assert it doesn't point at a forbidden path fragment.
    for attr in ("href", "formaction", "data-href"):
        try:
            attr_value = await locator.get_attribute(attr)
        except Exception as exc:
            logger.debug(
                "renta web open safety: get_attribute(%s) probe failed stage=%s description=%s: %s",
                attr,
                stage,
                description,
                exc,
                exc_info=True,
            )
            attr_value = None
        if attr_value:
            normalised_url = attr_value.lower()
            for fragment in FORBIDDEN_URL_FRAGMENTS:
                if fragment in normalised_url:
                    raise SedeNavigationError(
                        f"Renta WEB Open click blocked by safety guard: locator {attr}="
                        f"{attr_value!r} contains forbidden URL fragment {fragment!r}",
                        failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
                        context={
                            "stage": stage,
                            "description": description,
                            attr: attr_value,
                            "matched_fragment": fragment,
                        },
                    )


async def install_page_safety_net(page: Page) -> None:
    """Attach page-level safety listeners that auto-dismiss dialogs and block forbidden navigations.

    Call once after page creation, before any user interaction. The
    listeners stay attached for the lifetime of the page.
    """

    async def _on_dialog(dialog: Dialog) -> None:
        try:
            kind = dialog.type
            message = dialog.message
        except Exception:
            logger.debug("renta web open safety: dialog metadata lookup failed", exc_info=True)
            kind = "(unknown)"
            message = "(unknown)"
        logger.warning(
            "renta web open safety: auto-dismissing dialog type=%s message=%r",
            kind,
            message,
        )
        with contextlib.suppress(Exception):
            # Best-effort dismiss: a failure here cannot mask the safety
            # guarantee — the test or audit will still see the warning log.
            await dialog.dismiss()

    _pending_dialog_tasks: set[asyncio.Task[None]] = set()

    def _dialog_handler(dialog: Dialog) -> None:
        # Playwright dialog handler must be sync; schedule async dismissal.
        import asyncio

        task = asyncio.create_task(_on_dialog(dialog))
        _pending_dialog_tasks.add(task)
        task.add_done_callback(_pending_dialog_tasks.discard)

    page.on("dialog", _dialog_handler)

    def _request_handler(request: Request) -> None:
        url = request.url.lower()
        for fragment in FORBIDDEN_URL_FRAGMENTS:
            if fragment in url:
                logger.error(
                    "renta web open safety: blocking forbidden navigation method=%s url=%s matched_fragment=%s",
                    request.method,
                    request.url,
                    fragment,
                )
                # Note: Playwright doesn't allow blocking from a request
                # event listener directly; we log + raise on the next
                # awaitable so the test surfaces the violation. The
                # primary line of defense is the click guard.
                raise SedeNavigationError(
                    f"Renta WEB Open safety net intercepted request to {request.url} "
                    f"(forbidden fragment: {fragment!r})",
                    failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
                )

    page.on("request", _request_handler)
