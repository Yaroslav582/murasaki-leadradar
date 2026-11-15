"use client";

import { Coins, Database, MessageSquare, Radio, SendHorizontal, Users } from "lucide-react";
import { triggerHaptic } from "@/lib/telegram";

export type NavTab = "leads" | "telegram" | "accounts" | "inbox" | "pricing";

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
      id: "accounts" as const,
      label: "Аккаунты",
      icon: Users,
    },
    {
      id: "inbox" as const,
      label: "Диалоги",
      icon: MessageSquare,
    },
    {
      id: "pricing" as const,
      label: "Тариф",
      icon: Coins,
    },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 border-t border-white/[0.04] bg-[#111216]/80 px-3 pb-[max(env(safe-area-inset-bottom),8px)] pt-2 backdrop-blur-md md:hidden">
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
              className={`relative flex flex-col items-center justify-center gap-1 rounded-lg px-2.5 py-1 transition-all ${
                isActive ? "text-brand-300" : "text-[#9CA3AF] hover:text-[#F3F4F6]"
              }`}
            >
              <div
                className={`relative flex h-6 w-6 items-center justify-center rounded-md transition-transform ${
                  isActive ? "scale-105" : ""
                }`}
              >
                <Icon size={18} className={isActive ? "text-brand-400" : "text-[#9CA3AF]"} />
                {isActive && (
                  <span className="absolute -bottom-1 h-1 w-1 rounded-full bg-brand-400 shadow-[0_0_6px_rgba(139,92,246,0.8)]" />
                )}
              </div>
              <span className={`text-[10px] tracking-tight ${isActive ? "font-semibold text-[#F3F4F6]" : "font-normal text-[#9CA3AF]"}`}>
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
