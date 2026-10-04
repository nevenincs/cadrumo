import { TerminalView } from "./components/TerminalView";
import { DiagnosticsPanel } from "./components/DiagnosticsPanel";
import { useEffect, useState } from "react";

export function App() {
  const [logs, setLogs] = useState(false);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.shiftKey && event.code === "KeyL") {
        event.preventDefault();
        event.stopPropagation();
        setLogs((open) => !open);
      }
    };
    window.addEventListener("keydown", key, true);
    return () => window.removeEventListener("keydown", key, true);
  }, []);
  return (
    <main className="terminal-page">
      <TerminalView />
      {logs && <DiagnosticsPanel close={() => setLogs(false)} />}
    </main>
  );
}
