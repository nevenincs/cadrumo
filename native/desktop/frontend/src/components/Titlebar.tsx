import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { WindowAction, WindowPresentation } from "../ipc/contract";
import type { Host } from "../shell/host";
import { useStrings } from "../shell/strings";
import { Logo } from "./Logo";
import { identity } from "virtual:desktop-content";

export function Titlebar({
  host,
  children,
  onFailure,
}: {
  host: Host;
  children: ReactNode;
  onFailure: () => void;
}) {
  const t = useStrings();
  const [state, setState] = useState<WindowPresentation | null>(null);
  const fail = useRef(onFailure);
  fail.current = onFailure;
  const native = host.window;
  useEffect(() => {
    if (!native) return;
    let active = true;
    let stop: (() => void) | undefined;
    void native
      .observe((next) => {
        if (active) setState(next);
      })
      .then(
        (close) => {
          if (active) stop = close;
          else close();
        },
        () => {
          if (active) fail.current();
        },
      );
    return () => {
      active = false;
      stop?.();
    };
  }, [native]);
  const run = useCallback(
    (action: WindowAction) => {
      if (native) void native.action(action).catch(() => fail.current());
    },
    [native],
  );
  const dragging = (event: React.MouseEvent) => {
    if (event.button !== 0 || (event.target as Element).closest("button"))
      return;
    if (event.detail === 2) {
      if (state && !state.fullscreen) run("toggle_maximize");
    } else run("drag");
  };
  return (
    <header className="titlebar" aria-label={t("desktop.titlebar.label")}>
      <h1
        className="titlebar-brand"
        aria-label={identity.name}
        onMouseDown={dragging}
      >
        <Logo size="sm" />
      </h1>
      <div
        className="titlebar-drag-space"
        aria-hidden="true"
        onMouseDown={dragging}
      />
      <div className="titlebar-account">{children}</div>
      <div className="window-controls">
        <Button
          variant="ghost"
          size="icon-lg"
          className="window-control"
          disabled={!native}
          aria-label={t("desktop.titlebar.minimize")}
          title={t("desktop.titlebar.minimize")}
          onClick={() => run("minimize")}
        >
          <span className="window-glyph minimize" aria-hidden="true" />
        </Button>
        <Button
          variant="ghost"
          size="icon-lg"
          className="window-control"
          disabled={!native || !state || state.fullscreen}
          aria-label={t(
            state?.maximized
              ? "desktop.titlebar.restore"
              : "desktop.titlebar.maximize",
          )}
          title={t(
            state?.maximized
              ? "desktop.titlebar.restore"
              : "desktop.titlebar.maximize",
          )}
          onClick={() => run("toggle_maximize")}
        >
          <Icon
            name={state?.maximized ? "windowRestore" : "windowMaximize"}
            size="xs"
          />
        </Button>
        <Button
          variant="ghost"
          size="icon-lg"
          className="window-control window-close"
          disabled={!native}
          aria-label={t("desktop.titlebar.close")}
          title={t("desktop.titlebar.close")}
          onClick={() => run("close")}
        >
          <Icon name="close" size="xs" />
        </Button>
      </div>
    </header>
  );
}
