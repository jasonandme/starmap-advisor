"use client";

import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from "react";

export type VisualStyle = "terminal-pro" | "research-paper" | "ledger-east";
export type ThemeMode = "light" | "dark" | "system";
type ResolvedMode = "light" | "dark";

type ThemeContextValue = {
  visualStyle: VisualStyle;
  mode: ThemeMode;
  resolvedMode: ResolvedMode;
  setVisualStyle: (style: VisualStyle) => void;
  setMode: (mode: ThemeMode) => void;
  toggle: () => void;
};

const visualStyles: VisualStyle[] = ["terminal-pro", "research-paper", "ledger-east"];
const modes: ThemeMode[] = ["light", "dark", "system"];

function getSystemMode(): ResolvedMode {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function resolveThemeMode(mode: ThemeMode): ResolvedMode {
  return mode === "system" ? getSystemMode() : mode;
}

function readStorage(key: string) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // 主题状态仍然会在当前页面生效，无法写入时只是不持久化。
  }
}

const ThemeContext = createContext<ThemeContextValue>({
  visualStyle: "terminal-pro",
  mode: "dark",
  resolvedMode: "dark",
  setVisualStyle: () => {},
  setMode: () => {},
  toggle: () => {}
});

export function useTheme() {
  return useContext(ThemeContext);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [visualStyle, setVisualStyleState] = useState<VisualStyle>("terminal-pro");
  const [mode, setModeState] = useState<ThemeMode>("dark");
  const [resolvedMode, setResolvedMode] = useState<ResolvedMode>("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const savedVisualStyle = readStorage("starmap-visual-style") as VisualStyle | null;
    const savedMode = readStorage("starmap-mode") as ThemeMode | null;
    const legacyTheme = readStorage("starmap-theme") as ThemeMode | null;
    const nextVisualStyle = savedVisualStyle && visualStyles.includes(savedVisualStyle)
      ? savedVisualStyle
      : "terminal-pro";
    const nextMode = savedMode && modes.includes(savedMode)
      ? savedMode
      : legacyTheme === "light" || legacyTheme === "dark"
        ? legacyTheme
        : "dark";
    const nextResolvedMode = resolveThemeMode(nextMode);

    setVisualStyleState(nextVisualStyle);
    setModeState(nextMode);
    setResolvedMode(nextResolvedMode);
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    function resolveMode() {
      setResolvedMode(resolveThemeMode(mode));
    }

    resolveMode();
    if (mode !== "system" || typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", resolveMode);
      return () => media.removeEventListener("change", resolveMode);
    }
    media.addListener(resolveMode);
    return () => media.removeListener(resolveMode);
  }, [mode, mounted]);

  useEffect(() => {
    if (!mounted) return;
    const root = document.documentElement;
    root.classList.remove("dark", "light");
    root.classList.add(resolvedMode);
    root.dataset.style = visualStyle;
    root.dataset.mode = mode;
    root.dataset.resolvedMode = resolvedMode;
    writeStorage("starmap-visual-style", visualStyle);
    writeStorage("starmap-mode", mode);
    writeStorage("starmap-theme", resolvedMode);
  }, [visualStyle, mode, resolvedMode, mounted]);

  const setVisualStyle = useCallback((style: VisualStyle) => {
    setVisualStyleState(style);
  }, []);

  const setMode = useCallback((nextMode: ThemeMode) => {
    setModeState(nextMode);
  }, []);

  const toggle = useCallback(() => {
    setModeState((current) => {
      const currentResolved = resolveThemeMode(current);
      return currentResolved === "dark" ? "light" : "dark";
    });
  }, []);

  // Prevent flash of wrong theme
  if (!mounted) {
    return <div style={{ visibility: "hidden" }}>{children}</div>;
  }

  return (
    <ThemeContext.Provider value={{ visualStyle, mode, resolvedMode, setVisualStyle, setMode, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}
