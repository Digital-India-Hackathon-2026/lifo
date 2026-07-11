import { useEffect, useRef, type ReactNode, type HTMLAttributes } from "react";
import { gsap } from "@/lib/motion";

interface MagnetProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  padding?: number;
  disabled?: boolean;
  magnetStrength?: number;
  wrapperClassName?: string;
  innerClassName?: string;
  /** Fires 0→1 as the pointer moves through the padding zone toward the center. Drives the honeypot swarm attraction. */
  onPull?: (strength: number) => void;
}

/**
 * React Bits' Magnet, re-driven through GSAP quickTo with a custom spring ease
 * instead of the original CSS-transition strings — ponytail rule: no default
 * browser ease anywhere in this project.
 */
const Magnet = ({
  children,
  padding = 100,
  disabled = false,
  magnetStrength = 2,
  wrapperClassName = "",
  innerClassName = "",
  onPull,
  ...props
}: MagnetProps) => {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);
  const xTo = useRef<gsap.QuickToFunc | null>(null);
  const yTo = useRef<gsap.QuickToFunc | null>(null);

  useEffect(() => {
    if (!innerRef.current) return;
    xTo.current = gsap.quickTo(innerRef.current, "x", { duration: 0.6, ease: "kavachSpring" });
    yTo.current = gsap.quickTo(innerRef.current, "y", { duration: 0.6, ease: "kavachSpring" });
  }, []);

  useEffect(() => {
    if (disabled) {
      xTo.current?.(0);
      yTo.current?.(0);
      onPull?.(0);
      return;
    }

    const handleMouseMove = (e: MouseEvent) => {
      if (!wrapperRef.current) return;
      const { left, top, width, height } = wrapperRef.current.getBoundingClientRect();
      const centerX = left + width / 2;
      const centerY = top + height / 2;
      const distX = e.clientX - centerX;
      const distY = e.clientY - centerY;
      const dist = Math.hypot(distX, distY);
      const reach = width / 2 + padding;

      if (dist < reach) {
        xTo.current?.(distX / magnetStrength);
        yTo.current?.(distY / magnetStrength);
        onPull?.(1 - dist / reach);
      } else {
        xTo.current?.(0);
        yTo.current?.(0);
        onPull?.(0);
      }
    };

    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, [padding, disabled, magnetStrength, onPull]);

  return (
    <div
      ref={wrapperRef}
      className={wrapperClassName}
      style={{ position: "relative", display: "inline-block" }}
      {...props}
    >
      <div ref={innerRef} className={innerClassName} style={{ willChange: "transform" }}>
        {children}
      </div>
    </div>
  );
};

export default Magnet;
