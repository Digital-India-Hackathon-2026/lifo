/**
 * Pure string formatting — NOT translation. Backend enum values ("ai_generated",
 * "real") stay in English content-wise; this only improves casing for display.
 * Must behave identically regardless of the active UI language.
 */
export function humanizeEnum(value: string): string {
  const spaced = value.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
}

// risk_level and severity share the same three values across every screen —
// one shared table, not translated per-namespace.
const RISK_LEVEL_LABELS: Record<string, Record<string, string>> = {
  en: { low: "Low", medium: "Medium", high: "High" },
  hi: { low: "कम", medium: "मध्यम", high: "उच्च" },
  te: { low: "తక్కువ", medium: "మధ్యస్థం", high: "అధికం" },
};

const VERDICT_LABELS: Record<string, Record<string, string>> = {
  en: { real: "Real", ai_generated: "AI Generated", genuine: "Genuine", spoof: "Spoof" },
  hi: { real: "वास्तविक", ai_generated: "एआई-जनित", genuine: "वास्तविक", spoof: "नकली" },
  te: { real: "నిజమైనది", ai_generated: "AI-సృష్టితం", genuine: "నిజమైనది", spoof: "నకిలీ" },
};

function translateEnum(table: Record<string, Record<string, string>>, value: string, lang: string): string {
  const langTable = table[lang] ?? table.en;
  return langTable[value] ?? humanizeEnum(value);
}

/**
 * Translates a bounded, fixed-cardinality backend enum (risk_level/severity)
 * into the active UI language. Scoped deliberately to this closed set of
 * values — arbitrary backend text (OCR, notes, disclaimers) stays English-only
 * and continues to use humanizeEnum() above, never this.
 */
export function translateRiskLevel(value: string, lang: string): string {
  return translateEnum(RISK_LEVEL_LABELS, value, lang);
}

/** Translates the closed verdict-type enum (real/ai_generated/genuine/spoof). See translateRiskLevel(). */
export function translateVerdict(value: string, lang: string): string {
  return translateEnum(VERDICT_LABELS, value, lang);
}

const TARGET_AUDIENCE_LABELS: Record<string, Record<string, string>> = {
  en: { general: "General", elderly: "Elderly-focused" },
  hi: { general: "सामान्य", elderly: "वरिष्ठ नागरिकों के लिए" },
  te: { general: "సాధారణ", elderly: "వృద్ధుల కోసం" },
};

/** Translates the closed target_audience enum (general/elderly) on VideoContent. See translateRiskLevel(). */
export function translateTargetAudience(value: string, lang: string): string {
  return translateEnum(TARGET_AUDIENCE_LABELS, value, lang);
}

// The exact text of document.py's _ANCHOR constant, as returned (stripped) in
// hard_factual_anchor. Every other backend note/disclaimer field stays
// English-only — this one fixed, safety-critical constant is swapped for
// display only when it matches exactly; anything else passes through untouched.
const HARD_FACTUAL_ANCHOR_EN =
  "No Indian government agency (CBI, ED, RBI, TRAI, Police) arrests citizens via video call or demands payment for 'verification' or 'bail'.";

const HARD_FACTUAL_ANCHOR_TRANSLATIONS: Record<string, string> = {
  hi: "कोई भी भारतीय सरकारी एजेंसी (सीबीआई, ईडी, आरबीआई, ट्राई, पुलिस) वीडियो कॉल के ज़रिए गिरफ़्तार नहीं करती या 'सत्यापन' या 'ज़मानत' के लिए भुगतान नहीं मांगती।",
  te: "ఏ భారత ప్రభుత్వ సంస్థ (సీబీఐ, ఈడీ, ఆర్‌బీఐ, ట్రాయ్, పోలీసు) వీడియో కాల్ ద్వారా అరెస్టు చేయదు లేదా 'వెరిఫికేషన్' లేదా 'బెయిల్' కోసం చెల్లింపు అడగదు.",
};

export function translateHardFactualAnchor(text: string, lang: string): string {
  if (text.trim() !== HARD_FACTUAL_ANCHOR_EN) return text;
  return HARD_FACTUAL_ANCHOR_TRANSLATIONS[lang] ?? text;
}
