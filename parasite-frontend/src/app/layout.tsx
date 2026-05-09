import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'PARASITE',
  description: 'Live Trading Organism',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-parasite-bg text-parasite-bright font-mono antialiased">
        {children}
      </body>
    </html>
  );
}