"use client";

import { Building2, Filter, Globe2, MapPin, MessageCircle, Phone, RotateCcw, SlidersHorizontal, Star, X } from "lucide-react";
import type { LeadFilters, LeadStatus, Meta } from "@/lib/types";
import { ALL_STATUSES, STATUS_META, SOURCE_LABELS, categoryStyle, formatNumber } from "@/lib/utils";

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

function Switch({ checked, onChange }: { checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 shrink-0 rounded-full border transition ${
        checked ? "border-brand-500/60 bg-brand-500/80" : "border-white/10 bg-white/10"
      }`}
    >
      <span
        className={`absolute top-0.5 rounded-full bg-white shadow transition-all ${
          checked ? "left-[22px]" : "left-0.5"
        }`}
        style={{ height: 18, width: 18 }}
      />
    </button>
  );
}

export default function Sidebar({
  meta,
  filters,
  onChange,
  onReset,
  onClose,
}: {
  meta: Meta | null;
  filters: LeadFilters;
  onChange: (patch: Partial<LeadFilters>) => void;
  onReset: () => void;
  onClose?: () => void;
}) {
  const activeCount =
    filters.cities.length +
    filters.categories.length +
    filters.statuses.length +
    filters.sources.length +
    (filters.onlyNoWebsite ? 1 : 0) +
    (filters.onlySocial ? 1 : 0) +
    (filters.onlyPhone ? 1 : 0) +
    (filters.minRating !== null ? 1 : 0);

  return (
    <aside className="flex h-full w-[292px] shrink-0 flex-col border-r border-white/[0.06] bg-[#080a11]/95">
      <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-brand-500/30 bg-brand-500/15 text-brand-300">
            <SlidersHorizontal size={15} />
          </div>
          <div>
            <p className="text-sm font-bold text-white">Фильтры</p>
            <p className="text-[11px] text-slate-500">{activeCount ? `Активно: ${activeCount}` : "Все лиды"}</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={onReset} className="icon-btn" title="Сбросить фильтры">
            <RotateCcw size={14} />
          </button>
          {onClose ? (
            <button onClick={onClose} className="icon-btn lg:hidden" title="Закрыть">
              <X size={15} />
            </button>
          ) : null}
        </div>
      </div>

      <div className="flex-1 space-y-7 overflow-y-auto px-5 py-6">
        <section className="space-y-3">
          <p className="label">Быстрые фильтры</p>

          <label className="flex cursor-pointer items-center justify-between gap-3">
            <span className="flex items-center gap-2.5 text-sm text-slate-300">
              <Globe2 size={15} className="text-rose-300" />
              Только без сайта
            </span>
            <Switch checked={filters.onlyNoWebsite} onChange={(value) => onChange({ onlyNoWebsite: value })} />
          </label>

          <label className="flex cursor-pointer items-center justify-between gap-3">
            <span className="flex items-center gap-2.5 text-sm text-slate-300">
              <MessageCircle size={15} className="text-sky-300" />
              Только с соцсетями
            </span>
            <Switch checked={filters.onlySocial} onChange={(value) => onChange({ onlySocial: value })} />
          </label>

          <label className="flex cursor-pointer items-center justify-between gap-3">
            <span className="flex items-center gap-2.5 text-sm text-slate-300">
              <Phone size={15} className="text-emerald-300" />
              Только с телефоном
            </span>
            <Switch checked={filters.onlyPhone} onChange={(value) => onChange({ onlyPhone: value })} />
          </label>
        </section>

        <section className="space-y-3">
          <p className="label flex items-center gap-1.5">
            <Star size={12} className="text-amber-300" /> Рейтинг
          </p>
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: "Любой", value: null },
              { label: "4.0+", value: 4 },
              { label: "4.5+", value: 4.5 },
            ].map((option) => (
              <button
                key={option.label}
                onClick={() => onChange({ minRating: option.value })}
                className={`rounded-xl border px-2 py-2 text-xs font-semibold transition ${
                  filters.minRating === option.value
                    ? "border-brand-500/50 bg-brand-500/15 text-brand-300"
                    : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </section>

        <section className="space-y-3">
          <p className="label flex items-center gap-1.5">
            <MapPin size={12} className="text-brand-300" /> Города
          </p>
          <div className="space-y-1">
            {(meta?.cities ?? []).map((city) => {
              const active = filters.cities.includes(city.value);
              return (
                <button
                  key={city.value}
                  onClick={() => onChange({ cities: toggle(filters.cities, city.value) })}
                  className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-sm transition ${
                    active ? "bg-brand-500/15 text-brand-200" : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span
                      className={`flex h-3.5 w-3.5 items-center justify-center rounded-[4px] border ${
                        active ? "border-brand-400 bg-brand-500" : "border-white/20"
                      }`}
                    >
                      {active ? <span className="h-1.5 w-1.5 rounded-[2px] bg-white" /> : null}
                    </span>
                    {city.value}
                  </span>
                  <span className={`text-[11px] ${active ? "text-brand-300" : "text-slate-600"}`}>
                    {formatNumber(city.count)}
                  </span>
                </button>
              );
            })}
            {!meta?.cities.length ? <p className="text-xs text-slate-500">Пока нет данных</p> : null}
          </div>
        </section>

        <section className="space-y-3">
          <p className="label flex items-center gap-1.5">
            <Building2 size={12} className="text-cyan-300" /> Ниши
          </p>
          <div className="flex flex-wrap gap-1.5">
            {(meta?.categories ?? []).map((category) => {
              const active = filters.categories.includes(category.value);
              return (
                <button
                  key={category.value}
                  onClick={() => onChange({ categories: toggle(filters.categories, category.value) })}
                  className={`rounded-full border px-2.5 py-1.5 text-[11px] font-semibold transition ${
                    active ? categoryStyle(category.value) : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20"
                  }`}
                >
                  {category.value}
                  <span className="ml-1 opacity-60">{category.count}</span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="space-y-3">
          <p className="label flex items-center gap-1.5">
            <Filter size={12} className="text-violet-300" /> Статус
          </p>
          <div className="flex flex-wrap gap-1.5">
            {ALL_STATUSES.map((status: LeadStatus) => {
              const active = filters.statuses.includes(status);
              const metaItem = STATUS_META[status];
              return (
                <button
                  key={status}
                  onClick={() => onChange({ statuses: toggle(filters.statuses, status) })}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1.5 text-[11px] font-semibold transition ${
                    active ? metaItem.badge : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20"
                  }`}
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${metaItem.dot}`} />
                  {metaItem.label}
                </button>
              );
            })}
          </div>
        </section>

        {(meta?.sources?.length ?? 0) > 1 ? (
          <section className="space-y-3">
            <p className="label">Источник</p>
            <div className="flex flex-wrap gap-1.5">
              {(meta?.sources ?? []).map((source) => {
                const active = filters.sources.includes(source.value);
                return (
                  <button
                    key={source.value}
                    onClick={() => onChange({ sources: toggle(filters.sources, source.value) })}
                    className={`rounded-full border px-2.5 py-1.5 text-[11px] font-semibold transition ${
                      active
                        ? "border-brand-500/50 bg-brand-500/15 text-brand-300"
                        : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20"
                    }`}
                  >
                    {SOURCE_LABELS[source.value] ?? source.value}
                  </button>
                );
              })}
            </div>
          </section>
        ) : null}
      </div>

      <div className="border-t border-white/[0.06] px-5 py-4">
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
          <p className="text-[11px] leading-relaxed text-slate-500">
            Целевая аудитория — компании <span className="text-rose-300">без сайта</span>. Включите
            фильтр и генерируйте демо в один клик.
          </p>
        </div>
      </div>
    </aside>
  );
}
