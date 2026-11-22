import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#f6f7f9",
          100: "#eceef2",
          200: "#d5dae3",
          300: "#b1bac9",
          400: "#8593aa",
          500: "#66758f",
          600: "#515e76",
          700: "#424c60",
          800: "#3a4252",
          900: "#343a47",
          950: "#22262f",
        },
        accent: {
          50: "#fff8eb",
          100: "#ffecc6",
          200: "#ffd588",
          300: "#ffb84a",
          400: "#ff9b1f",
          500: "#f97c07",
          600: "#dd5a02",
          700: "#b73e06",
          800: "#94300c",
          900: "#7a290d",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,0.05), 0 1px 3px rgba(16,24,40,0.06)",
      },
    },
  },
  plugins: [],
};

export default config;
