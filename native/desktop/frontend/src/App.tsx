import { useState } from "react";
import { identity, mark } from "virtual:desktop-content";
import { TerminalPane } from "./TerminalPane";

export function App() {
  const [terminalOpen, setTerminalOpen] = useState(false);
  return terminalOpen ? (
    <main className="terminal-page">
      <TerminalPane />
      <button
        className="back-button"
        onClick={() => setTerminalOpen(false)}
        aria-label="Back to front page"
      >
        ←
      </button>
    </main>
  ) : (
    <main className="front-page">
      <img src={mark} alt="" width="80" height="80" />
      <h1>{identity.display_name}</h1>
      <button onClick={() => setTerminalOpen(true)}>Open TUI</button>
    </main>
  );
}
