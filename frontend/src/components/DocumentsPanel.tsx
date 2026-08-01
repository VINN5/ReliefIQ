import { useEffect, useRef, useState } from "react";
import { Upload, Loader2, CheckCircle2, XCircle, Lock, RefreshCw, History } from "lucide-react";
import { tokens, fonts } from "../lib/theme";
import { uploadDocument, replaceDocument, listDocuments, ApiError, type DocumentResponse, type DocumentStatus } from "../lib/api";

const IN_PROGRESS: DocumentStatus[] = [
  "uploading",
  "extracting",
  "requires_ocr",
  "extracted",
  "chunking",
  "chunked",
  "embedding",
  "indexing",
];

const STATUS_LABEL: Record<DocumentStatus, string> = {
  uploading: "Uploading",
  extracting: "Extracting text",
  requires_ocr: "Needs OCR",
  extracted: "Extracted",
  chunking: "Chunking",
  chunked: "Chunked",
  embedding: "Embedding",
  indexing: "Indexing",
  ready: "Ready",
  failed: "Failed",
};

function StatusBadge({ status }: { status: DocumentStatus }) {
  if (status === "ready") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs px-2 py-1" style={{ fontFamily: fonts.mono, background: tokens.amberSoft, color: tokens.mossDeep, border: `1px solid ${tokens.moss}` }}>
        <CheckCircle2 size={12} /> {STATUS_LABEL[status]}
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs px-2 py-1" style={{ fontFamily: fonts.mono, background: "#FBEAEA", color: "#8A2C2C", border: "1px solid #E3B4B4" }}>
        <XCircle size={12} /> {STATUS_LABEL[status]}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs px-2 py-1" style={{ fontFamily: fonts.mono, background: tokens.paper, color: tokens.muted, border: `1px solid ${tokens.border}` }}>
      <Loader2 size={12} className="animate-spin" /> {STATUS_LABEL[status]}
    </span>
  );
}

function VersionBadge({ version }: { version: number }) {
  return (
    <span
      className="inline-flex items-center text-xs px-1.5 py-0.5"
      style={{ fontFamily: fonts.mono, background: tokens.paper, color: tokens.muted, border: `1px solid ${tokens.border}` }}
    >
      v{version}
    </span>
  );
}

function RestrictedBadge() {
  return (
    <span
      className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5"
      style={{ fontFamily: fonts.mono, background: "#FFF7ED", color: "#7A5A1E", border: "1px solid #F0C888" }}
      title="Excluded from field staff search results and citations"
    >
      <Lock size={10} /> Restricted
    </span>
  );
}

function SupersededBadge() {
  return (
    <span
      className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5"
      style={{ fontFamily: fonts.mono, background: tokens.paper, color: tokens.muted, border: `1px solid ${tokens.border}` }}
      title="Replaced by a newer version — kept for history, no longer used in answers"
    >
      <History size={10} /> Superseded
    </span>
  );
}

type DocumentsPanelProps = {
  // Whether the current user's role permits uploading. Purely a UI
  // convenience — real enforcement lives on the backend's
  // require_role(MANAGER, ADMIN) for POST /documents/upload. Hiding
  // this button doesn't grant/deny anything by itself.
  canUpload: boolean;
};

