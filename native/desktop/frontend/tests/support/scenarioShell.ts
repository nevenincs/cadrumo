import { type Page } from "@playwright/test";
import { label } from "./strings";
import { useDomTerminal } from "./terminal";

// The development entry on the development server: the production shell on
// the scenario host, with the documentation fixture on another origin. These
// tests prove the scenarios present what they are named for. They are
// presentation evidence only; no host, runtime or sign-in is behind them.

export const open = async (target: Page, scenario: string, extra = "") => {
  await target.goto(`/scenarios.html?scenario=${scenario}&latency=0${extra}`);
  // Panel interaction tests open it explicitly after each fresh launch.
  await target.keyboard.press("Control+Backquote");
};

export const password = (target: Page) =>
  target.getByLabel(label("desktop.signin.password"), { exact: true });

export const submit = (target: Page) =>
  target.getByRole("button", {
    name: label("desktop.signin.submit"),
    exact: true,
  });

/** How many times the shell has made this host call in the current run. */
export const calls = (target: Page, call: string) => () =>
  target.evaluate(
    (name) =>
      (
        window as unknown as { __scenarioHostCalls?: string[] }
      ).__scenarioHostCalls?.filter((made) => made === name).length ?? 0,
    call,
  );

export const tui = (target: Page) =>
  target.locator('[data-terminal="tui"] textarea');

/** Starts a scenario from the documentation page with a DOM terminal. */
export const startFromDocs = async (target: Page) => {
  await useDomTerminal(target);
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    // These scenarios start from the documentation page; a test that needs
    // the TUI opens it, since no launch starts a terminal.
    localStorage.setItem(
      "cadrumo-shell-layout",
      JSON.stringify({ layout: { page: "docs" } }),
    );
    sessionStorage.setItem("layout-cleared", "1");
  });
};
