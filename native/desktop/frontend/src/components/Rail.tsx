import { Toolbar } from "radix-ui";
import { Badge } from "@/components/ui/badge";
import { Icon, type IconName } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Separator } from "@/components/ui/separator";

export type RailItem = {
  id: string;
  icon: IconName;
  label: string;
  shortcut?: string;
  pressed?: boolean;
  /** For a button that opens a surface: whether that surface is open. */
  expanded?: boolean;
  badge?: number;
  /** What the badge counts, said in full for the accessible name. */
  badgeLabel?: string;
  /** Starts a new cluster: a divider is drawn before this item. */
  divided?: boolean;
  onClick: () => void;
};

const BADGE_LIMIT = 99;

function RailButton({ item }: { item: RailItem }) {
  return (
    <>
      {item.divided && <Separator className="my-1 w-5" />}
      <Toolbar.Button asChild>
        <IconButton
          label={item.label}
          accessibleName={
            item.badge && item.badgeLabel
              ? `${item.label}, ${item.badgeLabel}`
              : undefined
          }
          shortcut={item.shortcut}
          size="lg"
          side="right"
          aria-pressed={item.pressed}
          aria-expanded={item.expanded}
          aria-haspopup={item.expanded === undefined ? undefined : "dialog"}
          onClick={item.onClick}
          // The chosen item carries a bar on the rail's edge as well as its
          // surface, so the choice does not rest on a tint alone. A button
          // whose surface is open is marked the same way.
          className="relative before:absolute before:inset-y-2 before:-left-1.5 before:w-0.5 before:rounded-xs before:bg-brand before:opacity-0 before:transition-opacity aria-expanded:bg-selected aria-expanded:text-accent-foreground aria-expanded:before:opacity-100 aria-pressed:before:opacity-100"
        >
          <Icon name={item.icon} size="lg" />
          {item.badge ? (
            <Badge
              variant="count"
              aria-hidden="true"
              className="absolute -top-0.5 -right-0.5 ring-2 ring-chrome"
            >
              {item.badge > BADGE_LIMIT ? `${BADGE_LIMIT}+` : item.badge}
            </Badge>
          ) : null}
        </IconButton>
      </Toolbar.Button>
    </>
  );
}

/**
 * The icon rail: a vertical toolbar. It is one tab stop; the arrow keys,
 * Home and End move within it. Every item is named by its tooltip, which
 * also shows its shortcut.
 */
export function Rail({
  label,
  top,
  bottom,
}: {
  label: string;
  top: RailItem[];
  bottom: RailItem[];
}) {
  return (
    <nav className="rail w-rail border-r bg-chrome" aria-label={label}>
      <Toolbar.Root
        orientation="vertical"
        // The side padding, not centring, places the buttons: the chosen
        // item's bar then sits exactly on the rail's outer edge.
        className="flex h-full flex-col items-start justify-between px-1.5 py-2"
      >
        <div className="rail-group flex flex-col items-center gap-1">
          {top.map((item) => (
            <RailButton key={item.id} item={item} />
          ))}
        </div>
        <div className="rail-group flex flex-col items-center gap-1">
          {bottom.map((item) => (
            <RailButton key={item.id} item={item} />
          ))}
        </div>
      </Toolbar.Root>
    </nav>
  );
}
