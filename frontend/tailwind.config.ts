import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        ink: "var(--text-primary)",
        "ink-secondary": "var(--text-secondary)",
        "ink-muted": "var(--text-muted)",
        panel: "var(--bg-surface)",
        "panel-solid": "var(--bg-card-solid)",
        card: "var(--bg-card)",
        line: "var(--border)",
        "line-strong": "var(--border-strong)",
        "line-glow": "var(--border-glow)",
        jade: "var(--accent)",
        "jade-soft": "var(--accent-soft)",
        "accent-soft": "var(--accent-soft)",
        "accent-strong": "var(--accent-strong)",
        "jade-dim": "var(--accent-dim)",
        up: "var(--up)",
        down: "var(--down)",
        amberline: "var(--warn)",
        rosemark: "var(--up)",
        "surface-0": "var(--surface-0)",
        "surface-1": "var(--surface-1)",
        "surface-2": "var(--surface-2)",
        "surface-3": "var(--surface-3)",
        "chart-1": "var(--chart-1)",
        "chart-2": "var(--chart-2)",
        "chart-3": "var(--chart-3)",
        "chart-4": "var(--chart-4)",
        "chart-grid": "var(--chart-grid)"
      },
      boxShadow: {
        quiet: "var(--shadow-quiet)",
        card: "var(--shadow-card)",
        hover: "var(--shadow-hover)",
        glow: "var(--shadow-glow)",
        "glow-md": "var(--shadow-glow-md)",
        "glow-lg": "var(--shadow-glow-lg)",
        "inner-glow": "var(--shadow-inner-glow)"
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "card-shine": "linear-gradient(135deg, var(--accent-soft) 0%, transparent 60%)",
        "card-subtle": "linear-gradient(180deg, var(--bg-card) 0%, var(--surface-1) 100%)"
      },
      animation: {
        "fade-in": "fadeInUp 0.4s ease-out both",
        "fade-in-delay": "fadeInUp 0.4s ease-out 0.1s both",
        "pulse-glow": "pulse-glow 2s ease-in-out infinite"
      },
      keyframes: {
        fadeInUp: {
          from: { opacity: "0", transform: "translateY(12px)" },
          to: { opacity: "1", transform: "translateY(0)" }
        },
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 8px rgba(16,185,129,0.15)" },
          "50%": { boxShadow: "0 0 16px rgba(16,185,129,0.3)" }
        }
      },
      borderRadius: {
        card: "var(--radius-card)",
        button: "var(--radius-button)",
        xl: "12px",
        "2xl": "16px"
      }
    }
  },
  plugins: []
};

export default config;
