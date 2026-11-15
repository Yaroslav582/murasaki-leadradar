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
      <div className="relative w-full max-w-lg rounded-2xl border border-white/10 bg-[#13131a] p-6 shadow-2xl space-y-5 animate-fadeIn max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-500/20 to-brand-500/20 border border-amber-500/30 text-amber-300">
              <Coins size={20} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                Тариф и Кредиты
                <span className="rounded-full bg-brand-500/20 border border-brand-500/30 px-2 py-0.5 text-[10px] font-bold text-brand-300">
                  SaaS
                </span>
              </h2>
              <p className="text-xs text-slate-400">Монетизация и 2-уровневая рефералка</p>
            </div>
          </div>
          <button onClick={onClose} className="icon-btn !h-8 !w-8">
            <X size={15} />
          </button>
        </div>

        {/* Tab switch */}
        <div className="flex rounded-xl border border-white/[0.08] bg-[#0c0d12] p-1 shrink-0">
          <button
            onClick={() => setActiveTab("balance")}
            className={`flex-1 rounded-lg py-1.5 text-xs font-semibold transition ${
              activeTab === "balance"
                ? "bg-brand-500 text-white shadow-[0_0_12px_rgba(124,92,255,0.4)]"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Баланс и Оплата
          </button>
          <button
            onClick={() => setActiveTab("pricing")}
            className={`flex-1 rounded-lg py-1.5 text-xs font-semibold transition ${
              activeTab === "pricing"
                ? "bg-brand-500 text-white shadow-[0_0_12px_rgba(124,92,255,0.4)]"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Списание кредитов
          </button>
          <button
            onClick={() => setActiveTab("referral")}
            className={`flex-1 rounded-lg py-1.5 text-xs font-semibold transition ${
              activeTab === "referral"
                ? "bg-brand-500 text-white shadow-[0_0_12px_rgba(124,92,255,0.4)]"
                : "text-slate-400 hover:text-white"
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
              <div className="rounded-2xl border border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-brand-500/5 to-transparent p-5 text-center relative overflow-hidden">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-amber-300">
                  Доступный баланс
                </span>
                <div className="mt-1 flex items-center justify-center gap-2">
                  <Coins size={26} className="text-amber-400" />
                  <span className="text-4xl font-black tracking-tight text-white font-mono">
                    {balance?.credits_balance ?? 0}
                  </span>
                  <span className="text-sm font-bold text-amber-400">кредитов</span>
                </div>
                <p className="mt-1 text-[11px] text-slate-400">
                  1 кредит ≈ 1 AI-отклик или сообщение рассылки
                </p>
              </div>

              {/* Deposit Packages */}
              <div>
                <p className="label mb-2">Выберите пакет пополнения</p>
                <div className="grid grid-cols-3 gap-2.5">
                  {[
                    { amount: 50, price: "250 ₽", badge: "Старт" },
                    { amount: 200, price: "790 ₽", badge: "Хит -20%" },
                    { amount: 500, price: "1 590 ₽", badge: "PRO -35%" },
                  ].map((pkg) => (
                    <div
                      key={pkg.amount}
                      className="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-center space-y-1.5 hover:border-brand-500/40 transition"
                    >
                      <span className="inline-block rounded-full bg-brand-500/20 px-1.5 py-0.5 text-[9px] font-bold text-brand-300">
                        {pkg.badge}
                      </span>
                      <p className="text-sm font-bold text-white font-mono">+{pkg.amount} cr</p>
                      <p className="text-xs font-semibold text-slate-400">{pkg.price}</p>
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
                  <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2.5 text-center flex flex-col items-center gap-1">
                    <span className="text-lg">⭐️</span>
                    <span className="font-bold text-slate-200">Telegram Stars</span>
                    <span className="text-[10px] text-slate-500">Мгновенно в TMA</span>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2.5 text-center flex flex-col items-center gap-1">
                    <span className="text-lg">⚡️</span>
                    <span className="font-bold text-slate-200">СБП / РФ Карты</span>
                    <span className="text-[10px] text-slate-500">Без комиссии</span>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2.5 text-center flex flex-col items-center gap-1">
                    <span className="text-lg">💎</span>
                    <span className="font-bold text-slate-200">CryptoBot</span>
                    <span className="text-[10px] text-slate-500">USDT / TON</span>
                  </div>
                </div>
              </div>

              {/* History */}
              <div>
                <p className="label mb-2">История операций</p>
                <div className="space-y-1.5 max-h-40 overflow-y-auto divide-y divide-white/[0.04]">
                  {transactions.length === 0 ? (
                    <p className="text-xs text-slate-500 text-center py-2">Транзакций пока нет</p>
                  ) : (
                    transactions.map((tx) => (
                      <div key={tx.id} className="pt-1.5 flex items-center justify-between text-xs">
                        <div className="truncate pr-2">
                          <p className="text-slate-300 font-medium truncate">{tx.description || tx.type}</p>
                          <span className="text-[10px] text-slate-500">
                            {new Date(tx.created_at).toLocaleString([], {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                        <span
                          className={`font-mono font-bold shrink-0 ${
                            tx.amount > 0 ? "text-emerald-400" : "text-slate-400"
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
              <p className="text-xs text-slate-300 leading-relaxed">
                Кредиты списываются прозрачно за каждое действие в соответствии с ТЗ платформы:
              </p>

              <div className="space-y-2">
                {[
                  {
                    title: "Генерация AI-демо сайта",
                    cost: "5 кредитов",
                    desc: "Создание адаптивного лендинга под ключ с уникальным текстом, стилями и промо-сообщением для лида.",
                    icon: Sparkles,
                    color: "text-brand-300",
                  },
                  {
                    title: "Парсинг 50 лидов с карт",
                    cost: "2 кредита",
                    desc: "Сбор организаций без сайта с геосервисов (2GIS, Яндекс, Google, Zoon, OSM) с проверкой соцсетей и телефонов.",
                    icon: CreditCard,
                    color: "text-cyan-300",
                  },
                  {
                    title: "1 AI-отклик / нейрокоммент / аутрич",
                    cost: "1 кредит",
                    desc: "Индивидуальный отклик на бирже (Kwork/FL), комментарий под постом канала или отправка касания по базе.",
                    icon: Zap,
                    color: "text-amber-300",
                  },
                  {
                    title: "1 день автопрогрева аккаунта",
                    cost: "2 кредита",
                    desc: "Полный суточный цикл: чтение постов, реакции, подписка на белые каналы и взаимные кросс-диалоги фермы.",
                    icon: Users,
                    color: "text-emerald-300",
                  },
                ].map((item, idx) => {
                  const Icon = item.icon;
                  return (
                    <div
                      key={idx}
                      className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-3.5 space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Icon size={15} className={item.color} />
                          <h4 className="text-xs font-bold text-white">{item.title}</h4>
                        </div>
                        <span className="font-mono text-xs font-bold text-brand-300 bg-brand-500/10 border border-brand-500/20 px-2 py-0.5 rounded-full">
                          {item.cost}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 pl-6 leading-relaxed">
                        {item.desc}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            /* Referral Tab */
            <div className="space-y-4">
              <div className="rounded-2xl border border-brand-500/30 bg-gradient-to-br from-brand-500/15 via-fuchsia-500/5 to-transparent p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <Gift size={20} className="text-brand-300" />
                  <h3 className="text-sm font-bold text-white">Реферальная программа 15%</h3>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Приглашайте коллег и клиентов по персональной ссылке. Вы пожизненно получаете <span className="font-bold text-white">15% в кредитах</span> от каждого пополнения каждого привлеченного пользователя!
                </p>

                {/* Referral Link Box */}
                <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-[#0c0d12] p-1.5 pl-3">
                  <span className="text-xs font-mono text-slate-300 truncate flex-1">
                    {referral?.referral_link || "Загрузка ссылки..."}
                  </span>
                  <button
                    onClick={handleCopyLink}
                    className="btn-primary !px-3 !py-1 text-xs shrink-0"
                  >
                    {copied ? <Check size={13} /> : <Copy size={13} />}
                    {copied ? "Скопировано" : "Копировать"}
                  </button>
                </div>
              </div>

              {/* Referral Stats */}
              <div className="grid grid-cols-2 gap-3">
                <div className="card p-3.5 text-center">
                  <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                    Приглашено пользователей
                  </span>
                  <p className="mt-1 text-2xl font-bold font-mono text-white">
                    {referral?.invited_count ?? 0}
                  </p>
                </div>
                <div className="card p-3.5 text-center">
                  <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                    Заработано кредитов
                  </span>
                  <p className="mt-1 text-2xl font-bold font-mono text-emerald-400">
                    +{referral?.earned_credits ?? 0}
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
