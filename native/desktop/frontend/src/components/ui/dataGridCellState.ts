import * as React from "react";

export const CellStateContext = React.createContext({ focused: false });

export const FOCUSED = { focused: true };
export const UNFOCUSED = { focused: false };
