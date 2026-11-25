"use client";

import { useEffect, useState } from "react";
import { Coins, Database, MessageSquare, Plus, Radar, Radio, RefreshCw, Settings, Sparkles, Users } from "lucide-react";
import { api } from "@/lib/api";
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
  onOpenBilling,
}: {
  onParse: () => void;
  onToggleSidebar?: () => void;
  onRefresh?: () => void;
  refreshing?: boolean;
  currentView?: "leads" | "telegram" | "accounts" | "inbox";
  onViewChange?: (view: "leads" | "telegram" | "accounts" | "inbox") => void;
  onOpenBilling?: () => void;
}) {
  const [showLLMModal, setShowLLMModal] = useState(false);
  const [activeModel, setActiveModel] = useState<string>("gpt-4o");
  const [credits, setCredits] = useState<number>(50);

  useEffect(() => {
    api
      .getLLMConfig()
      .then((cfg) => {
        if (cfg?.model) setActiveModel(cfg.model);
      })
      .catch(() => {});

    api
      .getBalance()
      .then((bal) => {
        if (typeof bal?.credits_balance === "number") setCredits(bal.credits_balance);
      })
      .catch(() => {});
  }, []);

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-[#22252A] bg-[#0B0C0E]/95 backdrop-blur-sm">
        <div className="flex h-14 items-center justify-between gap-3 px-4 lg:px-8">
          {/* Слева: Название + бренд */}
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-[#2A2E35] bg-[#181A1F] text-[#F4F4F5]">
              <Radar size={14} />
            </div>
            <span className="text-sm font-semibold tracking-tight text-[#F4F4F5]">LeadRadar</span>
          </div>

          {/* Десктопная навигация */}
          {onViewChange && (
            <div className="hidden md:flex items-center gap-1 rounded-lg border border-[#22252A] bg-[#121417] p-1">
              <button
                onClick={() => {
                  triggerHaptic("light");
                  onViewChange("leads");
                }}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition ${
                  currentView === "leads"
                    ? "bg-[#22252A] text-white"
                    : "text-[#A1A1AA] hover:text-white"
                }`}
              >
                <Database size={13} />
                Лиды
              </button>
              <button
                onClick={() => {
                  triggerHaptic("light");
                  onViewChange("telegram");
                }}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition ${
                  currentView === "telegram"
                    ? "bg-[#22252A] text-white"
                    : "text-[#A1A1AA] hover:text-white"
                }`}
              >
                <Radio size={13} />
                TG-Радар
              </button>
              <button
                onClick={() => {
                  triggerHaptic("light");
                  onViewChange("accounts");
                }}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition ${
                  currentView === "accounts"
                    ? "bg-[#22252A] text-white"
                    : "text-[#A1A1AA] hover:text-white"
                }`}
              >
                <Users size={13} />
                Аккаунты
              </button>
              <button
                onClick={() => {
                  triggerHaptic("light");
                  onViewChange("inbox");
                }}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition ${
                  currentView === "inbox"
                    ? "bg-[#22252A] text-white"
                    : "text-[#A1A1AA] hover:text-white"
                }`}
              >
                <MessageSquare size={13} />
                Диалоги
              </button>
            </div>
          )}

          {/* Справа: кликабельный баланс кредитов + настройки LLM + Собрать */}
          <div className="flex items-center gap-2">
            {/* Кликабельный баланс кредитов */}
            <button
              onClick={() => {
                triggerHaptic("light");
                if (onOpenBilling) onOpenBilling();
              }}
              className="group flex items-center gap-1.5 rounded-lg border border-white/[0.07] bg-[#242731] px-2.5 py-1 text-xs font-medium text-[#F3F4F6] transition hover:border-brand-500/40 hover:bg-[#2C303D]"
              title="Баланс кредитов и пополнение"
            >
              <Coins size={13} className="text-[#F59E0B] group-hover:scale-105 transition-transform" />
              <span className="font-mono tabular-nums tracking-tight text-xs font-medium text-[#F59E0B]">{credits} cr</span>
            </button>

            {/* Кнопка настроек LLM */}
            <button
              onClick={() => {
                triggerHaptic("light");
                setShowLLMModal(true);
              }}
              className="icon-btn hidden sm:inline-flex"
              title="Выбор AI-модели"
            >
              <Sparkles size={13} className="text-brand-300" />
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
                {refreshing ? <Spinner size={13} /> : <RefreshCw size={13} />}
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
              <Plus size={14} />
              <span className="text-xs font-medium sm:inline">Собрать</span>
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
