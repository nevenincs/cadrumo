import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import type {
  SedeClipboardAction,
  SedeViewInput,
  SedeViewVerb,
} from "../../ipc/sedeViewMessages";
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
const RESIZE_RETRY_MS = 350;
const RESIZE_ATTEMPTS = 3;

export type DrawnImage = Extract<SedeViewEvent, { kind: "image" }>;

const nothing = () => undefined;
const sameSize = (a: SedeViewSize | null, b: SedeViewSize | null) =>
  a?.cssWidth === b?.cssWidth &&
  a?.cssHeight === b?.cssHeight &&
  a?.scale === b?.scale;

/**
 * Owns the page's view from the first panel size to the page's unmount: it
 * opens the view, keeps what it says in memory, credits every image it is
 * sent once it is drawn or dropped, follows the panel's size, and closes the
 * view when the page is unmounted, which publishes the session. While the page
 * is put aside it grants no credit, so the worker holds its newest image and
 * sends nothing more; the view, its state and its prompts go on, and the
 * credit owed is granted when the page is shown again. Nothing it holds
 * reaches storage, the layout or a log.
 */
export function useSedeView({
  port,
  size,
  shown,
  draw,
}: {
  port: SedeViewPort;
  /** The panel's size once it has room; the view opens only then. */
  size: SedeViewSize | null;
  /** False while the page is put aside: no credit is granted then. */
  shown: boolean;
  /** Draws one image; settles when it is drawn or dropped. */
  draw: (image: DrawnImage) => Promise<void>;
}) {
  const [state, dispatch] = useReducer(reduceBrowser, FIRST_STATE);
  const [attempt, setAttempt] = useState(0);
  const session = useRef<SedeViewSession | null>(null);
  const [inputFailure, setInputFailure] = useState<SedeViewSession | null>(
    null,
  );
  const answering = useRef<{ owner: SedeViewSession; id: number } | null>(null);
  const [reply, setReply] = useState<{
    owner: SedeViewSession;
    id: number;
    pending: boolean | null;
    failed: boolean;
    text?: string;
  } | null>(null);
  const sent = useRef<SedeViewSize | null>(null);
  const resize = useRef<(() => void) | null>(null);
  const latest = useRef({ size, draw, shown });
  latest.current = { size, draw, shown };
  const sized = size !== null;
  // Images received and not yet credited; at most the two the view may have
  // in flight, so granting them all restores the credit the view started with.
  const owed = useRef(0);

  // Credit goes only to an open view and only while the page is shown.
  const settle = useCallback(() => {
    const view = session.current;
    if (!view || !latest.current.shown) return;
    for (; owed.current > 0; owed.current -= 1)
      void view.credit().catch(nothing);
  }, []);

  useEffect(() => {
    if (shown) settle();
  }, [shown, settle]);

  useEffect(() => {
    if (!sized) return;
    let cancelled = false;
    // The host said the view is over, possibly before it answered the open:
    // nothing is sent to a view that has ended.
    let ended = false;
    let timer = 0;
    let resizeTimer = 0;
    let resizing = false;
    let failures = 0;
    let failedSize: SedeViewSize | null = null;
    let opened: SedeViewSession | null = null;
    owed.current = 0;

    const scheduleResize = (delay = RESIZE_SETTLE_MS) => {
      window.clearTimeout(resizeTimer);
      if (!cancelled && !ended)
        resizeTimer = window.setTimeout(() => void sendSize(), delay);
    };
    const sendSize = async () => {
      const desired = latest.current.size;
      if (
        cancelled ||
        ended ||
        !opened ||
        resizing ||
        !desired ||
        sameSize(sent.current, desired)
      )
        return;
      if (!sameSize(failedSize, desired)) failures = 0;
      if (failures >= RESIZE_ATTEMPTS) return;
      resizing = true;
      try {
        await opened.resize(desired);
        if (cancelled) return;
        sent.current = desired;
        failures = 0;
        failedSize = null;
      } catch (error) {
        if (cancelled) return;
        failedSize = desired;
        failures += 1;
        if (failures === RESIZE_ATTEMPTS)
          dispatch({ type: "problem", code: sedeViewFailure(error).code });
      } finally {
        resizing = false;
        if (
          !cancelled &&
          !ended &&
          !sameSize(sent.current, latest.current.size) &&
          (failures < RESIZE_ATTEMPTS ||
            !sameSize(failedSize, latest.current.size))
        ) {
          scheduleResize(failures ? RESIZE_RETRY_MS : RESIZE_SETTLE_MS);
        }
      }
    };
    resize.current = scheduleResize;

    const credit = () => {
      if (cancelled || ended) return;
      owed.current += 1;
      settle();
    };
    const onEvent = (event: SedeViewEvent) => {
      if (cancelled) return;
      if (event.kind === "ended") {
        ended = true;
        window.clearTimeout(resizeTimer);
        owed.current = 0;
        opened = null;
        session.current = null;
        sent.current = null;
        dispatch({ type: "event", event });
        return;
      }
      if (event.kind === "image") {
        if (ended) return;
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
          // An end that arrived first left no view to resize or credit.
          if (ended) return;
          opened = view;
          session.current = view;
          sent.current = first;
          scheduleResize();
          settle();
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
      window.clearTimeout(resizeTimer);
      resize.current = null;
      session.current = null;
      sent.current = null;
      // Unmounting ends the view, which publishes the session.
      void opened?.close().catch(nothing);
    };
  }, [port, sized, attempt, settle]);

  useEffect(() => {
    resize.current?.();
  }, [size]);

  // A call the host refuses is said once; it never rejects into the page.
  const refused = useCallback((work: Promise<unknown> | undefined) => {
    work?.catch((error: unknown) =>
      dispatch({ type: "problem", code: sedeViewFailure(error).code }),
    );
  }, []);

  return {
    state,
    inputFailed: inputFailure !== null && inputFailure === session.current,
    dismissInputFailure: useCallback(() => setInputFailure(null), []),
    dialogReply: reply?.owner === session.current ? reply : null,
    input: useCallback((event: SedeViewInput) => {
      const owner = session.current;
      void owner?.input(event).catch(() => {
        if (session.current === owner) setInputFailure(owner);
      });
    }, []),
    navigate: useCallback(
      (verb: SedeViewVerb) => refused(session.current?.navigate(verb)),
      [refused],
    ),
    clipboard: useCallback(
      (action: SedeClipboardAction) =>
        refused(session.current?.clipboard(action)),
      [refused],
    ),
    answerDialog: useCallback(
      async (dialogId: number, accept: boolean, promptText?: string) => {
        const owner = session.current;
        if (!owner || answering.current?.owner === owner) return;
        const admission = { owner, id: dialogId };
        answering.current = admission;
        setReply({
          owner,
          id: dialogId,
          pending: accept,
          failed: false,
          text: promptText,
        });
        try {
          await owner.dialog(dialogId, accept, promptText);
          if (session.current === owner) {
            dispatch({ type: "dialog-answered", dialogId });
            setReply(null);
          }
        } catch {
          if (session.current === owner)
            setReply({
              owner,
              id: dialogId,
              pending: null,
              failed: true,
              text: promptText,
            });
        } finally {
          if (answering.current === admission) answering.current = null;
        }
      },
      [],
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
      () => refused(session.current?.openExternal()),
      [refused],
    ),
    dismissNote: useCallback(() => dispatch({ type: "note-dismissed" }), []),
    dismissProblem: useCallback(
      () => dispatch({ type: "problem-dismissed" }),
      [],
    ),
    reopen: useCallback(() => setAttempt((count) => count + 1), []),
  };
}
