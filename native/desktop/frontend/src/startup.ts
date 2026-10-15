import { tauriStartup } from "./shell/tauriStartup";
import mark from "../../../../docs/_static/cadrumo-favicon.svg";
import { identity } from "virtual:desktop-content";
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
const host = tauriStartup();
const status = document.querySelector<HTMLElement>("#status")!;
const failure = document.querySelector<HTMLElement>("#failure")!;
const main = document.querySelector("main")!;
document.querySelector<HTMLImageElement>("#logo")!.src = mark;
document.querySelector("#name")!.textContent = identity.name;
document.title = identity.name;
document.documentElement.dataset.scheme = matchMedia(
  "(prefers-color-scheme: dark)",
).matches
  ? "dark"
  : "light";
document.documentElement.lang = locale;
status.textContent = text("starting");
function failed(message: string) {
  main.setAttribute("aria-busy", "false");
  status.textContent = text("failed");
  failure.textContent = message;
  failure.title = message;
  failure.hidden = false;
}

async function refresh(): Promise<void> {
  try {
    const progress = await host!.status();
    if (progress.locale) locale = progress.locale;
    document.documentElement.lang = locale;
    status.textContent = text(progress.phase);
    main.dataset.phase = progress.phase;
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
