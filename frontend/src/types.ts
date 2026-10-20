export type Language = 'en' | 'ar';

export interface Stop {
  attraction_id: number;
  name: string;
  start: string;
  end: string;
  duration_min: number;
  travel_from_previous_min?: number | null;
  wait_min?: number | null;
  hours_confidence: 'listed' | 'check';
  ticket_price_egp?: number;
  price_note?: string;
  category?: string;
  region?: string;
  city?: string;
  description?: string;
  price_foreigner_egp?: number;
  price_egyptian_egp?: number;
  source_url?: string;
  last_verified?: string;
  lat?: number | null;
  lon?: number | null;
  hours_note?: string;
  place_note?: string;
}

export interface DayPlan {
  day: number;
  weekday?: string | null;
  area: string;
  stops: Stop[];
  warnings: string[];
  notes: string[];
}

export interface HotelRecommendation {
  area: string;
  desc: string;
}

export interface TransportRecommendation {
  mode: string;
  desc: string;
}

export interface Recommendations {
  hotels: HotelRecommendation[];
  transport: TransportRecommendation[];
}

export interface Itinerary {
  days: DayPlan[];
  not_included: Array<{ name: string; reason: string }>;
  warnings: string[];
  unscheduled: Array<{ attraction_id: number; name: string; reason: string }>;
  recommendations?: Recommendations;
  prices_note?: string;
}

export interface Intent {
  task: string;
  language: string;
  search_query: string;
  interests: string[];
  region?: string | null;
  unsupported_region?: string | null;
  days?: number | null;
  budget?: string | null;
  travelers?: string | number | null;
  travel_date?: string | null;
  visitor_type?: string | null;
  missing?: string[];
}

export interface ChatResponse {
  ok: boolean;
  status: 'planned' | 'needs_clarification' | 'unsupported_region' | 'out_of_scope' | 'no_results';
  language: Language;
  reply: string;
  intent?: Intent;
  itinerary?: Itinerary;
  missing?: string[];
  used_fallback?: boolean;
  cached?: boolean;
  response_ms?: number;
  demo?: boolean;
  error?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'ai' | 'error';
  text: string;
  result?: ChatResponse;
}

export interface AnalyticsSummary {
  period_days: number | null;
  total_queries: number;
  cache_hit_rate: number;
  avg_response_ms: number;
  arabic_ratio: number;
  planned_count: number;
  top_destinations: Array<{ name: string; count: number }>;
  top_regions: Array<{ name: string; count: number }>;
  top_attractions: Array<{ id: number; name: string; region: string; category: string; count: number }>;
  language_dist: { en: number; ar: number };
  daily_volume: Array<{ date: string; count: number }>;
}
