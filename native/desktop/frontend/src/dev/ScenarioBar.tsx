import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Separator } from "@/components/ui/separator";
import { SCENARIOS, type Scenario } from "./scenarios";

/** One host call, numbered so the list keeps its rows as it slides. */
export type HostCallLine = { id: number; call: string };

// The development entry's own control: it names the page as simulated and
// switches scenario and language. It is built from the shell's primitives
// only, so it follows the theme like everything else. Its text is tool text,
// not product chrome, so it is not in the locale catalogues, and it never
// ships.
export function ScenarioBar({
  scenario,
  language,
  languages,
  calls,
  onScenario,
  onLanguage,
  onRestart,
}: {
  scenario: Scenario;
  language: string;
  languages: readonly string[];
  calls: readonly HostCallLine[];
  onScenario: (id: string) => void;
  onLanguage: (language: string) => void;
  onRestart: () => void;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="xs"
          className="scenario-bar pointer-events-auto fixed right-2 bottom-2 z-(--layer-toast) gap-2 shadow-raised"
        >
          <Badge variant="warning">Simulated host</Badge>
          {scenario.title}
        </Button>
      </PopoverTrigger>
      <PopoverContent side="top" align="end" className="grid w-settings gap-3">
        <p className="text-sm text-muted-foreground">
          Nothing here reaches a desktop host. A sign-in this page accepts
          authenticated nothing.
        </p>
        <Field>
          <FieldLabel id="scenario-label">Scenario</FieldLabel>
          <div
            role="group"
            aria-labelledby="scenario-label"
            className="grid grid-cols-2 gap-1"
          >
            {SCENARIOS.map((entry) => (
              <Button
                key={entry.id}
                variant="ghost"
                size="xs"
                className="justify-start"
                aria-pressed={entry.id === scenario.id}
                onClick={() => onScenario(entry.id)}
              >
                <span className="truncate">{entry.title}</span>
              </Button>
            ))}
          </div>
          <FieldDescription>{scenario.summary}</FieldDescription>
        </Field>
        <Field>
          <FieldLabel id="scenario-language">Language</FieldLabel>
          <SegmentedControl
            aria-labelledby="scenario-language"
            value={language}
            onValueChange={onLanguage}
          >
            {languages.map((code) => (
              <SegmentedControlItem key={code} value={code}>
                {code}
              </SegmentedControlItem>
            ))}
          </SegmentedControl>
        </Field>
        <Separator />
        <Field>
          <div className="flex items-center justify-between gap-2">
            <FieldLabel id="scenario-calls">Host calls</FieldLabel>
            <Button variant="outline" size="xs" onClick={onRestart}>
              Restart scenario
            </Button>
          </div>
          <ol
            aria-labelledby="scenario-calls"
            className="max-h-32 overflow-auto rounded-md bg-muted px-2 py-1 font-mono text-xs text-muted-foreground"
          >
            {calls.map(({ id, call }) => (
              <li key={id}>{call}</li>
            ))}
          </ol>
        </Field>
      </PopoverContent>
    </Popover>
  );
}
