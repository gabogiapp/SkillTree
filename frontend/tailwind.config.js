/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        canvas: {
          bg: '#090d16',
          panel: '#111827',
          border: '#1f2937',
        },
        ground: {
          border: '#3b82f6',
          glow: 'rgba(59, 130, 246, 0.25)',
          badge: '#1d4ed8',
        },
        bridge: {
          border: '#a855f7',
          glow: 'rgba(168, 85, 247, 0.35)',
          badge: '#7e22ce',
        },
      },
      animation: {
        'pulse-subtle': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow-pulse': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 10px rgba(168, 85, 247, 0.4)' },
          '100%': { boxShadow: '0 0 22px rgba(168, 85, 247, 0.8)' },
        },
      },
    },
  },
  plugins: [],
};
