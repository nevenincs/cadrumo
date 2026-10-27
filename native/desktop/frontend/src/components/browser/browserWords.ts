import type {
  SedeViewEndReason,
  SedeViewFailureCode,
  SedeViewNoticeCode,
  SedeViewPublication,
  SedeViewTransfer,
} from "../../ipc/contract";
import type { Translate } from "../../shell/strings";

// The Browser page's wording. A code the host sends is said in the person's
// language; the page never shows a code, an identifier or the host's text.

const FAILURES: Record<SedeViewFailureCode, string> = {
  invalid: "desktop.browser.failure.invalid",
  not_admitted: "desktop.browser.failure.not_admitted",
  conflict: "desktop.browser.failure.conflict",
  unavailable: "desktop.browser.failure.unavailable",
  file_unavailable: "desktop.browser.failure.file_unavailable",
  refused: "desktop.browser.failure.refused",
  unknown: "desktop.browser.failure.unknown",
  not_signed_in: "desktop.browser.failure.not_signed_in",
};

export const failureText = (t: Translate, code: SedeViewFailureCode) =>
  t(FAILURES[code]);

const NOTICES: Record<SedeViewNoticeCode, string> = {
  download_offered: "desktop.browser.notice.download_offered",
  file_chooser_offered: "desktop.browser.notice.file_chooser_offered",
  dialog_opened: "desktop.browser.notice.dialog_opened",
};

export const noticeText = (t: Translate, code: SedeViewNoticeCode) =>
  t(NOTICES[code]);

const ENDS: Record<SedeViewEndReason, string> = {
  closed: "desktop.browser.ended.closed",
  session_lost: "desktop.browser.ended.session_lost",
  cancelled: "desktop.browser.ended.stopped",
  operation_ended: "desktop.browser.ended.stopped",
  runtime_stopping: "desktop.browser.ended.stopped",
  replaced: "desktop.browser.ended.stopped",
  protocol_violation: "desktop.browser.ended.failed",
  failed: "desktop.browser.ended.failed",
  unavailable: "desktop.browser.ended.unavailable",
  refused: "desktop.browser.ended.refused",
};

export const endText = (t: Translate, reason: SedeViewEndReason) =>
  t(ENDS[reason]);

const PUBLICATIONS: Record<SedeViewPublication, string> = {
  published: "desktop.browser.publication.published",
  unchanged: "desktop.browser.publication.unchanged",
  "kept-newer": "desktop.browser.publication.kept_newer",
  "verification-failed": "desktop.browser.publication.verification_failed",
  unknown: "desktop.browser.publication.unknown",
};

export const publicationText = (t: Translate, kind: SedeViewPublication) =>
  t(PUBLICATIONS[kind]);

const DOWNLOADS: Record<SedeViewTransfer, string> = {
  done: "desktop.browser.download.done",
  cancelled: "desktop.browser.download.cancelled",
  failed: "desktop.browser.download.failed",
};
const UPLOADS: Record<SedeViewTransfer, string> = {
  done: "desktop.browser.upload.done",
  cancelled: "desktop.browser.upload.cancelled",
  failed: "desktop.browser.upload.failed",
};

export const transferText = (
  t: Translate,
  kind: "download" | "upload",
  outcome: SedeViewTransfer,
) => t((kind === "download" ? DOWNLOADS : UPLOADS)[outcome]);
