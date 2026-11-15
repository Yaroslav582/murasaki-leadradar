"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Check,
  Flame,
  Key,
  Lock,
  Plus,
  RefreshCw,
  Server,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Smartphone,
  Trash2,
  Users,
  Wifi,
  X,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import { triggerHaptic, waitForTelegramUser } from "@/lib/telegram";
import type { AccountStatus, Proxy, TgAccount } from "@/lib/types";
import { Spinner } from "./ui";

const STATUS_CONFIG: Record<
  AccountStatus,
  { label: string; bg: string; text: string; border: string; dot: string }
> = {
  active: {
    label: "Активен",
    bg: "bg-[rgba(16,185,129,0.12)]",
    text: "text-[#10B981]",
    border: "border-emerald-500/20",
    dot: "bg-[#10B981] shadow-[0_0_6px_rgba(16,185,129,0.5)]",
  },
  warming: {
    label: "Прогрев",
    bg: "bg-amber-500/10",
    text: "text-[#F59E0B]",
    border: "border-amber-500/20",
    dot: "bg-[#F59E0B] shadow-[0_0_6px_rgba(245,158,11,0.5)]",
  },
  floodwait: {
    label: "FloodWait",
    bg: "bg-orange-500/10",
    text: "text-orange-400",
    border: "border-orange-500/20",
    dot: "bg-orange-400",
  },
  spamblock: {
    label: "Спам-блок",
    bg: "bg-rose-500/10",
    text: "text-[#EF4444]",
    border: "border-rose-500/20",
    dot: "bg-[#EF4444]",
  },
  banned: {
    label: "Забанен",
    bg: "bg-red-950/40",
    text: "text-red-400",
    border: "border-red-800/30",
    dot: "bg-red-500",
  },
};

