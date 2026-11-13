"use client";

import { Coins, Database, Radio, SendHorizontal } from "lucide-react";
import { triggerHaptic } from "@/lib/telegram";

export type NavTab = "leads" | "telegram" | "autopost" | "pricing";

export default function BottomNav({
  activeTab,
  onSelectTab,
}: {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
}) {
  const tabs = [
    {
      id: "leads" as const,
      label: "Карты",
      icon: Database,
    },
    {
      id: "telegram" as const,
      label: "Радар",
      icon: Radio,
    },
    {
      id: "autopost" as const,
      label: "Автопостинг",
      icon: SendHorizontal,
    },
    {
      id: "pricing" as const,
      label: "Тариф",
      icon: Coins,
    },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 border-t border-white/[0.06] bg-[#09090d]/90 px-3 pb-[max(env(safe-area-inset-bottom),8px)] pt-2 backdrop-blur-xl md:hidden">
      <div className="mx-auto flex max-w-md items-center justify-around">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          const Icon = tab.icon;

          return (
            <button
              key={tab.id}
              onClick={() => {
                triggerHaptic("light");
                onSelectTab(tab.id);
              }}
              className={`relative flex flex-col items-center justify-center gap-1 rounded-xl px-3 py-1 transition-all ${
                isActive ? "text-brand-300" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <div
                className={`relative flex h-7 w-7 items-center justify-center rounded-lg transition-transform ${
                  isActive ? "scale-110" : ""
                }`}
              >
                <Icon size={19} className={isActive ? "text-brand-400" : ""} />
                {isActive && (
                  <span className="absolute -bottom-1 h-1 w-1 rounded-full bg-brand-400 shadow-[0_0_8px_rgba(124,92,255,0.8)]" />
                )}
              </div>
              <span className={`text-[10px] tracking-tight ${isActive ? "font-bold text-white" : "font-medium"}`}>
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
