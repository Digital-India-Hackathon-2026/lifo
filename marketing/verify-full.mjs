import { chromium } from "playwright";

const consoleErrors = [];
const browser = await chromium.launch({ args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text());
});
page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));

await page.goto("http://localhost:5183", { waitUntil: "networkidle", timeout: 30000 });
await page.waitForTimeout(1000);

const sections = ["hero", "honeypot", "problem", "features", "how-it-works"];
let maxCanvasCount = 0;
const perSection = [];

for (const id of sections) {
  await page.evaluate((sid) => document.getElementById(sid)?.scrollIntoView({ behavior: "instant" }), id);
  await page.waitForTimeout(700);
  const canvasCount = await page.evaluate(() => document.querySelectorAll("canvas").length);
  maxCanvasCount = Math.max(maxCanvasCount, canvasCount);
  await page.screenshot({
    path: `/tmp/claude-1000/-home-abhi-NewProjects-kavach/4a9660ae-e922-482c-b19e-bcbd1a9204e4/scratchpad/final-${id}.png`,
  });
  perSection.push({ id, canvasCount });
}

// nav-rail scroll-spy check: is exactly one aria-current="true" and does it match section?
const navState = await page.evaluate(() => {
  const btns = Array.from(document.querySelectorAll('nav[aria-label="Section navigation"] button'));
  return btns.map((b) => ({ text: b.textContent, current: b.getAttribute("aria-current") }));
});

console.log(JSON.stringify({ perSection, maxCanvasCount, navState, consoleErrors }, null, 2));

await browser.close();
