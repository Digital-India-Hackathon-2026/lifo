import { useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import * as THREE from "three";

const VERT = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position.xy, 0.0, 1.0);
  }
`;

// Higher-fidelity static field: 6-octave fbm for the base noise, a second
// independent per-pixel grain layer for fine TV-static texture, radial lens
// chromatic aberration (grows toward edges) layered on top of the reveal-driven
// aberration, dual-frequency scanlines, and an occasional horizontal sync-glitch
// row displacement. Tuned deliberately so only the clarity ring/core cross the
// Bloom luminance threshold — the noise field must never bloom.
const FRAG = /* glsl */ `
  precision highp float;
  varying vec2 vUv;
  uniform vec2 u_resolution;
  uniform vec2 u_mouse;
  uniform float u_time;
  uniform float u_reduced;

  float hash(vec2 p){
    p = fract(p*vec2(123.34,456.21));
    p += dot(p, p+45.32);
    return fract(p.x*p.y);
  }
  float hash1(float n){ return fract(sin(n)*43758.5453123); }

  float noise(vec2 p){
    vec2 i = floor(p);
    vec2 f = fract(p);
    float a = hash(i);
    float b = hash(i+vec2(1.0,0.0));
    float c = hash(i+vec2(0.0,1.0));
    float d = hash(i+vec2(1.0,1.0));
    vec2 u = f*f*(3.0-2.0*f);
    return mix(a,b,u.x) + (c-a)*u.y*(1.0-u.x) + (d-b)*u.x*u.y;
  }

  float fbm(vec2 p){
    float v = 0.0;
    float amp = 0.5;
    for (int i = 0; i < 6; i++){
      v += amp*noise(p);
      p *= 2.05;
      amp *= 0.5;
    }
    return v;
  }

  void main(){
    vec2 uv = vUv;
    float aspect = u_resolution.x/u_resolution.y;
    vec2 uvA = vec2(uv.x*aspect, uv.y);
    vec2 mA = vec2(u_mouse.x*aspect, u_mouse.y);
    vec2 toPixel = uvA - mA;
    float dist = length(toPixel);
    float angle = atan(toPixel.y, toPixel.x);

    float radius = 0.17;
    float edge = 0.09;

    float speed = mix(1.0, 0.15, u_reduced);
    float t = u_time * speed;

    // organic reveal boundary: three angular wobble frequencies instead of a
    // perfect circle — reads as a living signal envelope, not a clip-art clip mask
    float wobble = sin(angle*3.0 + t*0.6)*0.014
                 + sin(angle*5.0 - t*0.9)*0.008
                 + sin(angle*8.0 + t*1.3)*0.005;
    float organicRadius = radius + wobble;
    float clarity = 1.0 - smoothstep(organicRadius-edge, organicRadius+edge, dist);

    // horizontal sync-glitch: occasional rows shift uv.x
    float row = floor(uv.y * 220.0);
    float rowJitterSeed = hash(vec2(row, floor(t*5.0)));
    float rowJitter = step(0.985, rowJitterSeed) * (rowJitterSeed - 0.985) * 40.0 * mix(1.0, 0.2, u_reduced);
    vec2 uvJ = uvA + vec2(rowJitter, 0.0);

    // coarse glitch blocks
    float blockCols = 64.0;
    vec2 blockUv = floor(uv*vec2(blockCols, blockCols/aspect));
    float blockSeed = hash(blockUv + floor(t*6.0));
    float blockFlicker = step(0.945, blockSeed) * mix(1.0, 0.3, u_reduced);

    // base fbm field (drifting)
    float n = fbm(uvJ*7.0 + vec2(t*0.22, -t*0.13));

    // fine independent per-pixel grain (real TV static), re-seeded ~12x/sec
    float grainRate = mix(12.0, 3.0, u_reduced);
    float grain = hash(uv*u_resolution.xy*0.75 + floor(t*grainRate));

    // chromatic aberration: constant radial lens term + reveal-driven dynamic term
    vec2 center = uvA - vec2(aspect, 1.0)*0.5;
    float radial = length(center);
    float abAmt = radial*0.010 + (1.0-clarity)*0.012;
    float nr = fbm((uvJ+vec2(abAmt,0.0))*7.0 + vec2(t*0.22,-t*0.13));
    float nb = fbm((uvJ-vec2(abAmt,0.0))*7.0 + vec2(t*0.22,-t*0.13));

    // dual-frequency scanlines
    float scanFine = 0.95 + 0.05*sin(uv.y*u_resolution.y*1.0 - t*46.0);
    float scanWide = 0.97 + 0.03*sin(uv.y*u_resolution.y*0.12 + t*4.0);

    vec3 ink   = vec3(0.055, 0.058, 0.063);
    vec3 amber = vec3(0.79, 0.54, 0.24);
    vec3 teal  = vec3(0.56, 0.90, 0.86);
    vec3 white = vec3(0.96, 0.98, 0.97);

    // block-flicker/grain drive every channel equally (a glitch flash is achromatic);
    // only the smooth fbm cloud differs per channel — that's the actual CA fringing.
    float baseFlicker = blockFlicker*0.55 + grain*0.05;
    float glitchMixG = clamp(smoothstep(0.46,0.86,n ) + baseFlicker, 0.0, 1.0);
    float glitchMixR = clamp(smoothstep(0.46,0.86,nr) + baseFlicker, 0.0, 1.0);
    float glitchMixB = clamp(smoothstep(0.46,0.86,nb) + baseFlicker, 0.0, 1.0);
    vec3 noiseColor;
    noiseColor.r = mix(ink.r, amber.r, glitchMixR*0.82);
    noiseColor.g = mix(ink.g, amber.g, glitchMixG*0.82);
    noiseColor.b = mix(ink.b, amber.b, glitchMixB*0.82);
    noiseColor += grain*0.035;
    noiseColor *= scanFine*scanWide;

    vec2 gridUv = fract(uvA*44.0);
    float gridLine = 1.0 - smoothstep(0.0,0.035,min(gridUv.x,gridUv.y));
    float glow = 1.0 - smoothstep(0.0, radius*1.5, dist);
    // kept below 1.0 with headroom to spare — the naive glow*0.92 + hot core additions
    // used to sum past 1.0 in G/B *before* Bloom even touched it, guaranteeing a hard
    // clip to neutral white at the center regardless of how teal the source color was.
    vec3 clarityColor = mix(ink, teal, glow*0.75);
    clarityColor += gridLine*teal*0.14*glow;

    // --- depth layer 1: finer inner lattice, drifting at a different rate than
    // the outer grid — two textures moving at different speeds read as two
    // depths, a cheap parallax cue without an actual second render pass.
    vec2 innerGridUv = fract((uvA + vec2(t*0.045, -t*0.03)) * 96.0);
    float innerGridLine = 1.0 - smoothstep(0.0, 0.022, min(innerGridUv.x, innerGridUv.y));
    clarityColor += innerGridLine * teal * 0.10 * glow;

    // --- depth layer 2: a slow rotating sonar sweep, independent of the mouse —
    // "actively scanning" ambient detail, not just a static fill
    float sweepAngle = mod(t*0.45, 6.2831853);
    float angleDelta = abs(mod(angle - sweepAngle + 3.14159265, 6.2831853) - 3.14159265);
    float sweepLine = 1.0 - smoothstep(0.0, 0.22, angleDelta);
    float sweepMask = 1.0 - smoothstep(0.0, organicRadius, dist);
    clarityColor += sweepLine * sweepMask * teal * 0.35;

    // --- depth layer 3: sparse data blips inside the zone only — small bright
    // points that flicker on independent phases, texture at a third scale
    vec2 blipUv = floor((uvA + vec2(t*0.06, 0.0)) * 16.0);
    float blipSeed = hash(blipUv + 11.0);
    float blipPhase = sin(blipSeed*62.0 + t*2.2)*0.5 + 0.5;
    float blip = step(0.982, blipSeed) * smoothstep(0.85, 1.0, blipPhase);
    float insideMask = 1.0 - smoothstep(0.0, organicRadius*0.88, dist);
    clarityColor += blip * insideMask * white * 0.4;

    vec3 color = mix(noiseColor, clarityColor, clarity);

    // ring and core stay teal-family, not neutral white — a pure-white ring's
    // bloom halo bleeds inward and reads as a white blob rather than "teal reveal"
    vec3 ringColor = mix(teal, white, 0.2);
    float ring = 1.0 - smoothstep(0.0, 0.014, abs(dist-organicRadius));
    color += ring*ringColor*0.4;

    vec3 hotCore = mix(teal, white, 0.1);
    float core = 1.0 - smoothstep(0.0, radius*0.4, dist);
    color += core*hotCore*0.22*clarity;

    gl_FragColor = vec4(color, 1.0);
  }
