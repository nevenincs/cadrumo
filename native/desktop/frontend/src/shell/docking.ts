/** Layout contains presentation identities only, never a panel's private state. */
export const DOCK_PANES = [
  "agent",
  "docs",
  "tui",
  "console",
  "python",
  "logs",
] as const;
export type DockPane = (typeof DOCK_PANES)[number];
export type DockSide = "left" | "right" | "top" | "bottom";
export type DockGroup = { kind: "tabs"; tabs: DockPane[]; active: DockPane };
export type DockNode =
  | DockGroup
  | {
      kind: "split";
      axis: "row" | "column";
      ratio: number;
      first: DockNode;
      second: DockNode;
    };
export type DockRect = { x: number; y: number; width: number; height: number };
export type FloatingPane = { pane: DockPane; rect: DockRect };
export type DockLayout = {
  version: 1;
  root: DockNode | null;
  floating: FloatingPane[];
  closed: DockPane[];
};
export type DockPlacement = { group: DockGroup; rect: DockRect };
export type DockDivider = {
  panes: DockPane[];
  path: string;
  axis: "row" | "column";
  /** Drawn stacked only because the window is too narrow for the saved
   * side-by-side split: its ratio is not the saved one and is not saved. */
  narrowed: boolean;
  ratio: number;
  rect: DockRect;
  minRatio: number;
  maxRatio: number;
};

export function isDockPane(value: unknown): value is DockPane {
  return typeof value === "string" && DOCK_PANES.some((pane) => pane === value);
}

const group = (pane: DockPane): DockGroup => ({
  kind: "tabs",
  tabs: [pane],
  active: pane,
});
const record = (value: unknown): Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
const finite = (value: unknown, fallback: number, low: number, high: number) =>
  typeof value === "number" && Number.isFinite(value)
    ? Math.max(low, Math.min(high, value))
    : fallback;

export function dockPanes(node: DockNode | null): DockPane[] {
  if (!node) return [];
  return node.kind === "tabs"
    ? node.tabs
    : [...dockPanes(node.first), ...dockPanes(node.second)];
}

/** Bound input depth and membership before it reaches recursive rendering. */
export function readDockLayout(value: unknown): DockLayout | null {
  const stored = record(value);
  if (stored.version !== 1) return null;
  const seen = new Set<DockPane>();
  let budget = DOCK_PANES.length * 4;
  const read = (value: unknown, depth: number): DockNode | null => {
    if (depth > DOCK_PANES.length || --budget < 0) return null;
    const node = record(value);
    if (node.kind === "tabs") {
      const tabs = (
        Array.isArray(node.tabs) ? node.tabs.slice(0, DOCK_PANES.length) : []
      ).filter((pane): pane is DockPane => {
        if (!isDockPane(pane) || seen.has(pane)) return false;
        seen.add(pane);
        return true;
      });
      const first = tabs[0];
      return first
        ? {
            kind: "tabs",
            tabs,
            active:
              isDockPane(node.active) && tabs.includes(node.active)
                ? node.active
                : first,
          }
        : null;
    }
    if (node.kind !== "split") return null;
    const first = read(node.first, depth + 1);
    const second = read(node.second, depth + 1);
    return first && second
      ? {
          kind: "split",
          axis: node.axis === "column" ? "column" : "row",
          ratio: finite(node.ratio, 0.5, 0.1, 0.9),
          first,
          second,
        }
      : (first ?? second);
  };
  const root = read(stored.root, 0);
  const floating: FloatingPane[] = [];
  for (const value of Array.isArray(stored.floating)
    ? stored.floating.slice(0, DOCK_PANES.length)
    : []) {
    const entry = record(value);
    if (!isDockPane(entry.pane) || seen.has(entry.pane)) continue;
    seen.add(entry.pane);
    const rect = record(entry.rect);
    floating.push({
      pane: entry.pane,
      rect: clampDockRect({
        x: finite(rect.x, 0.15, 0, 1),
        y: finite(rect.y, 0.15, 0, 1),
        width: finite(rect.width, 0.6, 0.2, 1),
        height: finite(rect.height, 0.6, 0.2, 1),
      }),
    });
  }
  return {
    version: 1,
    root,
    floating,
    closed: Array.isArray(stored.closed)
      ? [
          ...new Set(
            stored.closed.slice(0, DOCK_PANES.length).filter(isDockPane),
          ),
        ]
      : [],
  };
}

