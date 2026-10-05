// Deterministic terminal sessions for the scenario host. They feed the real
// xterm view the same event sequence a host session would: `started`, `data`
// frames, then `exited`. Nothing runs behind them, and every reply says so.

import type {
  TerminalEvent,
  TerminalKind,
  TerminalSession,
} from "../../shell/host";

const encoder = new TextEncoder();
const decoder = new TextDecoder();

const ESC = "\x1b";
const RESET = `${ESC}[0m`;
const DIM = `${ESC}[2m`;
const BOLD = `${ESC}[1m`;
const REVERSE = `${ESC}[7m`;
const ACCENT = `${ESC}[33m`;

type Size = { cols: number; rows: number };

type Program = {
  start(): void;
  input(text: string): void;
  resize(size: Size): void;
};

type Io = {
  write(text: string): void;
  exit(code: number): void;
};

/** Drops escape sequences (arrow keys, function keys, bracketed paste marks):
 * they are not text for a line. A CSI sequence runs to its final byte, any
 * other escape takes one character. */
function withoutControlSequences(text: string): string {
  let plain = "";
  for (let at = 0; at < text.length; at++) {
    if (text[at] !== ESC) {
      plain += text[at];
      continue;
    }
    at++;
    if (text[at] !== "[") continue;
    // A CSI sequence ends at its final byte, "@" through "~".
    let code: number;
    do code = text.charCodeAt(++at);
    while (at < text.length && (code < 0x40 || code > 0x7e));
  }
  return plain;
}

/** A prompt with line editing: enough to type, correct and submit a line. */
function lineShell(
  io: Io,
  options: {
    banner: string;
    prompt: string;
    exits: readonly string[];
    reply: (line: string) => string;
  },
): Program {
  let line = "";
  const prompt = () => io.write(options.prompt);
  return {
    start() {
      io.write(options.banner);
      prompt();
    },
    input(text) {
      for (const char of withoutControlSequences(text)) {
        if (char === "\r" || char === "\n") {
          io.write("\r\n");
          const entered = line.trim();
          line = "";
          if (options.exits.includes(entered)) return io.exit(0);
          if (entered) io.write(`${DIM}${options.reply(entered)}${RESET}\r\n`);
          prompt();
        } else if (char === "\x7f" || char === "\b") {
          if (!line) continue;
          line = line.slice(0, -1);
          io.write("\b \b");
        } else if (char === "\x03") {
          line = "";
          io.write("^C\r\n");
          prompt();
        } else if (char >= " ") {
          line += char;
          io.write(char);
        }
      }
    },
    resize() {},
  };
}

const pad = (text: string, width: number) =>
  text.length >= width ? text.slice(0, width) : text.padEnd(width, " ");

/** A full-screen application on the alternate screen, redrawn on resize. */
function fullScreen(io: Io, initial: Size): Program {
  let size = initial;
  const draw = () => {
    const { cols, rows } = size;
    const lines: string[] = [];
    lines.push(
      `${REVERSE}${pad(" CADRUMO   Simulated TUI session", cols)}${RESET}`,
    );
    lines.push("");
    lines.push(
      pad(
        `  ${BOLD}Home${RESET}   Declarations   Ledger   AEAT Sync`,
        cols + 8,
      ),
    );
    lines.push(`  ${DIM}${"─".repeat(Math.max(0, cols - 4))}${RESET}`);
    lines.push("");
    lines.push(`  ${ACCENT}This screen is a development fixture.${RESET}`);
    lines.push("  No runtime, profile or session is behind it.");
    lines.push("");
    lines.push(`  ${DIM}It exists so the pane, its header and its focus`);
    lines.push(`  behaviour can be designed in a browser.${RESET}`);
    const footer = `${REVERSE}${pad(" q Quit    Enter restarts an exited session", cols)}${RESET}`;
    const body = lines.slice(0, Math.max(0, rows - 1));
    while (body.length < rows - 1) body.push("");
    io.write(`${ESC}[H${ESC}[2J${[...body, footer].join("\r\n")}`);
  };
  return {
    start() {
      io.write(`${ESC}[?1049h${ESC}[?25l`);
      draw();
    },
    input(text) {
      if (text !== "q" && text !== "Q") return;
      io.write(`${ESC}[?25h${ESC}[?1049l`);
      io.exit(0);
    },
    resize(next) {
      size = next;
      draw();
    },
  };
}

function program(kind: TerminalKind, io: Io, size: Size): Program {
  if (kind === "tui") return fullScreen(io, size);
  if (kind === "python")
    return lineShell(io, {
      banner: `CADRUMO (simulated), Python [development scenario]\r\n${DIM}Nothing evaluates here. exit() ends the session.${RESET}\r\n`,
      prompt: ">>> ",
      exits: ["exit()", "quit()"],
      reply: () => "simulated session: nothing was evaluated",
    });
  return lineShell(io, {
    banner: `${DIM}Simulated console. No shell is running. exit ends the session.${RESET}\r\n`,
    prompt: "PS C:\\Users\\demo> ",
    exits: ["exit"],
    reply: (line) => `simulated session: "${line}" was not run`,
  });
}

/**
 * Opens a fixture session. `silent` starts and prints nothing, which is what
 * an idle or just-started child looks like.
 */
export function openFixtureTerminal(
  kind: TerminalKind,
  size: Size,
  listener: (event: TerminalEvent) => void,
  mode: "fixture" | "silent",
): TerminalSession {
  let open = true;
  const io: Io = {
    write(text) {
      if (!open) return;
      listener({
        type: "data",
        bytes: encoder.encode(text),
        drawn: () => undefined,
      });
    },
    exit(code) {
      if (!open) return;
      open = false;
      listener({ type: "exited", code });
    },
  };
  const running = mode === "fixture" ? program(kind, io, size) : null;
  // After the open call resolves, as a host session's first frame usually is.
  window.setTimeout(() => {
    if (!open) return;
    listener({ type: "started" });
    running?.start();
  }, 0);
  return {
    write(bytes) {
      if (open) running?.input(decoder.decode(bytes));
      return Promise.resolve();
    },
    resize(cols, rows) {
      if (open) running?.resize({ cols, rows });
      return Promise.resolve();
    },
    close() {
      open = false;
      return Promise.resolve();
    },
  };
}
