import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { MapPinned, LogOut, FileStack, MessageSquare, FileSearch, ShieldAlert, AlertTriangle } from "lucide-react";
import { tokens, fonts, fontImport } from "../lib/theme";
import { getCurrentUser, clearToken, type UserRole } from "../lib/api";
import ChatPanel from "../components/ChatPanel";
import DocumentsPanel from "../components/DocumentsPanel";
import GapDetectionPanel from "../components/GapDetectionPanel";
import ConflictDetectionPanel from "../components/ConflictDetectionPanel";
import AuditLogPanel from "../components/AuditLogPanel";

type Me = { id: string; full_name: string; organisation: string; email: string; role: UserRole };
type Tab = "chat" | "documents" | "gaps" | "conflicts" | "audit";

// Roles allowed to see/manage the document library — kept in one place
// so the frontend gate stays in sync with the backend's
// require_role(MANAGER, ADMIN) on both GET and POST /documents.
// field_staff still queries the knowledge base via /query/answer; they
// just never see the raw document list or upload control. This is a
// UX convenience only — hiding the tab doesn't grant/deny access by
// itself, the backend is still the real enforcement point.
const DOCUMENT_MANAGER_ROLES: UserRole[] = ["manager", "admin"];

export default function Dashboard() {
  const navigate = useNavigate();
  const [me, setMe] = useState<Me | null>(null);
  const [tab, setTab] = useState<Tab>("chat");

  useEffect(() => {
    getCurrentUser()
      .then(setMe)
      .catch(() => navigate("/signin"));
  }, [navigate]);

  function handleLogout() {
    clearToken();
    navigate("/");
  }

  const canManageDocuments = me ? DOCUMENT_MANAGER_ROLES.includes(me.role) : false;
  const isAdmin = me?.role === "admin";

  // If a non-admin somehow lands on "audit", or a field_staff account
  // lands on a manager-only tab (stale state, direct navigation, role
  // changed mid-session), bounce back to "chat" rather than rendering
  // a tab they shouldn't see.
  useEffect(() => {
    if (tab === "audit" && me && !isAdmin) {
      setTab("chat");
    } else if ((tab === "documents" || tab === "gaps" || tab === "conflicts") && me && !canManageDocuments) {
      setTab("chat");
    }
  }, [tab, me, canManageDocuments, isAdmin]);

  return (
    <div style={{ background: tokens.paper, fontFamily: fonts.body }} className="min-h-screen w-full">
      <style>{`${fontImport}`}</style>

      <header className="w-full" style={{ borderBottom: `1px solid ${tokens.border}` }}>
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 cursor-pointer">
            <MapPinned size={20} strokeWidth={1.75} style={{ color: tokens.mossDeep }} />
            <span style={{ fontFamily: fonts.display, fontWeight: 600, color: tokens.ink }} className="text-lg">
              ReliefIQ
            </span>
          </Link>
          <button
            type="button"
            onClick={handleLogout}
            className="cursor-pointer inline-flex items-center gap-2 text-sm px-3 py-2 hover:opacity-70"
            style={{ color: tokens.inkSoft }}
          >
            <LogOut size={16} /> Log out
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-12">
        {me && (
          <>
            <p
              className="text-xs uppercase tracking-wider mb-2"
              style={{ fontFamily: fonts.mono, color: tokens.moss, letterSpacing: "0.1em" }}
            >
              {me.organisation}
            </p>
            <h1 className="text-3xl mb-8" style={{ fontFamily: fonts.display, fontWeight: 600, color: tokens.ink }}>
              Welcome, {me.full_name.split(" ")[0]}.
            </h1>
          </>
        )}

        <div className="flex gap-2 mb-6" style={{ borderBottom: `1px solid ${tokens.border}` }}>
          <button
            type="button"
            onClick={() => setTab("chat")}
            className="cursor-pointer inline-flex items-center gap-2 px-4 py-3 text-sm"
            style={{
              color: tab === "chat" ? tokens.mossDeep : tokens.muted,
              borderBottom: tab === "chat" ? `2px solid ${tokens.moss}` : "2px solid transparent",
              marginBottom: "-1px",
            }}
          >
            <MessageSquare size={16} /> Chat
          </button>
          {canManageDocuments && (
            <button
              type="button"
              onClick={() => setTab("documents")}
              className="cursor-pointer inline-flex items-center gap-2 px-4 py-3 text-sm"
              style={{
                color: tab === "documents" ? tokens.mossDeep : tokens.muted,
                borderBottom: tab === "documents" ? `2px solid ${tokens.moss}` : "2px solid transparent",
                marginBottom: "-1px",
              }}
            >
              <FileStack size={16} /> Documents
            </button>
          )}
          {canManageDocuments && (
            <button
              type="button"
              onClick={() => setTab("gaps")}
              className="cursor-pointer inline-flex items-center gap-2 px-4 py-3 text-sm"
              style={{
                color: tab === "gaps" ? tokens.mossDeep : tokens.muted,
                borderBottom: tab === "gaps" ? `2px solid ${tokens.moss}` : "2px solid transparent",
                marginBottom: "-1px",
              }}
            >
              <FileSearch size={16} /> Gap Detection
            </button>
          )}
          {canManageDocuments && (
            <button
              type="button"
              onClick={() => setTab("conflicts")}
              className="cursor-pointer inline-flex items-center gap-2 px-4 py-3 text-sm"
              style={{
                color: tab === "conflicts" ? tokens.mossDeep : tokens.muted,
                borderBottom: tab === "conflicts" ? `2px solid ${tokens.moss}` : "2px solid transparent",
                marginBottom: "-1px",
              }}
            >
              <AlertTriangle size={16} /> Conflict Detection
            </button>
          )}
          {isAdmin && (
            <button
              type="button"
              onClick={() => setTab("audit")}
              className="cursor-pointer inline-flex items-center gap-2 px-4 py-3 text-sm"
              style={{
                color: tab === "audit" ? tokens.mossDeep : tokens.muted,
                borderBottom: tab === "audit" ? `2px solid ${tokens.moss}` : "2px solid transparent",
                marginBottom: "-1px",
              }}
            >
              <ShieldAlert size={16} /> Audit Log
            </button>
          )}
        </div>

        {tab === "chat" && <ChatPanel />}
        {tab === "documents" && <DocumentsPanel canUpload={canManageDocuments} />}
        {tab === "gaps" && <GapDetectionPanel />}
        {tab === "conflicts" && <ConflictDetectionPanel />}
        {tab === "audit" && <AuditLogPanel />}
      </main>
    </div>
  );
}
