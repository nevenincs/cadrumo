import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { cn } from "@/components/ui/cn";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { ResizeHandle } from "@/components/ui/resize-handle";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useStrings } from "../../shell/strings";
import { SessionDot, type SessionPhase } from "../PaneHeader";
import { DockedPane } from "./PaneChrome";
import {
  activateDockPane,
  clampDockRect,
  dockGeometry,
  dockPanes,
  floatDockPane,
  isDockPane,
  moveDockPane,
  resizeDockSplit,
  returnDockPane,
  swapDockPane,
  type DockLayout,
  type DockDivider,
  type DockPane,
  type DockRect,
  type DockSide,
} from "../../shell/docking";

const position = (rect: DockRect): CSSProperties => ({
  left: `${rect.x * 100}%`,
  top: `${rect.y * 100}%`,
  width: `${rect.width * 100}%`,
  height: `${rect.height * 100}%`,
});
const FULL: DockRect = { x: 0, y: 0, width: 1, height: 1 };
const SIDES = ["left", "right", "top", "bottom", "tab"] as const;
const DROP_TYPE = "application/x-cadrumo-pane";

export type DockContent = {
  id: DockPane;
  title: string;
  content: ReactNode;
  pageActions?: ReactNode;
  className?: string;
  status?: { phase: SessionPhase; note?: string };
};

