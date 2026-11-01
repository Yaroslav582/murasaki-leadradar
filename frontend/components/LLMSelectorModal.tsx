"use client";

import { useEffect, useState } from "react";
import { Bot, Check, Cpu, Key, Server, Sparkles, X } from "lucide-react";
import { api } from "@/lib/api";
import { triggerHaptic } from "@/lib/telegram";
import type { LLMConfig, LLMPreset } from "@/lib/types";

export default function LLMSelectorModal({
  isOpen,
  onClose,
  onModelChanged,
}: {
  isOpen: boolean;
  onClose: () => void;
  onModelChanged?: (modelName: string) => void;
}) {
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showCustom, setShowCustom] = useState(false);

  // Custom inputs
  const [customModel, setCustomModel] = useState("");
  const [customBaseUrl, setCustomBaseUrl] = useState("");
  const [customApiKey, setCustomApiKey] = useState("");

  useEffect(() => {
    if (isOpen) {
      loadConfig();
    }
  }, [isOpen]);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const cfg = await api.getLLMConfig();
      setConfig(cfg);
      setCustomModel(cfg.model);
      setCustomBaseUrl(cfg.base_url);
    } catch (err) {
      console.error("Failed to load LLM config:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPreset = async (preset: LLMPreset) => {
    setSaving(true);
    triggerHaptic("medium");
    try {
      const updated = await api.updateLLMConfig({
        provider: preset.provider,
        model: preset.id,
        base_url: preset.base_url,
      });
      setConfig(updated);
      if (onModelChanged) {
        onModelChanged(preset.id);
      }
      onClose();
    } catch (err) {
      console.error("Failed to update LLM:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveCustom = async () => {
    if (!customModel.trim()) return;
    setSaving(true);
    triggerHaptic("medium");
    try {
      const updated = await api.updateLLMConfig({
        provider: "openai",
        model: customModel.trim(),
        base_url: customBaseUrl.trim() || undefined,
        api_key: customApiKey.trim() || undefined,
      });
      setConfig(updated);
      if (onModelChanged) {
        onModelChanged(customModel.trim());
      }
      onClose();
    } catch (err) {
      console.error("Failed to update custom LLM:", err);
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-xl rounded-2xl border border-white/10 bg-[#0d0f1a] p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/[0.08]">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-500/10 text-brand-400 ring-1 ring-brand-500/25">
              <Sparkles size={18} />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Выбор нейросети</h3>
              <p className="text-xs text-slate-400">Генерация лендингов, аутрич-сообщений и откликов в TG</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-white/[0.06] hover:text-white transition"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="mt-4 space-y-4 max-h-[70vh] overflow-y-auto pr-1">
          {loading ? (
            <div className="py-12 text-center text-slate-400 text-sm">Загрузка моделей...</div>
          ) : (
            <>
              <div className="grid gap-2 sm:grid-cols-1">
                {config?.presets.map((preset) => {
                  const isActive = config.model === preset.id;
                  return (
                    <div
                      key={preset.id}
                      onClick={() => !saving && handleSelectPreset(preset)}
                      className={`group relative flex cursor-pointer items-start justify-between rounded-xl border p-3.5 transition ${
                        isActive
                          ? "border-brand-500/60 bg-brand-500/[0.08] ring-1 ring-brand-500/30"
                          : "border-white/[0.07] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]"
                      }`}
                    >
                      <div className="space-y-1 pr-3">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm text-white">{preset.name}</span>
                          {preset.badge && (
                            <span
                              className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                preset.badge === "Рекомендовано"
                                  ? "bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/30"
                                  : "bg-white/[0.08] text-slate-300"
                              }`}
                            >
                              {preset.badge}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-400 leading-relaxed">{preset.description}</p>
                        <div className="flex items-center gap-3 pt-1 text-[11px] text-slate-500">
                          <span className="flex items-center gap-1 font-mono">
                            <Cpu size={11} /> {preset.id}
                          </span>
                          <span className="flex items-center gap-1">
                            <Server size={11} /> {preset.provider.toUpperCase()}
                          </span>
                        </div>
                      </div>

                      <div className="pt-1">
                        {isActive ? (
                          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-500 text-white shadow-md shadow-brand-500/30">
                            <Check size={14} />
                          </div>
                        ) : (
                          <div className="h-6 w-6 rounded-full border border-white/20 group-hover:border-white/40 transition" />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Custom Model Toggle */}
              <div className="pt-2 border-t border-white/[0.08]">
                <button
                  type="button"
                  onClick={() => setShowCustom(!showCustom)}
                  className="flex items-center gap-2 text-xs font-medium text-slate-400 hover:text-white transition"
                >
                  <Bot size={14} />
                  <span>{showCustom ? "Скрыть пользовательскую модель" : "+ Своя модель (Ollama / OpenRouter / OpenAI)"}</span>
                </button>

                {showCustom && (
                  <div className="mt-3 space-y-3 rounded-xl border border-white/10 bg-white/[0.02] p-4 text-xs">
                    <div>
                      <label className="block text-slate-400 mb-1">Имя модели (ID):</label>
                      <input
                        type="text"
                        value={customModel}
                        onChange={(e) => setCustomModel(e.target.value)}
                        placeholder="например: gpt-6-astra или mistral-large"
                        className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-white placeholder-slate-600 focus:border-brand-500 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">Base URL (API):</label>
                      <input
                        type="text"
                        value={customBaseUrl}
                        onChange={(e) => setCustomBaseUrl(e.target.value)}
                        placeholder="https://mxr.one/v1"
                        className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-white placeholder-slate-600 focus:border-brand-500 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">API Key (необязательно, если уже задан):</label>
                      <input
                        type="password"
                        value={customApiKey}
                        onChange={(e) => setCustomApiKey(e.target.value)}
                        placeholder="mxr_sk_..."
                        className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-white placeholder-slate-600 focus:border-brand-500 focus:outline-none"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={handleSaveCustom}
                      disabled={saving || !customModel.trim()}
                      className="btn-primary w-full py-2 text-xs font-semibold"
                    >
                      Применить свою модель
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
