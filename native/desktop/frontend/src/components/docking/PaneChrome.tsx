import { createContext, useContext, type ReactNode } from "react";

const Docked = createContext(false);

/** The surrounding tab strip owns the pane title and window controls. */
export function DockedPane({ children }: { children: ReactNode }) {
  return <Docked.Provider value>{children}</Docked.Provider>;
}

export function useDockedPane() {
  return useContext(Docked);
}
