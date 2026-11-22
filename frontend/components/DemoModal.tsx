"use client";

import { useEffect, useState } from "react";
import {
  Check,
  Code2,
  Copy,
  Download,
  ExternalLink,
  Globe2,
  MessageSquare,
  Monitor,
  RefreshCw,
  Save,
  Smartphone,
  Sparkles,
  Wand2,
  X,
} from "lucide-react";
import { API_URL, api } from "@/lib/api";
import type { Demo, Lead } from "@/lib/types";
import { generatePromptForLead, getFirstTouchOffer } from "@/lib/utils";
import Modal from "./Modal";
import type { ToastVariant } from "./ui";
import { Spinner } from "./ui";

export default function DemoModal({
  demo,
  lead,
  onClose,
  onDemoUpdated,
  showToast,
}: {
  demo: Demo;
  lead: Lead;
  onClose: () => void;
  onDemoUpdated: (demo: Demo) => void;
  showToast: (message: string, variant?: ToastVariant) => void;
}) {
  const [current, setCurrent] = useState(demo);
  const [tab, setTab] = useState<"message" | "custom_prompt" | "html">("message");
  const [deviceMode, setDeviceMode] = useState<"mobile" | "desktop">("mobile");
  const [message, setMessage] = useState(demo.message);
  const [html, setHtml] = useState(demo.html);
  const [customHtmlInput, setCustomHtmlInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [customSaving, setCustomSaving] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    setCurrent(demo);
    setMessage(demo.message);
    setHtml(demo.html);
    setReloadKey((value) => value + 1);
  }, [demo]);

  const dirtyMessage = message !== current.message;
  const dirtyHtml = html !== current.html;

  const previewUrl = `${API_URL}/api/demos/${current.id}/raw?v=${encodeURIComponent(current.updated_at)}-${reloadKey}`;
  const fallbackHost = API_URL || (typeof window !== "undefined" ? window.location.origin : "");
  const displayPublicUrl = current.public_url || `${fallbackHost}/demo/${current.id}`;

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      showToast("Скопировано в буфер обмена", "success");
    } catch {
      showToast("Не удалось скопировать", "error");
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await api.updateDemo(current.id, {
        ...(dirtyMessage ? { message } : {}),
        ...(dirtyHtml ? { html } : {}),
      });
      setCurrent(updated);
      onDemoUpdated(updated);
      showToast("Изменения сохранены", "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Не удалось сохранить", "error");
    } finally {
      setSaving(false);
    }
  };

  const handlePublishDemo = async () => {
    setToggling(true);
    try {
      const updatedOffer = getFirstTouchOffer(lead, displayPublicUrl);
      const updated = await api.updateDemo(current.id, {
        published: true,
        message: updatedOffer,
      });
      setCurrent(updated);
      setMessage(updated.message);
      onDemoUpdated(updated);
      showToast("Демо опубликовано! Ссылка подставлена в оффер первого контакта", "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Не удалось опубликовать демо", "error");
    } finally {
      setToggling(false);
    }
  };

  const cleanExtractedHtml = (raw: string): string => {
    let cleanCode = raw.trim();
    // 1. Strip markdown fences ```html ... ```
    cleanCode = cleanCode.replace(/^```[a-z]*\s*/i, "").replace(/\s*```$/i, "").trim();

    // 2. Cut out any conversational preamble/postscript and isolate <!DOCTYPE html> ... </html>
    const lower = cleanCode.toLowerCase();
    const startIdx = lower.indexOf("<!doctype html");
    const htmlIdx = lower.indexOf("<html");
    const effectiveStart = startIdx !== -1 ? startIdx : htmlIdx;
    if (effectiveStart !== -1) {
      const endIdx = lower.lastIndexOf("</html>");
      if (endIdx !== -1) {
        cleanCode = cleanCode.slice(effectiveStart, endIdx + 7);
      } else {
        cleanCode = cleanCode.slice(effectiveStart) + "\n</html>";
      }
    }
    return cleanCode;
  };

  const handleApplyCustomHtml = async () => {
    const raw = customHtmlInput.trim();
    if (!raw) {
      showToast("Вставьте HTML или код лендинга", "error");
      return;
    }
    setCustomSaving(true);
    try {
      const cleanCode = cleanExtractedHtml(raw);

      const updated = await api.saveCustomDemo(lead.id, {
        html: cleanCode,
        message: getFirstTouchOffer(lead, displayPublicUrl),
      });

      setCurrent(updated);
      setHtml(updated.html);
      setMessage(updated.message);
      setReloadKey((k) => k + 1);
      onDemoUpdated(updated);
      setCustomHtmlInput("");
      showToast("Демо обновлено из своего кода (0 кредитов)!", "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Ошибка применения кода", "error");
    } finally {
      setCustomSaving(false);
    }
  };

  const handleCustomPaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const pasted = e.clipboardData.getData("text");
    if (pasted.includes("```") || pasted.toLowerCase().includes("<!doctype html")) {
      e.preventDefault();
      const cleaned = cleanExtractedHtml(pasted);
      setCustomHtmlInput(cleaned);
      showToast("Код автоматически очищен от markdown-обёрток!", "info");
    }
  };

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const fresh = await api.generateDemo(lead.id);
      setCurrent(fresh);
      setMessage(fresh.message);
      setHtml(fresh.html);
      setReloadKey((k) => k + 1);
      onDemoUpdated(fresh);
      showToast("Новое демо сгенерировано", "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Не удалось сгенерировать демо", "error");
    } finally {
      setRegenerating(false);
    }
  };

  const handleDownload = () => {
    const blob = new Blob([current.html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `demo-${lead.name.replace(/[^a-zA-Zа-яА-Я0-9]/g, "_")}.html`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Modal open={true} onClose={onClose} className="max-w-[1240px]">
      <div className="max-h-[94vh] overflow-hidden rounded-2xl border border-white/[0.04] bg-[#1A1C23] shadow-[0_10px_40px_rgba(0,0,0,0.6)]">
        {/* Шапка модалки */}
        <div className="flex flex-wrap items-center gap-3 border-b border-white/[0.07] px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-brand-500/30 bg-brand-500/15 text-brand-300">
            <Sparkles size={17} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="flex items-center gap-2 text-sm font-extrabold text-white">
              Генератор демо-сайта
              <span className="rounded bg-brand-500/20 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-brand-300">
                PRO
              </span>
            </p>
            <p className="truncate text-[11px] text-slate-500">{lead.name} · {lead.city}</p>
          </div>

          {/* Переключатель режимов Телефон / Десктоп */}
          <div className="flex items-center rounded-xl border border-white/10 bg-white/[0.04] p-0.5">
            <button
              onClick={() => setDeviceMode("mobile")}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
                deviceMode === "mobile"
                  ? "bg-brand-500 text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <Smartphone size={13} />
              Телефон
            </button>
            <button
              onClick={() => setDeviceMode("desktop")}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
                deviceMode === "desktop"
                  ? "bg-brand-500 text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <Monitor size={13} />
              Десктоп
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleRegenerate}
              disabled={regenerating}
              className="btn-ghost"
              title="Сгенерировать заново через AI (5 кредитов)"
            >
              {regenerating ? <Spinner size={14} /> : <RefreshCw size={14} />}
              <span className="hidden sm:inline">Перегенерировать (5 кр)</span>
            </button>
            <button onClick={onClose} className="icon-btn" aria-label="Закрыть">
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Основное тело: Превью + Панель управления */}
        <div className="grid max-h-[calc(94vh-73px)] overflow-y-auto lg:grid-cols-[1.1fr_1fr] lg:overflow-hidden">
          {/* Левая колонка: Превью с переключением Телефон / Десктоп */}
          <div className="relative flex flex-col items-center justify-center border-b border-white/[0.04] bg-[#111216] px-5 py-6 lg:border-b-0 lg:border-r">
            <div className="pointer-events-none absolute inset-0 opacity-40">
              <div className="absolute left-1/2 top-10 h-72 w-72 -translate-x-1/2 rounded-full bg-brand-500/15 blur-3xl" />
            </div>

            {/* Контейнер превью */}
            <div className="relative w-full flex items-center justify-center">
              {deviceMode === "mobile" ? (
                /* Телефонный фрейм */
                <div className="mx-auto flex w-[290px] flex-col rounded-[2.6rem] border-[6px] border-[#1d2136] bg-black p-1 shadow-2xl transition-all">
                  <div className="relative overflow-hidden rounded-[2.2rem] bg-white">
                    <div className="pointer-events-none absolute left-1/2 top-2 z-10 h-4 w-20 -translate-x-1/2 rounded-full bg-black/90" />
                    <iframe
                      key={previewUrl}
                      title="Превью демо-лендинга (моб)"
                      src={previewUrl}
                      sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox"
                      className="h-[520px] w-full bg-white"
                    />
                  </div>
                </div>
              ) : (
                /* Десктопный браузерный фрейм */
                <div className="w-full max-w-[540px] flex flex-col rounded-2xl border border-white/10 bg-[#161820] shadow-2xl overflow-hidden transition-all">
                  {/* Имитация панели браузера */}
                  <div className="flex items-center gap-2 border-b border-white/[0.08] bg-[#12131a] px-3.5 py-2">
                    <div className="flex items-center gap-1.5">
                      <div className="h-2.5 w-2.5 rounded-full bg-rose-500/80" />
                      <div className="h-2.5 w-2.5 rounded-full bg-amber-500/80" />
                      <div className="h-2.5 w-2.5 rounded-full bg-emerald-500/80" />
                    </div>
                    <div className="mx-auto flex h-6 w-3/4 items-center justify-center rounded-md bg-white/[0.05] px-2 text-[10px] text-slate-400 font-mono truncate">
                      https://{lead.name.toLowerCase().replace(/[^a-z0-9]/g, "") || "company"}.leadradar.site
                    </div>
                    <button onClick={() => setReloadKey((k) => k + 1)} className="text-slate-400 hover:text-white" title="Обновить">
                      <RefreshCw size={11} />
                    </button>
                  </div>
                  <iframe
                    key={previewUrl}
                    title="Превью демо-лендинга (десктоп)"
                    src={previewUrl}
                    sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox"
                    className="h-[490px] w-full bg-white"
                  />
                </div>
              )}
            </div>

            {/* Публичная ссылка и действия под превью */}
            <div className="relative mt-4 flex w-full max-w-[360px] items-center gap-2 rounded-xl border border-white/[0.07] bg-white/[0.03] px-3 py-2">
              <Globe2 size={13} className="shrink-0 text-brand-300" />
              <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-slate-300">
                {displayPublicUrl}
              </span>
              <button
                onClick={() => handleCopy(displayPublicUrl)}
                className="text-slate-400 transition hover:text-white"
                title="Копировать ссылку"
              >
                <Copy size={13} />
              </button>
              <a
                href={displayPublicUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-slate-400 transition hover:text-white"
                title="Открыть в новой вкладке"
              >
                <ExternalLink size={13} />
              </a>
            </div>

            <div className="relative mt-3 flex flex-wrap items-center justify-center gap-2">
              {/* Кнопка Опубликовать демо */}
              <button
                onClick={handlePublishDemo}
                disabled={toggling}
                className={`inline-flex items-center gap-1.5 rounded-xl border px-3.5 py-1.5 text-xs font-semibold shadow-sm transition ${
                  current.published
                    ? "border-emerald-500/30 bg-[rgba(16,185,129,0.15)] text-[#10B981] hover:bg-[rgba(16,185,129,0.25)]"
                    : "border-brand-500/40 bg-brand-500 text-white hover:bg-brand-600 shadow-[0_0_12px_rgba(139,92,246,0.35)]"
                }`}
              >
                {toggling ? <Spinner size={12} /> : <Check size={12} />}
                {current.published ? "Опубликовано (Обновить оффер)" : "Опубликовать демо"}
              </button>

              <button
                onClick={handleDownload}
                className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-semibold text-slate-300 transition hover:text-white"
              >
                <Download size={12} /> Скачать HTML
              </button>
            </div>
          </div>

          {/* Правая колонка: Вкладки (Сообщение / Свой промпт (0 кр) / HTML-код) */}
          <div className="flex min-h-[520px] flex-col bg-[#0a0c15]">
            <div className="flex items-center gap-1 border-b border-white/[0.06] px-5 pt-3">
              <button
                onClick={() => setTab("message")}
                className={`inline-flex items-center gap-1.5 rounded-t-lg border-b-2 px-3 pb-3 pt-1 text-xs font-semibold transition ${
                  tab === "message"
                    ? "border-brand-500 text-white"
                    : "border-transparent text-slate-500 hover:text-slate-300"
                }`}
              >
                <MessageSquare size={13} /> Первый контакт (Оффер)
              </button>
              <button
                onClick={() => setTab("custom_prompt")}
                className={`inline-flex items-center gap-1.5 rounded-t-lg border-b-2 px-3 pb-3 pt-1 text-xs font-semibold transition ${
                  tab === "custom_prompt"
                    ? "border-brand-500 text-white"
                    : "border-transparent text-slate-500 hover:text-slate-300"
                }`}
              >
                <Wand2 size={13} className="text-amber-400" /> Свой промпт (0 кр)
              </button>
              <button
                onClick={() => setTab("html")}
                className={`inline-flex items-center gap-1.5 rounded-t-lg border-b-2 px-3 pb-3 pt-1 text-xs font-semibold transition ${
                  tab === "html"
                    ? "border-brand-500 text-white"
                    : "border-transparent text-slate-500 hover:text-slate-300"
                }`}
              >
                <Code2 size={13} /> HTML
              </button>
            </div>

            {/* 1. Вкладка Сообщение первого контакта */}
            {tab === "message" && (
              <div className="flex flex-1 flex-col gap-3 p-5">
                <div className="rounded-xl border border-brand-500/20 bg-brand-500/[0.06] px-3.5 py-2.5 text-xs leading-relaxed text-brand-200">
                  Сообщение персонализировано под компанию и содержит ссылку на демо-лендинг. Отправьте клиенту в Telegram, WhatsApp или Direct.
                </div>
                <textarea
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  className="input min-h-[280px] flex-1 resize-none leading-relaxed text-xs"
                />
                <div className="flex flex-wrap items-center gap-2">
                  <button onClick={() => handleCopy(message)} className="btn-ghost">
                    <Copy size={14} /> Скопировать оффер
                  </button>
                  <button onClick={handleSave} disabled={saving || !dirtyMessage} className="btn-primary">
                    {saving ? <Spinner size={14} /> : <Save size={14} />}
                    Сохранить изменения
                  </button>
                  {dirtyMessage && (
                    <span className="text-[11px] text-amber-300">Есть несохранённые изменения</span>
                  )}
                </div>
              </div>
            )}

            {/* 2. Вкладка «Свой промпт (бесплатно / 0 кредитов)» */}
            {tab === "custom_prompt" && (
              <div className="flex flex-1 flex-col gap-3.5 p-5">
                <div className="rounded-xl border border-amber-500/25 bg-amber-500/[0.06] p-3 text-xs leading-relaxed text-amber-200">
                  <p className="font-semibold text-white">Режим бесплатной генерации (0 кредитов):</p>
                  <ol className="mt-1 list-decimal list-inside space-y-1 text-slate-300">
                    <li>Скопируйте подготовленный промпт с данными компании.</li>
                    <li>Вставьте в любую бесплатную нейросеть (ChatGPT, Claude, DeepSeek, Gemini).</li>
                    <li>Вставьте полученный HTML ниже и нажмите «Применить».</li>
                  </ol>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleCopy(generatePromptForLead(lead))}
                    className="inline-flex h-9 items-center gap-2 rounded-xl border border-brand-500/30 bg-[rgba(139,92,246,0.14)] px-3 text-xs font-semibold text-[#C4B5FD] transition hover:bg-[rgba(139,92,246,0.24)]"
                  >
                    <Copy size={13} />
                    Скопировать промпт с данными лида
                  </button>
                  <span className="text-[11px] text-slate-500">Название, город, телефон, рейтинг, услуги</span>
                </div>

                <div className="flex-1 flex flex-col gap-1.5">
                  <label className="text-[11px] font-semibold text-slate-400">
                    Вставить HTML / JSON из буфера:
                  </label>
                  <textarea
                    value={customHtmlInput}
                    onChange={(e) => setCustomHtmlInput(e.target.value)}
                    onPaste={handleCustomPaste}
                    placeholder="Вставьте сюда сгенерированный HTML код (<!DOCTYPE html>...)"
                    className="input flex-1 min-h-[220px] font-mono text-[11px] leading-relaxed resize-none"
                    spellCheck={false}
                  />
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <button
                    onClick={handleApplyCustomHtml}
                    disabled={customSaving || !customHtmlInput.trim()}
                    className="btn-primary"
                  >
                    {customSaving ? <Spinner size={14} /> : <Sparkles size={14} />}
                    Применить и отрендерить (0 кр)
                  </button>
                  <button
                    onClick={() => setCustomHtmlInput("")}
                    className="btn-ghost text-xs"
                  >
                    Очистить
                  </button>
                </div>
              </div>
            )}

            {/* 3. Вкладка Редактирование HTML кода */}
            {tab === "html" && (
              <div className="flex flex-1 flex-col gap-3 p-5">
                <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] px-3 py-2 text-[11px] leading-relaxed text-slate-400">
                  Прямой редактор HTML демо-страницы с CDN Tailwind. После сохранения превью обновляется автоматически.
                </div>
                <textarea
                  value={html}
                  onChange={(event) => setHtml(event.target.value)}
                  spellCheck={false}
                  className="input min-h-[300px] flex-1 resize-none font-mono text-[11px] leading-relaxed"
                />
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => setReloadKey((value) => value + 1)}
                    className="btn-ghost"
                    title="Обновить превью"
                  >
                    <RefreshCw size={14} /> Обновить превью
                  </button>
                  <button onClick={handleSave} disabled={saving || !dirtyHtml} className="btn-primary">
                    {saving ? <Spinner size={14} /> : <Save size={14} />}
                    Сохранить HTML
                  </button>
                  {dirtyHtml && (
                    <span className="text-[11px] text-amber-300">Есть несохранённые изменения</span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
}
