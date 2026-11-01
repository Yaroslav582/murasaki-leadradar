"use client";

import { ArrowUpRight, Globe2, MessageCircle, Radar, Sparkles, TrendingUp } from "lucide-react";
import type { Meta, Stats } from "@/lib/types";
import { formatNumber } from "@/lib/utils";

function MiniStat({
  icon,
  label,
  value,
  hint,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  hint: string;
  accent: string;
}) {
  return (
    <div className="card relative overflow-hidden p-5">
      <div className={`absolute -right-8 -top-8 h-24 w-24 rounded-full blur-2xl ${accent}`} />
      <div className="relative flex items-start justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">{label}</p>
          <p className="mt-2 text-3xl font-extrabold tracking-tight text-white">{formatNumber(value)}</p>
          <p className="mt-1 text-[11px] text-slate-500">{hint}</p>
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-300">
          {icon}
        </div>
      </div>
    </div>
  );
}

export default function StatsRow({
  stats,
  meta,
  onParse,
}: {
  stats: Stats | null;
  meta: Meta | null;
  onParse: () => void;
}) {
  const total = stats?.total ?? meta?.total ?? 0;
  const noWebsite = stats?.no_website ?? meta?.no_website ?? 0;
  const withSocial = stats?.with_social ?? meta?.with_social ?? 0;
  const demos = stats?.demos ?? 0;
  const deals = stats?.by_status?.deal ?? 0;
  const statuses = stats?.by_status ?? { new: 0, database: 0, sent: 0, rejected: 0, deal: 0 };
  const ratios = total
    ? {
        new: (statuses.new / total) * 100,
        database: (statuses.database / total) * 100,
        sent: (statuses.sent / total) * 100,
        rejected: (statuses.rejected / total) * 100,
        deal: (statuses.deal / total) * 100,
      }
    : { new: 0, database: 0, sent: 0, rejected: 0, deal: 0 };

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <div className="card relative overflow-hidden p-5 sm:col-span-2 xl:col-span-1">
        <div className="pointer-events-none absolute -right-10 -top-16 h-52 w-52 rounded-full bg-brand-500/25 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-20 -left-10 h-40 w-40 rounded-full bg-cyan-400/10 blur-3xl" />
        <div className="relative">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-brand-300">
              <Radar size={13} />
              Лидов в базе
            </span>
            <button
              onClick={onParse}
              className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2 py-1 text-[10px] font-semibold text-slate-300 transition hover:border-brand-500/40 hover:text-white"
            >
              <ArrowUpRight size={11} /> Собрать
            </button>
          </div>
          <p className="mt-3 text-5xl font-black tracking-tight text-white">{formatNumber(total)}</p>
          <p className="mt-1 text-xs text-slate-400">
            <span className="font-semibold text-rose-300">{formatNumber(noWebsite)}</span> без сайта — горячая аудитория
          </p>

          <div className="mt-5 flex h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
            <div className="bg-sky-400" style={{ width: `${ratios.new}%` }} />
            <div className="bg-violet-400" style={{ width: `${ratios.database}%` }} />
            <div className="bg-amber-400" style={{ width: `${ratios.sent}%` }} />
            <div className="bg-emerald-400" style={{ width: `${ratios.deal}%` }} />
            <div className="bg-rose-400" style={{ width: `${ratios.rejected}%` }} />
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slate-500">
            <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-sky-400" />Новые {statuses.new}</span>
            <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-violet-400" />В базе {statuses.database}</span>
            <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-amber-400" />Отправлено {statuses.sent}</span>
            <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Сделки {statuses.deal}</span>
          </div>
        </div>
      </div>

      <MiniStat
        icon={<Globe2 size={17} className="text-rose-300" />}
        label="Без сайта"
        value={noWebsite}
        hint="Готовы к продаже сайта"
        accent="bg-rose-500/20"
      />
      <MiniStat
        icon={<MessageCircle size={17} className="text-sky-300" />}
        label="С соцсетями"
        value={withSocial}
        hint="Можно писать сразу"
        accent="bg-sky-500/20"
      />
      <div className="card relative overflow-hidden p-5">
        <div className="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-emerald-500/15 blur-2xl" />
        <div className="relative flex items-start justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Демо и сделки</p>
            <p className="mt-2 text-3xl font-extrabold tracking-tight text-white">
              {formatNumber(demos)} <span className="text-lg font-bold text-slate-600">/</span>{" "}
              <span className="text-emerald-300">{formatNumber(deals)}</span>
            </p>
            <p className="mt-1 text-[11px] text-slate-500">
              {demos ? "Лендинги готовы к отправке" : "Сгенерируйте первое демо"}
            </p>
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-emerald-300">
            <TrendingUp size={17} />
          </div>
        </div>
        <div className="relative mt-3 inline-flex items-center gap-1.5 rounded-full border border-emerald-400/20 bg-emerald-400/[0.08] px-2.5 py-1 text-[10px] font-semibold text-emerald-300">
          <Sparkles size={11} />
          AI-генератор включён
        </div>
      </div>
    </div>
  );
}
