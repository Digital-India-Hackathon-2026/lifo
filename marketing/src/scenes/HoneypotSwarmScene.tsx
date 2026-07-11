import { useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";

export interface SwarmDrivers {
  /** CTA button center, in the same world units as the scene (1 unit = 1 CSS px, origin at canvas center, y-up). Updated by the parent every frame — no React re-render. */
  ctaWorldPos: { x: number; y: number };
  /** 0→1 magnet-pull strength from the CTA's Magnet wrapper. */
  pullStrength: number;
}

const TRAIL_STEPS = 2; // echo copies per particle — a cheap motion trail without per-point stretched sprites
const CELL_SIZE = 72; // spatial-hash bucket size for neighbor connections, ~= connectDist
const CONNECT_DIST = 78;
const MAX_CONNECTIONS_PER_PARTICLE = 3;

function makeSprite(): THREE.Texture {
  const size = 64;
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const ctx = c.getContext("2d")!;
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.4, "rgba(255,255,255,0.55)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(c);
  tex.needsUpdate = true;
  return tex;
}

const CALM = new THREE.Color(0.32, 0.42, 0.42); // dim teal-gray, at rest
const HOT = new THREE.Color(0.9, 0.36, 0.26); // rust, agitated/caught

const POINT_VERT = /* glsl */ `
  attribute float aSize;
  attribute vec3 color;
  varying vec3 vColor;
  uniform float uPixelRatio;
  void main() {
    vColor = color;
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mvPosition;
    gl_PointSize = aSize * uPixelRatio;
  }
`;
const POINT_FRAG = /* glsl */ `
  precision mediump float;
  uniform sampler2D map;
  varying vec3 vColor;
  void main() {
    vec4 tex = texture2D(map, gl_PointCoord);
    gl_FragColor = vec4(vColor, 1.0) * tex;
  }
`;

function SwarmField({
  count,
  drivers,
  reducedMotion,
}: {
  count: number;
  drivers: SwarmDrivers;
  reducedMotion: boolean;
}) {
  const spriteTex = useMemo(() => makeSprite(), []);
  const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
  const { size } = useThree();

  const totalPoints = count * (1 + TRAIL_STEPS);

  // Sum of three signed uniforms ≈ a triangular/bell-ish falloff: density peaks
  // at the center and fades smoothly outward with no hard edge, unlike a plain
  // uniform fill which cuts off abruptly at its bounds.
  const softRandom = () =>
    ((Math.random() - 0.5) + (Math.random() - 0.5) + (Math.random() - 0.5)) / 1.5;

  const {
    positions,
    velocities,
    homes,
    phases,
    colors,
    sizes,
  } = useMemo(() => {
    const positions = new Float32Array(totalPoints * 3);
    const velocities = new Float32Array(count * 3);
    const homes = new Float32Array(count * 3);
    const phases = new Float32Array(count);
    const colors = new Float32Array(totalPoints * 3);
    const sizes = new Float32Array(totalPoints);
    // Full-bleed: sized off the actual canvas, with a little extra so the field
    // visibly extends past the section edges rather than floating in a box.
    const spreadX = size.width * 1.15;
    const spreadY = size.height * 1.3;
    for (let i = 0; i < count; i++) {
      const x = softRandom() * spreadX;
      const y = softRandom() * spreadY;
      const z = (Math.random() - 0.5) * 60;
      // block A (live), block B (echo 1), block C (echo 2) all start co-located
      for (let b = 0; b <= TRAIL_STEPS; b++) {
        const off = (b * count + i) * 3;
        positions[off] = x;
        positions[off + 1] = y;
        positions[off + 2] = z;
        colors[off] = CALM.r;
        colors[off + 1] = CALM.g;
        colors[off + 2] = CALM.b;
        sizes[b * count + i] = b === 0 ? 7 : b === 1 ? 4.2 : 2.4;
      }
      homes.set([x, y, z], i * 3);
      phases[i] = Math.random() * Math.PI * 2;
    }
    return { positions, velocities, homes, phases, colors, sizes };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [count]);

  // Neighbor-connection line buffers, sized once for the worst case and reused via setDrawRange.
  const maxSegments = count * MAX_CONNECTIONS_PER_PARTICLE;
  const { linePositions, lineColors } = useMemo(
    () => ({
      linePositions: new Float32Array(maxSegments * 2 * 3),
      lineColors: new Float32Array(maxSegments * 2 * 3),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [count]
  );

  const geoRef = useRef<THREE.BufferGeometry>(null);
  const lineGeoRef = useRef<THREE.BufferGeometry>(null);
  const matRef = useRef<THREE.ShaderMaterial>(null);
  const tmpColor = useMemo(() => new THREE.Color(), []);
  const gridRef = useRef<Map<number, number[]>>(new Map());

  useFrame((state, rawDelta) => {
    const geo = geoRef.current;
    const lineGeo = lineGeoRef.current;
    if (!geo || !lineGeo) return;
    const dt = Math.min(rawDelta, 1 / 30);
    const posAttr = geo.attributes.position as THREE.BufferAttribute;
    const colAttr = geo.attributes.color as THREE.BufferAttribute;
    const sizeAttr = geo.attributes.aSize as THREE.BufferAttribute;

    // --- shift motion-trail echoes before this frame overwrites block A ---
    for (let i = 0; i < count; i++) {
      const a = i * 3;
      const b = (count + i) * 3;
      const c = (2 * count + i) * 3;
      colors[c] = colors[b] * 0.55;
      colors[c + 1] = colors[b + 1] * 0.55;
      colors[c + 2] = colors[b + 2] * 0.55;
      colors[b] = colors[a] * 0.78;
      colors[b + 1] = colors[a + 1] * 0.78;
      colors[b + 2] = colors[a + 2] * 0.78;
    }
    positions.copyWithin(2 * count * 3, count * 3, 2 * count * 3);
    positions.copyWithin(count * 3, 0, count * 3);

    const pointer = state.pointer;
    const cursorX = (pointer.x * state.size.width) / 2;
    const cursorY = (pointer.y * state.size.height) / 2;

    const repelRadius = 130;
    const repelStrength = reducedMotion ? 3200 : 9000;
    const attractRadius = 440;
    const attractStrength = reducedMotion ? 3200 : 12000;
    const ringRadius = 105;
    const damping = Math.pow(0.9, dt * 60);
    const homeSpring = 0.55;
    const t = state.clock.elapsedTime;

    for (let i = 0; i < count; i++) {
      const ix = i * 3;
      const px = positions[ix];
      const py = positions[ix + 1];
      const pz = positions[ix + 2];

      let fx = 0;
      let fy = 0;

      fx += Math.sin(t * 0.6 + phases[i]) * 6;
      fy += Math.cos(t * 0.5 + phases[i] * 1.3) * 6;

      const dxC = px - cursorX;
      const dyC = py - cursorY;
      const distC = Math.hypot(dxC, dyC);
      if (distC < repelRadius && distC > 0.001) {
        const f = (1 - distC / repelRadius) * repelStrength;
        fx += (dxC / distC) * f;
        fy += (dyC / distC) * f;
      }

      // CTA "closing net": a radial spring toward a ring radius (not straight to
      // the center — that reads as a clump) plus a tangential term so the ring
      // visibly spins closed rather than just drifting inward.
      if (drivers.pullStrength > 0.001) {
        const dxA = drivers.ctaWorldPos.x - px;
        const dyA = drivers.ctaWorldPos.y - py;
        const distA = Math.hypot(dxA, dyA);
        const influence = Math.max(0, 1 - distA / attractRadius) * drivers.pullStrength;
        if (distA > 0.001 && influence > 0) {
          const nx = dxA / distA;
          const ny = dyA / distA;
          const radialError = distA - ringRadius;
          fx += nx * radialError * attractStrength * 0.018 * influence;
          fy += ny * radialError * attractStrength * 0.018 * influence;
          const tx = -ny;
          const ty = nx;
          fx += tx * attractStrength * 0.85 * influence;
          fy += ty * attractStrength * 0.85 * influence;
        }
      }

      fx += (homes[ix] - px) * homeSpring;
      fy += (homes[ix + 1] - py) * homeSpring;

      velocities[ix] = (velocities[ix] + fx * dt) * damping;
      velocities[ix + 1] = (velocities[ix + 1] + fy * dt) * damping;
      velocities[ix + 2] *= damping;

      positions[ix] = px + velocities[ix] * dt;
      positions[ix + 1] = py + velocities[ix + 1] * dt;
      positions[ix + 2] = pz + Math.sin(t * 0.4 + phases[i]) * 0.15;

      const speed = Math.hypot(velocities[ix], velocities[ix + 1]);
      const heat = Math.min(1, speed / 240);
      tmpColor.copy(CALM).lerp(HOT, heat);
      colors[ix] = tmpColor.r;
      colors[ix + 1] = tmpColor.g;
      colors[ix + 2] = tmpColor.b;
      // fast/energized particles render bigger — reads as glow/streak with additive blending
      sizes[i] = 6.5 + Math.min(1, speed / 200) * 7.0;
    }

    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
    sizeAttr.needsUpdate = true;

    // --- spatial-hash neighbor connections among live (block A) particles only ---
    const grid = gridRef.current;
    grid.clear();
    for (let i = 0; i < count; i++) {
      const cx = Math.floor(positions[i * 3] / CELL_SIZE);
      const cy = Math.floor(positions[i * 3 + 1] / CELL_SIZE);
      const key = cx * 100000 + cy;
      let arr = grid.get(key);
      if (!arr) {
        arr = [];
        grid.set(key, arr);
      }
      arr.push(i);
    }

    let segCount = 0;
    const connectDistSq = CONNECT_DIST * CONNECT_DIST;
    for (let i = 0; i < count && segCount < maxSegments; i++) {
      const px = positions[i * 3];
      const py = positions[i * 3 + 1];
      const cx = Math.floor(px / CELL_SIZE);
      const cy = Math.floor(py / CELL_SIZE);
      let connections = 0;
      neighborScan: for (let ox = -1; ox <= 1; ox++) {
        for (let oy = -1; oy <= 1; oy++) {
          const arr = grid.get((cx + ox) * 100000 + (cy + oy));
          if (!arr) continue;
          for (const j of arr) {
            if (j <= i) continue;
            if (connections >= MAX_CONNECTIONS_PER_PARTICLE || segCount >= maxSegments) break neighborScan;
            const dx = positions[j * 3] - px;
            const dy = positions[j * 3 + 1] - py;
            const dsq = dx * dx + dy * dy;
            if (dsq < connectDistSq) {
              const vi = segCount * 6;
              linePositions[vi] = px;
              linePositions[vi + 1] = py;
              linePositions[vi + 2] = positions[i * 3 + 2];
              linePositions[vi + 3] = positions[j * 3];
              linePositions[vi + 4] = positions[j * 3 + 1];
              linePositions[vi + 5] = positions[j * 3 + 2];
              const alpha = 1.0 - Math.sqrt(dsq) / CONNECT_DIST;
              const ci = i * 3;
              const cj = j * 3;
              lineColors[vi] = colors[ci] * alpha;
              lineColors[vi + 1] = colors[ci + 1] * alpha;
              lineColors[vi + 2] = colors[ci + 2] * alpha;
              lineColors[vi + 3] = colors[cj] * alpha;
              lineColors[vi + 4] = colors[cj + 1] * alpha;
              lineColors[vi + 5] = colors[cj + 2] * alpha;
              segCount++;
              connections++;
            }
          }
        }
      }
    }
    lineGeo.setDrawRange(0, segCount * 2);
    (lineGeo.attributes.position as THREE.BufferAttribute).needsUpdate = true;
    (lineGeo.attributes.color as THREE.BufferAttribute).needsUpdate = true;
  });

  return (
    <>
      <points>
        <bufferGeometry ref={geoRef}>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
          <bufferAttribute attach="attributes-color" args={[colors, 3]} />
          <bufferAttribute attach="attributes-aSize" args={[sizes, 1]} />
        </bufferGeometry>
        <shaderMaterial
          ref={matRef}
          vertexShader={POINT_VERT}
          fragmentShader={POINT_FRAG}
          uniforms={{ map: { value: spriteTex }, uPixelRatio: { value: pixelRatio } }}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
      <lineSegments>
        <bufferGeometry ref={lineGeoRef}>
          <bufferAttribute attach="attributes-position" args={[linePositions, 3]} />
          <bufferAttribute attach="attributes-color" args={[lineColors, 3]} />
        </bufferGeometry>
        <lineBasicMaterial
          vertexColors
          transparent
          opacity={0.55}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </lineSegments>
    </>
  );
}

export default function HoneypotSwarmScene({
  particleCount = 5000,
  drivers,
  reducedMotion,
}: {
  particleCount?: number;
  drivers: SwarmDrivers;
  reducedMotion: boolean;
}) {
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
      camera={{ position: [0, 0, 100], near: 0.1, far: 1000, zoom: 1 }}
    >
      <SwarmField count={particleCount} drivers={drivers} reducedMotion={reducedMotion} />
    </Canvas>
  );
}
