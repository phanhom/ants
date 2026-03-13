/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "sans-serif",
        ],
      },
      colors: {
        surface: {
          DEFAULT: "rgba(22, 27, 34, 0.8)",
          solid: "#161b22",
          raised: "rgba(30, 37, 46, 0.85)",
          overlay: "rgba(22, 27, 34, 0.95)",
        },
        border: {
          DEFAULT: "rgba(240, 246, 252, 0.08)",
          subtle: "rgba(240, 246, 252, 0.04)",
          strong: "rgba(240, 246, 252, 0.16)",
        },
        accent: {
          DEFAULT: "#58a6ff",
          muted: "rgba(88, 166, 255, 0.15)",
        },
      },
      borderRadius: {
        xl: "12px",
        "2xl": "16px",
      },
      backdropBlur: {
        glass: "20px",
      },
      animation: {
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.3s ease-out",
      },
      keyframes: {
        fadeIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        slideUp: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
