/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        gold: {
          DEFAULT: "#C9A227",
          light: "#E6C878",
          dark: "#9A7C1E",
        },
        charcoal: {
          950: "#0B0B0D",
          900: "#121214",
          800: "#18181B",
          700: "#222226",
          600: "#2C2C31",
          border: "#33333A",
        },
      },
      fontFamily: {
        display: ["Inter", "system-ui", "sans-serif"],
        body: ["Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        gold: "0 0 0 1px rgba(201,162,39,0.25), 0 8px 24px -8px rgba(201,162,39,0.25)",
      },
      backgroundImage: {
        "gold-gradient": "linear-gradient(135deg, #C9A227 0%, #E6C878 100%)",
      },
    },
  },
  plugins: [],
};
