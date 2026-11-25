import type {
  BillingBalance,
  BlogStatus,
  ChatMessage,
  CommentLog,
  CommentTarget,
  CreditTransaction,
  Demo,
  DemoUpdate,
  DesignStyle,
  Dialog,
  Lead,
  LeadFilters,
  LeadsPage,
  LLMConfig,
  Meta,
  Outreach,
  ParsedUser,
  ParseJob,
  ParseRequest,
  Proxy,
  ReferralInfo,
  SortKey,
  Stats,
  StoriesStatus,
  TelegramBroadcast,
  TelegramChatTarget,
  TelegramOrder,
  TelegramStatus,
  TGStatItem,
  TGStatSearchParams,
  TGStatSearchResponse,
  TGStatStatus,
  TgAccount,
} from "./types";
import { getCurrentTelegramUserId, getTelegramWebApp } from "./telegram";

export const API_URL =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "")
    : (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const userId = getCurrentTelegramUserId();
  const tg = getTelegramWebApp();
  const authHeaders: Record<string, string> = {};
  if (userId) {
    authHeaders["X-Telegram-User-Id"] = userId;
    authHeaders["X-User-Id"] = userId;
  }
  if (tg?.initData) {
    authHeaders["X-Telegram-Init-Data"] = tg.initData;
  }

  const response = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...authHeaders,
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      message = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data);
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function leadQuery(
  filters: LeadFilters,
  search: string,
  sort: SortKey,
  page?: number,
  pageSize?: number,
): string {
  const params = new URLSearchParams();
  filters.cities.forEach((value) => params.append("city", value));
  filters.categories.forEach((value) => params.append("category", value));
  filters.statuses.forEach((value) => params.append("status", value));
  filters.sources.forEach((value) => params.append("source", value));
  if (filters.onlyNoWebsite) params.set("only_no_website", "true");
  if (filters.onlyWeakOrBroken) params.set("only_weak_or_broken", "true");
  if (filters.onlySocial) params.set("only_social", "true");
  if (filters.onlyPhone) params.set("only_phone", "true");
  if (filters.minRating !== null) params.set("min_rating", String(filters.minRating));
  if (search.trim()) params.set("search", search.trim());
  if (sort !== "new") params.set("sort", sort);
  if (page) params.set("page", String(page));
  if (pageSize) params.set("page_size", String(pageSize));
  return params.toString();
}

