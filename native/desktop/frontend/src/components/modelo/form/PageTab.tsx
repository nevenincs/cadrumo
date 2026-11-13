import { Badge } from "@/components/ui/badge";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { TabsTrigger } from "@/components/ui/tabs";
import type {
  ModeloFormCounts,
  ModeloFormText,
} from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings } from "../../../shell/strings";
import { calm } from "./FieldRow";

/** What a page tab needs of a page: the heading as the application served it,
 * with the account of where it came from. */
export type PageTabPage = {
  id: string;
  heading: ModeloFormText;
  applies: boolean | null;
  counts: ModeloFormCounts | null;
};

/**
 * One page's tab, worded by the heading the application served for the page.
 * A page the application could name only by its registry path serves that
 * path with the disclosure `technical`: it is a key, not words, so it is
 * drawn as the last resort it is, carried in `data-key` and glossed by the
 * served words for a technical name, and the window words nothing of its own.
 */
export function PageTab({ page, panel }: { page: PageTabPage; panel: string }) {
  const t = useStrings();
  const todo = page.counts?.needs_you ?? 0;
  const key = page.heading.disclosure === "technical";
  return (
    <TabsTrigger
      value={page.id}
      aria-controls={panel}
      data-heading-disclosure={page.heading.disclosure}
      className={cn("shrink-0", page.applies === false && "text-faint")}
    >
      {key ? (
        <span
          data-key={page.heading.text}
          title={t("workspace.modelo.disclosure.technical")}
          className="italic"
        >
          {page.heading.text}
        </span>
      ) : (
        calm(page.heading.text)
      )}
      {todo > 0 && page.applies !== false && (
        <Badge variant="warning">
          <Icon name="alert" size="xs" />
          {todo}
        </Badge>
      )}
    </TabsTrigger>
  );
}
