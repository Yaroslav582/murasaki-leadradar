export type LeadStatus = "new" | "database" | "sent" | "rejected" | "deal";

export interface Lead {
  id: string;
  name: string;
  category: string;
  city: string;
  address: string;
  phone: string | null;
  website_url: string | null;
  has_website: boolean;
  rating: number | null;
  reviews_count: number;
  latitude: number | null;
  longitude: number | null;
  social_links: {
    instagram?: string;
    telegram?: string;
    whatsapp?: string;
  };
  emails: string[];
  opening_hours: string[];
  price_level: number | null;
  source: string;
  source_id: string | null;
  status: LeadStatus;
  status_label: string;
  notes: string | null;
  demo_id: string | null;
  enriched_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface LeadsPage {
  items: Lead[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Facet {
  value: string;
  count: number;
}

export interface Meta {
  cities: Facet[];
  categories: Facet[];
  statuses: Facet[];
  sources: Facet[];
  total: number;
  no_website: number;
  with_social: number;
  with_phone: number;
}

export interface Demo {
  id: string;
  lead_id: string;
  title: string;
  html: string;
  message: string;
  published: boolean;
  public_url: string;
  created_at: string;
  updated_at: string;
}

export interface ParseJob {
  id: string;
  source: string;
  status: "queued" | "running" | "done" | "failed";
  params: Record<string, unknown>;
  total_found: number;
  total_saved: number;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface Stats {
  total: number;
  no_website: number;
  with_social: number;
  with_phone: number;
  demos: number;
  by_status: Record<LeadStatus, number>;
  latest_job: ParseJob | null;
}

export type SortKey = "new" | "rating" | "reviews" | "name";

export interface LeadFilters {
  cities: string[];
  categories: string[];
  statuses: string[];
  sources: string[];
  onlyNoWebsite: boolean;
  onlySocial: boolean;
  onlyPhone: boolean;
  minRating: number | null;
}

export interface ParseRequest {
  source: "demo" | "google" | "twogis" | "yandex" | "yandex_web" | "osm" | "scraper" | "vk" | "zoon";
  city: string;
  categories: string[];
  query?: string | null;
  limit: number;
  only_no_website: boolean;
  enrich: boolean;
}

export interface Outreach {
  message: string;
  demo_url: string | null;
}

export interface LLMPreset {
  id: string;
  name: string;
  provider: string;
  base_url: string;
  description: string;
  badge?: string;
}

export interface LLMConfig {
  provider: string;
  model: string;
  base_url: string;
  has_api_key: boolean;
  presets: LLMPreset[];
}

export interface TelegramStatus {
  is_connected: boolean;
  has_credentials: boolean;
  portfolio_url: string;
  auto_response_enabled: boolean;
  auto_posting_enabled: boolean;
  working_hours_enabled: boolean;
  working_hours_start: string;
  working_hours_end: string;
  is_in_working_hours: boolean;
  working_hours_status_text: string;
  auto_response_delay_min: number;
  auto_response_delay_max: number;
  broadcast_interval_minutes: number;
  keywords: string[];
  stop_words: string[];
  orders_count: number;
  broadcasts_count: number;
  chats_count: number;
}

export interface TelegramOrder {
  id: string;
  chat_id: string;
  chat_title: string;
  source?: "telegram" | "kwork" | "fl" | string;
  source_url?: string | null;
  message_id: number;
  author_username: string | null;
  author_name: string | null;
  raw_text: string;
  summary: string;
  category: string;
  budget: string | null;
  response_text: string | null;
  scheduled_for: string | null;
  responded_at: string | null;
  status: "pending" | "sent" | "skipped" | "failed";
  error: string | null;
  created_at: string;
}

export interface TelegramBroadcast {
  id: string;
  chat_id: string;
  chat_title: string;
  message_text: string;
  portfolio_url: string | null;
  status: "sent" | "failed";
  created_at: string;
}

export interface TelegramChatTarget {
  id: string;
  chat_id: string;
  title: string;
  username: string | null;
  kind: "orders" | "promo" | "both";
  is_active: boolean;
  cooldown_minutes: number;
  custom_text: string | null;
  auto_post_enabled: boolean;
  last_post_at: string | null;
  next_post_at: string | null;
  created_at: string;
}


export interface DemoUpdate {
  html?: string;
  message?: string;
  published?: boolean;
}
