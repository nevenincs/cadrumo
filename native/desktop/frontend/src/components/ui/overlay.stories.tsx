import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { Specimen } from "@/dev/catalogue/Frame";
import { Button } from "./button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "./command";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "./dialog";
import { Icon } from "./icon";
import { Kbd } from "./kbd";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "./tooltip";

const meta = { title: "Primitives/Overlays and navigation" } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const DialogAndPopover: Story = {
  render: () => (
    <div>
      <Specimen
        title="Dialog"
        note="Modal: focus is trapped inside and returns to the opener. Escape or a press outside closes it."
      >
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="outline">Open dialog</Button>
          </DialogTrigger>
          <DialogContent closeLabel="Close">
            <DialogHeader>
              <DialogTitle>Reset the layout?</DialogTitle>
              <DialogDescription>
                Panes, sizes and the open tab return to their defaults.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="ghost">Cancel</Button>
              <Button>Reset layout</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </Specimen>
      <Specimen
        title="Popover"
        note="Non-modal, anchored to its trigger, never larger than the window."
      >
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline">Open popover</Button>
          </PopoverTrigger>
          <PopoverContent align="start" className="grid w-72 gap-2">
            <p className="font-serif text-lg">Settings</p>
            <p className="text-sm text-muted-foreground">
              A popover holds a few related controls.
            </p>
          </PopoverContent>
        </Popover>
      </Specimen>
      <Specimen
        title="Tooltip"
        note="Names a control; it is never the only way to learn something."
      >
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="outline">Hover or focus me</Button>
          </TooltipTrigger>
          <TooltipContent>
            Search <Kbd>Ctrl+K</Kbd>
          </TooltipContent>
        </Tooltip>
      </Specimen>
    </div>
  ),
};

function PanelTabs() {
  const [tab, setTab] = useState("console");
  return (
    <Tabs value={tab} onValueChange={setTab} className="w-full bg-chrome">
      <TabsList className="border-b px-2">
        <TabsTrigger value="console">
          <Icon name="console" />
          Console
        </TabsTrigger>
        <TabsTrigger value="python">
          <Icon name="python" />
          Python
        </TabsTrigger>
        <TabsTrigger value="logs">
          <Icon name="logs" />
          Logs
        </TabsTrigger>
        <TabsTrigger value="off" disabled>
          Disabled
        </TabsTrigger>
      </TabsList>
      {["console", "python", "logs"].map((value) => (
        <TabsContent key={value} value={value} className="bg-background p-4">
          The {value} panel.
        </TabsContent>
      ))}
    </Tabs>
  );
}

export const TabRow: Story = {
  parameters: { surface: "chrome" },
  render: () => (
    <Specimen
      title="Tabs"
      note="One tab stop; arrow keys move and choose. The chosen tab is underlined."
      className="grid"
    >
      <PanelTabs />
    </Specimen>
  ),
};

export const CommandList_: Story = {
  name: "Command list",
  parameters: { surface: "chrome" },
  render: () => (
    <Specimen
      title="Command"
      note="Focus stays in the input; arrows, Home and End move the choice, Enter runs it."
    >
      <div className="h-80 w-full max-w-palette overflow-hidden rounded-2xl border shadow-overlay">
        <Command label="Command palette">
          <CommandInput placeholder="Search documentation and actions">
            <Kbd>Esc</Kbd>
          </CommandInput>
          <CommandList>
            <CommandEmpty>Nothing matches.</CommandEmpty>
            <CommandGroup heading="Documentation">
              <CommandItem value="modelo">
                <Icon name="term" size="md" className="text-faint" />
                Modelo
              </CommandItem>
              <CommandItem value="casilla">
                <Icon name="page" size="md" className="text-faint" />
                Casilla 01
              </CommandItem>
            </CommandGroup>
            <CommandGroup heading="Actions">
              <CommandItem value="show tui">
                <Icon name="tui" size="md" className="text-faint" />
                <span className="flex-1">Show the TUI</span>
                <Kbd>Ctrl+Shift+T</Kbd>
              </CommandItem>
              <CommandItem value="settings">
                <Icon name="settings" size="md" className="text-faint" />
                <span className="flex-1">Settings</span>
                <Kbd>Ctrl+,</Kbd>
              </CommandItem>
              <CommandItem value="disabled" disabled>
                <Icon name="copy" size="md" className="text-faint" />A disabled
                action
              </CommandItem>
            </CommandGroup>
          </CommandList>
        </Command>
      </div>
    </Specimen>
  ),
};
