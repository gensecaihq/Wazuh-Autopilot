import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { load, save } from "./storage";

type Theme = "dark" | "light";
const Ctx = createContext<{ theme: Theme; setTheme: (t: Theme) => void }>({ theme: "dark", setTheme: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => (load("ap.theme") === "light" ? "light" : "dark"));
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);
  const setTheme = useCallback((t: Theme) => {
    save("ap.theme", t);
    setThemeState(t);
  }, []);
  return <Ctx.Provider value={{ theme, setTheme }}>{children}</Ctx.Provider>;
}

export const useTheme = () => useContext(Ctx);

/** Read a CSS token as an `rgb()` color string for chart libraries. */
export function token(name: string, alpha = 1): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim() || "255 129 39";
  return `rgb(${v.split(/\s+/).join(" ")} / ${alpha})`;
}
