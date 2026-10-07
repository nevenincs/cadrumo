import { useEffect, useRef, useState } from "react";
import { Terminal, type ITheme } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import {
  HostUnavailable,
  type Host,
  type TerminalKind,
  type TerminalSession,
} from "../shell/host";
import { useStrings } from "../shell/strings";
import { failureCode } from "../errors";
import { terminalFont } from "../shell/terminalFont";
import { terminalRenderer } from "../shell/terminalRenderer";
import { Empty, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";

export type TerminalStatus =
  | { phase: "starting" }
  | { phase: "running" }
  | { phase: "exited"; code: number | null }
  | { phase: "failed"; message: string }
  | { phase: "unavailable" };

export type TerminalApi = {
  focus(): void;
  selection(): string;
  hasSelection(): boolean;
  selectAll(): void;
  clear(): void;
  paste(text: string): void;
};

const DIM = "\x1b[2m";
const RESET = "\x1b[0m";

type Props = {
  host: Host;
  kind: TerminalKind;
  shown: boolean;
  theme: ITheme;
  fontSize: number;
  label: string;
  isShellChord: (event: KeyboardEvent) => boolean;
  onStatus: (kind: TerminalKind, status: TerminalStatus) => void;
  onMenu: (event: MouseEvent, kind: TerminalKind) => void;
  register: (kind: TerminalKind, api: TerminalApi) => void;
  /** Render as the bottom panel's tab panel for this kind. */
  tabPanel?: boolean;
};

export function TerminalPane({
  host,
  kind,
  shown,
  theme,
  fontSize,
  label,
  isShellChord,
  onStatus,
  onMenu,
  register,
  tabPanel,
}: Props) {
  const t = useStrings();
  const container = useRef<HTMLDivElement>(null);
  const terminal = useRef<{ term: Terminal; fit: FitAddon } | null>(null);
  // Optional terminals acquire resources only when first opened. Once used,
  // keep their buffer and session while hidden; the account gate owns TUI.
  const [activated, setActivated] = useState(kind === "tui" || shown);
  if (shown && !activated) setActivated(true);
  // The session effect runs once per pane; everything else it reads is live.
  const live = useRef({
    isShellChord,
    onStatus,
    onMenu,
    register,
    theme,
    fontSize,
    t,
    shown,
  });
  live.current = {
    isShellChord,
    onStatus,
    onMenu,
    register,
    theme,
    fontSize,
    t,
    shown,
  };
  const [unavailable, setUnavailable] = useState(false);
  const [fontFamily, setFontFamily] = useState<string | null>(null);

  useEffect(() => {
    if (!activated) return;
    let cancelled = false;
    void terminalFont().then((family) => {
      if (!cancelled) setFontFamily(family);
    });
    return () => {
      cancelled = true;
    };
  }, [activated]);

  useEffect(() => {
    if (!activated || !fontFamily) return;
    const element = container.current;
    if (!element) return;
    const term = new Terminal({
      cursorBlink: true,
      fontFamily,
      fontSize: live.current.fontSize,
      lineHeight: 1,
      rescaleOverlappingGlyphs: true,
      scrollback: 5000,
      theme: live.current.theme,
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(element);
    const disposeRenderer = terminalRenderer(term, () => {
      if (element.clientWidth > 0 && element.clientHeight > 0) fit.fit();
    });
    terminal.current = { term, fit };
    // Shell chords never reach the session; every other key belongs to it.
    term.attachCustomKeyEventHandler(
      (event) =>
        !(event.type === "keydown" && live.current.isShellChord(event)),
    );

    let disposed = false;
    let session: TerminalSession | null = null;
    let exited = false;
    let mouseTracking = false;
    let queue = Promise.resolve();
    const status = (next: TerminalStatus) => {
      if (!disposed) live.current.onStatus(kind, next);
    };

    // Input is queued in order and never dropped: the host's write queue
    // applies backpressure, so even a very large paste arrives whole.
    const send = (bytes: Uint8Array) => {
      const target = session;
      if (!target || disposed) return;
      queue = queue
        .then(() => target.write(bytes))
        .catch((error: unknown) =>
          status({ phase: "failed", message: failureCode(error) }),
        );
    };

    const start = () => {
      exited = false;
      term.reset();
      status({ phase: "starting" });
      host
        .openTerminal(kind, { cols: term.cols, rows: term.rows }, (event) => {
          if (disposed) return;
          if (event.type === "data") {
            // Acknowledge only what xterm has drawn: the host pauses the PTY
            // instead of dropping output when the view falls behind.
            term.write(event.bytes, event.drawn);
          } else if (event.type === "started") {
            status({ phase: "running" });
          } else if (event.type === "exited") {
            session = null;
            exited = true;
            mouseTracking = false;
            term.write(
              `\r\n${DIM}${live.current.t("desktop.session.exit_line", { code: event.code ?? "?" })}${RESET}\r\n`,
            );
            status({ phase: "exited", code: event.code });
          } else {
            session = null;
            exited = true;
            term.write(
              `\r\n${DIM}${live.current.t("desktop.session.failed", { reason: event.message })}${RESET}\r\n`,
            );
            status({ phase: "failed", message: event.message });
          }
        })
        .then((opened) => {
          if (disposed) {
            void opened.close();
            return;
          }
          session = opened;
          void opened.resize(term.cols, term.rows);
        })
        .catch((error: unknown) => {
          if (error instanceof HostUnavailable) {
            setUnavailable(true);
            status({ phase: "unavailable" });
          } else {
            exited = true;
            status({ phase: "failed", message: failureCode(error) });
          }
        });
    };

    const encoder = new TextEncoder();
    const input = term.onData((data) => {
      if (session) send(encoder.encode(data));
      else if (exited && data === "\r") start();
    });
    const binary = term.onBinary((data) =>
      send(Uint8Array.from(data, (char) => char.charCodeAt(0))),
    );
    // Applications that enable mouse reporting own plain right-click.
    const modes = term.parser.registerCsiHandler(
      { prefix: "?", final: "h" },
      (params) => {
        if (params.some((p) => p === 1000 || p === 1002 || p === 1003))
          mouseTracking = true;
        return false;
      },
    );
    const modesOff = term.parser.registerCsiHandler(
      { prefix: "?", final: "l" },
      (params) => {
        if (params.some((p) => p === 1000 || p === 1002 || p === 1003))
          mouseTracking = false;
        return false;
      },
    );
    const resized = term.onResize(
      ({ cols, rows }) => void session?.resize(cols, rows),
    );

    const menu = (event: MouseEvent) => {
      if (mouseTracking && !event.shiftKey) return;
      event.preventDefault();
      live.current.onMenu(event, kind);
    };
    element.addEventListener("contextmenu", menu);

    live.current.register(kind, {
      focus: () => {
        if (live.current.shown && element.offsetParent !== null) term.focus();
      },
      selection: () => term.getSelection(),
      hasSelection: () => term.hasSelection(),
      selectAll: () => term.selectAll(),
      clear: () => term.clear(),
      paste: (text) => term.paste(text),
    });

    let frame = 0;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (element.clientWidth > 0 && element.clientHeight > 0) fit.fit();
      });
    });
    observer.observe(element);
    if (element.clientWidth > 0 && element.clientHeight > 0) fit.fit();
    start();

    return () => {
      disposed = true;
      observer.disconnect();
      cancelAnimationFrame(frame);
      element.removeEventListener("contextmenu", menu);
      input.dispose();
      binary.dispose();
      modes.dispose();
      modesOff.dispose();
      resized.dispose();
      // Close at once: closing stops any write still waiting on the host's
      // queue, so it cannot hold the session open.
      void session?.close().catch(() => undefined);
      disposeRenderer();
      term.dispose();
      terminal.current = null;
    };
  }, [host, kind, activated, fontFamily]);

  useEffect(() => {
    if (terminal.current) terminal.current.term.options.theme = theme;
  }, [theme]);

  useEffect(() => {
    const current = terminal.current;
    if (!current) return;
    current.term.options.fontSize = fontSize;
    const frame = requestAnimationFrame(() => {
      const element = container.current;
      if (element && element.clientWidth > 0 && element.clientHeight > 0)
        current.fit.fit();
    });
    return () => cancelAnimationFrame(frame);
  }, [fontSize]);

  return (
    <div
      className="relative min-h-0 flex-1"
      hidden={!shown}
      style={{ background: theme.background }}
      aria-label={label}
      data-terminal={kind}
      // Named, so it needs a role: the TUI's frame is a group, a panel
      // terminal the tab panel of its tab.
      role={tabPanel ? "tabpanel" : "group"}
      id={tabPanel ? `panel-${kind}` : undefined}
      aria-labelledby={tabPanel ? `tab-${kind}` : undefined}
    >
      {/* Without a host there is no session to show: keep the terminal's
          size for fitting but draw only the note, not an idle cursor. */}
      <div
        className="terminal-host absolute inset-y-1.5 right-1 left-3"
        ref={container}
        style={unavailable ? { visibility: "hidden" } : undefined}
      />
      {unavailable && (
        <Empty role="status" className="absolute inset-0">
          <EmptyMedia>
            <Icon name="unplug" />
          </EmptyMedia>
          <EmptyDescription className="terminal-note">
            {t("desktop.host.unavailable")}
          </EmptyDescription>
        </Empty>
      )}
    </div>
  );
}
