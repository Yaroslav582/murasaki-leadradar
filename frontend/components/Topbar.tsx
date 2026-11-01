"use client";

import { useEffect, useState } from "react";
import { Database, ExternalLink, Menu, Plus, Radar, Radio, RefreshCw, Sparkles } from "lucide-react";
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
  onToggleSidebar: () => void;
  onRefresh: () => void;
  refreshing?: boolean;
  currentView?: "leads" | "telegram";
  onViewChange?: (view: "leads" | "telegram") => void;
}) {
  const [showLLMModal, setShowLLMModal] = useState(false);
  const [activeModel, setActiveModel] = useState<string>("gpt-6-sol");

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
      <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-[#07080f]/80 backdrop-blur-xl">
        <div className="flex h-16 items-center gap-3 px-4 lg:px-8">
          <button onClick={onToggleSidebar} className="icon-btn lg:hidden" aria-label="Открыть фильтры">
            <Menu size={17} />
          </button>

          <div className="flex items-center gap-3">
            <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-fuchsia-500 text-white shadow-glow">
              <Radar size={19} />
              <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-emerald-400 ring-2 ring-[#07080f]" />
            </div>
            <div className="leading-tight">
              <p className="flex items-center gap-2 text-[15px] font-extrabold tracking-tight text-white">
                LeadRadar
                <span className="rounded bg-white/[0.07] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-400">
                  AI
                </span>
              </p>
              <p className="hidden text-[11px] text-slate-500 sm:block">Разведка клиентов и демо-лендинги</p>
            </div>
          </div>

          {onViewChange && (
            <div className="mx-auto hidden md:flex items-center gap-1 rounded-xl border border-white/10 bg-white/[0.03] p-1">
              <button
                onClick={() => {
                  triggerHaptic("light");
                  onViewChange("leads");
                }}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  currentView === "leads"
                    ? "bg-brand-500 text-white shadow-md shadow-brand-500/25"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <Database size={13} />
                Лиды из карт
              </button>
              <button
                onClick={() => {
                  triggerHaptic("light");
                  onViewChange("telegram");
                }}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  currentView === "telegram"
                    ? "bg-brand-500 text-white shadow-md shadow-brand-500/25"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <Radio size={13} className={currentView === "telegram" ? "animate-pulse" : ""} />
                TG-Радар заказов
              </button>
            </div>
          )}

          <div className="ml-auto flex items-center gap-2">
            {/* AI Model Selector Button */}
            <button
              onClick={() => {
                triggerHaptic("light");
                setShowLLMModal(true);
              }}
              className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-xs font-medium text-slate-300 transition hover:border-brand-500/40 hover:bg-white/[0.07]"
              title="Сменить активную нейросеть"
            >
              <Sparkles size={13} className="text-brand-400" />
              <span className="hidden sm:inline font-mono text-[11px] font-semibold">{activeModel}</span>
              <span className="sm:hidden font-mono text-[11px]">{activeModel.replace("gpt-", "")}</span>
            </button>

            <a
              href={`${API_URL}/docs`}
              target="_blank"
              rel="noopener noreferrer"
              className="hidden items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-xs font-medium text-slate-400 transition hover:bg-white/[0.05] hover:text-white lg:inline-flex"
            >
              API
              <ExternalLink size={12} />
            </a>
            <button onClick={onRefresh} className="icon-btn" title="Обновить данные" aria-label="Обновить данные">
              {refreshing ? <Spinner size={15} /> : <RefreshCw size={15} />}
            </button>
            <button onClick={onParse} className="btn-primary">
              <Plus size={16} />
              <span className="hidden sm:inline">Собрать лиды</span>
              <span className="sm:hidden">Собрать</span>
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
