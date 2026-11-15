// Telegram Web App SDK helpers

export interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  is_premium?: boolean;
}

export interface TelegramWebApp {
  initData: string;
  initDataUnsafe: {
    query_id?: string;
    user?: TelegramUser;
    auth_date?: string;
    hash?: string;
  };
  version: string;
  platform: string;
  colorScheme: "light" | "dark";
  themeParams: Record<string, string>;
  isExpanded: boolean;
  viewportHeight: number;
  viewportStableHeight: number;
  headerColor: string;
  backgroundColor: string;
  BackButton: {
    isVisible: boolean;
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
  };
  MainButton: {
    text: string;
    color: string;
    textColor: string;
    isVisible: boolean;
    isActive: boolean;
    show: () => void;
    hide: () => void;
    enable: () => void;
    disable: () => void;
    showProgress: (leaveActive: boolean) => void;
    hideProgress: () => void;
    onClick: (cb: () => void) => void;
  };
  HapticFeedback: {
    impactOccurred: (style: "light" | "medium" | "heavy" | "rigid" | "soft") => void;
    notificationOccurred: (type: "error" | "success" | "warning") => void;
    selectionChanged: () => void;
  };
  ready: () => void;
  expand: () => void;
  close: () => void;
  setHeaderColor: (color: string) => void;
  setBackgroundColor: (color: string) => void;
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}

export function getTelegramWebApp(): TelegramWebApp | null {
  if (typeof window !== "undefined" && window.Telegram?.WebApp) {
    return window.Telegram.WebApp;
  }
  return null;
}

export function getCurrentTelegramUserId(): string | null {
  const tg = getTelegramWebApp();
  if (tg?.initDataUnsafe?.user?.id) {
    const idStr = String(tg.initDataUnsafe.user.id);
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("murasaki_telegram_user_id", idStr);
      } catch {}
    }
    return idStr;
  }
  if (typeof window !== "undefined") {
    try {
      return localStorage.getItem("murasaki_telegram_user_id");
    } catch {}
  }
  return null;
}

export async function waitForTelegramUser(timeoutMs = 1500): Promise<TelegramUser | null> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const tg = getTelegramWebApp();
    if (tg?.initDataUnsafe?.user?.id) {
      const user = tg.initDataUnsafe.user;
      if (typeof window !== "undefined") {
        try {
          localStorage.setItem("murasaki_telegram_user_id", String(user.id));
        } catch {}
      }
      return user;
    }
    await new Promise((resolve) => setTimeout(resolve, 60));
  }

  // Fallback from localStorage
  if (typeof window !== "undefined") {
    try {
      const savedId = localStorage.getItem("murasaki_telegram_user_id");
      if (savedId) {
        return {
          id: Number(savedId) || 0,
          first_name: "Telegram User",
        };
      }
    } catch {}
  }
  return null;
}

export function isTelegramWebApp(): boolean {
  const tg = getTelegramWebApp();
  return Boolean(tg && (tg.platform === "ios" || tg.platform === "android" || tg.platform === "tdesktop" || tg.initData));
}

export function initTelegramWebApp(): void {
  const tg = getTelegramWebApp();
  if (!tg) return;

  try {
    tg.ready();
    tg.expand();
    tg.setHeaderColor("#000000");
    tg.setBackgroundColor("#07080f");
  } catch {
    // Ignore if not in iframe
  }
}

export function triggerHaptic(style: "light" | "medium" | "heavy" | "success" | "error" = "light"): void {
  const tg = getTelegramWebApp();
  if (!tg?.HapticFeedback) return;

  try {
    if (style === "success" || style === "error") {
      tg.HapticFeedback.notificationOccurred(style);
    } else {
      tg.HapticFeedback.impactOccurred(style);
    }
  } catch {
    // Ignore
  }
}
