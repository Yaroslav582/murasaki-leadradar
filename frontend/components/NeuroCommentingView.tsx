"use client";

import { useEffect, useState } from "react";
import {
  Bot,
  Check,
  Clock,
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
  TrendingUp,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import { triggerHaptic } from "@/lib/telegram";
import type { CommentLog, CommentTarget } from "@/lib/types";

export default function NeuroCommentingView({
  showToast,
}: {
  showToast: (message: string, variant?: "success" | "error" | "info") => void;
}) {
  const [targets, setTargets] = useState<CommentTarget[]>([]);
  const [logs, setLogs] = useState<CommentLog[]>([]);
  const [loading, setLoading] = useState(true);

  // Modal add
  const [showAdd, setShowAdd] = useState(false);
  const [channelId, setChannelId] = useState("");
  const [channelTitle, setChannelTitle] = useState("");
  const [tone, setTone] = useState("expert");
  const [customPrompt, setCustomPrompt] = useState("");
  const [adding, setAdding] = useState(false);

  // Test AI Preview
  const [testPostText, setTestPostText] = useState(
    "Запустили новую версию мобильного приложения, но конверсия в первый заказ просела на 12%. Кто сталкивался с подобным при редизайне?"
  );
  const [testTone, setTestTone] = useState("expert");
  const [generating, setGenerating] = useState(false);
  const [generatedPreview, setGeneratedPreview] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [tList, lList] = await Promise.all([
        api.getCommentTargets(),
        api.getCommentLogs(),
      ]);
      setTargets(tList);
      setLogs(lList);
    } catch (err) {
      console.error("Failed to load commenting data:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddTarget = async () => {
    if (!channelId.trim()) return;
    setAdding(true);
    triggerHaptic("medium");
    try {
      const newTarget = await api.addCommentTarget({
        channel_id: channelId.trim(),
        title: channelTitle.trim() || undefined,
        tone,
        custom_prompt: customPrompt.trim() || undefined,
      });
      setTargets((prev) => [...prev, newTarget]);
      setShowAdd(false);
      setChannelId("");
      setChannelTitle("");
      setCustomPrompt("");
      showToast("Канал успешно добавлен для нейрокомментинга", "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Ошибка добавления канала", "error");
    } finally {
      setAdding(false);
    }
  };

  const handleDeleteTarget = async (id: string) => {
    triggerHaptic("heavy");
    try {
      await api.deleteCommentTarget(id);
      setTargets((prev) => prev.filter((t) => t.id !== id));
      showToast("Канал удален из списка", "info");
    } catch (err) {
      showToast("Не удалось удалить канал", "error");
    }
  };

  const handleTestGenerate = async () => {
    if (!testPostText.trim()) return;
    setGenerating(true);
    triggerHaptic("light");
    try {
      const res = await api.generateCommentPreview({
        post_text: testPostText,
        channel_title: "Стартапы & Технологии",
        tone: testTone,
      });
      setGeneratedPreview(res.comment_text);
      // Reload logs
      const updatedLogs = await api.getCommentLogs();
      setLogs(updatedLogs);
      showToast("AI-комментарий сгенерирован!", "success");
    } catch (err) {
      showToast("Ошибка генерации комментария", "error");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Banner / Explanation */}
      <div className="rounded-2xl border border-brand-500/20 bg-gradient-to-r from-brand-950/40 via-purple-950/20 to-transparent p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <Bot className="text-brand-400" size={18} />
                Нейрокомментинг постов в каналах
              </h2>
            </div>
            <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
              Бот отслеживает свежие посты в целевых каналах и мгновенно пишет умный экспертный или вовлекающий
              комментарий через <strong>MXR (gpt-6-sol)</strong>. Никакого спама — люди видят ценную мысль, открывают
              профиль Murasaki и переходят в портфолио!
            </p>
          </div>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center justify-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-xs font-bold text-white shadow-lg shadow-brand-500/25 hover:bg-brand-600 transition shrink-0"
          >
            <Plus size={14} />
            Добавить канал
          </button>
        </div>
      </div>

      {/* Interactive AI Preview Sandbox */}
      <div className="rounded-2xl border border-white/10 bg-[#141414] p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="text-amber-400" size={16} />
            <h3 className="text-sm font-bold text-white">Тест генерации комментария нейросетью</h3>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">Стиль:</span>
            <select
              value={testTone}
              onChange={(e) => setTestTone(e.target.value)}
              className="rounded-lg border border-white/10 bg-[#1c1c1c] px-2.5 py-1 text-xs text-white outline-none"
            >
              <option value="expert">Экспертный (Web/UX)</option>
              <option value="witty">Остроумный / Лёгкий юмор</option>
              <option value="supportive">Поддерживающий / Вопрос</option>
              <option value="friendly">Дружеский тон</option>
            </select>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-medium text-slate-400">Пример текста поста из канала:</label>
          <textarea
            value={testPostText}
            onChange={(e) => setTestPostText(e.target.value)}
            rows={2}
            className="w-full rounded-xl border border-white/10 bg-[#0d0d0d] p-3 text-xs text-slate-200 outline-none focus:border-brand-500 transition resize-none"
            placeholder="Вставьте текст любого поста..."
          />
        </div>

        <div className="flex items-center justify-between">
          <button
            onClick={handleTestGenerate}
            disabled={generating}
            className="flex items-center gap-2 rounded-xl bg-brand-500/10 border border-brand-500/30 px-4 py-2 text-xs font-semibold text-brand-300 hover:bg-brand-500/20 transition disabled:opacity-50"
          >
            {generating ? (
              <RefreshCw className="animate-spin" size={13} />
            ) : (
              <Zap size={13} className="text-brand-400" />
            )}
            {generating ? "Генерация ответа через MXR..." : "Сгенерировать вариант комментария"}
          </button>
        </div>

        {generatedPreview && (
          <div className="rounded-xl border border-brand-500/30 bg-brand-500/5 p-4 space-y-1.5 animate-in fade-in duration-200">
            <div className="flex items-center justify-between text-[11px] text-brand-400 font-semibold">
              <span>Сгенерированный комментарий от @loves_kyni:</span>
              <span className="text-emerald-400 flex items-center gap-1">
                <Check size={12} /> Готов к отправке
              </span>
            </div>
            <p className="text-xs text-slate-100 font-medium leading-relaxed italic">
              «{generatedPreview}»
            </p>
          </div>
        )}
      </div>

      {/* Target Channels Grid */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Каналы для комментинга ({targets.length})
          </h3>
          <span className="text-[11px] text-slate-500">Автоматический ответ на новые посты</span>
        </div>

        {targets.length === 0 ? (
          <div className="rounded-xl border border-dashed border-white/10 p-8 text-center text-xs text-slate-400">
            Каналы пока не добавлены. Добавьте первый канал выше!
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {targets.map((t) => (
              <div
                key={t.id}
                className="group relative rounded-xl border border-white/10 bg-[#161616] p-4 hover:border-brand-500/30 transition flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="text-xs font-bold text-white group-hover:text-brand-300 transition">
                        {t.title || t.channel_id}
                      </h4>
                      <p className="text-[11px] text-slate-400 font-mono">{t.channel_id}</p>
                    </div>
                    <button
                      onClick={() => handleDeleteTarget(t.id)}
                      className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition"
                      title="Удалить"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>

                  <div className="flex flex-wrap gap-1.5 pt-1">
                    <span className="rounded-md border border-brand-500/25 bg-brand-500/10 px-2 py-0.5 text-[10px] font-semibold text-brand-300">
                      Тон: {t.tone}
                    </span>
                    <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-300 flex items-center gap-1">
                      <MessageSquare size={10} />
                      {t.comments_count} комментов
                    </span>
                  </div>
                </div>

                <div className="mt-3 pt-3 border-t border-white/5 flex items-center justify-between text-[11px] text-slate-500">
                  <span className="flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    Мониторинг активен
                  </span>
                  {t.last_comment_at ? (
                    <span>{new Date(t.last_comment_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                  ) : (
                    <span>Ожидает постов</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* History of published comments */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <Clock size={13} /> История опубликованных комментариев ({logs.length})
          </h3>
        </div>

        {logs.length === 0 ? (
          <div className="rounded-xl border border-dashed border-white/10 p-6 text-center text-xs text-slate-400">
            История пуста. Комментарии появятся при выходе новых постов или после теста.
          </div>
        ) : (
          <div className="space-y-2">
            {logs.slice(0, 10).map((log) => (
              <div
                key={log.id}
                className="rounded-xl border border-white/10 bg-[#161616] p-3.5 space-y-2"
              >
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-bold text-brand-300">{log.channel_title}</span>
                  <span className="text-slate-500">
                    {new Date(log.created_at).toLocaleString([], {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
                <p className="text-xs text-slate-300 bg-black/30 p-2.5 rounded-lg border border-white/5">
                  «{log.comment_text}»
                </p>
                <div className="text-[10px] text-slate-500 truncate">
                  К посту: {log.post_text}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal Add Channel */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-[#181818] p-5 shadow-2xl space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Plus size={16} className="text-brand-400" />
              Добавить канал для нейрокомментинга
            </h3>

            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs text-slate-400">Юзернейм или ссылка на канал</label>
                <input
                  type="text"
                  value={channelId}
                  onChange={(e) => setChannelId(e.target.value)}
                  placeholder="@temablog или https://t.me/channel"
                  className="w-full rounded-xl border border-white/10 bg-[#111] px-3.5 py-2 text-xs text-white outline-none focus:border-brand-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-400">Название (для удобства)</label>
                <input
                  type="text"
                  value={channelTitle}
                  onChange={(e) => setChannelTitle(e.target.value)}
                  placeholder="Блог Артемия Лебедева"
                  className="w-full rounded-xl border border-white/10 bg-[#111] px-3.5 py-2 text-xs text-white outline-none focus:border-brand-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-400">Стиль и тон комментирования</label>
                <select
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  className="w-full rounded-xl border border-white/10 bg-[#111] px-3.5 py-2 text-xs text-white outline-none focus:border-brand-500"
                >
                  <option value="expert">Экспертный (Web-разработка, UX/UI, запуск Mini Apps)</option>
                  <option value="witty">Остроумный / Привлекающий внимание юмор</option>
                  <option value="supportive">Поддерживающий / Задающий вопрос автору</option>
                  <option value="friendly">Дружеский свободный стиль</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-400">Индивидуальный акцент для нейросети (опционально)</label>
                <input
                  type="text"
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  placeholder="Например: акцентировать внимание на конверсиях и скорости сайта"
                  className="w-full rounded-xl border border-white/10 bg-[#111] px-3.5 py-2 text-xs text-white outline-none focus:border-brand-500"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-white/10">
              <button
                onClick={() => setShowAdd(false)}
                className="rounded-xl border border-white/10 px-4 py-2 text-xs text-slate-300 hover:text-white"
              >
                Отмена
              </button>
              <button
                onClick={handleAddTarget}
                disabled={adding || !channelId.trim()}
                className="flex items-center gap-1.5 rounded-xl bg-brand-500 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-brand-500/25 disabled:opacity-50"
              >
                {adding ? <RefreshCw className="animate-spin" size={13} /> : <Plus size={13} />}
                Добавить канал
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
