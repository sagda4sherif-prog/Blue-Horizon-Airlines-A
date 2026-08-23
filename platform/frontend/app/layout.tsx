import "./globals.css";

export const metadata = {
  title: "Blue Horizon Airlines — Ops Platform",
  description: "Flight operations agent chat and admin platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="topbar">
          <div className="topbar-title">Blue Horizon Airlines — Ops Platform</div>
          <nav className="topbar-nav">
            <a href="/">Chat</a>
            <a href="/admin">Admin</a>
          </nav>
        </div>
        {children}
      </body>
    </html>
  );
}
