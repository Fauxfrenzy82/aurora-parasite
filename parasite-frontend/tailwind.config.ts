import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/app/**/*.{js,ts,jsx,tsx}',
    './src/components/**/*.{js,ts,jsx,tsx}',
    './src/lib/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        parasite: {
          green: '#00ff44',
          amber: '#ffb800',
          red: '#ff3344',
          bg: '#0a0a0a',
          surface: '#111111',
          border: '#1a1a1a',
          text: '#888888',
          bright: '#cccccc',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;