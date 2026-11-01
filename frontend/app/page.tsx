"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  FileSpreadsheet,
  FileText,
  Filter,
  Plus,
  Search,
  SlidersHorizontal,
  Sparkles,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Demo, Lead, LeadFilters, LeadStatus, Meta, ParseJob, ParseRequest, SortKey, Stats } from "@/lib/types";
import { SOURCE_LABELS, STATUS_META, formatNumber } from "@/lib/utils";
import DemoModal from "@/components/DemoModal";
import JobBanner from "@/components/JobBanner";
import LeadCard from "@/components/LeadCard";
import LeadDrawer from "@/components/LeadDrawer";
import ParseModal from "@/components/ParseModal";
import Sidebar from "@/components/Sidebar";
import StatsRow from "@/components/StatsRow";
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
  const [mainView, setMainView] = useState<"leads" | "telegram">("leads");

  useEffect(() => {
    initTelegramWebApp();
  }, []);

  const [filters, setFilters] = useState<LeadFilters>(EMPTY_FILTERS);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("new");

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [parseOpen, setParseOpen] = useState(false);
  const [drawerLead, setDrawerLead] = useState<Lead | null>(null);
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

  const handleGenerateDemo = async (lead: Lead) => {
    setGeneratingId(lead.id);
    try {
      const demo = await api.generateDemo(lead.id);
      const updated = { ...lead, demo_id: demo.id };
      setLeads((previous) => previous.map((item) => (item.id === lead.id ? { ...item, demo_id: demo.id } : item)));
      setDrawerLead((previous) => (previous?.id === lead.id ? updated : previous));
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
      await handleGenerateDemo(lead);
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
          />

          {/* Mobile view switcher */}
          <div className="flex md:hidden items-center justify-center gap-2 border-b border-white/[0.06] bg-[#07080f] px-4 py-2">
            <button
              onClick={() => {
                triggerHaptic("light");
                setMainView("leads");
              }}
              className={`flex-1 flex items-center justify-center gap-1.5 rounded-lg py-1.5 text-xs font-semibold transition ${
                mainView === "leads"
                  ? "bg-brand-500 text-white shadow-md shadow-brand-500/25"
                  : "bg-white/[0.03] text-slate-400"
              }`}
            >
              Лиды из карт
            </button>
            <button
              onClick={() => {
                triggerHaptic("light");
                setMainView("telegram");
              }}
              className={`flex-1 flex items-center justify-center gap-1.5 rounded-lg py-1.5 text-xs font-semibold transition ${
                mainView === "telegram"
                  ? "bg-brand-500 text-white shadow-md shadow-brand-500/25"
                  : "bg-white/[0.03] text-slate-400"
              }`}
            >
              TG-Радар заказов
            </button>
          </div>

          <main className="mx-auto max-w-[1640px] px-4 py-6 lg:px-8 lg:py-8">
            {mainView === "telegram" ? (
              <TelegramRadarView showToast={showToast} />
            ) : (
              <>
                {job ? <JobBanner job={job} onDismiss={() => setJob(null)} /> : null}

                <StatsRow stats={stats} meta={meta} onParse={() => setParseOpen(true)} />

            <div className="mt-8 flex flex-col gap-4">
              <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-300">Рабочая область</p>
                  <h1 className="mt-1 flex items-center gap-3 text-2xl font-black tracking-tight text-white sm:text-[28px]">
                    База лидов
                    <span className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs font-bold text-slate-300">
                      {formatNumber(total)}
                    </span>
                  </h1>
                  <p className="mt-1 text-xs text-slate-500">
                    {meta ? `${formatNumber(meta.no_website)} без сайта из ${formatNumber(meta.total)}` : "Загружаем данные..."}
                    {debouncedSearch ? ` · поиск: «${debouncedSearch}»` : ""}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <div className="relative min-w-[220px] flex-1 sm:flex-none">
                    <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                    <input
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                      placeholder="Компания, адрес, телефон..."
                      className="input h-10 pl-9 pr-9"
                    />
                    {search ? (
                      <button
                        onClick={() => setSearch("")}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 transition hover:text-white"
                        aria-label="Очистить поиск"
                      >
                        <X size={14} />
                      </button>
                    ) : null}
                  </div>

                  <div className="relative">
                    <select
                      value={sort}
                      onChange={(event) => setSort(event.target.value as SortKey)}
                      className="h-10 appearance-none rounded-xl border border-white/10 bg-white/[0.04] pl-3 pr-9 text-xs font-semibold text-slate-300 outline-none transition hover:border-white/20 focus:border-brand-500/50"
                    >
                      <option value="new" className="bg-[#0a0c15]">Сначала новые</option>
                      <option value="rating" className="bg-[#0a0c15]">По рейтингу</option>
                      <option value="reviews" className="bg-[#0a0c15]">По отзывам</option>
                      <option value="name" className="bg-[#0a0c15]">По названию</option>
                    </select>
                    <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-500" />
                  </div>

                  <div className="flex items-center gap-1 rounded-xl border border-white/10 bg-white/[0.04] p-1">
                    <button
                      onClick={() => window.open(api.exportUrl(filters, debouncedSearch, sort, "csv"), "_blank")}
                      className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold text-slate-300 transition hover:bg-white/[0.06] hover:text-white"
                      title="Экспорт в CSV"
                    >
                      <FileText size={13} /> CSV
                    </button>
                    <button
                      onClick={() => window.open(api.exportUrl(filters, debouncedSearch, sort, "xlsx"), "_blank")}
                      className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold text-slate-300 transition hover:bg-white/[0.06] hover:text-white"
                      title="Экспорт в Excel"
                    >
                      <FileSpreadsheet size={13} /> XLSX
                    </button>
                  </div>

                  <button onClick={() => setSidebarOpen(true)} className="btn-ghost h-10 lg:hidden">
                    <SlidersHorizontal size={15} />
                    Фильтры
                    {activeCount ? (
                      <span className="rounded-full bg-brand-500 px-1.5 py-0.5 text-[10px] font-bold text-white">{activeCount}</span>
                    ) : null}
                  </button>
                </div>
              </div>

              {activeCount ? (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="mr-1 inline-flex items-center gap-1 text-[11px] text-slate-500">
                    <Filter size={11} /> Фильтры:
                  </span>
                  {activeChips.map((chip) => (
                    <button
                      key={chip.key}
                      onClick={chip.remove}
                      className="inline-flex items-center gap-1.5 rounded-full border border-brand-500/30 bg-brand-500/10 px-2.5 py-1 text-[11px] font-semibold text-brand-200 transition hover:bg-brand-500/20"
                    >
                      {chip.label}
                      <X size={10} />
                    </button>
                  ))}
                  <button onClick={resetFilters} className="ml-1 text-[11px] font-semibold text-slate-500 transition hover:text-white">
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
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
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
                  action={
                    <div className="flex flex-wrap items-center justify-center gap-2">
                      {activeCount || debouncedSearch ? (
                        <button onClick={resetFilters} className="btn-ghost">
                          <X size={15} /> Сбросить фильтры
                        </button>
                      ) : null}
                      <button onClick={() => setParseOpen(true)} className="btn-primary">
                        <Plus size={15} /> Собрать лиды
                      </button>
                    </div>
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

      <ParseModal open={parseOpen} onClose={() => setParseOpen(false)} onSubmit={handleParse} meta={meta} />

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

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
