import type { Metadata } from "next";
import "katex/dist/katex.min.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Synergy, or simple addition? — PDX combination therapy",
  description: "A transparent ODE analysis of BYL719 and LJM716 in patient-derived xenografts: the synergy signal depends on dose assumptions.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
