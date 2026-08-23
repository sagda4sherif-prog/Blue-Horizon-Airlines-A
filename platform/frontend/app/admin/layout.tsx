export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <a href="/admin">Overview</a>
        <a href="/admin/tools">Agent Tools</a>
        <a href="/admin/rag">RAG Documents</a>
        <a href="/admin/tickets">Tickets</a>
        <a href="/admin/hitl">HITL Queue</a>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
