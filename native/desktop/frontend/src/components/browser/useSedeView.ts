import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import type { SedeViewInput, SedeViewVerb } from "../../ipc/contract";
import {
  sedeViewFailure,
  type SedeViewEvent,
  type SedeViewPort,
  type SedeViewSession,
  type SedeViewSize,
} from "../../shell/sedeView";
import { FIRST_STATE, reduceBrowser } from "./browserModel";

/** How long to wait before asking again for a view while the previous one is
 * still publishing its session, and how many times to ask before giving up. */
const RETRY_MS = 750;
const RETRY_LIMIT = 80;
/** How long a panel size must hold before the page is told of it. */
const RESIZE_SETTLE_MS = 120;

export type DrawnImage = Extract<SedeViewEvent, { kind: "image" }>;

const nothing = () => undefined;
const sameSize = (a: SedeViewSize | null, b: SedeViewSize | null) =>
  a?.cssWidth === b?.cssWidth &&
  a?.cssHeight === b?.cssHeight &&
  a?.scale === b?.scale;

/**
 * Owns the page's view from the first panel size to the page's unmount: it
 * opens the view, keeps what it says in memory, credits every image it is
 * sent whether or not it was drawn, including while the page is put aside,
 * follows the panel's size, and closes the view when the page is unmounted,
 * which publishes the session. Nothing it holds reaches storage, the layout
 * or a log.
 */
export function useSedeView({
  port,
  size,
  draw,
}: {
  port: SedeViewPort;
  /** The panel's size once it has room; the view opens only then. */
  size: SedeViewSize | null;
  /** Draws one image; settles when it is drawn or dropped. */
  draw: (image: DrawnImage) => Promise<void>;
}) {
  const [state, dispatch] = useReducer(reduceBrowser, FIRST_STATE);
  const [attempt, setAttempt] = useState(0);
  const session = useRef<SedeViewSession | null>(null);
  const sent = useRef<SedeViewSize | null>(null);
  const latest = useRef({ size, draw });
  latest.current = { size, draw };
  const sized = size !== null;

  useEffect(() => {
    if (!sized) return;
    let cancelled = false;
    let timer = 0;
    let opened: SedeViewSession | null = null;
    // Images that arrive before the open call has answered are credited then.
    let owed = 0;

    const credit = () => {
      if (cancelled) return;
      if (opened) void opened.credit().catch(nothing);
      else owed += 1;
    };
    const onEvent = (event: SedeViewEvent) => {
      if (cancelled) return;
      if (event.kind === "image") {
        void latest.current.draw(event).catch(nothing).then(credit);
        return;
      }
      dispatch({ type: "event", event });
    };
    const begin = (tries: number) => {
      const first = latest.current.size;
      if (!first) return;
      dispatch({ type: tries === 0 ? "opening" : "waiting" });
      port.open(first, onEvent).then(
        (view) => {
          if (cancelled) {
            void view.close().catch(nothing);
            return;
          }
          opened = view;
          session.current = view;
          sent.current = first;
          for (; owed > 0; owed -= 1) void view.credit().catch(nothing);
        },
        (error: unknown) => {
          if (cancelled) return;
          const { code } = sedeViewFailure(error);
          // The previous view is publishing its session: it ends shortly.
          if (code === "conflict" && tries < RETRY_LIMIT) {
            dispatch({ type: "waiting" });
            timer = window.setTimeout(() => begin(tries + 1), RETRY_MS);
          } else dispatch({ type: "failed", code });
        },
      );
    };
    begin(0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      session.current = null;
      sent.current = null;
      // Unmounting ends the view, which publishes the session.
      void opened?.close().catch(nothing);
    };
  }, [port, sized, attempt]);

  useEffect(() => {
    if (!size || state.phase !== "open" || sameSize(sent.current, size)) return;
    const timer = window.setTimeout(() => {
      const open = session.current;
      if (!open) return;
      sent.current = size;
      void open.resize(size).catch(nothing);
    }, RESIZE_SETTLE_MS);
    return () => window.clearTimeout(timer);
  }, [size, state.phase]);

  // A call the host refuses is said once; it never rejects into the page.
  const refused = useCallback((work: Promise<unknown> | undefined) => {
    work?.catch((error: unknown) =>
      dispatch({ type: "problem", code: sedeViewFailure(error).code }),
    );
  }, []);

  return {
    state,
    input: useCallback((event: SedeViewInput) => {
      void session.current?.input(event).catch(nothing);
    }, []),
    navigate: useCallback(
      (verb: SedeViewVerb) => refused(session.current?.navigate(verb)),
      [refused],
    ),
    answerDialog: useCallback(
      (dialogId: number, accept: boolean, promptText?: string) => {
        dispatch({ type: "dialog-answered", dialogId });
        refused(session.current?.dialog(dialogId, accept, promptText));
      },
      [refused],
    ),
    /** Waits for the native save dialog. */
    answerDownload: useCallback(async (transferId: number, save: boolean) => {
      try {
        await session.current?.downloadAnswer(transferId, save);
      } catch (error) {
        dispatch({ type: "problem", code: sedeViewFailure(error).code });
      }
      dispatch({ type: "download-answered", transferId });
    }, []),
    /** Waits for the native open dialog. */
    answerChooser: useCallback(async (chooserId: number, choose: boolean) => {
      try {
        await session.current?.fileChooserAnswer(chooserId, choose);
      } catch (error) {
        dispatch({ type: "problem", code: sedeViewFailure(error).code });
      }
      dispatch({ type: "chooser-answered", chooserId });
    }, []),
    openExternal: useCallback(
      (offerId?: string) => refused(session.current?.openExternal(offerId)),
      [refused],
    ),
    dismissNotice: useCallback(
      (key: number) => dispatch({ type: "notice-dismissed", key }),
      [],
    ),
    dismissNote: useCallback(() => dispatch({ type: "note-dismissed" }), []),
    dismissProblem: useCallback(
      () => dispatch({ type: "problem-dismissed" }),
      [],
    ),
    reopen: useCallback(() => setAttempt((count) => count + 1), []),
  };
}
