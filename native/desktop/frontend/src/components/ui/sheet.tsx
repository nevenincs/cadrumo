import * as React from "react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { cn } from "@/components/ui/cn";
import { DialogOverlay } from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { revealFocused } from "@/components/ui/reveal";

function Sheet(props: React.ComponentProps<typeof DialogPrimitive.Root>) {
  return <DialogPrimitive.Root data-slot="sheet" {...props} />;
}

function SheetTrigger(
  props: React.ComponentProps<typeof DialogPrimitive.Trigger>,
) {
  return <DialogPrimitive.Trigger data-slot="sheet-trigger" {...props} />;
}

function SheetClose(props: React.ComponentProps<typeof DialogPrimitive.Close>) {
  return <DialogPrimitive.Close data-slot="sheet-close" {...props} />;
}

/**
 * A modal surface that slides in from an edge of the window over a scrim:
 * from the right for a record's editor, from the bottom on a narrow window.
 * It is a dialog in every other way: focus is trapped inside, Escape closes
 * it at the first press, and focus returns to the opener. `closeLabel` names
 * its corner close button. While open it holds the window, unless
 * `modalLayer={false}`, as for a dialog.
 */
function SheetContent({
  className,
  children,
  side = "right",
  closeLabel,
  modalLayer = true,
  onFocusCapture,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content> & {
  side?: "right" | "bottom";
  closeLabel: string;
  /** False for a surface that does not hold the window while open. */
  modalLayer?: boolean;
}) {
  const dismiss = React.useRef<HTMLButtonElement>(null);
  return (
    <DialogPrimitive.Portal>
      <DialogOverlay />
      <DialogPrimitive.Content
        data-slot="sheet-content"
        data-side={side}
        data-modal-layer={modalLayer ? "" : undefined}
        onFocusCapture={(event) => {
          onFocusCapture?.(event);
          revealFocused(event);
        }}
        onKeyDownCapture={(event) => {
          // A layer portalled out of the sheet keeps its own Escape.
          if (
            event.key === "Escape" &&
            !event.nativeEvent.isComposing &&
            event.currentTarget.contains(event.target as Node)
          )
            dismiss.current?.click();
        }}
        className={cn(
          "fixed z-(--layer-modal) flex flex-col gap-4 bg-card p-5 text-card-foreground shadow-overlay outline-none",
          "forced-colors:border-[CanvasText]",
          side === "right"
            ? "inset-y-0 right-0 w-sheet max-w-[calc(100%-var(--overlay-gutter))] overflow-y-auto forced-colors:border-l"
            : "inset-x-0 bottom-0 max-h-[calc(100dvh-var(--overlay-top))] overflow-y-auto rounded-t-xl forced-colors:border-t",
          "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0",
          side === "right"
            ? "data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right"
            : "data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom",
          className,
        )}
        {...props}
      >
        {children}
        <DialogPrimitive.Close ref={dismiss} hidden tabIndex={-1} />
        <DialogPrimitive.Close asChild>
          <IconButton
            label={closeLabel}
            size="sm"
            className="absolute top-3 right-3"
          >
            <Icon name="close" />
          </IconButton>
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

function SheetHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-header"
      className={cn("flex flex-col gap-1 pr-8", className)}
      {...props}
    />
  );
}

function SheetFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-footer"
      className={cn(
        "mt-auto flex flex-wrap items-center justify-end gap-2",
        className,
      )}
      {...props}
    />
  );
}

function SheetTitle({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      data-slot="sheet-title"
      className={cn("font-serif text-lg text-foreground", className)}
      {...props}
    />
  );
}

function SheetDescription({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      data-slot="sheet-description"
      className={cn("text-base text-muted-foreground", className)}
      {...props}
    />
  );
}

export {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
};
