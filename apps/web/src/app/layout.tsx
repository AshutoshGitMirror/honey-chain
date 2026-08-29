import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Honey Chain — web",
  description: "Honey Chain web - KVIC Honey Mission",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
