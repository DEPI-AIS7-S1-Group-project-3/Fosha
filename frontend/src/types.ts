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
  /** null = the source lists no price (places found online); 0 = free */
  price_foreigner_egp?: number | null;
  price_egyptian_egp?: number | null;
  /** Arabic name for places found online (from Wikidata) */
  name_ar?: string | null;
  /** Arabic copies of the English free text (agents/translate.py) */
  description_ar?: string;
  hours_note_ar?: string;
  place_note_ar?: string;
  /** true when the place came from Wikivoyage rather than the curated dataset */
  from_web?: boolean;
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
  area_ar?: string | null;
  warnings_ar?: string[];
  notes_ar?: string[];
  stops: Stop[];
  warnings: string[];
  notes: string[];
}

export interface HotelRecommendation {
  area: string;
  desc: string;
  example?: string | null;
  region?: string;
  why?: string[];
}

export interface TransportRecommendation {
  mode: string;
  desc: string;
  region?: string;
  why?: string[];
}

export interface Recommendations {
  hotels: HotelRecommendation[];
  transport: TransportRecommendation[];
  /** The traveller preferences the picks were ranked on (localised labels). */
  based_on?: string[];
}

export interface Itinerary {
  days: DayPlan[];
  not_included: Array<{ name: string; reason: string }>;
  warnings: string[];
  unscheduled: Array<{ attraction_id: number; name: string; reason: string; reason_ar?: string }>;
  warnings_ar?: string[];
  /** Hotel/transport picks in both languages; the UI shows the chosen one */
  recommendations_by_lang?: { en: Recommendations; ar: Recommendations };
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
  status: 'planned' | 'needs_clarification' | 'unsupported_region' | 'out_of_scope' | 'no_results' | 'edit_not_applied';
  /** true when this plan is an edit of the previous one */
  edited?: boolean;
  language: Language;
  reply: string;
  intent?: Intent;
  itinerary?: Itinerary;
  missing?: string[];
  /** Regions that fit the trip length, for the "where to?" buttons. */
  suggested_regions?: string[];
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

export interface WindowStats {
  total_queries: number;
  cache_hit_rate: number;
  avg_response_ms: number;
  languages: { en: number; ar: number };
  planned: number;
}

/** GET /api/v1/analytics (api/analytics.py summary) */
export interface AnalyticsSummary {
  window_days: number | null;
  current: WindowStats;
  previous: WindowStats | null;
  destinations: Array<{ name: string; count: number }>;
  regions: Array<{ name: string; count: number }>;
  attractions: Array<{ id: number; name: string; name_ar?: string | null; region: string; category: string; count: number }>;
}
