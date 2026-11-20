import type { Metadata } from "next";
import { Google_Sans, Google_Sans_Code } from "next/font/google";

import { Providers } from "@/components/providers";
import "./globals.css";

// The variable names must NOT be --font-sans/--font-mono: next/font sets them
// on <html>, which is also :root, so the Tailwind theme token would reference
// itself. CSS treats that as a cycle, discards the property, and the page
// silently renders in the browser default face.
const googleSans = Google_Sans({
  variable: "--font-google-sans",
  subsets: ["latin"],
  display: "swap",
});

// Same family's monospace, for tabular figures and code.
const googleSansCode = Google_Sans_Code({
  variable: "--font-google-sans-code",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "BiasHawk",
  description: "AI fairness, data quality and NIST risk assessment.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${googleSans.variable} ${googleSansCode.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