export default function DocumentsPanel({ canUpload }: DocumentsPanelProps) {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Whether the NEXT upload should be marked restricted. Reset after
  // each upload rather than persisted, so restricting one document
  // doesn't silently carry over and restrict the next unrelated one.
  const [restrictNext, setRestrictNext] = useState(false);
  // Which document is currently being replaced (drives the hidden
  // per-row file input) — null when no replace is in flight.
  const [replacingId, setReplacingId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const replaceInputRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    try {
      const docs = await listDocuments();
      setDocuments(docs);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reach the server.");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  // Poll every 3s only while something is still processing — no point
  // hammering the API once everything has settled into ready/failed.
  useEffect(() => {
    const hasInProgress = documents.some((d) => IN_PROGRESS.includes(d.status));
    if (!hasInProgress) return;
    const interval = setInterval(refresh, 3000);
    return () => clearInterval(interval);
  }, [documents]);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const doc = await uploadDocument(file, restrictNext);
      setDocuments((prev) => [doc, ...prev]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed. Is the backend running?");
    } finally {
      setUploading(false);
      setRestrictNext(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function startReplace(documentId: string) {
    setReplacingId(documentId);
    // Defer the click so the hidden input has re-rendered with the
    // right id association before we try to open the file picker.
    setTimeout(() => replaceInputRef.current?.click(), 0);
  }

  async function handleReplaceFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    const documentId = replacingId;
    if (!file || !documentId) {
      setReplacingId(null);
      return;
    }
    setError(null);
    try {
      const newDoc = await replaceDocument(documentId, file);
      // Mark the old row superseded locally (rather than waiting on a
      // full refetch) so the UI updates immediately, then prepend the
      // new version.
      setDocuments((prev) => [
        newDoc,
        ...prev.map((d) => (d.id === documentId ? { ...d, is_superseded: true } : d)),
      ]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Replace failed. Is the backend running?");
    } finally {
      setReplacingId(null);
      if (replaceInputRef.current) replaceInputRef.current.value = "";
    }
  }

  return (
    <div>
      {canUpload && (
        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.doc,.txt"
            onChange={handleFileChange}
            className="hidden"
            id="document-upload-input"
          />
          <label
            htmlFor="document-upload-input"
            className="cursor-pointer inline-flex items-center gap-2 px-5 py-2.5 text-sm"
            style={{ background: tokens.moss, color: "#fff" }}
          >
            {uploading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            {uploading ? "Uploading…" : "Upload document"}
          </label>

          {/* Hidden, reused for every "Replace" click — replacingId
              tracks which document the next selected file applies to. */}
          <input
            ref={replaceInputRef}
            type="file"
            accept=".pdf,.docx,.doc,.txt"
            onChange={handleReplaceFileChange}
            className="hidden"
          />

          <label
            className="mt-3 flex items-center gap-2 text-sm cursor-pointer w-fit"
            style={{ color: tokens.inkSoft }}
          >
            <input
              type="checkbox"
              checked={restrictNext}
              onChange={(e) => setRestrictNext(e.target.checked)}
              disabled={uploading}
              className="cursor-pointer"
            />
            <Lock size={14} style={{ color: tokens.muted }} />
            Restrict this document to managers/admins
          </label>
          <p className="text-xs mt-1" style={{ color: tokens.muted }}>
            Restricted documents are excluded from field staff search results and citations entirely.
          </p>
        </div>
      )}

      {error && (
        <div
          className="mt-4 text-sm px-3 py-2.5"
          style={{ background: "#FBEAEA", border: "1px solid #E3B4B4", color: "#8A2C2C" }}
          role="alert"
        >
          {error}
        </div>
      )}

      <div className="mt-6">
        {documents.length === 0 ? (
          <p className="text-sm" style={{ color: tokens.muted }}>
            No documents uploaded yet.
          </p>
        ) : (
          <div className="divide-y" style={{ borderColor: tokens.border }}>
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between gap-4 py-3"
                style={{ borderColor: tokens.border, opacity: doc.is_superseded ? 0.6 : 1 }}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm truncate" style={{ color: tokens.ink }}>
                      {doc.title}
                    </p>
                    <VersionBadge version={doc.version} />
                    {doc.access_level === "restricted" && <RestrictedBadge />}
                    {doc.is_superseded && <SupersededBadge />}
                  </div>
                  <p className="text-xs mt-0.5" style={{ color: tokens.muted, fontFamily: fonts.mono }}>
                    {new Date(doc.created_at).toLocaleString()}
                  </p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <StatusBadge status={doc.status} />
                  {canUpload && !doc.is_superseded && (
                    <button
                      type="button"
                      onClick={() => startReplace(doc.id)}
                      disabled={replacingId === doc.id}
                      className="cursor-pointer inline-flex items-center gap-1 text-xs px-2 py-1 disabled:opacity-50 disabled:cursor-not-allowed"
                      style={{ border: `1px solid ${tokens.border}`, color: tokens.inkSoft }}
                      title="Upload a newer version of this document"
                    >
                      {replacingId === doc.id ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <RefreshCw size={12} />
                      )}
                      Replace
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