export function clampDockRect(rect: DockRect): DockRect {
  const width = finite(rect.width, 0.6, 0.2, 1);
  const height = finite(rect.height, 0.6, 0.2, 1);
  return {
    width,
    height,
    x: finite(rect.x, 0, 0, 1 - width),
    y: finite(rect.y, 0, 0, 1 - height),
  };
}

function mapGroups(
  node: DockNode | null,
  visit: (group: DockGroup) => DockNode | null,
): DockNode | null {
  if (!node) return null;
  if (node.kind === "tabs") return visit(node);
  const first = mapGroups(node.first, visit);
  const second = mapGroups(node.second, visit);
  return first && second ? { ...node, first, second } : (first ?? second);
}

export function removeDockPane(layout: DockLayout, pane: DockPane): DockLayout {
  return {
    ...layout,
    floating: layout.floating.filter((item) => item.pane !== pane),
    root: mapGroups(layout.root, (node) => {
      const tabs = node.tabs.filter((item) => item !== pane);
      const first = tabs[0];
      return first
        ? {
            ...node,
            tabs,
            active: tabs.includes(node.active) ? node.active : first,
          }
        : null;
    }),
  };
}

export function activateDockPane(
  layout: DockLayout,
  pane: DockPane,
): DockLayout {
  return {
    ...layout,
    closed: layout.closed.filter((item) => item !== pane),
    root: mapGroups(layout.root, (node) =>
      node.tabs.includes(pane) ? { ...node, active: pane } : node,
    ),
    floating: [
      ...layout.floating.filter((item) => item.pane !== pane),
      ...layout.floating.filter((item) => item.pane === pane),
    ],
  };
}

/** A move first removes its source. Splitting never creates a second instance. */
export function moveDockPane(
  layout: DockLayout,
  pane: DockPane,
  target: DockPane,
  side: DockSide | "tab",
): DockLayout {
  if (pane === target || !dockPanes(layout.root).includes(target))
    return layout;
  const removed = removeDockPane(layout, pane);
  return {
    ...removed,
    root: mapGroups(removed.root, (node) => {
      if (!node.tabs.includes(target)) return node;
      if (side === "tab")
        return { ...node, tabs: [...node.tabs, pane], active: pane };
      const before = side === "left" || side === "top";
      return {
        kind: "split",
        axis: side === "left" || side === "right" ? "row" : "column",
        ratio: 0.5,
        first: before ? group(pane) : node,
        second: before ? node : group(pane),
      };
    }),
  };
}

export function floatDockPane(layout: DockLayout, pane: DockPane): DockLayout {
  if (layout.floating.some((item) => item.pane === pane))
    return activateDockPane(layout, pane);
  const removed = removeDockPane(layout, pane);
  return {
    ...removed,
    floating: [
      ...removed.floating,
      { pane, rect: { x: 0.15, y: 0.15, width: 0.6, height: 0.6 } },
    ],
  };
}

export function returnDockPane(layout: DockLayout, pane: DockPane): DockLayout {
  const target = dockPanes(layout.root)[0];
  return target
    ? moveDockPane(layout, pane, target, "tab")
    : { ...removeDockPane(layout, pane), root: group(pane) };
}

export function swapDockPane(layout: DockLayout, pane: DockPane): DockLayout {
  const visit = (node: DockNode): DockNode => {
    if (node.kind === "tabs") return node;
    const first = dockPanes(node.first).includes(pane);
    const child = first ? node.first : node.second;
    if (!dockPanes(child).includes(pane)) return node;
    if (child.kind === "tabs")
      return {
        ...node,
        first: node.second,
        second: node.first,
        ratio: 1 - node.ratio,
      };
    return { ...node, [first ? "first" : "second"]: visit(child) };
  };
  return layout.root ? { ...layout, root: visit(layout.root) } : layout;
}

