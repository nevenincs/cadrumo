import type { RefObject } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { IconButton } from "@/components/ui/icon-button";
import { Icon } from "@/components/ui/icon";
import {
  CLASSIFY_KINDS,
  type ClassifyAvailability,
  type ClassifyKind,
} from "../../../shell/ledgerCommands";
import { useStrings } from "../../../shell/strings";
import { CLASSIFY_CHORDS } from "./useClassifyChords";

/** What a group header's buttons do: set by the section after each render,
 * read when one is pressed. */
export type GroupCommands = {
  classify: (kind: ClassifyKind, ids: readonly string[]) => void;
  category: (ids: string[]) => void;
  select: (ids: string[]) => void;
  /** Null where the page has no rule dialog. */
  makeRule: ((ids: string[]) => void) | null;
};

/** A group header's quick actions, which act on the group's movements
 * through the page's one classify command: one Classify menu, and a menu of
 * the rest. A press on them is theirs, never the header's. */
export function GroupActions({
  ids,
  transfers,
  commands,
}: {
  ids: string[];
  transfers: boolean;
  commands: RefObject<GroupCommands>;
}) {
  const t = useStrings();
  const own = {
    onClick: (event: { stopPropagation: () => void }) =>
      event.stopPropagation(),
    onDoubleClick: (event: { stopPropagation: () => void }) =>
      event.stopPropagation(),
    onPointerDown: (event: { stopPropagation: () => void }) =>
      event.stopPropagation(),
  };
  const transferNote = transfers
    ? t("desktop.ledger.classify.transfers_only")
    : undefined;
  const kinds: [ClassifyKind, string][] = [
    ["business", t("desktop.ledger.group.business")],
    ["personal", t("desktop.ledger.group.personal")],
    ["mixed", t("desktop.ledger.group.mixed")],
  ];
  return (
    <span className="ledger-group-actions flex items-center gap-1" {...own}>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="xs"
            tabIndex={-1}
            className="ledger-group-classify"
          >
            {t("desktop.ledger.group.classify")}
            <Icon name="chevronDown" size="xs" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {kinds.map(([kind, label]) => (
            <DropdownMenuItem
              key={kind}
              disabled={kind !== "personal" && transferNote !== undefined}
              onSelect={() => commands.current.classify(kind, ids)}
            >
              {label}
              {kind !== "personal" && transferNote && (
                <DropdownMenuShortcut>{transferNote}</DropdownMenuShortcut>
              )}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <IconButton
            label={t("desktop.ledger.group.more")}
            size="xs"
            variant="outline"
            tabIndex={-1}
            className="ledger-group-more"
          >
            <Icon name="more" />
          </IconButton>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => commands.current.category(ids)}>
            {t("desktop.ledger.group.category")}…
          </DropdownMenuItem>
          {commands.current.makeRule && (
            <DropdownMenuItem onSelect={() => commands.current.makeRule?.(ids)}>
              {t("desktop.ledger.group.make_rule")}…
            </DropdownMenuItem>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => commands.current.select(ids)}>
            {t("desktop.ledger.group.select", { count: ids.length })}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </span>
  );
}

/** The toolbar's menu over a selection of more than one movement: each
 * classify kind with its chord, and a rule made from the selection where the
 * page has a rule dialog. */
export function SelectionActions({
  availabilityOf,
  classify,
  hidden,
  onMakeRule,
}: {
  availabilityOf: (kind: ClassifyKind) => ClassifyAvailability;
  classify: (kind: ClassifyKind) => void;
  /** Selected movements the grid does not draw, which a rule cannot take. */
  hidden: boolean;
  onMakeRule?: () => void;
}) {
  const t = useStrings();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <IconButton
          label={t("desktop.ledger.selection.actions")}
          size="sm"
          className="ledger-selection-actions"
        >
          <Icon name="more" />
        </IconButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {CLASSIFY_KINDS.map((kind) => (
          <DropdownMenuItem
            key={kind}
            icon="tick"
            disabled={availabilityOf(kind).kind !== "ready"}
            onSelect={() => classify(kind)}
          >
            {t(`desktop.ledger.classify.as_${kind}`)}
            <DropdownMenuShortcut chord={CLASSIFY_CHORDS[kind]} />
          </DropdownMenuItem>
        ))}
        {onMakeRule && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              icon="filter"
              disabled={hidden}
              onSelect={() => onMakeRule()}
            >
              {t("desktop.ledger.inspector.selection.make_rule")}…
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
