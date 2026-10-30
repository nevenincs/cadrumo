import { isTauri } from "@tauri-apps/api/core";
import ReactDOM from "react-dom/client";
import { identity } from "virtual:desktop-content";
import { App } from "./App";
import { Toast } from "./components/ui/toast";
import { Titlebar } from "./components/Titlebar";
import { browserHost } from "./shell/host";
import { reportReactError } from "./shell/hostCall";
import { tauriHost } from "./shell/tauriHost";
import { SOURCE_LOCALE, translator } from "./shell/strings";
import "./index.css";

import "virtual:desktop-palette.css";

document.title = identity.name;
const root = document.getElementById("root");
if (!root) throw new Error("Application root is missing.");
const host = isTauri() ? tauriHost() : browserHost(window.location);
const application = ReactDOM.createRoot(root, {
  onUncaughtError: () => {
    reportReactError();
    application.render(
      <>
        <Titlebar
          host={host}
          onFailure={reportReactError}
          guardClose={(proceed) => proceed()}
        >
          {null}
        </Titlebar>
        <Toast role="alert" aria-live="assertive">
          {translator(document.documentElement.lang || SOURCE_LOCALE)(
            "desktop.error.internal",
          )}
        </Toast>
      </>,
    );
  },
  onCaughtError: reportReactError,
  onRecoverableError: reportReactError,
});
application.render(<App host={host} />);
