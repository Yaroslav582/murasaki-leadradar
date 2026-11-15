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
      <div className="relative w-full max-w-lg rounded-2xl border border-white/10 bg-[#13131a] p-6 shadow-2xl space-y-4 animate-fadeIn">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500/15 border border-brand-500/20 text-brand-300">
              <Send size={18} />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                Запустить касание по выборке
                <span className="rounded-full bg-brand-500/20 px-2 py-0.5 text-[9px] font-bold text-brand-300 border border-brand-500/30">
                  AI-уникализация
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Мягкий аутрич через пул аккаунтов LeadRadar
              </p>
            </div>
          </div>
          <button onClick={onClose} className="icon-btn !h-8 !w-8">
            <X size={15} />
          </button>
        </div>

        {/* Lead Count Card */}
        <div className="rounded-xl border border-white/[0.08] bg-[#0c0d12] p-3 flex items-center justify-between text-xs">
          <div>
            <span className="text-slate-400 block">Выбрано лидов для касания:</span>
            <span className="font-bold text-white text-sm">
              {validLeads.length} из {leads.length} лидов с контактами
            </span>
          </div>
          <div className="text-right">
            <span className="text-slate-400 block">Стоимость:</span>
            <span className="font-mono font-bold text-amber-300 flex items-center gap-1 justify-end">
              <Coins size={12} /> {creditsRequired} cr
            </span>
          </div>
        </div>

        {/* Template Input */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="label">Шаблон оффера (перед отправкой уникализируется нейросетью)</label>
          </div>
          <textarea
            rows={4}
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
            className="input text-xs font-mono leading-relaxed"
          />
          <div className="flex flex-wrap gap-1.5 text-[10px] text-slate-400">
            <span>Переменные:</span>
            <span className="rounded bg-white/5 px-1 font-mono text-brand-300">&#123;company_name&#125;</span>
            <span className="rounded bg-white/5 px-1 font-mono text-brand-300">&#123;city&#125;</span>
            <span className="rounded bg-white/5 px-1 font-mono text-brand-300">&#123;category&#125;</span>
          </div>
        </div>

        {/* Safety Limits */}
        <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-3.5 space-y-2 text-xs">
          <div className="flex items-center gap-1.5 text-slate-300 font-semibold">
            <Flame size={14} className="text-amber-400" />
            Защита от спам-блоков (Антифлуд)
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            • Не более 10–15 новых диалогов в сутки на один прогретый аккаунт
            <br />• Рандомная задержка 180–600 сек между отправками
            <br />• Автоматическая ротация при FloodWaitError
          </p>
        </div>

        <button
          onClick={handleStart}
          disabled={submitting || validLeads.length === 0}
          className="btn-primary w-full !py-3 font-bold text-sm"
        >
          {submitting ? (
            <Spinner size={16} />
          ) : (
            <Play size={16} className="fill-white" />
          )}
          Запустить рассылку ({validLeads.length} лидов)
        </button>
      </div>
    </div>
  );
}
