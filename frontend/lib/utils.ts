import type { LeadStatus } from "./types";

export const STATUS_META: Record<
  LeadStatus,
  { label: string; dot: string; badge: string; soft: string }
> = {
  new: {
    label: "Новый",
    dot: "bg-sky-400",
    badge: "border-sky-400/30 bg-sky-400/10 text-sky-300",
    soft: "text-sky-300",
  },
  database: {
    label: "В базе",
    dot: "bg-violet-400",
    badge: "border-violet-400/30 bg-violet-400/10 text-violet-300",
    soft: "text-violet-300",
  },
  sent: {
    label: "Отправлено",
    dot: "bg-amber-400",
    badge: "border-amber-400/30 bg-amber-400/10 text-amber-300",
    soft: "text-amber-300",
  },
  rejected: {
    label: "Отказ",
    dot: "bg-rose-400",
    badge: "border-rose-400/30 bg-rose-400/10 text-rose-300",
    soft: "text-rose-300",
  },
  deal: {
    label: "Сделка",
    dot: "bg-emerald-400",
    badge: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    soft: "text-emerald-300",
  },
};

export const CATEGORY_STYLES: Record<string, string> = {
  Бьюти: "border-rose-400/25 bg-rose-400/10 text-rose-300",
  Рестораны: "border-amber-400/25 bg-amber-400/10 text-amber-300",
  Автосервисы: "border-cyan-400/25 bg-cyan-400/10 text-cyan-300",
  Медицина: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  Фитнес: "border-lime-400/25 bg-lime-400/10 text-lime-300",
  Отели: "border-sky-400/25 bg-sky-400/10 text-sky-300",
  Услуги: "border-violet-400/25 bg-violet-400/10 text-violet-300",
  Магазины: "border-fuchsia-400/25 bg-fuchsia-400/10 text-fuchsia-300",
};

export const SOURCE_LABELS: Record<string, string> = {
  demo: "Demo-данные",
  google: "Google Places",
  twogis: "2GIS",
  yandex: "Яндекс Карты",
  yandex_web: "Яндекс Карты (web)",
  osm: "OpenStreetMap",
  scraper: "Google Maps Scraper",
  vk: "ВКонтакте",
  zoon: "Zoon.ru",
};

export const ALL_STATUSES: LeadStatus[] = ["new", "database", "sent", "rejected", "deal"];

export const POPULAR_CITIES: string[] = [
  "Москва",
  "Санкт-Петербург",
  "Новосибирск",
  "Екатеринбург",
  "Казань",
  "Нижний Новгород",
  "Челябинск",
  "Красноярск",
  "Самара",
  "Уфа",
  "Ростов-на-Дону",
  "Краснодар",
  "Омск",
  "Воронеж",
  "Пермь",
  "Волгоград",
  "Саратов",
  "Тюмень",
  "Тольятти",
  "Барнаул",
  "Ижевск",
  "Махачкала",
  "Хабаровск",
  "Ульяновск",
  "Иркутск",
  "Владивосток",
  "Ярославль",
  "Кемерово",
  "Томск",
  "Набережные Челны",
  "Севастополь",
  "Ставрополь",
  "Оренбург",
  "Новокузнецк",
  "Рязань",
  "Балашиха",
  "Пенза",
  "Чебоксары",
  "Липецк",
  "Калининград",
  "Астрахань",
  "Тула",
  "Киров",
  "Сочи",
  "Курск",
  "Улан-Удэ",
  "Сургут",
  "Тверь",
  "Магнитогорск",
  "Иваново",
  "Брянск",
  "Белгород",
  "Владимир",
  "Чита",
  "Архангельск",
  "Калуга",
  "Смоленск",
  "Саранск",
  "Череповец",
  "Курган",
  "Вологда",
  "Орёл",
  "Владикавказ",
  "Подольск",
  "Грозный",
  "Мурманск",
  "Тамбов",
  "Петрозаводск",
  "Стерлитамак",
  "Кострома",
  "Нижневартовск",
  "Новороссийск",
  "Йошкар-Ола",
  "Таганрог",
  "Сыктывкар",
  "Нальчик",
  "Шахты",
  "Дзержинск",
  "Благовещенск",
  "Великий Новгород",
  "Псков",
  "Симферополь",
  "Якутск",
];

export function categoryStyle(category: string): string {
  return CATEGORY_STYLES[category] ?? "border-white/10 bg-white/[0.04] text-slate-300";
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("ru-RU").format(value);
}

export function formatDate(value: string): string {
  try {
    return new Intl.DateTimeFormat("ru-RU", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }).format(new Date(value));
  } catch {
    return "";
  }
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function phoneDigits(phone: string | null | undefined): string {
  return (phone ?? "").replace(/\D/g, "");
}

export function mapsUrl(lead: { latitude: number | null; longitude: number | null; address: string; name: string }): string {
  if (lead.latitude && lead.longitude) {
    return `https://yandex.ru/maps/?pt=${lead.longitude},${lead.latitude}&z=17&l=map`;
  }
  return `https://yandex.ru/maps/?text=${encodeURIComponent(`${lead.name} ${lead.address}`)}`;
}

export function mapEmbedUrl(latitude: number, longitude: number): string {
  return `https://yandex.ru/map-widget/v1/?ll=${longitude}%2C${latitude}&z=16&pt=${longitude}%2C${latitude}%2Cpm2rdm&l=map`;
}

export function socialCount(links: Record<string, string | undefined>): number {
  return Object.values(links ?? {}).filter(Boolean).length;
}