/** Contents have fixed React ancestry. Only geometry and visibility change. */
export function DockWorkspace({
  layout,
  visible,
  expanded,
  fullscreen,
  panes,
  minimumWidths,
  besideWidths,
  minimumHeights,
  onChange,
  onActivate,
  onFocusPane,
  onMenuClosed,
  onClose,
  onExpand,
  onFullscreen,
  onNarrowed,
  empty,
}: {
  layout: DockLayout;
  visible: DockPane[];
  expanded: DockPane | null;
  fullscreen: boolean;
  panes: DockContent[];
  /** Content widths in CSS pixels; fitting never rewrites the saved layout. */
  minimumWidths?: Partial<Record<DockPane, number>>;
  /** The widths in CSS pixels panes need to stand side by side; narrower,
   * their split is drawn stacked, and the saved layout is left as it is. */
  besideWidths?: Partial<Record<DockPane, number>>;
  /** Whole-pane heights in CSS pixels a stacked split keeps for each side
   * where both fit; the saved ratios are left as they are. */
  minimumHeights?: Partial<Record<DockPane, number>>;
  onChange: (update: (layout: DockLayout) => DockLayout) => void;
  onActivate: (pane: DockPane) => void;
  onFocusPane: (pane: DockPane) => void;
  onMenuClosed: () => void;
  onClose: (pane: DockPane) => void;
  onExpand: (pane: DockPane) => void;
  onFullscreen: (pane: DockPane) => void;
  /** The panes whose saved side-by-side split the window is too narrow to
   * draw, so it is drawn stacked; an arrangement choice there does nothing. */
  onNarrowed?: (panes: readonly DockPane[]) => void;
  empty: ReactNode;
}) {
  const t = useStrings();
  const surface = useRef<HTMLDivElement>(null);
  const [fit, setFit] = useState<{
    width: number;
    minimumWidths: Partial<Record<DockPane, number>>;
    besideWidths?: Partial<Record<DockPane, number>>;
    height: number;
    minimumHeights?: Partial<Record<DockPane, number>>;
  }>();
  useLayoutEffect(() => {
    const element = surface.current;
    if (!element || (!minimumWidths && !besideWidths && !minimumHeights)) {
      setFit(undefined);
      return;
    }
    const measure = () => {
      const minimum: Partial<Record<DockPane, number>> = {};
      for (const pane of element.querySelectorAll<HTMLElement>(
        "[data-dock-pane]",
      )) {
        const id = pane.dataset.dockPane;
        if (!isDockPane(id) || minimumWidths?.[id] === undefined) continue;
        const style = getComputedStyle(pane);
        minimum[id] =
          minimumWidths[id]! +
          parseFloat(style.borderLeftWidth) +
          parseFloat(style.borderRightWidth) +
          parseFloat(style.paddingLeft) +
          parseFloat(style.paddingRight);
      }
      const width = element.clientWidth;
      const height = element.clientHeight;
      setFit((before) =>
        before?.width === width &&
        before.height === height &&
        JSON.stringify(before.minimumWidths) === JSON.stringify(minimum) &&
        before.besideWidths === besideWidths &&
        before.minimumHeights === minimumHeights
          ? before
          : {
              width,
              minimumWidths: minimum,
              besideWidths,
              height,
              minimumHeights,
            },
      );
    };
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    measure();
    return () => observer.disconnect();
  }, [minimumWidths, besideWidths, minimumHeights]);
  const [dragged, setDragged] = useState<DockPane | null>(null);
  const [externalDrag, setExternalDrag] = useState(false);
  const [drop, setDrop] = useState<{
    target: DockPane;
    side: DockSide | "tab";
  } | null>(null);
  const { groups, dividers } = dockGeometry(layout, visible, fit);
  const narrowed = dividers
    .filter((divider) => divider.narrowed)
    .flatMap((divider) => divider.panes)
    .sort()
    .join(" ");
  useEffect(() => {
    onNarrowed?.(narrowed ? (narrowed.split(" ") as DockPane[]) : []);
  }, [narrowed, onNarrowed]);
  const resize = (divider: DockDivider, requested: number) => {
    const ratio = Math.max(
      divider.minRatio,
      Math.min(divider.maxRatio, requested),
    );
    // A gesture against an existing limit must not replace the saved preference.
    if (Math.abs(ratio - divider.ratio) < 1e-9) return;
    onChange((current) => resizeDockSplit(current, divider.path, ratio));
  };
  // Headers too narrow for their active title give up, in turn, the expand
  // and close buttons the arrangement menu repeats and then the page actions
  // their shortcuts and the palette reach, before they cut the title. Each
  // step remembers, for that title, the width at which it fits again.
  const [compact, setCompact] = useState<ReadonlyMap<DockPane, 1 | 2>>(
    () => new Map(),
  );
  const roomy = useRef(
    new Map<DockPane, { title: string; widths: number[] }>(),
  );
  const fitTitles = () => {
    const element = surface.current;
    if (!element) return;
    setCompact((before) => {
      const after = new Map<DockPane, 1 | 2>();
      for (const header of element.querySelectorAll<HTMLElement>(
        "[data-dock-header]",
      )) {
        const pane = header.dataset.dockHeader;
        if (!isDockPane(pane)) continue;
        const label = header.querySelector<HTMLElement>(
          '[aria-selected="true"] [data-dock-title]',
        );
        const words = label?.textContent ?? "";
        let memory = roomy.current.get(pane);
        let level = before.get(pane) ?? 0;
        if (memory?.title !== words) {
          // Another title needs its own measure, taken from the full header.
          memory = { title: words, widths: [] };
          roomy.current.set(pane, memory);
          if (level > 0) continue;
        }
        if (level > 0 && header.clientWidth >= memory.widths[level - 1]!) {
          level -= 1;
        } else {
          // Cut by its own ellipsis, or scrolled past the edge of the tab row.
          const row = label
            ?.closest("[data-dock-tabs]")
            ?.getBoundingClientRect();
          const box = label?.getBoundingClientRect();
          const cut =
            label && row && box
              ? Math.max(
                  label.scrollWidth - label.clientWidth,
                  box.right - row.right,
                  row.left - box.left,
                )
              : 0;
          const deepest = header.querySelector("[data-dock-page-actions]")
            ? 2
            : 1;
          if (cut > 0.5 && level < deepest) {
            memory.widths[level] = header.clientWidth + cut;
            level += 1;
          }
        }
        if (level > 0) after.set(pane, level as 1 | 2);
      }
      return after.size === before.size &&
        [...after].every(([pane, level]) => before.get(pane) === level)
        ? before
        : after;
    });
  };
  useLayoutEffect(fitTitles);
  useEffect(() => {
    const element = surface.current;
    if (!element) return;
    const observer = new ResizeObserver(fitTitles);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const title = (pane: DockPane) =>
    panes.find((item) => item.id === pane)?.title ?? pane;
  const status = (pane: DockPane) =>
    panes.find((item) => item.id === pane)?.status;
  const gesture = useRef<{
    pane: DockPane;
    x: number;
    y: number;
    rect: DockRect;
    resize: boolean;
  } | null>(null);
  const floating = layout.floating.filter((item) =>
    visible.includes(item.pane),
  );
  const placements = [
    ...groups.map(({ group, rect }) => ({
      tabs: group.tabs,
      active: group.active,
      rect,
      floating: false,
    })),
    ...floating.map(({ pane, rect }) => ({
      tabs: [pane],
      active: pane,
      rect,
      floating: true,
    })),
  ]
    .filter((item) => expanded === null || item.tabs.includes(expanded))
    .map((item) =>
      expanded ? { ...item, active: expanded, rect: FULL } : item,
    );

  const move = (pane: DockPane, target: DockPane, side: DockSide | "tab") => {
    if (expanded) onExpand(expanded);
    onChange((current) =>
      activateDockPane(moveDockPane(current, pane, target, side), pane),
    );
    onActivate(pane);
    setDragged(null);
    setDrop(null);
    setExternalDrag(false);
  };
  const menus = (pane: DockPane, isFloating: boolean) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <IconButton label={t("desktop.dock.arrange")}>
          <Icon name="more" />
        </IconButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        data-dock-menu=""
        onCloseAutoFocus={(event) => {
          const held = document.activeElement;
          if (held && held !== document.body) event.preventDefault();
          requestAnimationFrame(onMenuClosed);
        }}
      >
        <DropdownMenuItem icon="maximize" onSelect={() => onExpand(pane)}>
          {t(expanded ? "desktop.dock.restore" : "desktop.dock.expand")}
        </DropdownMenuItem>
        <DropdownMenuItem icon="fullscreen" onSelect={() => onFullscreen(pane)}>
          {t(
            fullscreen
              ? "desktop.dock.exit_fullscreen"
              : "desktop.dock.fullscreen",
          )}
        </DropdownMenuItem>
        <DropdownMenuItem
          icon="external"
          onSelect={() => {
            if (expanded) onExpand(expanded);
            onChange((current) =>
              isFloating
                ? returnDockPane(current, pane)
                : floatDockPane(current, pane),
            );
          }}
        >
          {t(isFloating ? "desktop.dock.dock" : "desktop.dock.float")}
        </DropdownMenuItem>
        <DropdownMenuItem
          icon="swap"
          disabled={isFloating}
          onSelect={() => {
            if (expanded) onExpand(expanded);
            onChange((current) => swapDockPane(current, pane));
          }}
        >
          {t("desktop.split.swap")}
        </DropdownMenuItem>
        {SIDES.map((side) => {
          const target = dockPanes(layout.root).find(
            (id) => id !== pane && visible.includes(id),
          );
          return (
            <DropdownMenuItem
              key={side}
              icon={side === "tab" ? "tabs" : "splitRow"}
              disabled={!target}
              onSelect={() => {
                if (target) move(pane, target, side);
              }}
            >
              {t(`desktop.dock.${side}`)}
            </DropdownMenuItem>
          );
        })}
        <DropdownMenuItem icon="close" onSelect={() => onClose(pane)}>
          {t("desktop.dock.close")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  return (
    <div
      ref={surface}
      role="main"
      className="dock-workspace relative min-h-0 min-w-0 flex-1 overflow-hidden"
      data-dock-workspace=""
      onDragEnter={(event) => {
        if (event.dataTransfer.types.includes(DROP_TYPE)) setExternalDrag(true);
      }}
      onDragOver={(event) => {
        if (event.dataTransfer.types.includes(DROP_TYPE)) {
          event.preventDefault();
          event.dataTransfer.dropEffect = "move";
        }
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setExternalDrag(false);
          setDrop(null);
        }
      }}
      onDragEnd={() => {
        setDragged(null);
        setDrop(null);
        setExternalDrag(false);
      }}
    >
      {placements.length === 0 && empty}
      {panes.map((pane) => {
        const placement = placements.find((item) => item.active === pane.id);
        return (
          <section
            key={pane.id}
            id={`dock-content-${pane.id}`}
            data-dock-pane={pane.id}
            hidden={!placement}
            onPointerDownCapture={() => {
              if (placement?.floating && floating.at(-1)?.pane !== pane.id)
                onChange((current) => activateDockPane(current, pane.id));
            }}
            className={cn(
              "absolute flex min-h-0 min-w-0 flex-col overflow-hidden border bg-background pt-control-lg",
              pane.className,
              placement?.floating &&
                "z-(--layer-dock-floating) rounded-lg shadow-overlay",
            )}
            style={
              placement
                ? {
                    ...position(placement.rect),
                    ...(placement.floating
                      ? {
                          zIndex: `calc(var(--layer-dock-floating) + ${floating.findIndex((entry) => entry.pane === pane.id) * 2})`,
                        }
                      : {}),
                  }
                : undefined
            }
          >
            <DockedPane>{pane.content}</DockedPane>
          </section>
        );
      })}
      {placements.map((item) => (
        <div
          key={item.tabs.join("-")}
          className={cn(
            "pointer-events-none absolute",
            item.floating
              ? "z-(--layer-dock-floating-controls)"
              : "z-(--layer-dock-controls)",
          )}
          style={{
            ...position(item.rect),
            ...(item.floating
              ? {
                  zIndex: `calc(var(--layer-dock-floating-controls) + ${floating.findIndex((entry) => entry.pane === item.active) * 2})`,
                }
              : {}),
          }}
        >
          <div
            className="pointer-events-auto flex h-control-lg min-w-0 items-center border-b bg-chrome"
            data-dock-header={item.active}
            onDoubleClick={(event) => {
              if (!(event.target as Element).closest("button"))
                onExpand(item.active);
            }}
          >
            {item.floating && !expanded && (
              <Button
                variant="ghost"
                size="icon-sm"
                className="cursor-move touch-none"
                aria-label={t("desktop.dock.move")}
                onPointerDown={(event) => {
                  if (event.button !== 0) return;
                  event.currentTarget.setPointerCapture(event.pointerId);
                  gesture.current = {
                    pane: item.active,
                    x: event.clientX,
                    y: event.clientY,
                    rect: item.rect,
                    resize: false,
                  };
                  onChange((current) => activateDockPane(current, item.active));
                }}
                onPointerMove={(event) => {
                  const held = gesture.current,
                    bounds = surface.current?.getBoundingClientRect();
                  if (
                    !held ||
                    !bounds ||
                    !event.currentTarget.hasPointerCapture(event.pointerId)
                  )
                    return;
                  const rect = clampDockRect({
                    ...held.rect,
                    x: held.rect.x + (event.clientX - held.x) / bounds.width,
                    y: held.rect.y + (event.clientY - held.y) / bounds.height,
                  });
                  onChange((current) => ({
                    ...current,
                    floating: current.floating.map((entry) =>
                      entry.pane === held.pane ? { ...entry, rect } : entry,
                    ),
                  }));
                }}
                onPointerUp={() => {
                  gesture.current = null;
                }}
                onLostPointerCapture={() => {
                  gesture.current = null;
                }}
                onKeyDown={(event) => {
                  const x =
                    event.key === "ArrowLeft"
                      ? -0.03
                      : event.key === "ArrowRight"
                        ? 0.03
                        : 0;
                  const y =
                    event.key === "ArrowUp"
                      ? -0.03
                      : event.key === "ArrowDown"
                        ? 0.03
                        : 0;
                  if (!x && !y) return;
                  event.preventDefault();
                  onChange((current) => ({
                    ...current,
                    floating: current.floating.map((entry) =>
                      entry.pane === item.active
                        ? {
                            ...entry,
                            rect: clampDockRect({
                              ...entry.rect,
                              x: entry.rect.x + x,
                              y: entry.rect.y + y,
                            }),
                          }
                        : entry,
                    ),
                  }));
                }}
              >
                <Icon name="move" />
              </Button>
            )}
            <Tabs
              value={item.active}
              onValueChange={(value) => {
                if (isDockPane(value)) {
                  onChange((current) => activateDockPane(current, value));
                  onActivate(value);
                  if (expanded && value !== expanded) onExpand(value);
                }
              }}
              className="min-w-0 flex-1 overflow-x-auto"
              data-dock-tabs=""
            >
              <TabsList
                aria-label={t("desktop.dock.tabs")}
                className="h-control-lg"
              >
                {item.tabs.map((pane) => (
                  <TabsTrigger
                    key={pane}
                    value={pane}
                    id={`tab-${pane}`}
                    aria-controls={
                      pane === "console" || pane === "python" || pane === "logs"
                        ? `panel-${pane}`
                        : `dock-content-${pane}`
                    }
                    draggable
                    // The active title keeps its width; the others give way.
                    className="data-[state=active]:shrink-0"
                    title={[title(pane), status(pane)?.note]
                      .filter(Boolean)
                      .join(" · ")}
                    aria-description={status(pane)?.note}
                    onDoubleClick={(event) => {
                      event.stopPropagation();
                      onExpand(pane);
                    }}
                    onClick={() => {
                      onChange((current) => activateDockPane(current, pane));
                      onFocusPane(pane);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onFocusPane(pane);
                      }
                    }}
                    onDragStart={(event) => {
                      event.dataTransfer.setData(DROP_TYPE, pane);
                      event.dataTransfer.effectAllowed = "move";
                      setDragged(pane);
                    }}
                    onDragOver={(event) => {
                      if (event.dataTransfer.types.includes(DROP_TYPE)) {
                        event.preventDefault();
                        setDrop({ target: pane, side: "tab" });
                      }
                    }}
                    onDrop={(event) => {
                      const source = event.dataTransfer.getData(DROP_TYPE);
                      if (!isDockPane(source)) return;
                      event.preventDefault();
                      move(source, pane, "tab");
                    }}
                  >
                    {status(pane) && <SessionDot phase={status(pane)!.phase} />}
                    <span className="truncate" data-dock-title="">
                      {title(pane)}
                    </span>
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            {panes.find((pane) => pane.id === item.active)?.pageActions && (
              <div
                className={cn(
                  "flex shrink-0 items-center",
                  compact.get(item.active) === 2 && "hidden",
                )}
                data-dock-page-actions=""
              >
                {panes.find((pane) => pane.id === item.active)?.pageActions}
              </div>
            )}
            {menus(item.active, item.floating)}
            {!compact.has(item.active) && (
              <>
                <IconButton
                  label={t(
                    expanded ? "desktop.dock.restore" : "desktop.dock.expand",
                  )}
                  onClick={() => onExpand(item.active)}
                >
                  <Icon name={expanded ? "restore" : "maximize"} />
                </IconButton>
                <IconButton
                  label={t("desktop.dock.close")}
                  onClick={() => onClose(item.active)}
                >
                  <Icon name="close" />
                </IconButton>
              </>
            )}
          </div>
          {!item.floating && !expanded && (
            <div
              className={cn(
                "absolute inset-0 top-control-lg",
                (dragged || drop || externalDrag) && "pointer-events-auto",
              )}
              onDragOver={(event) => {
                if (!event.dataTransfer.types.includes(DROP_TYPE)) return;
                event.preventDefault();
                const rect = event.currentTarget.getBoundingClientRect();
                const x = (event.clientX - rect.left) / rect.width,
                  y = (event.clientY - rect.top) / rect.height;
                const side =
                  x < 0.25
                    ? "left"
                    : x > 0.75
                      ? "right"
                      : y < 0.25
                        ? "top"
                        : y > 0.75
                          ? "bottom"
                          : "tab";
                setDrop({ target: item.active, side });
              }}
              onDrop={(event) => {
                const source = event.dataTransfer.getData(DROP_TYPE);
                if (!isDockPane(source)) return;
                event.preventDefault();
                move(
                  source,
                  item.active,
                  drop?.target === item.active ? drop.side : "tab",
                );
              }}
            >
              {drop?.target === item.active && (
                <div className="pointer-events-none absolute inset-0 flex items-center justify-center border-2 border-ring bg-selected opacity-80">
                  <span className="rounded bg-popover p-2 text-popover-foreground">
                    {t(`desktop.dock.${drop.side}`)}
                  </span>
                </div>
              )}
            </div>
          )}
          {item.floating &&
            !expanded &&
            (["width", "height"] as const).map((dimension) => (
              <ResizeHandle
                key={dimension}
                className={cn(
                  "pointer-events-auto absolute right-0 bottom-0",
                  dimension === "width" ? "top-control-lg" : "left-0",
                )}
                orientation={dimension === "width" ? "vertical" : "horizontal"}
                aria-label={`${t("desktop.dock.resize")}: ${title(item.active)}`}
                value={item.rect[dimension] * 100}
                onDrag={({ x, y }) => {
                  const bounds = surface.current?.getBoundingClientRect();
                  if (!bounds) return;
                  onChange((current) => ({
                    ...current,
                    floating: current.floating.map((entry) =>
                      entry.pane === item.active
                        ? {
                            ...entry,
                            rect: clampDockRect({
                              ...entry.rect,
                              [dimension]:
                                dimension === "width"
                                  ? (x - bounds.left) / bounds.width -
                                    entry.rect.x
                                  : (y - bounds.top) / bounds.height -
                                    entry.rect.y,
                            }),
                          }
                        : entry,
                    ),
                  }));
                }}
                onStep={(direction) =>
                  onChange((current) => ({
                    ...current,
                    floating: current.floating.map((entry) =>
                      entry.pane === item.active
                        ? {
                            ...entry,
                            rect: clampDockRect({
                              ...entry.rect,
                              [dimension]:
                                entry.rect[dimension] + direction * 0.03,
                            }),
                          }
                        : entry,
                    ),
                  }))
                }
              />
            ))}
        </div>
      ))}
      {!expanded &&
        // A split stacked for want of width has no saved height share to
        // move, so it offers no handle that would write one.
        dividers
          .filter((divider) => !divider.narrowed)
          .map((divider) => {
            const row = divider.axis === "row";
            const rect = {
              ...divider.rect,
              x:
                divider.rect.x + (row ? divider.rect.width * divider.ratio : 0),
              y:
                divider.rect.y +
                (row ? 0 : divider.rect.height * divider.ratio),
            };
            return (
              <ResizeHandle
                key={divider.path}
                data-dock-divider={divider.path}
                className="absolute"
                style={{
                  left: `${rect.x * 100}%`,
                  top: `${rect.y * 100}%`,
                  ...(row
                    ? { height: `${rect.height * 100}%` }
                    : { width: `${rect.width * 100}%` }),
                }}
                orientation={row ? "vertical" : "horizontal"}
                aria-label={`${t("desktop.split.resize")}: ${divider.panes.map(title).join(" / ")}`}
                value={divider.ratio * 100}
                aria-valuenow={divider.ratio * 100}
                aria-valuemin={divider.minRatio * 100}
                aria-valuemax={divider.maxRatio * 100}
                onDrag={({ x, y }) => {
                  const bounds = surface.current?.getBoundingClientRect();
                  if (!bounds) return;
                  const ratio = row
                    ? ((x - bounds.left) / bounds.width - divider.rect.x) /
                      divider.rect.width
                    : ((y - bounds.top) / bounds.height - divider.rect.y) /
                      divider.rect.height;
                  resize(divider, ratio);
                }}
                onStep={(direction) =>
                  resize(divider, divider.ratio + direction * 0.03)
                }
                onLimit={(limit) =>
                  resize(
                    divider,
                    limit === "min" ? divider.minRatio : divider.maxRatio,
                  )
                }
                onReset={() =>
                  onChange((current) =>
                    resizeDockSplit(current, divider.path, 0.5),
                  )
                }
              />
            );
          })}
    </div>
  );
}
