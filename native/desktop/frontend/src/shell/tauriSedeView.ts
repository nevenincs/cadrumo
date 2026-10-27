import { Channel } from "@tauri-apps/api/core";
import type { SedeViewDelivery } from "../ipc/contract";
import type { HostCall } from "./hostCall";
import { sedeViewReader, type SedeViewPort } from "./sedeView";

/** The Sede view port over the desktop host's `sede_view_*` commands. */
export function tauriSedeView(call: HostCall): SedeViewPort {
  return {
    async open(size, listener) {
      const messages = new Channel<SedeViewDelivery>();
      const reader = sedeViewReader((event) => {
        listener(event);
        if (event.kind === "ended") messages.onmessage = () => undefined;
      });
      messages.onmessage = reader.accept;

      let opened: { view: number };
      try {
        opened = await call("sede_view_open", { ...size, messages });
      } catch (error) {
        messages.onmessage = () => undefined;
        throw error;
      }
      const id = opened.view;
      reader.open(id);

      return {
        input: (event) =>
          call("sede_view_input", { view: id, event }).then(() => undefined),
        navigate: (verb) =>
          call("sede_view_navigate", { view: id, verb }).then(() => undefined),
        resize: ({ cssWidth, cssHeight, scale }) =>
          call("sede_view_resize", {
            view: id,
            cssWidth,
            cssHeight,
            scale,
          }).then(() => undefined),
        credit: () =>
          call("sede_view_credit", { view: id }).then(() => undefined),
        dialog: (dialogId, accept, promptText) =>
          call("sede_view_dialog", {
            view: id,
            dialogId,
            accept,
            ...(promptText === undefined ? {} : { promptText }),
          }).then(() => undefined),
        downloadAnswer: (transferId, save) =>
          call("sede_view_download_answer", { view: id, transferId, save }),
        fileChooserAnswer: (chooserId, choose) =>
          call("sede_view_file_chooser_answer", {
            view: id,
            chooserId,
            choose,
          }),
        openExternal: (offerId) =>
          call("sede_view_open_external", {
            view: id,
            ...(offerId === undefined ? {} : { offerId }),
          }).then(() => undefined),
        close: () =>
          call("sede_view_close", { view: id }).then(() => undefined),
      };
    },
  };
}
