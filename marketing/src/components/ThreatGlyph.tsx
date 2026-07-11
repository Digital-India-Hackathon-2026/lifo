import { useEffect, useRef } from "react";
import { gsap } from "@/lib/motion";

// Raw WebGL (no three.js) — five of these can live on screen at once without
// pulling the lazy-loaded R3F bundle into the main chunk just for small decorative glyphs.
const VERT = `
  attribute vec2 aPos;
  void main() { gl_Position = vec4(aPos, 0.0, 1.0); }
`;

const FRAG = `
  precision mediump float;
  uniform float uTime;
  uniform float uCorruption;
  uniform int uVariant;
  uniform vec2 uResolution;

  float hash(vec2 p){ p=fract(p*vec2(123.34,456.21)); p+=dot(p,p+45.32); return fract(p.x*p.y); }
  float noise(vec2 p){
    vec2 i=floor(p), f=fract(p);
    float a=hash(i), b=hash(i+vec2(1.0,0.0)), c=hash(i+vec2(0.0,1.0)), d=hash(i+vec2(1.0,1.0));
    vec2 u=f*f*(3.0-2.0*f);
    return mix(a,b,u.x)+(c-a)*u.y*(1.0-u.x)+(d-b)*u.x*u.y;
  }
  float fbm(vec2 p){
    float v=0.0, amp=0.5;
    for(int i=0;i<3;i++){ v+=amp*noise(p); p*=2.1; amp*=0.5; }
    return v;
  }

  float cleanPattern(vec2 uv, float t){
    if (uVariant == 0) {
      float wave = sin(uv.x*26.0+t*1.6)*0.5+0.5;
      return smoothstep(0.10,0.0,abs(uv.y-0.5-(wave-0.5)*0.34));
    }
    if (uVariant == 1) {
      return smoothstep(0.5,0.42,abs(fract(uv.y*9.0)-0.5));
    }
    if (uVariant == 2) {
      float rows = step(0.55, fract(uv.y*7.0 - t*0.1));
      float cutoff = step(uv.x, 0.78);
      return rows*cutoff;
    }
    if (uVariant == 3) {
      float d = length(uv-0.5);
      return smoothstep(0.05,0.0, abs(fract(d*5.0 - t*0.12)-0.5)-0.42);
    }
    float d = length(uv-0.5);
    float pulse = 0.16 + 0.035*sin(t*3.0);
    return smoothstep(pulse, pulse-0.035, d);
  }

  void main(){
    vec2 uv = gl_FragCoord.xy / uResolution.xy;
    float t = uTime;
    float clean = cleanPattern(uv, t);
    float n = fbm(uv*9.0 + vec2(t*0.35,-t*0.22));
    float blockSeed = hash(floor(uv*9.0)+floor(t*6.0));
    float flicker = step(0.88, blockSeed);
    float noiseVal = clamp(smoothstep(0.4,0.7,n) + flicker*0.5, 0.0, 1.0);

    vec3 ink = vec3(0.067,0.070,0.078);
    vec3 teal = vec3(0.56,0.90,0.86);
    vec3 amber = vec3(0.79,0.54,0.24);

    vec3 cleanColor = mix(ink, teal, clean*0.9);
    vec3 noiseColor = mix(ink, amber, noiseVal*0.85);
    vec3 color = mix(cleanColor, noiseColor, uCorruption);

    gl_FragColor = vec4(color, 1.0);
  }
`;

export default function ThreatGlyph({
  variant,
  active,
  size = 56,
  restValue = 0,
  activeValue = 1,
}: {
  variant: number;
  active: boolean;
  size?: number;
  /** Corruption level (0 clean → 1 full noise) when not active — lets callers invert
   *  the direction: Problem section rests clean and corrupts on hover; Features rests
   *  noisy and resolves clean on hover, mirroring the hero's own reveal direction. */
  restValue?: number;
  activeValue?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const corruption = useRef({ value: restValue });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const gl = canvas.getContext("webgl");
    if (!gl) return;

    const compile = (type: number, src: string) => {
      const s = gl.createShader(type)!;
      gl.shaderSource(s, src);
      gl.compileShader(s);
      return s;
    };
    const prog = gl.createProgram()!;
    gl.attachShader(prog, compile(gl.VERTEX_SHADER, VERT));
    gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(prog);
    gl.useProgram(prog);

    const posBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const aPos = gl.getAttribLocation(prog, "aPos");
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

    const uTime = gl.getUniformLocation(prog, "uTime");
    const uCorruption = gl.getUniformLocation(prog, "uCorruption");
    const uVariant = gl.getUniformLocation(prog, "uVariant");
    const uResolution = gl.getUniformLocation(prog, "uResolution");

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.uniform2f(uResolution, canvas.width, canvas.height);
    gl.uniform1i(uVariant, variant);

    let raf = 0;
    const start = performance.now();
    const frame = (now: number) => {
      gl.uniform1f(uTime, (now - start) / 1000);
      gl.uniform1f(uCorruption, corruption.current.value);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      gl.deleteProgram(prog);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [variant, size]);

  useEffect(() => {
    gsap.to(corruption.current, {
      value: active ? activeValue : restValue,
      duration: 0.6,
      ease: "kavachSettle",
    });
  }, [active, activeValue, restValue]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: size, height: size }}
      className="shrink-0 rounded-sm"
      aria-hidden="true"
    />
  );
}
