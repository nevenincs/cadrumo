import { useCallback } from "react";
import type { PastedLink } from "../components/CommandPalette";
import { isCadrumoLink, parseViewLink } from "./navigation/links";
import { NAVIGATION } from "./navigation/projection";
import { elementOf } from "./navigation/register";
import {
  refusalReasonText,
  type useNavigator,
} from "./navigation/useNavigator";
import type { Translate } from "./strings";

type Navigator = ReturnType<typeof useNavigator>;

/** A palette query that is a `cadrumo:` link is one palette entry: the view
 * it opens, or why it opens none. */
export function usePastedLink(
  t: Translate,
  resolveView: Navigator["resolve"],
  openViewLink: Navigator["openLink"],
) {
  return useCallback(
    (text: string): PastedLink | null => {
      if (!isCadrumoLink(text)) return null;
      const parsed = parseViewLink(text, NAVIGATION);
      if (parsed.kind === "refused")
        return {
          label: refusalReasonText(t, NAVIGATION, parsed.reason, null),
          open: null,
        };
      const resolved = resolveView(parsed.link);
      if (resolved.kind === "refused")
        return {
          label: refusalReasonText(
            t,
            NAVIGATION,
            resolved.reason,
            parsed.link.viewId,
          ),
          open: null,
        };
      const element = elementOf(NAVIGATION, resolved.opened);
      return {
        label: t("desktop.palette.open_link", {
          view: element ? t(element.label) : resolved.opened,
        }),
        open: () => openViewLink(text),
      };
    },
    [t, resolveView, openViewLink],
  );
}
