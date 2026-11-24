"use client";

import { useMemo, useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronUp,
  FileCode,
  Palette,
  Sparkles,
  Wand2,
  X,
} from "lucide-react";
import type { DesignStyle, Lead } from "@/lib/types";
import { triggerHaptic } from "@/lib/telegram";
import Modal from "./Modal";
import { Spinner } from "./ui";

export const BUILTIN_STYLES: DesignStyle[] = [
  {
    id: "dark_cyber_neon",
    name: "Dark Cyber Neon",
    name_ru: "Тёмный кибер / Неон",
    description: "Глубокий графитовый холст, неоновые оранжево-бирюзовые акценты, технологичные бейджи и матовая эстетика. Вдохновлен авто-презентациями и кибер-интерфейсами.",
    tags: ["Авто", "Детейлинг", "IT / AI", "Киберспорт", "Сервисы", "Спорт"],
    tone: "dark",
    preview_colors: {
      bg: "#08090C",
      card: "#12141C",
      accent: "#FF4500",
      text: "#F8FAFC",
      subtext: "#94A3B8",
      badge_bg: "#1E2230",
    },
    font_heading: "Unbounded",
    font_body: "Inter",
    recommended_niches: ["авто", "сервис", "шиномонтаж", "детейлинг", "мойка", "кузов", "сто", "ремонт авто", "it", "компьютер", "техник", "кибер"],
  },
  {
    id: "warm_artisan_coffee",
    name: "Warm Artisan Coffee",
    name_ru: "Тёплый крафт и кофе",
    description: "Уютная пергаментная палитра, аппетитные кофейно-карамельные акценты, элегантная антиква и крафтовая тактильность. Атмосфера тепла и свежей выпечки.",
    tags: ["Кофейни", "Пекарни", "Кондитерские", "Рестораны", "Доставка еды"],
    tone: "light",
    preview_colors: {
      bg: "#FAF6F0",
      card: "#FFFFFF",
      accent: "#C85A32",
      text: "#281D17",
      subtext: "#63534B",
      badge_bg: "#F2ECE4",
    },
    font_heading: "Playfair Display",
    font_body: "Plus Jakarta Sans",
    recommended_niches: ["ресторан", "кафе", "кофейн", "пекарн", "доставка еды", "выпечк", "кондитер", "чай"],
  },
  {
    id: "luxury_editorial",
    name: "Luxury Editorial",
    name_ru: "Премиум глянец и эстетика",
    description: "Элегантная журнальная эстетика, алебастровый фон, утончённые шрифты с засечками, шалфейные и золотые детали. Для бьюти-сферы и премиум-сегмента.",
    tags: ["Бьюти", "Косметология", "Спа", "Мода", "Парикмахерские", "Массаж"],
    tone: "light",
    preview_colors: {
      bg: "#F7F5F0",
      card: "#FFFFFF",
      accent: "#3E5848",
      text: "#18181B",
      subtext: "#52525B",
      badge_bg: "#EFEAE1",
    },
    font_heading: "Cormorant Garamond",
    font_body: "Inter",
    recommended_niches: ["бьюти", "красот", "маникюр", "педикюр", "волос", "парикмахер", "косметол", "одежд", "спа", "ногти", "брови", "массаж", "мода"],
  },
  {
    id: "acid_neo_brutalism",
    name: "Acid Neo-Brutalism",
    name_ru: "Кислотный нео-брутализм",
    description: "Дерзкий контраст тёмного графита и кислотно-лаймового (#D4FF00), массивный акцидентный гротеск, стикеры и резкая геометрия. Для агентств и ярких брендов.",
    tags: ["Digital-агентства", "Streetwear", "Студии", "Мерч", "Креатив", "Маркетинг"],
    tone: "vibrant",
    preview_colors: {
      bg: "#0D0E12",
      card: "#161822",
      accent: "#D4FF00",
      text: "#FFFFFF",
      subtext: "#CBD5E1",
      badge_bg: "#222533",
    },
    font_heading: "Syne",
    font_body: "Space Grotesk",
    recommended_niches: ["агентств", "дизайн", "digital", "маркетинг", "стритвер", "streetwear", "музык", "шоу", "креатив"],
  },
  {
    id: "clean_swiss_trust",
    name: "Clean Swiss Trust",
    name_ru: "Швейцарский минимализм",
    description: "Чистый белый холст, строгая сетка, королевский синий акцент, плашки гарантий и лицензий. Высочайший уровень солидности и доверия для B2B и медицины.",
    tags: ["Медицина", "Юристы", "Стоматология", "B2B", "Бухгалтерия", "Аудит"],
    tone: "light",
    preview_colors: {
      bg: "#F8FAFC",
      card: "#FFFFFF",
      accent: "#2563EB",
      text: "#0F172A",
      subtext: "#475569",
      badge_bg: "#EDF2F7",
    },
    font_heading: "Inter",
    font_body: "Inter",
    recommended_niches: ["медицин", "клиник", "стоматолог", "юрист", "адвокат", "бухгалтер", "аудит", "нотариус", "b2b", "недвижим"],
  },
  {
    id: "playful_pastel",
    name: "Playful Pastel & Sweet",
    name_ru: "Мягкая пастель и фреш",
    description: "Нежная ягодная палитра, мягкие скругления (pills), сочные малиново-клубничные акценты, дружелюбные округлые шрифты. Для десертов, бабл-ти и радости.",
    tags: ["Бабл-ти", "Десерты", "Торты", "Детские центры", "Подарки", "Праздники"],
    tone: "light",
    preview_colors: {
      bg: "#FFF4F6",
      card: "#FFFFFF",
      accent: "#E11D48",
      text: "#38141F",
      subtext: "#75394A",
      badge_bg: "#FFE4E8",
    },
    font_heading: "Comfortaa",
    font_body: "Plus Jakarta Sans",
    recommended_niches: ["бабл", "bubble", "мороженое", "торт", "десерт", "сладост", "дети", "детск", "подарк", "шары", "праздник"],
  },
  {
    id: "vintage_barber_leather",
    name: "Vintage Barber & Leather",
    name_ru: "Винтажный барбер и кожа",
    description: "Брутальная эстетика выделанной кожи, теплой латуни (#C28840) и дуба. Плотный ретро-гротеск Oswald, гербы, атмосфера мужского клуба и мастерства.",
    tags: ["Барбершопы", "Тату", "Мастерские", "Мужской клуб", "Кожгалантерея"],
    tone: "dark",
    preview_colors: {
      bg: "#1C1917",
      card: "#292524",
      accent: "#C28840",
      text: "#FAFAF9",
      subtext: "#A8A29E",
      badge_bg: "#3F3935",
    },
    font_heading: "Oswald",
    font_body: "Roboto",
    recommended_niches: ["барбер", "барбершоп", "тату", "мастерск", "кожа", "мужск", "брить"],
  },
  {
    id: "industrial_heavy_steel",
    name: "Industrial Heavy Steel",
    name_ru: "Индустриальный металл и стройка",
    description: "Мощный индустриальный характер: холодная сталь, дорожно-строительный янтарный акцент (#F59E0B), сверхтяжёлый монолитный шрифт Russo One и надёжность.",
    tags: ["Строительство", "Ремонт", "Спецтехника", "Металлопрокат", "Монтаж", "Производство"],
    tone: "dark",
    preview_colors: {
      bg: "#1E2022",
      card: "#2B2D31",
      accent: "#F59E0B",
      text: "#F3F4F6",
      subtext: "#9CA3AF",
      badge_bg: "#383B40",
    },
    font_heading: "Russo One",
    font_body: "Inter",
    recommended_niches: ["стройк", "строитель", "спецтехник", "металл", "бетон", "производств", "кран", "экскаватор", "кровл", "жби", "строймонтаж"],
  },
  {
    id: "organic_botanical_sage",
    name: "Organic Botanical Sage",
    name_ru: "Ботаника и эко-органика",
    description: "Спокойный шалфейный фон (#F3F6F2), глубокие лесные зелёные тона (#2D4A3E), воздушный шрифт Tenor Sans, дышащая верстка и природная утонченность.",
    tags: ["Цветы", "Эко-лавки", "Йога", "Флористика", "Органика", "Сад"],
    tone: "light",
    preview_colors: {
      bg: "#F3F6F2",
      card: "#FFFFFF",
      accent: "#2D4A3E",
      text: "#1A2821",
      subtext: "#4E6357",
      badge_bg: "#E5ECE3",
    },
    font_heading: "Tenor Sans",
    font_body: "Plus Jakarta Sans",
    recommended_niches: ["цветы", "флорист", "букет", "эко", "органик", "йог", "сад", "растени", "веган", "трав"],
  },
  {
    id: "tokyo_neo_izakaya",
    name: "Tokyo Neo-Izakaya",
    name_ru: "Японский стритфуд и суши",
    description: "Атмосфера вечернего Сибуя: глубокий графит (#121212), алые неоновые акценты (#E63946), плотная акцидентная типографика Dela Gothic One и яркие плашки меню.",
    tags: ["Суши", "Рамен", "Доставка еды", "Азиатская кухня", "Япония", "Стритфуд"],
    tone: "vibrant",
    preview_colors: {
      bg: "#121212",
      card: "#1E1E1E",
      accent: "#E63946",
      text: "#FDF0D5",
      subtext: "#A8A8A8",
      badge_bg: "#2A1F21",
    },
    font_heading: "Dela Gothic One",
    font_body: "Inter",
    recommended_niches: ["суши", "ролл", "рамен", "азиатск", "японск", "вок", "лапш", "том ям", "гёдза"],
  },
  {
    id: "kinetic_sport_volt",
    name: "Kinetic Sport Volt",
    name_ru: "Фитнес-драйв и энергия",
    description: "Высокооктановый спортивный стиль: тёмный фон спортзала (#0D0E12), агрессивный малиново-красный электро-акцент (#FF2A54), скошенные углы Chakra Petch.",
    tags: ["Фитнес", "Кроссфит", "Единоборства", "Тренажерный зал", "Спорт", "Бокс"],
    tone: "vibrant",
    preview_colors: {
      bg: "#0D0E12",
      card: "#171922",
      accent: "#FF2A54",
      text: "#FFFFFF",
      subtext: "#94A3B8",
      badge_bg: "#271822",
    },
    font_heading: "Chakra Petch",
    font_body: "Inter",
    recommended_niches: ["фитнес", "кроссфит", "единоборств", "бокс", "тренажер", "спортзал", "gym", "тренер", "бассейн", "борьб"],
  },
  {
    id: "bold_diner_grill",
    name: "Bold Diner & Grill",
    name_ru: "Сочный крафт и бургеры",
    description: "Аппетитный винтажный дайнер: теплый кремовый фон (#FFF8EB), сочный томатно-красный акцент (#DC2626), массивные монолитные плашки Rubik Mono One.",
    tags: ["Бургерные", "Пиццерии", "Стритфуд", "Гриль", "Барбекю", "Стейк-хаусы"],
    tone: "vibrant",
    preview_colors: {
      bg: "#FFF8EB",
      card: "#FFFFFF",
      accent: "#DC2626",
      text: "#2B1810",
      subtext: "#6B4F3B",
      badge_bg: "#FEEED4",
    },
    font_heading: "Rubik Mono One",
    font_body: "Plus Jakarta Sans",
    recommended_niches: ["бургер", "пицц", "гриль", "барбекю", "стейк", "шашлык", "мясо", "хот-дог", "пивн", "бургерн"],
  },
  {
    id: "architectural_brutal_loft",
    name: "Architectural Brutal Loft",
    name_ru: "Архитектурный бетон и лофт",
    description: "Монументальный архитектурный минимализм: текстурный бетон (#EAEAEA), строгие пропорции Space Grotesk, глубокая терракота (#B91C1C) и инженерная сетка.",
    tags: ["Интерьеры", "Мебель", "Недвижимость", "Архитектура", "Дизайн", "Лофт"],
    tone: "light",
    preview_colors: {
      bg: "#EAEAEA",
      card: "#FFFFFF",
      accent: "#B91C1C",
      text: "#171717",
      subtext: "#525252",
      badge_bg: "#DCDCDC",
    },
    font_heading: "Space Grotesk",
    font_body: "Inter",
    recommended_niches: ["интерьер", "мебел", "дизайн интерьер", "архитектур", "лофт", "фасад", "окна", "кухни на заказ"],
  },
  {
    id: "nordic_hygge_wood",
    name: "Nordic Hygge Wood",
    name_ru: "Скандинавский уют и дом",
    description: "Скандинавская философия хюгге: натуральный лен (#F9F7F4), светлая древесина (#D4A373), чистый шрифт Montserrat, много воздуха и ощущение чистоты.",
    tags: ["Клининг", "Химчистка", "Апартаменты", "Уютный дом", "Текстиль", "Отели"],
    tone: "light",
    preview_colors: {
      bg: "#F9F7F4",
      card: "#FFFFFF",
      accent: "#D4A373",
      text: "#262320",
      subtext: "#6E6862",
      badge_bg: "#EFE9E0",
    },
    font_heading: "Montserrat",
    font_body: "Inter",
    recommended_niches: ["клининг", "химчистк", "апартамент", "уборк", "стирк", "постель", "посуточно", "отель", "гостиниц"],
  },
  {
    id: "midnight_velvet_lounge",
    name: "Midnight Velvet Lounge",
    name_ru: "Ночной лаунж и кальянные",
    description: "Бархат ночи: глубокий аметистовый холст (#130D1A), неоновое фиолетовое свечение (#A855F7), дымчатые градиенты и кинематографичная римская антиква Cinzel.",
    tags: ["Кальянные", "Лаунж-бары", "Клубы", "Караоке", "Коктейль-бары", "Ночной отдых"],
    tone: "dark",
    preview_colors: {
      bg: "#130D1A",
      card: "#1E142B",
      accent: "#A855F7",
      text: "#FAF5FF",
      subtext: "#C084FC",
      badge_bg: "#2B1D3D",
    },
    font_heading: "Cinzel",
    font_body: "Plus Jakarta Sans",
    recommended_niches: ["кальян", "лаунж", "lounge", "бар", "клуб", "караоке", "коктейл", "ночн", "hookah"],
  },
  {
    id: "clean_tech_lab",
    name: "Clean Tech Lab",
    name_ru: "Техно-сервис и гаджеты",
    description: "Стерильная точность инженеров: светлый технологичный фон (#F4F6F9), моноширинный акцент JetBrains Mono, технический синий (#2563EB) и гарантийные бейджи.",
    tags: ["Ремонт техники", "Электроника", "Сервисные центры", "Смартфоны", "ПК", "IT-услуги"],
    tone: "light",
    preview_colors: {
      bg: "#F4F6F9",
      card: "#FFFFFF",
      accent: "#2563EB",
      text: "#0F172A",
      subtext: "#475569",
      badge_bg: "#E2E8F0",
    },
    font_heading: "JetBrains Mono",
    font_body: "Inter",
    recommended_niches: ["ремонт телефон", "ремонт техник", "сервисн", "apple", "ноутбук", "смартфон", "компьютерн", "электроник"],
  },
  {
    id: "nature_camp_glamping",
    name: "Nature Camp & Glamping",
    name_ru: "Эко-туризм и глэмпинг",
    description: "Хвойный лес и тепло костра: глубокий хвойный фон (#1A2E26), янтарный костровой акцент (#D97706), надежный брусковый шрифт Bitter и дух приключений.",
    tags: ["Глэмпинги", "Базы отдыха", "Туры", "Кемпинг", "Походы", "Эко-отели"],
    tone: "dark",
    preview_colors: {
      bg: "#1A2E26",
      card: "#243D33",
      accent: "#D97706",
      text: "#F4FBF7",
      subtext: "#96B9AA",
      badge_bg: "#304E42",
    },
    font_heading: "Bitter",
    font_body: "Plus Jakarta Sans",
    recommended_niches: ["глэмпинг", "база отдых", "тур", "поход", "кемпинг", "экскурси", "шале", "домик в лес", "сплав"],
  },
  {
    id: "modern_edtech_campus",
    name: "Modern EdTech Campus",
    name_ru: "Образование и академия",
    description: "Академическая структура и энергия прогресса: белоснежное пространство (#FFFFFF), умный ультрамарин (#4F46E5), шрифт Plus Jakarta Sans и лицензии.",
    tags: ["Автошколы", "Курсы", "Языковые школы", "Репетиторы", "Онлайн-школы", "Коучинг"],
    tone: "light",
    preview_colors: {
      bg: "#FFFFFF",
      card: "#F8FAFC",
      accent: "#4F46E5",
      text: "#0F172A",
      subtext: "#475569",
      badge_bg: "#EEF2FF",
    },
    font_heading: "Plus Jakarta Sans",
    font_body: "Inter",
    recommended_niches: ["автошкол", "курс", "языков", "школ", "обучени", "репетитор", "академи", "английск", "подготовк"],
  },
  {
    id: "friendly_pet_care",
    name: "Friendly Pet Care",
    name_ru: "Забота о питомцах",
    description: "Тепло, забота и профессиональный уход: мягкий сливочный фон (#FFF9F2), лечебный бирюзовый акцент (#0D9488), ласковый округлый шрифт Fredoka.",
    tags: ["Ветклиники", "Груминг", "Зоотовары", "Кинологи", "Передержка", "Ветврачи"],
    tone: "light",
    preview_colors: {
      bg: "#FFF9F2",
      card: "#FFFFFF",
      accent: "#0D9488",
      text: "#1C2D27",
      subtext: "#506960",
      badge_bg: "#E6F4F1",
    },
    font_heading: "Fredoka",
    font_body: "Plus Jakarta Sans",
    recommended_niches: ["ветклиник", "ветеринар", "груминг", "зоо", "питом", "собак", "кошек", "зоомагазин", "кинолог"],
  },
  {
    id: "obsidian_gold_luxury",
    name: "Obsidian & Gold Luxury",
    name_ru: "Ювелирный ночной шик",
    description: "Абсолютный обсидиановый эксклюзив: зеркальный черный бархат (#09090B), сияющее королевское золото (#D4AF37), высокая антиква Bodoni Moda и роскошь.",
    tags: ["Ювелирка", "Премиум-услуги", "VIP", "Часы", "Золото", "Антиквариат"],
    tone: "dark",
    preview_colors: {
      bg: "#09090B",
      card: "#141418",
      accent: "#D4AF37",
      text: "#FAFAFA",
      subtext: "#A1A1AA",
      badge_bg: "#27272A",
    },
    font_heading: "Bodoni Moda",
    font_body: "Montserrat",
    recommended_niches: ["ювелир", "золот", "бриллиант", "vip", "премиум", "часы", "украшени", "ломбард"],
  },
];

