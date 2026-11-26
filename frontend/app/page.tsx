"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  Download,
  FileSpreadsheet,
  FileText,
  Filter,
  LayoutGrid,
  List,
  MessageCircle,
  Phone,
  Plus,
  Search,
  Send,
  SlidersHorizontal,
  Sparkles,
  Star,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Demo, Lead, LeadFilters, LeadStatus, Meta, ParseJob, ParseRequest, SortKey, Stats } from "@/lib/types";
import { SOURCE_LABELS, STATUS_META, WEBSITE_STATUS_META, formatNumber, getLeadScore, getTelegramUrl, getWebsiteStatus, getWhatsAppUrl, phoneDigits } from "@/lib/utils";
import AccountsView from "@/components/AccountsView";
import BillingModal from "@/components/BillingModal";
import BottomNav, { type NavTab } from "@/components/BottomNav";
import DemoModal from "@/components/DemoModal";
import InboxView from "@/components/InboxView";
import JobBanner from "@/components/JobBanner";
import LeadCard from "@/components/LeadCard";
import LeadDrawer from "@/components/LeadDrawer";
import LLMSelectorModal from "@/components/LLMSelectorModal";
import OutreachModal from "@/components/OutreachModal";
import ParseModal from "@/components/ParseModal";
import Sidebar from "@/components/Sidebar";
import StatsRow from "@/components/StatsRow";
import StyleSelectModal from "@/components/StyleSelectModal";
import TelegramRadarView from "@/components/TelegramRadarView";
import Topbar from "@/components/Topbar";
import { initTelegramWebApp, triggerHaptic } from "@/lib/telegram";
import {
  EmptyState,
  SkeletonCard,
  ToastStack,
  type ToastItem,
  type ToastVariant,
} from "@/components/ui";

const EMPTY_FILTERS: LeadFilters = {
  cities: [],
  categories: [],
  statuses: [],
  sources: [],
  onlyNoWebsite: false,
  onlyWeakOrBroken: false,
  onlySocial: false,
  onlyPhone: false,
  minRating: null,
};

const PAGE_SIZE = 24;

