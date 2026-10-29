// The English text of the results view's strings, for the stories until the
// catalogue generated from the locale sources carries them. A key the
// catalogue has always wins.
export const AEAT_SYNC_RESULTS_WORDS: Record<string, string> = {
  "desktop.aeat_sync.area.census.name": "Census data",
  "desktop.aeat_sync.area.filed.name": "Filed declarations",
  "desktop.aeat_sync.area.notifications.name": "Notifications",
  "desktop.aeat_sync.area.vat.name": "VAT balance carried forward",
  "desktop.aeat_sync.area.borrador.name": "Income tax draft (Borrador)",
  "desktop.aeat_sync.area.identity.name": "Identity checks",
  "desktop.aeat_sync.results.title": "What came back from AEAT",
  "desktop.aeat_sync.results.read_only":
    "This only shows what AEAT displays. Nothing is filed or sent from here.",
  "desktop.aeat_sync.results.loading": "Loading what came back…",
  "desktop.aeat_sync.results.unavailable": "Couldn't show what came back.",
  "desktop.aeat_sync.results.retry": "Try again",
  "desktop.aeat_sync.results.retry_named": "Try again: {name}",
  "desktop.aeat_sync.results.retry_failed":
    "Couldn't start that. Try again in a moment.",
  "desktop.aeat_sync.results.retry_unknown":
    "We couldn't tell whether that started. Check before trying again.",
  "desktop.aeat_sync.results.updated": "Updated {date}",
  "desktop.aeat_sync.results.nothing_new": "Nothing new since last time.",
  "desktop.aeat_sync.results.nothing_found": "AEAT has nothing to show here.",
  "desktop.aeat_sync.results.failed": "Couldn't update. Try again.",
  "desktop.aeat_sync.results.partly": "Part of it couldn't be updated.",
  "desktop.aeat_sync.results.unknown":
    "We couldn't tell whether this finished. Check before trying again.",
  "desktop.aeat_sync.results.problems": "What couldn't be updated in {name}",
  "desktop.aeat_sync.results.part.all": "All of it",
  "desktop.aeat_sync.results.part.year": "Declarations for {year}",
  "desktop.aeat_sync.results.part.form": "Modelo {form} for {year}",
  "desktop.aeat_sync.results.reason.session_ended":
    "Your AEAT sign-in ended. Sign in again, then try again.",
  "desktop.aeat_sync.results.reason.no_access":
    "AEAT didn't accept your access details.",
  "desktop.aeat_sync.results.reason.unavailable": "AEAT didn't answer.",
  "desktop.aeat_sync.results.reason.refused": "AEAT wouldn't show this.",
  "desktop.aeat_sync.results.reason.other": "Something went wrong.",
  "desktop.aeat_sync.results.new.filed.one": "{count} new declaration at AEAT",
  "desktop.aeat_sync.results.new.filed.other":
    "{count} new declarations at AEAT",
  "desktop.aeat_sync.results.new.notifications.one": "{count} new notification",
  "desktop.aeat_sync.results.new.notifications.other":
    "{count} new notifications",
  "desktop.aeat_sync.results.new.other.one": "{count} new entry",
  "desktop.aeat_sync.results.new.other.other": "{count} new entries",
  "desktop.aeat_sync.results.changed.census.one":
    "{count} detail differs from your profile",
  "desktop.aeat_sync.results.changed.census.other":
    "{count} details differ from your profile",
  "desktop.aeat_sync.results.changed.filed.one":
    "{count} declaration differs from your records",
  "desktop.aeat_sync.results.changed.filed.other":
    "{count} declarations differ from your records",
  "desktop.aeat_sync.results.changed.other.one": "{count} entry changed",
  "desktop.aeat_sync.results.changed.other.other": "{count} entries changed",
  "desktop.aeat_sync.results.census_waiting":
    "AEAT's details are ready to compare with your profile.",
  "desktop.aeat_sync.results.census_review": "Review the differences",
  "desktop.aeat_sync.results.filed.note":
    "Your record, what AEAT shows and the receipt are kept apart: a declaration can match your records without a confirmed receipt.",
  "desktop.aeat_sync.results.filed.empty": "No filed declarations to show.",
  "desktop.aeat_sync.results.filed.title_period":
    "Modelo {form}, {period} {year}",
  "desktop.aeat_sync.results.filed.title_year": "Modelo {form}, {year}",
  "desktop.aeat_sync.results.filed.group.aeat_only": "New at AEAT ({count})",
  "desktop.aeat_sync.results.filed.group.differing":
    "Different from your records ({count})",
  "desktop.aeat_sync.results.filed.group.local_only":
    "Only in your records ({count})",
  "desktop.aeat_sync.results.filed.group.matched":
    "Matches your records ({count})",
  "desktop.aeat_sync.results.filed.group_about.aeat_only":
    "AEAT shows these and your records don't.",
  "desktop.aeat_sync.results.filed.group_about.differing":
    "Both have them, but they don't agree.",
  "desktop.aeat_sync.results.filed.group_about.local_only":
    "You have these and AEAT doesn't show them.",
  "desktop.aeat_sync.results.filed.column.record": "Your record",
  "desktop.aeat_sync.results.filed.column.aeat": "At AEAT",
  "desktop.aeat_sync.results.filed.column.receipt": "Receipt",
  "desktop.aeat_sync.results.filed.record.none": "No record",
  "desktop.aeat_sync.results.filed.record.draft": "Draft from {date}",
  "desktop.aeat_sync.results.filed.record.marked_filed":
    "Marked as filed on {date}",
  "desktop.aeat_sync.results.filed.aeat.none": "Not shown",
  "desktop.aeat_sync.results.filed.aeat.shown": "Shown on {date}",
  "desktop.aeat_sync.results.filed.receipt.confirmed": "Confirmed",
  "desktop.aeat_sync.results.filed.receipt.not_confirmed": "Not confirmed",
  "desktop.aeat_sync.results.filed.differs.amount": "Amount differs",
  "desktop.aeat_sync.results.filed.differs.date": "Date differs",
  "desktop.aeat_sync.results.filed.differs.status": "Status differs",
  "desktop.aeat_sync.results.notifications.empty": "No notifications.",
  "desktop.aeat_sync.results.notifications.warning":
    "Opening a notification at AEAT can count as receiving it. Open it there only when you're ready.",
  "desktop.aeat_sync.results.notifications.open": "Open AEAT",
  "desktop.aeat_sync.results.notifications.group.unread": "Unread ({count})",
  "desktop.aeat_sync.results.notifications.group.read": "Read ({count})",
  "desktop.aeat_sync.results.notifications.from": "From {sender}, {date}",
  "desktop.aeat_sync.results.notifications.unread_about":
    "Read it at AEAT first; then its document can be opened here.",
  "desktop.aeat_sync.results.notifications.read_on": "Read on {date}",
  "desktop.aeat_sync.results.notifications.read": "Read",
  "desktop.aeat_sync.results.borrador.about":
    "Download your Borrador from AEAT, then import the PDF here.",
  "desktop.aeat_sync.results.borrador.import": "Import PDF",
  "desktop.aeat_sync.results.borrador.imported": "Imported {name}.",
  "desktop.aeat_sync.results.borrador.nothing_found":
    "We couldn't find a Borrador in {name}.",
  "desktop.aeat_sync.results.borrador.failed":
    "Couldn't import {name}. Try again.",
  "desktop.aeat_sync.results.borrador.unknown":
    "We couldn't tell whether {name} was imported. Check before trying again.",
};
