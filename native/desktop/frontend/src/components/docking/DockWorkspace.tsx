import { useRef, useState, type CSSProperties, type ReactNode } from "react";
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
  className?: string;
};

/** Contents have fixed React ancestry. Only geometry and visibility change. */
export function DockWorkspace({
  layout,
  visible,
  expanded,
  panes,
  onChange,
  onActivate,
  onFocusPane,
  onClose,
  onExpand,
  onFullscreen,
  empty,
}: {
  layout: DockLayout;
  visible: DockPane[];
  expanded: DockPane | null;
  panes: DockContent[];
  onChange: (update: (layout: DockLayout) => DockLayout) => void;
  onActivate: (pane: DockPane) => void;
  onFocusPane: (pane: DockPane) => void;
  onClose: (pane: DockPane) => void;
  onExpand: (pane: DockPane) => void;
  onFullscreen: (pane: DockPane) => void;
  empty: ReactNode;
}) {
  const t = useStrings();
  const surface = useRef<HTMLDivElement>(null);
  const [dragged, setDragged] = useState<DockPane | null>(null);
  const [externalDrag, setExternalDrag] = useState(false);
  const [drop, setDrop] = useState<{
    target: DockPane;
    side: DockSide | "tab";
  } | null>(null);
  const { groups, dividers } = dockGeometry(layout, visible);
  const title = (pane: DockPane) =>
    panes.find((item) => item.id === pane)?.title ?? pane;
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
        onCloseAutoFocus={(event) => {
          const held = document.activeElement;
          if (held && held !== document.body) event.preventDefault();
        }}
      >
        <DropdownMenuItem icon="maximize" onSelect={() => onExpand(pane)}>
          {t(expanded ? "desktop.pane.restore" : "desktop.dock.expand")}
        </DropdownMenuItem>
        <DropdownMenuItem
          icon="windowMaximize"
          onSelect={() => onFullscreen(pane)}
        >
          {t("desktop.dock.fullscreen")}
        </DropdownMenuItem>
        <DropdownMenuItem
          icon="external"
          onSelect={() =>
            onChange((current) =>
              isFloating
                ? returnDockPane(current, pane)
                : floatDockPane(current, pane),
            )
          }
        >
          {t(isFloating ? "desktop.dock.dock" : "desktop.dock.float")}
        </DropdownMenuItem>
        <DropdownMenuItem
          icon="swap"
          disabled={isFloating}
          onSelect={() => onChange((current) => swapDockPane(current, pane))}
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
            {pane.content}
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
                }
              }}
              className="min-w-0 flex-1 overflow-x-auto"
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
                    title={title(pane)}
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
                    <span className="truncate">{title(pane)}</span>
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            {menus(item.active, item.floating)}
            <IconButton
              label={t(
                expanded ? "desktop.pane.restore" : "desktop.dock.expand",
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
        dividers.map((divider) => {
          const row = divider.axis === "row";
          const rect = {
            ...divider.rect,
            x: divider.rect.x + (row ? divider.rect.width * divider.ratio : 0),
            y: divider.rect.y + (row ? 0 : divider.rect.height * divider.ratio),
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
              onDrag={({ x, y }) => {
                const bounds = surface.current?.getBoundingClientRect();
                if (!bounds) return;
                const ratio = row
                  ? ((x - bounds.left) / bounds.width - divider.rect.x) /
                    divider.rect.width
                  : ((y - bounds.top) / bounds.height - divider.rect.y) /
                    divider.rect.height;
                onChange((current) =>
                  resizeDockSplit(current, divider.path, ratio),
                );
              }}
              onStep={(direction) =>
                onChange((current) =>
                  resizeDockSplit(
                    current,
                    divider.path,
                    divider.ratio + direction * 0.03,
                  ),
                )
              }
              onLimit={(limit) =>
                onChange((current) =>
                  resizeDockSplit(
                    current,
                    divider.path,
                    limit === "min" ? 0.1 : 0.9,
                  ),
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
