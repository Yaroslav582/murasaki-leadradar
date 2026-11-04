import type {
  CommentLog,
  CommentTarget,
  Demo,
  DemoUpdate,
  Lead,
  LeadFilters,
  LeadsPage,
  LLMConfig,
  Meta,
  Outreach,
  ParsedUser,
  ParseJob,
  ParseRequest,
  SortKey,
  Stats,
  StoriesStatus,
  TelegramBroadcast,
  TelegramChatTarget,
  TelegramOrder,
  TelegramStatus,
} from "./types";

export const API_URL =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "")
    : (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
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

  generateDemo(id: string) {
    return request<Demo>(`/api/leads/${id}/demo`, { method: "POST" });
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
};
