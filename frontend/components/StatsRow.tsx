"use client";

import { ArrowUpRight, Globe2, MessageCircle, Radar, Sparkles, TrendingUp } from "lucide-react";
import type { Meta, Stats } from "@/lib/types";
import { formatNumber } from "@/lib/utils";
import { triggerHaptic } from "@/lib/telegram";

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
  const inWork = statuses.database + statuses.sent;
  const inWorkRatio = total ? (inWork / total) * 100 : 0;
  const dealRatio = total ? (deals / total) * 100 : 0;

  return (
    <div className="grid grid-cols-2 gap-3.5 lg:grid-cols-4">
      {/* Bento 1: Без сайта */}
      <div className="card group relative overflow-hidden p-4">
        <div className="pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-rose-500/10 blur-2xl transition group-hover:bg-rose-500/20" />
        <div className="relative flex items-center justify-between">
          <span className="text-xs font-medium text-[#94A3B8]">
            Без сайта
          </span>
          <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-rose-500/20 bg-rose-500/10 text-rose-400">
            <Globe2 size={15} />
          </div>
        </div>
        <div className="relative mt-3">
          <p className="font-display text-2xl font-bold tracking-tight text-[#F8FAFC] tabular-nums sm:text-[28px]">
            {formatNumber(noWebsite)}
          </p>
          <p className="mt-1 text-xs text-[#64748B]">
            {total ? (
              <>
                <span className="font-mono font-semibold text-rose-300 tabular-nums">{Math.round((noWebsite / total) * 100)}%</span> базы готовы к сайту
              </>
            ) : (
              "Готовы к сайту"
            )}
          </p>
        </div>
      </div>

      {/* Bento 2: С соцсетями */}
      <div className="card group relative overflow-hidden p-4">
        <div className="pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-violet-500/15 blur-2xl transition group-hover:bg-violet-500/25" />
        <div className="relative flex items-center justify-between">
          <span className="text-xs font-medium text-[#94A3B8]">
            С соцсетями
          </span>
          <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-violet-500/25 bg-violet-500/10 text-[#A78BFA]">
            <MessageCircle size={15} />
          </div>
        </div>
        <div className="relative mt-3">
          <p className="font-display text-2xl font-bold tracking-tight text-[#F8FAFC] tabular-nums sm:text-[28px]">
            {formatNumber(withSocial)}
          </p>
          <p className="mt-1 text-xs text-[#64748B]">
            Прямой контакт · <span className="font-mono font-semibold text-violet-300 tabular-nums">{formatNumber(demos)}</span> демо
          </p>
        </div>
      </div>

      {/* Bento 3: Воронка лидов */}
      <div className="card col-span-2 relative overflow-hidden p-4 lg:col-span-2">
        <div className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-emerald-500/10 blur-3xl" />
        <div className="relative">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-violet-500/15 border border-violet-500/25 text-[#A78BFA]">
                <Radar size={14} />
              </span>
              <span className="text-xs font-medium text-[#94A3B8]">
                Воронка лидов
              </span>
            </div>
            <button
              onClick={() => {
                triggerHaptic("light");
                onParse();
              }}
              className="inline-flex items-center gap-1 rounded-lg border border-white/[0.08] bg-white/[0.05] px-2.5 py-1 text-xs font-semibold text-[#CBD5E1] transition hover:border-violet-500/40 hover:bg-violet-500/15 hover:text-white"
            >
              <ArrowUpRight size={12} /> Собрать ещё
            </button>
          </div>

          <div className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="font-display text-2xl font-bold tracking-tight text-[#F8FAFC] tabular-nums sm:text-[30px]">
              {formatNumber(total)}
            </span>
            <span className="text-xs text-[#64748B]">
              в базе · <span className="font-mono tabular-nums font-semibold text-[#10B981]">{formatNumber(deals)}</span> сделок
            </span>
          </div>

          {/* Сегментированный трекер */}
          <div className="mt-3.5 flex h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
            {inWorkRatio > 0 && (
              <div
                className="bg-[#8B5CF6] transition-all duration-500"
                style={{ width: `${inWorkRatio}%` }}
                title={`В работе: ${inWork}`}
              />
            )}
            {dealRatio > 0 && (
              <div
                className="bg-[#10B981] transition-all duration-500"
                style={{ width: `${dealRatio}%` }}
                title={`Сделки: ${deals}`}
              />
            )}
          </div>

          {/* Легенда воронки без пестроты */}
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[#9CA3AF]">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-[#8B5CF6] shadow-[0_0_6px_rgba(139,92,246,0.4)]" />
              <span>В работе (<span className="font-mono tabular-nums tracking-tight text-[#F3F4F6]">{inWork}</span>)</span>
            </span>
            <span className="inline-flex items-center gap-1.5 text-emerald-400 font-medium">
              <span className="h-1.5 w-1.5 rounded-full bg-[#10B981] shadow-[0_0_6px_rgba(16,185,129,0.5)]" />
              <span>Сделки (<span className="font-mono tabular-nums tracking-tight">{deals}</span>)</span>
            </span>
            <span className="inline-flex items-center gap-1.5 text-[#6B7280]">
              <span className="h-1.5 w-1.5 rounded-full bg-[#323644]" />
              <span>Новые (<span className="font-mono tabular-nums tracking-tight">{statuses.new}</span>)</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