export const api = {
  listLeads(filters: LeadFilters, search: string, sort: SortKey, page: number, pageSize = 24, signal?: AbortSignal) {
    return request<LeadsPage>(`/api/leads?${leadQuery(filters, search, sort, page, pageSize)}`, { signal });
  },

  meta() {
    return request<Meta>("/api/meta");
  },

  resolveTelegram(leadId: string) {
    return request<{ found: boolean; username?: string | null; telegram_url?: string | null; phone?: string }>(
      `/api/leads/${leadId}/resolve-telegram`,
      { method: "POST" },
    );
  },

  stats() {
    return request<Stats>("/api/stats");
  },

  updateLead(id: string, payload: Partial<Pick<Lead, "status" | "notes" | "phone" | "website_url">>) {
    return request<Lead>(`/api/leads/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  bulkStatus(ids: string[], status: Lead["status"]) {
    return request<{ updated: number }>("/api/leads/bulk-status", {
      method: "POST",
      body: JSON.stringify({ ids, status }),
    });
  },

  deleteLead(id: string) {
    return request<{ deleted: boolean }>(`/api/leads/${id}`, { method: "DELETE" });
  },

  enrichLead(id: string) {
    return request<Lead>(`/api/leads/${id}/enrich`, { method: "POST" });
  },

  generateDemo(id: string, options?: { style?: string }) {
    const q = options?.style ? `?style=${encodeURIComponent(options.style)}` : "";
    return request<Demo>(`/api/leads/${id}/demo${q}`, {
      method: "POST",
      body: options?.style ? JSON.stringify({ style: options.style }) : undefined,
    });
  },

  getStyles() {
    return request<{ styles: DesignStyle[] }>("/api/demos/styles");
  },

  getLeadDemo(id: string) {
    return request<Demo>(`/api/leads/${id}/demo`);
  },

  getDemo(id: string) {
    return request<Demo>(`/api/demos/${id}`);
  },

  updateDemo(id: string, payload: DemoUpdate) {
    return request<Demo>(`/api/demos/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  saveCustomDemo(leadId: string, payload: { html: string; message?: string; title?: string }) {
    return request<Demo>(`/api/leads/${leadId}/custom-demo`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  outreach(id: string) {
    return request<Outreach>(`/api/leads/${id}/message`, { method: "POST" });
  },

  startParse(payload: ParseRequest) {
    return request<ParseJob>("/api/parse", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getJob(id: string) {
    return request<ParseJob>(`/api/jobs/${id}`);
  },

  exportUrl(filters: LeadFilters, search: string, sort: SortKey, fmt: "csv" | "xlsx") {
    return `${API_URL}/api/export?fmt=${fmt}&${leadQuery(filters, search, sort)}`;
  },

  // Telegram Automation Endpoints
  getTelegramStatus() {
    return request<TelegramStatus>("/api/telegram/status");
  },

  listTelegramOrders(statusFilter?: string, sourceFilter?: string) {
    const params = new URLSearchParams();
    if (statusFilter) params.append("status_filter", statusFilter);
    if (sourceFilter) params.append("source_filter", sourceFilter);
    const q = params.toString() ? `?${params.toString()}` : "";
    return request<TelegramOrder[]>(`/api/telegram/orders${q}`);
  },

  syncExternalOrders() {
    return request<{ status: string; synced: number }>("/api/telegram/orders/sync-external", {
      method: "POST",
    });
  },

  simulateTelegramOrder() {
    return request<TelegramOrder>("/api/telegram/orders/simulate", { method: "POST" });
  },

  respondTelegramOrder(id: string) {
    return request<TelegramOrder>(`/api/telegram/orders/${id}/respond`, { method: "POST" });
  },

  skipTelegramOrder(id: string) {
    return request<TelegramOrder>(`/api/telegram/orders/${id}/skip`, { method: "POST" });
  },

  listTelegramBroadcasts() {
    return request<TelegramBroadcast[]>("/api/telegram/broadcasts");
  },

  // LLM AI Model Configuration
  getLLMConfig() {
    return request<LLMConfig>("/api/llm/config");
  },

  updateLLMConfig(payload: { provider: string; model: string; base_url?: string; api_key?: string }) {
    return request<LLMConfig>("/api/llm/config", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  triggerTelegramBroadcast() {
    return request<TelegramBroadcast>("/api/telegram/broadcasts/trigger", { method: "POST" });
  },

  listTelegramChats() {
    return request<TelegramChatTarget[]>("/api/telegram/chats");
  },

  addTelegramChat(payload: {
    chat_id: string;
    title: string;
    username?: string;
    kind: string;
    cooldown_minutes?: number;
    custom_text?: string;
    auto_post_enabled?: boolean;
  }) {
    return request<TelegramChatTarget>("/api/telegram/chats", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateTelegramChat(
    id: string,
    payload: {
      title?: string;
      kind?: string;
      is_active?: boolean;
      cooldown_minutes?: number;
      custom_text?: string;
      auto_post_enabled?: boolean;
    }
  ) {
    return request<TelegramChatTarget>(`/api/telegram/chats/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  postNowToTelegramChat(id: string) {
    return request<TelegramBroadcast>(`/api/telegram/chats/${id}/post-now`, {
      method: "POST",
    });
  },

  deleteTelegramChat(id: string) {
    return request<{ status: string }>(`/api/telegram/chats/${id}`, { method: "DELETE" });
  },

  // TGStat Chat Discovery
  getTGStatStatus() {
    return request<TGStatStatus>("/api/telegram/tgstat/status");
  },
  saveTGStatToken(token: string) {
    return request<{ saved: boolean; has_token: boolean }>("/api/telegram/tgstat/token", {
      method: "POST",
      body: JSON.stringify({ token }),
    });
  },
  searchTGStat(params: TGStatSearchParams) {
    return request<TGStatSearchResponse>("/api/telegram/tgstat/search", {
      method: "POST",
      body: JSON.stringify(params),
    });
  },
  addTGStatTargets(items: TGStatItem[], kind: string = "both", cooldown_minutes: number = 120) {
    return request<{ added_count: number }>("/api/telegram/tgstat/add-targets", {
      method: "POST",
      body: JSON.stringify({ items, kind, cooldown_minutes }),
    });
  },

  updateTelegramSettings(payload: {
    portfolio_url?: string;
    auto_response_enabled?: boolean;
    auto_posting_enabled?: boolean;
    working_hours_enabled?: boolean;
    working_hours_start?: string;
    working_hours_end?: string;
    telegram_auto_response_delay_min?: number;
    telegram_auto_response_delay_max?: number;
    telegram_broadcast_interval_minutes?: number;
    keywords?: string;
    stop_words?: string;
  }) {
    return request<{ status: string; message: string }>("/api/telegram/settings", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  refreshPortfolioScreenshot() {
    return request<{ status: string; message: string }>("/api/telegram/portfolio-screenshot/refresh", {
      method: "POST",
    });
  },

  async uploadPortfolioScreenshot(file: File) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_URL}/api/telegram/portfolio-screenshot/upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      throw new Error(`Ошибка загрузки: ${res.statusText}`);
    }
    return res.json();
  },

  // Growth, Neuro-commenting, Chat Scraper & Stories
  getCommentTargets() {
    return request<CommentTarget[]>("/api/growth/comment-targets");
  },
  addCommentTarget(payload: { channel_id: string; title?: string; tone?: string; custom_prompt?: string }) {
    return request<CommentTarget>("/api/growth/comment-targets", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  deleteCommentTarget(id: string) {
    return request<{ status: string }>(`/api/growth/comment-targets/${id}`, { method: "DELETE" });
  },
  generateCommentPreview(payload: { post_text: string; channel_id?: string; channel_title?: string; tone?: string; custom_prompt?: string }) {
    return request<{ success: boolean; status: string; comment_text: string }>("/api/growth/comment-targets/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getCommentLogs() {
    return request<CommentLog[]>("/api/growth/comment-logs");
  },
  parseChat(payload: { chat_identifier: string; limit?: number; only_active?: boolean; only_premium?: boolean }) {
    return request<ParsedUser[]>("/api/growth/parse-chat", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getParsedUsers(source_chat?: string) {
    const q = source_chat ? `?source_chat=${encodeURIComponent(source_chat)}` : "";
    return request<ParsedUser[]>(`/api/growth/parsed-users${q}`);
  },
  deleteParsedUser(id: string) {
    return request<{ status: string }>(`/api/growth/parsed-users/${id}`, { method: "DELETE" });
  },
  clearParsedUsers() {
    return request<{ status: string }>("/api/growth/parsed-users/clear", { method: "POST" });
  },
  getStoriesStatus() {
    return request<StoriesStatus>("/api/growth/stories/status");
  },
  toggleStoriesMasslooking(enable: boolean, delay_min?: number, delay_max?: number) {
    const min = delay_min ?? 15;
    const max = delay_max ?? 35;
    return request<{ status: string; is_running: boolean }>(
      `/api/growth/stories/toggle?enable=${enable}&delay_min=${min}&delay_max=${max}`,
      { method: "POST" }
    );
  },

  // Auto-blogger for user's own channel
  getBlogStatus() {
    return request<BlogStatus>("/api/growth/blog/status");
  },
  updateBlogSettings(payload: { enabled?: boolean; channel_id?: string; interval_hours?: number }) {
    return request<{ status: string; enabled: boolean; channel_id: string; interval_hours: number; last_post_at?: string | null; next_post_at?: string | null }>("/api/growth/blog/settings", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  generateBlogPreview(payload: { topic_hint?: string; channel_id?: string }) {
    return request<{ title: string; text: string; topic: string }>("/api/growth/blog/generate-preview", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  publishBlogNow(payload: { topic_hint?: string; channel_id?: string }) {
    return request<{ success: boolean; title: string; text: string; channel_id: string; published_at: string; next_post_at: string }>("/api/growth/blog/publish-now", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  // Accounts
  listAccounts(userId?: string) {
    const q = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
    return request<TgAccount[]>(`/api/accounts${q}`);
  },
  addAccount(payload: { phone: string; session_string?: string; proxy_id?: string; user_id?: string }) {
    return request<TgAccount>("/api/accounts", { method: "POST", body: JSON.stringify(payload) });
  },
  updateAccount(id: string, payload: Partial<Pick<TgAccount, "auto_warmup" | "warmup_preset" | "proxy_id">> & { auto_warmup_enabled?: boolean }) {
    return request<TgAccount>(`/api/accounts/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  getWarmupStatus() {
    return request<{ active_warmup_count: number; total_accounts: number; accounts: TgAccount[] }>("/api/accounts/warmup/status");
  },
  deleteAccount(id: string) { return request<{status: string}>(`/api/accounts/${id}`, { method: "DELETE" }); },
  checkAccount(id: string) { return request<TgAccount>(`/api/accounts/${id}/check`, { method: "POST" }); },

  // Proxies
  listProxies() { return request<Proxy[]>("/api/proxies"); },
  addProxy(payload: { protocol: string; host: string; port: number; username?: string; password?: string }) {
    return request<Proxy>("/api/proxies", { method: "POST", body: JSON.stringify(payload) });
  },
  deleteProxy(id: string) { return request<{status: string}>(`/api/proxies/${id}`, { method: "DELETE" }); },
  checkProxy(id: string) { return request<Proxy>(`/api/proxies/${id}/check`, { method: "POST" }); },

  // Billing
  getBalance() { return request<BillingBalance>("/api/billing/balance"); },
  getTransactions() { return request<CreditTransaction[]>("/api/billing/transactions"); },
  depositCredits(payload: { amount: number; payment_method: string }) {
    return request<BillingBalance>("/api/billing/deposit", { method: "POST", body: JSON.stringify(payload) });
  },
  getReferralInfo() { return request<ReferralInfo>("/api/billing/referral"); },

  // Dialogs (Inbox)
  listDialogs(accountId?: string) {
    const q = accountId ? `?account_id=${encodeURIComponent(accountId)}` : "";
    return request<Dialog[]>(`/api/dialogs${q}`);
  },
  getDialog(dialogId: string) { return request<Dialog>(`/api/dialogs/${dialogId}`); },
  getDialogMessages(dialogId: string) { return request<ChatMessage[]>(`/api/dialogs/${dialogId}/messages`); },
  sendMessage(dialogId: string, text: string) {
    return request<ChatMessage>(`/api/dialogs/${dialogId}/messages`, { method: "POST", body: JSON.stringify({ text }) });
  },
  updateDialogStatus(dialogId: string, status: string) {
    return request<Dialog>(`/api/dialogs/${dialogId}`, { method: "PATCH", body: JSON.stringify({ status }) });
  },
  updateDialog(dialogId: string, payload: { status?: string; ai_auto_reply_enabled?: boolean }) {
    return request<Dialog>(`/api/dialogs/${dialogId}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  syncDialog(dialogId: string) {
    return request<{ status: string; dialog_id: string; synced_count: number }>(`/api/dialogs/${dialogId}/sync`, { method: "POST" });
  },
  triggerAiReply(dialogId: string) {
    return request<{ message_id: string; text: string; status: string; is_deal: boolean }>(`/api/dialogs/${dialogId}/ai-reply`, {
      method: "POST",
    });
  },

  // Interactive Telegram Login & Archive Import
  sendAuthCode(payload: { phone: string; proxy_id?: string; device_model?: string }) {
    return request<{ status: string; phone: string; phone_code_hash: string }>("/api/accounts/auth/send-code", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  verifyAuthCode(payload: { phone: string; code: string; password?: string; proxy_id?: string }) {
    return request<{ status: string; phone: string; username?: string; message?: string }>("/api/accounts/auth/verify", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  // Soft Outreach
  startOutreach(payload: { lead_ids: string[]; template: string; delay_min?: number; delay_max?: number }) {
    return request<{ status: string; campaign_id: string; leads_count: number }>("/api/outreach/start", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getOutreachStatus() {
    return request<{ total_sent: number; total_failed: number; is_running: boolean; current_lead: string | null }>("/api/outreach/status");
  },
};
