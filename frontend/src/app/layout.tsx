import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Predator Brain — Value Betting AI",
  description: "Moteur de pronostics professionnels. Dixon-Coles, Value Bets, CLV, Backtesting.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className={inter.variable}>
      <body>{<Providers>{children}</Providers>}</body>
    </html>
  );
}
