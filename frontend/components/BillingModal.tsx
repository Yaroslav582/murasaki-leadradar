"use client";

import { useEffect, useState } from "react";
import {
  Check,
  Coins,
  Copy,
  CreditCard,
  Gift,
  HelpCircle,
  Share2,
  Sparkles,
  Users,
  Wallet,
  X,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import { triggerHaptic } from "@/lib/telegram";
import type { BillingBalance, CreditTransaction, ReferralInfo } from "@/lib/types";
import { Spinner } from "./ui";

export default function BillingModal({
  isOpen,
  onClose,
  showToast,
  onBalanceUpdated,
}: {
  isOpen: boolean;
  onClose: () => void;
  showToast?: (msg: string, variant?: "info" | "success" | "error") => void;
  onBalanceUpdated?: (newBalance: number) => void;
}) {
  const [activeTab, setActiveTab] = useState<"balance" | "pricing" | "referral">("balance");
  const [balance, setBalance] = useState<BillingBalance | null>(null);
  const [transactions, setTransactions] = useState<CreditTransaction[]>([]);
  const [referral, setReferral] = useState<ReferralInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [depositing, setDepositing] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    Promise.all([api.getBalance(), api.getTransactions(), api.getReferralInfo()])
      .then(([bal, txs, ref]) => {
        setBalance(bal);
        setTransactions(txs);
        setReferral(ref);
        if (onBalanceUpdated) onBalanceUpdated(bal.credits_balance);
      })
      .catch((err) => {
        if (showToast) showToast(err instanceof Error ? err.message : "Ошибка загрузки биллинга", "error");
      })
      .finally(() => setLoading(false));
  }, [isOpen]);

  if (!isOpen) return null;

  const handleDeposit = async (amount: number, method: string) => {
    setDepositing(true);
    triggerHaptic("medium");
    try {
      const res = await api.depositCredits({ amount, payment_method: method });
      setBalance((prev) => (prev ? { ...prev, credits_balance: res.credits_balance } : prev));
      if (onBalanceUpdated) onBalanceUpdated(res.credits_balance);
      if (showToast) {
        showToast(
          `Баланс успешно пополнен на +${amount} кредитов! Текущий баланс: ${res.credits_balance} cr.`,
          "success"
        );
      }
      // Reload transactions
      api.getTransactions().then(setTransactions).catch(() => {});
    } catch (e) {
      if (showToast) showToast(e instanceof Error ? e.message : "Ошибка пополнения", "error");
    } finally {
      setDepositing(false);
    }
  };

  const handleCopyLink = () => {
    if (!referral?.referral_link) return;
    navigator.clipboard.writeText(referral.referral_link);
    setCopied(true);
    triggerHaptic("light");
    if (showToast) showToast("Реферальная ссылка скопирована в буфер!", "success");
    setTimeout(() => setCopied(false), 2500);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg rounded-2xl border border-white/[0.08] bg-[#1A1C23] p-5 shadow-2xl space-y-4 animate-fadeIn max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#242731] border border-white/[0.08] text-[#F59E0B]">
              <Coins size={18} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-[#F3F4F6] flex items-center gap-2">
                Тариф и Кредиты
                <span className="rounded-md bg-[rgba(139,92,246,0.14)] border border-[rgba(139,92,246,0.3)] px-1.5 py-0.2 text-[10px] font-medium text-[#C4B5FD]">
                  SaaS
                </span>
              </h2>
              <p className="text-xs text-[#6B7280]">Монетизация и 2-уровневая рефералка</p>
            </div>
          </div>
          <button onClick={onClose} className="icon-btn !h-7 !w-7">
            <X size={14} />
          </button>
        </div>

        {/* Tab switch */}
        <div className="flex rounded-lg border border-white/[0.07] bg-[#111216] p-1 shrink-0">
          <button
            onClick={() => setActiveTab("balance")}
            className={`flex-1 rounded-md py-1 text-xs font-medium transition ${
              activeTab === "balance"
                ? "bg-[#8B5CF6] text-white"
                : "text-[#9CA3AF] hover:text-[#F3F4F6]"
            }`}
          >
            Баланс и Оплата
          </button>
          <button
            onClick={() => setActiveTab("pricing")}
            className={`flex-1 rounded-md py-1 text-xs font-medium transition ${
              activeTab === "pricing"
                ? "bg-[#8B5CF6] text-white"
                : "text-[#9CA3AF] hover:text-[#F3F4F6]"
            }`}
          >
            Списание кредитов
          </button>
          <button
            onClick={() => setActiveTab("referral")}
            className={`flex-1 rounded-md py-1 text-xs font-medium transition ${
              activeTab === "referral"
                ? "bg-[#8B5CF6] text-white"
                : "text-[#9CA3AF] hover:text-[#F3F4F6]"
            }`}
          >
            Рефералка 15%
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto space-y-4 pr-1">
          {loading ? (
            <div className="flex h-40 items-center justify-center">
              <Spinner size={24} />
            </div>
          ) : activeTab === "balance" ? (
            <div className="space-y-4">
              {/* Balance card */}
              <div className="rounded-xl border border-white/[0.08] bg-[#242731] p-4 text-center relative overflow-hidden">
                <span className="text-xs font-medium text-[#9CA3AF]">
                  Доступный баланс
                </span>
                <div className="mt-1 flex items-center justify-center gap-2">
                  <Coins size={22} className="text-[#F59E0B]" />
                  <span className="text-3xl font-semibold tracking-tight text-[#F3F4F6] font-mono tabular-nums">
                    {balance?.credits_balance ?? 0}
                  </span>
                  <span className="text-xs font-medium text-[#F59E0B]">кредитов</span>
                </div>
                <p className="mt-1 text-xs text-[#6B7280]">
                  1 кредит ≈ 1 AI-отклик или сообщение рассылки
                </p>
              </div>

              {/* Deposit Packages */}
              <div>
                <p className="label mb-2">Выберите пакет пополнения</p>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { amount: 50, price: "250 ₽", badge: "Старт" },
                    { amount: 200, price: "790 ₽", badge: "Хит -20%" },
                    { amount: 500, price: "1 590 ₽", badge: "PRO -35%" },
                  ].map((pkg) => (
                    <div
                      key={pkg.amount}
                      className="rounded-lg border border-white/[0.08] bg-[#242731] p-3 text-center space-y-1.5 hover:border-[#8B5CF6]/40 transition"
                    >
                      <span className="inline-block rounded-md bg-[rgba(139,92,246,0.14)] border border-[rgba(139,92,246,0.3)] px-1.5 py-0.2 text-[9px] font-medium text-[#C4B5FD]">
                        {pkg.badge}
                      </span>
                      <p className="text-sm font-semibold text-[#F3F4F6] font-mono tabular-nums">+{pkg.amount} cr</p>
                      <p className="text-xs text-[#9CA3AF] font-mono tabular-nums">{pkg.price}</p>
                      <button
                        onClick={() => handleDeposit(pkg.amount, "stars")}
                        disabled={depositing}
                        className="btn-primary !w-full !px-2 !py-1 text-xs"
                      >
                        {depositing ? <Spinner size={12} /> : "Купить"}
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Payment Methods */}
              <div>
                <p className="label mb-2">Способы оплаты</p>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div className="rounded-lg border border-white/[0.06] bg-[#242731] p-2 text-center flex flex-col items-center gap-0.5">
                    <span className="text-base">⭐️</span>
                    <span className="font-medium text-[#F3F4F6]">Telegram Stars</span>
                    <span className="text-[10px] text-[#6B7280]">Мгновенно в TMA</span>
                  </div>
                  <div className="rounded-lg border border-white/[0.06] bg-[#242731] p-2 text-center flex flex-col items-center gap-0.5">
                    <span className="text-base">⚡️</span>
                    <span className="font-medium text-[#F3F4F6]">СБП / РФ Карты</span>
                    <span className="text-[10px] text-[#6B7280]">Без комиссии</span>
                  </div>
                  <div className="rounded-lg border border-white/[0.06] bg-[#242731] p-2 text-center flex flex-col items-center gap-0.5">
                    <span className="text-base">💎</span>
                    <span className="font-medium text-[#F3F4F6]">CryptoBot</span>
                    <span className="text-[10px] text-[#6B7280]">USDT / TON</span>
                  </div>
                </div>
              </div>

              {/* History */}
              <div>
                <p className="label mb-2">История операций</p>
                <div className="space-y-1.5 max-h-36 overflow-y-auto divide-y divide-white/[0.04]">
                  {transactions.length === 0 ? (
                    <p className="text-xs text-[#6B7280] text-center py-2">Транзакций пока нет</p>
                  ) : (
                    transactions.map((tx) => (
                      <div key={tx.id} className="pt-1.5 flex items-center justify-between text-xs">
                        <div className="truncate pr-2">
                          <p className="text-[#F3F4F6] font-medium truncate">{tx.description || tx.type}</p>
                          <span className="text-[10px] text-[#6B7280] font-mono tabular-nums">
                            {new Date(tx.created_at).toLocaleString([], {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                        <span
                          className={`font-mono tabular-nums font-semibold shrink-0 ${
                            tx.amount > 0 ? "text-[#10B981]" : "text-[#9CA3AF]"
                          }`}
                        >
                          {tx.amount > 0 ? `+${tx.amount}` : tx.amount} cr
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          ) : activeTab === "pricing" ? (
            <div className="space-y-3">
              <p className="text-xs text-[#9CA3AF] leading-relaxed">
                Кредиты списываются прозрачно за каждое действие в соответствии с ТЗ платформы:
              </p>

              <div className="space-y-2">
                {[
                  {
                    title: "Генерация AI-демо сайта",
                    cost: "5 cr",
                    desc: "Создание адаптивного лендинга под ключ с уникальным текстом, стилями и промо-сообщением для лида.",
                    icon: Sparkles,
                    color: "text-[#8B5CF6]",
                  },
                  {
                    title: "Парсинг 50 лидов с карт",
                    cost: "2 cr",
                    desc: "Сбор организаций без сайта с геосервисов (2GIS, Яндекс, Google, Zoon, OSM) с проверкой соцсетей и телефонов.",
                    icon: CreditCard,
                    color: "text-[#9CA3AF]",
                  },
                  {
                    title: "1 AI-отклик / нейрокоммент / аутрич",
                    cost: "1 cr",
                    desc: "Индивидуальный отклик на бирже (Kwork/FL), комментарий под постом канала или отправка касания по базе.",
                    icon: Zap,
                    color: "text-[#F59E0B]",
                  },
                  {
                    title: "1 день автопрогрева аккаунта",
                    cost: "2 cr",
                    desc: "Полный суточный цикл: чтение постов, реакции, подписка на белые каналы и взаимные кросс-диалоги фермы.",
                    icon: Users,
                    color: "text-[#10B981]",
                  },
                ].map((item, idx) => {
                  const Icon = item.icon;
                  return (
                    <div
                      key={idx}
                      className="rounded-lg border border-white/[0.06] bg-[#242731] p-3 space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Icon size={14} className={item.color} />
                          <h4 className="text-xs font-semibold text-[#F3F4F6]">{item.title}</h4>
                        </div>
                        <span className="font-mono tabular-nums text-xs font-semibold text-[#C4B5FD] bg-[rgba(139,92,246,0.14)] border border-[rgba(139,92,246,0.3)] px-1.5 py-0.2 rounded-md">
                          {item.cost}
                        </span>
                      </div>
                      <p className="text-[11px] text-[#9CA3AF] pl-5 leading-relaxed">
                        {item.desc}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            /* Referral Tab */
            <div className="space-y-3">
              <div className="rounded-xl border border-white/[0.08] bg-[#242731] p-4 space-y-2.5">
                <div className="flex items-center gap-2">
                  <Gift size={18} className="text-[#8B5CF6]" />
                  <h3 className="text-sm font-semibold text-[#F3F4F6]">Реферальная программа 15%</h3>
                </div>
                <p className="text-xs text-[#9CA3AF] leading-relaxed">
                  Приглашайте коллег по персональной ссылке. Вы получаете <span className="font-semibold text-[#F3F4F6]">15% в кредитах</span> от каждого пополнения приглашенного пользователя.
                </p>

                {/* Referral Link Box */}
                <div className="flex items-center gap-2 rounded-lg border border-white/[0.07] bg-[#111216] p-1.5 pl-3">
                  <span className="text-xs font-mono text-[#9CA3AF] truncate flex-1">
                    {referral?.referral_link || "Загрузка ссылки..."}
                  </span>
                  <button
                    onClick={handleCopyLink}
                    className="btn-primary !px-2.5 !py-1 text-xs shrink-0"
                  >
                    {copied ? <Check size={12} /> : <Copy size={12} />}
                    {copied ? "Скопировано" : "Копировать"}
                  </button>
                </div>
              </div>

              {/* Referral Stats */}
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-lg border border-white/[0.06] bg-[#242731] p-3 text-center">
                  <span className="text-[10px] uppercase font-medium text-[#6B7280]">
                    Приглашено
                  </span>
                  <p className="mt-0.5 text-xl font-semibold font-mono tabular-nums text-[#F3F4F6]">
                    {referral?.invited_count ?? 0}
                  </p>
                </div>
                <div className="rounded-lg border border-white/[0.06] bg-[#242731] p-3 text-center">
                  <span className="text-[10px] uppercase font-medium text-[#6B7280]">
                    Заработано
                  </span>
                  <p className="mt-0.5 text-xl font-semibold font-mono tabular-nums text-[#10B981]">
                    +{referral?.earned_credits ?? 0} cr
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
