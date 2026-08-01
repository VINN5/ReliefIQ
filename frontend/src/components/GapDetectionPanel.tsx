import { useRef, useState, type FormEvent } from "react";
import { FileSearch, Upload, Loader2, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { tokens, fonts } from "../lib/theme";
import { analyzeGapDetection, ApiError, type GapAnalysisResponse, type CoverageStatus } from "../lib/api";

const STATUS_STYLES: Record<CoverageStatus, { bg: string; border: string; text: string; label: string; icon: typeof CheckCircle2 }> = {
  covered: { bg: tokens.amberSoft, border: tokens.moss, text: tokens.mossDeep, label: "Covered", icon: CheckCircle2 },
  partial: { bg: "#FFF7ED", border: "#F0C888", text: "#7A5A1E", label: "Partial", icon: AlertTriangle },
  gap: { bg: "#FBEAEA", border: "#E3B4B4", text: "#8A2C2C", label: "Gap", icon: XCircle },
};

function StatusPill({ status }: { status: CoverageStatus }) {
  const s = STATUS_STYLES[status];
  const Icon = s.icon;
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs px-2 py-1 shrink-0"
      style={{ fontFamily: fonts.mono, background: s.bg, color: s.text, border: `1px solid ${s.border}` }}
    >
      <Icon size={12} /> {s.label}
    </span>
  );
}

export default function GapDetectionPanel() {
  const [mode, setMode] = useState<"file" | "text">("file");
  const [pastedText, setPastedText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GapAnalysisResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    const file = fileInputRef.current?.files?.[0];
    if (mode === "file" && !file) {
      setError("Choose a PDF to analyze.");
      return;
    }
    if (mode === "text" && !pastedText.trim()) {
      setError("Paste in the donor requirements text to analyze.");
      return;
    }

    setLoading(true);
    setResult(null);
    try {
      const analysis = await analyzeGapDetection(
        mode === "file" ? { file } : { text: pastedText.trim() }
      );
      setResult(analysis);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Analysis failed. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <p className="text-sm mb-4" style={{ color: tokens.inkSoft }}>
        Upload a donor's policy document, or paste its requirements as text, to see which
        requirements your organisation's existing internal policies already cover — and
        which are gaps.
      </p>

      <div className="flex gap-2 mb-4" style={{ borderBottom: `1px solid ${tokens.border}` }}>
        <button
          type="button"
          onClick={() => setMode("file")}
          className="cursor-pointer px-3 py-2 text-sm"
          style={{
            color: mode === "file" ? tokens.mossDeep : tokens.muted,
            borderBottom: mode === "file" ? `2px solid ${tokens.moss}` : "2px solid transparent",
            marginBottom: "-1px",
          }}
        >
          Upload PDF
        </button>
        <button
          type="button"
          onClick={() => setMode("text")}
          className="cursor-pointer px-3 py-2 text-sm"
          style={{
            color: mode === "text" ? tokens.mossDeep : tokens.muted,
            borderBottom: mode === "text" ? `2px solid ${tokens.moss}` : "2px solid transparent",
            marginBottom: "-1px",
          }}
        >
          Paste text
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        {mode === "file" ? (
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            className="block text-sm"
            style={{ color: tokens.inkSoft }}
          />
        ) : (
          <textarea
            value={pastedText}
            onChange={(e) => setPastedText(e.target.value)}
            placeholder="Paste the donor policy's requirements here…"
            rows={6}
            className="w-full px-3 py-2.5 text-sm outline-none"
            style={{ background: tokens.surface, border: `1px solid ${tokens.border}`, color: tokens.ink }}
          />
        )}

        <button
          type="submit"
          disabled={loading}
          className="mt-4 cursor-pointer inline-flex items-center gap-2 px-5 py-2.5 text-sm disabled:opacity-60 disabled:cursor-not-allowed"
          style={{ background: tokens.moss, color: "#fff" }}
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <FileSearch size={16} />}
          {loading ? "Analyzing…" : "Analyze for gaps"}
        </button>
      </form>

      {error && (
        <div
          className="mt-4 text-sm px-3 py-2.5"
          style={{ background: "#FBEAEA", border: "1px solid #E3B4B4", color: "#8A2C2C" }}
          role="alert"
        >
          {error}
        </div>
      )}

      {result && !error && (
        <div className="mt-6">
          <div className="p-4 mb-4" style={{ background: tokens.surface, border: `1px solid ${tokens.border}` }}>
            <p className="text-sm" style={{ color: tokens.ink }}>{result.summary}</p>
          </div>

          <div className="divide-y" style={{ borderColor: tokens.border }}>
            {result.items.map((item, i) => (
              <div key={i} className="py-4 flex gap-4 items-start">
                <StatusPill status={item.status} />
                <div className="min-w-0">
                  <p className="text-sm" style={{ color: tokens.ink }}>{item.requirement}</p>
                  <p className="text-xs mt-1" style={{ color: tokens.muted }}>{item.explanation}</p>
                  {item.matched_documents.length > 0 && (
                    <p className="text-xs mt-1" style={{ fontFamily: fonts.mono, color: tokens.muted }}>
                      Matched: {item.matched_documents.join(", ")}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
