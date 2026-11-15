"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Bot,
  CheckCircle2,
  ChevronRight,
  Clock,
  Flame,
  MessageSquare,
  RefreshCw,
  Send,
  Sparkles,
  User,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import { triggerHaptic } from "@/lib/telegram";
import type { ChatMessage, Dialog, DialogStatus } from "@/lib/types";
import { Spinner } from "./ui";

const STATUS_BADGES: Record<
  DialogStatus,
  { label: string; bg: string; text: string; border: string }
> = {
  new: {
    label: "Новый",
    bg: "bg-[#242731]",
    text: "text-[#9CA3AF]",
    border: "border-white/[0.08]",
  },
  ai_handling: {
    label: "AI-дожим",
    bg: "bg-[rgba(139,92,246,0.14)]",
    text: "text-[#C4B5FD]",
    border: "border-[rgba(139,92,246,0.3)]",
  },
  manual: {
    label: "Вручную",
    bg: "bg-[#242731]",
    text: "text-[#9CA3AF]",
    border: "border-white/[0.06]",
  },
  deal: {
    label: "Сделка 🔥",
    bg: "bg-[rgba(16,185,129,0.12)]",
    text: "text-[#10B981]",
    border: "border-emerald-500/25",
  },
};

function Switch({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => {
        triggerHaptic("medium");
        onChange(!checked);
      }}
      className={`relative h-4 w-7 shrink-0 rounded-full border transition ${
        checked
          ? "border-brand-500/60 bg-brand-500 shadow-[0_0_8px_rgba(139,92,246,0.35)]"
          : "border-white/10 bg-[#242731]"
      }`}
    >
      <span
        className={`absolute top-0.5 rounded-full bg-white shadow transition-all ${
          checked ? "left-[14px]" : "left-0.5"
        }`}
        style={{ height: 10, width: 10 }}
      />
    </button>
  );
}

