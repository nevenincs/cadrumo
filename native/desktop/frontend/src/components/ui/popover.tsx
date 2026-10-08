import * as React from "react";
import { Popover as PopoverPrimitive } from "radix-ui";
import { cn } from "@/components/ui/cn";
import { revealFocused } from "@/components/ui/reveal";

function Popover(props: React.ComponentProps<typeof PopoverPrimitive.Root>) {
  return <PopoverPrimitive.Root data-slot="popover" {...props} />;
}

function PopoverTrigger(
  props: React.ComponentProps<typeof PopoverPrimitive.Trigger>,
) {
  return <PopoverPrimitive.Trigger data-slot="popover-trigger" {...props} />;
}

function PopoverAnchor(
  props: React.ComponentProps<typeof PopoverPrimitive.Anchor>,
) {
  return <PopoverPrimitive.Anchor data-slot="popover-anchor" {...props} />;
}

/**
 * A non-modal surface anchored to its trigger. It closes on Escape or a
 * press outside and hands focus back to the trigger. It never grows past the
 * window: tall content scrolls inside it.
 *
 * Escape pressed inside it closes it at the first press. The foundation gives
 * the key to the topmost layer only, so a tooltip showing anywhere in the
 * window would otherwise take the first press and leave the popover up.
 */
function PopoverContent({
  className,
  align = "center",
  sideOffset = 8,
  collisionPadding = 8,
  children,
  onFocusCapture,
  ...props
}: React.ComponentProps<typeof PopoverPrimitive.Content>) {
  const dismiss = React.useRef<HTMLButtonElement>(null);
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        data-slot="popover-content"
        // Tall content scrolls inside: what takes focus is brought into view.
        onFocusCapture={(event) => {
          onFocusCapture?.(event);
          revealFocused(event);
        }}
        onKeyDownCapture={(event) => {
          // A layer portalled out of the popover keeps its own Escape.
          if (
            event.key === "Escape" &&
            !event.nativeEvent.isComposing &&
            event.currentTarget.contains(event.target as Node)
          )
            dismiss.current?.click();
        }}
        align={align}
        sideOffset={sideOffset}
        collisionPadding={collisionPadding}
        className={cn(
          "z-(--layer-popover) max-h-(--radix-popover-content-available-height) max-w-(--radix-popover-content-available-width) origin-(--radix-popover-content-transform-origin) overflow-y-auto rounded-xl border bg-popover p-3.5 text-popover-foreground shadow-overlay outline-none",
          "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
          className,
        )}
        {...props}
      >
        {children}
        <PopoverPrimitive.Close ref={dismiss} hidden tabIndex={-1} />
      </PopoverPrimitive.Content>
    </PopoverPrimitive.Portal>
  );
}

export { Popover, PopoverAnchor, PopoverContent, PopoverTrigger };
