import { motion, AnimatePresence } from "framer-motion";

function groupByDate(conversations) {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  const startOf7DaysAgo = new Date(startOfToday);
  startOf7DaysAgo.setDate(startOf7DaysAgo.getDate() - 7);

  const groups = { Today: [], Yesterday: [], "Past 7 Days": [], Older: [] };
  for (const conv of conversations) {
    const d = new Date(conv.updated_at);
    const day = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    if (day >= startOfToday)          groups.Today.push(conv);
    else if (day >= startOfYesterday) groups.Yesterday.push(conv);
    else if (d >= startOf7DaysAgo)    groups["Past 7 Days"].push(conv);
    else                              groups.Older.push(conv);
  }
  return groups;
}

function IconPencil() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
    </svg>
  );
}

function IconChevronLeft() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="15 18 9 12 15 6"/>
    </svg>
  );
}

function IconChevronRight() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="9 18 15 12 9 6"/>
    </svg>
  );
}

function IconTrash() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="3 6 5 6 21 6"/>
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
      <path d="M10 11v6M14 11v6"/>
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
    </svg>
  );
}

export function ConversationSidebar({
  conversations = [],
  activeConvId,
  onNewChat,
  onSelectConversation,
  onDeleteConversation,
  accentColor = "#b2945b",
  isCollapsed,
  onToggle,
}) {
  const groups = groupByDate(conversations);
  const hasConversations = conversations.length > 0;

  return (
    <aside
      className={`conv-sidebar${isCollapsed ? " conv-sidebar--collapsed" : ""}`}
      aria-label="Conversation history"
    >
      <div className="conv-sidebar-header">
        {!isCollapsed && (
          <button
            type="button"
            className="btn-new-chat"
            onClick={onNewChat}
            style={{ "--accent": accentColor }}
            aria-label="Start new conversation"
          >
            <IconPencil />
            <span>New chat</span>
          </button>
        )}
        <button
          type="button"
          className="btn-sidebar-toggle"
          onClick={onToggle}
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {isCollapsed ? <IconChevronRight /> : <IconChevronLeft />}
        </button>
      </div>

      {!isCollapsed && (
        <div className="conv-list" role="list">
          {!hasConversations && (
            <p className="conv-empty-hint">No conversations yet. Start chatting!</p>
          )}
          {Object.entries(groups).map(([group, convs]) =>
            convs.length === 0 ? null : (
              <div key={group} className="conv-group">
                <div className="conv-group-label">{group}</div>
                <AnimatePresence initial={false}>
                  {convs.map((conv) => (
                    <motion.div
                      key={conv.id}
                      role="listitem"
                      className={`conv-item${conv.id === activeConvId ? " conv-item--active" : ""}`}
                      style={conv.id === activeConvId ? { "--accent": accentColor } : {}}
                      onClick={() => onSelectConversation(conv)}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -8 }}
                      transition={{ duration: 0.15 }}
                      tabIndex={0}
                      onKeyDown={(e) => e.key === "Enter" && onSelectConversation(conv)}
                      aria-current={conv.id === activeConvId ? "true" : undefined}
                    >
                      <span className="conv-item-title">{conv.title || "New conversation"}</span>
                      <button
                        type="button"
                        className="conv-item-delete"
                        onClick={(e) => { e.stopPropagation(); onDeleteConversation(conv.id); }}
                        aria-label="Delete conversation"
                        tabIndex={-1}
                      >
                        <IconTrash />
                      </button>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )
          )}
        </div>
      )}

      {isCollapsed && (
        <button
          type="button"
          className="btn-new-chat btn-new-chat--icon-only"
          onClick={onNewChat}
          aria-label="Start new conversation"
          style={{ "--accent": accentColor }}
        >
          <IconPencil />
        </button>
      )}
    </aside>
  );
}
