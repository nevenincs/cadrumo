import { isTauri } from "@tauri-apps/api/core";
import ReactDOM from "react-dom/client";
import { identity } from "virtual:desktop-content";
import { App } from "./App";
import { browserHost } from "./shell/host";
import { tauriHost } from "./shell/tauriHost";
import "./tokens.css";
import "./styles.css";

// The generated palette is optional at build time: before its generator has
// run the file is simply absent.
import.meta.glob("./generated/palette.css", { eager: true });

document.title = identity.name;
const root = document.getElementById("root");
if (!root) throw new Error("Application root is missing.");
const host = isTauri() ? tauriHost() : browserHost(window.location);
ReactDOM.createRoot(root).render(<App host={host} />);
