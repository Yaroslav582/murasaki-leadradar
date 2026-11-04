"use client";

import { useEffect, useState } from "react";
import {
  Eye,
  Info,
  Pause,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import { triggerHaptic } from "@/lib/telegram";
import type { StoriesStatus } from "@/lib/types";

export default function StoriesMasslookingView({
  showToast,
  onGoToScraper,
}: {
  showToast: (message: string, variant?: "success" | "error" | "info") => void;
  onGoToScraper?: () => void;
}) {
  const [status, setStatus] = useState<StoriesStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);

  const [delayMin, setDelayMin] = useState(15);
  const [delayMax, setDelayMax] = useState(35);

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 6000);
    return () => clearInterval(interval);
  }, []);

  const loadStatus = async () => {
    try {
      const s = await api.getStoriesStatus();
      setStatus(s);
    } catch (err) {
      console.error("Failed to load stories status:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async () => {
    if (!status) return;
    const nextState = !status.is_running;
    setToggling(true);
    triggerHaptic(nextState ? "success" : "light");

    try {
      const res = await api.toggleStoriesMasslooking(nextState, delayMin, delayMax);
      setStatus((prev) => (prev ? { ...prev, is_running: res.is_running } : null));
      showToast(
        res.is_running
          ? "Масслукинг историй запущен! Бот безопасно просматривает Stories"
          : "Масслукинг историй приостановлен",
        res.is_running ? "success" : "info"
      );
    } catch (err) {
      showToast("Ошибка управления масслукингом", "error");
    } finally {
      setToggling(false);
    }
  };

  const percent =
    status && status.total_users > 0
      ? Math.round((status.viewed_count / status.total_users) * 100)
      : 0;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Banner */}
      <div className="rounded-2xl border border-brand-500/20 bg-gradient-to-r from-brand-950/40 via-purple-950/20 to-transparent p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Eye className="text-brand-400" size={18} />
              Масслукинг историй (Просмотр Stories)
            </h2>
            <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
              Автоматический просмотр историй целевой аудитории. Ваш профиль <strong>Yarik — Design Engineer</strong> с
              аватаркой Murasaki появляется в списке зрителей у потенциальных клиентов. Они открывают ваш аккаунт,
              видят портфолио <strong>murasaki-portfolio.vercel.app</strong> и заказывают разработку!
            </p>
          </div>
          {onGoToScraper && (
            <button
              onClick={onGoToScraper}
              className="flex items-center justify-center gap-1.5 rounded-xl border border-brand-500/30 bg-brand-500/10 px-4 py-2 text-xs font-semibold text-brand-300 hover:bg-brand-500/20 transition shrink-0"
            >
              <Users size={13} className="text-brand-400" />
              Пополнить базу из чатов
            </button>
          )}
        </div>
      </div>

      {/* Main Control Panel */}
      <div className="rounded-2xl border border-white/10 bg-[#141414] p-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-5">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <span
                className={`h-3 w-3 rounded-full ${
                  status?.is_running
                    ? "bg-emerald-400 animate-pulse ring-4 ring-emerald-500/20"
                    : "bg-slate-600"
                }`}
              />
              <span className="text-base font-bold text-white">
                {status?.is_running ? "Двигатель масслукинга активен" : "Масслукинг на паузе"}
              </span>
            </div>
            <p className="text-xs text-slate-400">
              {status?.is_running
                ? `Безопасный интервал: ${delayMin}-${delayMax} сек. между историями`
                : "Нажмите запуск для старта просмотров по собранной базе"}
            </p>
          </div>

          <button
            onClick={handleToggle}
            disabled={toggling || (status?.total_users === 0 && !status?.is_running)}
            className={`flex items-center gap-2 rounded-xl px-6 py-3 text-xs font-bold transition shadow-lg shrink-0 ${
              status?.is_running
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/30 hover:bg-amber-500/30"
                : "bg-emerald-500 text-white shadow-emerald-500/25 hover:bg-emerald-600"
            } disabled:opacity-50`}
          >
            {toggling ? (
              <RefreshCw className="animate-spin" size={14} />
            ) : status?.is_running ? (
              <Pause size={14} />
            ) : (
              <Play size={14} />
            )}
            {status?.is_running ? "Остановить масслукинг" : "Запустить масслукинг историй"}
          </button>
        </div>

        {/* Counter cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="rounded-xl border border-brand-500/20 bg-brand-500/5 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-brand-400">
              Просмотрено историй
            </p>
            <p className="text-2xl font-bold text-white mt-1">
              {status?.viewed_count ?? 0}
            </p>
          </div>

          <div className="rounded-xl border border-white/10 bg-[#1b1b1b] p-4">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Ожидают в очереди
            </p>
            <p className="text-2xl font-bold text-amber-300 mt-1">
              {status?.unviewed_count ?? 0}
            </p>
          </div>

          <div className="rounded-xl border border-white/10 bg-[#1b1b1b] p-4">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Всего аудитории
            </p>
            <p className="text-2xl font-bold text-slate-200 mt-1">
              {status?.total_users ?? 0}
            </p>
          </div>
        </div>

        {/* Progress Bar */}
        {status && status.total_users > 0 && (
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs font-semibold">
              <span className="text-slate-400">Прогресс охвата базы:</span>
              <span className="text-brand-400">{percent}%</span>
            </div>
            <div className="h-2 w-full rounded-full bg-white/5 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-brand-500 to-purple-400 transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(5, percent))}%` }}
              />
            </div>
          </div>
        )}

        {/* Speed & Anti-Spam protection */}
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 flex items-start gap-3">
          <ShieldCheck className="text-emerald-400 shrink-0 mt-0.5" size={18} />
          <div className="space-y-1 text-xs">
            <p className="font-bold text-emerald-300">Встроенная защита от лимитов Telegram (Safe Anti-Flood)</p>
            <p className="text-slate-300 leading-relaxed">
              Запросы чтения историй (ReadStories) имитируют поведение обычного человека с мобильного устройства:
              рандомная задержка 15–35 сек, приоритет пользователям с Telegram Premium и распределение нагрузки.
              Просмотр историй абсолютно безопасен для аккаунта.
            </p>
          </div>
        </div>
      </div>

      {/* Guide Card */}
      <div className="rounded-2xl border border-white/10 bg-[#161616] p-5 space-y-3">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
          <Info size={14} className="text-brand-400" />
          Схема воронки органического трафика:
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div className="rounded-xl border border-white/5 bg-black/20 p-3 space-y-1">
            <p className="font-bold text-white">1. Сбор целевой базы</p>
            <p className="text-slate-400">Парсер находит предпринимателей в чатах e-com, стартапов и фриланса.</p>
          </div>
          <div className="rounded-xl border border-white/5 bg-black/20 p-3 space-y-1">
            <p className="font-bold text-white">2. Просмотр Stories</p>
            <p className="text-slate-400">Пользователи видят аватарку Murasaki в списке тех, кто посмотрел их историю.</p>
          </div>
          <div className="rounded-xl border border-white/5 bg-black/20 p-3 space-y-1">
            <p className="font-bold text-white">3. Переход в портфолио</p>
            <p className="text-slate-400">Человек открывает профиль @loves_kyni, кликает на сайт и пишет в ЛС.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
