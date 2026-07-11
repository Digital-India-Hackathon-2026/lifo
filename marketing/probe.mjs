import { chromium } from "playwright";

const browser = await chromium.launch({
  args: ["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
await page.goto("http://localhost:5183", { waitUntil: "networkidle" });
await page.waitForTimeout(1500); // let entrance animation settle

async function collectFrames(durationMs, driveMouse) {
  await page.evaluate((duration) => {
    window.__frames = [];
    window.__collecting = true;
    let last = performance.now();
    function loop(now) {
      window.__frames.push(now - last);
      last = now;
      if (window.__collecting) requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);
    setTimeout(() => {
      window.__collecting = false;
    }, duration);
  }, durationMs);

  const start = Date.now();
  while (Date.now() - start < durationMs) {
    await driveMouse();
    await page.waitForTimeout(16);
  }
  await page.waitForTimeout(250);
  return page.evaluate(() => window.__frames);
}

function summarize(frames) {
  const deltas = frames.slice(2).filter((x) => x > 0 && x < 500);
  const fps = deltas.map((ms) => 1000 / ms);
  const avg = fps.reduce((a, b) => a + b, 0) / fps.length;
  const sorted = [...fps].sort((a, b) => a - b);
  const p1low = sorted[Math.max(0, Math.floor(sorted.length * 0.01))];
  const p50 = sorted[Math.floor(sorted.length * 0.5)];
  return {
    samples: fps.length,
    avgFps: +avg.toFixed(1),
    minFps: +sorted[0].toFixed(1),
    p1LowFps: +p1low.toFixed(1),
    medianFps: +p50.toFixed(1),
    maxFrameMs: +Math.max(...deltas).toFixed(2),
  };
}

// ---- Phase 1: hero shader interaction ----
let t = 0;
const heroFrames = await collectFrames(4000, async () => {
  t += 0.12;
  const x = 800 + Math.sin(t) * 400;
  const y = 450 + Math.cos(t * 1.3) * 250;
  await page.mouse.move(x, y);
});
const heroStats = summarize(heroFrames);

// ---- Canvas-exclusivity check across a full scroll pass ----
const scrollHeight = await page.evaluate(() => document.body.scrollHeight - window.innerHeight);
const steps = 14;
let maxCanvasCount = 0;
const perStep = [];
for (let i = 0; i <= steps; i++) {
  const y = Math.round((scrollHeight * i) / steps);
  await page.evaluate((yy) => window.scrollTo(0, yy), y);
  await page.waitForTimeout(220); // let IntersectionObserver callback + mount/unmount settle
  const count = await page.evaluate(() => document.querySelectorAll("canvas").length);
  perStep.push({ scrollY: y, canvasCount: count });
  maxCanvasCount = Math.max(maxCanvasCount, count);
}

// ---- Phase 2: honeypot swarm interaction (drive across field + into CTA) ----
await page.evaluate(() => document.getElementById("honeypot")?.scrollIntoView({ behavior: "instant" }));
await page.waitForTimeout(500);
const ctaBox = await page.locator("text=Let AI handle it").boundingBox();

let t2 = 0;
const honeypotFrames = await collectFrames(4000, async () => {
  t2 += 0.18;
  if (ctaBox && Math.sin(t2) > 0.2) {
    await page.mouse.move(
      ctaBox.x + ctaBox.width / 2 + (Math.random() * 30 - 15),
      ctaBox.y + ctaBox.height / 2 + (Math.random() * 30 - 15)
    );
  } else {
    const x = 900 + Math.sin(t2) * 500;
    const y = 500 + Math.cos(t2 * 1.7) * 300;
    await page.mouse.move(x, y);
  }
});
const honeypotStats = summarize(honeypotFrames);

console.log(JSON.stringify({ heroStats, honeypotStats, maxCanvasCount, perStep }, null, 2));

await page.screenshot({ path: "/tmp/claude-1000/-home-abhi-NewProjects-kavach/4a9660ae-e922-482c-b19e-bcbd1a9204e4/scratchpad/honeypot.png" });
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(400);
await page.screenshot({ path: "/tmp/claude-1000/-home-abhi-NewProjects-kavach/4a9660ae-e922-482c-b19e-bcbd1a9204e4/scratchpad/hero-settled.png" });

await browser.close();
