"use client";

import { CheckCircle2, CircleAlert, Info, Instagram, Loader2, MessageCircle, Radar, Send, Star, X } from "lucide-react";
import type { Lead, LeadStatus } from "@/lib/types";
import { STATUS_META, categoryStyle, initials } from "@/lib/utils";

export function Spinner({ size = 16, className = "" }: { size?: number; className?: string }) {
  return <Loader2 size={size} className={`animate-spin ${className}`} />;
}

export function StatusBadge({ status, label }: { status: LeadStatus; label?: string }) {
  const meta = STATUS_META[status] ?? STATUS_META.new;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${meta.badge}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
      {label ?? meta.label}
    </span>
  );
}

export function CategoryBadge({ category }: { category: string }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${categoryStyle(category)}`}>
      {category}
    </span>
  );
}

export function WebsiteBadge({ hasWebsite }: { hasWebsite: boolean }) {
  if (hasWebsite) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-2.5 py-1 text-[11px] font-semibold text-emerald-300">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
        Есть сайт
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-400/25 bg-rose-400/10 px-2.5 py-1 text-[11px] font-semibold text-rose-300">
      <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
      Без сайта
    </span>
  );
}

export function Rating({ rating, reviews }: { rating: number | null; reviews: number }) {
  if (rating === null) {
    return <span className="text-xs text-slate-500">Нет рейтинга</span>;
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-slate-400">
      <Star size={13} className="fill-amber-400 text-amber-400" />
      <span className="font-semibold text-slate-200">{rating.toFixed(1)}</span>
      <span className="text-slate-500">({reviews})</span>
    </span>
  );
}

const SOCIAL_META = {
  instagram: {
    label: "Instagram",
    icon: Instagram,
    className: "text-pink-300 hover:border-pink-400/40 hover:bg-pink-400/10",
  },
  telegram: {
    label: "Telegram",
    icon: Send,
    className: "text-sky-300 hover:border-sky-400/40 hover:bg-sky-400/10",
  },
  whatsapp: {
    label: "WhatsApp",
    icon: MessageCircle,
    className: "text-emerald-300 hover:border-emerald-400/40 hover:bg-emerald-400/10",
  },
} as const;

export function SocialLinks({
  links,
  size = "sm",
  stopPropagation = true,
}: {
  links: Lead["social_links"];
  size?: "sm" | "md";
  stopPropagation?: boolean;
}) {
  const entries = (Object.keys(SOCIAL_META) as Array<keyof typeof SOCIAL_META>)
    .filter((key) => Boolean(links?.[key]))
    .map((key) => ({ key, href: links[key] as string, ...SOCIAL_META[key] }));

  if (!entries.length) return null;

  return (
    <div
      className="flex items-center gap-1.5"
      onClick={stopPropagation ? (event) => event.stopPropagation() : undefined}
    >
      {entries.map(({ key, href, label, icon: Icon, className }) => (
        <a
          key={key}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          title={label}
          aria-label={label}
          className={`inline-flex items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] transition ${className} ${
            size === "md" ? "h-9 w-9" : "h-8 w-8"
          }`}
        >
          <Icon size={size === "md" ? 16 : 14} />
        </a>
      ))}
    </div>
  );
}

export function Avatar({ name, category }: { name: string; category: string }) {
  const palette: Record<string, string> = {
    Бьюти: "from-rose-500/30 to-pink-500/10",
    Рестораны: "from-amber-500/30 to-orange-500/10",
    Автосервисы: "from-cyan-500/30 to-sky-500/10",
    Медицина: "from-emerald-500/30 to-teal-500/10",
    Фитнес: "from-lime-500/30 to-green-500/10",
    Отели: "from-sky-500/30 to-blue-500/10",
    Услуги: "from-violet-500/30 to-purple-500/10",
    Магазины: "from-fuchsia-500/30 to-pink-500/10",
  };
  return (
    <div
      className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-gradient-to-br text-sm font-bold text-white ${
        palette[category] ?? "from-brand-500/30 to-white/5"
      }`}
    >
      {initials(name)}
    </div>
  );
}

export type ToastVariant = "success" | "error" | "info";

export interface ToastItem {
  id: number;
  message: string;
  variant: ToastVariant;
}

export function ToastStack({ toasts, onDismiss }: { toasts: ToastItem[]; onDismiss: (id: number) => void }) {
  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-[120] flex w-[min(360px,calc(100vw-2.5rem))] flex-col gap-2">
      {toasts.map((toast) => {
        const Icon = toast.variant === "success" ? CheckCircle2 : toast.variant === "error" ? CircleAlert : Info;
        const color =
          toast.variant === "success"
            ? "text-emerald-300 border-emerald-400/25"
            : toast.variant === "error"
              ? "text-rose-300 border-rose-400/25"
              : "text-sky-300 border-sky-400/25";
        return (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-start gap-3 rounded-xl border bg-[#0d101b]/95 px-4 py-3 text-sm text-slate-200 shadow-card backdrop-blur animate-slideUp ${color}`}
          >
            <Icon size={18} className="mt-0.5 shrink-0" />
            <p className="flex-1 leading-relaxed">{toast.message}</p>
            <button onClick={() => onDismiss(toast.id)} className="text-slate-500 transition hover:text-white" aria-label="Закрыть">
              <X size={15} />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export function EmptyState({
  title = "Ничего не найдено",
  description = "Попробуйте изменить фильтры или запустите сбор новых лидов.",
  action,
}: {
  title?: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-3xl border border-dashed border-white/10 bg-white/[0.015] px-6 py-20 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-brand-300">
        <Radar size={28} />
      </div>
      <h3 className="mt-5 text-lg font-bold text-white">{title}</h3>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-slate-400">{description}</p>
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="card space-y-4 p-5">
      <div className="flex items-center justify-between">
        <div className="skeleton h-6 w-20 rounded-full" />
        <div className="skeleton h-6 w-16 rounded-full" />
      </div>
      <div className="skeleton h-5 w-3/4 rounded-lg" />
      <div className="skeleton h-4 w-1/2 rounded-lg" />
      <div className="skeleton h-4 w-2/3 rounded-lg" />
      <div className="flex gap-2 pt-2">
        <div className="skeleton h-9 flex-1 rounded-xl" />
        <div className="skeleton h-9 w-24 rounded-xl" />
      </div>
    </div>
  );
}
