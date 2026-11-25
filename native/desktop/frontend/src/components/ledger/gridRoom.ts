import { createContext } from "react";

/** How the movements grid and the panel beside it share the row: the grid
 * says the least width it needs to show any scrolling column whole, and
 * the page gives the panel the least the grid's column keeps. */
export type GridRoom = {
  /** In CSS pixels; null keeps the panel's own least for the grid. */
  columnFloor: number | null;
  onLeast?: (width: number) => void;
};

export const GridRoomContext = createContext<GridRoom>({ columnFloor: null });
