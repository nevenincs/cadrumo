import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";

/**
 * A filter in force, as a pill that names it, with its own button to take
 * it off. The button is a full header-sized target, never a glyph-sized one.
 * `removeLabel` should name the filter it removes.
 */
function FilterChip({
  removeLabel,
  onRemove,
  className,
  children,
  ...props
}: React.ComponentProps<typeof Badge> & {
  removeLabel: string;
  onRemove: () => void;
}) {
  return (
    <Badge
      data-slot="filter-chip"
      variant="soft"
      className={cn("gap-0.5 py-0 pr-0 pl-2.5", className)}
      {...props}
    >
      <span className="min-w-0 truncate">{children}</span>
      <IconButton
        label={removeLabel}
        onClick={onRemove}
        className="rounded-full forced-colors:text-[Canvas]"
      >
        <Icon name="close" size="xs" />
      </IconButton>
    </Badge>
  );
}

export { FilterChip };
