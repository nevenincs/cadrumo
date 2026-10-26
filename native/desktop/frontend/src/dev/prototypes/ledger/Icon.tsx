import { clsx as cx } from "clsx";
import {
  ArrowUpDown,
  File,
  Files,
  Layers,
  type LucideIcon,
  Minus,
  Package,
  PanelRight,
  PanelRightClose,
  ReceiptText,
  Redo2,
  RotateCcwClock,
  Scale,
  Trash,
  Undo2,
} from "lucide-react";
import {
  Icon as ShellIcon,
  type IconName as ShellName,
} from "@/components/ui/icon";

// The prototype's icon names. Where the shell's registry holds the same glyph
// the shell draws it; the few the registry lacks are drawn from the same
// library here.

const LOCAL = {
  trash: Trash,
  group: Layers,
  sort: ArrowUpDown,
  undo: Undo2,
  redo: Redo2,
  panelRight: PanelRight,
  panelRightClose: PanelRightClose,
  stash: Package,
  receipt: ReceiptText,
  history: RotateCcwClock,
  scale: Scale,
  minus: Minus,
  file: File,
  duplicate: Files,
} satisfies Record<string, LucideIcon>;

const SHELL = {
  moneyIn: "directionIn",
  moneyOut: "directionOut",
} as const satisfies Record<string, ShellName>;

// The names the shell registry already has, used as they are.
type SameName = ShellName &
  (
    | "agent"
    | "alert"
    | "archive"
    | "arrow"
    | "attach"
    | "back"
    | "book"
    | "bookmark"
    | "calendar"
    | "check"
    | "chevronDown"
    | "chevronUp"
    | "clock"
    | "close"
    | "collapseAll"
    | "columns"
    | "console"
    | "copy"
    | "download"
    | "edit"
    | "erase"
    | "expandAll"
    | "eye"
    | "eyeOff"
    | "filter"
    | "folder"
    | "forward"
    | "idCard"
    | "image"
    | "info"
    | "key"
    | "keyboard"
    | "ledger"
    | "link"
    | "loader"
    | "lock"
    | "mail"
    | "maximize"
    | "merge"
    | "more"
    | "noRate"
    | "office"
    | "page"
    | "paste"
    | "pause"
    | "pending"
    | "play"
    | "plus"
    | "refused"
    | "reset"
    | "search"
    | "selectAll"
    | "settings"
    | "sheet"
    | "shield"
    | "sortAsc"
    | "sortDesc"
    | "split"
    | "swap"
    | "sync"
    | "tick"
    | "tui"
    | "unarchive"
    | "unknown"
    | "unplug"
    | "upload"
    | "user"
    | "users"
    | "windowMaximize"
  );

export type IconName = keyof typeof LOCAL | keyof typeof SHELL | SameName;

export type IconSize = "xs" | "sm" | "md" | "lg";

function isLocal(name: IconName): name is keyof typeof LOCAL {
  return name in LOCAL;
}
function isMoney(name: IconName): name is keyof typeof SHELL {
  return name in SHELL;
}

export function Icon({
  name,
  size,
  className,
}: {
  name: IconName;
  size?: IconSize;
  className?: string;
}) {
  const classes = cx("icon", size, className);
  if (isLocal(name)) {
    const Glyph = LOCAL[name];
    return <Glyph aria-hidden="true" className={classes} />;
  }
  return (
    <ShellIcon
      name={isMoney(name) ? SHELL[name] : name}
      size={size ?? "sm"}
      className={classes}
    />
  );
}
