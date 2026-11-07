import type { PaneControl } from "../components/PaneHeader";
import { primaryChord, type Action } from "./actions";
import type { Maximized, Prefs } from "./layout";
import type { Translate } from "./strings";

/** The controls a pane's header carries for the arrangement: maximize or
 * restore the pane, and the split's own controls while it holds both the
 * first pane and the TUI. */
export function paneControls({
  t,
  maximized,
  firstPaneShown,
  tuiVisible,
  prefs,
  byId,
  runAction,
  toggleMaximize,
}: {
  t: Translate;
  maximized: Maximized;
  firstPaneShown: boolean;
  tuiVisible: boolean;
  prefs: Prefs;
  byId: (id: string) => Action | undefined;
  runAction: (id: string) => void;
  toggleMaximize: (area: Exclude<Maximized, null>) => void;
}) {
  const maximizeControl = (
    area: Exclude<Maximized, null>,
    labelKey: string,
  ): PaneControl => {
    const on = maximized === area;
    return {
      id: "maximize",
      icon: on ? "restore" : "maximize",
      label: on ? t("desktop.pane.restore") : t(labelKey),
      shortcut: primaryChord(byId("view.maximize")),
      pressed: on,
      run: () => toggleMaximize(area),
    };
  };
  const orientation = prefs.orientation;

  // The split's own controls, only while it holds both panes.
  const splitControls: PaneControl[] =
    maximized || !(firstPaneShown && tuiVisible)
      ? []
      : [
          {
            id: "swap",
            icon: "swap",
            label: t("desktop.split.swap"),
            run: () => runAction("split.swap"),
          },
          // While the window forces stacking, the orientation choice would
          // change nothing visible, so it is not offered.
          ...(orientation === prefs.orientation
            ? [
                {
                  id: "orientation",
                  icon: byId("split.orientation")?.icon ?? "splitColumn",
                  label: byId("split.orientation")?.label ?? "",
                  run: () => runAction("split.orientation"),
                },
              ]
            : []),
        ];
  return { maximizeControl, splitControls };
}