export default function HomePage() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);
  const [mainView, setMainView] = useState<"leads" | "telegram" | "accounts" | "inbox">("leads");
  const [radarSubTab, setRadarSubTab] = useState<"orders" | "blog">("orders");
  const [pricingOpen, setPricingOpen] = useState(false);
  const [billingOpen, setBillingOpen] = useState(false);
  const [outreachOpen, setOutreachOpen] = useState(false);

  useEffect(() => {
    initTelegramWebApp();
  }, []);

  const [filters, setFilters] = useState<LeadFilters>(EMPTY_FILTERS);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("new");
  const [viewMode, setViewMode] = useState<"table" | "grid">("table");

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);
  const [parseOpen, setParseOpen] = useState(false);
  const [drawerLead, setDrawerLead] = useState<Lead | null>(null);
  const [styleSelectLead, setStyleSelectLead] = useState<Lead | null>(null);
  const [demoModal, setDemoModal] = useState<{ demo: Demo; lead: Lead } | null>(null);
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [enrichingId, setEnrichingId] = useState<string | null>(null);

  const [job, setJob] = useState<ParseJob | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const toastId = useRef(0);

  const showToast = useCallback((message: string, variant: ToastVariant = "info") => {
    const id = ++toastId.current;
    setToasts((previous) => [...previous.slice(-3), { id, message, variant }]);
    window.setTimeout(() => {
      setToasts((previous) => previous.filter((item) => item.id !== id));
    }, 4500);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((previous) => previous.filter((item) => item.id !== id));
  }, []);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (exportRef.current && !exportRef.current.contains(event.target as Node)) {
        setExportOpen(false);
      }
    }
    if (exportOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [exportOpen]);

  const refreshMetaStats = useCallback(async () => {
    try {
      const [nextMeta, nextStats] = await Promise.all([api.meta(), api.stats()]);
      setMeta(nextMeta);
      setStats(nextStats);
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Не удалось обновить статистику", "error");
    }
  }, [showToast]);

  useEffect(() => {
    void refreshMetaStats();
  }, [refreshMetaStats]);

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedSearch(search), 350);
    return () => window.clearTimeout(timeout);
  }, [search]);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    setLoading(true);

    api
      .listLeads(filters, debouncedSearch, sort, 1, PAGE_SIZE, controller.signal)
      .then((data) => {
        if (cancelled) return;
        setLeads(data.items);
        setTotal(data.total);
        setPage(1);
      })
      .catch((error) => {
        if (cancelled || (error instanceof DOMException && error.name === "AbortError")) return;
        showToast(error instanceof Error ? error.message : "Не удалось загрузить лиды", "error");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [filters, debouncedSearch, sort, refreshTick, showToast]);

  useEffect(() => {
    if (!activeJobId) return;
    let cancelled = false;
    let timer: number;

    const tick = async () => {
      try {
        const current = await api.getJob(activeJobId);
        if (cancelled) return;
        setJob(current);

        if (current.status === "done") {
          setActiveJobId(null);
          showToast(`Сбор завершён: сохранено ${current.total_saved} лидов`, "success");
          void refreshMetaStats();
          setRefreshTick((value) => value + 1);
          return;
        }
        if (current.status === "failed") {
          setActiveJobId(null);
          showToast(current.error ?? "Не удалось собрать лиды", "error");
          void refreshMetaStats();
          return;
        }
      } catch (error) {
        if (cancelled) return;
        showToast(error instanceof Error ? error.message : "Ошибка при получении статуса задачи", "error");
      }
      if (!cancelled) timer = window.setTimeout(tick, 1500);
    };

    timer = window.setTimeout(tick, 700);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [activeJobId, refreshMetaStats, showToast]);

  const updateFilters = (patch: Partial<LeadFilters>) => {
    setFilters((previous) => ({ ...previous, ...patch }));
  };

  const resetFilters = () => {
    setFilters(EMPTY_FILTERS);
    setSearch("");
    setSort("new");
  };

  const handleParse = async (payload: ParseRequest) => {
    const created = await api.startParse(payload);
    setJob(created);
    setActiveJobId(created.id);
    showToast("Задача сбора запущена", "info");
  };

  const handleRefresh = () => {
    setRefreshing(true);
    setRefreshTick((value) => value + 1);
    void refreshMetaStats();
    window.setTimeout(() => setRefreshing(false), 800);
  };

  const handleLoadMore = async () => {
    const nextPage = page + 1;
    setLoadingMore(true);
    try {
      const data = await api.listLeads(filters, debouncedSearch, sort, nextPage, PAGE_SIZE);
      setLeads((previous) => [...previous, ...data.items]);
      setPage(nextPage);
      setTotal(data.total);
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Не удалось загрузить ещё", "error");
    } finally {
      setLoadingMore(false);
    }
  };

  const handleStatus = async (lead: Lead, status: LeadStatus) => {
    try {
      const updated = await api.updateLead(lead.id, { status });
      setLeads((previous) => previous.map((item) => (item.id === updated.id ? updated : item)));
      setDrawerLead((previous) => (previous?.id === updated.id ? updated : previous));
      void refreshMetaStats();
      showToast(`Статус: ${STATUS_META[status].label}`, "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Не удалось обновить статус", "error");
    }
  };

  const handleEnrich = async (lead: Lead) => {
    setEnrichingId(lead.id);
    try {
      const updated = await api.enrichLead(lead.id);
      setLeads((previous) => previous.map((item) => (item.id === updated.id ? updated : item)));
      setDrawerLead((previous) => (previous?.id === updated.id ? updated : previous));
      showToast("Контакты обновлены", "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Не удалось обогатить контакты", "error");
    } finally {
      setEnrichingId(null);
    }
  };

  const handleGenerateDemo = async (lead: Lead, styleId?: string) => {
    // If no explicit style chosen yet, open the Style Selection modal
    if (!styleId) {
      setStyleSelectLead(lead);
      return;
    }

    setGeneratingId(lead.id);
    try {
      const demo = await api.generateDemo(lead.id, { style: styleId });
      const updated = { ...lead, demo_id: demo.id };
      setLeads((previous) => previous.map((item) => (item.id === lead.id ? { ...item, demo_id: demo.id } : item)));
      setDrawerLead((previous) => (previous?.id === lead.id ? updated : previous));
      setStyleSelectLead(null);
      setDemoModal({ demo, lead: updated });
      void refreshMetaStats();
      showToast("Демо-лендинг готов", "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Не удалось сгенерировать демо", "error");
    } finally {
      setGeneratingId(null);
    }
  };

  const handleOpenDemo = async (lead: Lead) => {
    if (!lead.demo_id) {
      setStyleSelectLead(lead);
      return;
    }
    setGeneratingId(lead.id);
    try {
      const demo = await api.getDemo(lead.demo_id);
      setDemoModal({ demo, lead });
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Не удалось открыть демо", "error");
    } finally {
      setGeneratingId(null);
    }
  };

  const handleDemoUpdated = useCallback(
    (demo: Demo) => {
      setDemoModal((previous) =>
        previous ? { demo, lead: { ...previous.lead, demo_id: demo.id } } : previous,
      );
      setLeads((previous) =>
        previous.map((item) => (item.id === demo.lead_id ? { ...item, demo_id: demo.id } : item)),
      );
      setDrawerLead((previous) =>
        previous?.id === demo.lead_id ? { ...previous, demo_id: demo.id } : previous,
      );
    },
    [],
  );

  const handleDemoChanged = useCallback((demoId: string, leadId: string) => {
    setLeads((previous) =>
      previous.map((item) => (item.id === leadId ? { ...item, demo_id: demoId } : item)),
    );
    setDrawerLead((previous) =>
      previous?.id === leadId ? { ...previous, demo_id: demoId } : previous,
    );
  }, []);

  const handleDemoFromCard = (lead: Lead) => {
    if (lead.demo_id) {
      void handleOpenDemo(lead);
    } else {
      void handleGenerateDemo(lead);
    }
  };

  const activeChips: Array<{ key: string; label: string; remove: () => void }> = [];
  filters.cities.forEach((city) =>
    activeChips.push({
      key: `city-${city}`,
      label: city,
      remove: () => updateFilters({ cities: filters.cities.filter((value) => value !== city) }),
    }),
  );
  filters.categories.forEach((category) =>
    activeChips.push({
      key: `cat-${category}`,
      label: category,
      remove: () => updateFilters({ categories: filters.categories.filter((value) => value !== category) }),
    }),
  );
  filters.statuses.forEach((status) =>
    activeChips.push({
      key: `status-${status}`,
      label: STATUS_META[status as LeadStatus]?.label ?? status,
      remove: () => updateFilters({ statuses: filters.statuses.filter((value) => value !== status) }),
    }),
  );
  filters.sources.forEach((source) =>
    activeChips.push({
      key: `source-${source}`,
      label: SOURCE_LABELS[source] ?? source,
      remove: () => updateFilters({ sources: filters.sources.filter((value) => value !== source) }),
    }),
  );
  if (filters.onlyNoWebsite)
    activeChips.push({ key: "no-site", label: "Без сайта", remove: () => updateFilters({ onlyNoWebsite: false }) });
  if (filters.onlySocial)
    activeChips.push({ key: "social", label: "С соцсетями", remove: () => updateFilters({ onlySocial: false }) });
  if (filters.onlyPhone)
    activeChips.push({ key: "phone", label: "С телефоном", remove: () => updateFilters({ onlyPhone: false }) });
  if (filters.minRating !== null)
    activeChips.push({
      key: "rating",
      label: `Рейтинг ${filters.minRating}+`,
      remove: () => updateFilters({ minRating: null }),
    });

  const activeCount = activeChips.length;

  const sidebar = (
    <Sidebar
      meta={meta}
      filters={filters}
      onChange={updateFilters}
      onReset={resetFilters}
      onClose={() => setSidebarOpen(false)}
    />
  );

  const currentBottomTab: NavTab =
    mainView === "leads"
      ? "leads"
      : mainView === "accounts"
      ? "accounts"
      : mainView === "inbox"
      ? "inbox"
      : "telegram";

  const handleBottomTabSelect = (tab: NavTab) => {
    if (tab === "leads") {
      setMainView("leads");
    } else if (tab === "telegram") {
      setRadarSubTab("orders");
      setMainView("telegram");
    } else if (tab === "accounts") {
      setMainView("accounts");
    } else if (tab === "inbox") {
      setMainView("inbox");
    } else if (tab === "pricing") {
      setBillingOpen(true);
    }
  };

  return (
    <div className="min-h-screen">
      <div className="flex">
        <div className="sticky top-0 z-30 hidden h-screen lg:block">{sidebar}</div>

        <div className="min-w-0 flex-1">
          <Topbar
            onParse={() => setParseOpen(true)}
            onToggleSidebar={() => setSidebarOpen(true)}
            onRefresh={handleRefresh}
            refreshing={refreshing}
            currentView={mainView}
            onViewChange={setMainView}
            onOpenBilling={() => setBillingOpen(true)}
          />

          <main className="mx-auto max-w-[1640px] px-4 py-6 pb-24 lg:px-8 lg:py-8 lg:pb-8">
            {mainView === "telegram" ? (
              <TelegramRadarView showToast={showToast} initialTab={radarSubTab} />
            ) : mainView === "accounts" ? (
              <AccountsView showToast={showToast} />
            ) : mainView === "inbox" ? (
              <InboxView showToast={showToast} />
            ) : (
              <>
                {job ? <JobBanner job={job} onDismiss={() => setJob(null)} /> : null}

                <StatsRow stats={stats} meta={meta} onParse={() => setParseOpen(true)} />

            <div className="mt-6 flex flex-col gap-3">
              <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div className="flex items-center gap-2.5">
                  <h1 className="text-xl font-semibold text-[#F3F4F6] tracking-tight">
                    База лидов
                  </h1>
                  <span className="font-mono text-xs text-[#9CA3AF] tabular-nums tracking-tight rounded-md bg-[#242731] border border-white/[0.06] px-2 py-0.5">
                    {formatNumber(total)}
                  </span>
                  {meta && (
                    <span className="text-xs text-[#6B7280] hidden sm:inline">
                      · <span className="font-mono tabular-nums tracking-tight">{formatNumber(meta.no_website)}</span> без сайта
                    </span>
                  )}
                  {debouncedSearch ? (
                    <span className="text-xs text-[#6B7280] hidden md:inline">
                      · «{debouncedSearch}»
                    </span>
                  ) : null}
                </div>

                <div className="flex items-center gap-2">
                  {/* Поиск */}
                  <div className="relative min-w-[170px] flex-1 sm:w-64 sm:flex-none">
                    <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#6B7280]" />
                    <input
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                      placeholder="Поиск по базе..."
                      className="input !h-9 pl-9 pr-8 text-xs bg-[#1A1C23] border-white/[0.07] text-[#F3F4F6]"
                    />
                    {search ? (
                      <button
                        onClick={() => setSearch("")}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#6B7280] transition hover:text-[#F3F4F6]"
                        aria-label="Очистить поиск"
                      >
                        <X size={13} />
                      </button>
                    ) : null}
                  </div>

                  {/* Сортировка */}
                  <div className="relative">
                    <select
                      value={sort}
                      onChange={(event) => setSort(event.target.value as SortKey)}
                      className="h-9 appearance-none rounded-lg border border-white/[0.07] bg-[#1A1C23] pl-3 pr-8 text-xs font-medium text-[#F3F4F6] outline-none transition hover:border-white/20"
                    >
                      <option value="new" className="bg-[#1A1C23]">Сначала новые</option>
                      <option value="rating" className="bg-[#1A1C23]">По рейтингу</option>
                      <option value="reviews" className="bg-[#1A1C23]">По отзывам</option>
                      <option value="name" className="bg-[#1A1C23]">По названию</option>
                    </select>
                    <ChevronDown size={13} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[#6B7280]" />
                  </div>

                  {/* Компактный Экспорт [ ↓ ] с дропдауном */}
                  <div className="relative" ref={exportRef}>
                    <button
                      onClick={() => setExportOpen((prev) => !prev)}
                      className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border transition ${
                        exportOpen
                          ? "border-[#8B5CF6]/50 bg-[rgba(139,92,246,0.14)] text-[#C4B5FD]"
                          : "border-white/[0.07] bg-[#1A1C23] text-[#9CA3AF] hover:border-white/20 hover:text-[#F3F4F6]"
                      }`}
                      title="Экспорт базы (CSV / Excel)"
                      aria-label="Экспорт базы"
                    >
                      <Download size={14} />
                    </button>

                    {exportOpen && (
                      <div className="absolute right-0 top-full z-50 mt-1.5 w-44 rounded-xl border border-white/[0.08] bg-[#1A1C23] p-1.5 shadow-[0_10px_30px_rgba(0,0,0,0.5)] backdrop-blur-xl animate-fadeIn">
                        <button
                          onClick={() => {
                            setExportOpen(false);
                            window.open(api.exportUrl(filters, debouncedSearch, sort, "csv"), "_blank");
                          }}
                          className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-[#9CA3AF] transition hover:bg-[#242731] hover:text-[#F3F4F6]"
                        >
                          <FileText size={13} className="text-[#8B5CF6]" />
                          <span>Экспорт в CSV</span>
                        </button>
                        <button
                          onClick={() => {
                            setExportOpen(false);
                            window.open(api.exportUrl(filters, debouncedSearch, sort, "xlsx"), "_blank");
                          }}
                          className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-[#9CA3AF] transition hover:bg-[#242731] hover:text-[#F3F4F6]"
                        >
                          <FileSpreadsheet size={13} className="text-[#10B981]" />
                          <span>Экспорт в Excel (.xlsx)</span>
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Переключатель вида: Таблица / Карточки */}
                  <div className="hidden md:flex items-center rounded-lg border border-[#22252A] bg-[#121417] p-0.5">
                    <button
                      onClick={() => setViewMode("table")}
                      className={`inline-flex h-7 w-7 items-center justify-center rounded-md transition ${
                        viewMode === "table" ? "bg-[#22252A] text-white" : "text-[#71717A] hover:text-white"
                      }`}
                      title="Табличный вид (CRM)"
                    >
                      <List size={14} />
                    </button>
                    <button
                      onClick={() => setViewMode("grid")}
                      className={`inline-flex h-7 w-7 items-center justify-center rounded-md transition ${
                        viewMode === "grid" ? "bg-[#22252A] text-white" : "text-[#71717A] hover:text-white"
                      }`}
                      title="Карточки"
                    >
                      <LayoutGrid size={14} />
                    </button>
                  </div>

                  {/* Компактная кнопка «Касание по выборке» */}
                  <button
                    onClick={() => {
                      triggerHaptic("medium");
                      setOutreachOpen(true);
                    }}
                    className="btn-primary !h-9 !px-3.5 shrink-0"
                    title="Запустить мягкий аутрич по текущей выборке"
                  >
                    <Send size={13} />
                    <span className="hidden sm:inline">Рассылка</span>
                    <span className="font-mono text-[11px] opacity-70">{formatNumber(total)}</span>
                  </button>

                  {/* Компактная квадратная кнопка Фильтры в одну строку с инпутом */}
                  <button
                    onClick={() => setSidebarOpen(true)}
                    className="relative inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[#22252A] bg-[#121417] text-[#A1A1AA] transition hover:border-[#32363E] hover:text-white lg:hidden"
                    title="Фильтры"
                    aria-label="Фильтры"
                  >
                    <SlidersHorizontal size={14} />
                    {activeCount ? (
                      <span className="absolute -top-1 -right-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-[#F4F4F5] px-1 font-mono text-[9px] font-bold text-[#09090B] tabular-nums">
                        {activeCount}
                      </span>
                    ) : null}
                  </button>
                </div>
              </div>

              {activeCount ? (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="mr-1 inline-flex items-center gap-1 text-xs text-[#6B7280]">
                    <Filter size={11} /> Фильтры:
                  </span>
                  {activeChips.map((chip) => (
                    <button
                      key={chip.key}
                      onClick={chip.remove}
                      className="inline-flex items-center gap-1 rounded-md border border-[rgba(139,92,246,0.3)] bg-[rgba(139,92,246,0.14)] px-2 py-0.5 text-xs font-medium text-[#C4B5FD] transition hover:bg-[rgba(139,92,246,0.22)]"
                    >
                      {chip.label}
                      <X size={10} />
                    </button>
                  ))}
                  <button onClick={resetFilters} className="ml-1 text-xs font-medium text-[#6B7280] transition hover:text-[#9CA3AF]">
                    Сбросить всё
                  </button>
                </div>
              ) : null}
            </div>

            <div className="mt-5">
              {loading && !leads.length ? (
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                  {Array.from({ length: 8 }).map((_, index) => (
                    <SkeletonCard key={index} />
                  ))}
                </div>
              ) : leads.length ? (
                <>
                  {viewMode === "table" ? (
                    <div className="hidden md:block overflow-hidden rounded-xl border border-[#22252A] bg-[#121417]">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-[#22252A] bg-[#16181D] text-[11px] font-medium text-[#71717A]">
                            <th className="py-2.5 pl-4 pr-3">Компания</th>
                            <th className="px-3 py-2.5">Город / Рейтинг</th>
                            <th className="px-3 py-2.5">Сайт и аудит</th>
                            <th className="px-3 py-2.5">Контакты</th>
                            <th className="px-3 py-2.5">Статус</th>
                            <th className="py-2.5 pl-3 pr-4 text-right">Действие</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#1D2025]">
                          {leads.map((lead) => {
                            const st = STATUS_META[lead.status] ?? STATUS_META.new;
                            const siteSt = getWebsiteStatus(lead);
                            const siteMeta = WEBSITE_STATUS_META[siteSt] ?? WEBSITE_STATUS_META.no_website;
                            const score = getLeadScore(lead);
                            const tg = getTelegramUrl(lead);
                            const wa = getWhatsAppUrl(lead);
                            const digits = phoneDigits(lead.phone);

                            return (
                              <tr
                                key={lead.id}
                                onClick={() => setDrawerLead(lead)}
                                className="cursor-pointer transition-colors hover:bg-[#181A20]"
                              >
                                <td className="py-3 pl-4 pr-3">
                                  <div className="flex items-center gap-2">
                                    <span className="font-mono text-[11px] font-semibold text-[#A1A1AA] tabular-nums">
                                      {score.toFixed(1)}
                                    </span>
                                    <div className="min-w-0">
                                      <p className="truncate font-medium text-[#F4F4F5] max-w-[260px]">{lead.name}</p>
                                      <p className="truncate text-[11px] text-[#71717A]">{lead.category || "Без категории"}</p>
                                    </div>
                                  </div>
                                </td>
                                <td className="px-3 py-3 whitespace-nowrap">
                                  <p className="text-[#D4D4D8]">{lead.city}</p>
                                  <p className="mt-0.5 flex items-center gap-1 text-[11px] text-[#71717A]">
                                    <Star size={10} className="fill-amber-400 text-amber-400" />
                                    <span className="font-mono text-[#D4D4D8]">{lead.rating ? lead.rating.toFixed(1) : "—"}</span>
                                    <span className="font-mono">({lead.reviews_count})</span>
                                  </p>
                                </td>
                                <td className="px-3 py-3">
                                  <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-medium ${siteMeta.badge}`}>
                                    <span className={`h-1.5 w-1.5 rounded-full ${siteMeta.dot}`} />
                                    {siteMeta.label}
                                  </span>
                                  {lead.site_audit?.issues?.[0] ? (
                                    <p className="mt-1 truncate max-w-[220px] text-[11px] text-amber-400/90">
                                      {lead.site_audit.issues[0]}
                                    </p>
                                  ) : lead.website_url ? (
                                    <p className="mt-1 truncate max-w-[220px] text-[11px] text-[#71717A]">
                                      {lead.website_url.replace(/^https?:\/\//, "")}
                                    </p>
                                  ) : null}
                                </td>
                                <td className="px-3 py-3 whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                                  <div className="flex items-center gap-1.5">
                                    {digits ? (
                                      <a
                                        href={`tel:${digits}`}
                                        className="inline-flex items-center gap-1 rounded-md border border-[#22252A] bg-[#16181D] px-2 py-1 font-mono text-[11px] text-[#D4D4D8] hover:border-[#32363E] hover:text-white"
                                      >
                                        <Phone size={10} className="text-emerald-400" />
                                        {lead.phone}
                                      </a>
                                    ) : (
                                      <span className="text-[11px] text-[#52525B]">—</span>
                                    )}
                                    {wa && (
                                      <a
                                        href={wa}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-[#22252A] bg-[#16181D] text-emerald-400 hover:border-emerald-500/40"
                                        title="WhatsApp"
                                      >
                                        <MessageCircle size={12} />
                                      </a>
                                    )}
                                    {tg && (
                                      <a
                                        href={tg}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-[#22252A] bg-[#16181D] text-sky-400 hover:border-sky-500/40"
                                        title="Telegram"
                                      >
                                        <Send size={11} />
                                      </a>
                                    )}
                                  </div>
                                </td>
                                <td className="px-3 py-3 whitespace-nowrap">
                                  <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-medium ${st.badge}`}>
                                    <span className={`h-1.5 w-1.5 rounded-full ${st.dot}`} />
                                    {st.label}
                                  </span>
                                </td>
                                <td className="py-3 pl-3 pr-4 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                                  <button
                                    onClick={() => handleDemoFromCard(lead)}
                                    disabled={generatingId === lead.id}
                                    className="inline-flex items-center gap-1 rounded-md border border-[#2A2E35] bg-[#181A1F] px-2.5 py-1 text-[11px] font-medium text-[#F4F4F5] transition hover:bg-[#22252A] disabled:opacity-50"
                                  >
                                    <Sparkles size={11} />
                                    {generatingId === lead.id ? "..." : lead.demo_id ? "Демо" : "Создать демо"}
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : null}

                  <div className={`grid gap-3.5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 ${viewMode === "table" ? "md:hidden" : ""}`}>
                    {leads.map((lead) => (
                      <LeadCard
                        key={lead.id}
                        lead={lead}
                        onOpen={setDrawerLead}
                        onStatus={handleStatus}
                        onDemo={handleDemoFromCard}
                        generating={generatingId === lead.id}
                      />
                    ))}
                  </div>

                  <div className="mt-8 flex flex-col items-center gap-3">
                    <p className="text-[11px] text-slate-600">
                      Показано {leads.length} из {formatNumber(total)}
                    </p>
                    {leads.length < total ? (
                      <button onClick={handleLoadMore} disabled={loadingMore} className="btn-ghost min-w-[200px]">
                        {loadingMore ? (
                          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" />
                        ) : (
                          <Plus size={15} />
                        )}
                        Показать ещё
                      </button>
                    ) : (
                      <div className="inline-flex items-center gap-1.5 rounded-full border border-white/[0.06] bg-white/[0.02] px-3 py-1.5 text-[11px] text-slate-500">
                        <Sparkles size={11} className="text-brand-300" />
                        Это все лиды по текущим фильтрам
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <EmptyState
                  title={activeCount || debouncedSearch ? "Под фильтры ничего не подошло" : "База пока пуста"}
                  description={
                    activeCount || debouncedSearch
                      ? "Сбросьте часть фильтров или расширьте географию — и попробуйте снова."
                      : "Запустите первый сбор: выберите город и ниши, а мы найдём компании без сайта и с контактами."
                  }
                  showDemoCard={!activeCount && !debouncedSearch}
                  onStartParse={!activeCount && !debouncedSearch ? () => setParseOpen(true) : undefined}
                  action={
                    activeCount || debouncedSearch ? (
                      <div className="flex flex-wrap items-center justify-center gap-2">
                        <button onClick={resetFilters} className="btn-ghost">
                          <X size={15} /> Сбросить фильтры
                        </button>
                        <button onClick={() => setParseOpen(true)} className="btn-primary">
                          <Plus size={15} /> Собрать лиды
                        </button>
                      </div>
                    ) : null
                  }
                />
              )}
            </div>
          </>
        )}
      </main>
        </div>
      </div>

      {sidebarOpen ? (
        <div className="fixed inset-0 z-[70] lg:hidden">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm animate-fadeIn" onClick={() => setSidebarOpen(false)} />
          <div className="absolute left-0 top-0 h-full animate-fadeIn">{sidebar}</div>
        </div>
      ) : null}

      <ParseModal
        open={parseOpen}
        onClose={() => setParseOpen(false)}
        onSubmit={handleParse}
        onDirectParsed={(parsedLead, parsedDemo) => {
          setLeads((prev) => [parsedLead, ...prev.filter((item) => item.id !== parsedLead.id)]);
          setTotal((prev) => prev + 1);
          void refreshMetaStats();
          if (parsedDemo) {
            setDemoModal({ demo: parsedDemo, lead: parsedLead });
            showToast(`Организация «${parsedLead.name}» добавлена и демо готово!`, "success");
          } else {
            setDrawerLead(parsedLead);
            showToast(`Организация «${parsedLead.name}» добавлена в базу`, "success");
          }
        }}
        meta={meta}
      />

      <LeadDrawer
        lead={drawerLead}
        onClose={() => setDrawerLead(null)}
        onStatus={handleStatus}
        onGenerateDemo={handleGenerateDemo}
        onOpenDemo={handleOpenDemo}
        onEnrich={handleEnrich}
        onUpdated={(updated) => {
          setDrawerLead((previous) => (previous?.id === updated.id ? updated : previous));
          setLeads((previous) => previous.map((item) => (item.id === updated.id ? updated : item)));
        }}
        onDemoChanged={handleDemoChanged}
        generating={drawerLead ? generatingId === drawerLead.id : false}
        enriching={drawerLead ? enrichingId === drawerLead.id : false}
        showToast={showToast}
      />

      {demoModal ? (
        <DemoModal
          demo={demoModal.demo}
          lead={demoModal.lead}
          onClose={() => setDemoModal(null)}
          onDemoUpdated={handleDemoUpdated}
          showToast={showToast}
        />
      ) : null}

      {styleSelectLead ? (
        <StyleSelectModal
          lead={styleSelectLead}
          generating={generatingId === styleSelectLead.id}
          onClose={() => setStyleSelectLead(null)}
          onSelectStyle={async (styleId) => {
            await handleGenerateDemo(styleSelectLead, styleId);
          }}
        />
      ) : null}

      <ToastStack toasts={toasts} onDismiss={dismissToast} />

      <BottomNav activeTab={currentBottomTab} onSelectTab={handleBottomTabSelect} />

      <LLMSelectorModal
        isOpen={pricingOpen}
        onClose={() => setPricingOpen(false)}
      />

      <BillingModal
        isOpen={billingOpen}
        onClose={() => setBillingOpen(false)}
        showToast={showToast}
      />

      <OutreachModal
        isOpen={outreachOpen}
        onClose={() => setOutreachOpen(false)}
        leads={leads}
        showToast={showToast}
        onStarted={() => {
          showToast("Кампания аутрича запущена в фоне", "info");
        }}
      />
    </div>
  );
}
