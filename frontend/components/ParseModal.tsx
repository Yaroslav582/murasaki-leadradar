"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Bot, Check, Compass, Database, Globe2, Map, MapPin, Radar, Search, Sparkles, Store, Users, X } from "lucide-react";
import type { Meta, ParseRequest } from "@/lib/types";
import { CATEGORY_STYLES, POPULAR_CITIES } from "@/lib/utils";
import Modal from "./Modal";
import { Spinner } from "./ui";

const SOURCES: Array<{
  value: ParseRequest["source"];
  title: string;
  description: string;
  icon: React.ReactNode;
  badge: string;
  badgeClass: string;
}> = [
  {
    value: "demo",
    title: "Demo-база",
    description: "Готовые компании для теста. Работает без ключей",
    icon: <Database size={18} />,
    badge: "без ключа",
    badgeClass: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  },
  {
    value: "google",
    title: "Google Places",
    description: "Text Search + Place Details",
    icon: <MapPin size={18} />,
    badge: "API-ключ",
    badgeClass: "border-amber-400/25 bg-amber-400/10 text-amber-300",
  },
  {
    value: "twogis",
    title: "2GIS",
    description: "Каталог организаций, контакты",
    icon: <Map size={18} />,
    badge: "API-ключ",
    badgeClass: "border-amber-400/25 bg-amber-400/10 text-amber-300",
  },
  {
    value: "yandex",
    title: "Яндекс Карты",
    description: "Геопоиск API, русские данные",
    icon: <Compass size={18} />,
    badge: "API-ключ",
    badgeClass: "border-amber-400/25 bg-amber-400/10 text-amber-300",
  },
  {
    value: "yandex_web",
    title: "Яндекс Карты (web)",
    description: "Быстрый парсер без ключей и браузера",
    icon: <Compass size={18} />,
    badge: "бесплатно",
    badgeClass: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  },
  {
    value: "vk",
    title: "ВКонтакте",
    description: "Бизнес-сообщества и клиенты без сайта",
    icon: <Users size={18} />,
    badge: "бесплатно",
    badgeClass: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  },
  {
    value: "zoon",
    title: "Zoon.ru",
    description: "Каталог услуг, заведений и контакты",
    icon: <Store size={18} />,
    badge: "бесплатно",
    badgeClass: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  },
  {
    value: "osm",
    title: "OpenStreetMap",
    description: "Бесплатно, контакты из OSM",
    icon: <Globe2 size={18} />,
    badge: "бесплатно",
    badgeClass: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  },
  {
    value: "scraper",
    title: "Maps Scraper",
    description: "Playwright + резидентские прокси",
    icon: <Bot size={18} />,
    badge: "эксперимент",
    badgeClass: "border-rose-400/25 bg-rose-400/10 text-rose-300",
  },
];

const FALLBACK_CATEGORIES = [
  "Бьюти",
  "Рестораны",
  "Автосервисы",
  "Медицина",
  "Фитнес",
  "Отели",
  "Услуги",
  "Магазины",
];

