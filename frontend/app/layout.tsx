import "./globals.css";

export const metadata = {
  title: "Azzurro Hotels — Review Insights",
  description: "Guest review monitoring for Azzurro Hotels properties",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen text-slate-800">{children}</body>
    </html>
  );
}
