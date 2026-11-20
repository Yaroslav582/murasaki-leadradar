"use client";

import { useEffect, useState } from "react";
import {
  Bell,
  BookOpen,
  Bot,
  Check,
  Clock,
  Copy,
  Edit3,
  ExternalLink,
  Eye,
  Image as ImageIcon,
  MessageCircle,
  MessageSquare,
  Moon,
  Pause,
  Play,
  Plus,
  Radio,
  RefreshCw,
  Search,
  Send,
  Settings,
  Share2,
  Sparkles,
  Sun,
  Trash2,
  UserCheck,
  Users,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { triggerHaptic } from "@/lib/telegram";
import type { TelegramBroadcast, TelegramChatTarget, TelegramOrder, TelegramStatus } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import type { ToastVariant } from "./ui";
import { Spinner } from "./ui";
import NeuroCommentingView from "./NeuroCommentingView";
import ChatScrapingView from "./ChatScrapingView";
import StoriesMasslookingView from "./StoriesMasslookingView";
import ChannelAutoBlogView from "./ChannelAutoBlogView";
import TGStatModal from "./TGStatModal";

const COOLDOWN_OPTIONS = [
  { label: "30 минут", value: 30 },
  { label: "1 час", value: 60 },
  { label: "2 часа", value: 120 },
  { label: "4 часа", value: 240 },
  { label: "6 часов", value: 360 },
  { label: "12 часов", value: 720 },
  { label: "24 часа (раз в сутки)", value: 1440 },
];

export default function TelegramRadarView({
  showToast,
  initialTab = "orders",
}: {
  showToast: (message: string, variant?: ToastVariant) => void;
  initialTab?: "orders" | "blog" | "comments" | "scraper" | "stories" | "promo" | "chats";
}) {
  const [tab, setTab] = useState<"orders" | "blog" | "comments" | "scraper" | "stories" | "promo" | "chats">(initialTab);

  useEffect(() => {
    if (initialTab) {
      setTab(initialTab);
    }
  }, [initialTab]);
  const [status, setStatus] = useState<TelegramStatus | null>(null);
  const [orders, setOrders] = useState<TelegramOrder[]>([]);
  const [broadcasts, setBroadcasts] = useState<TelegramBroadcast[]>([]);
  const [chats, setChats] = useState<TelegramChatTarget[]>([]);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [broadcasting, setBroadcasting] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [nowTs, setNowTs] = useState(Date.now());
  const [refreshingScreenshot, setRefreshingScreenshot] = useState(false);
  const [screenshotVersion, setScreenshotVersion] = useState(Date.now());

  // Settings
  const [portfolioInput, setPortfolioInput] = useState("https://murasaki-portfolio.vercel.app/");
  const [delayInput, setDelayInput] = useState(10);
  const [workingHoursStart, setWorkingHoursStart] = useState("09:00");
  const [workingHoursEnd, setWorkingHoursEnd] = useState("23:00");
  const [workingHoursEnabled, setWorkingHoursEnabled] = useState(true);
  const [autoPostingEnabled, setAutoPostingEnabled] = useState(true);
  const [broadcastInterval, setBroadcastInterval] = useState(120);
  const [keywordsInput, setKeywordsInput] = useState("");
  const [stopWordsInput, setStopWordsInput] = useState("");
  const [settingsTab, setSettingsTab] = useState<"radar" | "autopost">("radar");
  const [savingSettings, setSavingSettings] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // New chat modal
  const [showAddChat, setShowAddChat] = useState(false);
  const [showTGStatModal, setShowTGStatModal] = useState(false);
  const [newChatId, setNewChatId] = useState("");
  const [newChatTitle, setNewChatTitle] = useState("");
  const [newChatKind, setNewChatKind] = useState("both");
  const [newChatCooldown, setNewChatCooldown] = useState(120);
  const [addingChat, setAddingChat] = useState(false);

  // Edit custom text modal
  const [editingChat, setEditingChat] = useState<TelegramChatTarget | null>(null);
  const [customTextDraft, setCustomTextDraft] = useState("");
  const [savingChatText, setSavingChatText] = useState(false);

  // Filter for chats tab
  const [chatFilter, setChatFilter] = useState<"all" | "orders" | "promo">("all");
  const [orderSourceFilter, setOrderSourceFilter] = useState<"all" | "kwork" | "fl" | "telegram">("all");
  const [syncingExternal, setSyncingExternal] = useState(false);

  // Timer loop for countdowns
  useEffect(() => {
    const timer = setInterval(() => setNowTs(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [st, ords, bcasts, chs] = await Promise.all([
        api.getTelegramStatus(),
        api.listTelegramOrders(),
        api.listTelegramBroadcasts(),
        api.listTelegramChats(),
      ]);
      setStatus(st);
      setOrders(ords);
      setBroadcasts(bcasts);
      setChats(chs);
      setPortfolioInput(st.portfolio_url || "https://murasaki-portfolio.vercel.app/");
      setDelayInput(Math.round((st.auto_response_delay_min + st.auto_response_delay_max) / 120));
      setWorkingHoursStart(st.working_hours_start || "09:00");
      setWorkingHoursEnd(st.working_hours_end || "23:00");
      setWorkingHoursEnabled(st.working_hours_enabled ?? true);
      setAutoPostingEnabled(st.auto_posting_enabled ?? true);
      setBroadcastInterval(st.broadcast_interval_minutes || 120);
      setKeywordsInput(Array.isArray(st.keywords) ? st.keywords.join(", ") : "");
      setStopWordsInput(Array.isArray(st.stop_words) ? st.stop_words.join(", ") : "");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Не удалось загрузить данные Telegram", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Toggle master auto-response switch (Start / Stop)
  const handleToggleAutoResponse = async () => {
    if (!status) return;
    const newState = !status.auto_response_enabled;
    triggerHaptic("medium");
    try {
      await api.updateTelegramSettings({ auto_response_enabled: newState });
      setStatus({ ...status, auto_response_enabled: newState });
      showToast(
        newState ? "🟢 Автоотклик активирован — ловим заказы!" : "⏸ Автоотклик остановлен (на паузе)",
        newState ? "success" : "info"
      );
    } catch (err) {
      showToast("Ошибка смены статуса автоотклика", "error");
    }
  };

  const handleSimulate = async () => {
    setSimulating(true);
    triggerHaptic("medium");
    try {
      const newOrder = await api.simulateTelegramOrder();
      setOrders((prev) => [newOrder, ...prev]);
      showToast("Заказ перехвачен! Нейросеть подготовила отклик с таймером ~10 мин", "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Ошибка симуляции", "error");
    } finally {
      setSimulating(false);
    }
  };

  const handleSyncExternal = async () => {
    setSyncingExternal(true);
    triggerHaptic("medium");
    try {
      const res = await api.syncExternalOrders();
      await loadData();
      showToast(`Найдено и добавлено ${res.synced} новых заказов с Kwork и FL.ru!`, "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Не удалось спарсить биржи", "error");
    } finally {
      setSyncingExternal(false);
    }
  };

  const handleSendNow = async (orderId: string) => {
    triggerHaptic("light");
    try {
      const updated = await api.respondTelegramOrder(orderId);
      setOrders((prev) => prev.map((o) => (o.id === orderId ? updated : o)));
      showToast("Отклик отправлен заказчику в Telegram!", "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Ошибка отправки", "error");
    }
  };

  const handleSkip = async (orderId: string) => {
    triggerHaptic("light");
    try {
      const updated = await api.skipTelegramOrder(orderId);
      setOrders((prev) => prev.map((o) => (o.id === orderId ? updated : o)));
      showToast("Заказ пропущен", "info");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Ошибка", "error");
    }
  };

  const handleBroadcast = async () => {
    setBroadcasting(true);
    triggerHaptic("medium");
    try {
      const newBroadcast = await api.triggerTelegramBroadcast();
      setBroadcasts((prev) => [newBroadcast, ...prev]);
      showToast("Пост-визитка с портфолио опубликован в Telegram!", "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Ошибка автопосева", "error");
    } finally {
      setBroadcasting(false);
    }
  };

  const handlePostNowToChat = async (chatId: string, title: string) => {
    triggerHaptic("medium");
    try {
      const res = await api.postNowToTelegramChat(chatId);
      setBroadcasts((prev) => [res, ...prev]);
      showToast(`Пост опубликован в «${title}»!`, "success");
      loadData();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Ошибка публикации", "error");
    }
  };

  const handleRefreshScreenshot = async () => {
    triggerHaptic("medium");
    setRefreshingScreenshot(true);
    try {
      const res = await api.refreshPortfolioScreenshot();
      setScreenshotVersion(Date.now());
      showToast(res.message || "Скриншот первой страницы портфолио обновлен!", "success");
    } catch (err) {
      showToast("Ошибка обновления скриншота", "error");
    } finally {
      setRefreshingScreenshot(false);
    }
  };

  const handleToggleChatAutoPost = async (chat: TelegramChatTarget) => {
    triggerHaptic("light");
    const updatedState = !chat.auto_post_enabled;
    try {
      const updated = await api.updateTelegramChat(chat.id, {
        auto_post_enabled: updatedState,
      });
      setChats((prev) => prev.map((c) => (c.id === chat.id ? updated : c)));
      showToast(
        updatedState
          ? `Автопостинг для «${chat.title}» включен (КД ${chat.cooldown_minutes} мин)`
          : `Автопостинг для «${chat.title}» отключен`,
        "info"
      );
    } catch (err) {
      showToast("Ошибка обновления", "error");
    }
  };

  const handleChangeCooldown = async (chat: TelegramChatTarget, cd: number) => {
    triggerHaptic("light");
    try {
      const updated = await api.updateTelegramChat(chat.id, {
        cooldown_minutes: cd,
      });
      setChats((prev) => prev.map((c) => (c.id === chat.id ? updated : c)));
      showToast(`КД для «${chat.title}» изменен на ${cd} мин`, "success");
    } catch (err) {
      showToast("Ошибка обновления КД", "error");
    }
  };

  const handleOpenEditCustomText = (chat: TelegramChatTarget) => {
    setEditingChat(chat);
    setCustomTextDraft(chat.custom_text || "");
  };

  const handleSaveCustomText = async () => {
    if (!editingChat) return;
    setSavingChatText(true);
    triggerHaptic("light");
    try {
      const updated = await api.updateTelegramChat(editingChat.id, {
        custom_text: customTextDraft.trim() || undefined,
      });
      setChats((prev) => prev.map((c) => (c.id === editingChat.id ? updated : c)));
      showToast(`Текст для «${editingChat.title}» сохранен`, "success");
      setEditingChat(null);
    } catch (err) {
      showToast("Ошибка сохранения текста", "error");
    } finally {
      setSavingChatText(false);
    }
  };

  const handleSaveSettings = async () => {
    setSavingSettings(true);
    triggerHaptic("light");
    try {
      await api.updateTelegramSettings({
        portfolio_url: portfolioInput.trim(),
        auto_posting_enabled: autoPostingEnabled,
        working_hours_enabled: workingHoursEnabled,
        working_hours_start: workingHoursStart.trim(),
        working_hours_end: workingHoursEnd.trim(),
        telegram_auto_response_delay_min: Math.max(1, delayInput - 2) * 60,
        telegram_auto_response_delay_max: Math.max(2, delayInput + 2) * 60,
        telegram_broadcast_interval_minutes: broadcastInterval,
        keywords: keywordsInput.trim(),
        stop_words: stopWordsInput.trim(),
      });
      showToast("Настройки успешно сохранены в Supabase", "success");
      setShowSettings(false);
      await loadData();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Ошибка сохранения", "error");
    } finally {
      setSavingSettings(false);
    }
  };

  const handleAddChat = async () => {
    if (!newChatId.trim()) return;
    setAddingChat(true);
    triggerHaptic("light");
    try {
      const added = await api.addTelegramChat({
        chat_id: newChatId.trim(),
        title: newChatTitle.trim() || newChatId.trim(),
        kind: newChatKind,
        cooldown_minutes: newChatCooldown,
      });
      setChats((prev) => [...prev, added]);
      setShowAddChat(false);
      setNewChatId("");
      setNewChatTitle("");
      showToast("Чат добавлен в мониторинг", "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Не удалось добавить чат", "error");
    } finally {
      setAddingChat(false);
    }
  };

  const handleDeleteChat = async (id: string) => {
    triggerHaptic("light");
    try {
      await api.deleteTelegramChat(id);
      setChats((prev) => prev.filter((c) => c.id !== id));
      showToast("Чат удален из мониторинга", "info");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Ошибка удаления", "error");
    }
  };

  const copyText = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    triggerHaptic("light");
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
    showToast("Текст скопирован в буфер", "info");
  };

  const formatCountdown = (scheduledForStr: string | null) => {
    if (!scheduledForStr) return null;
    const target = new Date(scheduledForStr).getTime();
    const diff = Math.max(0, Math.floor((target - nowTs) / 1000));
    if (diff <= 0) return "Отправка прямо сейчас";
    const mins = Math.floor(diff / 60);
    const secs = diff % 60;
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  const formatNextPost = (nextPostStr: string | null) => {
    if (!nextPostStr) return "В очереди";
    const target = new Date(nextPostStr).getTime();
    const diff = Math.floor((target - nowTs) / 1000);
    if (diff <= 0) return "Готов к публикации";
    const mins = Math.floor(diff / 60);
    if (mins < 60) return `через ${mins} мин`;
    const hours = Math.floor(mins / 60);
    return `через ${hours} ч ${mins % 60} мин`;
  };

  const filteredChats = chats.filter((c) => {
    if (chatFilter === "orders") return c.kind === "orders" || c.kind === "both";
    if (chatFilter === "promo") return c.kind === "promo" || c.kind === "both";
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Top Banner / Master Controls */}
      <div className="rounded-2xl border border-white/[0.04] bg-[#1A1C23] p-5 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05),0_4px_20px_rgba(0,0,0,0.3)] sm:p-6">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#242731] border border-white/[0.06] text-[#8B5CF6]">
                <Radio size={14} className={status?.auto_response_enabled ? "animate-pulse" : ""} />
              </span>
              <h2 className="text-xl font-semibold tracking-tight text-[#F3F4F6]">TG-Радар заказов и автопосев</h2>
              <span className="rounded-md border border-emerald-500/20 bg-[rgba(16,185,129,0.12)] px-2 py-0.5 text-xs font-medium text-[#10B981]">
                {status?.is_connected ? "UserBot @loves_kyni активен" : "Готов к подключению"}
              </span>
            </div>
            <p className="text-xs text-[#9CA3AF] max-w-2xl">
              Мониторит каналы фриланса, перехватывает заказы на сайты, готовит вежливый отклик через нейросеть с таймером ~10 мин и сеет промо по расписанию.
            </p>
          </div>

          {/* Master Action Buttons */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Auto-response Start / Stop button */}
            <button
              onClick={handleToggleAutoResponse}
              className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
                status?.auto_response_enabled
                  ? "bg-rose-500/15 text-rose-300 border border-rose-500/30 hover:bg-rose-500/25"
                  : "bg-[#10B981] text-white hover:bg-emerald-600"
              }`}
            >
              {status?.auto_response_enabled ? (
                <>
                  <Pause size={13} />
                  <span>Остановить автоотклик</span>
                </>
              ) : (
                <>
                  <Play size={13} />
                  <span>Возобновить автоотклик</span>
                </>
              )}
            </button>

            <button onClick={handleSimulate} disabled={simulating} className="btn-primary">
              {simulating ? <Spinner size={14} /> : <Sparkles size={14} />}
              Симулировать заказ
            </button>

            <button
              onClick={() => {
                triggerHaptic("light");
                setSettingsTab(tab === "promo" ? "autopost" : "radar");
                setShowSettings((prev) => !prev);
              }}
              className="btn-ghost"
              title="Настройки модулей"
            >
              <Settings size={14} />
              Настройки
            </button>

            <button onClick={loadData} disabled={loading} className="icon-btn" title="Обновить данные">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
        </div>

        {/* Working Hours & Status Banner */}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/[0.06] bg-[#242731] px-4 py-2.5 text-xs">
          <div className="flex items-center gap-2">
            {status?.is_in_working_hours ? (
              <Sun size={15} className="text-amber-400" />
            ) : (
              <Moon size={15} className="text-indigo-400" />
            )}
            <span className="text-slate-300 font-medium">
              Таймер ловли заказов:{" "}
              <strong className={status?.is_in_working_hours ? "text-emerald-400" : "text-amber-400"}>
                {status?.working_hours_status_text || "09:00 - 23:00"}
              </strong>
            </span>
          </div>

          <div className="flex items-center gap-3 text-slate-400">
            <span>
              Портфолио:{" "}
              <a
                href={status?.portfolio_url || "https://murasaki-portfolio.vercel.app/"}
                target="_blank"
                rel="noopener noreferrer"
                className="text-brand-300 underline font-mono"
              >
                murasaki-portfolio.vercel.app
              </a>
            </span>
            <span className="hidden sm:inline">•</span>
            <span className="text-slate-300 font-semibold">
              Статус отклика:{" "}
              {status?.auto_response_enabled ? (
                <span className="text-emerald-400 font-bold">Включен (активен)</span>
              ) : (
                <span className="text-rose-400 font-bold">На паузе</span>
              )}
            </span>
          </div>
        </div>

        {/* Quick Stats Grid */}
        <div className="mt-4 grid grid-cols-2 gap-2.5 border-t border-white/[0.06] pt-4 sm:grid-cols-4">
          <div className="rounded-lg border border-white/[0.06] bg-[#242731] p-3">
            <p className="text-[11px] font-medium text-[#9CA3AF]">Перехвачено заказов</p>
            <p className="mt-1 text-lg font-semibold font-mono tabular-nums text-[#F3F4F6]">{orders.length}</p>
          </div>
          <div className="rounded-lg border border-white/[0.06] bg-[#242731] p-3">
            <p className="text-[11px] font-medium text-[#9CA3AF]">Автопосевов сделано</p>
            <p className="mt-1 text-lg font-semibold font-mono tabular-nums text-[#F3F4F6]">{broadcasts.length}</p>
          </div>
          <div className="rounded-lg border border-white/[0.06] bg-[#242731] p-3">
            <p className="text-[11px] font-medium text-[#9CA3AF]">Каналов на радаре</p>
            <p className="mt-1 text-lg font-semibold font-mono tabular-nums text-[#F3F4F6]">{chats.length}</p>
          </div>
          <div className="rounded-lg border border-white/[0.06] bg-[#242731] p-3">
            <p className="text-[11px] font-medium text-[#9CA3AF]">КД отклика</p>
            <p className="mt-1 text-lg font-semibold font-mono tabular-nums text-[#C4B5FD]">~{delayInput} мин</p>
          </div>
        </div>
      </div>

      {/* Settings Panel (collapsible) */}
      {showSettings && (
        <div className="rounded-2xl border border-brand-500/30 bg-[#181818] p-5 shadow-2xl space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-white/10 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/10 text-brand-400 border border-brand-500/20">
                <Settings size={16} />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  {settingsTab === "radar" ? "Настройки: ТГ Радар заказов" : "Настройки: Автопосев визиток"}
                </h3>
                <p className="text-[11px] text-slate-400">
                  Сохраняются в Supabase и синхронизируются с воркерами на сервере
                </p>
              </div>
            </div>

            {/* Sub-tabs between Radar and Autopost */}
            <div className="flex items-center gap-2">
              <div className="flex rounded-lg border border-white/[0.06] bg-[#242731] p-1">
                <button
                  type="button"
                  onClick={() => {
                    triggerHaptic("light");
                    setSettingsTab("radar");
                  }}
                  className={`px-3 py-1 rounded text-xs font-semibold transition ${
                    settingsTab === "radar"
                      ? "bg-brand-500 text-white shadow-sm"
                      : "text-[#9CA3AF] hover:text-[#F3F4F6]"
                  }`}
                >
                  Радар заказов
                </button>
                <button
                  type="button"
                  onClick={() => {
                    triggerHaptic("light");
                    setSettingsTab("autopost");
                  }}
                  className={`px-3 py-1 rounded text-xs font-semibold transition ${
                    settingsTab === "autopost"
                      ? "bg-brand-500 text-white shadow-sm"
                      : "text-[#9CA3AF] hover:text-[#F3F4F6]"
                  }`}
                >
                  Автопосев
                </button>
              </div>

              <button
                onClick={() => setShowSettings(false)}
                className="text-xs text-slate-400 hover:text-white px-2.5 py-1.5 rounded-lg bg-white/5 border border-white/5 transition"
              >
                ✕ Закрыть
              </button>
            </div>
          </div>

          {settingsTab === "radar" ? (
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5 sm:col-span-2">
                <label className="text-xs font-semibold text-slate-300">Ссылка на портфолио / сайт для откликов</label>
                <input
                  value={portfolioInput}
                  onChange={(e) => setPortfolioInput(e.target.value)}
                  placeholder="https://murasaki-portfolio.vercel.app/"
                  className="input"
                />
                <p className="text-[11px] text-slate-500">
                  Подставляется в AI-отклики заказчикам на Kwork, FL.ru и в Telegram.
                </p>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">Задержка перед автооткликом (минут)</label>
                <input
                  type="number"
                  min={1}
                  max={60}
                  value={delayInput}
                  onChange={(e) => setDelayInput(Number(e.target.value))}
                  className="input"
                />
                <p className="text-[11px] text-slate-500">Имитирует человека и защищает от спам-фильтров Telegram.</p>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-300">Часы ловли заказов (МСК)</label>
                  <label className="flex items-center gap-1.5 text-[11px] text-slate-400 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={workingHoursEnabled}
                      onChange={(e) => setWorkingHoursEnabled(e.target.checked)}
                      className="rounded border-white/10"
                    />
                    <span>Активны</span>
                  </label>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={workingHoursStart}
                    onChange={(e) => setWorkingHoursStart(e.target.value)}
                    placeholder="09:00"
                    className="input w-24 text-center font-mono"
                  />
                  <span className="text-slate-400">—</span>
                  <input
                    type="text"
                    value={workingHoursEnd}
                    onChange={(e) => setWorkingHoursEnd(e.target.value)}
                    placeholder="23:00"
                    className="input w-24 text-center font-mono"
                  />
                </div>
                <p className="text-[11px] text-slate-500">Ночью автоотклики не отправляются, чтобы не беспокоить клиентов.</p>
              </div>

              <div className="space-y-1.5 sm:col-span-2">
                <label className="text-xs font-semibold text-slate-300">Ключевые слова для ловли заказов (через запятую)</label>
                <input
                  value={keywordsInput}
                  onChange={(e) => setKeywordsInput(e.target.value)}
                  placeholder="сайт, лендинг, разработка, мини апп, mini app, webapp, bot, бот, figma"
                  className="input"
                />
                <p className="text-[11px] text-slate-500">Заказы, содержащие эти слова, попадают на радар и получают AI-отклик.</p>
              </div>

              <div className="space-y-1.5 sm:col-span-2">
                <label className="text-xs font-semibold text-slate-300">Стоп-слова / минус-слова (через запятую)</label>
                <input
                  value={stopWordsInput}
                  onChange={(e) => setStopWordsInput(e.target.value)}
                  placeholder="вакансия, fulltime, офис, 1с, bitrix, seo, контекст, стажер"
                  className="input"
                />
                <p className="text-[11px] text-slate-500">Сообщения с этими словами автоматически отсеиваются и не засоряют радар.</p>
              </div>
            </div>
          ) : (
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-white/10 bg-[#242731] p-4 sm:col-span-2 flex items-center justify-between">
                <div>
                  <p className="text-xs font-bold text-white">Автопостинг промо-визиток в каналы</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Автоматическая публикация Retina-скриншота портфолио с уникальным AI-текстом по таймеру
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    triggerHaptic("medium");
                    setAutoPostingEnabled(!autoPostingEnabled);
                  }}
                  className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition ${
                    autoPostingEnabled
                      ? "bg-emerald-500 text-white shadow-emerald-500/20 shadow-md"
                      : "bg-white/10 text-slate-400 hover:text-white"
                  }`}
                >
                  {autoPostingEnabled ? "✓ Включен" : "✕ На паузе"}
                </button>
              </div>

              <div className="space-y-1.5 sm:col-span-2">
                <label className="text-xs font-semibold text-slate-300">Периодичность автопосева:</label>
                <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                  {[
                    { label: "30 мин", val: 30 },
                    { label: "1 час", val: 60 },
                    { label: "2 часа", val: 120 },
                    { label: "6 часов", val: 360 },
                    { label: "12 часов", val: 720 },
                    { label: "24 часа", val: 1440 },
                  ].map((item) => (
                    <button
                      key={item.val}
                      type="button"
                      onClick={() => setBroadcastInterval(item.val)}
                      className={`rounded-xl p-2 text-center text-xs font-semibold transition ${
                        broadcastInterval === item.val
                          ? "border border-brand-500 bg-brand-500/20 text-brand-300 shadow-sm"
                          : "border border-white/10 bg-[#242731] text-slate-400 hover:text-white"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-slate-500">
                  Минимальный интервал между публикациями промо-визиток по добавленным каналам.
                </p>
              </div>

              <div className="space-y-1.5 sm:col-span-2">
                <label className="text-xs font-semibold text-slate-300">Ссылка на портфолио в визитках</label>
                <input
                  value={portfolioInput}
                  onChange={(e) => setPortfolioInput(e.target.value)}
                  placeholder="https://murasaki-portfolio.vercel.app/"
                  className="input"
                />
              </div>

              <div className="rounded-xl border border-white/5 bg-[#242731] p-3.5 sm:col-span-2 flex items-center justify-between text-xs">
                <span className="text-slate-300">
                  Управление чатами и каналами для посева ({chats.filter((c) => c.kind === "promo" || c.kind === "both").length} подключено)
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setShowSettings(false);
                    setTab("chats");
                  }}
                  className="text-xs text-brand-300 hover:underline font-semibold"
                >
                  Открыть вкладку «Каналы» →
                </button>
              </div>
            </div>
          )}

          <div className="mt-4 flex items-center justify-between border-t border-white/10 pt-3">
            <span className="text-[11px] text-slate-400">
              {settingsTab === "radar" ? "Настройки ТГ-Радара" : "Настройки Автопосева"}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setShowSettings(false)}
                className="btn-ghost text-xs"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={handleSaveSettings}
                disabled={savingSettings}
                className="btn-primary text-xs"
              >
                {savingSettings ? <Spinner size={13} /> : <Check size={13} />}
                Сохранить настройки
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Tabs Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.07] pb-3">
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => {
              triggerHaptic("light");
              setTab("orders");
            }}
            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              tab === "orders"
                ? "bg-[#8B5CF6] text-white"
                : "border border-white/[0.06] bg-[#242731] text-[#9CA3AF] hover:text-[#F3F4F6]"
            }`}
          >
            <MessageSquare size={13} />
            Заказы фриланса (<span className="font-mono tabular-nums">{orders.length}</span>)
          </button>

          <button
            onClick={() => {
              triggerHaptic("light");
              setTab("blog");
            }}
            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              tab === "blog"
                ? "bg-[#8B5CF6] text-white"
                : "border border-white/[0.06] bg-[#242731] text-[#9CA3AF] hover:text-[#F3F4F6]"
            }`}
          >
            <BookOpen size={13} className={tab === "blog" ? "text-white" : "text-amber-400"} />
            Автоблогер
          </button>

          <button
            onClick={() => {
              triggerHaptic("light");
              setTab("comments");
            }}
            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              tab === "comments"
                ? "bg-[#8B5CF6] text-white"
                : "border border-white/[0.06] bg-[#242731] text-[#9CA3AF] hover:text-[#F3F4F6]"
            }`}
          >
            <MessageCircle size={13} className={tab === "comments" ? "text-white" : "text-[#8B5CF6]"} />
            Нейрокомментинг
          </button>

          <button
            onClick={() => {
              triggerHaptic("light");
              setTab("scraper");
            }}
            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              tab === "scraper"
                ? "bg-[#8B5CF6] text-white"
                : "border border-white/[0.06] bg-[#242731] text-[#9CA3AF] hover:text-[#F3F4F6]"
            }`}
          >
            <UserCheck size={13} className={tab === "scraper" ? "text-white" : "text-emerald-400"} />
            Парсер чатов
          </button>

          <button
            onClick={() => {
              triggerHaptic("light");
              setTab("stories");
            }}
            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              tab === "stories"
                ? "bg-[#8B5CF6] text-white"
                : "border border-white/[0.06] bg-[#242731] text-[#9CA3AF] hover:text-[#F3F4F6]"
            }`}
          >
            <Eye size={13} className={tab === "stories" ? "text-white" : "text-amber-400"} />
            Stories
          </button>

          <button
            onClick={() => {
              triggerHaptic("light");
              setTab("promo");
            }}
            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              tab === "promo"
                ? "bg-[#8B5CF6] text-white"
                : "border border-white/[0.06] bg-[#242731] text-[#9CA3AF] hover:text-[#F3F4F6]"
            }`}
          >
            <Share2 size={13} />
            История автопосева (<span className="font-mono tabular-nums">{broadcasts.length}</span>)
          </button>

          <button
            onClick={() => {
              triggerHaptic("light");
              setTab("chats");
            }}
            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              tab === "chats"
                ? "bg-[#8B5CF6] text-white"
                : "border border-white/[0.06] bg-[#242731] text-[#9CA3AF] hover:text-[#F3F4F6]"
            }`}
          >
            <Users size={13} />
            Каналы & Автопостинг (<span className="font-mono tabular-nums">{chats.length}</span>)
          </button>
        </div>

        {tab === "promo" && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                triggerHaptic("light");
                setSettingsTab("autopost");
                setShowSettings(true);
              }}
              className="btn-ghost text-xs flex items-center gap-1.5"
              title="Настройки параметров и периодичности автопосева"
            >
              <Settings size={13} />
              <span>Настройки</span>
            </button>
            <button onClick={handleBroadcast} disabled={broadcasting} className="btn-primary text-xs">
              {broadcasting ? <Spinner size={13} /> : <Send size={13} />}
              Сгенерировать и отправить вариант
            </button>
          </div>
        )}

        {tab === "chats" && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                triggerHaptic("light");
                setShowTGStatModal(true);
              }}
              className="btn-secondary text-xs flex items-center gap-1.5 bg-gradient-to-r from-violet-600/20 to-brand-500/20 text-brand-300 border border-brand-500/30 hover:border-brand-500/50 shadow-sm"
              title="Поиск супергрупп и чатов через официальный TGStat API"
            >
              <Sparkles size={13} className="text-amber-400" />
              <span>Поиск чатов в TGStat</span>
            </button>
            <button onClick={() => setShowAddChat(true)} className="btn-primary text-xs">
              <Plus size={13} />
              Добавить вручную
            </button>
          </div>
        )}
      </div>

      {/* Tab 1: Orders Feed */}
      {tab === "orders" && (
        <div className="space-y-4">
          {/* Source Sub-filters & Manual Sync */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-3 text-xs">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-slate-400 mr-1.5 font-medium">Биржи:</span>
              <button
                onClick={() => setOrderSourceFilter("all")}
                className={`rounded-lg px-2.5 py-1 font-semibold transition ${
                  orderSourceFilter === "all" ? "bg-brand-500 text-white" : "bg-white/[0.04] text-slate-400 hover:text-white"
                }`}
              >
                Все заказы ({orders.length})
              </button>
              <button
                onClick={() => setOrderSourceFilter("kwork")}
                className={`flex items-center gap-1 rounded-lg px-2.5 py-1 font-semibold transition ${
                  orderSourceFilter === "kwork"
                    ? "bg-amber-500 text-black font-bold"
                    : "bg-amber-500/10 text-amber-300 hover:bg-amber-500/20"
                }`}
              >
                <span>🟠 Kwork</span>
                <span className="text-[10px] opacity-80">
                  ({orders.filter((o) => o.source === "kwork").length})
                </span>
              </button>
              <button
                onClick={() => setOrderSourceFilter("fl")}
                className={`flex items-center gap-1 rounded-lg px-2.5 py-1 font-semibold transition ${
                  orderSourceFilter === "fl"
                    ? "bg-sky-500 text-white font-bold"
                    : "bg-sky-500/10 text-sky-300 hover:bg-sky-500/20"
                }`}
              >
                <span>🔵 FL.ru</span>
                <span className="text-[10px] opacity-80">
                  ({orders.filter((o) => o.source === "fl").length})
                </span>
              </button>
              <button
                onClick={() => setOrderSourceFilter("telegram")}
                className={`flex items-center gap-1 rounded-lg px-2.5 py-1 font-semibold transition ${
                  orderSourceFilter === "telegram"
                    ? "bg-indigo-500 text-white font-bold"
                    : "bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20"
                }`}
              >
                <span>✈️ Telegram</span>
                <span className="text-[10px] opacity-80">
                  ({orders.filter((o) => !o.source || o.source === "telegram").length})
                </span>
              </button>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  triggerHaptic("light");
                  setSettingsTab("radar");
                  setShowSettings(true);
                }}
                className="flex items-center gap-1.5 rounded-xl border border-white/[0.08] bg-[#242731] px-3 py-1.5 text-xs font-semibold text-[#9CA3AF] transition hover:text-[#F3F4F6] hover:border-white/20"
                title="Настройки перехвата заказов и автооткликов"
              >
                <Settings size={12} />
                <span>Настройки</span>
              </button>

              <button
                onClick={handleSyncExternal}
                disabled={syncingExternal}
                className="flex items-center gap-1.5 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-semibold text-amber-300 transition hover:bg-amber-500/20"
                title="Спарсить свежие заказы с бирж Kwork и FL.ru"
              >
                {syncingExternal ? <Spinner size={12} /> : <Sparkles size={12} />}
                Собрать с Kwork & FL ⚡️
              </button>
            </div>
          </div>

          {orders.filter((o) => {
            if (orderSourceFilter === "kwork") return o.source === "kwork";
            if (orderSourceFilter === "fl") return o.source === "fl";
            if (orderSourceFilter === "telegram") return !o.source || o.source === "telegram";
            return true;
          }).length === 0 ? (
            <div className="rounded-2xl border border-dashed border-white/10 p-10 text-center">
              <MessageSquare size={32} className="mx-auto text-slate-600" />
              <p className="mt-3 text-sm font-semibold text-slate-300">
                {orderSourceFilter !== "all"
                  ? `Нет заказов из источника «${orderSourceFilter.toUpperCase()}»`
                  : "Пока нет перехваченных заказов"}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Нажмите «Собрать с Kwork & FL ⚡️» или «Симулировать заказ», чтобы наполнить радар.
              </p>
            </div>
          ) : (
            orders
              .filter((o) => {
                if (orderSourceFilter === "kwork") return o.source === "kwork";
                if (orderSourceFilter === "fl") return o.source === "fl";
                if (orderSourceFilter === "telegram") return !o.source || o.source === "telegram";
                return true;
              })
              .map((order) => {
                const isPending = order.status === "pending";
                const isSent = order.status === "sent";
                const isSkipped = order.status === "skipped";
                const countdown = isPending ? formatCountdown(order.scheduled_for) : null;
                const isKwork = order.source === "kwork";
                const isFL = order.source === "fl";

                return (
                  <div
                    key={order.id}
                    className="rounded-2xl border border-white/10 bg-[#161616] p-5 shadow-lg transition hover:border-white/20"
                  >
                    <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
                      <div className="flex flex-wrap items-center gap-2">
                        {/* Source Tag Badge */}
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border ${
                            isKwork
                              ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
                              : isFL
                                ? "bg-sky-500/15 text-sky-300 border-sky-500/30"
                                : "bg-indigo-500/15 text-indigo-300 border-indigo-500/30"
                          }`}
                        >
                          {isKwork ? "Kwork.ru" : isFL ? "FL.ru" : "Telegram"}
                        </span>

                        <span className="font-semibold text-white">{order.author_name || order.chat_title}</span>

                        {order.author_username && !order.source_url && (
                          <a
                            href={`https://t.me/${order.author_username}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-brand-300 hover:underline"
                          >
                            @{order.author_username} <ExternalLink size={11} />
                          </a>
                        )}

                        {order.source_url && (
                          <a
                            href={order.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[11px] text-slate-300 transition hover:bg-white/10 hover:text-white"
                          >
                            <span>Открыть проект</span>
                            <ExternalLink size={10} />
                          </a>
                        )}

                        <span className="text-xs text-slate-500">из {order.chat_title}</span>
                      </div>

                      <div className="flex items-center gap-2">
                        {order.budget && (
                          <span className="rounded-lg border border-emerald-400/25 bg-emerald-400/10 px-2.5 py-0.5 text-xs font-bold text-emerald-300">
                            {order.budget}
                          </span>
                        )}
                        <span
                          className={`rounded-lg px-2 py-0.5 text-xs font-semibold ${
                            isSent
                              ? "border border-emerald-400/30 bg-emerald-400/15 text-emerald-300"
                              : isSkipped
                                ? "border border-slate-700 bg-slate-800 text-slate-400"
                                : "border border-amber-400/30 bg-amber-400/15 text-amber-300 animate-pulse"
                          }`}
                        >
                          {isSent
                            ? "✓ Отклик отправлен"
                            : isSkipped
                              ? "Пропущен"
                              : countdown
                                ? `⏳ Отправка через ${countdown}`
                                : "В очереди (~10 мин)"}
                        </span>
                      </div>
                    </div>

                    {/* Raw Order Text */}
                    <div className="mt-3 rounded-xl border border-white/[0.05] bg-[#1a1a1a] p-3 text-xs leading-relaxed text-slate-300">
                      <p className="font-semibold text-slate-400 mb-1">Задача заказчика:</p>
                      {order.raw_text}
                    </div>

                    {/* AI Generated Response */}
                    {order.response_text && (
                      <div className="mt-3 rounded-xl border border-brand-500/20 bg-brand-500/[0.04] p-3.5">
                        <div className="flex items-center justify-between text-xs text-brand-300 font-semibold mb-1.5">
                          <span className="flex items-center gap-1.5">
                            <Bot size={13} /> Персональный вежливый отклик:
                          </span>
                          <button
                            onClick={() => copyText(order.id, order.response_text || "")}
                            className="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-white"
                          >
                            {copiedId === order.id ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
                            Копировать
                          </button>
                        </div>
                        <p className="text-xs leading-relaxed text-slate-200">{order.response_text}</p>
                      </div>
                    )}

                    {/* Order Footer & Actions */}
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.05] pt-3 text-xs text-slate-500">
                      <span className="flex items-center gap-1.5">
                        <Clock size={12} /> Обнаружен: {formatDate(order.created_at)}
                      </span>

                      {isPending && (
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleSkip(order.id)}
                            className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-400 hover:bg-white/5 hover:text-white"
                          >
                            Пропустить
                          </button>
                          <button
                            onClick={() => handleSendNow(order.id)}
                            className="rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-600 shadow-md shadow-brand-500/20"
                          >
                            Отправить прямо сейчас
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
          )}
        </div>
      )}

      {/* Tab: Channel Auto-Blogger */}
      {tab === "blog" && (
        <ChannelAutoBlogView showToast={showToast} />
      )}

      {/* Tab: Neuro-commenting */}
      {tab === "comments" && (
        <NeuroCommentingView showToast={showToast} />
      )}

      {/* Tab: Chat Member Scraper */}
      {tab === "scraper" && (
        <ChatScrapingView
          showToast={showToast}
          onGoToStories={() => {
            triggerHaptic("light");
            setTab("stories");
          }}
        />
      )}

      {/* Tab: Stories Masslooking */}
      {tab === "stories" && (
        <StoriesMasslookingView
          showToast={showToast}
          onGoToScraper={() => {
            triggerHaptic("light");
            setTab("scraper");
          }}
        />
      )}

      {/* Tab: Promo Broadcasts Feed */}
      {tab === "promo" && (
        <div className="space-y-4">
          {/* Portfolio Screenshot Hero Card */}
          <div className="rounded-2xl border border-white/10 bg-[#161616] p-4 text-xs text-slate-300">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-2.5">
              <div className="flex items-center gap-2">
                <ImageIcon size={16} className="text-brand-400" />
                <span className="font-semibold text-white">Скриншот первой страницы портфолио</span>
                <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-400 font-medium">✓ Фото-пост (без плашек)</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    triggerHaptic("light");
                    setSettingsTab("autopost");
                    setShowSettings(true);
                  }}
                  className="btn-secondary text-[11px] py-1 px-2.5 flex items-center gap-1.5"
                  title="Настройки параметров автопосева"
                >
                  <Settings size={12} />
                  <span>Настройки автопосева</span>
                </button>
                <button
                  onClick={handleRefreshScreenshot}
                  disabled={refreshingScreenshot}
                  className="btn-secondary text-[11px] py-1 px-2.5 flex items-center gap-1.5"
                >
                  <RefreshCw size={12} className={refreshingScreenshot ? "animate-spin" : ""} />
                  {refreshingScreenshot ? "Снимок делается..." : "Обновить скриншот с сайта"}
                </button>
              </div>
            </div>
            <p className="text-[11px] text-slate-400 mb-3 leading-relaxed">
              Все посты в Telegram отправляются как фото первого экрана вашего сайта (2560x1600 Retina) с текстом в подписи. Больше никаких уродливых ссылочных плашек Telegram.
            </p>
            <div className="relative aspect-[16/9] w-full max-w-md overflow-hidden rounded-xl border border-white/10 bg-black/40 shadow-inner">
              <img
                src={`/api/telegram/portfolio-screenshot?v=${screenshotVersion}`}
                alt="Первая страница портфолио"
                className="w-full h-full object-cover object-top"
                onError={(e) => {
                  (e.target as HTMLImageElement).src = "https://iad.microlink.io/ZGGmB0GX1dEwZHyDj_RBkCg2cF2BiYd5XVbC6kYrCWm67gTCECtgf55jXrSp4nC_9kEAXPN1xV_zsBGtTT20Bg.png";
                }}
              />
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-[#161616] p-4 text-xs text-slate-400 leading-relaxed">
            <span className="font-semibold text-white">Автопостинг и ротация визиток:</span> в каждом канале действует свой таймер (кулдаун), а для каждого канала можно задать индивидуальный текст или доверить уникальную генерацию нейросети.
          </div>

          {broadcasts.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-white/10 p-10 text-center">
              <Share2 size={32} className="mx-auto text-slate-600" />
              <p className="mt-3 text-sm font-semibold text-slate-300">Пока не отправлено ни одной визитки</p>
              <p className="mt-1 text-xs text-slate-500">
                Нажмите «Сгенерировать и отправить вариант» или настройте автопостинг во вкладке «Каналы».
              </p>
            </div>
          ) : (
            broadcasts.map((b) => (
              <div key={b.id} className="rounded-2xl border border-white/10 bg-[#161616] p-5 shadow-lg">
                <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                  <span className="font-semibold text-white">
                    Канал / Чат: {b.chat_title} ({b.chat_id})
                  </span>
                  <span>{formatDate(b.created_at)}</span>
                </div>
                <div className="rounded-xl border border-white/[0.05] bg-[#1a1a1a] p-3.5 text-xs leading-relaxed text-slate-200 whitespace-pre-line">
                  {b.message_text}
                </div>
                <div className="mt-3 flex items-center justify-between text-[11px] text-slate-500">
                  <span className="font-mono">Ссылка: {b.portfolio_url}</span>
                  <span className="text-emerald-400 font-semibold">✓ Опубликовано</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 3: Channels & Chats Management */}
      {tab === "chats" && (
        <div className="space-y-4">
          {/* TGStat Pro Discovery Banner */}
          <div className="relative overflow-hidden rounded-2xl border border-violet-500/30 bg-gradient-to-r from-violet-950/40 via-[#1F1E2E] to-brand-950/30 p-4 text-xs shadow-lg">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-violet-600/20 border border-violet-500/40 text-violet-300">
                  <Sparkles size={18} className="text-amber-400" />
                </div>
                <div>
                  <h4 className="font-bold text-white flex items-center gap-2">
                    Авто-поиск целевых чатов через TGStat
                    <span className="rounded-full bg-violet-500/20 px-1.5 py-0.2 text-[10px] text-violet-300 font-semibold border border-violet-500/30">
                      PRO
                    </span>
                  </h4>
                  <p className="text-slate-400 text-[11px] mt-0.5">
                    Находите живые супергруппы по ключевым словам («фриланс заказы», «веб-разработка», «дизайн») и добавляйте в радар в 1 клик
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  triggerHaptic("medium");
                  setShowTGStatModal(true);
                }}
                className="btn-primary text-xs shrink-0 py-1.5 px-3 bg-gradient-to-r from-violet-600 to-brand-500 hover:from-violet-500 hover:to-brand-400 shadow-md shadow-violet-900/40 flex items-center gap-1.5"
              >
                <Search size={12} />
                <span>Найти чаты в TGStat</span>
              </button>
            </div>
          </div>

          {/* Subfilter */}
          <div className="flex items-center gap-2 border-b border-white/10 pb-3 text-xs">
            <span className="text-slate-400 mr-2">Фильтр:</span>
            <button
              onClick={() => setChatFilter("all")}
              className={`rounded-lg px-2.5 py-1 font-semibold transition ${
                chatFilter === "all" ? "bg-brand-500 text-white" : "bg-white/[0.04] text-slate-400 hover:text-white"
              }`}
            >
              Все ({chats.length})
            </button>
            <button
              onClick={() => setChatFilter("orders")}
              className={`rounded-lg px-2.5 py-1 font-semibold transition ${
                chatFilter === "orders" ? "bg-brand-500 text-white" : "bg-white/[0.04] text-slate-400 hover:text-white"
              }`}
            >
              Поиск заказов ({chats.filter((c) => c.kind === "orders" || c.kind === "both").length})
            </button>
            <button
              onClick={() => setChatFilter("promo")}
              className={`rounded-lg px-2.5 py-1 font-semibold transition ${
                chatFilter === "promo" ? "bg-brand-500 text-white" : "bg-white/[0.04] text-slate-400 hover:text-white"
              }`}
            >
              Автопостинг промо ({chats.filter((c) => c.kind === "promo" || c.kind === "both").length})
            </button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {filteredChats.map((c) => {
              const isPromoEligible = c.kind === "promo" || c.kind === "both";
              return (
                <div
                  key={c.id}
                  className="flex flex-col justify-between rounded-xl border border-white/10 bg-[#161616] p-4 shadow-md transition hover:border-white/20"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-bold text-white">{c.title}</p>
                        <a
                          href={`https://t.me/${c.chat_id.replace("@", "")}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-brand-300 hover:underline inline-flex items-center gap-1"
                        >
                          {c.chat_id} <ExternalLink size={10} />
                        </a>
                      </div>

                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleDeleteChat(c.id)}
                          className="icon-btn text-rose-400 hover:bg-rose-400/10 p-1.5"
                          title="Удалить чат"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>

                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <span className="rounded bg-white/[0.05] px-2 py-0.5 text-[10px] text-slate-300 font-semibold uppercase">
                        {c.kind === "orders" ? "Только заказы" : c.kind === "promo" ? "Только промо" : "Заказы + Промо"}
                      </span>

                      {isPromoEligible && (
                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                            c.auto_post_enabled
                              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                              : "bg-white/[0.04] text-slate-500"
                          }`}
                        >
                          {c.auto_post_enabled ? `Автопост: каждые ${c.cooldown_minutes} мин` : "Автопост: выключен"}
                        </span>
                      )}
                    </div>

                    {/* Custom text preview */}
                    {isPromoEligible && (
                      <div className="mt-2.5 rounded-lg border border-white/[0.05] bg-[#1a1a1a] p-2 text-[11px] text-slate-400">
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-medium text-slate-300">Текст публикации:</span>
                          <button
                            onClick={() => handleOpenEditCustomText(c)}
                            className="inline-flex items-center gap-1 text-[10px] text-brand-400 hover:underline"
                          >
                            <Edit3 size={10} /> Изменить
                          </button>
                        </div>
                        <p className="line-clamp-2 italic text-slate-300">
                          {c.custom_text || "✨ Автогенерация уникального текста через AI"}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Channel Controls */}
                  {isPromoEligible && (
                    <div className="mt-4 border-t border-white/[0.06] pt-3 flex flex-wrap items-center justify-between gap-2 text-xs">
                      <div className="flex items-center gap-2">
                        {/* Auto-post toggle */}
                        <button
                          onClick={() => handleToggleChatAutoPost(c)}
                          className={`rounded-lg px-2.5 py-1 text-[11px] font-semibold transition ${
                            c.auto_post_enabled
                              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                              : "border border-white/10 bg-white/[0.03] text-slate-400 hover:text-white"
                          }`}
                        >
                          {c.auto_post_enabled ? "В автопостинге" : "+ Включить автопост"}
                        </button>

                        {/* Cooldown selector */}
                        <select
                          value={c.cooldown_minutes || 120}
                          onChange={(e) => handleChangeCooldown(c, Number(e.target.value))}
                          className="rounded-lg border border-white/10 bg-black/40 px-2 py-1 text-[11px] text-slate-300 focus:outline-none"
                        >
                          {COOLDOWN_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              КД: {opt.label}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-slate-500">
                          {c.auto_post_enabled ? formatNextPost(c.next_post_at) : ""}
                        </span>
                        <button
                          onClick={() => handlePostNowToChat(c.id, c.title)}
                          className="rounded-lg bg-white/[0.06] hover:bg-brand-500 hover:text-white px-2.5 py-1 text-[11px] font-semibold text-slate-300 transition"
                          title="Опубликовать в этот канал прямо сейчас"
                        >
                          Пост сейчас 🚀
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Edit Custom Text Modal */}
      {editingChat && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#161616] p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Edit3 size={15} className="text-brand-400" /> Текст для «{editingChat.title}»
              </h3>
              <button onClick={() => setEditingChat(null)} className="text-slate-400 hover:text-white">
                <X size={16} />
              </button>
            </div>

            <div className="mt-4 space-y-3">
              <p className="text-xs text-slate-400">
                Задайте собственный индивидуальный текст для этого канала. Переменная{" "}
                <code className="text-brand-300">{"{portfolio}"}</code> автоматически заменяется на вашу ссылку портфолио.
                Если оставить поле пустым — нейросеть будет генерировать уникальные варианты перед каждой публикацией.
              </p>

              <textarea
                rows={6}
                value={customTextDraft}
                onChange={(e) => setCustomTextDraft(e.target.value)}
                placeholder="Оставьте пустым для автогенерации AI, или введите свой текст поста..."
                className="input font-mono text-xs leading-relaxed"
              />

              <div className="flex justify-between items-center text-[11px] text-slate-500">
                <button
                  type="button"
                  onClick={() =>
                    setCustomTextDraft(
                      "⚡️ Разработка современных сайтов, лендингов и Telegram Mini Apps под ключ.\n\nПортфолио проектов: {portfolio}\nСвязь: @loves_kyni"
                    )
                  }
                  className="text-brand-400 hover:underline"
                >
                  Вставить шаблон
                </button>
                <span>{customTextDraft.length} символов</span>
              </div>
            </div>

            <div className="mt-5 flex justify-end gap-2 border-t border-white/10 pt-4">
              <button onClick={() => setEditingChat(null)} className="btn-ghost text-xs">
                Отмена
              </button>
              <button
                onClick={handleSaveCustomText}
                disabled={savingChatText}
                className="btn-primary text-xs"
              >
                {savingChatText ? <Spinner size={13} /> : <Check size={13} />}
                Сохранить текст
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Chat Modal */}
      {showAddChat && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-[#181818] p-5 shadow-2xl">
            <h3 className="text-base font-bold text-white mb-4">Добавить канал или чат на радар</h3>

            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-300">Юзернейм или ссылка (@freelance_chat)</label>
                <input
                  value={newChatId}
                  onChange={(e) => setNewChatId(e.target.value)}
                  placeholder="@chat_name"
                  className="input"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-300">Название канала / чата</label>
                <input
                  value={newChatTitle}
                  onChange={(e) => setNewChatTitle(e.target.value)}
                  placeholder="Биржа веб-дизайна"
                  className="input"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-300">Назначение</label>
                <select value={newChatKind} onChange={(e) => setNewChatKind(e.target.value)} className="input">
                  <option value="both">И перехват заказов, и автопосев визитки</option>
                  <option value="orders">Только перехват заказов</option>
                  <option value="promo">Только автопосев визитки</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-300">Кулдаун между автопостами</label>
                <select
                  value={newChatCooldown}
                  onChange={(e) => setNewChatCooldown(Number(e.target.value))}
                  className="input"
                >
                  {COOLDOWN_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-5 flex justify-end gap-2 border-t border-white/10 pt-4">
              <button onClick={() => setShowAddChat(false)} className="btn-ghost text-xs">
                Отмена
              </button>
              <button onClick={handleAddChat} disabled={addingChat} className="btn-primary text-xs">
                {addingChat ? <Spinner size={13} /> : <Plus size={13} />}
                Добавить канал
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TGStat Discovery Modal */}
      <TGStatModal
        open={showTGStatModal}
        onClose={() => setShowTGStatModal(false)}
        onSuccess={loadData}
        showToast={showToast}
      />
    </div>
  );
}