export default function ParseModal({
  open,
  onClose,
  onSubmit,
  meta,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: ParseRequest) => Promise<void>;
  meta: Meta | null;
}) {
  const [source, setSource] = useState<ParseRequest["source"]>("demo");
  const [city, setCity] = useState("Москва");
  const [categories, setCategories] = useState<string[]>(["Бьюти", "Рестораны"]);
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(30);
  const [onlyNoWebsite, setOnlyNoWebsite] = useState(true);
  const [enrich, setEnrich] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cityDropdownOpen, setCityDropdownOpen] = useState(false);
  const cityContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      setError(null);
      setSubmitting(false);
      setCityDropdownOpen(false);
    }
  }, [open]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (cityContainerRef.current && !cityContainerRef.current.contains(e.target as Node)) {
        setCityDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const allCities = useMemo(() => {
    return [...new Set([...(meta?.cities ?? []).map((item) => item.value), ...POPULAR_CITIES])];
  }, [meta?.cities]);

  const filteredCities = useMemo(() => {
    const q = city.trim().toLowerCase();
    if (!q) return allCities.slice(0, 10);
    return allCities.filter((c) => c.toLowerCase().includes(q)).slice(0, 12);
  }, [allCities, city]);

  const categoriesAvailable = meta?.categories?.length
    ? meta.categories.map((item) => item.value)
    : FALLBACK_CATEGORIES;

  const toggleCategory = (value: string) => {
    setCategories((previous) =>
      previous.includes(value) ? previous.filter((item) => item !== value) : [...previous, value],
    );
  };

  const handleSubmit = async () => {
    if (!city.trim()) {
      setError("Укажите город");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        source,
        city: city.trim(),
        categories,
        query: query.trim() || null,
        limit,
        only_no_website: onlyNoWebsite,
        enrich,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось запустить сбор");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} className="max-w-2xl">
      <div className="max-h-[90vh] overflow-y-auto rounded-3xl border border-white/10 bg-[#0a0c15] shadow-2xl">
        <div className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b border-white/[0.07] bg-[#0a0c15]/95 px-6 py-5 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-brand-500/30 bg-brand-500/15 text-brand-300">
              <Radar size={19} />
            </div>
            <div>
              <h2 className="text-lg font-extrabold tracking-tight text-white">Сбор новых лидов</h2>
              <p className="text-xs text-slate-500">Выберите источник, город и ниши</p>
            </div>
          </div>
          <button onClick={onClose} className="icon-btn" aria-label="Закрыть">
            <X size={16} />
          </button>
        </div>

        <div className="space-y-6 px-6 py-5">
          <section className="space-y-3">
            <p className="label">Источник данных</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {SOURCES.map((option) => {
                const active = source === option.value;
                return (
                  <button
                    key={option.value}
                    onClick={() => setSource(option.value)}
                    className={`flex items-start gap-3 rounded-2xl border p-3.5 text-left transition ${
                      active
                        ? "border-brand-500/50 bg-brand-500/[0.1]"
                        : "border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]"
                    }`}
                  >
                    <div
                      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${
                        active ? "border-brand-500/40 bg-brand-500/15 text-brand-300" : "border-white/10 bg-white/[0.03] text-slate-400"
                      }`}
                    >
                      {option.icon}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <p className="text-sm font-bold text-white">{option.title}</p>
                        <span className={`rounded border px-1.5 py-0.5 text-[9px] font-bold uppercase ${option.badgeClass}`}>
                          {option.badge}
                        </span>
                      </div>
                      <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500">{option.description}</p>
                    </div>
                  </button>
                );
              })}
            </div>
            {source === "google" || source === "twogis" || source === "yandex" || source === "scraper" ? (
              <p className="rounded-xl border border-amber-400/15 bg-amber-400/[0.06] px-3 py-2 text-[11px] leading-relaxed text-amber-200/80">
                {source === "google"
                  ? "Нужен GOOGLE_PLACES_API_KEY. Google Maps Platform недоступен для российского биллинга — используйте 2GIS, Яндекс, OpenStreetMap или demo."
                  : source === "twogis"
                    ? "Ключ 2GIS указывается в backend/.env. Демо-ключ отдаёт ограниченный набор полей — часто без телефонов и сайтов."
                    : source === "yandex"
                      ? "Нужен YANDEX_MAPS_API_KEY (API Геопоиска, платный тариф Яндекс Карт). Ключ указывается в backend/.env."
                      : "Нужен Playwright и прокси. Источник экспериментальный и зависит от вёрстки карт."}
              </p>
            ) : source === "osm" ? (
              <p className="rounded-xl border border-emerald-400/15 bg-emerald-400/[0.06] px-3 py-2 text-[11px] leading-relaxed text-emerald-200/80">
                Бесплатный источник без ключей. Телефоны, сайты и соцсети берутся из тегов OSM,
                поэтому покрытие зависит от города и активности участников карты.
              </p>
            ) : source === "yandex_web" ? (
              <p className="rounded-xl border border-emerald-400/15 bg-emerald-400/[0.06] px-3 py-2 text-[11px] leading-relaxed text-emerald-200/80">
                Бесплатно и без ключей: прямой быстрый сбор данных с Яндекс.Карт (названия, телефоны,
                сайты, WhatsApp, Telegram, VK, рейтинги и часы работы) без необходимости запускать браузер.
              </p>
            ) : source === "vk" ? (
              <p className="rounded-xl border border-emerald-400/15 bg-emerald-400/[0.06] px-3 py-2 text-[11px] leading-relaxed text-emerald-200/80">
                Бесплатный поиск бизнес-сообществ ВКонтакте. Идеально для поиска компаний без сайта
                (автосервисы, салоны, клиники, мастера). Для работы укажите бесплатный VK_ACCESS_TOKEN в backend/.env (получается за 1 минуту на dev.vk.com).
              </p>
            ) : source === "zoon" ? (
              <p className="rounded-xl border border-emerald-400/15 bg-emerald-400/[0.06] px-3 py-2 text-[11px] leading-relaxed text-emerald-200/80">
                Бесплатный сбор из каталога заведений Zoon.ru: адреса, телефоны, рейтинги и отзывы
                по сферам услуг и городам.
              </p>
            ) : null}
          </section>

          <section className="grid gap-4 sm:grid-cols-2">
            <div ref={cityContainerRef} className="relative space-y-2">
              <p className="label flex items-center gap-1.5">
                <MapPin size={12} /> Город
              </p>
              <input
                value={city}
                onChange={(event) => {
                  setCity(event.target.value);
                  setCityDropdownOpen(true);
                }}
                onFocus={() => setCityDropdownOpen(true)}
                className="input"
                placeholder="Москва"
                autoComplete="off"
              />
              {cityDropdownOpen && filteredCities.length > 0 && (
                <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-56 overflow-y-auto rounded-xl border border-white/10 bg-[#161616] p-1 shadow-2xl backdrop-blur-md">
                  {filteredCities.map((cityName) => {
                    const isSelected = cityName.toLowerCase() === city.trim().toLowerCase();
                    return (
                      <button
                        key={cityName}
                        type="button"
                        onClick={() => {
                          setCity(cityName);
                          setCityDropdownOpen(false);
                        }}
                        className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs font-medium transition ${
                          isSelected
                            ? "bg-brand-500/20 text-brand-300 font-semibold"
                            : "text-slate-300 hover:bg-white/[0.06] hover:text-white"
                        }`}
                      >
                        <span>{cityName}</span>
                        {isSelected && <Check size={13} className="text-brand-400" />}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <p className="label flex items-center gap-1.5">
                <Search size={12} /> Ключевой запрос
              </p>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="input"
                placeholder="например, стоматология"
              />
            </div>
          </section>

          <section className="space-y-3">
            <p className="label flex items-center gap-1.5">
              <Globe2 size={12} /> Ниши
            </p>
            <div className="flex flex-wrap gap-2">
              {categoriesAvailable.map((value) => {
                const active = categories.includes(value);
                return (
                  <button
                    key={value}
                    onClick={() => toggleCategory(value)}
                    className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                      active
                        ? CATEGORY_STYLES[value] ?? "border-brand-500/50 bg-brand-500/15 text-brand-300"
                        : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20"
                    }`}
                  >
                    {value}
                  </button>
                );
              })}
            </div>
            <p className="text-[11px] text-slate-600">Ничего не выбрано — соберём по всем категориям.</p>
          </section>

          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="label">Сколько лидов собрать</p>
              <span className="rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs font-bold text-white">
                {limit}
              </span>
            </div>
            <input
              type="range"
              min={5}
              max={500}
              step={5}
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value))}
              className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-white/10 accent-brand-500"
            />
            <div className="flex justify-between text-[10px] text-slate-600">
              <span>5</span>
              <span>500</span>
            </div>
          </section>

          <section className="space-y-3 rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4">
            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={onlyNoWebsite}
                onChange={(event) => setOnlyNoWebsite(event.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-white/20 bg-white/10 accent-brand-500"
              />
              <span>
                <span className="block text-sm font-semibold text-white">Только без сайта</span>
                <span className="block text-[11px] text-slate-500">Главная целевая аудитория для продажи сайтов</span>
              </span>
            </label>
            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={enrich}
                onChange={(event) => setEnrich(event.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-white/20 bg-white/10 accent-brand-500"
              />
              <span>
                <span className="block text-sm font-semibold text-white">Обогатить контакты</span>
                <span className="block text-[11px] text-slate-500">
                  Просканируем сайты: Instagram, Telegram, WhatsApp, email
                </span>
              </span>
            </label>
          </section>

          {error ? (
            <p className="rounded-xl border border-rose-400/20 bg-rose-400/[0.08] px-3 py-2.5 text-xs leading-relaxed text-rose-200">
              {error}
            </p>
          ) : null}
        </div>

        <div className="sticky bottom-0 flex items-center justify-between gap-3 border-t border-white/[0.07] bg-[#0a0c15]/95 px-6 py-4 backdrop-blur">
          <p className="hidden items-center gap-1.5 text-[11px] text-slate-500 sm:flex">
            <Sparkles size={12} className="text-brand-300" />
            Задача выполняется в фоне — интерфейс не зависнет
          </p>
          <div className="flex w-full gap-2 sm:w-auto">
            <button onClick={onClose} className="btn-ghost flex-1 sm:flex-none">
              Отмена
            </button>
            <button onClick={handleSubmit} disabled={submitting} className="btn-primary flex-1 sm:flex-none">
              {submitting ? <Spinner size={15} /> : <Radar size={15} />}
              {submitting ? "Запускаем..." : "Собрать лиды"}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
