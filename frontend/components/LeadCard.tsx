"use client";

import { Check, Database, MapPin, MoreHorizontal, Phone, Sparkles, Star } from "lucide-react";
import type { Lead } from "@/lib/types";
import { STATUS_META, categoryStyle, phoneDigits } from "@/lib/utils";
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

  return (
    <article
      onClick={() => onOpen(lead)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen(lead);
        }
      }}
      role="button"
      tabIndex={0}
      className="group card relative flex cursor-pointer flex-col p-5 transition duration-200 hover:-translate-y-0.5 hover:border-brand-500/25 hover:bg-white/[0.045] hover:shadow-glow focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50"
    >
      <div className="flex items-start justify-between gap-2">
        <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${categoryStyle(lead.category)}`}>
          {lead.category}
        </span>
        <div className="flex items-center gap-1.5">
          {lead.demo_id ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/20 bg-emerald-400/[0.08] px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
              <Sparkles size={10} /> демо
            </span>
          ) : null}
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${status.badge}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${status.dot}`} />
            {status.label}
          </span>
        </div>
      </div>

      <h3 className="mt-3 line-clamp-2 text-[15px] font-bold leading-snug text-white transition group-hover:text-brand-200">
        {lead.name}
      </h3>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
        <span className="inline-flex items-center gap-1">
          <MapPin size={12} className="text-slate-500" />
          {lead.city}
        </span>
        <span className="inline-flex items-center gap-1">
          <Star size={12} className="fill-amber-400 text-amber-400" />
          <span className="font-semibold text-slate-200">{lead.rating ? lead.rating.toFixed(1) : "—"}</span>
          <span className="text-slate-600">({lead.reviews_count})</span>
        </span>
        <span
          className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold ${
            lead.has_website
              ? "border-emerald-400/20 bg-emerald-400/[0.07] text-emerald-300"
              : "border-rose-400/20 bg-rose-400/[0.07] text-rose-300"
          }`}
        >
          {lead.has_website ? "Есть сайт" : "Без сайта"}
        </span>
      </div>

      <p className="mt-2 line-clamp-1 text-xs text-slate-500">{lead.address || "Адрес не указан"}</p>

      <div className="mt-4 flex items-center justify-between gap-2">
        {lead.phone ? (
          <a
            href={`tel:${phoneDigits(lead.phone)}`}
            onClick={(event) => event.stopPropagation()}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-300 transition hover:text-white"
          >
            <Phone size={12} className="text-emerald-300" />
            {lead.phone}
          </a>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-xs text-slate-600">
            <Phone size={12} /> Нет телефона
          </span>
        )}

        {socials ? (
          <SocialLinks links={lead.social_links} />
        ) : (
          <span className="text-[10px] text-slate-600">нет соцсетей</span>
        )}
      </div>

      <div className="mt-4 flex items-center gap-2 border-t border-white/[0.06] pt-3">
        <button
          onClick={(event) => {
            event.stopPropagation();
            if (lead.status === "new") onStatus(lead, "database");
            else onOpen(lead);
          }}
          className={`inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-xl border text-xs font-semibold transition ${
            lead.status === "new"
              ? "border-white/10 bg-white/[0.04] text-slate-200 hover:border-brand-500/40 hover:bg-brand-500/10 hover:text-white"
              : `${status.badge} hover:brightness-110`
          }`}
        >
          {lead.status === "new" ? <Database size={13} /> : <Check size={13} />}
          {lead.status === "new" ? "В базу" : status.label}
        </button>

        <button
          onClick={(event) => {
            event.stopPropagation();
            onDemo(lead);
          }}
          disabled={generating}
          className="inline-flex h-9 items-center justify-center gap-1.5 rounded-xl border border-brand-500/30 bg-brand-500/[0.12] px-3 text-xs font-semibold text-brand-200 transition hover:bg-brand-500/20 hover:text-white disabled:opacity-60"
        >
          {generating ? <Spinner size={13} /> : <Sparkles size={13} />}
          {generating ? "Генерация" : lead.demo_id ? "Демо" : "Сделать демо"}
        </button>

        <button
          onClick={(event) => {
            event.stopPropagation();
            onOpen(lead);
          }}
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.02] text-slate-500 transition hover:text-white"
          title="Подробнее"
        >
          <MoreHorizontal size={15} />
        </button>
      </div>
    </article>
  );
}
