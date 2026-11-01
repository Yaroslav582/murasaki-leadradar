"use client";

import { CheckCircle2, CircleAlert, Radar, X } from "lucide-react";
import type { ParseJob } from "@/lib/types";
import { SOURCE_LABELS } from "@/lib/utils";
import { Spinner } from "./ui";

export default function JobBanner({ job, onDismiss }: { job: ParseJob; onDismiss: () => void }) {
  const running = job.status === "queued" || job.status === "running";
  const failed = job.status === "failed";
  const city = typeof job.params?.city === "string" ? job.params.city : "";
  const source = SOURCE_LABELS[job.source] ?? job.source;

  return (
    <div
      className={`card relative mb-4 overflow-hidden px-4 py-3.5 sm:px-5 ${
        failed
          ? "border-rose-400/20 bg-rose-400/[0.05]"
          : running
            ? "border-brand-500/20 bg-brand-500/[0.06]"
            : "border-emerald-400/20 bg-emerald-400/[0.05]"
      }`}
    >
      <div className="flex items-center gap-3">
        <div
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${
            failed
              ? "border-rose-400/25 bg-rose-400/10 text-rose-300"
              : running
                ? "border-brand-500/30 bg-brand-500/15 text-brand-300"
                : "border-emerald-400/25 bg-emerald-400/10 text-emerald-300"
          }`}
        >
          {running ? <Spinner size={16} /> : failed ? <CircleAlert size={17} /> : <CheckCircle2 size={17} />}
        </div>

        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-white">
            {running ? (
              <>
                <Radar size={13} className="text-brand-300" />
                Собираем лиды
              </>
            ) : failed ? (
              "Сбор не удался"
            ) : (
              "Сбор завершён"
            )}
            <span className="rounded bg-white/[0.06] px-1.5 py-0.5 text-[10px] font-medium text-slate-400">
              {source}
              {city ? ` · ${city}` : ""}
            </span>
          </p>
          <p className={`mt-0.5 truncate text-[11px] ${failed ? "text-rose-200/80" : "text-slate-400"}`}>
            {failed
              ? job.error ?? "Неизвестная ошибка"
              : running
                ? "Задача выполняется в фоне — можно продолжать работу"
                : `Найдено ${job.total_found}, сохранено ${job.total_saved} лидов`}
          </p>
        </div>

        <button onClick={onDismiss} className="text-slate-500 transition hover:text-white" aria-label="Скрыть">
          <X size={15} />
        </button>
      </div>

      {running ? (
        <div className="absolute inset-x-0 bottom-0 h-0.5 overflow-hidden bg-white/[0.04]">
          <div className="h-full w-1/3 animate-[shimmer_1.6s_infinite] bg-gradient-to-r from-transparent via-brand-400 to-transparent" />
        </div>
      ) : null}
    </div>
  );
}
