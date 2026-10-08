"""Native manager strings projected from the canonical locale catalogues."""

from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from cadrumo.core.i18n.render import extract_placeholders

from .desktop_chrome import desktop_chrome_strings
from .errors import LocaleError

MANAGER_CHROME_KEYS = frozenset(
    {
        "common.manager.open_application",
        "common.manager.open_logs",
        "common.manager.start_at_sign_in",
        "common.manager.restart",
        "common.manager.retry",
        "common.manager.quit",
        "common.manager.running",
        "common.manager.starting",
        "common.manager.waiting",
        "common.manager.unavailable",
        "common.manager.stopping",
        "common.manager.restart_warning",
        "common.manager.quit_warning",
        "common.manager.action_failed",
    }
)


def manager_chrome_strings() -> dict[str, dict[str, str]]:
    """Require every locale and refuse formatting placeholders absent in native UI."""
    strings = desktop_chrome_strings(keys=MANAGER_CHROME_KEYS, locales=SUPPORTED_OUTPUT_LANGUAGES)
    for values in strings.values():
        for key, value in values.items():
            if extract_placeholders(value):
                raise LocaleError(f"Manager label {key} cannot contain placeholders")
    return strings
