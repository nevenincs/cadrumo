// Operating-system observations for the packaged run: the desktop session,
// windows, real input and processes, through desktop-input.ps1.
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

const SCRIPT = fileURLToPath(new URL("./desktop-input.ps1", import.meta.url));

/** The managed input helper needs no inherited native compiler search paths. */
export function desktopInputEnvironment(inherited = process.env) {
  return Object.fromEntries(
    Object.entries(inherited).filter(
      ([name]) => !["LIB", "LIBPATH"].includes(name.toUpperCase()),
    ),
  );
}

export class DesktopInput {
  constructor() {
    this.child = spawn(
      "powershell.exe",
      [
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        SCRIPT,
      ],
      {
        stdio: ["pipe", "pipe", "pipe"],
        windowsHide: true,
        env: desktopInputEnvironment(),
      },
    );
    this.pending = new Map();
    this.next = 0;
    this.errors = [];
    createInterface({ input: this.child.stdout }).on("line", (line) => {
      let reply;
      try {
        reply = JSON.parse(line.replace(/^﻿/, ""));
      } catch {
        return;
      }
      const waiting = this.pending.get(reply.id);
      if (!waiting) return;
      this.pending.delete(reply.id);
      if (reply.ok) waiting.resolve(reply.result);
      else waiting.reject(new Error(reply.error));
    });
    this.child.stderr.on("data", (data) => this.errors.push(String(data)));
    this.child.on("exit", () => {
      for (const waiting of this.pending.values())
        waiting.reject(
          new Error(`desktop input helper exited: ${this.errors.join("")}`),
        );
      this.pending.clear();
    });
  }

  request(op, fields = {}, timeout = 60000) {
    const id = (this.next += 1);
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`desktop input helper timed out on ${op}`));
      }, timeout);
      this.pending.set(id, {
        resolve: (value) => (clearTimeout(timer), resolve(value)),
        reject: (error) => (clearTimeout(timer), reject(error)),
      });
      this.child.stdin.write(`${JSON.stringify({ id, op, ...fields })}\n`);
    });
  }

  session() {
    return this.request("session");
  }

  async windows(pids) {
    const list = await this.request("windows", { pids });
    return Array.isArray(list) ? list : [];
  }

  activate(pid) {
    return this.request("activate", { pid });
  }

  client(pid) {
    return this.request("client", { pid });
  }

  chord(pid, key, modifiers = []) {
    return this.request("chord", { pid, key, modifiers });
  }

  click(pid, x, y, right = false) {
    return this.request("click", { pid, x, y, right });
  }

  post(pid, message, hwnd) {
    return this.request("post", { pid, message, ...(hwnd && { hwnd }) });
  }

  async processes(names) {
    const list = await this.request("processes", { names });
    return Array.isArray(list) ? list : [];
  }

  close() {
    this.child.stdin.end();
  }
}

/** A TCP port that was free a moment ago on the loopback interface. */
export function freePort() {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

/** Every process descended from `root` in a process list. */
export function descendants(list, root) {
  const found = [];
  const parents = new Set([root]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const process of list)
      if (parents.has(process.ppid) && !parents.has(process.pid)) {
        parents.add(process.pid);
        found.push(process);
        grew = true;
      }
  }
  return found;
}

/** The processes in `before` still running with the same start time. */
export function survivors(before, now) {
  const running = new Map(now.map((process) => [process.pid, process.created]));
  return before.filter(
    (process) => running.get(process.pid) === process.created,
  );
}
