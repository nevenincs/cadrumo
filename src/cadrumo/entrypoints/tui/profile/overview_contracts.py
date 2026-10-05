"""Shared identifiers and locale keys for the profile manager screens."""

from __future__ import annotations

from ....application.user_profile.acquisition_sources import ProfileAcquisitionSourceKey
from ....domain.user_profile.plantilla_media import PLANTILLA_MEDIA_PATH
from ..components.theme import tokenised
from .setup_journey import ProfileSetupStage

_PRESENT_GLYPH = "●"

"""Marks a field carrying a value. A glyph, not colour alone."""

_ABSENT_GLYPH = "○"

"""Marks a declared field the operator has not filled in yet."""

_FIELD_COLUMN_WIDTH = 24

"""Cap, in cells, on the field-name column of every section table.

``DataTable`` sums its columns' natural content width with no clamp against
the container: an unbounded field-name column on a long-label section (the
declared AEAT field names run long) grows wide enough on its own to push the
value column past the right edge of an eighty-column terminal, with the
table's own horizontal scroll left at its default leftmost position and no
visible affordance hinting a value sits further right. The operator sees a
table that looks like it has no value column at all.

A fixed cap paired with the row's auto height (see the ``add_row`` calls
below) wraps a long label onto more lines instead, which is what keeps the
state and value columns inside the viewport at every terminal width this
screen supports — not merely at whatever width the widest declared label
happens to fit. The value column is deliberately left uncapped: it is the
column the operator opened the page to see, and it is a real fact from the
profile rather than a fixed schema label, so letting it use whatever room
the field-name column no longer claims is the point of the cap.
"""

_ROW_INDEX_SEPARATOR = " · "

"""Sits between a repeated row's instance number and its field label.

Punctuation rather than copy, which is why it is written here and not in
the locale catalogues: the label beside it is already translated, and the
number is a stored identity. A taxpayer with three socios would otherwise
read three identical ``NIF`` rows, since the path telling them apart is
shown only once the row is opened.
"""

_LANGUAGE_KEY = "f2"

"""The key that opens the language chooser."""

_COMPLETE_SETUP_KEY = "f8"

"""The key that declares the profile's setup complete, while it is not."""

_COMPLETE_SETUP_ACTION = "complete_setup"

_LANGUAGE_ACTION = "choose_language"

"""The action that key runs.

Named because the footer entry for the key is written at render time
rather than declared beside it, and the two halves have to find each
other.
"""

_SOURCE_TITLE_LOCALE_KEYS: dict[ProfileAcquisitionSourceKey, str] = {
    ProfileAcquisitionSourceKey.CENSAL_REVIEW: "profile.journey.source.censal_review.title",
    ProfileAcquisitionSourceKey.FILED_HISTORY: "profile.journey.source.filed_history.title",
}

_SOURCE_DESCRIPTION_LOCALE_KEYS: dict[ProfileAcquisitionSourceKey, str] = {
    ProfileAcquisitionSourceKey.CENSAL_REVIEW: "profile.journey.source.censal_review.description",
    ProfileAcquisitionSourceKey.FILED_HISTORY: "profile.journey.source.filed_history.description",
}

_SOURCE_ACTION_LOCALE_KEYS: dict[ProfileAcquisitionSourceKey, str] = {
    ProfileAcquisitionSourceKey.CENSAL_REVIEW: "profile.journey.source.censal_review.action",
    ProfileAcquisitionSourceKey.FILED_HISTORY: "profile.journey.source.filed_history.action",
}

_DOCUMENT_READER_CARD_ID = "manager-document-reader"

_PLANTILLA_MEDIA_SECTION = PLANTILLA_MEDIA_PATH.split(".", 1)[0]

"""The non-repeatable section whose panel carries the average-workforce years."""

_PLANTILLA_MEDIA_BUTTON_ID = "manager-plantilla-media"

_CONTINUE_BUTTON_ID = "onboarding-continue"

_SETUP_TITLE_LOCALE_KEYS = {
    ProfileSetupStage.OVERVIEW: "flows.manager.setup.overview_title",
    ProfileSetupStage.GET_DATA: "flows.manager.setup.get_data_title",
    ProfileSetupStage.REQUIRED: "flows.manager.setup.required_title",
    ProfileSetupStage.REVIEW: "flows.manager.setup.review_title",
    ProfileSetupStage.READY: "flows.manager.setup.ready_title",
}

_SETUP_NAV_LOCALE_KEYS = {
    ProfileSetupStage.OVERVIEW: "flows.manager.setup.nav_overview",
    ProfileSetupStage.GET_DATA: "flows.manager.setup.nav_get_data",
    ProfileSetupStage.REQUIRED: "flows.manager.setup.nav_required",
    ProfileSetupStage.REVIEW: "flows.manager.setup.nav_review",
    ProfileSetupStage.READY: "flows.manager.setup.nav_ready",
}

_SETUP_COPY_LOCALE_KEYS = {
    ProfileSetupStage.OVERVIEW: "flows.manager.setup.overview_copy",
    ProfileSetupStage.GET_DATA: "flows.manager.setup.get_data_copy",
    ProfileSetupStage.REQUIRED: "flows.manager.setup.required_copy",
    ProfileSetupStage.REVIEW: "flows.manager.setup.review_copy",
    ProfileSetupStage.READY: "flows.manager.setup.ready_copy",
}

_SEARCH_ID = "manager-search"

_REQUIRED_ONLY_ID = "manager-required-only"

_SEARCH_SETTLE_SECONDS = 0.15

"""How long typing pauses before the sections are filtered again.

Filtering rebuilds every section table, so doing it on each keystroke would
make the box lag behind the operator's typing on a full profile."""

_REQUIRED_MARK = "*"

"""Marks a field filing will eventually require."""

_EDIT_DIALOG_CSS = tokenised("""
#edit-dialog {
    border: $cadrumo-radius-overlay $accent;
    background: $surface;
    padding: $cadrumo-space-0 $cadrumo-space-1;
    width: 100%;
    height: auto;
    max-height: 100%;
}
#edit-body { height: auto; max-height: $cadrumo-modal-max-height; }
#edit-requirement { color: $text-muted; }
#edit-context { color: $text-muted; margin-bottom: $cadrumo-space-1; }
#edit-label { text-style: bold; }
#edit-hint { color: $text-muted; }
#edit-help { color: $text-muted; margin-bottom: $cadrumo-space-1; }
#edit-refusal { color: $error; text-style: bold; }
#edit-masked-note { color: $text-muted; }
#edit-dialog Input { margin: $cadrumo-space-0; }
#edit-actions { height: auto; align-horizontal: right; margin: $cadrumo-space-0; }
#edit-actions Button { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap; }
""")