export function detectNicheStyle(category: string | undefined): string {
  const cat = (category || "").toLowerCase();

  // 1. Specialized Nightlife / Hookah / Club
  if (cat.includes("кальян") || cat.includes("лаунж") || cat.includes("lounge") || cat.includes("караоке") || cat.includes("hookah") || cat.includes("ночн") || cat.includes("коктейл")) {
    return "midnight_velvet_lounge";
  }

  // 2. Asian / Sushi / Ramen street food
  if (cat.includes("суши") || cat.includes("ролл") || cat.includes("рамен") || cat.includes("азиатск") || cat.includes("японск") || cat.includes("вок") || cat.includes("лапш") || cat.includes("том ям") || cat.includes("гёдза")) {
    return "tokyo_neo_izakaya";
  }

  // 3. Burgers / Pizza / Grill / BBQ
  if (cat.includes("бургер") || cat.includes("пицц") || cat.includes("гриль") || cat.includes("барбекю") || cat.includes("стейк") || cat.includes("шашлык") || cat.includes("мясо") || cat.includes("хот-дог") || cat.includes("пивн")) {
    return "bold_diner_grill";
  }

  // 4. Barber / Tattoo / Leather craft
  if (cat.includes("барбер") || cat.includes("барбершоп") || cat.includes("тату") || cat.includes("кожгалантере") || cat.includes("брить")) {
    return "vintage_barber_leather";
  }

  // 5. Sports / Fitness / Combat / Gym
  if (cat.includes("фитнес") || cat.includes("кроссфит") || cat.includes("единоборств") || cat.includes("бокс") || cat.includes("тренажер") || cat.includes("спортзал") || cat.includes("gym") || cat.includes("тренер") || cat.includes("бассейн") || cat.includes("борьб")) {
    return "kinetic_sport_volt";
  }

  // 6. Pets & Vet care
  if (cat.includes("ветклиник") || cat.includes("ветеринар") || cat.includes("груминг") || cat.includes("зоо") || cat.includes("питом") || cat.includes("собак") || cat.includes("кошек") || cat.includes("зоомагазин") || cat.includes("кинолог")) {
    return "friendly_pet_care";
  }

  // 7. Jewelry & Luxury / VIP
  if (cat.includes("ювелир") || cat.includes("золот") || cat.includes("бриллиант") || cat.includes("vip") || cat.includes("часы") || cat.includes("украшени") || cat.includes("ломбард")) {
    return "obsidian_gold_luxury";
  }

  // 8. Glamping & Nature tours
  if (cat.includes("глэмпинг") || cat.includes("база отдых") || cat.includes("тур") || cat.includes("поход") || cat.includes("кемпинг") || cat.includes("экскурси") || cat.includes("шале") || cat.includes("домик в лес") || cat.includes("сплав")) {
    return "nature_camp_glamping";
  }

  // 9. Flowers & Organic Botanical
  if (cat.includes("цветы") || cat.includes("флорист") || cat.includes("букет") || cat.includes("эко-лав") || cat.includes("органик") || cat.includes("йог") || cat.includes("сад") || cat.includes("растени") || cat.includes("веган") || cat.includes("трав")) {
    return "organic_botanical_sage";
  }

  // 10. Education / Courses / Driving school
  if (cat.includes("автошкол") || cat.includes("курс") || cat.includes("языков") || cat.includes("школ") || cat.includes("обучени") || cat.includes("репетитор") || cat.includes("академи") || cat.includes("английск") || cat.includes("подготовк")) {
    return "modern_edtech_campus";
  }

  // 11. Gadget & Tech repair
  if (cat.includes("ремонт телефон") || cat.includes("ремонт техник") || cat.includes("apple") || cat.includes("ноутбук") || cat.includes("смартфон") || cat.includes("компьютерн") || cat.includes("электроник")) {
    return "clean_tech_lab";
  }

  // 12. Auto, Detailing & Cyber
  if (cat.includes("авто") || cat.includes("сервис") || cat.includes("шиномонтаж") || cat.includes("детейлинг") || cat.includes("мойка") || cat.includes("кузов") || cat.includes("сто") || cat.includes("кибер") || cat.includes("gadget") || cat.includes("it-")) {
    return "dark_cyber_neon";
  }

  // 13. Heavy Steel & Construction
  if (cat.includes("стройк") || cat.includes("строитель") || cat.includes("спецтехник") || cat.includes("металл") || cat.includes("бетон") || cat.includes("производств") || cat.includes("кран") || cat.includes("экскаватор") || cat.includes("кровл") || cat.includes("жби") || cat.includes("строймонтаж")) {
    return "industrial_heavy_steel";
  }

  // 14. Architecture & Loft Furniture
  if (cat.includes("интерьер") || cat.includes("мебел") || cat.includes("дизайн интерьер") || cat.includes("архитектур") || cat.includes("лофт") || cat.includes("фасад") || cat.includes("окна") || cat.includes("кухни на заказ")) {
    return "architectural_brutal_loft";
  }

  // 15. Cleaning & Nordic Hygge
  if (cat.includes("клининг") || cat.includes("химчистк") || cat.includes("апартамент") || cat.includes("уборк") || cat.includes("стирк") || cat.includes("постель") || cat.includes("посуточно") || cat.includes("отель") || cat.includes("гостиниц")) {
    return "nordic_hygge_wood";
  }

  // 16. Sweet pastel (bubble tea, desserts, kids)
  if (cat.includes("бабл") || cat.includes("bubble") || cat.includes("мороженое") || cat.includes("торт") || cat.includes("десерт") || cat.includes("сладост") || cat.includes("дети") || cat.includes("детск") || cat.includes("подарк") || cat.includes("шары") || cat.includes("праздник")) {
    return "playful_pastel";
  }

  // 17. Creative & Digital Neo-brutalism
  if (cat.includes("digital") || cat.includes("диджитал") || cat.includes("агентств") || cat.includes("стритвер") || cat.includes("streetwear") || cat.includes("мерч") || cat.includes("продакшн") || cat.includes("креатив")) {
    return "acid_neo_brutalism";
  }

  // 18. Beauty & Fashion Editorial
  if (cat.includes("бьюти") || cat.includes("красот") || cat.includes("маникюр") || cat.includes("педикюр") || cat.includes("волос") || cat.includes("парикмахер") || cat.includes("косметол") || cat.includes("одежд") || cat.includes("спа") || cat.includes("ногти") || cat.includes("брови") || cat.includes("массаж") || cat.includes("мода")) {
    return "luxury_editorial";
  }

  // 19. Coffee & Bakery Craft
  if (cat.includes("кофе") || cat.includes("пекарн") || cat.includes("кондитер") || cat.includes("выпечк") || cat.includes("ресторан") || cat.includes("кафе") || cat.includes("доставка еды") || cat.includes("кухн") || cat.includes("чай")) {
    return "warm_artisan_coffee";
  }

  // 20. Default clean swiss trust
  return "clean_swiss_trust";
}

