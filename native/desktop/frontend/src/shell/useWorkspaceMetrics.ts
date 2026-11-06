import type { Prefs } from "./layout";
import { useMetric, useTerminalFontSize } from "./metrics";

/** Layout geometry, read from the canonical tokens (src/styles/tokens.css)
 * instead of duplicated as literals; each metric re-reads on resize. */
export function useWorkspaceMetrics(fontSize: Prefs["fontSize"]) {
  const splitMinA = useMetric("--split-min-a", 260);
  const splitMinBRow = useMetric("--split-min-b-row", 320);
  const railWidth = useMetric("--rail-w", 48);
  const agentMin = useMetric("--agent-min", 240);
  const docsMin = useMetric("--docs-min", 200);
  const panelMin = useMetric("--panel-min", 140);
  const terminalFontSize = useTerminalFontSize(fontSize);
  return {
    splitMinA,
    splitMinBRow,
    railWidth,
    agentMin,
    docsMin,
    panelMin,
    terminalFontSize,
  };
}
