import type { ReactNode } from "react";
import { cn } from "@/components/ui/cn";
import { Icon, type IconName } from "@/components/ui/icon";

const fileIcon = (name: string): IconName =>
  /\.(png|jpe?g|tiff?|webp|heic|heif)$/i.test(name)
    ? "image"
    : /\.(pdf|xml)$/i.test(name)
      ? "page"
      : "sheet";

/** One file in a list: its kind's icon, its name and what is said of it. */
export function FileRow({
  name,
  icon,
  children,
  refused = false,
  action,
}: {
  name: string;
  icon?: IconName;
  children?: ReactNode;
  refused?: boolean;
  action?: ReactNode;
}) {
  return (
    <li
      data-refused={refused || undefined}
      className="flex items-start gap-2 rounded-md border border-border px-2.5 py-2"
    >
      {/* A file that cannot be read is a refusal, not a danger: its glyph
          says so, in the ink of the rest. */}
      <Icon
        name={icon ?? (refused ? "refused" : fileIcon(name))}
        className={cn("mt-0.5", refused && "text-muted-foreground")}
      />
      <div className="grid min-w-0 flex-1 gap-1">
        <span className="font-medium [overflow-wrap:anywhere]">{name}</span>
        {children}
      </div>
      {action}
    </li>
  );
}
