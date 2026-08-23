"use client";

import { useEffect, useState } from "react";
import {
  getRagDocuments,
  addRagDocument,
  removeRagDocument,
  RagDocument,
} from "@/lib/api";

export default function RagPage() {
  const [docs, setDocs] = useState<RagDocument[]>([]);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    getRagDocuments()
      .then((r) => setDocs(r.documents))
      .catch((e) => setError(e.message));
  }

  useEffect(load, []);

  async function handleAdd() {
    if (!title.trim() || !content.trim()) return;

    setBusy(true);
    setError(null);
    setNotice(null);

    try {
      const res = await addRagDocument(title, content);
      setTitle("");
      setContent("");
      load();

      setNotice(
        res.indexed
          ? "Document saved and indexed — the RAG agent will retrieve it on the next query."
          : "Document saved, but the RAG pipeline doesn't expose add_document() yet, so it's not searchable until that lands (see platform/API_CONTRACT.md)."
      );
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(docId: number) {
    setError(null);
    setNotice(null);

    try {
      const res: any = await removeRagDocument(docId);
      load();

      setNotice(
        res.removed_from_index
          ? "Removed from the index."
          : "Marked removed here, but couldn't remove from the live index yet (pipeline doesn't expose remove_document() yet)."
      );
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <div>
      <h2>RAG Documents</h2>
      <p className="muted">
        Add or remove documents the Policy &amp; Knowledge agent can retrieve from.
      </p>

      {error && <div className="card" style={{ color: "#c0392b" }}>{error}</div>}
      {notice && <div className="card" style={{ color: "#1a73e8" }}>{notice}</div>}

      <div className="card">
        <strong>Add a document</strong>
        <div style={{ marginTop: 10 }}>
          <input
            placeholder="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            style={{ marginBottom: 8 }}
          />
          <textarea
            placeholder="Content"
            rows={5}
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
        </div>
        <div style={{ marginTop: 10 }}>
          <button disabled={busy} onClick={handleAdd}>
            Add document
          </button>
        </div>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Added</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {docs.map((doc) => (
              <tr key={doc.doc_id}>
                <td>{doc.title}</td>
                <td className="muted">{new Date(doc.added_at).toLocaleString()}</td>
                <td>
                  <button className="danger" onClick={() => handleRemove(doc.doc_id)}>
                    Remove
                  </button>
                </td>
              </tr>
            ))}
            {docs.length === 0 && (
              <tr>
                <td colSpan={3} className="muted">No documents yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
