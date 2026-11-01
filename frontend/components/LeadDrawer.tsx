"use client";

import { useEffect, useState } from "react";
import {
  CalendarDays,
  Check,
  Clock,
  Copy,
  ExternalLink,
  Globe2,
  Mail,
  MapPin,
  MessageCircle,
  Phone,
  RefreshCw,
  Send,
  Sparkles,
  Star,
  StickyNote,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Lead, LeadStatus } from "@/lib/types";
import {
  ALL_STATUSES,
  SOURCE_LABELS,
  STATUS_META,
  categoryStyle,
  formatDate,
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

  return (
    <div className="fixed inset-0 z-[85]">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm animate-fadeIn" onClick={onClose} />
      <div className="absolute right-0 top-0 flex h-full w-full max-w-[560px] flex-col border-l border-white/[0.08] bg-[#080a11] shadow-2xl animate-slideLeft">
        <div className="flex items-start gap-3 border-b border-white/[0.06] px-5 py-5">
          <Avatar name={lead.name} category={lead.category} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${categoryStyle(lead.category)}`}>
                {lead.category}
              </span>
              <StatusBadge status={lead.status} />
            </div>
            <h2 className="mt-2 text-xl font-extrabold leading-tight tracking-tight text-white">{lead.name}</h2>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
              <span className="inline-flex items-center gap-1">
                <MapPin size={12} /> {lead.city}
              </span>
              <span className="inline-flex items-center gap-1">
                <Star size={12} className="fill-amber-400 text-amber-400" />
                {lead.rating ? lead.rating.toFixed(1) : "—"} · {lead.reviews_count} отзывов
              </span>
              <span className="text-slate-600">{SOURCE_LABELS[lead.source] ?? lead.source}</span>
            </div>
          </div>
          <button onClick={onClose} className="icon-btn" aria-label="Закрыть">
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => (lead.demo_id ? onOpenDemo(lead) : onGenerateDemo(lead))}
              disabled={generating}
              className="btn-primary flex-1"
            >
              {generating ? <Spinner size={15} /> : <Sparkles size={15} />}
              {lead.demo_id ? "Открыть демо-лендинг" : "Сгенерировать демо"}
            </button>
            {lead.phone ? (
              <a href={`tel:${phoneDigits(lead.phone)}`} className="btn-ghost">
                <Phone size={15} />
                Позвонить
              </a>
            ) : null}
            {lead.website_url ? (
              <button onClick={() => onEnrich(lead)} disabled={enriching} className="btn-ghost">
                {enriching ? <Spinner size={15} /> : <RefreshCw size={15} />}
                {lead.enriched_at ? "Обновить контакты" : "Обогатить"}
              </button>
            ) : null}
          </div>

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
                    className="text-sm font-semibold text-white transition hover:text-emerald-300"
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
                ) : (
                  <span className="rounded-full border border-rose-400/25 bg-rose-400/10 px-2.5 py-1 text-[11px] font-semibold text-rose-300">
                    сайта нет
                  </span>
                )}
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
