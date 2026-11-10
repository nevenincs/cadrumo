#!/usr/bin/env node
// One exploratory action per invocation, with a persistent native session.
import {
  appendFileSync,
  readFileSync,
  writeFileSync,
  existsSync,
} from "node:fs";
import { randomBytes } from "node:crypto";
import { resolve } from "node:path";
import {
  start,
  stop,
  connect,
  within,
  readSession,
  verifyListener,
  queuePickerSelection,
} from "./session.mjs";

const [command, session, ...args] = process.argv.slice(2);
const print = (value) => console.log(JSON.stringify(value, null, 2));

async function visibleElement(browser, selector) {
  const element = await browser.$(selector);
  await element.waitForExist({ timeout: 10000 });
  // The embedded WebKit driver can report isDisplayed=false for visible
  // controls. Check layout in the actual webview before using native actions.
  await browser.waitUntil(
    () =>
      browser.execute((node) => {
        if (!node?.isConnected || !node.getClientRects().length) return false;
        const style = getComputedStyle(node);
        return style.visibility !== "hidden" && style.visibility !== "collapse";
      }, element),
    { timeout: 10000, timeoutMsg: `Control is not visible: ${selector}` },
  );
  return element;
}

try {
  if (!command || command === "help") {
    console.log(`Native exploratory automation (macOS: ps and lsof required; Windows: PowerShell and netstat required)
Build: cmake --build --preset macos-arm64-debug --target bundle desktop-packaged-host
Set CADRUMO_CMAKE_BINARY_DIR to the absolute build/macos-arm64 path and CADRUMO_BUILD_CONFIG=Debug.
On Windows use the windows-x64 preset and build path; the host is confirmed by exact PID
and image path, and the WebDriver page must return the nonce this launch gave it; anything else refuses.
The host starts without taking the foreground or focus on the desktop.
Start: node native/desktop/tests/automation/cli.mjs start
The result names a SESSION file. Keep it for subsequent commands:
  windows SESSION | window SESSION main | snapshot SESSION
  click SESSION SELECTOR | fill SESSION SELECTOR TEXT
  fill-secret SESSION SELECTOR SECRET-NAME (generated synthetic credential, never printed)
  select SESSION SELECTOR VALUE | keys SESSION KEY...
  frame SESSION SELECTOR | parent SESSION
  screenshot SESSION NAME.png
  choose-file SESSION open|save ABSOLUTE-PATH (queue answer, then click the real chooser control)
  cancel-file SESSION open|save (queue cancellation, then click the real chooser control)
  export-file SESSION ABSOLUTE-PATH (verifies output is under this run's exports directory)
  stop SESSION | resume SESSION (same synthetic storage after stopping/rebuilding)
Use real GUI controls for all account, ledger and Modelo changes. Save exports into run/exports.
No fixture seeding, tax flow or backend-command shortcut is built into this harness.`);
  } else if (command === "start") {
    print(await start());
  } else if (command === "resume") {
    print(await start(session));
  } else if (command === "stop") {
    print(await stop(session));
  } else if (command === "choose-file" || command === "cancel-file") {
    if (args.length !== (command === "choose-file" ? 2 : 1))
      throw new Error(
        "Supply a chooser kind and, for choose-file, an absolute path.",
      );
    const state = readSession(session);
    verifyListener(state);
    print(
      queuePickerSelection(
        state.run,
        args[0],
        command === "choose-file" ? args[1] : null,
      ),
    );
  } else {
    const { browser, state } = await connect(session);
    let result;
    switch (command) {
      case "windows":
        result = await browser.getWindowHandles();
        break;
      case "window":
        await browser.switchToWindow(args[0]);
        result = { window: args[0] };
        break;
      case "frame":
        await browser.switchFrame(await browser.$(args[0]));
        result = { frame: args[0] };
        break;
      case "parent":
        await browser.switchToParentFrame();
        result = { parent: true };
        break;
      case "snapshot":
        result = await browser.execute(() => {
          const visible = (element) =>
            element.getClientRects().length &&
            getComputedStyle(element).visibility !== "hidden";
          const text = (element) =>
            (element.innerText || element.textContent || "")
              .trim()
              .slice(0, 160);
          const scope =
            [...document.querySelectorAll('[role="dialog"], dialog[open]')]
              .filter(visible)
              .at(-1) || document.body;
          return {
            title: document.title,
            dialog: scope !== document.body,
            text: scope.innerText.slice(0, 14000),
            controls: [
              ...scope.querySelectorAll(
                "button,input,textarea,select,a,[role=button],[role=combobox],[role=tab],[role=checkbox]",
              ),
            ]
              .filter(visible)
              .slice(0, 150)
              .map((element) => ({
                tag: element.tagName.toLowerCase(),
                id: element.id || undefined,
                role: element.getAttribute("role") || undefined,
                type: element.getAttribute("type") || undefined,
                label:
                  element.getAttribute("aria-label") ||
                  element.labels?.[0]?.innerText ||
                  undefined,
                placeholder: element.getAttribute("placeholder") || undefined,
                text: text(element),
                disabled: element.disabled || undefined,
                checked: element.checked ?? undefined,
                options:
                  element.tagName === "SELECT"
                    ? [...element.options].map((option) => ({
                        value: option.value,
                        text: option.text,
                      }))
                    : undefined,
              })),
          };
        });
        break;
      case "click": {
        const element = await visibleElement(browser, args[0]);
        await element.click();
        result = { clicked: args[0] };
        break;
      }
      case "fill": {
        const element = await visibleElement(browser, args[0]);
        await element.setValue(args[1]);
        result = { filled: args[0] };
        break;
      }
      case "fill-secret": {
        if (!/^[a-z][a-z0-9-]{0,40}$/.test(args[1] || ""))
          throw new Error("Supply a synthetic secret name.");
        const file = resolve(state.run, `${args[1]}.secret`);
        if (!existsSync(file))
          writeFileSync(
            file,
            `Synthetic-${randomBytes(24).toString("base64url")}!`,
            { mode: 0o600, flag: "wx" },
          );
        const secret = readFileSync(within(state.run, file), "utf8");
        const element = await visibleElement(browser, args[0]);
        await element.setValue(secret);
        result = { filled: args[0], syntheticSecret: args[1] };
        break;
      }
      case "select": {
        const element = await visibleElement(browser, args[0]);
        await browser.execute(
          (node, value) => {
            if (
              !(node instanceof HTMLSelectElement) ||
              node.disabled ||
              node.multiple
            )
              throw new Error("Expected an enabled single-selection control.");
            const option = [...node.options].find(
              (item) => item.value === value,
            );
            if (!option || option.disabled || option.parentElement?.disabled)
              throw new Error("The requested option is unavailable.");
            // WKWebView's WebDriver option click may return without changing the
            // select. Use its DOM setter and normal input/change event path.
            const setter = Object.getOwnPropertyDescriptor(
              HTMLSelectElement.prototype,
              "value",
            ).set;
            setter.call(node, value);
            node.dispatchEvent(new Event("input", { bubbles: true }));
            node.dispatchEvent(new Event("change", { bubbles: true }));
            if (node.value !== value)
              throw new Error("Selection did not take effect.");
          },
          element,
          args[1],
        );
        result = { selected: args[0] };
        break;
      }
      case "keys":
        await browser.keys(args);
        result = { keys: true };
        break;
      case "export-file": {
        const file = within(resolve(state.run, "exports"), args[0]);
        result = { export: file, bytes: readFileSync(file).length };
        break;
      }
      case "screenshot": {
        if (!/^[a-z0-9-]+\.png$/.test(args[0] || ""))
          throw new Error("Supply a plain PNG filename.");
        const file = resolve(state.run, args[0]);
        await browser.saveScreenshot(file);
        result = { screenshot: file };
        break;
      }
      default:
        throw new Error(
          "Commands: start, stop SESSION, choose-file/cancel-file/snapshot/windows/window/frame/parent/click/fill/fill-secret/select/keys/screenshot SESSION [arguments]",
        );
    }
    // Action types only: field values and secret material never enter this log.
    appendFileSync(
      resolve(state.run, "actions.jsonl"),
      JSON.stringify({ at: new Date().toISOString(), command }) + "\n",
      { mode: 0o600 },
    );
    print(result);
  }
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
