import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ReportProvider } from "@/context/ReportContext";
import ReportSlideOver from "@/components/ReportSlideOver";
import AppShell from "@/components/AppShell";
import Dashboard from "@/screens/Dashboard";
import MediaVerdict from "@/screens/MediaVerdict";
import DocumentCheck from "@/screens/DocumentCheck";
import CheckLinkProfileCall from "@/screens/CheckLinkProfileCall";
import FraudScanner from "@/screens/FraudScanner";
import QuickSafetyCheck from "@/screens/QuickSafetyCheck";
import VaultScreen from "@/screens/VaultScreen";
import HoneypotScreen from "@/screens/HoneypotScreen";
import FamilyProtection from "@/screens/FamilyProtection";
import ReportScam from "@/screens/ReportScam";
import LegalRecovery from "@/screens/LegalRecovery";
import CaseTimeline from "@/screens/CaseTimeline";
import PrivacyConsent from "@/screens/PrivacyConsent";
import NewsAwareness from "@/screens/NewsAwareness";

function App() {
  return (
    <ReportProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Dashboard />} />
            <Route path="media-verdict" element={<MediaVerdict />} />
            <Route path="document-check" element={<DocumentCheck />} />
            <Route path="check" element={<CheckLinkProfileCall />} />
            <Route path="fraud-scanner" element={<FraudScanner />} />
            <Route path="quick-safety-check" element={<QuickSafetyCheck />} />
            <Route path="vault" element={<VaultScreen />} />
            <Route path="honeypot" element={<HoneypotScreen />} />
            <Route path="family-protection" element={<FamilyProtection />} />
            <Route path="report-scam" element={<ReportScam />} />
            <Route path="legal-recovery" element={<LegalRecovery />} />
            <Route path="case-timeline" element={<CaseTimeline />} />
            <Route path="privacy-consent" element={<PrivacyConsent />} />
            <Route path="news" element={<NewsAwareness />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <ReportSlideOver />
    </ReportProvider>
  );
}

export default App;
