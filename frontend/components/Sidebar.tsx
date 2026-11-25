"use client";

import { Building2, Filter, Flame, Globe2, MapPin, MessageCircle, Phone, RotateCcw, SlidersHorizontal, Star, X } from "lucide-react";
import type { LeadFilters, LeadStatus, Meta } from "@/lib/types";
import { ALL_STATUSES, STATUS_META, SOURCE_LABELS, categoryStyle, formatNumber } from "@/lib/utils";
import { triggerHaptic } from "@/lib/telegram";

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

function Switch({ checked, onChange }: { checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => {
        triggerHaptic("medium");
        onChange(!checked);
      }}
      className={`relative h-5 w-9 shrink-0 rounded-full border transition ${
        checked ? "border-[#8B5CF6] bg-[#8B5CF6]" : "border-white/[0.08] bg-[#242731]"
      }`}
    >
      <span
        className={`absolute top-0.5 rounded-full bg-white shadow transition-all ${
          checked ? "left-[18px]" : "left-0.5"
        }`}
        style={{ height: 14, width: 14 }}
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
    (filters.onlyWeakOrBroken ? 1 : 0) +
    (filters.onlySocial ? 1 : 0) +
    (filters.onlyPhone ? 1 : 0) +
    (filters.minRating !== null ? 1 : 0);

  return (
    <aside className="flex h-full w-[280px] shrink-0 flex-col border-r border-[#22252A] bg-[#0D0E11] pt-2">
      <div className="flex items-center justify-between border-b border-white/[0.04] px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/[0.06] bg-[#242731] text-[#8B5CF6]">
            <SlidersHorizontal size={14} />
          </div>
          <div>
            <p className="text-sm font-semibold text-[#F3F4F6]">Фильтры</p>
            <p className="text-[11px] text-[#6B7280]">
              {activeCount ? (
                <>Активно: <span className="font-mono tabular-nums tracking-tight text-[#8B5CF6]">{activeCount}</span></>
              ) : (
                "Все лиды"
              )}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => {
              triggerHaptic("light");
              onReset();
            }}
            className="icon-btn !h-7 !w-7"
            title="Сбросить фильтры"
          >
            <RotateCcw size={13} />
          </button>
          {onClose ? (
            <button
              onClick={() => {
                triggerHaptic("light");
                onClose();
              }}
              className="icon-btn !h-7 !w-7 lg:hidden"
              title="Закрыть"
            >
              <X size={14} />
            </button>
          ) : null}
        </div>
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto px-4 py-5">
        <section className="space-y-2.5">
          <p className="label">Быстрые фильтры</p>

          <label className="flex cursor-pointer items-center justify-between gap-3">
            <span className="flex items-center gap-2 text-xs text-[#94A3B8]">
              <Globe2 size={14} className="text-rose-400" />
              Только без сайта
            </span>
            <Switch checked={filters.onlyNoWebsite} onChange={(value) => onChange({ onlyNoWebsite: value })} />
          </label>

          <label className="flex cursor-pointer items-center justify-between gap-3">
            <span className="flex items-center gap-2 text-xs text-[#D4D4D8]">
              <Flame size={14} className="text-amber-400" />
              Горячие (нет / сломан)
            </span>
            <Switch checked={Boolean(filters.onlyWeakOrBroken)} onChange={(value) => onChange({ onlyWeakOrBroken: value })} />
          </label>

          <label className="flex cursor-pointer items-center justify-between gap-3">
            <span className="flex items-center gap-2 text-xs text-[#9CA3AF]">
              <MessageCircle size={14} className="text-[#8B5CF6]" />
              Только с соцсетями
            </span>
            <Switch checked={filters.onlySocial} onChange={(value) => onChange({ onlySocial: value })} />
          </label>

          <label className="flex cursor-pointer items-center justify-between gap-3">
            <span className="flex items-center gap-2 text-xs text-[#9CA3AF]">
              <Phone size={14} className="text-[#10B981]" />
              Только с телефоном
            </span>
            <Switch checked={filters.onlyPhone} onChange={(value) => onChange({ onlyPhone: value })} />
          </label>
        </section>

        <section className="space-y-2.5">
          <p className="label flex items-center gap-1.5">
            <Star size={11} className="text-amber-400" /> Рейтинг
          </p>
          <div className="grid grid-cols-3 gap-1.5">
            {[
              { label: "Любой", value: null },
              { label: "4.0+", value: 4 },
              { label: "4.5+", value: 4.5 },
            ].map((option) => (
              <button
                key={option.label}
                onClick={() => {
                  triggerHaptic("light");
                  onChange({ minRating: option.value });
                }}
                className={`rounded-lg border px-2 py-1.5 text-xs font-medium transition ${
                  filters.minRating === option.value
                    ? "border-[rgba(139,92,246,0.3)] bg-[rgba(139,92,246,0.14)] text-[#C4B5FD]"
                    : "border-white/[0.06] bg-[#242731] text-[#9CA3AF] hover:border-white/20"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </section>

        <section className="space-y-2.5">
          <p className="label flex items-center gap-1.5">
            <MapPin size={11} className="text-[#8B5CF6]" /> Города
          </p>
          <div className="space-y-0.5">
            {(meta?.cities ?? []).map((city) => {
              const active = filters.cities.includes(city.value);
              return (
                <button
                  key={city.value}
                  onClick={() => {
                    triggerHaptic("light");
                    onChange({ cities: toggle(filters.cities, city.value) });
                  }}
                  className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-xs transition ${
                    active ? "bg-[rgba(139,92,246,0.14)] text-[#C4B5FD]" : "text-[#9CA3AF] hover:bg-[#242731] hover:text-[#F3F4F6]"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span
                      className={`flex h-3.5 w-3.5 items-center justify-center rounded border ${
                        active ? "border-[#8B5CF6] bg-[#8B5CF6]" : "border-white/20"
                      }`}
                    >
                      {active ? <span className="h-1.5 w-1.5 rounded-[1px] bg-white" /> : null}
                    </span>
                    {city.value}
                  </span>
                  <span className={`text-[10px] font-mono tabular-nums ${active ? "text-[#C4B5FD]" : "text-[#6B7280]"}`}>
                    {formatNumber(city.count)}
                  </span>
                </button>
              );
            })}
            {!meta?.cities.length ? <p className="text-xs text-[#6B7280]">Пока нет данных</p> : null}
          </div>
        </section>

        <section className="space-y-2.5">
          <p className="label flex items-center gap-1.5">
            <Building2 size={11} className="text-[#9CA3AF]" /> Ниши
          </p>
          <div className="flex flex-wrap gap-1">
            {(meta?.categories ?? []).map((category) => {
              const active = filters.categories.includes(category.value);
              return (
                <button
                  key={category.value}
                  onClick={() => {
                    triggerHaptic("light");
                    onChange({ categories: toggle(filters.categories, category.value) });
                  }}
                  className={`rounded-md border px-2 py-1 text-xs font-medium transition ${
                    active
                      ? "border-[rgba(139,92,246,0.3)] bg-[rgba(139,92,246,0.14)] text-[#C4B5FD]"
                      : "border-white/[0.06] bg-[#242731] text-[#9CA3AF] hover:border-white/20"
                  }`}
                >
                  {category.value}
                  <span className="ml-1 opacity-60 font-mono tabular-nums">{category.count}</span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="space-y-2.5">
          <p className="label flex items-center gap-1.5">
            <Filter size={11} className="text-[#8B5CF6]" /> Статус
          </p>
          <div className="flex flex-wrap gap-1">
            {ALL_STATUSES.map((status: LeadStatus) => {
              const active = filters.statuses.includes(status);
              const metaItem = STATUS_META[status];
              return (
                <button
                  key={status}
                  onClick={() => onChange({ statuses: toggle(filters.statuses, status) })}
                  className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium transition ${
                    active ? metaItem.badge : "border-white/[0.06] bg-[#242731] text-[#9CA3AF] hover:border-white/20"
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
          <section className="space-y-2.5">
            <p className="label">Источник</p>
            <div className="flex flex-wrap gap-1">
              {(meta?.sources ?? []).map((source) => {
                const active = filters.sources.includes(source.value);
                return (
                  <button
                    key={source.value}
                    onClick={() => onChange({ sources: toggle(filters.sources, source.value) })}
                    className={`rounded-md border px-2 py-1 text-xs font-medium transition ${
                      active
                        ? "border-[rgba(139,92,246,0.3)] bg-[rgba(139,92,246,0.14)] text-[#C4B5FD]"
                        : "border-white/[0.06] bg-[#242731] text-[#9CA3AF] hover:border-white/20"
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

      <div className="border-t border-white/[0.04] px-4 py-3">
        <div className="rounded-lg border border-white/[0.06] bg-[#242731] p-2.5">
          <p className="text-[11px] leading-relaxed text-[#9CA3AF]">
            Фокус на компаниях <span className="text-rose-400 font-medium">без сайта</span> — конверсия в ответ выше в 3.5 раза.
          </p>
        </div>
      </div>
    </aside>
  );
}
