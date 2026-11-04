"use client";

import { useEffect, useState } from "react";
import {
  Check,
  Download,
  Filter,
  RefreshCw,
  Search,
  Sparkles,
  Star,
  Trash2,
  Users,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import { triggerHaptic } from "@/lib/telegram";
import type { ParsedUser } from "@/lib/types";

export default function ChatScrapingView({
  showToast,
  onGoToStories,
}: {
  showToast: (message: string, variant?: "success" | "error" | "info") => void;
  onGoToStories?: () => void;
}) {
  const [users, setUsers] = useState<ParsedUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [parsing, setParsing] = useState(false);

  // Form params
  const [chatInput, setChatInput] = useState("");
  const [limit, setLimit] = useState(100);
  const [onlyActive, setOnlyActive] = useState(true);
  const [onlyPremium, setOnlyPremium] = useState(false);

  // Search filter in table
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const list = await api.getParsedUsers();
      setUsers(list);
    } catch (err) {
      console.error("Failed to load parsed users:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleStartParse = async () => {
    if (!chatInput.trim()) {
      showToast("Укажите юзернейм или ссылку на чат", "error");
      return;
    }

    setParsing(true);
    triggerHaptic("medium");
    try {
      const parsed = await api.parseChat({
        chat_identifier: chatInput.trim(),
        limit,
        only_active: onlyActive,
        only_premium: onlyPremium,
      });
      // Refresh list
      const all = await api.getParsedUsers();
      setUsers(all);
      showToast(`Успешно спарсено ${parsed.length} участников!`, "success");
      setChatInput("");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Ошибка парсинга чата", "error");
    } finally {
      setParsing(false);
    }
  };

  const handleDeleteUser = async (id: string) => {
    triggerHaptic("light");
    try {
      await api.deleteParsedUser(id);
      setUsers((prev) => prev.filter((u) => u.id !== id));
      showToast("Участник удален из базы", "info");
    } catch (err) {
      showToast("Не удалось удалить", "error");
    }
  };

  const handleClearAll = async () => {
    if (!confirm("Вы уверены, что хотите полностью очистить базу участников?")) return;
    triggerHaptic("error");
    try {
      await api.clearParsedUsers();
      setUsers([]);
      showToast("База участников очищена", "info");
    } catch (err) {
      showToast("Не удалось очистить", "error");
    }
  };

  const handleExportCSV = () => {
    if (users.length === 0) return;
    triggerHaptic("light");
    const headers = ["Telegram ID", "Username", "First Name", "Last Name", "Premium", "Status", "Source Chat"];
    const rows = users.map((u) => [
      u.telegram_id,
      u.username ? `@${u.username}` : "",
      `"${u.first_name || ""}"`,
      `"${u.last_name || ""}"`,
      u.has_premium ? "Да" : "Нет",
      u.last_seen_status || "",
      u.source_chat,
    ]);
    const csvContent = "\uFEFF" + [headers.join(";"), ...rows.map((r) => r.join(";"))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `telegram_parsed_audience_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast("Экспорт в CSV готов!", "success");
  };

  const filteredUsers = users.filter((u) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      (u.username && u.username.toLowerCase().includes(q)) ||
      (u.first_name && u.first_name.toLowerCase().includes(q)) ||
      (u.last_name && u.last_name.toLowerCase().includes(q)) ||
      u.source_chat.toLowerCase().includes(q)
    );
  });

  const premiumCount = users.filter((u) => u.has_premium).length;
  const activeCount = users.filter((u) => u.last_seen_status === "online" || u.last_seen_status === "recently").length;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Banner */}
      <div className="rounded-2xl border border-brand-500/20 bg-gradient-to-r from-brand-950/40 via-purple-950/20 to-transparent p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Users className="text-brand-400" size={18} />
              Парсер участников групп и чатов
            </h2>
            <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
              Вытягивайте платёжеспособную аудиторию из тематических чатов бизнеса, e-commerce, стартапов и фриланса.
              Отсеивайте ботов, собирайте людей с <strong>Telegram Premium</strong> и активных пользователей для
              масслукинга историй и тёплого аутрича!
            </p>
          </div>
          {onGoToStories && (
            <button
              onClick={onGoToStories}
              className="flex items-center justify-center gap-1.5 rounded-xl border border-brand-500/30 bg-brand-500/10 px-4 py-2 text-xs font-semibold text-brand-300 hover:bg-brand-500/20 transition shrink-0"
            >
              <Sparkles size={13} className="text-amber-400" />
              Перейти к просмотру Stories
            </button>
          )}
        </div>
      </div>

      {/* Parsing Form */}
      <div className="rounded-2xl border border-white/10 bg-[#141414] p-5 space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center gap-2 border-b border-white/10 pb-3">
          <Zap className="text-brand-400" size={15} />
          Параметры сбора участников
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">
              Юзернейм или ссылка на открытый чат:
            </label>
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="@startup_chat или t.me/business_chat"
              className="w-full rounded-xl border border-white/10 bg-[#0d0d0d] px-3.5 py-2.5 text-xs text-white outline-none focus:border-brand-500 transition"
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs font-medium text-slate-400">
              <span>Лимит участников:</span>
              <span className="font-bold text-brand-400">{limit} чел.</span>
            </div>
            <input
              type="range"
              min={20}
              max={500}
              step={20}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="w-full accent-brand-500"
            />
            <div className="flex justify-between text-[10px] text-slate-500">
              <span>20</span>
              <span>250</span>
              <span>500</span>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-white/5">
          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={onlyActive}
                onChange={(e) => setOnlyActive(e.target.checked)}
                className="rounded accent-brand-500"
              />
              <span>Только активные (были в сети недавно)</span>
            </label>

            <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={onlyPremium}
                onChange={(e) => setOnlyPremium(e.target.checked)}
                className="rounded accent-brand-500"
              />
              <span className="flex items-center gap-1">
                Только с <Star size={11} className="text-amber-400 fill-amber-400" /> Telegram Premium
              </span>
            </label>
          </div>

          <button
            onClick={handleStartParse}
            disabled={parsing || !chatInput.trim()}
            className="flex items-center gap-2 rounded-xl bg-brand-500 px-5 py-2.5 text-xs font-bold text-white shadow-lg shadow-brand-500/25 hover:bg-brand-600 transition disabled:opacity-50"
          >
            {parsing ? <RefreshCw className="animate-spin" size={14} /> : <Zap size={14} />}
            {parsing ? "Сбор участников..." : "Запустить сбор"}
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="rounded-xl border border-white/10 bg-[#161616] p-4">
          <p className="text-[11px] text-slate-400 uppercase font-semibold">Всего собрано</p>
          <p className="text-xl font-bold text-white mt-1">{users.length} лидов</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-[#161616] p-4">
          <p className="text-[11px] text-slate-400 uppercase font-semibold flex items-center gap-1">
            <Star size={12} className="text-amber-400 fill-amber-400" /> Telegram Premium
          </p>
          <p className="text-xl font-bold text-amber-300 mt-1">{premiumCount} чел.</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-[#161616] p-4">
          <p className="text-[11px] text-slate-400 uppercase font-semibold">Активны онлайн / недавно</p>
          <p className="text-xl font-bold text-emerald-400 mt-1">{activeCount} чел.</p>
        </div>
      </div>

      {/* Audience Table */}
      <div className="rounded-2xl border border-white/10 bg-[#141414] overflow-hidden space-y-3 p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-2.5 text-slate-500" size={13} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Поиск по юзернейму, имени или чату..."
              className="w-full rounded-xl border border-white/10 bg-[#0d0d0d] pl-9 pr-3.5 py-1.5 text-xs text-white outline-none focus:border-brand-500"
            />
          </div>

          <div className="flex items-center gap-2">
            {users.length > 0 && (
              <>
                <button
                  onClick={handleExportCSV}
                  className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-[#1b1b1b] px-3 py-1.5 text-xs font-medium text-slate-300 hover:text-white transition"
                >
                  <Download size={13} />
                  Экспорт CSV
                </button>
                <button
                  onClick={handleClearAll}
                  className="flex items-center gap-1.5 rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-500/20 transition"
                >
                  <Trash2 size={13} />
                  Очистить
                </button>
              </>
            )}
          </div>
        </div>

        {users.length === 0 ? (
          <div className="rounded-xl border border-dashed border-white/10 p-10 text-center text-xs text-slate-400">
            База пуста. Введите ссылку на чат выше и запустите сбор участников!
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 text-[11px] text-slate-400">
                  <th className="pb-2.5 font-medium">Пользователь</th>
                  <th className="pb-2.5 font-medium">Юзернейм</th>
                  <th className="pb-2.5 font-medium">Статус</th>
                  <th className="pb-2.5 font-medium">Источник</th>
                  <th className="pb-2.5 font-medium">Stories</th>
                  <th className="pb-2.5 font-medium text-right">Действие</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filteredUsers.map((u) => (
                  <tr key={u.id} className="hover:bg-white/[0.02] transition">
                    <td className="py-2.5">
                      <div className="flex items-center gap-2">
                        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-500/10 text-brand-400 font-bold text-[11px]">
                          {(u.first_name || u.username || "U")[0].toUpperCase()}
                        </div>
                        <div>
                          <p className="font-semibold text-white flex items-center gap-1">
                            {u.first_name} {u.last_name || ""}
                            {u.has_premium && (
                              <span title="Telegram Premium">
                                <Star size={11} className="text-amber-400 fill-amber-400" />
                              </span>
                            )}
                          </p>
                          <p className="text-[10px] text-slate-500 font-mono">ID: {u.telegram_id}</p>
                        </div>
                      </div>
                    </td>

                    <td className="py-2.5">
                      {u.username ? (
                        <a
                          href={`https://t.me/${u.username}`}
                          target="_blank"
                          rel="noreferrer"
                          className="font-mono text-brand-400 hover:underline"
                        >
                          @{u.username}
                        </a>
                      ) : (
                        <span className="text-slate-500 italic">Скрыт</span>
                      )}
                    </td>

                    <td className="py-2.5">
                      <span
                        className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-semibold ${
                          u.last_seen_status === "online"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : u.last_seen_status === "recently"
                            ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                            : "bg-white/5 text-slate-400 border border-white/10"
                        }`}
                      >
                        {u.last_seen_status === "online" && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />}
                        {u.last_seen_status === "online"
                          ? "Онлайн"
                          : u.last_seen_status === "recently"
                          ? "Недавно"
                          : "Офлайн"}
                      </span>
                    </td>

                    <td className="py-2.5 text-slate-400 font-mono text-[11px] truncate max-w-[120px]">
                      {u.source_chat}
                    </td>

                    <td className="py-2.5">
                      {u.stories_viewed_at ? (
                        <span className="text-emerald-400 text-[11px] flex items-center gap-1">
                          <Check size={12} /> Просмотрено
                        </span>
                      ) : (
                        <span className="text-slate-500 text-[11px]">В очереди</span>
                      )}
                    </td>

                    <td className="py-2.5 text-right">
                      <button
                        onClick={() => handleDeleteUser(u.id)}
                        className="p-1 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition"
                        title="Удалить"
                      >
                        <Trash2 size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
