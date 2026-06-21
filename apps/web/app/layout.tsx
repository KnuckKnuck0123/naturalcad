import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NaturalCAD",
  description: "Prompt-to-CAD for fast generation, iteration, and export.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.4.0/model-viewer.min.js"></script>
      </head>
      <body>{children}</body>
    </html>
  );
}
