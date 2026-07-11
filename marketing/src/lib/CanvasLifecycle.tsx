import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

interface LifecycleCtx {
  activeId: string | null;
  observe: (id: string, el: Element) => void;
  unobserve: (id: string) => void;
}

const Ctx = createContext<LifecycleCtx | null>(null);

/** Below this intersection ratio a section doesn't count as "on screen" for canvas purposes. */
const MIN_VISIBLE_RATIO = 0.22;

/**
 * Enforces "exactly one live WebGL context at a time": every section wraps its
 * <Canvas> in <CanvasSlot>, and only the most-visible registered slot ever
 * renders its real children — the rest render a static placeholder. Mounting
 * false→true / true→false is what does the work: R3F disposes the renderer
 * and loses the GL context on unmount for free.
 */
export function CanvasLifecycleProvider({ children }: { children: ReactNode }) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const ratios = useRef(new Map<string, number>());
  const elements = useRef(new Map<string, Element>());
  const activeIdRef = useRef<string | null>(null);
  activeIdRef.current = activeId;
  const observerRef = useRef<IntersectionObserver | null>(null);

  const recompute = useCallback(() => {
    let bestId: string | null = null;
    let bestRatio = MIN_VISIBLE_RATIO;
    for (const [id, ratio] of ratios.current) {
      if (ratio > bestRatio) {
        bestRatio = ratio;
        bestId = id;
      }
    }
    if (bestId !== activeIdRef.current) setActiveId(bestId);
  }, []);

  // Created during render (once, guarded) rather than in an effect: child
  // slots register in their own mount effect, which fires before this
  // component's effects — the observer must already exist by then.
  if (observerRef.current === null && typeof IntersectionObserver !== "undefined") {
    observerRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const id = (entry.target as HTMLElement).dataset.canvasSlot;
          if (id) ratios.current.set(id, entry.intersectionRatio);
        }
        recompute();
      },
      { threshold: [0, 0.22, 0.35, 0.5, 0.65, 0.8, 1] }
    );
  }

  useEffect(() => () => observerRef.current?.disconnect(), []);

  const observe = useCallback((id: string, el: Element) => {
    (el as HTMLElement).dataset.canvasSlot = id;
    elements.current.set(id, el);
    observerRef.current?.observe(el);
  }, []);

  const unobserve = useCallback(
    (id: string) => {
      const el = elements.current.get(id);
      if (el) observerRef.current?.unobserve(el);
      elements.current.delete(id);
      ratios.current.delete(id);
      recompute();
    },
    [recompute]
  );

  const value = useMemo(() => ({ activeId, observe, unobserve }), [activeId, observe, unobserve]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

function useCanvasLifecycle() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useCanvasLifecycle must be used inside CanvasLifecycleProvider");
  return ctx;
}

export function CanvasSlot({
  id,
  children,
  placeholder = null,
  className,
}: {
  id: string;
  children: ReactNode;
  placeholder?: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const { activeId, observe, unobserve } = useCanvasLifecycle();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    observe(id, el);
    return () => unobserve(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const isActive = activeId === id;

  return (
    <div ref={ref} className={className}>
      {isActive ? children : placeholder}
    </div>
  );
}

export function useIsCanvasActive(id: string) {
  const { activeId } = useCanvasLifecycle();
  return activeId === id;
}
