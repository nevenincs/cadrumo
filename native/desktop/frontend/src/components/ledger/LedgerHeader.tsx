import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { PaneHeader, type PaneControl } from "../PaneHeader";
import type { LedgerSection } from "../../shell/layout";
import { useStrings } from "../../shell/strings";
import {
  SETUP_SECTIONS,
  TAB_SECTIONS,
  sectionName,
  sectionTabId,
} from "./ledgerWords";

/** A header action: what it runs, or why it cannot run here. */
export type LedgerHeaderAction =
  { run: () => void; reason?: undefined } | { run?: undefined; reason: string };

/** What a section tab counts, said in full where the badge shows a number. */
export type SectionCount = { count: number; label: string };

const COUNT_LIMIT = 999;

/** A text button that stays focusable while it cannot run, and says why. */
export function HeldButton({
  action,
  name,
  children,
  className,
}: {
  action: LedgerHeaderAction;
  /** The accessible name; it contains the visible words. */
  name: string;
  children: ReactNode;
  className?: string;
}) {
  const button = (
    <Button
      variant="outline"
      size="xs"
      className={className}
      aria-label={action.reason ? `${name}, ${action.reason}` : name}
      aria-disabled={action.reason ? true : undefined}
      onClick={action.run}
    >
      {children}
    </Button>
  );
  if (!action.reason) return button;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent>{action.reason}</TooltipContent>
    </Tooltip>
  );
}

/**
 * The Ledger page's header: the pane's own title and controls, and between
 * them the page's sections, its period and its actions. It is the pane's
 * header, not a second one inside the page.
 */
export function LedgerHeader({
  title,
  controls,
  onToggleMaximize,
  section,
  onSection,
  counts,
  panel,
  period,
  importAction,
  exportAction,
  addAction,
  addName,
}: {
  title: string;
  controls: PaneControl[];
  onToggleMaximize(): void;
  /** The section shown; left out while the page shows nothing to choose
   * between, as when it is withheld. */
  section?: LedgerSection;
  onSection(section: LedgerSection): void;
  counts: Partial<Record<LedgerSection, SectionCount>>;
  /** The id of the region the sections show in. */
  panel: string;
  period?: ReactNode;
  importAction?: LedgerHeaderAction;
  exportAction?: LedgerHeaderAction;
  /** Adding, where the section shown adds anything. */
  addAction?: LedgerHeaderAction;
  /** What Add adds, in full; a movement unless said. */
  addName?: string;
}) {
  const t = useStrings();
  const inSetup =
    section !== undefined &&
    (SETUP_SECTIONS as readonly string[]).includes(section);
  return (
    <PaneHeader
      title={title}
      controls={controls}
      onToggleMaximize={onToggleMaximize}
    >
      {section === undefined ? (
        <span className="flex-1" />
      ) : (
        <div className="ledger-head flex min-w-0 flex-1 shrink-[9999] items-center gap-2">
          <Tabs
            value={section}
            onValueChange={(value) => onSection(value as LedgerSection)}
            className="min-w-0 shrink"
          >
            <TabsList
              aria-label={t("desktop.ledger.sections")}
              className="ledger-sections h-control-sm overflow-x-auto"
            >
              {TAB_SECTIONS.map((value) => {
                const count = counts[value];
                const trigger = (
                  <TabsTrigger
                    key={value}
                    value={value}
                    id={sectionTabId(panel, value)}
                    aria-controls={panel}
                    className="min-w-0 px-2 text-sm"
                  >
                    {sectionName(t, value)}
                    {count && (
                      <>
                        <Badge
                          variant="neutral"
                          aria-hidden="true"
                          className="tabular-nums"
                        >
                          {count.count > COUNT_LIMIT
                            ? `${COUNT_LIMIT}+`
                            : count.count}
                        </Badge>
                        <span className="sr-only">{count.label}</span>
                      </>
                    )}
                  </TabsTrigger>
                );
                return count ? (
                  <Tooltip key={value}>
                    <TooltipTrigger asChild>{trigger}</TooltipTrigger>
                    <TooltipContent>{count.label}</TooltipContent>
                  </Tooltip>
                ) : (
                  trigger
                );
              })}
            </TabsList>
          </Tabs>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="xs"
                className={cn(
                  "ledger-setup shrink-0 gap-1",
                  inSetup && "bg-selected text-accent-foreground",
                )}
                aria-label={
                  inSetup
                    ? t("desktop.ledger.setup_current", {
                        section: sectionName(t, section),
                      })
                    : undefined
                }
              >
                {inSetup ? sectionName(t, section) : t("desktop.ledger.setup")}
                <Icon name="chevronDown" size="xs" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              {SETUP_SECTIONS.map((value) => (
                <DropdownMenuItem
                  key={value}
                  aria-current={value === section ? "page" : undefined}
                  onSelect={() => onSection(value)}
                >
                  <Icon
                    name="tick"
                    className={value === section ? undefined : "invisible"}
                  />
                  {sectionName(t, value)}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <span className="flex-1" />
          {period}
          {importAction && (
            <IconButton
              label={t("desktop.ledger.action.import")}
              hint={importAction.reason}
              aria-disabled={importAction.reason ? true : undefined}
              onClick={importAction.run}
            >
              <Icon name="upload" />
            </IconButton>
          )}
          {exportAction && (
            <IconButton
              label={t("desktop.ledger.action.export")}
              hint={exportAction.reason}
              aria-disabled={exportAction.reason ? true : undefined}
              onClick={exportAction.run}
            >
              <Icon name="download" />
            </IconButton>
          )}
          {addAction && (
            <HeldButton
              action={addAction}
              name={addName ?? t("desktop.ledger.action.add_movement")}
              className="ledger-add shrink-0"
            >
              <Icon name="plus" />
              {t("desktop.ledger.action.add")}
            </HeldButton>
          )}
        </div>
      )}
    </PaneHeader>
  );
}
