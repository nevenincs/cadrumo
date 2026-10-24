import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { LedgerSection } from "../layout";
import type { Translate } from "../strings";
import { FocusRegister } from "./focus";
import { decide, GuardRegister, type Guard, type Leaving } from "./guards";
import type { NavigationRuntime } from "./hooks";
import { parseViewLink, type ViewLink, type ViewLinkRefusal } from "./links";
import {
  elementOf,
  lineage,
  type NavigationRegister,
  type Surface,
  type ViewParams,
} from "./register";
import {
  declaredImplementation,
  resolveView,
  type Implemented,
  type ViewOpened,
  type ViewRefusalReason,
} from "./resolve";
import {
  WINDOW_VIEWS,
  mountedNow,
  unmountedBy,
  type WindowPort,
  type WindowViewEntry,
} from "./windowViews";

/** The question a navigation waits on, drawn by the window. */
export type NavigatorPrompt =
  /** Dirty work the owners left to the shared prompt. */
  | {
      readonly kind: "leave";
      readonly discard: () => void;
      readonly stay: () => void;
    }
  /** The window's close over work still in flight. */
  | {
      readonly kind: "close_busy";
      readonly close: () => void;
      readonly stay: () => void;
    };

/** What the navigator needs of the window. */
export type NavigatorWindow = {
  readonly register: NavigationRegister;
  readonly t: Translate;
  say(text: string): void;
  /** The page shown and the Ledger section saved. */
  shown(): { page: string; ledgerSection: LedgerSection };
  /** Whether the host offers a port a window view needs. */
  hasPort(port: WindowPort): boolean;
  signedIn(): boolean;
  /** Whether this host can ask a TUI to present a view at all. */
  presents(): boolean;
  /** Applies a window view through the layout store. Panes, terminals and
   * panel tabs take the keyboard as the window gives it to them; a page's
   * and the agent's focus is asked of the focus register. */
  showInWindow(id: string, entry: WindowViewEntry): void;
  /** Shows the TUI with the keyboard and asks the host to present the
   * view; true once a TUI was passed it. Says itself why it was not. */
  showInTui(view: string, params: ViewParams): Promise<boolean>;
  /** A view of the profile was asked for while nobody is signed in. */
  askSignIn(): void;
};

/** Where a navigation came from, for what follows it. */
export type NavigationOptions = {
  /** Called once the view is shown (or, for a TUI view, delivered). */
  readonly opened?: (opened: ViewOpened) => void;
};

const SYNTAX_REFUSALS: ReadonlySet<ViewLinkRefusal> = new Set([
  "too_long",
  "malformed",
  "uppercase",
  "not_a_view_link",
  "credentials",
  "percent_encoding",
  "fragment",
  "query",
  "too_many_segments",
]);

/** What the window implements now: its table's views whose host port is
 * there, each honouring the parameters the table declares. */
function windowImplementation(hasPort: (port: WindowPort) => boolean) {
  const ids = Object.keys(WINDOW_VIEWS).filter((id) => {
    const port = WINDOW_VIEWS[id]?.port ?? null;
    return port === null || hasPort(port);
  });
  return {
    views: new Set(ids),
    params: new Map(
      ids.map((id) => [id, new Set(WINDOW_VIEWS[id]?.honours ?? [])]),
    ),
  };
}

/**
 * The window's navigator: every navigation from a link, the palette, the
 * rail, a page, sign-out, a profile switch or the window's close resolves
 * here, passes the guard register, applies through the layout store and
 * then focuses its element when that element signals it is mounted.
 */
