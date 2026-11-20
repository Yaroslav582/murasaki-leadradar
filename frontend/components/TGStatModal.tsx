"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  Check,
  CheckSquare,
  ExternalLink,
  Filter,
  Key,
  Plus,
  Radio,
  RefreshCw,
  Search,
  Sparkles,
  Square,
  Users,
  X,
  Zap,
} from "lucide-react";
import Modal from "./Modal";
import { api } from "@/lib/api";
import { triggerHaptic } from "@/lib/telegram";
import type { TGStatItem, TGStatStatus } from "@/lib/types";
import { Spinner } from "./ui";

const QUICK_TAGS = [
  "фриланс заказы",
  "веб разработка",
  "дизайн сайтов",
  "чат фрилансеров",
  "it вакансии",
  "разработка ботов",
  "маркетинг",
];

const CATEGORIES = [
  { label: "Все категории", value: "all" },
  { label: "Фриланс", value: "freelance" },
  { label: "Бизнес", value: "business" },
  { label: "Разработка", value: "development" },
  { label: "Дизайн", value: "design" },
  { label: "Маркетинг", value: "marketing" },
];

export default function TGStatModal({
  open,
  onClose,
  onSuccess,
  showToast,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  showToast: (message: string, variant?: "success" | "error" | "info") => void;
}) {
  const [status, setStatus] = useState<TGStatStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(false);

  // Form params
  const [keywords, setKeywords] = useState("фриланс заказы, веб разработка, дизайн сайтов");
  const [category, setCategory] = useState("freelance");
  const [minMembers, setMinMembers] = useState(100);
  const [minCi, setMinCi] = useState(5.0);

  // Token editor
  const [showTokenInput, setShowTokenInput] = useState(false);
  const [tokenDraft, setTokenDraft] = useState("");
  const [savingToken, setSavingToken] = useState(false);

  // Search state
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<TGStatItem[]>([]);
  const [selectedHandles, setSelectedHandles] = useState<Set<string>>(new Set());
  const [targetKind, setTargetKind] = useState<"both" | "orders" | "promo">("both");
  const [addingTargets, setAddingTargets] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  useEffect(() => {
    if (open) {
      loadStatus();
    }
  }, [open]);

  const loadStatus = async () => {
    setLoadingStatus(true);
    try {
      const res = await api.getTGStatStatus();
      setStatus(res);
    } catch (err) {
      console.error("Failed to load TGStat status:", err);
    } finally {
      setLoadingStatus(false);
    }
  };

  const handleSaveToken = async () => {
    if (!tokenDraft.trim()) {
      showToast("Введите токен API TGStat", "error");
      return;
    }
    setSavingToken(true);
    try {
      await api.saveTGStatToken(tokenDraft.trim());
      showToast("Токен TGStat успешно сохранён!", "success");
      setShowTokenInput(false);
      setTokenDraft("");
      await loadStatus();
    } catch (err) {
      showToast("Ошибка сохранения токена", "error");
    } finally {
      setSavingToken(false);
    }
  };

  const handleToggleTag = (tag: string) => {
    triggerHaptic("light");
    const current = keywords.split(",").map((k) => k.trim()).filter(Boolean);
    if (current.includes(tag)) {
      setKeywords(current.filter((k) => k !== tag).join(", "));
    } else {
      setKeywords(current.concat(tag).join(", "));
    }
  };

  const handleSearch = async () => {
    triggerHaptic("medium");
    setSearching(true);
    setHasSearched(true);
    try {
      const res = await api.searchTGStat({
        keywords: keywords.trim(),
        category: category,
        min_ci: minCi,
        min_members: minMembers,
      });

      setResults(res.items);
      // Pre-select items that are not already added
      const newHandles = new Set<string>();
      res.items.forEach((item) => {
        if (!item.is_already_added) {
          newHandles.add(item.username_or_link);
        }
      });
      setSelectedHandles(newHandles);

      if (res.items.length === 0) {
        showToast("По заданным критериям чаты не найдены. Попробуйте изменить ключевые слова.", "info");
      } else {
        showToast(
          res.used_token
            ? `TGStat API: найдено ${res.items.length} активных чатов!`
            : `Загружено ${res.items.length} проверенных фриланс-чатов из базы!`,
          "success"
        );
      }
    } catch (err: any) {
      showToast(err?.message || "Ошибка при поиске чатов через TGStat", "error");
    } finally {
      setSearching(false);
    }
  };

  const handleToggleSelect = (handle: string) => {
    triggerHaptic("light");
    const next = new Set(selectedHandles);
    if (next.has(handle)) {
      next.delete(handle);
    } else {
      next.add(handle);
    }
    setSelectedHandles(next);
  };

  const handleSelectAll = (select: boolean) => {
    triggerHaptic("light");
    if (!select) {
      setSelectedHandles(new Set());
    } else {
      const next = new Set<string>();
      results.forEach((item) => {
        if (!item.is_already_added) {
          next.add(item.username_or_link);
        }
      });
      setSelectedHandles(next);
    }
  };

  const handleAddSelected = async () => {
    const toAdd = results.filter((item) => selectedHandles.has(item.username_or_link));
    if (toAdd.length === 0) {
      showToast("Выберите хотя бы один чат для добавления", "error");
      return;
    }

    setAddingTargets(true);
    triggerHaptic("medium");
    try {
      const res = await api.addTGStatTargets(toAdd, targetKind, 120);
      showToast(`Успешно добавлено ${res.added_count} чатов в мониторинг!`, "success");
      onSuccess();
      onClose();
    } catch (err: any) {
      showToast(err?.message || "Ошибка при добавлении чатов", "error");
    } finally {
      setAddingTargets(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} className="max-w-2xl">
      <div className="relative max-h-[90vh] overflow-y-auto rounded-2xl border border-white/10 bg-[#17181F] p-5 shadow-2xl sm:p-6 text-white scrollbar-thin">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 border-b border-white/10 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600/30 to-brand-500/30 border border-brand-500/40 text-brand-400">
              <Sparkles size={20} className="text-amber-400" />
            </div>
            <div>
              <h2 className="text-base sm:text-lg font-bold text-white flex items-center gap-2">
                Парсер чатов TGStat
                <span className="rounded-full bg-violet-500/20 px-2 py-0.5 text-[10px] font-semibold text-violet-300 border border-violet-500/30">
                  api.tgstat.ru
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Автоматический поиск живых фриланс-чатов, групп и каналов с обсуждениями
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 transition hover:bg-white/10 hover:text-white"
          >
            <X size={18} />
          </button>
        </div>

        {/* API Token Connection Bar */}
        <div className="my-4 rounded-xl border border-white/[0.08] bg-[#1F222C] p-3 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${status?.has_token ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`} />
              <span className="font-medium text-slate-200">
                {status?.has_token ? (
                  <>
                    TGStat API подключён{" "}
                    {status.token_preview && (
                      <span className="font-mono text-[11px] text-slate-400">({status.token_preview})</span>
                    )}
                  </>
                ) : (
                  <>Демо-база чатов активирована</>
                )}
              </span>
            </div>
            <button
              onClick={() => setShowTokenInput(!showTokenInput)}
              className="flex items-center gap-1 text-[11px] font-medium text-brand-400 hover:text-brand-300 transition"
            >
              <Key size={12} />
              {showTokenInput ? "Скрыть" : status?.has_token ? "Изменить токен" : "Указать API токен"}
            </button>
          </div>

          {!status?.has_token && !showTokenInput && (
            <p className="mt-1.5 text-[11px] text-slate-400">
              Поиск работает по проверенной выборке фриланс-чатов. Для поиска по миллионам каналов укажите токен с{" "}
              <a
                href="https://api.tgstat.ru"
                target="_blank"
                rel="noreferrer"
                className="text-brand-400 underline hover:text-brand-300"
              >
                api.tgstat.ru
              </a>
              .
            </p>
          )}

          {showTokenInput && (
            <div className="mt-3 flex items-center gap-2 border-t border-white/10 pt-3">
              <input
                type="text"
                value={tokenDraft}
                onChange={(e) => setTokenDraft(e.target.value)}
                placeholder="Вставьте TGStat API Token..."
                className="input-text text-xs flex-1 bg-[#13141B] border-white/10"
              />
              <button
                onClick={handleSaveToken}
                disabled={savingToken}
                className="btn-primary text-xs shrink-0 px-3 py-1.5"
              >
                {savingToken ? <Spinner size={12} /> : "Сохранить"}
              </button>
            </div>
          )}
        </div>

        {/* Search Parameters */}
        <div className="space-y-3.5">
          {/* Keywords input */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-300">
              Ключевые слова (через запятую)
            </label>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-3 text-slate-400" />
              <input
                type="text"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="фриланс, разработка сайтов, дизайн..."
                className="input-text text-xs w-full pl-9 bg-[#1F222C] border-white/10 text-white placeholder:text-slate-500"
              />
            </div>
            {/* Quick tag chips */}
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] text-slate-400">Быстрые теги:</span>
              {QUICK_TAGS.map((tag) => {
                const active = keywords.includes(tag);
                return (
                  <button
                    key={tag}
                    onClick={() => handleToggleTag(tag)}
                    className={`rounded-md px-2 py-0.5 text-[11px] font-medium transition ${
                      active
                        ? "bg-brand-500 text-white"
                        : "bg-white/[0.04] text-slate-400 hover:bg-white/[0.08] hover:text-white"
                    }`}
                  >
                    {tag}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Category & Filters */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div>
              <label className="mb-1 block text-slate-300 font-medium">Категория TGStat</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="input-text text-xs w-full bg-[#1F222C] border-white/10 text-white"
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-slate-300 font-medium">Мин. участников в чате</label>
              <select
                value={minMembers}
                onChange={(e) => setMinMembers(Number(e.target.value))}
                className="input-text text-xs w-full bg-[#1F222C] border-white/10 text-white"
              >
                <option value={50}>От 50 участников</option>
                <option value={100}>От 100 участников (рекомендуется)</option>
                <option value={500}>От 500 участников</option>
                <option value={1000}>От 1 000 участников</option>
                <option value={5000}>От 5 000 участников</option>
              </select>
            </div>
          </div>

          {/* Search Button */}
          <button
            onClick={handleSearch}
            disabled={searching}
            className="w-full btn-primary py-2.5 text-xs font-semibold flex items-center justify-center gap-2 bg-gradient-to-r from-violet-600 to-brand-500 hover:from-violet-500 hover:to-brand-400 shadow-lg shadow-violet-900/30"
          >
            {searching ? (
              <>
                <Spinner size={14} />
                <span>Поиск супергрупп и чатов на TGStat...</span>
              </>
            ) : (
              <>
                <Search size={14} />
                <span>Найти чаты по параметрам</span>
              </>
            )}
          </button>
        </div>

        {/* Results Section */}
        {hasSearched && (
          <div className="mt-5 border-t border-white/10 pt-4">
            <div className="flex items-center justify-between mb-3 text-xs">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white">Найденные чаты</span>
                <span className="rounded-full bg-white/10 px-2 py-0.5 text-[11px] font-mono text-slate-300">
                  {results.length}
                </span>
              </div>
              {results.length > 0 && (
                <div className="flex items-center gap-3 text-[11px]">
                  <button
                    onClick={() => handleSelectAll(true)}
                    className="text-brand-400 hover:text-brand-300 transition"
                  >
                    Выбрать все новые
                  </button>
                  <button
                    onClick={() => handleSelectAll(false)}
                    className="text-slate-400 hover:text-slate-300 transition"
                  >
                    Снять выбор
                  </button>
                </div>
              )}
            </div>

            {results.length === 0 && !searching && (
              <div className="rounded-xl border border-dashed border-white/10 p-6 text-center text-xs text-slate-400">
                Чатов не найдено. Попробуйте расширить ключевые слова или снизить порог участников.
              </div>
            )}

            {results.length > 0 && (
              <div className="space-y-2 max-h-64 overflow-y-auto pr-1 scrollbar-thin">
                {results.map((item) => {
                  const isSelected = selectedHandles.has(item.username_or_link);
                  const cleanLink = item.username_or_link.startsWith("http")
                    ? item.username_or_link
                    : `https://t.me/${item.username_or_link.replace("@", "")}`;

                  return (
                    <div
                      key={item.username_or_link}
                      onClick={() => !item.is_already_added && handleToggleSelect(item.username_or_link)}
                      className={`flex items-center justify-between gap-3 rounded-xl border p-3 text-xs transition cursor-pointer ${
                        item.is_already_added
                          ? "border-white/5 bg-[#171821]/60 opacity-60 cursor-default"
                          : isSelected
                          ? "border-brand-500/50 bg-brand-500/[0.08]"
                          : "border-white/5 bg-[#1F222C] hover:border-white/15"
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        {item.is_already_added ? (
                          <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-emerald-500/20 text-emerald-400">
                            <Check size={12} />
                          </div>
                        ) : (
                          <button
                            type="button"
                            className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border transition ${
                              isSelected
                                ? "bg-brand-500 border-brand-500 text-white"
                                : "border-white/20 bg-white/5"
                            }`}
                          >
                            {isSelected && <Check size={12} />}
                          </button>
                        )}

                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-white truncate max-w-[200px] sm:max-w-[280px]">
                              {item.title || item.username_or_link}
                            </span>
                            <a
                              href={cleanLink}
                              target="_blank"
                              rel="noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="text-slate-400 hover:text-brand-400 transition"
                              title="Открыть в Telegram"
                            >
                              <ExternalLink size={11} />
                            </a>
                          </div>
                          <div className="flex items-center gap-2 mt-0.5 text-[11px] text-slate-400">
                            <span className="font-mono text-brand-300">{item.username_or_link}</span>
                            <span>•</span>
                            <span className="flex items-center gap-1 text-slate-300">
                              <Users size={10} />
                              {item.members_count.toLocaleString("ru-RU")}
                            </span>
                            {item.category && (
                              <>
                                <span>•</span>
                                <span className="rounded bg-white/5 px-1.5 py-0.2 text-[10px] text-slate-400">
                                  {item.category}
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="shrink-0 text-right">
                        {item.is_already_added ? (
                          <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400 border border-emerald-500/20">
                            В мониторинге
                          </span>
                        ) : isSelected ? (
                          <span className="rounded-full bg-brand-500/20 px-2 py-0.5 text-[10px] font-medium text-brand-300 border border-brand-500/30">
                            Выбран
                          </span>
                        ) : (
                          <span className="text-[11px] text-slate-500">Нажмите для выбора</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Bottom target kind selector & action button */}
            {results.length > 0 && selectedHandles.size > 0 && (
              <div className="mt-4 pt-4 border-t border-white/10 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-slate-400">Назначение:</span>
                  <select
                    value={targetKind}
                    onChange={(e: any) => setTargetKind(e.target.value)}
                    className="input-text text-xs bg-[#1F222C] border-white/10 py-1 px-2 text-white"
                  >
                    <option value="both">Оба: Заказы и автопостинг</option>
                    <option value="orders">Только мониторинг заказов</option>
                    <option value="promo">Только автопостинг</option>
                  </select>
                </div>

                <button
                  onClick={handleAddSelected}
                  disabled={addingTargets}
                  className="btn-primary text-xs py-2 px-4 flex items-center gap-1.5"
                >
                  {addingTargets ? <Spinner size={12} /> : <Plus size={13} />}
                  <span>Добавить выбранные ({selectedHandles.size})</span>
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}

