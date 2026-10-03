declare module "virtual:desktop-content" {
  export interface Chapter {
    id: string;
    title: string;
    source: string;
    markdown: string;
  }
  export const identity: {
    display_name: string;
    prose_name: string;
    cli_executable: string;
  };
  export const chapters: Chapter[];
  export const mark: string;
}
