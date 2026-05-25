import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { messages } from "@/lib/i18n";

// Vazirmatn — self-hosted (Phase 4 will drop the WOFF2 files into web/public/fonts/).
// Until then we declare the family so Tailwind's `font-sans` class compiles.
const vazirmatn = localFont({
  src: [
    {
      path: "../../public/fonts/Vazirmatn-Regular.woff2",
      weight: "400",
      style: "normal",
    },
    {
      path: "../../public/fonts/Vazirmatn-Bold.woff2",
      weight: "700",
      style: "normal",
    },
  ],
  variable: "--font-vazirmatn",
  display: "swap",
  // OK to fall back to system fonts during development if files are absent.
  fallback: ["system-ui", "Tahoma", "Arial"],
  adjustFontFallback: false,
  preload: false,
});

export const metadata: Metadata = {
  title: messages.appTitle,
  description: messages.appDescription,
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0f172a",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl" className={vazirmatn.variable}>
      <body className="min-h-screen bg-white font-sans text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
