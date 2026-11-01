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
  RefreshCw,
  Save,
  Smartphone,
  Sparkles,
  X,
} from "lucide-react";
import { API_URL, api } from "@/lib/api";
import type { Demo, Lead } from "@/lib/types";
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
  const [tab, setTab] = useState<"message" | "html">("message");
  const [message, setMessage] = useState(demo.message);
  const [html, setHtml] = useState(demo.html);
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [toggling, setToggling] = useState(false);
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

  const handlePublish = async () => {
    setToggling(true);
    try {
      const updated = await api.updateDemo(current.id, { published: !current.published });
      setCurrent(updated);
      onDemoUpdated(updated);
      showToast(updated.published ? "Демо опубликовано" : "Публикация отключена", "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Не удалось изменить публикацию", "error");
    } finally {
      setToggling(false);
    }
  };

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const fresh = await api.generateDemo(lead.id);
      onDemoUpdated(fresh);
      showToast("Новое демо готово", "success");
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
    anchor.download = `demo-${current.id.slice(0, 8)}.html`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Modal open={true} onClose={onClose} className="max-w-[1180px]">
      <div className="max-h-[92vh] overflow-hidden rounded-3xl border border-white/10 bg-[#0a0c15] shadow-2xl">
        <div className="flex flex-wrap items-center gap-3 border-b border-white/[0.07] px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-brand-500/30 bg-brand-500/15 text-brand-300">
            <Sparkles size={17} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="flex items-center gap-2 text-sm font-extrabold text-white">
              Демо-лендинг
              <span className="rounded bg-white/[0.07] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-400">
                AI
              </span>
            </p>
            <p className="truncate text-[11px] text-slate-500">{lead.name} · {lead.city}</p>
          </div>

          <div className="flex items-center gap-2">
            <a
              href={current.public_url}
              target="_blank"
              rel="noopener noreferrer"
              className="hidden items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-semibold text-slate-300 transition hover:text-white sm:inline-flex"
            >
              <Globe2 size={13} />
              Открыть
              <ExternalLink size={11} />
            </a>
            <button
              onClick={handleRegenerate}
              disabled={regenerating}
              className="btn-ghost"
              title="Сгенерировать заново"
            >
              {regenerating ? <Spinner size={14} /> : <RefreshCw size={14} />}
              <span className="hidden sm:inline">Перегенерировать</span>
            </button>
            <button onClick={onClose} className="icon-btn" aria-label="Закрыть">
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="grid max-h-[calc(92vh-73px)] overflow-y-auto lg:grid-cols-[460px_1fr] lg:overflow-hidden">
          <div className="relative flex flex-col items-center justify-center border-b border-white/[0.06] bg-[#070810] px-5 py-7 lg:border-b-0 lg:border-r">
            <div className="pointer-events-none absolute inset-0 opacity-60">
              <div className="absolute left-1/2 top-10 h-64 w-64 -translate-x-1/2 rounded-full bg-brand-500/15 blur-3xl" />
            </div>

            <div className="relative">
              <div className="mx-auto flex w-[300px] flex-col rounded-[2.6rem] border-[6px] border-[#1d2136] bg-black p-1.5 shadow-2xl">
                <div className="relative overflow-hidden rounded-[2.2rem] bg-white">
                  <div className="pointer-events-none absolute left-1/2 top-2 z-10 h-5 w-24 -translate-x-1/2 rounded-full bg-black/90" />
                  <iframe
                    key={previewUrl}
                    title="Превью демо-лендинга"
                    src={previewUrl}
                    sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox"
                    className="h-[560px] w-full bg-white"
                  />
                </div>
              </div>
              <div className="mx-auto mt-4 h-1.5 w-24 rounded-full bg-white/10" />
            </div>

            <div className="relative mt-5 flex w-full max-w-[320px] items-center gap-2 rounded-xl border border-white/[0.07] bg-white/[0.03] px-3 py-2">
              <Smartphone size={13} className="shrink-0 text-slate-500" />
              <span className="min-w-0 flex-1 truncate text-[11px] text-slate-400">{current.public_url}</span>
              <button onClick={() => handleCopy(current.public_url)} className="text-slate-400 transition hover:text-white" title="Копировать ссылку">
                <Copy size={13} />
              </button>
              <a href={current.public_url} target="_blank" rel="noopener noreferrer" className="text-slate-400 transition hover:text-white" title="Открыть">
                <ExternalLink size={13} />
              </a>
            </div>

            <div className="relative mt-3 flex items-center gap-2">
              <button
                onClick={handlePublish}
                disabled={toggling}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] font-semibold transition ${
                  current.published
                    ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-300"
                    : "border-white/10 bg-white/[0.04] text-slate-400"
                }`}
              >
                {toggling ? <Spinner size={11} /> : <Check size={11} />}
                {current.published ? "Опубликовано" : "Черновик"}
              </button>
              <button onClick={handleDownload} className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[11px] font-semibold text-slate-400 transition hover:text-white">
                <Download size={11} /> HTML
              </button>
            </div>
          </div>

          <div className="flex min-h-[520px] flex-col bg-[#0a0c15]">
            <div className="flex items-center gap-1 border-b border-white/[0.06] px-5 pt-4">
              <button
                onClick={() => setTab("message")}
                className={`inline-flex items-center gap-1.5 rounded-t-lg border-b-2 px-3 pb-3 pt-1 text-xs font-semibold transition ${
                  tab === "message"
                    ? "border-brand-500 text-white"
                    : "border-transparent text-slate-500 hover:text-slate-300"
                }`}
              >
                <MessageSquare size={13} /> Сообщение
              </button>
              <button
                onClick={() => setTab("html")}
                className={`inline-flex items-center gap-1.5 rounded-t-lg border-b-2 px-3 pb-3 pt-1 text-xs font-semibold transition ${
                  tab === "html"
                    ? "border-brand-500 text-white"
                    : "border-transparent text-slate-500 hover:text-slate-300"
                }`}
              >
                <Code2 size={13} /> HTML-код
              </button>
              <span className="ml-auto hidden text-[10px] text-slate-600 sm:block">
                {tab === "message" ? "Скрипт первого касания" : "Можно править вручную"}
              </span>
            </div>

            {tab === "message" ? (
              <div className="flex flex-1 flex-col gap-3 p-5">
                <div className="rounded-xl border border-brand-500/20 bg-brand-500/[0.06] px-3 py-2 text-[11px] leading-relaxed text-brand-200/80">
                  Персональное сообщение уже содержит ссылку на демо. Скопируйте и отправьте в Telegram,
                  WhatsApp или Instagram.
                </div>
                <textarea
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  className="input min-h-[280px] flex-1 resize-none leading-relaxed"
                />
                <div className="flex flex-wrap items-center gap-2">
                  <button onClick={() => handleCopy(message)} className="btn-ghost">
                    <Copy size={14} /> Копировать
                  </button>
                  <button onClick={handleSave} disabled={saving || !dirtyMessage} className="btn-primary">
                    {saving ? <Spinner size={14} /> : <Save size={14} />}
                    Сохранить
                  </button>
                  {dirtyMessage ? <span className="text-[11px] text-amber-300">Есть несохранённые изменения</span> : null}
                </div>
              </div>
            ) : (
              <div className="flex flex-1 flex-col gap-3 p-5">
                <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] px-3 py-2 text-[11px] leading-relaxed text-slate-400">
                  Полный HTML демо-страницы. Tailwind подключён через CDN — превью обновится после
                  сохранения.
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
                    <RefreshCw size={14} /> Превью
                  </button>
                  <button onClick={handleSave} disabled={saving || !dirtyHtml} className="btn-primary">
                    {saving ? <Spinner size={14} /> : <Save size={14} />}
                    Сохранить
                  </button>
                  {dirtyHtml ? <span className="text-[11px] text-amber-300">Есть несохранённые изменения</span> : null}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
}
