/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx}", "./src/app/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] },
      colors: { drift: { black: "#0a0a0a", cream: "#FFF8F0", accent: "#FF3B30" } }
    }
  },
  plugins: []
};
