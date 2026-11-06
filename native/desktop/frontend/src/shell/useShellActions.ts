import { useMemo } from "react";
import { useAccountActions } from "./accountActions";
import type { Action } from "./actions";
import { useArrangementActions } from "./arrangementActions";
import { useDocsActions } from "./docsActions";
import { useLogActions } from "./logActions";
import { useSetupActions } from "./setupActions";
import { useTerminalActions } from "./terminalActions";
import { useViewActions } from "./viewNavigationActions";
import {
  useFocusActions,
  useWindowChromeActions,
  useWindowDialogActions,
} from "./windowActions";

/** What each group of actions needs of the window. */
type ShellActionSources = Parameters<typeof useWindowChromeActions>[0] &
  Parameters<typeof useDocsActions>[0] &
  Parameters<typeof useArrangementActions>[0] &
  Parameters<typeof useLogActions>[0] &
  Parameters<typeof useWindowDialogActions>[0] &
  Parameters<typeof useSetupActions>[0] &
  Parameters<typeof useViewActions>[0] &
  Parameters<typeof useAccountActions>[0] &
  Parameters<typeof useFocusActions>[0] &
  Parameters<typeof useTerminalActions>[0];

/** The window's single action registry: the palette, the shortcuts, the
 * rail and the menus all run what it declares. Each group declares its own
 * actions; the registry lists them in this order, which the palette shows
 * and the shortcuts are matched in. */
export function useShellActions(sources: ShellActionSources): Action[] {
  const chrome = useWindowChromeActions(sources);
  const docs = useDocsActions(sources);
  const arrangement = useArrangementActions(sources);
  const logs = useLogActions(sources);
  const dialogs = useWindowDialogActions(sources);
  const setup = useSetupActions(sources);
  const views = useViewActions(sources);
  const account = useAccountActions(sources);
  const focus = useFocusActions(sources);
  const terminal = useTerminalActions(sources);
  return useMemo(
    () => [
      ...chrome,
      ...docs,
      ...arrangement,
      ...logs,
      ...dialogs,
      ...setup,
      ...views,
      ...account,
      ...focus,
      ...terminal,
    ],
    [
      chrome,
      docs,
      arrangement,
      logs,
      dialogs,
      setup,
      views,
      account,
      focus,
      terminal,
    ],
  );
}
