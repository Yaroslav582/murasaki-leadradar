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
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {/* Bento 1: Без сайта */}
      <div className="card group relative flex flex-col justify-between p-3.5 sm:p-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-[#9CA3AF]">
            Без сайта
          </span>
          <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/[0.06] bg-[#242731] text-rose-400">
            <Globe2 size={14} />
          </div>
        </div>
        <div className="mt-2.5">
          <p className="font-mono text-2xl font-semibold tracking-tight text-[#F3F4F6] tabular-nums sm:text-[26px]">
            {formatNumber(noWebsite)}
          </p>
          <p className="mt-0.5 text-xs text-[#6B7280]">
            {total ? (
              <>
                <span className="font-mono tabular-nums tracking-tight">{Math.round((noWebsite / total) * 100)}%</span> базы
              </>
            ) : (
              "Готовы к сайту"
            )}
          </p>
        </div>
      </div>

      {/* Bento 2: С соцсетями */}
      <div className="card group relative flex flex-col justify-between p-3.5 sm:p-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-[#9CA3AF]">
            С соцсетями
          </span>
          <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/[0.06] bg-[#242731] text-[#8B5CF6]">
            <MessageCircle size={14} />
          </div>
        </div>
        <div className="mt-2.5">
          <p className="font-mono text-2xl font-semibold tracking-tight text-[#F3F4F6] tabular-nums sm:text-[26px]">
            {formatNumber(withSocial)}
          </p>
          <p className="mt-0.5 text-xs text-[#6B7280]">Прямой контакт в TG/IG</p>
        </div>
      </div>

      {/* Bento 3: Воронка лидов */}
      <div className="card col-span-2 relative p-3.5 sm:p-4 lg:col-span-2">
        <div className="relative">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-[#242731] border border-white/[0.06] text-[#8B5CF6]">
                <Radar size={13} />
              </span>
              <span className="text-xs font-medium text-[#9CA3AF]">
                Воронка лидов
              </span>
            </div>
            <button
              onClick={() => {
                triggerHaptic("light");
                onParse();
              }}
              className="inline-flex items-center gap-1 rounded-md border border-white/[0.06] bg-[#242731] px-2 py-0.5 text-xs font-medium text-[#9CA3AF] transition hover:bg-white/[0.08] hover:text-[#F3F4F6]"
            >
              <ArrowUpRight size={12} /> Собрать ещё
            </button>
          </div>

          <div className="mt-2.5 flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
            <span className="font-mono text-2xl font-semibold tracking-tight text-[#F3F4F6] tabular-nums sm:text-[28px]">
              {formatNumber(total)}
            </span>
            <span className="text-xs text-[#6B7280]">
              в базе · <span className="font-mono tabular-nums tracking-tight font-semibold text-[#10B981]">{formatNumber(deals)}</span> сделок
            </span>
          </div>

          {/* Лаконичный 4px сегментированный трекер: серый фон, фиолетовый в работе, зеленый для сделок */}
          <div className="mt-3 flex h-1 w-full overflow-hidden rounded-full bg-[#242731]">
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