export default function StyleSelectModal({
  lead,
  availableStyles = BUILTIN_STYLES,
  onSelectStyle,
  onClose,
  generating = false,
}: {
  lead: Lead;
  availableStyles?: DesignStyle[];
  onSelectStyle: (styleId: string) => Promise<void> | void;
  onClose: () => void;
  generating?: boolean;
}) {
  const recommendedId = useMemo(() => detectNicheStyle(lead.category), [lead.category]);
  const [selectedId, setSelectedId] = useState<string>(recommendedId);
  const [toneFilter, setToneFilter] = useState<"all" | "dark" | "light" | "vibrant">("all");
  const [expandedSpecId, setExpandedSpecId] = useState<string | null>(null);

  // Filtered & sorted styles: AI recommendation always appears FIRST!
  const filteredAndSortedStyles = useMemo(() => {
    let list = availableStyles;
    if (toneFilter !== "all") {
      list = list.filter((s) => (s.tone || "light") === toneFilter);
    }
    // Sort so recommendedId is at index 0
    return [...list].sort((a, b) => {
      if (a.id === recommendedId) return -1;
      if (b.id === recommendedId) return 1;
      return 0;
    });
  }, [availableStyles, toneFilter, recommendedId]);

  // Counts for filter chips
  const counts = useMemo(() => {
    const total = availableStyles.length;
    const dark = availableStyles.filter((s) => s.tone === "dark").length;
    const light = availableStyles.filter((s) => s.tone === "light").length;
    const vibrant = availableStyles.filter((s) => s.tone === "vibrant").length;
    return { total, dark, light, vibrant };
  }, [availableStyles]);

  const selectedStyle = availableStyles.find((s) => s.id === selectedId) || availableStyles[0];

  const handleConfirm = () => {
    triggerHaptic("heavy");
    void onSelectStyle(selectedId);
  };

  const handleAutoSelect = () => {
    triggerHaptic("medium");
    setSelectedId(recommendedId);
    void onSelectStyle(recommendedId);
  };

  const handleCardSelect = (id: string) => {
    if (generating) return;
    triggerHaptic("light");
    setSelectedId(id);
  };

  return (
    <Modal open={true} onClose={onClose} zIndex="z-[100]" className="max-w-[1120px]">
      <div className="flex max-h-[92vh] flex-col overflow-hidden rounded-2xl border border-white/[0.08] bg-[#14161E] shadow-[0_20px_60px_rgba(0,0,0,0.7)] text-slate-100">
        
        {/* Шапка модалки */}
        <div className="flex items-center justify-between border-b border-white/[0.08] px-4 py-3 sm:px-6 sm:py-4 bg-[#181B26]">
          <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
            <div className="flex h-9 w-9 sm:h-10 sm:w-10 shrink-0 items-center justify-center rounded-xl border border-brand-500/40 bg-brand-500/15 text-brand-300 shadow-sm">
              <Palette size={18} />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
                <h2 className="text-sm sm:text-base font-extrabold text-white truncate">Выбор стиля сайта</h2>
                <span className="inline-flex items-center gap-1 rounded bg-gradient-to-r from-indigo-500/20 to-purple-500/20 px-1.5 sm:px-2 py-0.5 text-[9px] sm:text-[10px] font-mono font-bold uppercase tracking-wider text-indigo-300 border border-indigo-500/30">
                  <FileCode size={10} />
                  AWESOME-DESIGN-MD · 20 стилей
                </span>
              </div>
              <p className="text-[11px] sm:text-xs text-slate-400 truncate">
                <span className="font-semibold text-slate-200">{lead.name}</span> · <span className="font-semibold text-brand-300">{lead.category}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={generating}
            className="icon-btn shrink-0"
            aria-label="Закрыть"
          >
            <X size={18} />
          </button>
        </div>

        {/* AI Рекомендация баннер */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 sm:gap-3 border-b border-white/[0.06] bg-brand-500/[0.07] px-4 py-2.5 sm:px-6 sm:py-3">
          <div className="flex items-center gap-2 text-xs">
            <Sparkles size={15} className="text-brand-400 shrink-0" />
            <span className="text-slate-300 text-[11px] sm:text-xs leading-tight">
              AI подобрал под нишу «<span className="font-bold text-white">{lead.category}</span>»: стиль{" "}
              <span className="font-extrabold text-brand-300">
                {availableStyles.find((s) => s.id === recommendedId)?.name_ru || "Швейцарский минимализм"}
              </span>
            </span>
          </div>
          <button
            onClick={handleAutoSelect}
            disabled={generating}
            className="self-start sm:self-auto shrink-0 flex items-center gap-1.5 rounded-lg border border-brand-500/40 bg-brand-500/20 px-2.5 py-1 text-[11px] sm:text-xs font-bold text-brand-200 transition hover:bg-brand-500/30 active:scale-95"
          >
            <Wand2 size={12} />
            Применить автовыбор
          </button>
        </div>

        {/* Компактные чипсы-фильтры: Все (20), Тёмные (6), Светлые (10), Яркие (4) */}
        <div className="flex items-center gap-1.5 overflow-x-auto px-4 py-2.5 sm:px-6 border-b border-white/[0.06] bg-[#161822] scrollbar-none">
          <button
            type="button"
            onClick={() => {
              triggerHaptic("light");
              setToneFilter("all");
            }}
            className={`shrink-0 rounded-lg px-2.5 py-1 text-xs font-semibold transition active:scale-95 ${
              toneFilter === "all"
                ? "bg-brand-500 text-white shadow-sm ring-1 ring-brand-400"
                : "bg-white/[0.05] text-slate-300 hover:bg-white/[0.1] hover:text-white"
            }`}
          >
            Все ({counts.total})
          </button>
          <button
            type="button"
            onClick={() => {
              triggerHaptic("light");
              setToneFilter("dark");
            }}
            className={`shrink-0 flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-semibold transition active:scale-95 ${
              toneFilter === "dark"
                ? "bg-brand-500 text-white shadow-sm ring-1 ring-brand-400"
                : "bg-white/[0.05] text-slate-300 hover:bg-white/[0.1] hover:text-white"
            }`}
          >
            <span>🌙</span> Тёмные ({counts.dark})
          </button>
          <button
            type="button"
            onClick={() => {
              triggerHaptic("light");
              setToneFilter("light");
            }}
            className={`shrink-0 flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-semibold transition active:scale-95 ${
              toneFilter === "light"
                ? "bg-brand-500 text-white shadow-sm ring-1 ring-brand-400"
                : "bg-white/[0.05] text-slate-300 hover:bg-white/[0.1] hover:text-white"
            }`}
          >
            <span>☀️</span> Светлые ({counts.light})
          </button>
          <button
            type="button"
            onClick={() => {
              triggerHaptic("light");
              setToneFilter("vibrant");
            }}
            className={`shrink-0 flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-semibold transition active:scale-95 ${
              toneFilter === "vibrant"
                ? "bg-brand-500 text-white shadow-sm ring-1 ring-brand-400"
                : "bg-white/[0.05] text-slate-300 hover:bg-white/[0.1] hover:text-white"
            }`}
          >
            <span>⚡</span> Яркие ({counts.vibrant})
          </button>
        </div>

        {/* Сетка стилей */}
        <div className="flex-1 overflow-y-auto p-3.5 sm:p-6">
          <div className="grid gap-3 sm:gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            {filteredAndSortedStyles.map((style) => {
              const isSelected = selectedId === style.id;
              const isRecommended = recommendedId === style.id;
              const colors = style.preview_colors;
              const isExpanded = expandedSpecId === style.id;

              return (
                <div
                  key={style.id}
                  onClick={() => handleCardSelect(style.id)}
                  className={`group relative flex flex-col justify-between rounded-xl border p-3.5 sm:p-4 transition-all cursor-pointer active:scale-[0.99] ${
                    isSelected
                      ? "border-brand-500 bg-brand-500/[0.09] shadow-[0_0_24px_rgba(99,102,241,0.25)] ring-2 ring-brand-500/40"
                      : "border-white/[0.08] bg-[#171922] hover:border-white/20 hover:bg-[#1C1F2B]"
                  }`}
                >
                  {/* Верхние бейджи */}
                  <div className="flex items-center justify-between gap-2 mb-2.5">
                    <span className="text-xs font-mono font-bold text-slate-400">
                      {style.font_heading}
                    </span>
                    <div className="flex items-center gap-1.5">
                      {isRecommended && (
                        <span className="flex items-center gap-1 rounded-full bg-emerald-500/20 border border-emerald-500/40 px-2 py-0.5 text-[10px] font-bold text-emerald-300">
                          <Sparkles size={10} />
                          Рекомендация
                        </span>
                      )}
                      <div
                        className={`flex h-5 w-5 items-center justify-center rounded-full border transition ${
                          isSelected
                            ? "border-brand-500 bg-brand-500 text-white"
                            : "border-white/20 bg-white/5 text-transparent"
                        }`}
                      >
                        <Check size={12} strokeWidth={3} />
                      </div>
                    </div>
                  </div>

                  {/* Визуальная мини-карточка превью палитры и шрифта */}
                  <div
                    className="relative mb-3 overflow-hidden rounded-lg border p-3 shadow-inner transition group-hover:scale-[1.01]"
                    style={{
                      backgroundColor: colors.bg,
                      borderColor: colors.card === "#FFFFFF" ? "#E2E8F0" : "rgba(255,255,255,0.1)",
                    }}
                  >
                    <div
                      className="rounded-md p-2.5 shadow-sm"
                      style={{
                        backgroundColor: colors.card,
                        color: colors.text,
                      }}
                    >
                      <p
                        className="text-xs font-extrabold truncate"
                        style={{ color: colors.text }}
                      >
                        {style.name_ru}
                      </p>
                      <p
                        className="text-[10px] opacity-75 truncate"
                        style={{ color: colors.subtext || colors.text }}
                      >
                        Заголовок в стиле {style.font_heading}
                      </p>
                      
                      {/* Мини-кнопка акцента */}
                      <div className="mt-2.5 flex items-center justify-between">
                        <span
                          className="inline-block rounded px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider shadow-sm"
                          style={{
                            backgroundColor: colors.accent,
                            color: ["#D4FF00", "#F59E0B", "#FCD34D", "#D4AF37", "#00F2FE"].includes(colors.accent) ? "#000000" : "#FFFFFF",
                          }}
                        >
                          Кнопка CTA
                        </span>
                        
                        {/* Свотчи цветов */}
                        <div className="flex items-center gap-1">
                          <span
                            className="h-3 w-3 rounded-full border border-black/10"
                            style={{ backgroundColor: colors.bg }}
                            title="Фон страницы"
                          />
                          <span
                            className="h-3 w-3 rounded-full border border-black/10"
                            style={{ backgroundColor: colors.card }}
                            title="Фон карточки"
                          />
                          <span
                            className="h-3 w-3 rounded-full border border-black/10 shadow-sm"
                            style={{ backgroundColor: colors.accent }}
                            title="Цвет акцента (CTA)"
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Название и английский подзаголовок */}
                  <div className="mb-2">
                    <h3 className="text-sm font-extrabold text-white flex items-center gap-1.5">
                      {style.name_ru}
                    </h3>
                    <p className="text-[11px] font-mono font-medium text-slate-400">
                      {style.name}
                    </p>
                  </div>

                  {/* Описание стиля */}
                  <p className="text-xs leading-relaxed text-slate-300 line-clamp-2 mb-3">
                    {style.description}
                  </p>

                  {/* Теги ниш */}
                  <div className="flex flex-wrap gap-1 mb-3">
                    {style.tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-md bg-white/[0.04] border border-white/[0.06] px-1.5 py-0.5 text-[10px] text-slate-300"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>

                  {/* Сворачиваемая секция спецификации DESIGN.md */}
                  <div className="mt-auto pt-2.5 border-t border-white/[0.06]">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setExpandedSpecId(isExpanded ? null : style.id);
                      }}
                      className="flex items-center justify-between w-full text-[11px] text-brand-300 hover:text-brand-200 transition"
                    >
                      <span className="font-semibold flex items-center gap-1">
                        <FileCode size={11} />
                        DESIGN.md спецификация
                      </span>
                      {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    </button>

                    {isExpanded && (
                      <div className="mt-2 rounded-lg bg-black/40 border border-white/[0.06] p-2.5 font-mono text-[10px] text-slate-300 space-y-1 animate-fadeIn">
                        <div><span className="text-slate-500">canvas:</span> {colors.bg}</div>
                        <div><span className="text-slate-500">surface:</span> {colors.card}</div>
                        <div><span className="text-slate-500">accent:</span> {colors.accent}</div>
                        <div><span className="text-slate-500">heading:</span> {style.font_heading}</div>
                        <div><span className="text-slate-500">body:</span> {style.font_body}</div>
                        <div className="text-[9px] text-slate-500 italic mt-1">
                          Стандарт: Stitch / VoltAgent awesome-design-md
                        </div>
                      </div>
                    )}
                  </div>

                </div>
              );
            })}
          </div>
        </div>

        {/* Футер модалки */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-t border-white/[0.08] bg-[#181B26] px-4 py-3 sm:px-6 sm:py-4">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">
              Выбран стиль: <strong className="text-white">{selectedStyle.name_ru}</strong>
              <span className="hidden sm:inline text-slate-500 ml-1">({selectedStyle.name})</span>
            </span>
          </div>

          <div className="flex items-center gap-2 sm:gap-3 w-full sm:w-auto justify-end">
            <button
              onClick={onClose}
              disabled={generating}
              className="btn-ghost text-xs px-3 py-2"
            >
              Отмена
            </button>

            <button
              onClick={handleConfirm}
              disabled={generating}
              className="btn-primary flex-1 sm:flex-none flex items-center justify-center gap-2 px-4 sm:px-5 py-2.5 text-xs font-bold shadow-lg shadow-brand-500/25 active:scale-95"
            >
              {generating ? (
                <>
                  <Spinner size={15} />
                  <span>Генерация...</span>
                </>
              ) : (
                <>
                  <Sparkles size={14} />
                  <span>Сгенерировать ({selectedStyle.name_ru})</span>
                </>
              )}
            </button>
          </div>
        </div>

      </div>
    </Modal>
  );
}