export function orientDockPane(layout: DockLayout, pane: DockPane): DockLayout {
  const visit = (node: DockNode): DockNode => {
    if (node.kind === "tabs") return node;
    const side = dockPanes(node.first).includes(pane) ? "first" : "second";
    if (!dockPanes(node[side]).includes(pane)) return node;
    return node[side].kind === "tabs"
      ? { ...node, axis: node.axis === "row" ? "column" : "row" }
      : { ...node, [side]: visit(node[side]) };
  };
  return layout.root ? { ...layout, root: visit(layout.root) } : layout;
}

export function resizeDockSplit(
  layout: DockLayout,
  path: string,
  ratio: number,
): DockLayout {
  const visit = (node: DockNode, rest: string): DockNode => {
    if (node.kind !== "split") return node;
    if (rest === "")
      return { ...node, ratio: finite(ratio, node.ratio, 0.1, 0.9) };
    const side = rest[0] === "0" ? "first" : "second";
    return { ...node, [side]: visit(node[side], rest.slice(1)) };
  };
  return layout.root ? { ...layout, root: visit(layout.root, path) } : layout;
}

/** Hidden tabs keep their place; empty branches take no screen space. A
 * side-by-side split too narrow for both sides' `besideWidths` is drawn
 * stacked, and a stacked split keeps each side's `minimumHeights` where both
 * fit and shares the height in their proportion where they do not; the
 * layout keeps its own arrangement and ratios for when there is room. */
