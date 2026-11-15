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

export const WEBSITE_STATUS_META = {
  no_website: {
    label: "Без сайта",
    badge: "border-rose-500/25 bg-rose-500/10 text-rose-400",
    dot: "bg-rose-400",
    description: "Сайта нет — максимальный потенциал для продажи",
  },
  only_social: {
    label: "Только соцсети",
    badge: "border-purple-500/30 bg-[rgba(139,92,246,0.14)] text-[#C4B5FD]",
    dot: "bg-[#8B5CF6] shadow-[0_0_6px_rgba(139,92,246,0.5)]",
    description: "Ведут соцсети, но теряют клиентов из поиска без сайта",
  },
  weak_website: {
    label: "Слабый сайт",
    badge: "border-amber-500/25 bg-amber-500/10 text-[#F59E0B]",
    dot: "bg-[#F59E0B]",
    description: "Конструктор / без HTTPS / устаревший мобильный вид",
  },
  has_website: {
    label: "Есть сайт",
    badge: "border-emerald-500/25 bg-[rgba(16,185,129,0.12)] text-[#10B981]",
    dot: "bg-[#10B981]",
    description: "Полноценный рабочий сайт",
  },
};

export function getWebsiteStatus(lead: {
  website_status?: string;
  website_url?: string | null;
  has_website?: boolean;
  social_links?: Record<string, string | undefined>;
}): "no_website" | "only_social" | "weak_website" | "has_website" {
  if (
    lead.website_status &&
    ["no_website", "only_social", "weak_website", "has_website"].includes(lead.website_status)
  ) {
    return lead.website_status as any;
  }

  const socials = lead.social_links ?? {};
  const hasSocials = Object.values(socials).some(Boolean);
  const url = (lead.website_url ?? "").trim().toLowerCase();

  if (!url) {
    return hasSocials ? "only_social" : "no_website";
  }

  const weakBuilders = [
    "tilda.ws",
    "wixsite.com",
    "taplink.cc",
    "ucoz.",
    "blogspot.",
    "wordpress.com",
    "sites.google.com",
    "timeweb.me",
    "nethouse.ru",
    "setup.ru",
    "insales.ru",
    "linktr.ee",
    "msto.me",
  ];

  const isBuilder = weakBuilders.some((builder) => url.includes(builder));
  const isInsecure = url.startsWith("http://");

  if (isBuilder || isInsecure) {
    return "weak_website";
  }

  return "has_website";
}

export function getLeadScore(lead: {
  lead_score?: number;
  website_status?: string;
  website_url?: string | null;
  has_website?: boolean;
  phone?: string | null;
  rating?: number | null;
  reviews_count?: number;
  social_links?: Record<string, string | undefined>;
}): number {
  if (typeof lead.lead_score === "number" && lead.lead_score > 0) {
    return lead.lead_score;
  }

  const status = getWebsiteStatus(lead);
  let score = 1.0;

  if (status === "only_social") score += 2.0;
  else if (status === "no_website" || status === "weak_website") score += 1.8;
  else score += 0.4;

  if (lead.phone && lead.phone.trim()) score += 0.8;

  if (lead.rating) {
    if (lead.rating >= 4.5) score += 0.8;
    else if (lead.rating >= 4.0) score += 0.5;
    else if (lead.rating >= 3.0) score += 0.3;
  }

  const reviews = lead.reviews_count ?? 0;
  if (reviews > 10) score += 0.4;
  else if (reviews > 0) score += 0.2;

  return Math.min(5.0, Math.round(score * 10) / 10);
}

export function getLeadScoreBadge(score: number): {
  text: string;
  bg: string;
  border: string;
  label: string;
} {
  if (score >= 4.2) {
    return {
      text: "text-amber-400",
      bg: "bg-amber-400/10",
      border: "border-amber-400/30",
      label: "Hot Lead",
    };
  }
  if (score >= 3.2) {
    return {
      text: "text-[#C4B5FD]",
      bg: "bg-[rgba(139,92,246,0.14)]",
      border: "border-[#8B5CF6]/30",
      label: "Warm Lead",
    };
  }
  return {
    text: "text-slate-400",
    bg: "bg-white/[0.04]",
    border: "border-white/10",
    label: "Lead",
  };
}

export function getGrowthPoints(lead: {
  growth_points?: string[];
  website_status?: string;
  website_url?: string | null;
  has_website?: boolean;
  social_links?: Record<string, string | undefined>;
}): string[] {
  if (lead.growth_points && lead.growth_points.length > 0) {
    return lead.growth_points;
  }

  const status = getWebsiteStatus(lead);
  if (status === "no_website") {
    return [
      "Теряют до 60% горячих заявок из поиска Яндекс и Google — клиенты уходят к конкурентам с сайтом.",
      "Нет онлайн-записи и витрины услуг 24/7 — клиенты в нерабочее время не могут оставить заявку.",
      "Полная зависимость от одного источника на картах без собственного управляемого канала продаж.",
    ];
  }
  if (status === "only_social") {
    return [
      "Холодный трафик из соцсетей не конвертируется: клиентам тяжело найти каталог услуг и прайс в ленте.",
      "Высокий риск блокировок и просадки охватов соцсетей без своего независимого сайта компании.",
      "Менеджеры тратят часы на ручные ответы в чате вместо автоматического приема заказов с сайта.",
    ];
  }
  if (status === "weak_website") {
    return [
      "Сайт на конструкторе или без SSL-сертификата (HTTPS) отпугивает клиентов предупреждением браузера.",
      "Устаревшая или медленная мобильная версия приводит к уходу до 45% посетителей со смартфонов.",
      "Отсутствие современной продающей структуры снижает конверсию переходов в реальные звонки.",
    ];
  }
  return [
    "Сайт требует обновления мобильной конверсии и прямого подключения к Telegram и WhatsApp.",
    "Возможность поднять конверсию существующего трафика за счет современного редизайна и оффера.",
  ];
}

