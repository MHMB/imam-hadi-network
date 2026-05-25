import type { Metadata, Viewport } from "next";
import { Vazirmatn } from "next/font/google";
import "./globals.css";
import { messages } from "@/lib/i18n";
import { ReactQueryProvider } from "@/lib/query/provider";
import { AppShell } from "@/components/shell/AppShell";

// Vazirmatn from Google Fonts — auto-self-hosted by Next at build time.
// No CDN dependency at runtime, no FOUT on slow networks.
const vazirmatn = Vazirmatn({
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-vazirmatn",
  display: "swap",
  fallback: ["system-ui", "Tahoma", "Arial"],
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
      <body className="min-h-screen bg-slate-50 font-sans text-slate-900 antialiased">
        <ReactQueryProvider>
          <AppShell>{children}</AppShell>
        </ReactQueryProvider>
      </body>
    </html>
  );
}