`;

function ScannerPlane({ reducedMotion }: { reducedMotion: boolean }) {
  const mat = useRef<THREE.ShaderMaterial>(null);
  const { size } = useThree();

  const uniforms = useMemo(
    () => ({
      u_resolution: { value: new THREE.Vector2(size.width, size.height) },
      u_mouse: { value: new THREE.Vector2(0.72, 0.55) },
      u_time: { value: 0 },
      u_reduced: { value: reducedMotion ? 1 : 0 },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  useFrame((state) => {
    if (!mat.current) return;
    uniforms.u_resolution.value.set(state.size.width, state.size.height);
    uniforms.u_time.value = state.clock.elapsedTime;
    const targetX = (state.pointer.x + 1) / 2;
    const targetY = (state.pointer.y + 1) / 2;
    // ease the mouse target rather than snapping — smoother reveal motion
    uniforms.u_mouse.value.x += (targetX - uniforms.u_mouse.value.x) * 0.14;
    uniforms.u_mouse.value.y += (targetY - uniforms.u_mouse.value.y) * 0.14;
  });

  return (
    <mesh>
      <planeGeometry args={[2, 2]} />
      <shaderMaterial
        ref={mat}
        vertexShader={VERT}
        fragmentShader={FRAG}
        uniforms={uniforms}
      />
    </mesh>
  );
}

export default function SignalScannerScene({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <Canvas
      dpr={[1, 2]}
      gl={{
        antialias: false,
        powerPreference: "high-performance",
        toneMapping: THREE.NoToneMapping,
        outputColorSpace: THREE.LinearSRGBColorSpace,
      }}
      orthographic
      camera={{ position: [0, 0, 1] }}
    >
      <ScannerPlane reducedMotion={reducedMotion} />
      <EffectComposer multisampling={0}>
        <Bloom
          intensity={0.45}
          luminanceThreshold={0.78}
          luminanceSmoothing={0.2}
          mipmapBlur
        />
      </EffectComposer>
    </Canvas>
  );
}
