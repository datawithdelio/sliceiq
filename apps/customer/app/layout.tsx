import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Customer App",
  description: "SliceIQ customer storefront",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
