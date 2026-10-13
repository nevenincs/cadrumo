import type * as React from "react";
import { useState } from "react";
import { Button, type ButtonProps } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon, type IconName } from "@/components/ui/icon";
import { IconButton, type IconButtonProps } from "@/components/ui/icon-button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useStrings, type Translate } from "../../shell/strings";

/**
 * Why an action cannot be taken now, or null when it can. An action given no
 * handler is not available yet; one with a handler can still be held back
 * by a reason of the caller's.
 */
function blockedReason(
  t: Translate,
  onAction: (() => void) | undefined,
  heldBy: string | undefined,
): string | null {
  if (!onAction) return t("desktop.agent.unavailable");
  return heldBy ?? null;
}

type AgentIconActionProps = Omit<
  IconButtonProps,
  "onClick" | "children" | "aria-disabled"
> & {
  icon: IconName;
  /** What the button does. Without it the button says it is not available. */
  onAction?: () => void;
  /** Why the action is held back for now, though it has a handler. */
  heldBy?: string;
  /** Drawn over the icon's corner, as a count is. */
  badge?: React.ReactNode;
};

/**
 * An icon-only action of the agent column. One that cannot act stays in
 * place and keeps focus, looks disabled, and says why in its tooltip and
 * accessible name, so it is never a silent no-op.
 */
export function AgentIconAction({
  icon,
  onAction,
  heldBy,
  badge,
  hint,
  accessibleName,
  className,
  ...props
}: AgentIconActionProps) {
  const t = useStrings();
  const blocked = blockedReason(t, onAction, heldBy);
  return (
    <IconButton
      {...props}
      hint={blocked ?? hint}
      accessibleName={
        accessibleName && blocked
          ? `${accessibleName}, ${blocked}`
          : accessibleName
      }
      aria-disabled={blocked ? true : undefined}
      className={cn(badge !== undefined && "relative", className)}
      onClick={blocked ? undefined : onAction}
    >
      <Icon name={icon} />
      {badge}
    </IconButton>
  );
}

type AgentTextActionProps = Omit<ButtonProps, "onClick" | "aria-disabled"> & {
  onAction?: () => void;
  heldBy?: string;
};

/**
 * A worded action of the agent column, held back the same way as an icon
 * action: in place, focusable, and saying why in a tooltip and to a screen
 * reader.
 */
export function AgentTextAction({
  onAction,
  heldBy,
  children,
  ...props
}: AgentTextActionProps) {
  const t = useStrings();
  const blocked = blockedReason(t, onAction, heldBy);
  const [hovered, setHovered] = useState(false);
  // The tooltip stays mounted and controlled either way, so the button is
  // never remounted and keeps focus when it becomes available.
  return (
    <Tooltip open={Boolean(blocked) && hovered} onOpenChange={setHovered}>
      <TooltipTrigger asChild>
        <Button
          {...props}
          aria-disabled={blocked ? true : undefined}
          onClick={blocked ? undefined : onAction}
        >
          {children}
          {blocked && <span className="sr-only">, {blocked}</span>}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{blocked}</TooltipContent>
    </Tooltip>
  );
}
