import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Preicfes Plan Studio",
  description: "Editor y generador web de planes ICFES",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
