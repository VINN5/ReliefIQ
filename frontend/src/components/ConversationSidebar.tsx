import { useEffect, useState } from "react";
import { Plus, MessageSquare, Loader2, Trash2 } from "lucide-react";
import { tokens, fonts } from "../lib/theme";
import { listConversations, ApiError, type ConversationSummary } from "../lib/api";

type ConversationSidebarProps = {
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  onDeleteConversation: (id: string) => void;
  refreshSignal: number;
};

type Group = { label: string; items: ConversationSummary[] };

function groupByRecency(conversations: ConversationSummary[]): Group[] {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  const sevenDaysAgo = new Date(startOfToday);
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

  const today: ConversationSummary[] = [];
  const yesterday: ConversationSummary[] = [];
  const previous7Days: ConversationSummary[] = [];
  const older: ConversationSummary[] = [];

  for (const c of conversations) {
    const updated = new Date(c.updated_at);
    if (updated >= startOfToday) today.push(c);
    else if (updated >= startOfYesterday) yesterday.push(c);
    else if (updated >= sevenDaysAgo) previous7Days.push(c);
    else older.push(c);
  }

  return [
    { label: "Today", items: today },
    { label: "Yesterday", items: yesterday },
    { label: "Previous 7 days", items: previous7Days },
    { label: "Older", items: older },
  ].filter((g) => g.items.length > 0);
}

export default function ConversationSidebar({
  activeConversationId,
  onSelectConversation,
  onNewChat,
  onDeleteConversation,
  refreshSignal,
}: ConversationSidebarProps) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listConversations()
      .then(setConversations)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load conversations."))
      .finally(() => setLoading(false));
  }, [refreshSignal]);

  const groups = groupByRecency(conversations);

  return (
    <div
      className="w-64 shrink-0 h-full flex flex-col"
      style={{ borderRight: `1px solid ${tokens.border}`, background: tokens.paper }}
    >
      <div className="p-3">
        <button
          type="button"
          onClick={onNewChat}
          className="cursor-pointer w-full inline-flex items-center justify-center gap-2 px-3 py-2.5 text-sm transition-colors duration-150"
          style={{ background: tokens.moss, color: "#fff", borderRadius: 8 }}
          onMouseEnter={(e) => (e.currentTarget.style.background = tokens.mossDeep)}
          onMouseLeave={(e) => (e.currentTarget.style.background = tokens.moss)}
        >
          <Plus size={16} /> New chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {loading && (
          <div className="flex items-center gap-2 text-sm px-2 py-2" style={{ color: tokens.muted }}>
            <Loader2 size={14} className="animate-spin" /> Loading…
          </div>
        )}

        {error && (
          <p className="text-xs px-2 py-2" style={{ color: "#8A2C2C" }}>
            {error}
          </p>
        )}

        {!loading && !error && conversations.length === 0 && (
          <p className="text-xs px-2 py-3 leading-relaxed" style={{ color: tokens.muted }}>
            No conversations yet — ask a question to start one.
          </p>
        )}

        {groups.map((group) => (
          <div key={group.label} className="mb-4">
            <p
              className="text-xs uppercase tracking-wider px-2 mb-1.5"
              style={{ fontFamily: fonts.mono, color: tokens.muted, letterSpacing: "0.08em" }}
            >
              {group.label}
            </p>
            {group.items.map((c) => {
              const isActive = c.id === activeConversationId;
              return (
                <div
                  key={c.id}
                  className="group relative flex items-center rounded-md transition-colors duration-150"
                  style={{
                    background: isActive ? tokens.amberSoft : "transparent",
                    borderRadius: 6,
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) e.currentTarget.style.background = tokens.surface;
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) e.currentTarget.style.background = "transparent";
                  }}
                >
                  <span
                    aria-hidden
                    className="absolute left-0 top-1.5 bottom-1.5 transition-opacity duration-150"
                    style={{
                      width: 3,
                      background: tokens.moss,
                      opacity: isActive ? 1 : 0,
                      borderRadius: 2,
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => onSelectConversation(c.id)}
                    className="cursor-pointer flex-1 min-w-0 text-left flex items-center gap-2 pl-2.5 pr-1 py-2 text-sm truncate"
                    style={{ color: isActive ? tokens.mossDeep : tokens.inkSoft }}
                  >
                    <MessageSquare size={14} className="shrink-0" style={{ opacity: isActive ? 1 : 0.6 }} />
                    <span className="truncate">{c.title}</span>
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteConversation(c.id);
                    }}
                    className="cursor-pointer shrink-0 p-1.5 mr-1 opacity-0 group-hover:opacity-100 transition-opacity duration-150"
                    style={{ color: tokens.muted }}
                    title="Delete conversation"
                    aria-label={`Delete conversation: ${c.title}`}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