export function dockGeometry(
  layout: DockLayout,
  visible: readonly DockPane[],
  fit?: {
    width: number;
    minimumWidths: Partial<Record<DockPane, number>>;
    besideWidths?: Partial<Record<DockPane, number>>;
    height?: number;
    minimumHeights?: Partial<Record<DockPane, number>>;
  },
): { groups: DockPlacement[]; dividers: DockDivider[] } {
  const groups: DockPlacement[] = [];
  const dividers: DockDivider[] = [];
  const has = (node: DockNode) =>
    dockPanes(node).some((pane) => visible.includes(pane));
  const active = (node: DockGroup) =>
    visible.includes(node.active)
      ? node.active
      : node.tabs.find((pane) => visible.includes(pane));
  const widths = new Map<DockNode, number>();
  const minimum = (node: DockNode): number => {
    const cached = widths.get(node);
    if (cached !== undefined) return cached;
    let width: number;
    if (node.kind === "tabs") {
      const pane = active(node);
      width = pane ? Math.max(0, fit?.minimumWidths[pane] ?? 0) : 0;
    } else if (!has(node.first) || !has(node.second)) {
      width = has(node.first)
        ? minimum(node.first)
        : has(node.second)
          ? minimum(node.second)
          : 0;
    } else {
      const a = minimum(node.first),
        b = minimum(node.second);
      // Side-by-side children also need room within the model's 10–90% limits;
      // a split that stacks where it is narrow needs only its wider side.
      width =
        node.axis === "row" && !stackable(node)
          ? Math.max(a + b, a / 0.9, b / 0.9)
          : Math.max(a, b);
    }
    widths.set(node, width);
    return width;
  };
  // The width a branch needs to stand beside another: its active panes'
  // floors, added across and the widest down.
  const beside = (node: DockNode): number => {
    if (!has(node)) return 0;
    if (node.kind === "tabs") {
      const pane = active(node);
      return pane ? Math.max(0, fit?.besideWidths?.[pane] ?? 0) : 0;
    }
    if (!has(node.first) || !has(node.second))
      return beside(has(node.first) ? node.first : node.second);
    const a = beside(node.first),
      b = beside(node.second);
    return node.axis === "row" ? a + b : Math.max(a, b);
  };
  // The height a branch needs: its active panes' floors, added down and the
  // tallest across.
  const tall = (node: DockNode): number => {
    if (!has(node)) return 0;
    if (node.kind === "tabs") {
      const pane = active(node);
      return pane ? Math.max(0, fit?.minimumHeights?.[pane] ?? 0) : 0;
    }
    if (!has(node.first) || !has(node.second))
      return tall(has(node.first) ? node.first : node.second);
    const a = tall(node.first),
      b = tall(node.second);
    return node.axis === "column" ? a + b : Math.max(a, b);
  };
  const stackable = (node: DockNode & { kind: "split" }) =>
    node.axis === "row" &&
    !!fit &&
    fit.width > 0 &&
    beside(node.first) > 0 &&
    beside(node.second) > 0;
  const stacked = (node: DockNode & { kind: "split" }, rect: DockRect) =>
    stackable(node) &&
    rect.width * fit!.width < beside(node.first) + beside(node.second);
  const visit = (node: DockNode, rect: DockRect, path: string) => {
    if (node.kind === "tabs") {
      const tabs = node.tabs.filter((pane) => visible.includes(pane));
      const first = tabs[0];
      if (first)
        groups.push({
          rect,
          group: {
            ...node,
            tabs,
            active: tabs.includes(node.active) ? node.active : first,
          },
        });
      return;
    }
    const a = has(node.first),
      b = has(node.second);
    if (!a && !b) return;
    if (!a || !b)
      return visit(a ? node.first : node.second, rect, path + (a ? "0" : "1"));
    const narrowed = stacked(node, rect);
    const axis = narrowed ? "column" : node.axis;
    let minRatio = 0.1,
      maxRatio = 0.9;
    if (axis === "row" && fit && fit.width > 0) {
      const available = rect.width * fit.width;
      const low = Math.max(minRatio, minimum(node.first) / available);
      const high = Math.min(maxRatio, 1 - minimum(node.second) / available);
      // An infeasible split keeps its arrangement and local overflow behavior.
      if (low <= high + 1e-12) {
        minRatio = low;
        maxRatio = Math.max(low, high);
      }
    }
    if (axis === "column" && fit?.height) {
      const available = rect.height * fit.height;
      const above = tall(node.first),
        below = tall(node.second);
      if (above + below > available && above > 0 && below > 0) {
        // Neither floor fits: the two share the height and stay on screen.
        minRatio = maxRatio = Math.max(
          minRatio,
          Math.min(maxRatio, above / (above + below)),
        );
      } else {
        minRatio = Math.max(minRatio, Math.min(maxRatio, above / available));
        maxRatio = Math.max(
          minRatio,
          Math.min(maxRatio, 1 - below / available),
        );
      }
    }
    // The saved ratio divides the width; stacked for want of it, the two
    // share the height evenly within their floors.
    const ratio = Math.max(
      minRatio,
      Math.min(maxRatio, narrowed ? 0.5 : node.ratio),
    );
    dividers.push({
      path,
      axis,
      narrowed,
      ratio,
      minRatio,
      maxRatio,
      rect,
      panes: dockPanes(node).filter((pane) => visible.includes(pane)),
    });
    const row = axis === "row";
    visit(
      node.first,
      {
        ...rect,
        width: row ? rect.width * ratio : rect.width,
        height: row ? rect.height : rect.height * ratio,
      },
      path + "0",
    );
    visit(
      node.second,
      {
        x: row ? rect.x + rect.width * ratio : rect.x,
        y: row ? rect.y : rect.y + rect.height * ratio,
        width: row ? rect.width * (1 - ratio) : rect.width,
        height: row ? rect.height : rect.height * (1 - ratio),
      },
      path + "1",
    );
  };
  if (layout.root) visit(layout.root, { x: 0, y: 0, width: 1, height: 1 }, "");
  return { groups, dividers };
}

export function initialDockLayout(
  prefs: { orientation: "row" | "column"; order: "docs" | "tui" },
  layout: {
    agentRatio: number;
    splitRatio: number;
    panelRatio: number;
    tab: "console" | "python" | "logs";
  },
): DockLayout {
  const docs = group("docs"),
    tui = group("tui");
  return {
    version: 1,
    floating: [],
    closed: [],
    root: {
      kind: "split",
      axis: "row",
      ratio: layout.agentRatio,
      first: group("agent"),
      second: {
        kind: "split",
        axis: "column",
        ratio: 1 - layout.panelRatio,
        first: {
          kind: "split",
          axis: prefs.orientation,
          ratio:
            prefs.order === "docs" ? layout.splitRatio : 1 - layout.splitRatio,
          first: prefs.order === "docs" ? docs : tui,
          second: prefs.order === "docs" ? tui : docs,
        },
        second: {
          kind: "tabs",
          tabs: ["console", "python", "logs"],
          active: layout.tab,
        },
      },
    },
  };
}
