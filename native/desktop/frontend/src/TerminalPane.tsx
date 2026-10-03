import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { identity } from "virtual:desktop-content";
import "@xterm/xterm/css/xterm.css";

export function TerminalPane({ mode }: { mode: "python" | "tui" }) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current) return;
    const terminal = new Terminal({
      disableStdin: true,
      cursorBlink: false,
      fontFamily: "Cascadia Code, Consolas, monospace",
      fontSize: 13,
      lineHeight: 1.5,
      scrollback: 1500,
      screenReaderMode: true,
      theme: {
        background: "#172320",
        foreground: "#cedbd4",
        selectionBackground: "#476457",
      },
    });
    const fit = new FitAddon();
    terminal.loadAddon(fit);
    terminal.open(container.current);
    terminal.writeln(
      `\x1b[1;32m${identity.display_name}\x1b[0m  ${mode === "python" ? "Python console" : "Textual workbench"}`,
    );
    terminal.writeln("");
    terminal.writeln(
      "Not connected. The bundled environment is not available in this preview.",
    );
    terminal.writeln(
      "Your workspace and local documentation remain available.",
    );
    let frame = 0;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (container.current?.clientWidth && container.current.clientHeight)
          fit.fit();
      });
    });
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
      terminal.dispose();
    };
  }, [mode]);
  return (
    <div
      className="terminal-surface"
      ref={container}
      aria-label={`${mode === "python" ? "Python console" : "Textual workbench"} output`}
    />
  );
}
