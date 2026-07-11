import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

/** Whatever a detection screen can honestly forward — grows as more screens wire in. */
export interface ForwardableFields {
  matched_patterns?: string[];
  payment_indicators?: string[];
}

interface ReportContextValue {
  isOpen: boolean;
  forwardedFields: ForwardableFields;
  openReport: (fields: ForwardableFields) => void;
  closeReport: () => void;
}

const ReportContext = createContext<ReportContextValue | null>(null);

export function ReportProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [forwardedFields, setForwardedFields] = useState<ForwardableFields>({});

  const openReport = useCallback((fields: ForwardableFields) => {
    setForwardedFields(fields);
    setIsOpen(true);
  }, []);

  const closeReport = useCallback(() => setIsOpen(false), []);

  return (
    <ReportContext.Provider value={{ isOpen, forwardedFields, openReport, closeReport }}>
      {children}
    </ReportContext.Provider>
  );
}

export function useReport() {
  const ctx = useContext(ReportContext);
  if (!ctx) throw new Error("useReport must be used inside ReportProvider");
  return ctx;
}
