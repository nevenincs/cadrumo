import { useMemo, useRef } from "react";
import type { AgentColumnControl } from "../components/AgentColumn";
import type { ModelList } from "./agentModelList";
import type { Host } from "./host";
import type { useNavigator } from "./navigation/useNavigator";

/** The model documents are read with is picked in the agent column's model
 * picker; a page beside a reading with no model leads to the picker. */
export function useReadingModelPicker(
  agentSession: Host["agentSession"],
  openView: ReturnType<typeof useNavigator>["openView"],
) {
  const agentControl = useRef<AgentColumnControl>(null);
  const modelList = useMemo<ModelList | null>(
    () =>
      agentSession?.localModels && agentSession.chooseReadingModel
        ? {
            open: () => {
              openView("agent");
              agentControl.current?.openModelPicker();
            },
          }
        : null,
    [agentSession, openView],
  );
  return { agentControl, modelList };
}
