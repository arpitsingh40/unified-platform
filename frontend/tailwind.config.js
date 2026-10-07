/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: "class",
    content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
    extend: {
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
        xl: '12px',
        '2xl': '16px',
        '3xl': '24px',
      },
      colors: {
        background: 'hsl(var(--background))',
        surface: 'hsl(var(--surface))',
        'surface-2': 'hsl(var(--surface-2))',
        hairline: 'hsl(var(--hairline))',
        text: 'hsl(var(--text))',
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          wash: 'hsl(var(--accent-wash))',
          foreground: 'hsl(var(--text))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(0 0% 98%)',
        },
        /* legacy shadcn aliases — map to new tokens */
        card: {
          DEFAULT: 'hsl(var(--surface))',
          foreground: 'hsl(var(--text))',
        },
        popover: {
          DEFAULT: 'hsl(var(--surface))',
          foreground: 'hsl(var(--text))',
        },
        primary: {
          DEFAULT: 'hsl(var(--text))',
          foreground: 'hsl(var(--background))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--surface-2))',
          foreground: 'hsl(var(--text))',
        },
        border: 'hsl(var(--hairline))',
        input: 'hsl(var(--hairline))',
        ring: 'hsl(var(--accent))',
      },
      spacing: {
        '0.5': '2px',
        '1': '4px',
        '2': '8px',
        '3': '12px',
        '4': '16px',
        '5': '20px',
        '6': '24px',
        '8': '32px',
        '10': '40px',
        '12': '48px',
        '14': '56px',
        '16': '64px',
      },
      boxShadow: {
        'elevation-1': 'var(--shadow-elevation-1)',
        'elevation-2': 'var(--shadow-elevation-2)',
        'elevation-3': 'var(--shadow-elevation-3)',
        'elevation-4': 'var(--shadow-elevation-4)',
      },
      keyframes: {
        'field-in': {
          from: { opacity: '0', transform: 'translateY(4px)', filter: 'blur(2px)' },
          to: { opacity: '1', transform: 'translateY(0)', filter: 'blur(0)' },
        },
        'pulse-width': {
          '0%, 100%': { width: '1.75rem' },
          '50%': { width: '2.5rem' },
        },
        'shimmer-slide': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(200%)' },
        },
        'bounce-x': {
          '0%, 100%': { transform: 'translateX(0)' },
          '50%': { transform: 'translateX(4px)' },
        },
        'bounce-y': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(4px)' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0)', opacity: '0.4' },
          '50%': { transform: 'translateY(6px)', opacity: '0.8' },
        },
        'pulse-soft': {
          '0%, 100%': { transform: 'scale(1)' },
          '50%': { transform: 'scale(1.05)' },
        },
        'spin-slow': {
          from: { transform: 'rotate(0deg)' },
          to: { transform: 'rotate(360deg)' },
        },
        'spin-reverse': {
          from: { transform: 'rotate(360deg)' },
          to: { transform: 'rotate(0deg)' },
        },
        'scale-pulse': {
          '0%, 100%': { transform: 'scale(1)', opacity: '0.3' },
          '50%': { transform: 'scale(1.2)', opacity: '0.5' },
        },
        'scale-pulse-2': {
          '0%, 100%': { transform: 'scale(1)', opacity: '0.2' },
          '50%': { transform: 'scale(1.3)', opacity: '0.4' },
        },
        'shake': {
          '0%, 100%': { transform: 'rotate(0deg)' },
          '25%': { transform: 'rotate(-5deg)' },
          '75%': { transform: 'rotate(5deg)' },
        },
      },
      animation: {
        'field-in': 'field-in 0.26s ease-out both',
        'pulse-width': 'pulse-width 2.5s ease-in-out infinite',
        'shimmer-slide': 'shimmer-slide 2s linear infinite',
        'bounce-x': 'bounce-x 1.5s ease-in-out infinite',
        'bounce-y': 'bounce-y 1.5s ease-in-out infinite',
        'float': 'float 2.5s ease-in-out infinite',
        'pulse-soft': 'pulse-soft 6s ease-in-out infinite',
        'spin-slow': 'spin-slow 40s linear infinite',
        'spin-reverse': 'spin-reverse 30s linear infinite',
        'scale-pulse': 'scale-pulse 8s ease-in-out infinite',
        'scale-pulse-2': 'scale-pulse-2 10s ease-in-out infinite',
        'shake': 'shake 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
