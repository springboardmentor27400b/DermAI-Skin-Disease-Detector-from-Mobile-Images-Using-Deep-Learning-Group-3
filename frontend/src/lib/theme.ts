import { useEffect } from "react";
import type { ThemeKey } from "./roles";

export function useTheme(theme: ThemeKey) {
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
}

