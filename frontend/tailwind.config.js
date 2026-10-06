/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#14171F",
        canvas: "#F6F7F5",
        surface: "#FFFFFF",
        line: "#E4E7E2",
        brand: {
          DEFAULT: "#1F5D4C",
          deep: "#163F33",
          light: "#E9F1EE",
        },
        status: {
          new: "#64748B",
          contacted: "#2563EB",
          qualified: "#0D9488",
          proposal: "#B9860B",
          won: "#1F5D4C",
          lost: "#B0433B",
        },
      },
      fontFamily: {
        display: ["Sora", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
