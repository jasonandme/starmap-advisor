"use client";

import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";

export type VisualStyle = "terminal-pro" | "research-paper" | "ledger-east";
export type ThemeMode = "light" | "dark" | "system";
type ResolvedMode = "light" | "dark";

type ThemeContextValue = {
  visualStyle: VisualStyle;
  mode: ThemeMode;
  resolvedMode: ResolvedMode;
  setVisualStyle: (style: VisualStyle) => void;
  setMode: (mode: ThemeMode) => void;
  resetTheme: () => void;
  toggle: () => void;
};

const DEFAULT_VISUAL_STYLE: VisualStyle = "terminal-pro";
const DEFAULT_MODE: ThemeMode = "dark";
const THEME_STORAGE_VERSION = "2026-06-11-theme-v2";
const THEME_VERSION_KEY = "starmap-theme-version";
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
    // The theme still applies for the current page when storage is unavailable.
  }
}

const ThemeContext = createContext<ThemeContextValue>({
  visualStyle: DEFAULT_VISUAL_STYLE,
  mode: DEFAULT_MODE,
  resolvedMode: "dark",
  setVisualStyle: () => {},
  setMode: () => {},
  resetTheme: () => {},
  toggle: () => {}
});

export function useTheme() {
  return useContext(ThemeContext);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [visualStyle, setVisualStyleState] = useState<VisualStyle>(DEFAULT_VISUAL_STYLE);
  const [mode, setModeState] = useState<ThemeMode>(DEFAULT_MODE);
  const [resolvedMode, setResolvedMode] = useState<ResolvedMode>("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const savedVersion = readStorage(THEME_VERSION_KEY);
    const savedVisualStyle = readStorage("starmap-visual-style") as VisualStyle | null;
    const savedMode = readStorage("starmap-mode") as ThemeMode | null;
    const canUseSavedTheme = savedVersion === THEME_STORAGE_VERSION;
    const nextVisualStyle = canUseSavedTheme && savedVisualStyle && visualStyles.includes(savedVisualStyle)
      ? savedVisualStyle
      : DEFAULT_VISUAL_STYLE;
    const nextMode = canUseSavedTheme && savedMode && modes.includes(savedMode)
      ? savedMode
      : DEFAULT_MODE;
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
    writeStorage(THEME_VERSION_KEY, THEME_STORAGE_VERSION);
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

  const resetTheme = useCallback(() => {
    setVisualStyleState(DEFAULT_VISUAL_STYLE);
    setModeState(DEFAULT_MODE);
  }, []);

  const toggle = useCallback(() => {
    setModeState((current) => {
      const currentResolved = resolveThemeMode(current);
      return currentResolved === "dark" ? "light" : "dark";
    });
  }, []);

  if (!mounted) {
    return <div style={{ visibility: "hidden" }}>{children}</div>;
  }

  return (
    <ThemeContext.Provider value={{ visualStyle, mode, resolvedMode, setVisualStyle, setMode, resetTheme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}
