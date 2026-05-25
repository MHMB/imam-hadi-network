import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx,js,jsx,mdx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-vazirmatn)", "system-ui", "sans-serif"],
      },
      colors: {
        // Status palette — tuned for accessible RTL Persian UI
        paid: {
          DEFAULT: "#16a34a", // green-600
          subtle: "#dcfce7",
        },
        unpaid: {
          DEFAULT: "#64748b", // slate-500
          subtle: "#f1f5f9",
        },
        overdue: {
          DEFAULT: "#dc2626", // red-600
          subtle: "#fee2e2",
        },
      },
    },
  },
  // tailwindcss-rtl adds logical-direction utility variants
  plugins: [require("tailwindcss-rtl")],
};

export default config;
