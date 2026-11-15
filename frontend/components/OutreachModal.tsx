"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  Check,
  Coins,
  Flame,
  Play,
  Send,
  Sparkles,
  Users,
  X,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import { triggerHaptic } from "@/lib/telegram";
import type { Lead } from "@/lib/types";
import { Spinner } from "./ui";

const DEFAULT_TEMPLATE =
  "Здравствуйте! Обратили внимание на компанию {company_name} в {city}. " +
  "Мы специализируемся на разработке конверсионных сайтов и лендингов для вашей сферы. " +
  "Подготовили интерактивное демо решения — показать вам?";

export default function OutreachModal({
  isOpen,
  onClose,
  leads,
  showToast,
  onStarted,
}: {
  isOpen: boolean;
  onClose: () => void;
  leads: Lead[];
  showToast: (msg: string, variant?: "info" | "success" | "error") => void;
  onStarted?: () => void;
}) {
  const [template, setTemplate] = useState(DEFAULT_TEMPLATE);
  const [delayMin, setDelayMin] = useState(180);
  const [delayMax, setDelayMax] = useState(600);
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    if (isOpen) {
      api.getOutreachStatus().then(setStatus).catch(() => {});
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const validLeads = leads.filter(
    (l) => l.phone || (l.social_links && l.social_links.telegram)
  );

  const creditsRequired = validLeads.length * 1;

  const handleStart = async () => {
    if (validLeads.length === 0) {
      showToast("В выборке нет лидов с Telegram контактом или телефоном", "error");
      return;
    }
    setSubmitting(true);
    triggerHaptic("medium");
    try {
      const res = await api.startOutreach({
        lead_ids: validLeads.map((l) => l.id),
        template,
        delay_min: delayMin,
        delay_max: delayMax,
      });
      showToast(
        `Касание запущено для ${res.leads_count} лидов через пул Telegram аккаунтов!`,
        "success"
      );
      if (onStarted) onStarted();
      onClose();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка запуска рассылки", "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg rounded-2xl border border-white/[0.08] bg-[#1A1C23] p-5 shadow-2xl space-y-4 animate-fadeIn">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#242731] border border-white/[0.08] text-[#8B5CF6]">
              <Send size={16} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-[#F3F4F6] flex items-center gap-2">
                Касание по выборке
                <span className="rounded-md bg-[rgba(139,92,246,0.14)] border border-[rgba(139,92,246,0.3)] px-1.5 py-0.2 text-[10px] font-medium text-[#C4B5FD]">
                  AI-уникализация
                </span>
              </h2>
              <p className="text-xs text-[#6B7280]">
                Мягкий аутрич через пул Telegram аккаунтов
              </p>
            </div>
          </div>
          <button onClick={onClose} className="icon-btn !h-7 !w-7">
            <X size={14} />
          </button>
        </div>

        {/* Lead Count Card */}
        <div className="rounded-xl border border-white/[0.07] bg-[#242731] p-3 flex items-center justify-between text-xs">
          <div>
            <span className="text-[#9CA3AF] block">Выбрано лидов:</span>
            <span className="font-semibold text-[#F3F4F6] text-sm">
              <span className="font-mono tabular-nums">{validLeads.length}</span> из <span className="font-mono tabular-nums">{leads.length}</span> с контактами
            </span>
          </div>
          <div className="text-right">
            <span className="text-[#9CA3AF] block">Стоимость:</span>
            <span className="font-mono tabular-nums font-semibold text-[#F59E0B] flex items-center gap-1 justify-end">
              <Coins size={12} /> {creditsRequired} cr
            </span>
          </div>
        </div>

        {/* Template Input */}
        <div className="space-y-1.5">
          <label className="label">Шаблон оффера (AI уникализирует каждое сообщение)</label>
          <textarea
            rows={4}
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
            className="input text-xs font-mono leading-relaxed"
          />
          <div className="flex flex-wrap gap-1 text-[10px] text-[#9CA3AF]">
            <span>Переменные:</span>
            <span className="rounded bg-[#242731] border border-white/[0.06] px-1 font-mono text-[#C4B5FD]">&#123;company_name&#125;</span>
            <span className="rounded bg-[#242731] border border-white/[0.06] px-1 font-mono text-[#C4B5FD]">&#123;city&#125;</span>
            <span className="rounded bg-[#242731] border border-white/[0.06] px-1 font-mono text-[#C4B5FD]">&#123;category&#125;</span>
          </div>
        </div>

        {/* Safety Limits */}
        <div className="rounded-xl border border-white/[0.06] bg-[#242731] p-3 space-y-1.5 text-xs">
          <div className="flex items-center gap-1.5 text-[#F3F4F6] font-medium">
            <Flame size={13} className="text-[#F59E0B]" />
            Защита от спам-блоков (Антифлуд)
          </div>
          <p className="text-[11px] text-[#9CA3AF] leading-relaxed">
            • 10–15 новых диалогов в сутки на прогретый аккаунт
            <br />• Рандомная задержка 180–600 сек между отправками
            <br />• Автоматическая ротация при FloodWait
          </p>
        </div>

        <button
          onClick={handleStart}
          disabled={submitting || validLeads.length === 0}
          className="btn-primary w-full !h-10 text-xs font-medium"
        >
          {submitting ? (
            <Spinner size={14} />
          ) : (
            <Play size={14} className="fill-white" />
          )}
          Запустить касание (<span className="font-mono tabular-nums">{validLeads.length}</span> лидов)
        </button>
      </div>
    </div>
  );
}