export function getFirstTouchOffer(
  lead: {
    first_touch_offer?: string;
    name: string;
    city: string;
    rating?: number | null;
  },
  demoUrl?: string | null
): string {
  const ratingPart = lead.rating ? `с отличным рейтингом ${lead.rating.toFixed(1)}★` : "на картах";
  const urlPart = demoUrl
    ? `\n\nСпециально для вас мы набросали визуальный концепт современного адаптивного сайта: ${demoUrl}\nПосмотрите с телефона, как это может выглядеть в живую.`
    : `\n\nСпециально для вашей компании мы подготовили визуальный концепт современного сайта. Могу прислать ссылку на демо?`;

  return (
    `Здравствуйте! Обратил внимание на компанию «${lead.name}» в г. ${lead.city} ${ratingPart}. ` +
    `Заметил, что у вас сильная репутация, но клиентам сложно быстро ознакомиться со всеми услугами онлайн.` +
    urlPart +
    `\n\nЕсли понравится, сможем адаптировать и запустить за 2-3 дня. Будет интересно взглянуть?`
  );
}

export function getTelegramUrl(lead: {
  phone?: string | null;
  social_links?: Record<string, string | undefined>;
}): string | null {
  const tg = lead.social_links?.telegram;
  if (tg) {
    if (tg.startsWith("http")) return tg;
    const username = tg.replace("@", "").trim();
    return `https://t.me/${username}`;
  }
  return null;
}

export function getWhatsAppUrl(
  lead: {
    phone?: string | null;
    social_links?: Record<string, string | undefined>;
  },
  text?: string
): string | null {
  const wa = lead.social_links?.whatsapp;
  const digits = phoneDigits(lead.phone);
  const msgParam = text ? `?text=${encodeURIComponent(text)}` : "";

  if (wa && wa.includes("wa.me")) {
    return text ? `${wa}${wa.includes("?") ? "&" : "?"}text=${encodeURIComponent(text)}` : wa;
  }
  if (digits) {
    return `https://wa.me/${digits}${msgParam}`;
  }
  return null;
}

export function generatePromptForLead(lead: {
  name: string;
  category: string;
  city: string;
  address?: string;
  phone?: string | null;
  rating?: number | null;
  reviews_count?: number;
  opening_hours?: string[];
  social_links?: Record<string, string | undefined>;
}): string {
  const hours = (lead.opening_hours ?? []).join(", ") || "Ежедневно 10:00–21:00";
  const socials = Object.entries(lead.social_links ?? {})
    .filter(([_, v]) => Boolean(v))
    .map(([k, v]) => `${k}: ${v}`)
    .join(", ") || "нет";

  return `Создай премиальный одностраничный конверсионный лендинг (landing page) для компании:
- Название: ${lead.name}
- Сфера/ниша: ${lead.category}
- Город: ${lead.city}
- Адрес: ${lead.address || "Центр города"}
- Телефон: ${lead.phone || "Уточняется"}
- Рейтинг: ${lead.rating ? lead.rating.toFixed(1) + "★" : "5.0★"} (${lead.reviews_count || 15} отзывов на картах)
- Часы работы: ${hours}
- Соцсети: ${socials}

Технические требования:
1. Валидный, самодостаточный HTML5 с CDN Tailwind CSS (<script src="https://cdn.tailwindcss.com"></script>).
2. Темный современный дизайн (графитово-серый фон #0D0E12, карточки #181920 с тонкими рамками, яркие акценты).
3. Mobile-first адаптивность: безупречный вид на смартфонах и десктопе.
4. Секции лендинга:
   - Шапка: логотип/название, город, кнопка звонка / WhatsApp.
   - Hero-блок: броский оффер под нишу, подзаголовок с выгодой, бейдж рейтинга, кнопка «Записаться / Оставить заявку».
   - Каталог популярных услуг с ценами в рублях.
   - 3 ключевых преимущества компании.
   - 2-3 реальных отзыва клиентов с оценкой 5 звёзд.
   - Контакты, адрес и интерактивные кнопки прямого звонка (tel:) и мессенджера (wa.me).
5. Не используй внешние картинки, требующие API. Используй качественные SVG-иконки или стильные эмодзи-плашки.

Верни ТОЛЬКО готовый HTML-код (от <!DOCTYPE html> до </html>) без пояснительного текста.`;
}