export default function InboxView({
  showToast,
}: {
  showToast: (msg: string, variant?: "info" | "success" | "error") => void;
}) {
  const [dialogs, setDialogs] = useState<Dialog[]>([]);
  const [activeDialog, setActiveDialog] = useState<Dialog | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [inputText, setInputText] = useState("");
  const [sending, setSending] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [aiGenerating, setAiGenerating] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const loadDialogs = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await api.listDialogs();
      setDialogs(data);
      if (data.length > 0 && !activeDialog) {
        // Select first dialog by default on desktop
        if (typeof window !== "undefined" && window.innerWidth >= 768) {
          setActiveDialog(data[0]);
        }
      }
    } catch (e) {
      if (!silent) showToast(e instanceof Error ? e.message : "Ошибка загрузки диалогов", "error");
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const loadMessages = async (dialogId: string) => {
    setMessagesLoading(true);
    try {
      const msgs = await api.getDialogMessages(dialogId);
      setMessages(msgs);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка загрузки сообщений", "error");
    } finally {
      setMessagesLoading(false);
    }
  };

  const handleToggleAiAutoReply = async (val: boolean) => {
    if (!activeDialog) return;
    try {
      await api.updateDialog(activeDialog.id, { ai_auto_reply_enabled: val });
      setActiveDialog((prev) => (prev ? { ...prev, ai_auto_reply_enabled: val } : prev));
      setDialogs((prev) =>
        prev.map((d) => (d.id === activeDialog.id ? { ...d, ai_auto_reply_enabled: val } : d))
      );
      showToast(
        val
          ? "AI-автоответчик включен для этого диалога"
          : "AI-автоответчик отключен (ручной ответ)",
        "info"
      );
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка обновления", "error");
    }
  };

  const handleSyncHistory = async () => {
    if (!activeDialog || syncing) return;
    setSyncing(true);
    triggerHaptic("light");
    try {
      const res = await api.syncDialog(activeDialog.id);
      showToast(`Синхронизировано сообщений: ${res.synced_count}`, "success");
      void loadMessages(activeDialog.id);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка синхронизации", "error");
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    void loadDialogs();
    // Real-time polling every 6 seconds
    const interval = setInterval(() => {
      void loadDialogs(true);
      if (activeDialog) {
        api.getDialogMessages(activeDialog.id).then(setMessages).catch(() => {});
      }
    }, 6000);
    return () => clearInterval(interval);
  }, [activeDialog?.id]);

  useEffect(() => {
    if (activeDialog) {
      void loadMessages(activeDialog.id);
    } else {
      setMessages([]);
    }
  }, [activeDialog?.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSendMessage = async () => {
    if (!activeDialog || !inputText.trim() || sending) return;
    setSending(true);
    triggerHaptic("medium");
    try {
      const msg = await api.sendMessage(activeDialog.id, inputText.trim());
      setMessages((prev) => [...prev, msg]);
      setInputText("");
      // Update last message in dialogs list
      setDialogs((prev) =>
        prev.map((d) =>
          d.id === activeDialog.id
            ? { ...d, last_message_preview: msg.text, last_message_at: msg.created_at }
            : d
        )
      );
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Не удалось отправить сообщение", "error");
    } finally {
      setSending(false);
    }
  };

  const handleAiAutoReply = async () => {
    if (!activeDialog || aiGenerating) return;
    setAiGenerating(true);
    triggerHaptic("medium");
    try {
      const res = await api.triggerAiReply(activeDialog.id);
      showToast(
        res.is_deal
          ? "🔥 Клиент готов к сделке! Статус изменён, пуш отправлен в бота."
          : "AI-ответ сгенерирован и отправлен!",
        "success"
      );
      void loadMessages(activeDialog.id);
      void loadDialogs(true);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка AI генерации", "error");
    } finally {
      setAiGenerating(false);
    }
  };

  const handleStatusChange = async (newStatus: DialogStatus) => {
    if (!activeDialog) return;
    try {
      await api.updateDialogStatus(activeDialog.id, newStatus);
      setActiveDialog((prev) => (prev ? { ...prev, status: newStatus } : prev));
      setDialogs((prev) =>
        prev.map((d) => (d.id === activeDialog.id ? { ...d, status: newStatus } : d))
      );
      showToast(`Статус диалога: ${STATUS_BADGES[newStatus].label}`, "success");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка", "error");
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-[#F3F4F6] tracking-tight">Единый Inbox</h1>
          <span className="font-mono text-xs text-[#9CA3AF] tabular-nums tracking-tight rounded-md bg-[#242731] border border-white/[0.06] px-2 py-0.5">
            {dialogs.length} диалогов
          </span>
        </div>

        <button
          onClick={() => loadDialogs()}
          className="btn-ghost !px-3 !py-1.5 text-xs text-[#9CA3AF] hover:text-[#F3F4F6]"
        >
          <RefreshCw size={13} />
          Обновить
        </button>
      </div>

      {/* Main Split Layout: Dialogs List + Chat View */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3.5 h-[calc(100vh-210px)] min-h-[500px]">
        {/* Left Side: Dialogs List */}
        <div
          className={`card flex flex-col overflow-hidden md:col-span-5 lg:col-span-4 ${
            activeDialog ? "hidden md:flex" : "flex"
          }`}
        >
          <div className="p-3 border-b border-white/[0.07] flex items-center justify-between bg-[#1A1C23]">
            <span className="text-xs font-medium text-[#9CA3AF]">
              Диалоги (<span className="font-mono tabular-nums tracking-tight">{dialogs.length}</span>)
            </span>
            <span className="text-[11px] text-[#6B7280] font-mono tabular-nums tracking-tight">auto 6s</span>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-white/[0.04]">
            {loading ? (
              <div className="p-4 text-center text-xs text-[#6B7280]">Загрузка диалогов...</div>
            ) : dialogs.length === 0 ? (
              <div className="p-8 text-center text-xs text-[#6B7280] space-y-2">
                <MessageSquare size={22} className="mx-auto text-[#6B7280]" />
                <p>Пока нет входящих диалогов.</p>
                <p className="text-[11px] text-[#6B7280]">
                  Запустите касание по лидам или дождитесь откликов.
                </p>
              </div>
            ) : (
              dialogs.map((d) => {
                const isActive = activeDialog?.id === d.id;
                const statusMeta = STATUS_BADGES[d.status] || STATUS_BADGES.new;

                return (
                  <button
                    key={d.id}
                    onClick={() => {
                      triggerHaptic("light");
                      setActiveDialog(d);
                    }}
                    className={`w-full text-left p-3 transition flex items-start gap-2.5 hover:bg-[#242731]/50 ${
                      isActive ? "bg-[#242731] border-l-2 border-[#8B5CF6]" : ""
                    }`}
                  >
                    {/* Avatar */}
                    <div className="relative h-9 w-9 shrink-0 rounded-full bg-[#242731] border border-white/[0.08] flex items-center justify-center text-[#C4B5FD] font-semibold text-xs">
                      {d.peer_name ? d.peer_name.slice(0, 2).toUpperCase() : "TG"}
                      {d.unread_count > 0 && (
                        <span className="absolute -top-1 -right-1 flex h-4 min-w-[16px] px-1 items-center justify-center rounded-full bg-[#8B5CF6] text-[9px] font-mono font-bold text-white tabular-nums tracking-tight">
                          {d.unread_count}
                        </span>
                      )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <p className="text-xs font-semibold text-[#F3F4F6] truncate">
                          {d.peer_name || d.peer_username || `ID ${d.peer_id}`}
                        </p>
                        <span className="text-[10px] text-[#6B7280] font-mono tabular-nums tracking-tight shrink-0">
                          {d.last_message_at
                            ? new Date(d.last_message_at).toLocaleTimeString([], {
                                hour: "2-digit",
                                minute: "2-digit",
                              })
                            : ""}
                        </span>
                      </div>

                      <p className="mt-0.5 text-xs text-[#9CA3AF] line-clamp-1">
                        {d.last_message_preview || "Нет сообщений"}
                      </p>

                      <div className="mt-1.5 flex items-center justify-between">
                        <span
                          className={`rounded-md px-1.5 py-0.5 text-[10px] font-medium border ${statusMeta.bg} ${statusMeta.text} ${statusMeta.border}`}
                        >
                          {statusMeta.label}
                        </span>
                        {d.account_id && (
                          <span className="text-[10px] text-[#6B7280] font-mono tabular-nums">
                            TG
                          </span>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right Side: Active Chat View */}
        <div
          className={`card flex flex-col overflow-hidden md:col-span-7 lg:col-span-8 ${
            !activeDialog ? "hidden md:flex" : "flex"
          }`}
        >
          {activeDialog ? (
            <>
              {/* Chat Header */}
              <div className="p-3 border-b border-white/[0.07] flex items-center justify-between bg-[#1A1C23]">
                <div className="flex items-center gap-2.5 min-w-0">
                  <button
                    onClick={() => setActiveDialog(null)}
                    className="icon-btn !h-7 !w-7 md:hidden shrink-0"
                    title="Назад к списку"
                  >
                    <ArrowLeft size={14} />
                  </button>

                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h2 className="text-sm font-semibold text-[#F3F4F6] truncate">
                        {activeDialog.peer_name || activeDialog.peer_username || activeDialog.peer_id}
                      </h2>
                      {activeDialog.peer_username && (
                        <span className="text-xs text-[#8B5CF6] font-medium hidden sm:inline">
                          @{activeDialog.peer_username}
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] text-[#6B7280] truncate font-mono tabular-nums">
                      {activeDialog.account_phone ? `От лица: ${activeDialog.account_phone}` : "Telegram пул"} · {activeDialog.status}
                    </p>
                  </div>
                </div>

                {/* Status Switcher & AI Button & AI Auto-Reply Switch */}
                <div className="flex items-center gap-2">
                  {/* AI Auto-Reply Toggle Switch */}
                  <label className="flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-[#242731] px-2 py-1 cursor-pointer">
                    <Switch
                      checked={activeDialog.ai_auto_reply_enabled ?? true}
                      onChange={handleToggleAiAutoReply}
                    />
                    <span className="text-[11px] font-medium text-[#F3F4F6] hidden sm:inline">
                      AI-автоответчик
                    </span>
                  </label>

                  {/* Sync messages button */}
                  <button
                    onClick={handleSyncHistory}
                    disabled={syncing}
                    className="btn-ghost !h-7.5 !w-7.5 !p-0 text-xs text-[#9CA3AF] hover:text-[#F3F4F6]"
                    title="Синхронизировать историю с Telegram"
                  >
                    <RefreshCw size={13} className={syncing ? "animate-spin" : ""} />
                  </button>

                  <button
                    onClick={handleAiAutoReply}
                    disabled={aiGenerating}
                    className="btn-primary !px-2.5 !py-1 text-xs"
                    title="Сгенерировать AI-ответ от лица менеджера"
                  >
                    {aiGenerating ? <Spinner size={13} /> : <Sparkles size={13} />}
                    <span className="hidden sm:inline">AI-дожим</span>
                  </button>

                  <select
                    value={activeDialog.status}
                    onChange={(e) => handleStatusChange(e.target.value as DialogStatus)}
                    className="h-7.5 rounded-lg border border-white/[0.08] bg-[#242731] px-2 text-xs font-medium text-[#F3F4F6] outline-none"
                  >
                    <option value="new">Новый</option>
                    <option value="ai_handling">AI-дожим</option>
                    <option value="manual">Вручную</option>
                    <option value="deal">Сделка 🔥</option>
                  </select>
                </div>
              </div>

              {/* Chat Messages Body */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-[#111216]">
                {messagesLoading && messages.length === 0 ? (
                  <div className="flex h-full items-center justify-center">
                    <Spinner size={24} />
                  </div>
                ) : messages.length === 0 ? (
                  <div className="flex h-full flex-col items-center justify-center text-center p-6 text-[#6B7280] space-y-2">
                    <MessageSquare size={28} className="text-[#6B7280]" />
                    <p className="text-xs">В этом диалоге ещё нет сообщений.</p>
                    <button
                      onClick={handleSyncHistory}
                      disabled={syncing}
                      className="btn-ghost !px-3 !py-1 text-xs text-[#9CA3AF]"
                    >
                      <RefreshCw size={12} className={syncing ? "animate-spin" : ""} />
                      Загрузить историю из Telegram
                    </button>
                  </div>
                ) : (
                  messages.map((m) => {
                    const isOut = m.direction === "out";

                    return (
                      <div
                        key={m.id}
                        className={`flex flex-col ${isOut ? "items-end" : "items-start"}`}
                      >
                        <div
                          className={`max-w-[85%] rounded-xl px-3.5 py-2 text-xs leading-relaxed ${
                            isOut
                              ? "bg-[rgba(139,92,246,0.16)] border border-[#8B5CF6]/30 text-[#F3F4F6] rounded-br-none"
                              : "bg-[#242731] border border-white/[0.06] text-[#F3F4F6] rounded-bl-none"
                          }`}
                        >
                          {m.text}

                          <div
                            className={`mt-1 flex items-center gap-1.5 text-[9px] font-mono tabular-nums ${
                              isOut ? "text-[#C4B5FD] justify-end" : "text-[#6B7280]"
                            }`}
                          >
                            {m.is_ai_generated && (
                              <span className="inline-flex items-center gap-0.5 rounded bg-[rgba(139,92,246,0.25)] px-1 py-0.2 font-sans font-semibold text-[8px] text-[#C4B5FD]">
                                <Sparkles size={8} /> AI
                              </span>
                            )}
                            <span>
                              {new Date(m.created_at).toLocaleTimeString([], {
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Chat Input Footer */}
              <div className="p-3 border-t border-white/[0.07] bg-[#1A1C23] flex flex-col gap-1.5">
                <div className="flex items-center justify-between text-[10px] text-[#6B7280]">
                  <span>
                    Отправка от лица:{" "}
                    <span className="font-mono text-[#C4B5FD] font-semibold">
                      {activeDialog.account_phone || "Telegram аккаунт"}
                    </span>
                  </span>
                  <span className="sm:hidden flex items-center gap-1">
                    <Switch
                      checked={activeDialog.ai_auto_reply_enabled ?? true}
                      onChange={handleToggleAiAutoReply}
                    />
                    <span>AI-ответ</span>
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    placeholder={`Напишите ответ от лица ${activeDialog.account_phone || "аккаунта"}...`}
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        void handleSendMessage();
                      }
                    }}
                    className="input !h-9 text-xs flex-1"
                  />

                  <button
                    onClick={handleSendMessage}
                    disabled={sending || !inputText.trim()}
                    className="btn-primary !h-9 !w-9 !p-0 shrink-0"
                    title="Отправить сообщение"
                  >
                    {sending ? <Spinner size={14} /> : <Send size={14} />}
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex h-full flex-col items-center justify-center p-8 text-center text-[#6B7280] space-y-2.5">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#242731] text-[#8B5CF6] border border-white/[0.08]">
                <MessageSquare size={22} />
              </div>
              <h3 className="text-sm font-semibold text-[#F3F4F6]">Выберите диалог</h3>
              <p className="max-w-xs text-xs text-[#9CA3AF]">
                Выберите диалог из списка слева, чтобы просмотреть переписку и включить AI-дожим.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
