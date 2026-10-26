import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const template = readFileSync(
  new URL("../src-tauri/src/shell/token.js", import.meta.url),
  "utf8",
);
const shellOrigin = "http://tauri.localhost";
const token = "0123456789abcdef".repeat(4);

// Mirrors ShellToken::script: JSON literals replace the two placeholders.
function render(origins) {
  return template
    .replace("__CADRUMO_SHELL_TOKEN__", JSON.stringify(token))
    .replace("__CADRUMO_SHELL_ORIGINS__", JSON.stringify(origins));
}

function frame({ origin, top }) {
  const sandbox = { location: { origin } };
  const context = vm.createContext(sandbox);
  vm.runInContext("var window = globalThis;", context);
  if (top) vm.runInContext("window.top = window;", context);
  else vm.runInContext("window.top = {};", context);
  vm.runInContext(render([shellOrigin]), context);
  return (expression) => vm.runInContext(expression, context);
}

test("the shell top frame receives the token exactly once", () => {
  const run = frame({ origin: shellOrigin, top: true });
  assert.equal(run("Object.keys(window).includes('__CADRUMO_SHELL__')"), false);
  assert.equal(run("Object.keys(window.__CADRUMO_SHELL__).length"), 0);
  assert.equal(run("window.__CADRUMO_SHELL__.token"), token);
  assert.equal(run("window.__CADRUMO_SHELL__.token"), undefined);
  assert.equal(run("'token' in window.__CADRUMO_SHELL__"), false);
});

test("a subframe on the shell origin receives nothing", () => {
  const run = frame({ origin: shellOrigin, top: false });
  assert.equal(run("typeof window.__CADRUMO_SHELL__"), "undefined");
});

test("a top frame on another origin receives nothing", () => {
  for (const origin of [
    "http://cadrumo-docs.localhost",
    "cadrumo-docs://localhost",
    "https://tauri.localhost",
    "null",
  ]) {
    const run = frame({ origin, top: true });
    assert.equal(run("typeof window.__CADRUMO_SHELL__"), "undefined", origin);
  }
});

test("the token appears only as the script argument", () => {
  const script = render([shellOrigin]);
  assert.equal(script.split(token).length, 2);
  for (const placeholder of [
    "__CADRUMO_SHELL_TOKEN__",
    "__CADRUMO_SHELL_ORIGINS__",
  ])
    assert.ok(!script.includes(placeholder), placeholder);
});
