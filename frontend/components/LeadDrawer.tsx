"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  CalendarDays,
  Check,
  Clock,
  Copy,
  ExternalLink,
  Flame,
  Globe2,
  Mail,
  MapPin,
  MessageCircle,
  Palette,
  Phone,
  RefreshCw,
  Send,
  Sparkles,
  Star,
  StickyNote,
  TrendingUp,
  X,
} from "lucide-react";
import { api, API_URL } from "@/lib/api";
import type { Lead, LeadStatus } from "@/lib/types";
import {
  ALL_STATUSES,
  SOURCE_LABELS,
  STATUS_META,
  WEBSITE_STATUS_META,
  categoryStyle,
  formatDate,
  generatePromptForLead,
  getFirstTouchOffer,
  getGrowthPoints,
  getLeadScore,
  getLeadScoreBadge,
  getTelegramUrl,
  getWebsiteStatus,
  getWhatsAppUrl,
  mapEmbedUrl,
  mapsUrl,
  phoneDigits,
} from "@/lib/utils";
import type { ToastVariant } from "./ui";
import { Avatar, SocialLinks, Spinner, StatusBadge } from "./ui";

export default function LeadDrawer({
  lead,
  onClose,
  onStatus,
  onGenerateDemo,
  onOpenDemo,
  onEnrich,
  onUpdated,
  onDemoChanged,
  generating,
  enriching,
  showToast,
}: {
  lead: Lead | null;
  onClose: () => void;
  onStatus: (lead: Lead, status: LeadStatus) => Promise<void> | void;
  onGenerateDemo: (lead: Lead) => Promise<void> | void;
  onOpenDemo: (lead: Lead) => Promise<void> | void;
  onEnrich: (lead: Lead) => Promise<void> | void;
  onUpdated: (lead: Lead) => void;
  onDemoChanged: (demoId: string, leadId: string) => void;
  generating: boolean;
  enriching: boolean;
  showToast: (message: string, variant?: ToastVariant) => void;
}) {
  const [notes, setNotes] = useState("");
  const [draftStatus, setDraftStatus] = useState<LeadStatus>("new");
  const [savingNotes, setSavingNotes] = useState(false);
  const [savingStatus, setSavingStatus] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [messageLoading, setMessageLoading] = useState(false);
  const [resolvingTg, setResolvingTg] = useState(false);

  useEffect(() => {
    if (!lead) return;
    setNotes(lead.notes ?? "");
    setDraftStatus(lead.status);
    setMessage(null);
  }, [lead?.id, lead?.notes, lead?.status]);

  useEffect(() => {
    if (!lead) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previous;
    };
  }, [lead, onClose]);

  if (!lead) return null;

  const status = STATUS_META[lead.status] ?? STATUS_META.new;
  const socials = lead.social_links ?? {};
  const hasSocials = Object.values(socials).some(Boolean);
  const priceLabel = lead.price_level ? "₽".repeat(Math.min(3, lead.price_level)) : null;

  const siteStatus = getWebsiteStatus(lead);
  const siteMeta = WEBSITE_STATUS_META[siteStatus] ?? WEBSITE_STATUS_META.no_website;
  const score = getLeadScore(lead);
  const scoreBadge = getLeadScoreBadge(score);
  const growthPoints = getGrowthPoints(lead);
  const fallbackDemoHost = API_URL || (typeof window !== "undefined" ? window.location.origin : "");
  const publicDemoUrl = lead.demo_id
    ? (lead.demo_url ?? `${fallbackDemoHost}/demo/${lead.demo_id}`)
    : null;
  const firstTouchOffer = getFirstTouchOffer(lead, publicDemoUrl);
  const tgUrl = getTelegramUrl(lead);
  const waUrl = getWhatsAppUrl(lead, firstTouchOffer);
  const waDirectUrl = getWhatsAppUrl(lead);

  const handleSaveNotes = async () => {
    setSavingNotes(true);
    try {
      const updated = await api.updateLead(lead.id, { notes });
      onUpdated(updated);
      showToast("Заметка сохранена", "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Не удалось сохранить заметку", "error");
    } finally {
      setSavingNotes(false);
    }
  };

  const handleStatus = async (nextStatus: LeadStatus) => {
    setDraftStatus(nextStatus);
    setSavingStatus(true);
    try {
      await onStatus(lead, nextStatus);
    } finally {
      setSavingStatus(false);
    }
  };

  const handleOutreach = async () => {
    setMessageLoading(true);
    try {
      const result = await api.outreach(lead.id);
      setMessage(result.message);
      if (result.demo_url) {
        const demoId = result.demo_url.split("/").pop();
        if (demoId && demoId !== lead.demo_id) {
          onDemoChanged(demoId, lead.id);
          onUpdated({ ...lead, demo_id: demoId });
        }
      }
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Не удалось сгенерировать сообщение", "error");
    } finally {
      setMessageLoading(false);
    }
  };

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      showToast("Скопировано в буфер обмена", "success");
    } catch {
      showToast("Не удалось скопировать", "error");
    }
  };

  const handleResolveTelegram = async () => {
    setResolvingTg(true);
    try {
      const res = await api.resolveTelegram(lead.id);
      if (res.found && res.telegram_url) {
        onUpdated({
          ...lead,
          social_links: { ...(lead.social_links ?? {}), telegram: res.telegram_url },
        });
        showToast(
          res.username ? `Найден Telegram: @${res.username}` : "Найден профиль Telegram по номеру!",
          "success",
        );
      } else {
        showToast("К этому номеру не привязан Telegram (или скрыт настройками)", "info");
      }
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Ошибка поиска Telegram", "error");
    } finally {
      setResolvingTg(false);
    }
  };

  const audit = lead.site_audit;

  return (
    <div className="fixed inset-0 z-[85]">
      <div className="absolute inset-0 bg-black/75 backdrop-blur-md animate-fadeIn" onClick={onClose} />
      <div className="absolute right-0 top-0 flex h-full w-full max-w-[560px] flex-col border-l border-white/[0.08] bg-[#0C0E15]/95 backdrop-blur-2xl shadow-2xl animate-slideLeft pt-3">
        <div className="flex items-start gap-3 border-b border-white/[0.06] px-5 py-5">
          <Avatar name={lead.name} category={lead.category} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center rounded-md bg-[#242731]/50 border border-white/[0.06] px-2 py-0.5 text-[10px] uppercase tracking-wider font-semibold text-[#9CA3AF]">
                {lead.category}
              </span>
              <StatusBadge status={lead.status} />
              <span
                className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-semibold ${siteMeta.badge}`}
                title={siteMeta.description}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${siteMeta.dot}`} />
                {siteMeta.label}
              </span>
              <span
                className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-bold ${scoreBadge.border} ${scoreBadge.bg} ${scoreBadge.text}`}
                title={`Lead Score: ${score.toFixed(1)} / 5.0 (${scoreBadge.label})`}
              >
                <Flame size={11} className="fill-current text-amber-400" />
                <span className="font-mono tabular-nums tracking-tight">{score.toFixed(1)}</span>
                <span className="text-[9px] opacity-80">{scoreBadge.label}</span>
              </span>
            </div>
            <h2 className="mt-2 text-xl font-bold leading-tight tracking-tight text-[#F3F4F6]">{lead.name}</h2>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[#9CA3AF]">
              <span className="inline-flex items-center gap-1">
                <MapPin size={12} className="text-[#6B7280]" /> {lead.city}
              </span>
              <span className="inline-flex items-center gap-1">
                <Star size={12} className="fill-amber-400 text-amber-400" />
                <span className="font-mono tabular-nums tracking-tight font-semibold text-[#F3F4F6]">
                  {lead.rating ? lead.rating.toFixed(1) : "—"}
                </span>
                <span>·</span>
                <span className="font-mono tabular-nums tracking-tight">{lead.reviews_count}</span> отзывов
              </span>
              <span className="text-[#6B7280]">{SOURCE_LABELS[lead.source] ?? lead.source}</span>
            </div>
          </div>
          <button onClick={onClose} className="icon-btn" aria-label="Закрыть">
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
          {/* Кнопки быстрых действий */}
          <div className="flex flex-wrap gap-2">
            {lead.demo_id ? (
              <>
                <button
                  onClick={() => onOpenDemo(lead)}
                  disabled={generating}
                  className="btn-primary flex-1 min-w-[150px]"
                >
                  {generating ? <Spinner size={15} /> : <Sparkles size={15} />}
                  Открыть демо-лендинг
                </button>
                <button
                  onClick={() => onGenerateDemo(lead)}
                  disabled={generating}
                  className="inline-flex h-9 items-center justify-center gap-1.5 rounded-xl border border-brand-500/30 bg-brand-500/10 px-3 text-xs font-semibold text-brand-300 transition hover:bg-brand-500/20 hover:text-white disabled:opacity-50"
                  title="Выбрать другой стиль и сгенерировать демо"
                >
                  <Palette size={14} />
                  Сменить стиль
                </button>
              </>
            ) : (
              <button
                onClick={() => onGenerateDemo(lead)}
                disabled={generating}
                className="btn-primary flex-1 min-w-[170px]"
              >
                {generating ? <Spinner size={15} /> : <Sparkles size={15} />}
                Выбрать стиль и создать демо
              </button>
            )}
            {waDirectUrl && (
              <a
                href={waDirectUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-emerald-500/25 bg-[rgba(16,185,129,0.12)] px-3 text-xs font-semibold text-[#10B981] transition hover:bg-[rgba(16,185,129,0.22)]"
              >
                <MessageCircle size={14} />
                WhatsApp
              </a>
            )}
            {tgUrl && (
              <a
                href={tgUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-sky-500/25 bg-sky-500/10 px-3 text-xs font-semibold text-sky-400 transition hover:bg-sky-500/20"
              >
                <Send size={14} />
                Telegram
              </a>
            )}
            {lead.phone ? (
              <a href={`tel:${phoneDigits(lead.phone)}`} className="btn-ghost">
                <Phone size={15} />
                Позвонить
              </a>
            ) : null}
            <button
              onClick={() => handleCopy(generatePromptForLead(lead))}
              className="btn-ghost"
              title="Скопировать готовый промпт с данными компании для бесплатной генерации в ChatGPT / Claude"
            >
              <Copy size={13} />
              Свой промпт (0 кр)
            </button>
            {lead.phone && !tgUrl && (
              <button onClick={handleResolveTelegram} disabled={resolvingTg} className="btn-ghost border-sky-500/25 text-sky-300 hover:bg-sky-500/10">
                {resolvingTg ? <Spinner size={14} /> : <Send size={14} />}
                Найти TG по номеру
              </button>
            )}
            {lead.website_url ? (
              <button onClick={() => onEnrich(lead)} disabled={enriching} className="btn-ghost">
                {enriching ? <Spinner size={15} /> : <RefreshCw size={15} />}
                {lead.enriched_at ? "Обновить" : "Обогатить"}
              </button>
            ) : null}
          </div>

          {audit && audit.audited_at && (
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-3.5 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="label flex items-center gap-1.5 text-slate-300">
                  <Globe2 size={13} className="text-violet-400" />
                  Технический аудит сайта
                </span>
                {audit.response_ms ? (
                  <span className="font-mono text-[11px] text-slate-400">{audit.response_ms} мс</span>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-1.5 text-[11px]">
                <span className={`rounded-md border px-2 py-0.5 font-medium ${audit.is_alive ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" : "border-red-500/30 bg-red-500/15 text-red-300"}`}>
                  {audit.is_alive ? `HTTP ${audit.status_code ?? 200}` : `Не отвечает${audit.status_code ? ` (${audit.status_code})` : ""}`}
                </span>
                <span className={`rounded-md border px-2 py-0.5 font-medium ${audit.ssl_valid && audit.is_https ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" : "border-amber-500/30 bg-amber-500/10 text-amber-300"}`}>
                  {audit.ssl_valid && audit.is_https ? "SSL OK" : "Проблема SSL"}
                </span>
                {audit.has_viewport !== null && audit.has_viewport !== undefined && (
                  <span className={`rounded-md border px-2 py-0.5 font-medium ${audit.has_viewport ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" : "border-rose-500/30 bg-rose-500/10 text-rose-300"}`}>
                    {audit.has_viewport ? "Мобильная версия OK" : "Нет мобильной адаптации"}
                  </span>
                )}
                {audit.is_stub && (
                  <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-medium text-amber-300">
                    Заглушка ({audit.stub_domain})
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Индикатор стилей awesome-design-md */}
          <div className="flex items-center gap-2 rounded-xl border border-brand-500/20 bg-brand-500/[0.05] px-3 py-2 text-[11px] text-slate-300">
            <Palette size={14} className="text-brand-400 shrink-0" />
            <div className="flex-1">
              <span className="font-semibold text-brand-200">20 дизайн-систем (AWESOME-DESIGN-MD): </span>
              <span className="text-slate-400">Тёмные, Светлые и Яркие шаблоны с автоподбором под нишу</span>
            </div>
          </div>

          {/* Блок «Что мешает (точки роста)» */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="label flex items-center gap-1.5 text-amber-300">
                <TrendingUp size={13} className="text-amber-400" />
                Что мешает (точки роста для продажи)
              </p>
              <span className="text-[10px] text-slate-500">2–3 аргумента для продажи</span>
            </div>
            <div className="space-y-2 rounded-2xl border border-amber-500/20 bg-amber-500/[0.04] p-3.5">
              {growthPoints.map((point, index) => (
                <div key={index} className="flex items-start gap-2.5 text-xs leading-relaxed text-slate-300">
                  <div className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-amber-500/15 text-[10px] font-bold text-amber-300">
                    {index + 1}
                  </div>
                  <p>{point}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Блок «Первый контакт» */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="label flex items-center gap-1.5 text-[#C4B5FD]">
                <Send size={13} className="text-[#8B5CF6]" />
                Первый контакт (Готовый оффер)
              </p>
              <button
                onClick={() => handleCopy(firstTouchOffer)}
                className="inline-flex items-center gap-1 text-xs font-semibold text-[#C4B5FD] transition hover:text-white"
              >
                <Copy size={11} /> Скопировать
              </button>
            </div>
            <div className="rounded-2xl border border-[rgba(139,92,246,0.3)] bg-[rgba(139,92,246,0.06)] p-4">
              <p className="whitespace-pre-wrap text-xs leading-relaxed text-slate-200">
                {firstTouchOffer}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  onClick={() => handleCopy(firstTouchOffer)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-[11px] font-semibold text-slate-200 transition hover:bg-white/[0.08]"
                >
                  <Copy size={12} /> Скопировать оффер
                </button>
                {waUrl && (
                  <a
                    href={waUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-[rgba(16,185,129,0.15)] px-2.5 py-1.5 text-[11px] font-semibold text-[#10B981] transition hover:bg-[rgba(16,185,129,0.25)]"
                  >
                    <MessageCircle size={12} /> Открыть в WhatsApp
                  </a>
                )}
                {tgUrl && (
                  <a
                    href={tgUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-lg border border-sky-500/30 bg-sky-500/15 px-2.5 py-1.5 text-[11px] font-semibold text-sky-300 transition hover:bg-sky-500/25"
                  >
                    <Send size={12} /> Открыть в Telegram
                  </a>
                )}
                {lead.demo_id ? (
                  <button
                    onClick={() => onOpenDemo(lead)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-[11px] font-semibold text-slate-300 transition hover:text-white"
                  >
                    <ExternalLink size={11} /> Открыть демо
                  </button>
                ) : null}
              </div>
            </div>
          </section>

          <section className="space-y-3">
            <p className="label">Контакты</p>
            <div className="overflow-hidden rounded-2xl border border-white/[0.07] bg-white/[0.02]">
              <div className="flex items-center justify-between gap-3 border-b border-white/[0.05] px-4 py-3">
                <span className="inline-flex items-center gap-2 text-sm text-slate-400">
                  <Phone size={14} className="text-emerald-300" /> Телефон
                </span>
                {lead.phone ? (
                  <a
                    href={`tel:${phoneDigits(lead.phone)}`}
                    className="font-mono tabular-nums tracking-tight text-sm font-semibold text-[#F3F4F6] transition hover:text-emerald-300"
                  >
                    {lead.phone}
                  </a>
                ) : (
                  <span className="text-sm text-slate-600">не указан</span>
                )}
              </div>

              <div className="flex items-center justify-between gap-3 border-b border-white/[0.05] px-4 py-3">
                <span className="inline-flex items-center gap-2 text-sm text-slate-400">
                  <Globe2 size={14} className="text-sky-300" /> Сайт
                </span>
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${siteMeta.badge}`}>
                    {siteMeta.label}
                  </span>
                  {lead.website_url ? (
                    <a
                      href={lead.website_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex min-w-0 items-center gap-1 truncate text-sm font-semibold text-sky-300 hover:underline"
                    >
                      <span className="truncate">{lead.website_url.replace(/^https?:\/\//, "").replace(/\/$/, "")}</span>
                      <ExternalLink size={12} className="shrink-0" />
                    </a>
                  ) : null}
                </div>
              </div>

              <div className="flex items-center justify-between gap-3 border-b border-white/[0.05] px-4 py-3">
                <span className="inline-flex items-center gap-2 text-sm text-slate-400">
                  <Mail size={14} className="text-violet-300" /> Email
                </span>
                <span className="truncate text-sm text-slate-300">
                  {lead.emails?.length ? lead.emails.join(", ") : "—"}
                </span>
              </div>

              <div className="flex items-center justify-between gap-3 px-4 py-3">
                <span className="inline-flex items-center gap-2 text-sm text-slate-400">
                  <MessageCircle size={14} className="text-brand-300" /> Соцсети
                </span>
                {hasSocials ? (
                  <SocialLinks links={socials} size="md" stopPropagation={false} />
                ) : (
                  <span className="text-sm text-slate-600">не найдены</span>
                )}
              </div>
            </div>
          </section>

          <section className="space-y-3">
            <p className="label flex items-center gap-1.5">
              <MapPin size={12} /> Локация
            </p>
            {lead.latitude && lead.longitude ? (
              <div className="overflow-hidden rounded-2xl border border-white/[0.07]">
                <iframe
                  title={`Карта: ${lead.name}`}
                  src={mapEmbedUrl(lead.latitude, lead.longitude)}
                  className="h-44 w-full"
                  loading="lazy"
                />
              </div>
            ) : null}
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] px-4 py-3">
              <p className="text-sm leading-relaxed text-slate-300">{lead.address || "Адрес не указан"}</p>
              <a
                href={mapsUrl(lead)}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-brand-300 hover:text-brand-200"
              >
                Открыть в Яндекс.Картах <ExternalLink size={11} />
              </a>
            </div>
          </section>

          <section className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4">
              <p className="label flex items-center gap-1.5">
                <Clock size={12} /> Часы работы
              </p>
              <div className="mt-2 space-y-1 text-xs text-slate-400">
                {(lead.opening_hours ?? []).length ? (
                  lead.opening_hours.map((value) => <p key={value}>{value}</p>)
                ) : (
                  <p className="text-slate-600">не указаны</p>
                )}
              </div>
            </div>
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4">
              <p className="label flex items-center gap-1.5">
                <CalendarDays size={12} /> Карточка
              </p>
              <div className="mt-2 space-y-1.5 text-xs text-slate-400">
                <p>Добавлен: {formatDate(lead.created_at)}</p>
                <p>Обогащён: {lead.enriched_at ? formatDate(lead.enriched_at) : "нет"}</p>
                {priceLabel ? <p>Средний чек: {priceLabel}</p> : null}
              </div>
            </div>
          </section>

          <section className="space-y-3">
            <p className="label">Статус</p>
            <div className="flex flex-wrap gap-2">
              {ALL_STATUSES.map((value) => {
                const meta = STATUS_META[value];
                const active = draftStatus === value;
                return (
                  <button
                    key={value}
                    onClick={() => handleStatus(value)}
                    disabled={savingStatus}
                    className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                      active ? meta.badge : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20"
                    }`}
                  >
                    <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
                    {meta.label}
                    {active ? <Check size={11} /> : null}
                  </button>
                );
              })}
            </div>
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="label flex items-center gap-1.5">
                <StickyNote size={12} /> Заметки
              </p>
              <button
                onClick={handleSaveNotes}
                disabled={savingNotes}
                className="text-xs font-semibold text-brand-300 transition hover:text-brand-200 disabled:opacity-50"
              >
                {savingNotes ? "Сохраняем..." : "Сохранить"}
              </button>
            </div>
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Что обсудили, когда перезвонить, детали сделки..."
              rows={3}
              className="input resize-none"
            />
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="label flex items-center gap-1.5">
                <Send size={12} /> Сообщение для аутрича
              </p>
              <button
                onClick={handleOutreach}
                disabled={messageLoading}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand-300 transition hover:text-brand-200 disabled:opacity-50"
              >
                {messageLoading ? <Spinner size={11} /> : <Sparkles size={11} />}
                {message ? "Обновить" : "Сгенерировать"}
              </button>
            </div>
            {message ? (
              <div className="rounded-2xl border border-brand-500/20 bg-brand-500/[0.06] p-4">
                <p className="whitespace-pre-wrap text-xs leading-relaxed text-slate-200">{message}</p>
                <div className="mt-3 flex items-center gap-2">
                  <button
                    onClick={() => handleCopy(message)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-[11px] font-semibold text-slate-300 transition hover:text-white"
                  >
                    <Copy size={11} /> Копировать
                  </button>
                  {lead.demo_id ? (
                    <button
                      onClick={() => onOpenDemo(lead)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-[11px] font-semibold text-slate-300 transition hover:text-white"
                    >
                      <ExternalLink size={11} /> Открыть демо
                    </button>
                  ) : null}
                </div>
              </div>
            ) : (
              <p className="rounded-2xl border border-dashed border-white/10 bg-white/[0.015] px-4 py-4 text-xs leading-relaxed text-slate-500">
                Сгенерируем персональный скрипт первого сообщения со ссылкой на демо-лендинг, чтобы
                сразу перейти в диалог.
              </p>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