function Switch({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      disabled={disabled}
      aria-checked={checked}
      onClick={() => {
        triggerHaptic("medium");
        onChange(!checked);
      }}
      className={`relative h-5 w-9 shrink-0 rounded-full border transition ${
        checked
          ? "border-brand-500/60 bg-brand-500 shadow-[0_0_8px_rgba(139,92,246,0.35)]"
          : "border-white/10 bg-[#242731]"
      } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
    >
      <span
        className={`absolute top-0.5 rounded-full bg-white shadow transition-all ${
          checked ? "left-[18px]" : "left-0.5"
        }`}
        style={{ height: 14, width: 14 }}
      />
    </button>
  );
}

export default function AccountsView({
  showToast,
}: {
  showToast: (msg: string, variant?: "info" | "success" | "error") => void;
}) {
  const [tab, setTab] = useState<"accounts" | "proxies">("accounts");
  const [accounts, setAccounts] = useState<TgAccount[]>([]);
  const [proxies, setProxies] = useState<Proxy[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkingId, setCheckingId] = useState<string | null>(null);

  // Modals
  const [addAccountOpen, setAddAccountOpen] = useState(false);
  const [addProxyOpen, setAddProxyOpen] = useState(false);

  // Auth flow state
  const [authStep, setAuthStep] = useState<"phone" | "code">("phone");
  const [authPhone, setAuthPhone] = useState("");
  const [authProxyId, setAuthProxyId] = useState("");
  const [authCode, setAuthCode] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [sessionInput, setSessionInput] = useState("");
  const [manualTab, setManualTab] = useState<"phone" | "session">("phone");

  // New Proxy state
  const [proxyProto, setProxyProto] = useState<"socks5" | "http">("socks5");
  const [proxyHost, setProxyHost] = useState("");
  const [proxyPort, setProxyPort] = useState("1080");
  const [proxyUser, setProxyUser] = useState("");
  const [proxyPass, setProxyPass] = useState("");
  const [proxySubmitting, setProxySubmitting] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const user = await waitForTelegramUser();
      const userIdStr = user ? String(user.id) : undefined;
      const [accs, prxs] = await Promise.all([api.listAccounts(userIdStr), api.listProxies()]);
      setAccounts(accs);
      setProxies(prxs);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Не удалось загрузить данные", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const handleToggleAutoWarmup = async (account: TgAccount, value: boolean) => {
    try {
      await api.updateAccount(account.id, { auto_warmup: value });
      setAccounts((prev) =>
        prev.map((a) => (a.id === account.id ? { ...a, auto_warmup: value } : a))
      );
      showToast(
        value
          ? `Автопрогрев включен для ${account.phone}`
          : `Автопрогрев приостановлен для ${account.phone}`,
        "info"
      );
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка обновления", "error");
    }
  };

  const handleChangePreset = async (account: TgAccount, preset: string) => {
    try {
      await api.updateAccount(account.id, { warmup_preset: preset });
      setAccounts((prev) =>
        prev.map((a) => (a.id === account.id ? { ...a, warmup_preset: preset } : a))
      );
      showToast(`Интенсивность изменена на: ${preset}`, "success");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка", "error");
    }
  };

  const handleCheckAccount = async (account: TgAccount) => {
    setCheckingId(account.id);
    try {
      const res = await api.checkAccount(account.id);
      setAccounts((prev) =>
        prev.map((a) =>
          a.id === account.id ? { ...a, status: res.status } : a
        )
      );
      showToast(`Статус аккаунта ${account.phone}: ${res.status}`, "success");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Проверка не удалась", "error");
    } finally {
      setCheckingId(null);
    }
  };

  const handleDeleteAccount = async (id: string) => {
    if (!confirm("Удалить этот аккаунт из системы?")) return;
    try {
      await api.deleteAccount(id);
      setAccounts((prev) => prev.filter((a) => a.id !== id));
      showToast("Аккаунт удален", "info");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка удаления", "error");
    }
  };

  // Auth flow handlers
  const handleSendCode = async () => {
    if (!authPhone.trim()) {
      showToast("Введите номер телефона", "error");
      return;
    }
    setAuthLoading(true);
    try {
      await api.sendAuthCode({
        phone: authPhone.trim(),
        proxy_id: authProxyId || undefined,
      });
      setAuthStep("code");
      showToast("Код подтверждения отправлен в Telegram", "success");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка отправки кода", "error");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleVerifyCode = async () => {
    if (!authCode.trim()) {
      showToast("Введите полученный код", "error");
      return;
    }
    setAuthLoading(true);
    try {
      const res = await api.verifyAuthCode({
        phone: authPhone.trim(),
        code: authCode.trim(),
        password: authPassword.trim() || undefined,
        proxy_id: authProxyId || undefined,
      });
      if (res.status === "needs_2fa") {
        showToast("У аккаунта включен 2FA пароль. Введите его ниже.", "info");
        return;
      }
      showToast(`Аккаунт ${res.phone} успешно подключен!`, "success");
      setAddAccountOpen(false);
      setAuthStep("phone");
      setAuthPhone("");
      setAuthCode("");
      setAuthPassword("");
      void loadData();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка подтверждения кода", "error");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSaveManualSession = async () => {
    if (!authPhone.trim()) {
      showToast("Введите номер телефона", "error");
      return;
    }
    setAuthLoading(true);
    try {
      await api.addAccount({
        phone: authPhone.trim(),
        session_string: sessionInput.trim() || undefined,
        proxy_id: authProxyId || undefined,
      });
      showToast("Аккаунт добавлен", "success");
      setAddAccountOpen(false);
      setSessionInput("");
      setAuthPhone("");
      void loadData();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка добавления", "error");
    } finally {
      setAuthLoading(false);
    }
  };

  // Proxy actions
  const handleAddProxy = async () => {
    if (!proxyHost.trim() || !proxyPort) {
      showToast("Укажите хост и порт", "error");
      return;
    }
    setProxySubmitting(true);
    try {
      await api.addProxy({
        protocol: proxyProto,
        host: proxyHost.trim(),
        port: parseInt(proxyPort, 10),
        username: proxyUser.trim() || undefined,
        password: proxyPass.trim() || undefined,
      });
      showToast("Прокси добавлен", "success");
      setAddProxyOpen(false);
      setProxyHost("");
      setProxyUser("");
      setProxyPass("");
      void loadData();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка добавления прокси", "error");
    } finally {
      setProxySubmitting(false);
    }
  };

  const handleCheckProxy = async (proxy: Proxy) => {
    try {
      const res = await api.checkProxy(proxy.id);
      setProxies((prev) =>
        prev.map((p) => (p.id === proxy.id ? { ...p, is_alive: res.is_alive, last_check: res.last_check } : p))
      );
      showToast(res.is_alive ? "Прокси активен и доступен" : "Прокси недоступен", res.is_alive ? "success" : "error");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка проверки", "error");
    }
  };

  const handleDeleteProxy = async (id: string) => {
    try {
      await api.deleteProxy(id);
      setProxies((prev) => prev.filter((p) => p.id !== id));
      showToast("Прокси удален", "info");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка удаления", "error");
    }
  };

  return (
    <div className="space-y-4">
      {/* Header & Sub-Navigation */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-[#F3F4F6]">
            Аккаунты и Прокси
          </h1>
        </div>

        {/* Buttons / Tabs switch */}
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-white/[0.06] bg-[#242731] p-1">
            <button
              onClick={() => {
                triggerHaptic("light");
                setTab("accounts");
              }}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition ${
                tab === "accounts"
                  ? "bg-brand-500 text-white shadow-[0_0_12px_rgba(139,92,246,0.3)]"
                  : "text-[#9CA3AF] hover:text-[#F3F4F6]"
              }`}
            >
              <Users size={13} />
              <span>Аккаунты</span>
              <span className="font-mono tabular-nums text-[11px] opacity-80">({accounts.length})</span>
            </button>
            <button
              onClick={() => {
                triggerHaptic("light");
                setTab("proxies");
              }}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition ${
                tab === "proxies"
                  ? "bg-brand-500 text-white shadow-[0_0_12px_rgba(139,92,246,0.3)]"
                  : "text-[#9CA3AF] hover:text-[#F3F4F6]"
              }`}
            >
              <Wifi size={13} />
              <span>Прокси</span>
              <span className="font-mono tabular-nums text-[11px] opacity-80">({proxies.length})</span>
            </button>
          </div>

          {tab === "accounts" ? (
            <button
              onClick={() => {
                triggerHaptic("medium");
                setAddAccountOpen(true);
              }}
              className="btn-primary"
            >
              <Plus size={14} />
              <span className="hidden sm:inline">Добавить аккаунт</span>
              <span className="sm:hidden">Добавить</span>
            </button>
          ) : (
            <button
              onClick={() => {
                triggerHaptic("medium");
                setAddProxyOpen(true);
              }}
              className="btn-primary"
            >
              <Plus size={14} />
              <span>Добавить прокси</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="card p-5 animate-pulse space-y-4">
              <div className="h-6 w-3/4 rounded bg-white/5" />
              <div className="h-4 w-1/2 rounded bg-white/5" />
              <div className="h-10 rounded bg-white/5" />
            </div>
          ))}
        </div>
      ) : tab === "accounts" ? (
        accounts.length === 0 ? (
          <div className="card flex flex-col items-center justify-center p-12 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-500/10 text-brand-300 border border-brand-500/20 mb-4">
              <Smartphone size={28} />
            </div>
            <h3 className="text-lg font-bold text-white">В ферме пока нет аккаунтов</h3>
            <p className="mt-1.5 max-w-sm text-xs text-slate-400">
              Подключите первый Telegram аккаунт по номеру телефона или загрузите готовую сессию, чтобы запустить автопрогрев и рассылку.
            </p>
            <button
              onClick={() => setAddAccountOpen(true)}
              className="btn-primary mt-5"
            >
              <Plus size={15} />
              Подключить Telegram аккаунт
            </button>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {accounts.map((acc) => {
              const statusCfg = STATUS_CONFIG[acc.status] || STATUS_CONFIG.active;
              const linkedProxy = proxies.find((p) => p.id === acc.proxy_id);

              return (
                <div
                  key={acc.id}
                  className="card p-3.5 space-y-3 relative overflow-hidden transition-all hover:border-white/[0.12]"
                >
                  {/* Top info: phone, username, status badge */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <Smartphone size={14} className="text-brand-400 shrink-0" />
                        <span className="font-mono tabular-nums tracking-tight text-xs font-semibold text-[#F3F4F6] truncate">
                          {acc.phone}
                        </span>
                      </div>
                      {acc.username && (
                        <p className="mt-0.5 text-[11px] text-brand-300/80 truncate">
                          @{acc.username}
                        </p>
                      )}
                    </div>

                    <div
                      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-medium ${statusCfg.bg} ${statusCfg.text} ${statusCfg.border}`}
                    >
                      <span className={`h-1.5 w-1.5 rounded-full ${statusCfg.dot}`} />
                      {statusCfg.label}
                    </div>
                  </div>

                  {/* Device model / proxy pills */}
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="rounded-md border border-white/[0.06] bg-[#242731] px-2 py-0.5 text-[10px] text-[#9CA3AF] truncate max-w-[140px]">
                      {acc.device_model || "Samsung S21"}
                    </span>
                    <span className="rounded-md border border-white/[0.06] bg-[#242731] px-2 py-0.5 text-[10px] font-mono tabular-nums tracking-tight text-[#9CA3AF]">
                      {linkedProxy
                        ? `${linkedProxy.protocol.toUpperCase()} ${linkedProxy.host}:${linkedProxy.port}`
                        : "Прямой IP"}
                    </span>
                  </div>

                  {/* Warmup Progress Bar */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-1 text-[#9CA3AF] text-[11px]">
                        <Flame size={12} className="text-[#F59E0B]" />
                        Прогрев
                      </span>
                      <span className="font-mono tabular-nums tracking-tight text-xs font-medium text-[#F3F4F6]">
                        {acc.warmup_level}%
                      </span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-[#242731] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-[#7C3AED] to-[#A78BFA] transition-all duration-500 shadow-[0_0_8px_rgba(139,92,246,0.4)]"
                        style={{ width: `${Math.max(4, acc.warmup_level)}%` }}
                      />
                    </div>
                  </div>

                  {/* Presets and Actions counter */}
                  <div className="pt-2.5 border-t border-white/[0.06] flex items-center justify-between text-xs">
                    <div>
                      <span className="text-[#6B7280] block text-[10px] font-medium">
                        Пресет
                      </span>
                      <select
                        value={acc.warmup_preset || "optimal"}
                        onChange={(e) => handleChangePreset(acc, e.target.value)}
                        className="mt-0.5 rounded-md border border-white/[0.06] bg-[#242731] px-1.5 py-0.5 text-[11px] text-[#F3F4F6] outline-none cursor-pointer hover:border-white/20"
                      >
                        <option value="light" className="bg-[#1A1C23]">Лайт (1-2/д)</option>
                        <option value="optimal" className="bg-[#1A1C23]">Оптимальный (3-4/д)</option>
                        <option value="active" className="bg-[#1A1C23]">Активный (5-6/д)</option>
                      </select>
                    </div>

                    <div className="text-right">
                      <span className="text-[#6B7280] block text-[10px] font-medium">
                        Действий
                      </span>
                      <span className="font-mono tabular-nums text-[11px] font-medium text-[#9CA3AF]">
                        {acc.daily_actions_count} / 50
                      </span>
                    </div>
                  </div>

                  {/* Footer: Switch auto-warmup + Check + Delete */}
                  <div className="pt-2.5 border-t border-white/[0.06] flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <Switch
                        checked={acc.auto_warmup}
                        onChange={(val) => handleToggleAutoWarmup(acc, val)}
                      />
                      <span className="text-[11px] font-medium text-[#9CA3AF]">
                        Автопрогрев
                      </span>
                    </div>

                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleCheckAccount(acc)}
                        disabled={checkingId === acc.id}
                        className="btn-ghost !px-2 !py-0.5 text-[11px]"
                        title="Проверить здоровье (@SpamBot)"
                      >
                        {checkingId === acc.id ? (
                          <Spinner size={11} />
                        ) : (
                          <Activity size={11} className="text-brand-300" />
                        )}
                        <span>Чек</span>
                      </button>

                      <button
                        onClick={() => handleDeleteAccount(acc.id)}
                        className="icon-btn !h-6 !w-6 text-[#6B7280] hover:text-[#EF4444]"
                        title="Удалить аккаунт"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )
      ) : (
        /* Proxies Tab */
        proxies.length === 0 ? (
          <div className="card flex flex-col items-center justify-center p-10 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-500/10 text-brand-300 border border-brand-500/20 mb-3">
              <Server size={22} />
            </div>
            <h3 className="text-sm font-semibold text-[#F3F4F6]">Нет добавленных прокси</h3>
            <p className="mt-1 max-w-sm text-xs text-[#9CA3AF]">
              Добавьте SOCKS5 или HTTP прокси для изоляции аккаунтов фермы.
            </p>
            <button onClick={() => setAddProxyOpen(true)} className="btn-primary mt-4">
              <Plus size={14} />
              Добавить прокси
            </button>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {proxies.map((p) => (
              <div key={p.id} className="card p-3.5 space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <div
                      className={`flex h-7 w-7 items-center justify-center rounded-lg border ${
                        p.is_alive
                          ? "border-emerald-500/20 bg-[rgba(16,185,129,0.12)] text-[#10B981]"
                          : "border-rose-500/20 bg-rose-500/10 text-[#EF4444]"
                      }`}
                    >
                      <Wifi size={14} />
                    </div>
                    <div>
                      <span className="text-[9px] uppercase font-semibold text-[#6B7280]">
                        {p.protocol.toUpperCase()}
                      </span>
                      <p className="font-mono tabular-nums text-xs font-semibold text-[#F3F4F6]">
                        {p.host}:{p.port}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span
                      className={`h-2 w-2 rounded-full ${
                        p.is_alive
                          ? "bg-[#10B981] shadow-[0_0_6px_rgba(16,185,129,0.7)]"
                          : "bg-[#EF4444]"
                      }`}
                    />
                    <span className="text-[11px] text-[#9CA3AF]">
                      {p.is_alive ? "В сети" : "Оффлайн"}
                    </span>
                  </div>
                </div>

                {p.username && (
                  <p className="text-[11px] text-[#9CA3AF] font-mono truncate">
                    user: {p.username}
                  </p>
                )}

                <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between text-[11px] text-[#6B7280]">
                  <span className="font-mono tabular-nums">
                    {p.last_check ? new Date(p.last_check).toLocaleTimeString() : "Не проверен"}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => handleCheckProxy(p)}
                      className="btn-ghost !px-2 !py-0.5 text-[11px]"
                    >
                      <RefreshCw size={10} />
                      Чек
                    </button>
                    <button
                      onClick={() => handleDeleteProxy(p.id)}
                      className="icon-btn !h-6 !w-6 text-[#6B7280] hover:text-[#EF4444]"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {/* Modal: Add Telegram Account */}
      {addAccountOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/80 backdrop-blur-sm"
            onClick={() => setAddAccountOpen(false)}
          />
          <div className="relative w-full max-w-md rounded-xl border border-white/[0.08] bg-[#1A1C23] p-5 shadow-2xl space-y-4 animate-fadeIn">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/15 border border-brand-500/25 text-brand-300">
                  <Smartphone size={16} />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-[#F3F4F6]">Подключить Telegram</h3>
                  <p className="text-[11px] text-[#9CA3AF]">Вход по коду или сессии</p>
                </div>
              </div>
              <button
                onClick={() => setAddAccountOpen(false)}
                className="icon-btn !h-7 !w-7"
              >
                <X size={14} />
              </button>
            </div>

            {/* Sub-tabs: Phone vs Session */}
            <div className="flex rounded-lg border border-white/[0.06] bg-[#242731] p-1">
              <button
                onClick={() => setManualTab("phone")}
                className={`flex-1 rounded-md py-1 text-xs font-medium transition ${
                  manualTab === "phone"
                    ? "bg-brand-500 text-white shadow"
                    : "text-[#9CA3AF] hover:text-[#F3F4F6]"
                }`}
              >
                По номеру телефона
              </button>
              <button
                onClick={() => setManualTab("session")}
                className={`flex-1 rounded-md py-1 text-xs font-medium transition ${
                  manualTab === "session"
                    ? "bg-brand-500 text-white shadow"
                    : "text-[#9CA3AF] hover:text-[#F3F4F6]"
                }`}
              >
                StringSession
              </button>
            </div>

            {manualTab === "phone" ? (
              authStep === "phone" ? (
                <div className="space-y-3">
                  <div>
                    <label className="label mb-1 block">Номер телефона (с кодом страны)</label>
                    <input
                      type="text"
                      placeholder="+7 999 123-45-67"
                      value={authPhone}
                      onChange={(e) => setAuthPhone(e.target.value)}
                      className="input"
                    />
                  </div>

                  <div>
                    <label className="label mb-1 block">Привязать прокси (рекомендуется)</label>
                    <select
                      value={authProxyId}
                      onChange={(e) => setAuthProxyId(e.target.value)}
                      className="input"
                    >
                      <option value="">Без прокси (прямое подключение)</option>
                      {proxies.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.protocol.toUpperCase()} {p.host}:{p.port}
                        </option>
                      ))}
                    </select>
                  </div>

                  <button
                    onClick={handleSendCode}
                    disabled={authLoading}
                    className="btn-primary w-full"
                  >
                    {authLoading ? <Spinner size={14} /> : <ArrowRight size={14} />}
                    Получить код в Telegram
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-xs text-[#9CA3AF]">
                    Код отправлен на номер <span className="font-semibold text-[#F3F4F6]">{authPhone}</span> в Telegram.
                  </p>

                  <div>
                    <label className="label mb-1 block">Код подтверждения</label>
                    <input
                      type="text"
                      placeholder="12345"
                      value={authCode}
                      onChange={(e) => setAuthCode(e.target.value)}
                      className="input text-center text-base font-mono tracking-widest"
                    />
                  </div>

                  <div>
                    <label className="label mb-1 block flex items-center gap-1">
                      <Lock size={11} /> Пароль 2FA (если установлен)
                    </label>
                    <input
                      type="password"
                      placeholder="Пароль двухфакторной защиты"
                      value={authPassword}
                      onChange={(e) => setAuthPassword(e.target.value)}
                      className="input"
                    />
                  </div>

                  <div className="flex gap-2 pt-1">
                    <button
                      onClick={() => setAuthStep("phone")}
                      className="btn-ghost flex-1"
                    >
                      Назад
                    </button>
                    <button
                      onClick={handleVerifyCode}
                      disabled={authLoading}
                      className="btn-primary flex-1"
                    >
                      {authLoading ? <Spinner size={14} /> : <Check size={14} />}
                      Подтвердить
                    </button>
                  </div>
                </div>
              )
            ) : (
              <div className="space-y-3">
                <div>
                  <label className="label mb-1 block">Номер телефона</label>
                  <input
                    type="text"
                    placeholder="+7 999 123-45-67"
                    value={authPhone}
                    onChange={(e) => setAuthPhone(e.target.value)}
                    className="input"
                  />
                </div>

                <div>
                  <label className="label mb-1 block">Telethon StringSession</label>
                  <textarea
                    rows={4}
                    placeholder="1BJWap1wB..."
                    value={sessionInput}
                    onChange={(e) => setSessionInput(e.target.value)}
                    className="input font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="label mb-1 block">Прокси</label>
                  <select
                    value={authProxyId}
                    onChange={(e) => setAuthProxyId(e.target.value)}
                    className="input"
                  >
                    <option value="">Без прокси</option>
                    {proxies.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.protocol.toUpperCase()} {p.host}:{p.port}
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  onClick={handleSaveManualSession}
                  disabled={authLoading}
                  className="btn-primary w-full"
                >
                  {authLoading ? <Spinner size={14} /> : <Check size={14} />}
                  Сохранить аккаунт
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modal: Add Proxy */}
      {addProxyOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/80 backdrop-blur-sm"
            onClick={() => setAddProxyOpen(false)}
          />
          <div className="relative w-full max-w-md rounded-xl border border-white/[0.08] bg-[#1A1C23] p-5 shadow-2xl space-y-3.5 animate-fadeIn">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-[#F3F4F6] flex items-center gap-2">
                <Wifi size={15} className="text-brand-400" />
                Новый прокси-сервер
              </h3>
              <button
                onClick={() => setAddProxyOpen(false)}
                className="icon-btn !h-7 !w-7"
              >
                <X size={14} />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label className="label mb-1 block">Протокол</label>
                <select
                  value={proxyProto}
                  onChange={(e) => setProxyProto(e.target.value as "socks5" | "http")}
                  className="input"
                >
                  <option value="socks5">SOCKS5</option>
                  <option value="http">HTTP</option>
                </select>
              </div>
              <div>
                <label className="label mb-1 block">Порт</label>
                <input
                  type="number"
                  value={proxyPort}
                  onChange={(e) => setProxyPort(e.target.value)}
                  placeholder="1080"
                  className="input font-mono"
                />
              </div>
            </div>

            <div>
              <label className="label mb-1 block">Хост / IP</label>
              <input
                type="text"
                value={proxyHost}
                onChange={(e) => setProxyHost(e.target.value)}
                placeholder="185.220.101.5"
                className="input font-mono"
              />
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label className="label mb-1 block">Логин (опционально)</label>
                <input
                  type="text"
                  value={proxyUser}
                  onChange={(e) => setProxyUser(e.target.value)}
                  placeholder="user"
                  className="input"
                />
              </div>
              <div>
                <label className="label mb-1 block">Пароль</label>
                <input
                  type="password"
                  value={proxyPass}
                  onChange={(e) => setProxyPass(e.target.value)}
                  placeholder="••••••"
                  className="input"
                />
              </div>
            </div>

            <button
              onClick={handleAddProxy}
              disabled={proxySubmitting}
              className="btn-primary w-full mt-1"
            >
              {proxySubmitting ? <Spinner size={14} /> : <Check size={14} />}
              Добавить прокси
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
