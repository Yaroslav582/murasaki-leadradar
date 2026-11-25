"use client";

import { Check, ChevronRight, Database, Flame, Globe2, MapPin, MessageCircle, Phone, Send, Sparkles, Star } from "lucide-react";
import type { Lead } from "@/lib/types";
import {
  STATUS_META,
  WEBSITE_STATUS_META,
  categoryStyle,
  getLeadScore,
  getLeadScoreBadge,
  getTelegramUrl,
  getWebsiteStatus,
  getWhatsAppUrl,
  phoneDigits,
} from "@/lib/utils";
import { triggerHaptic } from "@/lib/telegram";
import { SocialLinks, Spinner } from "./ui";

export default function LeadCard({
  lead,
  onOpen,
  onStatus,
  onDemo,
  generating,
}: {
  lead: Lead;
  onOpen: (lead: Lead) => void;
  onStatus: (lead: Lead, status: Lead["status"]) => void;
  onDemo: (lead: Lead) => void;
  generating: boolean;
}) {
  const status = STATUS_META[lead.status] ?? STATUS_META.new;
  const socials = Object.values(lead.social_links ?? {}).filter(Boolean).length;

  const siteStatus = getWebsiteStatus(lead);
  const siteMeta = WEBSITE_STATUS_META[siteStatus] ?? WEBSITE_STATUS_META.no_website;
  const score = getLeadScore(lead);
  const scoreBadge = getLeadScoreBadge(score);
  const auditIssue = lead.site_audit?.issues?.[0];

  const tgUrl = getTelegramUrl(lead);
  const waUrl = getWhatsAppUrl(lead);
  const digits = phoneDigits(lead.phone);

  const handleCardClick = () => {
    triggerHaptic("light");
    onOpen(lead);
  };

  return (
    <article
      onClick={handleCardClick}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          handleCardClick();
        }
      }}
      role="button"
      tabIndex={0}
      className="group card-interactive relative flex cursor-pointer flex-col p-4 focus:outline-none focus-visible:ring-1 focus-visible:ring-[#52525B]"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="inline-flex items-center rounded-md bg-[#242731]/50 border border-white/[0.06] px-2 py-0.5 text-[10px] uppercase tracking-wider font-semibold text-[#9CA3AF]">
            {lead.category}
          </span>
          <span
            className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-bold ${scoreBadge.border} ${scoreBadge.bg} ${scoreBadge.text}`}
            title={`Lead Score: ${score.toFixed(1)} / 5.0 (${scoreBadge.label})`}
          >
            <Flame size={10} className="fill-current text-amber-400" />
            <span className="font-mono tabular-nums tracking-tight">{score.toFixed(1)}</span>
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          {lead.demo_id ? (
            <span className="inline-flex items-center gap-1 rounded-md border border-emerald-500/20 bg-[rgba(16,185,129,0.12)] px-1.5 py-0.5 text-[10px] font-medium text-[#10B981]">
              <Sparkles size={10} /> демо
            </span>
          ) : null}
          <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-medium ${status.badge}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${status.dot}`} />
            {status.label}
          </span>
        </div>
      </div>

      <h3 className="mt-2.5 line-clamp-2 text-[14px] font-semibold leading-snug text-[#F4F4F5] transition group-hover:text-white">
        {lead.name}
      </h3>

      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-[#9CA3AF]">
        <span className="inline-flex items-center gap-1 rounded-md bg-[#242731] border border-white/[0.06] px-2 py-0.5 text-[11px]">
          <MapPin size={11} className="text-[#6B7280]" />
          {lead.city}
        </span>
        <span className="inline-flex items-center gap-1 rounded-md bg-[#242731] border border-white/[0.06] px-2 py-0.5 text-[11px]">
          <Star size={11} className="fill-amber-400 text-amber-400" />
          <span className="font-mono tabular-nums tracking-tight font-semibold text-[#F3F4F6]">
            {lead.rating ? lead.rating.toFixed(1) : "—"}
          </span>
          <span className="font-mono tabular-nums tracking-tight text-[#6B7280]">({lead.reviews_count})</span>
        </span>
        <span
          className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-semibold ${siteMeta.badge}`}
          title={siteMeta.description}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${siteMeta.dot}`} />
          {siteMeta.label}
        </span>
      </div>

      <p className="mt-2 line-clamp-1 text-xs text-[#64748B]">{lead.address || "Адрес не указан"}</p>

      {auditIssue && (
        <p className="mt-1.5 line-clamp-1 rounded-md border border-amber-500/20 bg-amber-500/[0.07] px-2 py-1 text-[11px] font-medium text-amber-300/90">
          {auditIssue}
        </p>
      )}

      {/* Быстрые контакты и мессенджеры */}
      <div className="mt-3 flex items-center justify-between gap-2 border-t border-white/[0.04] pt-2.5">
        <div className="flex items-center gap-1">
          {digits ? (
            <a
              href={`tel:${digits}`}
              onClick={(event) => {
                event.stopPropagation();
                triggerHaptic("light");
              }}
              className="inline-flex h-8 py-1.5 items-center gap-1 rounded-lg border border-white/[0.06] bg-[#242731] px-2 text-[11px] font-medium text-[#9CA3AF] transition hover:border-[#10B981]/40 hover:text-[#10B981]"
              title="Позвонить"
            >
              <Phone size={11} className="text-[#10B981]" />
              <span className="font-mono tabular-nums tracking-tight">{lead.phone}</span>
            </a>
          ) : (
            <span className="inline-flex items-center gap-1 text-[11px] text-[#6B7280]">
              <Phone size={11} /> Нет тел.
            </span>
          )}
        </div>

        {/* Кнопки прямого перехода в мессенджеры */}
        <div className="flex items-center gap-1">
          {waUrl && (
            <a
              href={waUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(event) => {
                event.stopPropagation();
                triggerHaptic("light");
              }}
              className="inline-flex h-8 py-1.5 items-center gap-1 rounded-lg border border-emerald-500/25 bg-[rgba(16,185,129,0.1)] px-2 text-[11px] font-medium text-[#10B981] transition hover:bg-[rgba(16,185,129,0.2)]"
              title="Написать в WhatsApp"
            >
              <MessageCircle size={11} />
              <span>WhatsApp</span>
            </a>
          )}

          {tgUrl && (
            <a
              href={tgUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(event) => {
                event.stopPropagation();
                triggerHaptic("light");
              }}
              className="inline-flex h-8 py-1.5 items-center gap-1 rounded-lg border border-sky-500/25 bg-sky-500/10 px-2 text-[11px] font-medium text-sky-400 transition hover:bg-sky-500/20"
              title="Написать в Telegram"
            >
              <Send size={11} />
              <span>TG</span>
            </a>
          )}

          {socials && !waUrl && !tgUrl ? (
            <SocialLinks links={lead.social_links} />
          ) : null}
        </div>
      </div>

      <div className="mt-3 flex items-center gap-1.5 border-t border-white/[0.04] pt-2.5">
        <button
          onClick={(event) => {
            event.stopPropagation();
            triggerHaptic("light");
            if (lead.status === "new") onStatus(lead, "database");
            else onOpen(lead);
          }}
          className={`inline-flex h-8 py-1.5 flex-1 items-center justify-center gap-1.5 rounded-lg border text-xs font-medium transition ${
            lead.status === "new"
              ? "border-white/[0.06] bg-[#242731] text-[#9CA3AF] hover:border-[#8B5CF6]/40 hover:bg-[#8B5CF6]/10 hover:text-[#C4B5FD]"
              : `${status.badge} hover:brightness-110`
          }`}
        >
          {lead.status === "new" ? <Database size={12} /> : <Check size={12} />}
          {lead.status === "new" ? "В базу" : status.label}
        </button>

        <button
          onClick={(event) => {
            event.stopPropagation();
            triggerHaptic("medium");
            onDemo(lead);
          }}
          disabled={generating}
          className="inline-flex h-8 py-1.5 items-center justify-center gap-1.5 rounded-lg border border-[#8B5CF6]/30 bg-[#8B5CF6]/5 px-2.5 text-xs font-medium text-[#C4B5FD] transition hover:bg-[#8B5CF6]/15 hover:text-white disabled:opacity-50"
        >
          {generating ? <Spinner size={12} /> : <Sparkles size={12} className="text-[#8B5CF6]" />}
          {generating ? "Генерация" : lead.demo_id ? "Демо" : "Сделать демо"}
        </button>

        <button
          onClick={(event) => {
            event.stopPropagation();
            onOpen(lead);
          }}
          className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/[0.06] bg-[#242731] text-[#9CA3AF] transition hover:border-white/20 hover:text-[#F3F4F6]"
          title="Открыть карточку"
          aria-label="Открыть карточку"
        >
          <ChevronRight size={14} />
        </button>
      </div>
    </article>
  );
}
