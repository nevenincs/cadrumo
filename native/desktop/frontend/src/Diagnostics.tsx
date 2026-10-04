import { useEffect, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { failureMessage, type HostFailure } from "./failure";

type ProcessStatus = {
  id: number;
  pid: number;
  role: string;
  phase: string;
  exitCode: number | null;
  stdoutBytes: number;
  stderrBytes: number;
  terminalBytes: number;
};
type Event = {
  timestampMs: number;
  kind: string;
  process: number | null;
  failure: HostFailure | null;
};
type Chunk = {
  sequence: number;
  process: number;
  stream: string;
  bytes: number[];
};
type Snapshot = {
  paths: { current: string } | null;
  logFailure: HostFailure | null;
  processes: ProcessStatus[];
  events: Event[];
  output: Chunk[];
  droppedBytes: number;
};

export function Diagnostics({ close }: { close: () => void }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  useEffect(() => {
    let disposed = false;
    let timer = 0;
    const refresh = async () => {
      if (!isTauri()) {
        setFailure(
          "Native diagnostics are available in the desktop application.",
        );
        return;
      }
      try {
        const state = await invoke<Snapshot>("diagnostics_snapshot", {
          after: 0,
        });
        if (!disposed) setSnapshot(state);
      } catch (error) {
        if (!disposed) setFailure(failureMessage(error));
      }
      if (!disposed) timer = window.setTimeout(() => void refresh(), 500);
    };
    void refresh();
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, []);
  const decoders = new Map<string, TextDecoder>();
  return (
    <aside className="diagnostics" aria-label="Application logs">
      <header>
        <strong>Application logs</strong>
        <button onClick={close}>Close logs</button>
      </header>
      {failure && <p role="alert">{failure}</p>}
      {snapshot && (
        <>
          <p>{snapshot.paths?.current ?? "File logging unavailable"}</p>
          {snapshot.logFailure && (
            <p role="alert">{failureMessage(snapshot.logFailure)}</p>
          )}
          <table>
            <thead>
              <tr>
                <th>Process</th>
                <th>PID</th>
                <th>Status</th>
                <th>Exit</th>
                <th>Output bytes</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.processes.map((process) => (
                <tr key={process.id}>
                  <td>{process.role}</td>
                  <td>{process.pid}</td>
                  <td>{process.phase}</td>
                  <td>{process.exitCode ?? "—"}</td>
                  <td>
                    {process.stdoutBytes +
                      process.stderrBytes +
                      process.terminalBytes}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <pre>
            {snapshot.events
              .map(
                (event) =>
                  `${new Date(event.timestampMs).toISOString()} ${event.kind}${event.failure ? ` ${failureMessage(event.failure)}` : ""}`,
              )
              .join("\n")}
          </pre>
          {snapshot.droppedBytes > 0 && (
            <p>{snapshot.droppedBytes} earlier output bytes discarded.</p>
          )}
          <pre aria-label="Captured child output">
            {snapshot.output
              .map((chunk) => {
                const key = `${chunk.process}:${chunk.stream}`;
                const decoder = decoders.get(key) ?? new TextDecoder();
                decoders.set(key, decoder);
                return decoder.decode(new Uint8Array(chunk.bytes), {
                  stream: true,
                });
              })
              .join("")}
          </pre>
        </>
      )}
    </aside>
  );
}
