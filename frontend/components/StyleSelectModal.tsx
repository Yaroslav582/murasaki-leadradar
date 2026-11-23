"use client";

import { useMemo, useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronUp,
  FileCode,
  Layers,
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
    tags: ["Авто", "Детейлинг", "IT / AI", "Киберспорт", "Барбершопы", "Спорт"],
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
    recommended_niches: ["авто", "сервис", "шиномонтаж", "детейлинг", "мойка", "кузов", "сто", "барбер", "спорт", "стройк", "it", "техник"],
  },
  {
    id: "warm_artisan_coffee",
    name: "Warm Artisan Coffee",
    name_ru: "Тёплый крафт и кофе",
    description: "Уютная пергаментная палитра, аппетитные кофейно-карамельные акценты, элегантная антиква и крафтовая тактильность. Атмосфера тепла и свежей выпечки.",
    tags: ["Кофейни", "Пекарни", "Кондитерские", "Рестораны", "Доставка еды"],
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
    recommended_niches: ["ресторан", "кафе", "кофейн", "пекарн", "доставка еды", "пицц", "суши", "бургер", "бар", "кухн", "кондитер", "еда"],
  },
  {
    id: "luxury_editorial",
    name: "Luxury Editorial",
    name_ru: "Премиум глянец и эстетика",
    description: "Элегантная журнальная эстетика, алебастровый фон, утончённые шрифты с засечками, шалфейные и золотые детали. Для бьюти-сферы и премиум-сегмента.",
    tags: ["Бьюти", "Косметология", "Спа", "Мода", "Архитектура", "Дизайн"],
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
    recommended_niches: ["бьюти", "красот", "маникюр", "педикюр", "волос", "парикмахер", "косметол", "цветы", "одежд", "спа", "ногти", "брови", "массаж"],
  },
  {
    id: "acid_neo_brutalism",
    name: "Acid Neo-Brutalism",
    name_ru: "Нео-брутализм и диджитал",
    description: "Дерзкий контраст тёмного графита и кислотно-лаймового (#D4FF00), массивный акцидентный гротеск, стикеры и резкая геометрия. Для агентств и ярких брендов.",
    tags: ["Digital-агентства", "Streetwear", "Тату", "Студии", "Мерч", "Креатив"],
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
    recommended_niches: ["агентств", "дизайн", "digital", "маркетинг", "тату", "стритвер", "streetwear", "музык", "шоу", "мото"],
  },
  {
    id: "clean_swiss_trust",
    name: "Clean Swiss Trust",
    name_ru: "Швейцарский минимализм",
    description: "Чистый белый холст, строгая сетка, королевский синий акцент, плашки гарантий и лицензий. Высочайший уровень солидности и доверия для B2B и медицины.",
    tags: ["Медицина", "Юристы", "Стоматология", "B2B", "Недвижимость", "Клининг"],
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
    recommended_niches: ["медицин", "клиник", "стоматолог", "юрист", "адвокат", "бухгалтер", "аудит", "нотариус", "b2b", "недвижим", "клининг", "ремонт"],
  },
  {
    id: "playful_pastel",
    name: "Playful Pastel & Sweet",
    name_ru: "Игривый пастельный и фреш",
    description: "Нежная ягодная палитра, мягкие скругления (pills), сочные малиново-клубничные акценты, дружелюбные округлые шрифты. Для десертов, бабл-ти и радости.",
    tags: ["Бабл-ти", "Десерты", "Торты", "Детские центры", "Зоосалоны", "Подарки"],
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
    recommended_niches: ["бабл-ти", "мороженое", "торт", "десерт", "сладост", "дети", "детск", "зоо", "груминг", "подарк", "шары", "праздник"],
  },
];

export function detectNicheStyle(category: string | undefined): string {
  const cat = (category || "").toLowerCase();
  for (const style of BUILTIN_STYLES) {
    if (style.recommended_niches.some((n) => cat.includes(n))) {
      return style.id;
    }
  }
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
  const [expandedSpecId, setExpandedSpecId] = useState<string | null>(null);

  const selectedStyle = availableStyles.find((s) => s.id === selectedId) || availableStyles[0];

  const handleConfirm = () => {
    triggerHaptic("medium");
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
    <Modal open={true} onClose={onClose} zIndex="z-[100]" className="max-w-[1080px]">
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
                  awesome-design-md
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

        {/* Сетка стилей */}
        <div className="flex-1 overflow-y-auto p-3.5 sm:p-6">
          <div className="grid gap-3 sm:gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            {availableStyles.map((style) => {
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
                  <div className="flex items-center justify-between gap-2 mb-3">
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
                    className="relative mb-3.5 overflow-hidden rounded-lg border p-3 shadow-inner transition group-hover:scale-[1.01]"
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
                            color: colors.accent === "#D4FF00" || colors.accent === "#FF4500" ? "#000000" : "#FFFFFF",
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
                            title="Карточки"
                          />
                          <span
                            className="h-3 w-3 rounded-full border border-black/10"
                            style={{ backgroundColor: colors.accent }}
                            title="Акцент"
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Описание стиля */}
                  <div>
                    <h3 className="text-sm font-extrabold text-white flex items-center justify-between">
                      {style.name_ru}
                      <span className="text-[10px] font-normal text-slate-500">
                        {style.name}
                      </span>
                    </h3>
                    <p className="mt-1 text-xs text-slate-400 leading-relaxed line-clamp-2">
                      {style.description}
                    </p>

                    {/* Теги ниш */}
                    <div className="mt-2.5 flex flex-wrap gap-1">
                      {style.tags.slice(0, 4).map((tag) => (
                        <span
                          key={tag}
                          className="rounded bg-white/[0.05] border border-white/[0.05] px-1.5 py-0.5 text-[10px] font-medium text-slate-300"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Токен-спецификация DESIGN.md (раскрывающаяся) */}
                  <div className="mt-3 pt-2.5 border-t border-white/[0.06]">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setExpandedSpecId(isExpanded ? null : style.id);
                      }}
                      className="flex w-full items-center justify-between text-[11px] font-medium text-slate-400 hover:text-brand-300"
                    >
                      <span className="flex items-center gap-1">
                        <FileCode size={12} />
                        DESIGN.md спецификация
                      </span>
                      {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                    </button>

                    {isExpanded && (
                      <div className="mt-2 rounded bg-black/50 p-2 font-mono text-[10px] text-slate-300 border border-white/10 space-y-1">
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
