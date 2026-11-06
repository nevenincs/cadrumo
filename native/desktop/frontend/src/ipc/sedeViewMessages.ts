// The Sede view's wire shapes: its phases, dialogs, outcomes, the messages
// its channel delivers and the input the page sends it. Field names and casing
// follow the host's serde output exactly.

// ---------------------------------------------------------------------------
// The Sede view
// ---------------------------------------------------------------------------

/** What the view's page is doing: a login runs in it, the person browses, or
 * it publishes the session and ends. */
export type SedeViewPhase = "acquiring" | "browsing" | "closing";

/** Whether the page's address can be shown: an https page shows its origin
 * and path; any other page shows only that it is not secure, or not known. */
export type SedeViewPageSecurity = "secure" | "insecure" | "unknown";

/** Every notice the view may raise: a page dialog, which carries its dialog. */
export type SedeViewNoticeCode = "dialog_opened" | "identity_mismatch";

export type SedeViewDialogKind =
  "alert" | "confirm" | "prompt" | "beforeunload";

/** A page dialog waiting for the person's answer. */
export type SedeViewDialog = {
  dialog_id: number;
  dialog_kind: SedeViewDialogKind;
  message: string;
  default_prompt: string | null;
};

/** How a download or an upload ended. */
export type SedeViewTransfer = "done" | "cancelled" | "failed";

/** Why a view ended, as the host says it. */
export type SedeViewEndReason =
  | "closed"
  | "session_lost"
  | "cancelled"
  | "operation_ended"
  | "replaced"
  | "protocol_violation"
  | "runtime_stopping"
  | "failed"
  | "unavailable"
  | "refused"
  /** A component the view needs is not set up; the ended message's
   * `recovery_action_id` names its setup. */
  | "component_not_ready";

/** What became of the session when the view ended. */
export type SedeViewPublication =
  | "published"
  | "unchanged"
  | "kept-newer"
  | "verification-failed"
  | "identity-mismatch"
  | "unknown";

/** How the view's operation settled, where the host could observe it. */
export type SedeViewOutcome = {
  condition:
    | "succeeded"
    | "refused"
    | "failed"
    | "cancelled"
    | "timed_out"
    | "interrupted";
  end:
    | "closed"
    | "page_lost"
    | "stream_ended"
    | "stopped"
    | "protocol_violation"
    | null;
  publication: SedeViewPublication | null;
};

/**
 * A JSON message on the view's channel. Every message names its `view`, so a
 * late message of an earlier view is told apart. An `image` is followed by
 * one raw message holding that image's JPEG bytes.
 */
export type SedeViewMessage =
  | { kind: "opened"; view: number }
  | {
      kind: "image";
      view: number;
      sequence: number;
      byte_length: number;
      pixel_width: number;
      pixel_height: number;
      css_width: number;
      css_height: number;
      scale: number;
    }
  | {
      kind: "state";
      view: number;
      security: SedeViewPageSecurity;
      /** Null unless the page is `secure`. */
      origin: string | null;
      path: string | null;
      title: string;
      can_go_back: boolean;
      can_go_forward: boolean;
      loading: boolean;
      phase: SedeViewPhase;
      /** Whether the host holds this page's address to open externally. */
      external: boolean;
    }
  | {
      kind: "notice";
      view: number;
      code: SedeViewNoticeCode;
      dialog: SedeViewDialog | null;
    }
  | {
      kind: "download";
      view: number;
      transfer_id: number;
      filename: string;
      size: number | null;
      mime: string | null;
    }
  | {
      kind: "download_ended";
      view: number;
      transfer_id: number;
      outcome: SedeViewTransfer;
    }
  | {
      kind: "file_chooser";
      view: number;
      chooser_id: number;
      accept: string[];
      multiple: boolean;
    }
  | {
      kind: "upload_ended";
      view: number;
      chooser_id: number;
      outcome: SedeViewTransfer;
    }
  | { kind: "closing"; view: number }
  | {
      kind: "ended";
      view: number;
      reason: SedeViewEndReason;
      code: string | null;
      outcome: SedeViewOutcome | null;
      /** The setup action that readies the missing component, present only
       * when `reason` is "component_not_ready". */
      recovery_action_id: string | null;
    };

/** A raw frame the host keeps for the shell document, named on its channel.
 * `shell_channel_frame` hands over its bytes once. */
export type ChannelRawFrame = { raw_frame: string };

/** What the channel carries: JSON messages, and after each image the name of
 * the frame holding its bytes. Where the host could not keep the frame, the
 * bytes themselves arrive. */
export type SedeViewDelivery = SedeViewMessage | ChannelRawFrame | ArrayBuffer;

/** One input event of the person, in CSS pixels of the view's page. The
 * modifier mask is Alt 1, Control 2, Meta 4, Shift 8. */
export type SedeViewInput =
  | {
      type: "pointer";
      action: "down" | "up" | "move";
      x: number;
      y: number;
      button: "none" | "left" | "middle" | "right";
      click_count: number;
      modifiers: number;
    }
  | {
      type: "wheel";
      x: number;
      y: number;
      delta_x: number;
      delta_y: number;
      modifiers: number;
    }
  | {
      type: "key";
      action: "down" | "up";
      key: string;
      code: string;
      modifiers: number;
    }
  | { type: "text"; text: string };

export type SedeViewVerb = "back" | "forward" | "reload" | "home";

export type SedeClipboardAction = "copy" | "cut";

/** `code` of a refused view command; `operation_id` is for diagnostics and
 * the window never shows it. */
export type SedeViewFailureCode =
  | "invalid"
  | "not_admitted"
  | "conflict"
  | "unavailable"
  | "file_unavailable"
  | "refused"
  | "unknown"
  | "not_signed_in";

export type SedeViewFailure = {
  code: SedeViewFailureCode;
  operation_id: string | null;
  reason?: string;
};
