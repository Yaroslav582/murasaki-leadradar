"use client";

import { useEffect, useState } from "react";
import {
  Calendar,
  Check,
  Clock,
  Edit3,
  ExternalLink,
  Flame,
  Pause,
  Play,
  RefreshCw,
  Send,
  Sparkles,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import { triggerHaptic } from "@/lib/telegram";
import type { BlogStatus } from "@/lib/types";

export default function ChannelAutoBlogView({
  showToast,
}: {
  showToast: (message: string, variant?: "success" | "error" | "info") => void;
}) {
  const [status, setStatus] = useState<BlogStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Settings
  const [channelId, setChannelId] = useState("@Murasaki_website");
  const [intervalHours, setIntervalHours] = useState(24);

  // Post generation & preview
  const [selectedTopic, setSelectedTopic] = useState("");
  const [customTopic, setCustomTopic] = useState("");
  const [generating, setGenerating] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [previewTitle, setPreviewTitle] = useState<string | null>(null);
  const [previewText, setPreviewText] = useState<string | null>(null);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    setLoading(true);
    try {
      const s = await api.getBlogStatus();
      setStatus(s);
      setChannelId(s.channel_id);
      setIntervalHours(s.interval_hours);
    } catch (err) {
      console.error("Failed to load blog status:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleActive = async () => {
    if (!status) return;
    const next = !status.enabled;
    setSaving(true);
    triggerHaptic(next ? "success" : "light");
    try {
      const res = await api.updateBlogSettings({ enabled: next });
      setStatus((prev) => (prev ? { ...prev, enabled: res.enabled } : null));
      showToast(
        next ? "Автоблогер включен! Посты будут выходить по расписанию" : "Автоблогер поставлен на паузу",
        next ? "success" : "info"
      );
    } catch (err) {
      showToast("Ошибка сохранения настроек", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSettings = async (hours: number, ch: string) => {
    setSaving(true);
    triggerHaptic("light");
    try {
      const res = await api.updateBlogSettings({
        interval_hours: hours,
        channel_id: ch.trim(),
      });
      setStatus((prev) =>
        prev
          ? {
              ...prev,
              interval_hours: res.interval_hours,
              channel_id: res.channel_id,
            }
          : null
      );
      showToast("Настройки автоблогера обновлены", "success");
    } catch (err) {
      showToast("Ошибка сохранения", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleGeneratePreview = async () => {
    const topic = customTopic.trim() || selectedTopic || undefined;
    setGenerating(true);
    triggerHaptic("light");
    try {
      const res = await api.generateBlogPreview({
        topic_hint: topic,
        channel_id: channelId,
      });
      setPreviewTitle(res.title);
      setPreviewText(res.text);
      showToast("Экспертный пост сгенерирован!", "success");
    } catch (err) {
      showToast("Ошибка генерации поста", "error");
    } finally {
      setGenerating(false);
    }
  };

  const handlePublishNow = async () => {
    const topic = customTopic.trim() || selectedTopic || undefined;
    setPublishing(true);
    triggerHaptic("success");
    try {
      const res = await api.publishBlogNow({
        topic_hint: topic,
        channel_id: channelId,
      });
      setPreviewTitle(res.title);
      setPreviewText(res.text);
      showToast(`Пост успешно опубликован в ${channelId}! 🚀`, "success");
      await loadStatus();
    } catch (err) {
      showToast("Не удалось опубликовать пост в канал", "error");
    } finally {
      setPublishing(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Banner */}
      <div className="rounded-2xl border border-brand-500/20 bg-gradient-to-r from-brand-950/40 via-purple-950/20 to-transparent p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Sparkles className="text-amber-400" size={18} />
              AI-Автоблогер для Telegram-канала
            </h2>
            <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
              Нейросеть <strong>MXR (gpt-6-sol)</strong> регулярно пишет структурированные экспертные посты в твой канал
              раз в 24 часа. Темы: зачем бизнесу сайт, разборы ошибок, конверсии, Telegram Mini Apps, окупаемость и тренды.
              Каждый пост прогревает подписчиков и ведёт в портфолио!
            </p>
          </div>

          <button
            onClick={handleToggleActive}
            disabled={saving}
            className={`flex items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-xs font-bold transition shadow-lg shrink-0 ${
              status?.enabled
                ? "bg-emerald-500 text-white shadow-emerald-500/25 hover:bg-emerald-600"
                : "border border-white/10 bg-[#161616] text-slate-400 hover:text-white"
            }`}
          >
            {status?.enabled ? <Check size={14} /> : <Play size={14} />}
            {status?.enabled ? "Автоблогер включен (24 ч)" : "Включить автопостинг"}
          </button>
        </div>
      </div>

      {/* Settings Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Card 1: Channel & Interval */}
        <div className="rounded-2xl border border-white/10 bg-[#141414] p-5 space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2 border-b border-white/10 pb-3">
            <Calendar size={15} className="text-brand-400" />
            Канал и расписание публикаций
          </h3>

          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs text-slate-400">Целевой канал для постов:</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={channelId}
                  onChange={(e) => setChannelId(e.target.value)}
                  placeholder="@Murasaki_website"
                  className="flex-1 rounded-xl border border-white/10 bg-[#0d0d0d] px-3.5 py-2 text-xs text-white font-mono outline-none focus:border-brand-500"
                />
                <button
                  onClick={() => handleSaveSettings(intervalHours, channelId)}
                  disabled={saving}
                  className="rounded-xl border border-white/10 bg-[#222] px-3 py-2 text-xs font-semibold text-white hover:bg-brand-500 transition"
                >
                  Сохранить
                </button>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs text-slate-400">Периодичность автопостинга:</label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label: "12 часов", val: 12 },
                  { label: "24 часа (1 раз в день)", val: 24 },
                  { label: "48 часов (раз в 2 дня)", val: 48 },
                ].map((item) => (
                  <button
                    key={item.val}
                    type="button"
                    onClick={() => {
                      setIntervalHours(item.val);
                      handleSaveSettings(item.val, channelId);
                    }}
                    className={`rounded-xl p-2.5 text-center text-xs font-semibold transition ${
                      intervalHours === item.val
                        ? "border border-brand-500 bg-brand-500/20 text-brand-300"
                        : "border border-white/10 bg-[#0d0d0d] text-slate-400 hover:text-white"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-white/5 bg-black/30 p-3 flex items-center justify-between text-xs">
              <span className="text-slate-400 flex items-center gap-1.5">
                <Clock size={13} className="text-brand-400" />
                Следующий пост:
              </span>
              <span className="font-semibold text-emerald-400">
                {status?.enabled ? "По расписанию (через 24ч)" : "На паузе"}
              </span>
            </div>
          </div>
        </div>

        {/* Card 2: Interactive Sandbox */}
        <div className="rounded-2xl border border-white/10 bg-[#141414] p-5 space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2 border-b border-white/10 pb-3">
            <Flame size={15} className="text-amber-400" />
            Выбор темы или своя идея
          </h3>

          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs text-slate-400">Готовые экспертные темы из ротации:</label>
              <select
                value={selectedTopic}
                onChange={(e) => {
                  setSelectedTopic(e.target.value);
                  setCustomTopic("");
                }}
                className="w-full rounded-xl border border-white/10 bg-[#0d0d0d] p-2.5 text-xs text-white outline-none focus:border-brand-500"
              >
                <option value="">Случайная экспертная тема (ротация нейросети)</option>
                {status?.topics?.map((top, idx) => (
                  <option key={idx} value={top}>
                    {top}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-xs text-slate-400">Или напишите свою тему/заметку:</label>
              <input
                type="text"
                value={customTopic}
                onChange={(e) => {
                  setCustomTopic(e.target.value);
                  setSelectedTopic("");
                }}
                placeholder="Например: почему лендинг лучше группы в ВК"
                className="w-full rounded-xl border border-white/10 bg-[#0d0d0d] px-3.5 py-2 text-xs text-white outline-none focus:border-brand-500"
              />
            </div>

            <div className="flex gap-2 pt-1">
              <button
                onClick={handleGeneratePreview}
                disabled={generating}
                className="flex-1 flex items-center justify-center gap-1.5 rounded-xl border border-brand-500/30 bg-brand-500/10 py-2.5 text-xs font-semibold text-brand-300 hover:bg-brand-500/20 transition disabled:opacity-50"
              >
                {generating ? <RefreshCw className="animate-spin" size={13} /> : <Sparkles size={13} />}
                {generating ? "Генерация текста..." : "Предпросмотр поста"}
              </button>

              <button
                onClick={handlePublishNow}
                disabled={publishing}
                className="flex-1 flex items-center justify-center gap-1.5 rounded-xl bg-brand-500 py-2.5 text-xs font-bold text-white shadow-lg shadow-brand-500/25 hover:bg-brand-600 transition disabled:opacity-50"
              >
                {publishing ? <RefreshCw className="animate-spin" size={13} /> : <Send size={13} />}
                {publishing ? "Публикация..." : "Опубликовать сейчас 🚀"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Live Preview of Generated Post */}
      {previewText && (
        <div className="rounded-2xl border border-brand-500/30 bg-[#161616] p-5 space-y-3 animate-in fade-in duration-200">
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <div className="flex items-center gap-2">
              <span className="flex h-2 w-2 rounded-full bg-emerald-400" />
              <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400">
                Предпросмотр поста для {channelId}
              </h4>
            </div>
            <a
              href={`https://t.me/${channelId.replace("@", "")}`}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-slate-400 hover:text-white flex items-center gap-1 transition"
            >
              Открыть канал <ExternalLink size={12} />
            </a>
          </div>

          <div className="whitespace-pre-line rounded-xl border border-white/5 bg-black/40 p-4 text-xs text-slate-200 leading-relaxed font-sans">
            {previewText}
          </div>

          <div className="flex justify-end pt-2">
            <button
              onClick={handlePublishNow}
              disabled={publishing}
              className="flex items-center gap-2 rounded-xl bg-emerald-500 px-5 py-2.5 text-xs font-bold text-white shadow-lg shadow-emerald-500/25 hover:bg-emerald-600 transition disabled:opacity-50"
            >
              <Send size={13} />
              Опубликовать этот пост в канал
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
