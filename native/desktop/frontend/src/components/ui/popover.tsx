import * as React from "react";
import { Popover as PopoverPrimitive } from "radix-ui";
import { suggestionsOpenOn } from "@/components/ui/suggestionsOpen";
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

/** The popover a popover was opened inside, for what only the inner one sees. */
const EnclosingPopover = React.createContext<{
  close: () => void;
  holds: (node: Node) => boolean;
} | null>(null);

/**
 * A non-modal surface anchored to its trigger. It closes on Escape or a
 * press outside and hands focus back to the trigger. It never grows past the
 * window: tall content scrolls inside it.
 *
 * Escape pressed inside it closes it at the first press. The foundation gives
 * the key to the topmost layer only, so a tooltip showing anywhere in the
 * window would otherwise take the first press and leave the popover up.
 *
 * Focus goes back to the trigger a task after the popover has gone, so whatever
 * took focus in between keeps it: a menu opened in that moment would otherwise
 * lose focus to the trigger and close. If what took it is outside the popover
 * around this one, that one closes too: its own watch never saw focus leave,
 * for the element holding it was removed without losing it.
 *
 * A popover already going has no more use for Escape, though the foundation
 * still gives it the key until it is gone, so it passes the press to the one
 * around it.
 */
function PopoverContent({
  className,
  align = "center",
  sideOffset = 8,
  collisionPadding = 8,
  children,
  onFocusCapture,
  onCloseAutoFocus,
  ...props
}: React.ComponentProps<typeof PopoverPrimitive.Content>) {
  const dismiss = React.useRef<HTMLButtonElement>(null);
  const enclosing = React.useContext(EnclosingPopover);
  const self = React.useMemo(
    () => ({
      close: () => dismiss.current?.click(),
      holds: (node: Node) =>
        dismiss.current?.parentElement?.contains(node) ?? false,
    }),
    [],
  );
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        data-slot="popover-content"
        onCloseAutoFocus={(event) => {
          onCloseAutoFocus?.(event);
          const held = document.activeElement;
          if (held && held !== document.body) {
            event.preventDefault();
            if (enclosing && !enclosing.holds(held)) enclosing.close();
          }
        }}
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
            event.currentTarget.contains(event.target as Node) &&
            !suggestionsOpenOn(event.target)
          ) {
            if (event.currentTarget.dataset.state === "closed")
              enclosing?.close();
            else self.close();
          }
        }}
        align={align}
        sideOffset={sideOffset}
        collisionPadding={collisionPadding}
        className={cn(
          "z-(--layer-popover) max-h-(--radix-popover-content-available-height) max-w-(--radix-popover-content-available-width) origin-(--radix-popover-content-transform-origin) overflow-y-auto rounded-xl bg-popover p-3.5 text-popover-foreground shadow-overlay outline-none",
          // Where colours are forced the shadow is dropped: an edge stands in.
          "forced-colors:border forced-colors:border-[CanvasText]",
          "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
          className,
        )}
        {...props}
      >
        <EnclosingPopover.Provider value={self}>
          {children}
        </EnclosingPopover.Provider>
        <PopoverPrimitive.Close ref={dismiss} hidden tabIndex={-1} />
      </PopoverPrimitive.Content>
    </PopoverPrimitive.Portal>
  );
}

export { Popover, PopoverAnchor, PopoverContent, PopoverTrigger };
