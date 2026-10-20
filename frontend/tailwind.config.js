/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Акцент — глубокий оранжево-красный (кирпичный).
        accent: {
          DEFAULT: '#EA580C',
          strong: '#C2410C',
          deep: '#9A3412',
          soft: '#FFEDD5',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
        bar: '0 -4px 16px 0 rgb(0 0 0 / 0.06)',
      },
    },
  },
  plugins: [],
}
