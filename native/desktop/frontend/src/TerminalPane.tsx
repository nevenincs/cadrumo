import { useEffect, useRef, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { failureMessage, type HostFailure } from "./failure";

type Output = {
  bytes: number[];
  exitCode: number | null;
  error: HostFailure | null;
};

export function TerminalPane() {
  const container = useRef<HTMLDivElement>(null);
  const [failure, setFailure] = useState<string | null>(null);
  useEffect(() => {
    if (!container.current) return;
    const terminal = new Terminal({
      disableStdin: true,
      cursorBlink: true,
      fontFamily: "Cascadia Code, Consolas, monospace",
      fontSize: 14,
      scrollback: 1500,
      screenReaderMode: true,
      theme: { background: "#172320", foreground: "#cedbd4" },
    });
    const fit = new FitAddon();
    terminal.loadAddon(fit);
    terminal.open(container.current);
    fit.fit();
    let disposed = false;
    let started = false;
    let frame = 0;
    let pollTimer = 0;
    let inputQueue = Promise.resolve();
    let pendingBytes = 0;
    const fail = (error: unknown) => {
      if (!disposed) {
        terminal.options.disableStdin = true;
        setFailure(failureMessage(error));
      }
    };
    const send = (bytes: Uint8Array) => {
      if (!started || disposed || terminal.options.disableStdin) return;
      if (pendingBytes + bytes.length > 262144) {
        fail("Terminal input queue is full");
        return;
      }
      pendingBytes += bytes.length;
      inputQueue = inputQueue
        .then(async () => {
          try {
            for (
              let offset = 0;
              offset < bytes.length && !disposed;
              offset += 16384
            ) {
              await invoke("terminal_input", {
                data: Array.from(bytes.subarray(offset, offset + 16384)),
              });
            }
          } finally {
            pendingBytes -= bytes.length;
          }
        })
        .catch(fail);
    };
    const input = terminal.onData((data) =>
      send(new TextEncoder().encode(data)),
    );
    const binary = terminal.onBinary((data) =>
      send(Uint8Array.from(data, (char) => char.charCodeAt(0))),
    );
    const resize = () => {
      if (container.current?.clientWidth && container.current.clientHeight) {
        fit.fit();
        if (started)
          void invoke("terminal_resize", {
            cols: terminal.cols,
            rows: terminal.rows,
          }).catch(fail);
      }
    };
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(resize);
    });
    observer.observe(container.current);
    const poll = async () => {
      try {
        const output = await invoke<Output>("terminal_read");
        if (disposed) return;
        if (output.bytes.length) {
          await new Promise<void>((resolve) =>
            terminal.write(new Uint8Array(output.bytes), resolve),
          );
        }
        if (output.error) throw output.error;
        if (output.exitCode !== null) {
          terminal.options.disableStdin = true;
          if (output.exitCode !== 0)
            fail(`TUI exited with code ${output.exitCode}`);
          return;
        }
        if (!disposed)
          pollTimer = window.setTimeout(
            () => void poll(),
            output.bytes.length ? 0 : 16,
          );
      } catch (error) {
        fail(error);
      }
    };
    const startup = isTauri()
      ? invoke("terminal_start", { cols: terminal.cols, rows: terminal.rows })
          .then(async () => {
            started = true;
            if (disposed) {
              await invoke("terminal_stop");
              return;
            }
            terminal.options.disableStdin = false;
            resize();
            terminal.focus();
            void poll();
          })
          .catch(fail)
      : Promise.resolve();
    return () => {
      disposed = true;
      observer.disconnect();
      cancelAnimationFrame(frame);
      clearTimeout(pollTimer);
      input.dispose();
      binary.dispose();
      terminal.dispose();
      void startup
        .then(() => started && invoke("terminal_stop"))
        .catch(() => {});
    };
  }, []);
  return (
    <>
      <div
        className="terminal-surface"
        ref={container}
        aria-label="TUI terminal"
      />
      {failure && (
        <div className="terminal-error" role="alert">
          {failure}
        </div>
      )}
    </>
  );
}
