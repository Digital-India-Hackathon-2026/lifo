import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import enCommon from "./locales/en/common.json";
import enMediaVerdict from "./locales/en/mediaVerdict.json";
import enDocumentCheck from "./locales/en/documentCheck.json";
import enCheckLink from "./locales/en/checkLink.json";
import enVaultScreen from "./locales/en/vaultScreen.json";
import enHoneypot from "./locales/en/honeypot.json";
import enReport from "./locales/en/report.json";
import enNewsAwareness from "./locales/en/newsAwareness.json";
import enFraudScanner from "./locales/en/fraudScanner.json";
import enReportScam from "./locales/en/reportScam.json";
import enFamilyProtection from "./locales/en/familyProtection.json";
import enLegalRecovery from "./locales/en/legalRecovery.json";
import enPrivacyConsent from "./locales/en/privacyConsent.json";
import enQuickSafetyCheck from "./locales/en/quickSafetyCheck.json";
import enCaseTimeline from "./locales/en/caseTimeline.json";

import hiCommon from "./locales/hi/common.json";
import hiMediaVerdict from "./locales/hi/mediaVerdict.json";
import hiDocumentCheck from "./locales/hi/documentCheck.json";
import hiCheckLink from "./locales/hi/checkLink.json";
import hiVaultScreen from "./locales/hi/vaultScreen.json";
import hiHoneypot from "./locales/hi/honeypot.json";
import hiReport from "./locales/hi/report.json";
import hiNewsAwareness from "./locales/hi/newsAwareness.json";
import hiFraudScanner from "./locales/hi/fraudScanner.json";
import hiReportScam from "./locales/hi/reportScam.json";
import hiFamilyProtection from "./locales/hi/familyProtection.json";
import hiLegalRecovery from "./locales/hi/legalRecovery.json";
import hiPrivacyConsent from "./locales/hi/privacyConsent.json";
import hiQuickSafetyCheck from "./locales/hi/quickSafetyCheck.json";
import hiCaseTimeline from "./locales/hi/caseTimeline.json";

import teCommon from "./locales/te/common.json";
import teMediaVerdict from "./locales/te/mediaVerdict.json";
import teDocumentCheck from "./locales/te/documentCheck.json";
import teCheckLink from "./locales/te/checkLink.json";
import teVaultScreen from "./locales/te/vaultScreen.json";
import teHoneypot from "./locales/te/honeypot.json";
import teReport from "./locales/te/report.json";
import teNewsAwareness from "./locales/te/newsAwareness.json";
import teFraudScanner from "./locales/te/fraudScanner.json";
import teReportScam from "./locales/te/reportScam.json";
import teFamilyProtection from "./locales/te/familyProtection.json";
import teLegalRecovery from "./locales/te/legalRecovery.json";
import tePrivacyConsent from "./locales/te/privacyConsent.json";
import teQuickSafetyCheck from "./locales/te/quickSafetyCheck.json";
import teCaseTimeline from "./locales/te/caseTimeline.json";

export const SUPPORTED_LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिंदी" },
  { code: "te", label: "తెలుగు" },
] as const;

export type LanguageCode = (typeof SUPPORTED_LANGUAGES)[number]["code"];

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: {
        common: enCommon,
        mediaVerdict: enMediaVerdict,
        documentCheck: enDocumentCheck,
        checkLink: enCheckLink,
        vaultScreen: enVaultScreen,
        honeypot: enHoneypot,
        report: enReport,
        newsAwareness: enNewsAwareness,
        fraudScanner: enFraudScanner,
        reportScam: enReportScam,
        familyProtection: enFamilyProtection,
        legalRecovery: enLegalRecovery,
        privacyConsent: enPrivacyConsent,
        quickSafetyCheck: enQuickSafetyCheck,
        caseTimeline: enCaseTimeline,
      },
      hi: {
        common: hiCommon,
        mediaVerdict: hiMediaVerdict,
        documentCheck: hiDocumentCheck,
        checkLink: hiCheckLink,
        vaultScreen: hiVaultScreen,
        honeypot: hiHoneypot,
        report: hiReport,
        newsAwareness: hiNewsAwareness,
        fraudScanner: hiFraudScanner,
        reportScam: hiReportScam,
        familyProtection: hiFamilyProtection,
        legalRecovery: hiLegalRecovery,
        privacyConsent: hiPrivacyConsent,
        quickSafetyCheck: hiQuickSafetyCheck,
        caseTimeline: hiCaseTimeline,
      },
      te: {
        common: teCommon,
        mediaVerdict: teMediaVerdict,
        documentCheck: teDocumentCheck,
        checkLink: teCheckLink,
        vaultScreen: teVaultScreen,
        honeypot: teHoneypot,
        report: teReport,
        newsAwareness: teNewsAwareness,
        fraudScanner: teFraudScanner,
        reportScam: teReportScam,
        familyProtection: teFamilyProtection,
        legalRecovery: teLegalRecovery,
        privacyConsent: tePrivacyConsent,
        quickSafetyCheck: teQuickSafetyCheck,
        caseTimeline: teCaseTimeline,
      },
    },
    fallbackLng: "en",
    defaultNS: "common",
    ns: [
      "common",
      "mediaVerdict",
      "documentCheck",
      "checkLink",
      "vaultScreen",
      "honeypot",
      "report",
      "newsAwareness",
      "fraudScanner",
      "reportScam",
      "familyProtection",
      "legalRecovery",
      "privacyConsent",
      "quickSafetyCheck",
      "caseTimeline",
    ],
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
    },
  });

export default i18n;
