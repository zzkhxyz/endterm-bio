"use client";

import { useEffect, useState } from "react";

export default function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  useEffect(() => { if (localStorage.getItem("pdx-theme") === "dark") setTheme("dark"); }, []);
  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem("pdx-theme", theme); }, [theme]);
  return <button type="button" className="theme-toggle" onClick={() => setTheme(theme === "light" ? "dark" : "light")} aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}>{theme === "light" ? "◐" : "◑"}<span>Theme</span></button>;
}