export function useNavigator(window: NavigatorWindow) {
  const runtime: NavigationRuntime = useMemo(
    () => ({ guards: new GuardRegister(), focus: new FocusRegister() }),
    [],
  );
  const host = useRef(window);
  host.current = window;
  const [prompt, setPrompt] = useState<NavigatorPrompt | null>(null);
  // One navigation waits for an answer at a time.
  const pending = useRef(false);
  // A commit after each applied navigation, so a wish whose element is
  // already mounted is flushed even when the layout did not change.
  const [, setApplied] = useState(0);

  useEffect(() => {
    runtime.focus.flush();
  });
  useEffect(() => {
    // Whatever the person presses next decides where focus is.
    const drop = (event: Event) => runtime.focus.dropBefore(event.timeStamp);
    globalThis.addEventListener("pointerdown", drop, true);
    globalThis.addEventListener("keydown", drop, true);
    return () => {
      globalThis.removeEventListener("pointerdown", drop, true);
      globalThis.removeEventListener("keydown", drop, true);
    };
  }, [runtime]);

  /** Weighs a navigation against the guards and lets it through, refuses
   * it with a toast, or asks once. `stay` runs whenever it does not go. */
  const guard = useCallback(
    (leaving: Leaving, proceed: () => void, stay?: () => void) => {
      const { say, t } = host.current;
      if (pending.current) {
        say(t("desktop.navigation.pending"));
        stay?.();
        return;
      }
      const decision = decide(leaving, runtime.guards.assess(leaving));
      if (decision.kind === "proceed") {
        proceed();
        return;
      }
      if (decision.kind === "refuse") {
        say(
          t(
            decision.reason === "modal"
              ? "desktop.navigation.modal"
              : "desktop.navigation.busy",
          ),
        );
        stay?.();
        return;
      }
      pending.current = true;
      const settle = (then?: () => void) => {
        pending.current = false;
        setPrompt(null);
        then?.();
      };
      if (decision.kind === "ask_busy_close") {
        setPrompt({
          kind: "close_busy",
          close: () => settle(proceed),
          stay: () => settle(stay),
        });
        return;
      }
      // Owners that ask in their own words are asked in turn; the rest are
      // asked once, together, in the shared words.
      const own = decision.owners.filter((owner) => owner.ask);
      const shared = decision.owners.filter((owner) => !owner.ask);
      const askShared = () => {
        if (shared.length === 0) {
          settle(proceed);
          return;
        }
        setPrompt({
          kind: "leave",
          discard: () => {
            for (const owner of shared) owner.discard?.();
            settle(proceed);
          },
          stay: () => settle(stay),
        });
      };
      const askOwn = (index: number) => {
        const owner: Guard | undefined = own[index];
        if (!owner) {
          askShared();
          return;
        }
        const asked = owner.ask?.(
          () => askOwn(index + 1),
          () => settle(stay),
        );
        if (!asked) askOwn(index + 1);
      };
      askOwn(0);
    },
    [runtime],
  );

  /** Opens a resolved request: guards, requirements, apply, notice, focus. */
  const open = useCallback(
    (request: ViewLink, options: NavigationOptions = {}) => {
      const window = host.current;
      const { register, say, t } = window;
      const implemented: Implemented = {
        gui: windowImplementation(window.hasPort),
        ...(window.presents()
          ? { tui: declaredImplementation(register).tui }
          : {}),
      };
      const resolved = resolveView(request, implemented, register);
      if (resolved.kind === "refused") {
        say(refusalText(t, register, resolved.reason, request.viewId));
        return;
      }
      const notice = () => {
        if (resolved.noticeDue)
          say(noticeText(t, register, resolved, request.viewId));
      };
      if (resolved.surface === "tui") {
        // Showing the TUI takes nothing down: only a dialog holds it.
        guard({ kind: "navigate", unmounted: new Set() }, () => {
          void window
            .showInTui(resolved.opened, resolved.params)
            .then((delivered) => {
              if (!delivered) return;
              notice();
              options.opened?.(resolved);
            });
        });
        return;
      }
      const entry = WINDOW_VIEWS[resolved.opened];
      if (!entry) return;
      if (entry.signedIn && !window.signedIn()) {
        const element = elementOf(register, resolved.opened);
        say(
          t("desktop.navigation.sign_in", {
            view: element ? t(element.label) : resolved.opened,
          }),
        );
        window.askSignIn();
        return;
      }
      const shown = window.shown();
      const unmounted = unmountedBy(
        mountedNow(shown.page, shown.ledgerSection),
        entry.view,
        shown.ledgerSection,
      );
      guard({ kind: "navigate", unmounted }, () => {
        window.showInWindow(resolved.opened, entry);
        if (entry.view.kind === "page" || entry.view.kind === "agent")
          runtime.focus.request(
            lineage(register, resolved.opened).map((element) => element.id),
            performance.now(),
          );
        setApplied((count) => count + 1);
        notice();
        options.opened?.(resolved);
      });
    },
    [guard, runtime],
  );

  /** Opens a `cadrumo:` link, or says why it cannot. */
  const openLink = useCallback(
    (text: string, options?: NavigationOptions) => {
      const { register, say, t } = host.current;
      const parsed = parseViewLink(text, register);
      if (parsed.kind === "refused") {
        say(refusalText(t, register, parsed.reason, null));
        return;
      }
      open(parsed.link, options);
    },
    [open],
  );

  /** Opens a register element by id, as the palette and pages do. */
  const openView = useCallback(
    (
      viewId: string,
      params: ViewParams = {},
      prefer: Surface | null = null,
      options?: NavigationOptions,
    ) => open({ viewId, params, prefer }, options),
    [open],
  );

  return { runtime, prompt, guard, openLink, openView };
}

/** The toast for a link or request that opens nothing. */
function refusalText(
  t: Translate,
  register: NavigationRegister,
  reason: ViewLinkRefusal | ViewRefusalReason,
  viewId: string | null,
): string {
  if (reason === "not_implemented") {
    const element = viewId === null ? undefined : elementOf(register, viewId);
    return t("desktop.navigation.refused.not_implemented", {
      view: element ? t(element.label) : (viewId ?? ""),
    });
  }
  if (reason === "unknown_view")
    return t("desktop.navigation.refused.unknown_view");
  if (SYNTAX_REFUSALS.has(reason as ViewLinkRefusal))
    return t("desktop.navigation.refused.link");
  return t("desktop.navigation.refused.param");
}

/** The notice for a view that opened other than asked. */
function noticeText(
  t: Translate,
  register: NavigationRegister,
  opened: ViewOpened,
  requested: string,
): string {
  const label = (id: string) => {
    const element = elementOf(register, id);
    return element ? t(element.label) : id;
  };
  const view = label(opened.opened);
  if (opened.fallback === "ancestor")
    return t("desktop.navigation.notice.ancestor", {
      requested: label(requested),
      view,
    });
  const where =
    opened.fallback === "other_surface"
      ? t(
          opened.surface === "tui"
            ? "desktop.navigation.notice.in_tui"
            : "desktop.navigation.notice.in_window",
          { view },
        )
      : null;
  const dropped =
    Object.keys(opened.params).length <
    Object.keys(opened.requested.params).length
      ? t("desktop.navigation.notice.params_dropped", { view })
      : null;
  return [where, dropped].filter((part) => part !== null).join(" ");
}
