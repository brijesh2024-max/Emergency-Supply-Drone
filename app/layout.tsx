import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Aeris | Rescue Operations",
  description: "Emergency rescue and supply exercise command center",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="stylesheet" href="/vendor/leaflet/leaflet.css" />
      </head>
      <body>{children}</body>
    </html>
  );
}
