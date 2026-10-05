import * as React from "react";
import { Button, type ButtonProps } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

type IconButtonProps = Omit<ButtonProps, "size" | "aria-label" | "title"> & {
  /** The accessible name, also shown as the tooltip. */
  label: string;
  /** The accessible name where it must say more than the tooltip does, as
   * when the button also shows a count. It has to contain what is visible. */
  accessibleName?: string;
  /** A chord shown beside the label in the tooltip; it binds nothing. */
  shortcut?: string;
  size?: "xs" | "sm" | "md" | "lg";
  /** Where the tooltip opens. */
  side?: React.ComponentProps<typeof TooltipContent>["side"];
};

/**
 * An icon-only button. It always has a name: the label is its accessible name
 * and its tooltip, so an icon is never the only way to learn what it does.
 */
function IconButton({
  label,
  accessibleName,
  shortcut,
  size = "xs",
  side = "bottom",
  variant = "ghost",
  children,
  ...props
}: IconButtonProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          data-slot="icon-button"
          variant={variant}
          size={`icon-${size}`}
          aria-label={accessibleName ?? label}
          {...props}
        >
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent side={side}>
        {label}
        {shortcut && <Kbd>{shortcut}</Kbd>}
      </TooltipContent>
    </Tooltip>
  );
}

export { IconButton, type IconButtonProps };
