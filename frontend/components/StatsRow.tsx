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
    <div className="grid grid-cols-2 divide-y divide-[#22252A] overflow-hidden rounded-xl border border-[#22252A] bg-[#121417] lg:grid-cols-4 lg:divide-x lg:divide-y-0">
      <div className="flex flex-col justify-between p-4">
        <div className="flex items-center justify-between text-xs text-[#71717A]">
          <span>Всего в базе</span>
          <Radar size={14} className="text-[#71717A]" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="font-mono text-2xl font-semibold tracking-tight text-[#F4F4F5] tabular-nums">
            {formatNumber(total)}
          </span>
          <span className="text-xs text-[#71717A]">
            <span className="font-mono text-emerald-400">{formatNumber(deals)}</span> сделок
          </span>
        </div>
      </div>

      <div className="flex flex-col justify-between p-4">
        <div className="flex items-center justify-between text-xs text-[#71717A]">
          <span>Без сайта</span>
          <Globe2 size={14} className="text-[#71717A]" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="font-mono text-2xl font-semibold tracking-tight text-[#F4F4F5] tabular-nums">
            {formatNumber(noWebsite)}
          </span>
          {total > 0 && (
            <span className="font-mono text-xs text-[#A1A1AA] tabular-nums">
              {Math.round((noWebsite / total) * 100)}%
            </span>
          )}
        </div>
      </div>

      <div className="flex flex-col justify-between p-4">
        <div className="flex items-center justify-between text-xs text-[#71717A]">
          <span>Есть мессенджеры</span>
          <MessageCircle size={14} className="text-[#71717A]" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="font-mono text-2xl font-semibold tracking-tight text-[#F4F4F5] tabular-nums">
            {formatNumber(withSocial)}
          </span>
          <span className="text-xs text-[#71717A]">
            <span className="font-mono text-[#A1A1AA]">{formatNumber(demos)}</span> демо
          </span>
        </div>
      </div>

      <div className="flex flex-col justify-between p-4">
        <div className="flex items-center justify-between text-xs text-[#71717A]">
          <span>Воронка</span>
          <button
            onClick={() => {
              triggerHaptic("light");
              onParse();
            }}
            className="inline-flex items-center gap-1 rounded-md border border-[#22252A] bg-[#181A1F] px-2 py-0.5 text-[11px] font-medium text-[#D4D4D8] transition hover:border-[#32363E] hover:text-white"
          >
            <ArrowUpRight size={11} /> Сбор
          </button>
        </div>
        <div className="mt-2">
          <div className="flex items-center justify-between text-xs text-[#A1A1AA]">
            <span>В работе: <strong className="font-mono text-[#F4F4F5]">{formatNumber(inWork)}</strong></span>
            <span className="font-mono text-emerald-400">{total ? Math.round((deals / total) * 100) : 0}%</span>
          </div>
          <div className="mt-2 flex h-1.5 w-full overflow-hidden rounded-full bg-[#1E2025]">
            {inWorkRatio > 0 && (
              <div className="bg-zinc-400 transition-all duration-500" style={{ width: `${inWorkRatio}%` }} />
            )}
            {dealRatio > 0 && (
              <div className="bg-emerald-500 transition-all duration-500" style={{ width: `${dealRatio}%` }} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
