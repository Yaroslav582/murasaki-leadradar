"use client";

import { Check, Database, MapPin, MoreHorizontal, Phone, Sparkles, Star } from "lucide-react";
import type { Lead } from "@/lib/types";
import { STATUS_META, categoryStyle, phoneDigits } from "@/lib/utils";
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
      className="group card relative flex cursor-pointer flex-col p-4 transition duration-200 hover:-translate-y-0.5 hover:border-white/[0.14] hover:bg-[#1E202A] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#8B5CF6]/50"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="inline-flex items-center rounded-md bg-[#242731] border border-white/[0.06] px-2 py-0.5 text-[11px] font-medium text-[#9CA3AF]">
          {lead.category}
        </span>
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

      <h3 className="mt-2.5 line-clamp-2 text-sm font-semibold leading-snug text-[#F3F4F6] transition group-hover:text-[#C4B5FD]">
        {lead.name}
      </h3>

      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-[#9CA3AF]">
        <span className="inline-flex items-center gap-1 rounded-md bg-[#242731] border border-white/[0.06] px-2 py-0.5 text-[11px]">
          <MapPin size={11} className="text-[#6B7280]" />
          {lead.city}
        </span>
        <span className="inline-flex items-center gap-1 rounded-md bg-[#242731] border border-white/[0.06] px-2 py-0.5 text-[11px]">
          <Star size={11} className="fill-amber-400 text-amber-400" />
          <span className="font-mono tabular-nums font-semibold text-[#F3F4F6]">
            {lead.rating ? lead.rating.toFixed(1) : "—"}
          </span>
          <span className="font-mono tabular-nums text-[#6B7280]">({lead.reviews_count})</span>
        </span>
        <span
          className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-medium ${
            lead.has_website
              ? "border-emerald-500/20 bg-[rgba(16,185,129,0.12)] text-[#10B981]"
              : "border-rose-500/20 bg-rose-500/10 text-rose-400"
          }`}
        >
          {lead.has_website ? "Есть сайт" : "Без сайта"}
        </span>
      </div>

      <p className="mt-2 line-clamp-1 text-xs text-[#6B7280]">{lead.address || "Адрес не указан"}</p>

      <div className="mt-3 flex items-center justify-between gap-2">
        {lead.phone ? (
          <a
            href={`tel:${phoneDigits(lead.phone)}`}
            onClick={(event) => event.stopPropagation()}
            className="inline-flex items-center gap-1.5 text-xs font-mono tabular-nums text-[#9CA3AF] transition hover:text-[#F3F4F6]"
          >
            <Phone size={11} className="text-[#10B981]" />
            {lead.phone}
          </a>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#6B7280]">
            <Phone size={11} /> Нет телефона
          </span>
        )}

        {socials ? (
          <SocialLinks links={lead.social_links} />
        ) : (
          <span className="text-[10px] text-[#6B7280]">нет соцсетей</span>
        )}
      </div>

      <div className="mt-3 flex items-center gap-1.5 border-t border-white/[0.06] pt-2.5">
        <button
          onClick={(event) => {
            event.stopPropagation();
            triggerHaptic("light");
            if (lead.status === "new") onStatus(lead, "database");
            else onOpen(lead);
          }}
          className={`inline-flex h-8 flex-1 items-center justify-center gap-1.5 rounded-lg border text-xs font-medium transition ${
            lead.status === "new"
              ? "border-white/[0.08] bg-[#242731] text-[#9CA3AF] hover:border-[#8B5CF6]/40 hover:bg-[rgba(139,92,246,0.14)] hover:text-[#C4B5FD]"
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
          className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-[rgba(139,92,246,0.3)] bg-[rgba(139,92,246,0.14)] px-2.5 text-xs font-medium text-[#C4B5FD] transition hover:bg-[rgba(139,92,246,0.24)] hover:text-white disabled:opacity-50"
        >
          {generating ? <Spinner size={12} /> : <Sparkles size={12} />}
          {generating ? "Генерация" : lead.demo_id ? "Демо" : "Сделать демо"}
        </button>

        <button
          onClick={(event) => {
            event.stopPropagation();
            onOpen(lead);
          }}
          className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-[#242731] text-[#9CA3AF] transition hover:text-[#F3F4F6]"
          title="Подробнее"
        >
          <MoreHorizontal size={14} />
        </button>
      </div>
    </article>
  );
}
