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
import { triggerHaptic } from "@/lib/telegram";
import type { AccountStatus, Proxy, TgAccount } from "@/lib/types";
import { Spinner } from "./ui";

const STATUS_CONFIG: Record<
  AccountStatus,
  { label: string; bg: string; text: string; border: string; dot: string }
> = {
  active: {
    label: "Активен",
    bg: "bg-emerald-500/10",
    text: "text-emerald-400",
    border: "border-emerald-500/20",
    dot: "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]",
  },
  warming: {
    label: "Прогрев",
    bg: "bg-amber-500/10",
    text: "text-amber-400",
    border: "border-amber-500/20",
    dot: "bg-amber-400 animate-pulse shadow-[0_0_8px_rgba(251,191,36,0.6)]",
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
    text: "text-rose-400",
    border: "border-rose-500/20",
    dot: "bg-rose-400",
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
      className={`relative h-6 w-11 shrink-0 rounded-full border transition ${
        checked
          ? "border-brand-500/60 bg-brand-500/80 shadow-[0_0_12px_rgba(124,92,255,0.4)]"
          : "border-white/10 bg-white/10"
      } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
    >
      <span
        className={`absolute top-0.5 rounded-full bg-white shadow transition-all ${
          checked ? "left-[22px]" : "left-0.5"
        }`}
        style={{ height: 18, width: 18 }}
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
      const [accs, prxs] = await Promise.all([api.listAccounts(), api.listProxies()]);
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
    <div className="space-y-6">
      {/* Header & Sub-Navigation */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-300">
              Инфраструктура фермы
            </span>
            <span className="rounded-full bg-brand-500/10 px-2 py-0.5 text-[10px] font-bold text-brand-300 border border-brand-500/20">
              Account Pool
            </span>
          </div>
          <h1 className="mt-1 text-2xl font-black tracking-tight text-white sm:text-[28px]">
            Аккаунты и Прокси
          </h1>
          <p className="mt-1 text-xs text-slate-400">
            Мультиаккаунтинг Telethon с автопрогревом, пулом ротации при FloodWait и защитой от спамб-блоков.
          </p>
        </div>

        {/* Buttons / Tabs switch */}
        <div className="flex items-center gap-2">
          <div className="flex rounded-xl border border-white/[0.08] bg-[#12131a] p-1">
            <button
              onClick={() => {
                triggerHaptic("light");
                setTab("accounts");
              }}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                tab === "accounts"
                  ? "bg-brand-500 text-white shadow-[0_0_16px_rgba(124,92,255,0.4)]"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <Users size={13} />
              Аккаунты ({accounts.length})
            </button>
            <button
              onClick={() => {
                triggerHaptic("light");
                setTab("proxies");
              }}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                tab === "proxies"
                  ? "bg-brand-500 text-white shadow-[0_0_16px_rgba(124,92,255,0.4)]"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <Wifi size={13} />
              Прокси ({proxies.length})
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
              <Plus size={15} />
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
              <Plus size={15} />
              Добавить прокси
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
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {accounts.map((acc) => {
              const statusCfg = STATUS_CONFIG[acc.status] || STATUS_CONFIG.active;
              const linkedProxy = proxies.find((p) => p.id === acc.proxy_id);

              return (
                <div
                  key={acc.id}
                  className="card p-5 relative overflow-hidden transition-all hover:border-white/15 hover:shadow-[0_4px_24px_rgba(0,0,0,0.5)]"
                >
                  {/* Top info: phone, username, status badge */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Smartphone size={16} className="text-brand-300 shrink-0" />
                        <span className="font-mono text-sm font-bold text-white truncate">
                          {acc.phone}
                        </span>
                      </div>
                      {acc.username && (
                        <p className="mt-0.5 text-xs text-brand-300/80 truncate">
                          @{acc.username}
                        </p>
                      )}
                    </div>

                    <div
                      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${statusCfg.bg} ${statusCfg.text} ${statusCfg.border}`}
                    >
                      <span className={`h-1.5 w-1.5 rounded-full ${statusCfg.dot}`} />
                      {statusCfg.label}
                    </div>
                  </div>

                  {/* Device model / proxy tag */}
                  <div className="mt-4 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-400">
                    <span className="rounded-md border border-white/5 bg-white/[0.03] px-2 py-0.5 truncate max-w-[160px]">
                      {acc.device_model || "Samsung S21"}
                    </span>
                    <span className="rounded-md border border-white/5 bg-white/[0.03] px-2 py-0.5">
                      {linkedProxy
                        ? `${linkedProxy.protocol.toUpperCase()} ${linkedProxy.host}:${linkedProxy.port}`
                        : "Прямой IP"}
                    </span>
                  </div>

                  {/* Warmup Progress Bar */}
                  <div className="mt-4 space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-1 text-slate-400">
                        <Flame size={13} className="text-amber-400" />
                        Уровень прогрева
                      </span>
                      <span className="font-mono font-bold text-white">
                        {acc.warmup_level}%
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-white/5 overflow-hidden p-[1px]">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-brand-500 via-fuchsia-500 to-emerald-400 transition-all duration-500 shadow-[0_0_8px_rgba(124,92,255,0.7)]"
                        style={{ width: `${Math.max(5, acc.warmup_level)}%` }}
                      />
                    </div>
                  </div>

                  {/* Presets and Actions counter */}
                  <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs">
                    <div>
                      <span className="text-slate-500 block text-[10px] uppercase font-bold tracking-wider">
                        Пресет прогрева
                      </span>
                      <select
                        value={acc.warmup_preset || "optimal"}
                        onChange={(e) => handleChangePreset(acc, e.target.value)}
                        className="mt-0.5 bg-transparent text-xs font-semibold text-slate-200 outline-none cursor-pointer hover:text-white"
                      >
                        <option value="light" className="bg-[#13131a]">Лайт (1-2/д)</option>
                        <option value="optimal" className="bg-[#13131a]">Оптимальный (3-4/д)</option>
                        <option value="active" className="bg-[#13131a]">Активный (5-6/д)</option>
                      </select>
                    </div>

                    <div className="text-right">
                      <span className="text-slate-500 block text-[10px] uppercase font-bold tracking-wider">
                        Действий сегодня
                      </span>
                      <span className="font-mono text-xs font-bold text-slate-300">
                        {acc.daily_actions_count} / 50
                      </span>
                    </div>
                  </div>

                  {/* Footer: Switch auto-warmup + Check + Delete */}
                  <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={acc.auto_warmup}
                        onChange={(val) => handleToggleAutoWarmup(acc, val)}
                      />
                      <span className="text-xs font-medium text-slate-300">
                        Автопрогрев
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => handleCheckAccount(acc)}
                        disabled={checkingId === acc.id}
                        className="btn-ghost !px-2.5 !py-1 text-xs"
                        title="Проверить здоровье (@SpamBot)"
                      >
                        {checkingId === acc.id ? (
                          <Spinner size={12} />
                        ) : (
                          <Activity size={12} className="text-brand-300" />
                        )}
                        <span className="hidden sm:inline">Чек</span>
                      </button>

                      <button
                        onClick={() => handleDeleteAccount(acc.id)}
                        className="icon-btn !h-7 !w-7 text-slate-500 hover:text-rose-400 hover:border-rose-500/30"
                        title="Удалить аккаунт"
                      >
                        <Trash2 size={13} />
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
          <div className="card flex flex-col items-center justify-center p-12 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-500/10 text-brand-300 border border-brand-500/20 mb-4">
              <Server size={28} />
            </div>
            <h3 className="text-lg font-bold text-white">Нет добавленных прокси</h3>
            <p className="mt-1.5 max-w-sm text-xs text-slate-400">
              Добавьте SOCKS5 или HTTP прокси для изоляции аккаунтов и предотвращения флуд-блокировок по IP.
            </p>
            <button onClick={() => setAddProxyOpen(true)} className="btn-primary mt-5">
              <Plus size={15} />
              Добавить первый прокси
            </button>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {proxies.map((p) => (
              <div key={p.id} className="card p-5 space-y-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <div
                      className={`flex h-8 w-8 items-center justify-center rounded-lg border ${
                        p.is_alive
                          ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-400"
                          : "border-rose-500/30 bg-rose-500/15 text-rose-400"
                      }`}
                    >
                      <Wifi size={15} />
                    </div>
                    <div>
                      <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
                        {p.protocol.toUpperCase()}
                      </span>
                      <p className="font-mono text-sm font-bold text-white">
                        {p.host}:{p.port}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span
                      className={`h-2.5 w-2.5 rounded-full ${
                        p.is_alive
                          ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]"
                          : "bg-rose-500"
                      }`}
                    />
                    <span className="text-xs text-slate-400">
                      {p.is_alive ? "В сети" : "Оффлайн"}
                    </span>
                  </div>
                </div>

                {p.username && (
                  <p className="text-xs text-slate-400 font-mono truncate">
                    Логин: {p.username}
                  </p>
                )}

                <div className="pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-slate-500">
                  <span>
                    Чек: {p.last_check ? new Date(p.last_check).toLocaleTimeString() : "Никогда"}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleCheckProxy(p)}
                      className="btn-ghost !px-2.5 !py-1 text-xs"
                    >
                      <RefreshCw size={11} />
                      Проверить
                    </button>
                    <button
                      onClick={() => handleDeleteProxy(p.id)}
                      className="icon-btn !h-7 !w-7 text-slate-500 hover:text-rose-400"
                    >
                      <Trash2 size={13} />
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
          <div className="relative w-full max-w-md rounded-2xl border border-white/10 bg-[#13131a] p-6 shadow-2xl space-y-5 animate-fadeIn">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-500/15 border border-brand-500/20 text-brand-300">
                  <Smartphone size={18} />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Подключить Telegram</h3>
                  <p className="text-xs text-slate-400">Вход по коду или сессии</p>
                </div>
              </div>
              <button
                onClick={() => setAddAccountOpen(false)}
                className="icon-btn !h-8 !w-8"
              >
                <X size={15} />
              </button>
            </div>

            {/* Sub-tabs: Phone vs Session */}
            <div className="flex rounded-xl border border-white/[0.08] bg-[#0c0d12] p-1">
              <button
                onClick={() => setManualTab("phone")}
                className={`flex-1 rounded-lg py-1.5 text-xs font-semibold transition ${
                  manualTab === "phone"
                    ? "bg-brand-500 text-white shadow"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                По номеру телефона
              </button>
              <button
                onClick={() => setManualTab("session")}
                className={`flex-1 rounded-lg py-1.5 text-xs font-semibold transition ${
                  manualTab === "session"
                    ? "bg-brand-500 text-white shadow"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                StringSession
              </button>
            </div>

            {manualTab === "phone" ? (
              authStep === "phone" ? (
                <div className="space-y-4">
                  <div>
                    <label className="label mb-1.5 block">Номер телефона (с кодом страны)</label>
                    <input
                      type="text"
                      placeholder="+7 999 123-45-67"
                      value={authPhone}
                      onChange={(e) => setAuthPhone(e.target.value)}
                      className="input"
                    />
                  </div>

                  <div>
                    <label className="label mb-1.5 block">Привязать прокси (рекомендуется)</label>
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
                    {authLoading ? <Spinner size={16} /> : <ArrowRight size={16} />}
                    Получить код в Telegram
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  <p className="text-xs text-slate-300">
                    Код отправлен на номер <span className="font-bold text-white">{authPhone}</span> в официальное приложение Telegram.
                  </p>

                  <div>
                    <label className="label mb-1.5 block">Код подтверждения</label>
                    <input
                      type="text"
                      placeholder="12345"
                      value={authCode}
                      onChange={(e) => setAuthCode(e.target.value)}
                      className="input text-center text-lg font-mono tracking-widest"
                    />
                  </div>

                  <div>
                    <label className="label mb-1.5 block flex items-center gap-1">
                      <Lock size={11} /> Облачный пароль 2FA (если установлен)
                    </label>
                    <input
                      type="password"
                      placeholder="Ваш пароль двухфакторной защиты"
                      value={authPassword}
                      onChange={(e) => setAuthPassword(e.target.value)}
                      className="input"
                    />
                  </div>

                  <div className="flex gap-2">
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
                      {authLoading ? <Spinner size={16} /> : <Check size={16} />}
                      Подтвердить
                    </button>
                  </div>
                </div>
              )
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="label mb-1.5 block">Номер телефона</label>
                  <input
                    type="text"
                    placeholder="+7 999 123-45-67"
                    value={authPhone}
                    onChange={(e) => setAuthPhone(e.target.value)}
                    className="input"
                  />
                </div>

                <div>
                  <label className="label mb-1.5 block">Telethon StringSession</label>
                  <textarea
                    rows={4}
                    placeholder="1BJWap1wB..."
                    value={sessionInput}
                    onChange={(e) => setSessionInput(e.target.value)}
                    className="input font-mono text-xs"
                  />
                </div>

                <div>
                  <label className="label mb-1.5 block">Прокси</label>
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
                  {authLoading ? <Spinner size={16} /> : <Check size={16} />}
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
          <div className="relative w-full max-w-md rounded-2xl border border-white/10 bg-[#13131a] p-6 shadow-2xl space-y-4 animate-fadeIn">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Wifi size={17} className="text-brand-300" />
                Новый прокси-сервер
              </h3>
              <button
                onClick={() => setAddProxyOpen(false)}
                className="icon-btn !h-8 !w-8"
              >
                <X size={15} />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label mb-1.5 block">Протокол</label>
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
                <label className="label mb-1.5 block">Порт</label>
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
              <label className="label mb-1.5 block">Хост / IP</label>
              <input
                type="text"
                value={proxyHost}
                onChange={(e) => setProxyHost(e.target.value)}
                placeholder="185.220.101.5"
                className="input font-mono"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label mb-1.5 block">Логин (опционально)</label>
                <input
                  type="text"
                  value={proxyUser}
                  onChange={(e) => setProxyUser(e.target.value)}
                  placeholder="user"
                  className="input"
                />
              </div>
              <div>
                <label className="label mb-1.5 block">Пароль</label>
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
              className="btn-primary w-full mt-2"
            >
              {proxySubmitting ? <Spinner size={16} /> : <Check size={16} />}
              Добавить прокси
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
