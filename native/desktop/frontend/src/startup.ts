import type { StartupPhase as Phase } from "./ipc/contract";
import { tauriStartup } from "./shell/tauriStartup";
import catalogue from "virtual:desktop-strings";
import "./styles/startup.css";
import "virtual:desktop-palette.css";

let locale = navigator.language.split("-")[0] ?? "en";
function text(key: string, code?: string): string {
  const full = `desktop.startup.${key}`;
  return (catalogue[locale]?.[full] ?? catalogue.en?.[full] ?? full).replace(
    "{code}",
    code ?? "",
  );
}
const phases: Phase[] = ["environment", "runtime", "workspace"];
const host = tauriStartup();
const status = document.querySelector<HTMLElement>("#status")!;
const failure = document.querySelector<HTMLElement>("#failure")!;
const main = document.querySelector("main")!;
document.documentElement.dataset.scheme = matchMedia(
  "(prefers-color-scheme: dark)",
).matches
  ? "dark"
  : "light";
document.documentElement.lang = locale;
status.textContent = text("starting");
document.querySelector("ol")!.setAttribute("aria-label", text("progress"));
for (const item of document.querySelectorAll<HTMLElement>("[data-phase]")) {
  item.textContent = text(`${item.dataset.phase}_step`);
}

function failed(message: string) {
  main.setAttribute("aria-busy", "false");
  status.textContent = text("failed");
  failure.textContent = message;
  failure.hidden = false;
}

async function refresh(): Promise<void> {
  try {
    const progress = await host!.status();
    if (progress.locale) locale = progress.locale;
    document.documentElement.lang = locale;
    status.textContent = text(progress.phase);
    document.querySelector("ol")!.setAttribute("aria-label", text("progress"));
    for (const item of document.querySelectorAll<HTMLElement>("[data-phase]")) {
      const phase = item.dataset.phase as Phase;
      item.textContent = text(`${phase}_step`);
      item.toggleAttribute(
        "data-complete",
        phases.indexOf(phase) < phases.indexOf(progress.phase),
      );
      if (phase === progress.phase) item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
    }
    if (progress.failure) {
      failed(text("failure", progress.failure.code));
      return;
    }
    window.setTimeout(() => void refresh(), 150);
  } catch {
    failed(text("interrupted"));
  }
}

// Two frames allow the loading page to paint before asking the host to assemble.
if (host) {
  requestAnimationFrame(() =>
    requestAnimationFrame(() => {
      void host
        .begin()
        .then(refresh)
        .catch(() => {
          failed(text("interrupted"));
        });
    }),
  );
}
