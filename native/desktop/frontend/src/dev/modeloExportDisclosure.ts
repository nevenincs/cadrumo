import type { ModeloExportDisclosure } from "../shell/modeloContract/modeloExport";

/** What an export's result discloses beside its file, in placeholder words:
 * the lead sentence, one limitation on a box and one on the whole
 * declaration. The window draws the served sentences as they are. */
export const EXPORT_DISCLOSURE: ModeloExportDisclosure = {
  lead_words: "Synthetic lead: this file carries the limits below as they are.",
  limitations: [
    {
      message_locale_key: "synthetic.disclosure.box_limit",
      casilla_id: "0001",
      words: "Synthetic limit: one box is left out of the calculation.",
    },
    {
      message_locale_key: "synthetic.disclosure.declaration_limit",
      casilla_id: null,
      words: "Synthetic limit: one figure rests on a value you stated.",
    },
  ],
};
