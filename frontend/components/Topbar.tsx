"use client";

import { useEffect, useState } from "react";
import { Coins, Database, ExternalLink, Plus, Radar, Radio, RefreshCw, Sparkles } from "lucide-react";
import { api, API_URL } from "@/lib/api";
import { triggerHaptic } from "@/lib/telegram";
import LLMSelectorModal from "./LLMSelectorModal";
import { Spinner } from "./ui";

export default function Topbar({
  onParse,
  onToggleSidebar,
  onRefresh,
  refreshing,
  currentView = "leads",
  onViewChange,
}: {
  onParse: () => void;
  onToggleSidebar?: () => void;
  onRefresh?: () => void;
  refreshing?: boolean;
  currentView?: "leads" | "telegram";
  onViewChange?: (view: "leads" | "telegram") => void;
}) {
  const [showLLMModal, setShowLLMModal] = useState(false);
  const [activeModel, setActiveModel] = useState<string>("gpt-4o");

  useEffect(() => {
    api
      .getLLMConfig()
      .then((cfg) => {
        if (cfg?.model) setActiveModel(cfg.model);
      })
      .catch(() => {});
  }, []);

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-[#09090d]/85 backdrop-blur-xl">
        <div className="flex h-16 items-center justify-between gap-3 px-4 lg:px-8">
          {/* Слева: Название + бренд */}
          <div className="flex items-center gap-2.5">
            <div className="relative flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-fuchsia-500 text-white shadow-[0_0_16px_rgba(124,92,255,0.35)]">
              <Radar size={17} />
              <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-emerald-400 ring-2 ring-[#09090d]" />
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[15px] font-black tracking-tight text-white">LeadRadar</span>
              <span className="rounded bg-brand-500/15 px-1.5 py-0.5 text-[9px] font-extrabold uppercase tracking-wider text-brand-300 border border-brand-500/20">
                PRO
              </span>
            </div>
          </div>

          {/* Десктопная навигация */}
          {onViewChange && (
            <div className="hidden md:flex items-center gap-1 rounded-xl border border-white/[0.08] bg-[#12131a]/80 p-1">
              <button
                onClick={() => {
                  triggerHaptic("light");
                  onViewChange("leads");
                }}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  currentView === "leads"
                    ? "bg-brand-500 text-white shadow-[0_0_18px_rgba(124,92,255,0.4)]"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <Database size={13} />
                Карты
              </button>
              <button
                onClick={() => {
                  triggerHaptic("light");
                  onViewChange("telegram");
                }}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  currentView === "telegram"
                    ? "bg-brand-500 text-white shadow-[0_0_18px_rgba(124,92,255,0.4)]"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <Radio size={13} className={currentView === "telegram" ? "animate-pulse" : ""} />
                TG-Радар
              </button>
            </div>
          )}

          {/* Справа: кликабельный баланс SOL + целевая кнопка + Собрать */}
          <div className="flex items-center gap-2">
            {/* Кликабельный баланс SOL / активная модель */}
            <button
              onClick={() => {
                triggerHaptic("light");
                setShowLLMModal(true);
              }}
              className="group flex items-center gap-1.5 rounded-xl border border-white/[0.08] bg-[#13131a]/90 px-2.5 py-1.5 text-xs font-medium text-slate-200 transition hover:border-brand-500/50 hover:bg-[#181824]"
              title="Баланс SOL и настройки нейросети"
            >
              <Coins size={13} className="text-amber-400 group-hover:scale-110 transition-transform" />
              <span className="font-mono text-[11px] font-bold text-amber-300">0.85 SOL</span>
              <span className="text-slate-600">·</span>
              <span className="font-mono text-[11px] text-slate-400 group-hover:text-slate-200">
                {activeModel.replace("gpt-", "")}
              </span>
            </button>

            {/* Десктопные кнопки */}
            {onRefresh && (
              <button
                onClick={() => {
                  triggerHaptic("light");
                  onRefresh();
                }}
                className="icon-btn hidden sm:inline-flex"
                title="Обновить данные"
                aria-label="Обновить"
              >
                {refreshing ? <Spinner size={14} /> : <RefreshCw size={14} />}
              </button>
            )}

            {/* Главная целевая кнопка */}
            <button
              onClick={() => {
                triggerHaptic("medium");
                onParse();
              }}
              className="btn-primary"
            >
              <Plus size={15} />
              <span className="text-xs font-bold sm:inline">Собрать</span>
            </button>
          </div>
        </div>
      </header>

      <LLMSelectorModal
        isOpen={showLLMModal}
        onClose={() => setShowLLMModal(false)}
        onModelChanged={(model) => setActiveModel(model)}
      />
    </>
  );
}
