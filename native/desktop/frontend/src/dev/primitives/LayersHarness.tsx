import { useMemo, useState } from "react";
import { DateEditor } from "@/components/editors/DateEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import { EditorField } from "@/components/ledger/setup/EditorField";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Field, FieldLabel } from "@/components/ui/field";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { StringsContext, translator } from "@/shell/strings";
import { fixtureDay } from "@/dev/fixtureDates";

const SUGGESTIONS = ["Alpha", "Alpine", "Beta"].map((word) => ({
  value: word,
  label: word,
}));

/** Every kind of layer that can open inside a dialog, for the browser tests of
 * who gets Escape. */
function Layers({ tallSuggestions = false }: { tallSuggestions?: boolean }) {
  const [day, setDay] = useState(fixtureDay(3, 14));
  const [text, setText] = useState("");
  const [choice, setChoice] = useState<string | null>(null);
  const [cancels, setCancels] = useState<string[]>([]);
  const [refused, setRefused] = useState(false);
  return (
    <>
      <Field>
        <FieldLabel htmlFor="day">Day</FieldLabel>
        <DateEditor id="day" value={day} onChange={setDay} />
      </Field>
      <Field>
        <FieldLabel htmlFor="text">Text</FieldLabel>
        <TextEditor
          id="text"
          value={text}
          onChange={setText}
          suggestions={
            tallSuggestions
              ? Array.from({ length: 8 }, (_, index) => ({
                  value: `Choice ${index + 1}`,
                  label: `Choice ${index + 1}: a deliberately long supplier name that wraps within the suggestion panel`,
                  note: "Additional supplied detail makes this option taller without changing the input focus.",
                }))
              : SUGGESTIONS
          }
        />
      </Field>
      <EditorField label="Choice" error={refused ? "Choose another." : null}>
        {({ id, invalid, describedBy }) => (
          <Combobox
            label="Choice"
            value={choice}
            options={SUGGESTIONS}
            emptyLabel="None"
            invalid={invalid}
            describedBy={describedBy}
            onCommit={setChoice}
            onCancel={(via) => setCancels((held) => [...held, via])}
          >
            <Button id={id} variant="outline">
              Pick
            </Button>
          </Combobox>
        )}
      </EditorField>
      <output data-testid="cancels">{cancels.join(" ")}</output>
      <Button variant="ghost" onClick={() => setRefused((held) => !held)}>
        Refuse
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline">Menu</Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem>Item</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="outline">Outer</Button>
        </PopoverTrigger>
        <PopoverContent role="dialog" aria-label="Outer popover">
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline">Inner</Button>
            </PopoverTrigger>
            <PopoverContent role="dialog" aria-label="Inner popover">
              <Button variant="ghost">Inside</Button>
            </PopoverContent>
          </Popover>
        </PopoverContent>
      </Popover>
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="outline">Quiet</Button>
        </PopoverTrigger>
        <PopoverContent
          role="dialog"
          aria-label="Quiet popover"
          onOpenAutoFocus={(event) => event.preventDefault()}
        >
          Focus stays on what opened this.
        </PopoverContent>
      </Popover>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="ghost">Explained</Button>
        </TooltipTrigger>
        <TooltipContent>Explanation</TooltipContent>
      </Tooltip>
      <Dialog>
        <DialogTrigger asChild>
          <Button variant="outline">Nested</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogTitle>Nested dialog</DialogTitle>
          <DialogDescription>On top of the first.</DialogDescription>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** The layers in a dialog and in a sheet, each opened from a button that takes
 * focus back when it closes. */
export function LayersHarness({ params }: { params: URLSearchParams }) {
  const translate = useMemo(
    () => translator(params.get("locale") ?? "en"),
    [params],
  );
  const [leaves, setLeaves] = useState(0);
  return (
    <StringsContext.Provider value={translate}>
      <Dialog
        onOpenChange={(open) => {
          if (!open) setLeaves((count) => count + 1);
        }}
      >
        <DialogTrigger asChild>
          <Button className="w-fit">Open dialog</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogTitle>Layers</DialogTitle>
          <DialogDescription>Each opens over this dialog.</DialogDescription>
          <Layers tallSuggestions={params.has("tallSuggestions")} />
        </DialogContent>
      </Dialog>
      <Sheet>
        <SheetTrigger asChild>
          <Button className="w-fit">Open sheet</Button>
        </SheetTrigger>
        <SheetContent closeLabel="Close">
          <SheetTitle>Sheet</SheetTitle>
          <SheetDescription>Each opens over this sheet.</SheetDescription>
          <Layers tallSuggestions={params.has("tallSuggestions")} />
        </SheetContent>
      </Sheet>
      <output data-testid="leaves">{leaves}</output>
    </StringsContext.Provider>
  );
}
