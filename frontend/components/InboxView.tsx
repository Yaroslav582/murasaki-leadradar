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
    bg: "bg-sky-500/10",
    text: "text-sky-300",
    border: "border-sky-500/20",
  },
  ai_handling: {
    label: "AI-дожим",
    bg: "bg-brand-500/15",
    text: "text-brand-300",
    border: "border-brand-500/30",
  },
  manual: {
    label: "Вручную",
    bg: "bg-slate-500/15",
    text: "text-slate-300",
    border: "border-slate-500/20",
  },
  deal: {
    label: "Сделка 🔥",
    bg: "bg-emerald-500/15",
    text: "text-emerald-300",
    border: "border-emerald-500/30",
  },
};

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
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-300">
              Сквозная коммуникация
            </span>
            <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-300 border border-emerald-500/20">
              Live Feed
            </span>
          </div>
          <h1 className="mt-0.5 text-2xl font-black tracking-tight text-white sm:text-[28px]">
            Единый Inbox
          </h1>
          <p className="text-xs text-slate-400">
            Все переписки фермы в одном окне с AI-дожимом и автоквалификацией сделок.
          </p>
        </div>

        <button
          onClick={() => loadDialogs()}
          className="btn-ghost self-start sm:self-auto !px-3 !py-1.5 text-xs text-slate-300"
        >
          <RefreshCw size={13} />
          Обновить
        </button>
      </div>

      {/* Main Split Layout: Dialogs List + Chat View */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 h-[calc(100vh-230px)] min-h-[500px]">
        {/* Left Side: Dialogs List (Hidden on mobile if chat is active) */}
        <div
          className={`card flex flex-col overflow-hidden md:col-span-5 lg:col-span-4 ${
            activeDialog ? "hidden md:flex" : "flex"
          }`}
        >
          <div className="p-3.5 border-b border-white/[0.06] flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Диалоги ({dialogs.length})
            </span>
            <span className="text-[11px] text-slate-500">Автообновление 6с</span>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-white/[0.04]">
            {loading ? (
              <div className="p-4 text-center text-xs text-slate-500">Загрузка диалогов...</div>
            ) : dialogs.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500 space-y-2">
                <MessageSquare size={24} className="mx-auto text-slate-600" />
                <p>Пока нет входящих диалогов.</p>
                <p className="text-[11px] text-slate-600">
                  Запустите рассылку по лидам или дождитесь откликов с радара.
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
                    className={`w-full text-left p-3.5 transition flex items-start gap-3 hover:bg-white/[0.03] ${
                      isActive ? "bg-white/[0.06] border-l-2 border-brand-500" : ""
                    }`}
                  >
                    {/* Avatar */}
                    <div className="relative h-10 w-10 shrink-0 rounded-full bg-gradient-to-tr from-brand-600/40 to-fuchsia-600/40 border border-brand-500/30 flex items-center justify-center text-white font-bold text-xs">
                      {d.peer_name ? d.peer_name.slice(0, 2).toUpperCase() : "TG"}
                      {d.unread_count > 0 && (
                        <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-brand-500 text-[9px] font-bold text-white shadow-[0_0_8px_rgba(124,92,255,0.9)]">
                          {d.unread_count}
                        </span>
                      )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <p className="text-xs font-bold text-white truncate">
                          {d.peer_name || d.peer_username || `ID ${d.peer_id}`}
                        </p>
                        <span className="text-[10px] text-slate-500 shrink-0">
                          {d.last_message_at
                            ? new Date(d.last_message_at).toLocaleTimeString([], {
                                hour: "2-digit",
                                minute: "2-digit",
                              })
                            : ""}
                        </span>
                      </div>

                      <p className="mt-1 text-xs text-slate-400 line-clamp-1">
                        {d.last_message_preview || "Нет сообщений"}
                      </p>

                      <div className="mt-2 flex items-center justify-between">
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold border ${statusMeta.bg} ${statusMeta.text} ${statusMeta.border}`}
                        >
                          {statusMeta.label}
                        </span>
                        {d.account_id && (
                          <span className="text-[10px] text-slate-500 font-mono">
                            ферма TG
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

        {/* Right Side: Active Chat View (Full width on mobile when active) */}
        <div
          className={`card flex flex-col overflow-hidden md:col-span-7 lg:col-span-8 ${
            !activeDialog ? "hidden md:flex" : "flex"
          }`}
        >
          {activeDialog ? (
            <>
              {/* Chat Header */}
              <div className="p-3.5 border-b border-white/[0.06] flex items-center justify-between bg-[#111218]">
                <div className="flex items-center gap-2.5 min-w-0">
                  <button
                    onClick={() => setActiveDialog(null)}
                    className="icon-btn !h-8 !w-8 md:hidden shrink-0"
                    title="Назад к списку"
                  >
                    <ArrowLeft size={15} />
                  </button>

                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h2 className="text-sm font-bold text-white truncate">
                        {activeDialog.peer_name || activeDialog.peer_username || activeDialog.peer_id}
                      </h2>
                      {activeDialog.peer_username && (
                        <span className="text-xs text-brand-300 font-medium hidden sm:inline">
                          @{activeDialog.peer_username}
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] text-slate-400 truncate">
                      Диалог в Telegram · Статус: {activeDialog.status}
                    </p>
                  </div>
                </div>

                {/* Status Switcher & AI Button */}
                <div className="flex items-center gap-2">
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
                    className="h-8 rounded-lg border border-white/10 bg-[#161722] px-2 text-xs font-semibold text-slate-200 outline-none"
                  >
                    <option value="new">Новый</option>
                    <option value="ai_handling">AI-дожим</option>
                    <option value="manual">Вручную</option>
                    <option value="deal">Сделка 🔥</option>
                  </select>
                </div>
              </div>

              {/* Chat Messages Body */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-[#0a0b10]">
                {messagesLoading && messages.length === 0 ? (
                  <div className="flex h-full items-center justify-center">
                    <Spinner size={24} />
                  </div>
                ) : messages.length === 0 ? (
                  <div className="flex h-full flex-col items-center justify-center text-center p-6 text-slate-500 space-y-2">
                    <MessageSquare size={32} className="text-slate-600" />
                    <p className="text-xs">В этом диалоге ещё нет сообщений.</p>
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
                          className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-xs leading-relaxed shadow-sm ${
                            isOut
                              ? "bg-brand-500/20 border border-brand-500/30 text-white rounded-br-none"
                              : "bg-[#181924] border border-white/[0.08] text-slate-200 rounded-bl-none"
                          }`}
                        >
                          {m.text}

                          <div
                            className={`mt-1.5 flex items-center gap-1.5 text-[9px] ${
                              isOut ? "text-brand-300 justify-end" : "text-slate-500"
                            }`}
                          >
                            {m.is_ai_generated && (
                              <span className="inline-flex items-center gap-0.5 rounded bg-brand-500/30 px-1 py-0.2 font-bold text-[8px] text-brand-200">
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
              <div className="p-3 border-t border-white/[0.06] bg-[#111218] flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Напишите ответ клиенту..."
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      void handleSendMessage();
                    }
                  }}
                  className="input !h-10 text-xs"
                />

                <button
                  onClick={handleSendMessage}
                  disabled={sending || !inputText.trim()}
                  className="btn-primary !h-10 !w-10 !p-0 shrink-0"
                >
                  {sending ? <Spinner size={14} /> : <Send size={15} />}
                </button>
              </div>
            </>
          ) : (
            <div className="flex h-full flex-col items-center justify-center p-8 text-center text-slate-500 space-y-3">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-500/10 text-brand-300 border border-brand-500/20">
                <MessageSquare size={26} />
              </div>
              <h3 className="text-sm font-bold text-white">Выберите диалог</h3>
              <p className="max-w-xs text-xs text-slate-400">
                Выберите диалог из списка слева, чтобы просмотреть переписку и включить AI-дожим.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
