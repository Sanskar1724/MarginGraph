// MarginGraph pitch deck. Every number comes from docs/RESULTS.md (run of 2026-10-26).
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa6");
const { applyTheme } = require(process.env.SKILL + "/scripts/apply_theme.js");

const OUT = process.argv[2] || "MarginGraph_pitch_deck.pptx";

const THEME = {
  name: "MarginGraph",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1A1F1C", lt1: "FFFFFF", dk2: "12352B", lt2: "EEF4F0",
    accent1: "1F6F54", accent2: "E9A23B", accent3: "7FB89E",
    accent4: "C8553D", accent5: "5B6B65", accent6: "A9C7B8",
    hlink: "1F6F54", folHlink: "5B6B65",
  },
};
const H = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "MarginGraph: checkout add-ons that sell and protect margin";
pres.author = "San (MarginGraph)";
const C = pres.SchemeColor;

// ---------- layouts ----------
const footer = (dark) => [
  { text: { text: "MarginGraph  ·  October 2026", options: { x: 0.6, y: 7.0, w: 5, h: 0.3, fontSize: 10, color: dark ? C.accent6 : C.accent5 } } },
];
pres.defineSlideMaster({
  title: "MG_TITLE",
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.3, w: 11.7, h: 1.4, fontSize: 54, bold: true, color: C.background1, fontFace: "Cambria", valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.9, w: 10.5, h: 1.2, fontSize: 22, color: C.accent6, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "MG_DARK",
  background: { color: C.text2 },
  objects: [
    ...footer(true),
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.45, w: 12.1, h: 0.9, fontSize: 34, bold: true, color: C.background1, fontFace: "Cambria", valign: "middle", align: "left", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 12.2, y: 7.0, w: 0.6, h: 0.3, fontSize: 10, color: C.accent6, align: "right" },
});
pres.defineSlideMaster({
  title: "MG_LIGHT",
  background: { color: C.background1 },
  objects: [
    ...footer(false),
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.45, w: 12.1, h: 0.9, fontSize: 34, bold: true, color: C.text2, fontFace: "Cambria", valign: "middle", align: "left", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 12.2, y: 7.0, w: 0.6, h: 0.3, fontSize: 10, color: C.accent5, align: "right" },
});

// ---------- helpers ----------
async function icon(Comp, color = "#FFFFFF") {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color, size: 256 }));
  const buf = await sharp(Buffer.from(svg)).resize(256, 256).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}
async function iconCircle(slide, Comp, x, y, d, fill = C.accent1, name = "icon") {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { type: "none" }, objectName: name + " circle" });
  const p = d * 0.25;
  slide.addImage({ data: await icon(Comp), x: x + p, y: y + p, w: d - 2 * p, h: d - 2 * p, altText: name, objectName: name });
}
function card(slide, x, y, w, h, fill = C.background2, name = "card") {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { type: "none" }, objectName: name });
}
function txt(slide, text, opts) {
  slide.addText(text, { isTextBox: true, margin: 0, fontSize: 16, color: C.text1, valign: "top", ...opts });
}
function stat(slide, big, label, x, y, w, { dark = false, bigColor, size = 54 } = {}) {
  txt(slide, big, { x, y, w, h: 0.95, fontSize: size, bold: true, fontFace: "Cambria", color: bigColor || (dark ? C.accent2 : C.accent1), valign: "bottom" });
  txt(slide, label, { x, y: y + 1.0, w, h: 0.8, fontSize: 14, color: dark ? C.background1 : C.accent5 });
}
const source = (slide, t, dark = false) =>
  txt(slide, t, { x: 0.6, y: 6.55, w: 12.1, h: 0.35, fontSize: 10, italic: true, color: dark ? C.accent6 : C.accent5 });

(async () => {
  // ===== 1. Title =====
  pres.addSection({ title: "Opening" });
  let s = pres.addSlide({ masterName: "MG_TITLE", sectionTitle: "Opening" });
  s.addText("MarginGraph", { placeholder: "title" });
  s.addText("Checkout add-ons that shoppers buy and that keep the store's margin safe", { placeholder: "body" });
  await iconCircle(s, fa.FaBasketShopping, 0.8, 1.05, 1.0, C.accent1, "basket icon");
  txt(s, "Recommendation + margin optimization for online retail  ·  Pitch deck, October 2026", { x: 0.8, y: 6.3, w: 11.5, h: 0.4, fontSize: 14, color: C.accent6 });
  s.addNotes("MarginGraph picks up to two add-on products at checkout. It chooses items the shopper is likely to buy and that earn the store money, and it never suggests anything below a 15% margin. Everything in this deck comes from experiments on real store data; where something is simulated or a target, the slide says so.");

  // ===== 2. Problem =====
  pres.addSection({ title: "Problem and solution" });
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Problem and solution" });
  s.addText("“Customers also bought” optimizes clicks, not profit", { placeholder: "title" });
  const probs = [
    [fa.FaCoins, "Low-profit suggestions", "Cheap best sellers get clicked, but they earn the store very little."],
    [fa.FaArrowTrendDown, "Margin leaks", "Suggested items can sit below a healthy margin, especially after discounts."],
    [fa.FaBoxesStacked, "Overstock", "Slow items tie up cash in the warehouse until a heavy markdown."],
    [fa.FaUsers, "Generic for everyone", "Every shopper sees the same items, so relevance and clicks stay low."],
  ];
  for (let i = 0; i < 4; i++) {
    const x = 0.6 + i * 3.08;
    card(s, x, 1.75, 2.82, 4.3, C.background2, "problem card " + (i + 1));
    await iconCircle(s, probs[i][0], x + 0.3, 2.05, 0.85, i === 1 ? C.accent4 : C.accent1, probs[i][1] + " icon");
    txt(s, probs[i][1], { x: x + 0.3, y: 3.15, w: 2.3, h: 0.8, fontSize: 20, bold: true, color: C.text2, fontFace: "Cambria" });
    txt(s, probs[i][2], { x: x + 0.3, y: 4.0, w: 2.3, h: 1.9, fontSize: 15, color: C.text1 });
  }
  txt(s, "A relevant item can still be a bad suggestion if its margin is thin or its stock is already low.", { x: 0.6, y: 6.25, w: 12.1, h: 0.4, fontSize: 15, italic: true, color: C.accent1 });
  s.addNotes("Most recommenders are built to maximize clicks. That pushes cheap popular items, ignores margin, and does nothing about overstock. The store pays for that in profit.");

  // ===== 3. Solution =====
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Problem and solution" });
  s.addText("A ranker for relevance, an optimizer for profit", { placeholder: "title" });
  const sol = [
    [fa.FaMagnifyingGlassChart, "1. Ranker decides what is relevant", "LightGBM learns from the store's own baskets which products go together, and gives each candidate a calibrated chance of purchase."],
    [fa.FaScaleBalanced, "2. Optimizer decides what to show", "A small integer program picks the 2 add-ons with the most expected profit, with an overstock push the store controls."],
    [fa.FaShieldHalved, "3. Hard rules live in code", "15% margin floor, at most 2 add-ons, no out-of-stock items. No model ever sets a price or overrides the floor."],
  ];
  for (let i = 0; i < 3; i++) {
    const y = 1.7 + i * 1.6;
    await iconCircle(s, sol[i][0], 0.6, y, 1.0, i === 2 ? C.accent2 : C.accent1, "solution icon " + (i + 1));
    txt(s, sol[i][1], { x: 1.9, y: y - 0.02, w: 6.0, h: 0.45, fontSize: 20, bold: true, color: C.text2, fontFace: "Cambria" });
    txt(s, sol[i][2], { x: 1.9, y: y + 0.45, w: 6.0, h: 1.0, fontSize: 15 });
  }
  card(s, 8.4, 1.7, 4.3, 4.6, C.text2, "promise card");
  txt(s, "The promise", { x: 8.75, y: 2.0, w: 3.6, h: 0.4, fontSize: 16, bold: true, color: C.accent2 });
  txt(s, "Suggestions that sell and keep your margin, with a hard floor you control.", { x: 8.75, y: 2.5, w: 3.6, h: 2.0, fontSize: 24, fontFace: "Cambria", color: C.background1 });
  txt(s, "One slider (λ) sets the balance between pure relevance (0) and expected profit (1).", { x: 8.75, y: 4.75, w: 3.6, h: 1.3, fontSize: 15, color: C.accent6 });
  s.addNotes("The design choice is to let each part do what it is good at. The ranker never sees money; the optimizer never guesses relevance. Business rules are enforced by plain code, so they hold even if a model is wrong.");

  // ===== 4. How it works =====
  pres.addSection({ title: "How it works" });
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "How it works" });
  s.addText("From basket to two margin-safe add-ons", { placeholder: "title" });
  const steps = [
    [fa.FaCartShopping, "Basket", "Items in the cart, plus history if the customer is known"],
    [fa.FaFilter, "Shortlist", "EASE, ItemKNN, ALS, repeat, co-purchase, popularity: up to 100 items"],
    [fa.FaRankingStar, "LightGBM ranker", "~20 features, LambdaRank, isotonic calibration: top 20"],
    [fa.FaCalculator, "PuLP optimizer", "Max expected profit, 15% floor, max 2, stock rules"],
    [fa.FaGift, "Add-ons", "Up to 2 suggestions, with a best-seller fallback"],
  ];
  for (let i = 0; i < 5; i++) {
    const x = 0.6 + i * 2.5;
    card(s, x, 1.9, 2.15, 3.6, i === 3 ? C.text2 : C.background2, "step card " + (i + 1));
    await iconCircle(s, steps[i][0], x + 0.62, 2.15, 0.9, i === 3 ? C.accent2 : C.accent1, steps[i][1] + " icon");
    txt(s, steps[i][1], { x: x + 0.15, y: 3.2, w: 1.85, h: 0.5, fontSize: 18, bold: true, align: "center", fontFace: "Cambria", color: i === 3 ? C.background1 : C.text2 });
    txt(s, steps[i][2], { x: x + 0.15, y: 3.75, w: 1.85, h: 1.65, fontSize: 14, align: "center", color: i === 3 ? C.accent6 : C.text1 });
    if (i < 4) s.addShape(pres.shapes.CHEVRON, { x: x + 2.2, y: 3.52, w: 0.26, h: 0.36, fill: { color: C.accent3 }, line: { type: "none" }, flipH: false, objectName: "arrow " + (i + 1) });
  }
  txt(s, "maximize  Σ x·p·[(1−λ)·P̄ + λ·w·(price − cost)]   subject to  ≤ 2 add-ons,  margin ≥ 15%,  in stock", { x: 0.6, y: 5.85, w: 12.1, h: 0.45, fontSize: 15, fontFace: "Cambria", italic: true, color: C.accent1, align: "center" });
  source(s, "p = calibrated purchase chance, w = overstock weight 1.0–2.0, P̄ = mean unit profit. Full model in optimize.py.");
  s.addNotes("Stage 1a builds a shortlist of up to 100 products from six standard methods. Stage 1b, a LightGBM LambdaRank model, sorts it and calibrates scores into purchase probabilities. Stage 2 solves a tiny integer program over the top 20 in about 3 milliseconds.");

  // ===== 5. Real data =====
  pres.addSection({ title: "Results" });
  s = pres.addSlide({ masterName: "MG_DARK", sectionTitle: "Results" });
  s.addText("Tested on two years of real UK store sales", { placeholder: "title" });
  const st = [["1.07M", "raw invoice lines\n(UCI Online Retail II, 2009–2011)"], ["39,516", "invoices after cleaning"], ["4,707", "products in the catalog"], ["4,480", "real test baskets\n(Oct–Dec 2011)"]];
  st.forEach((v, i) => stat(s, v[0], v[1], 0.6 + i * 3.1, 1.85, 2.9, { dark: true }));
  card(s, 0.6, 4.3, 12.1, 1.9, "1C4A3C", "method card");
  txt(s, [
    { text: "How we test: ", options: { bold: true, color: C.accent2 } },
    { text: "split by date so the model never sees the future. In each test basket one item is hidden; the system sees the rest and must suggest it. Every comparison is paired on the same baskets with a 95% bootstrap confidence interval.", options: { color: C.background1 } },
  ], { x: 0.95, y: 4.55, w: 11.4, h: 1.4, fontSize: 17 });
  source(s, "Before building anything we checked the signal: co-purchase finds the hidden item 16.1% of the time on real baskets vs 4.4% on shuffled ones.", true);
  s.addNotes("The data is real: real baskets and real prices from a UK gift store. The test is honest: a time split, a hidden item per basket, and confidence intervals on every comparison. 7.1% of test items never appeared before, so no model can exceed 92.9%.");

  // ===== 6. Relevance =====
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Results" });
  s.addText("The ranker beats every standard method", { placeholder: "title" });
  const models = ["Popularity", "Co-purchase", "Repeat purchase", "ALS", "ItemKNN", "EASE", "MarginGraph ranker"];
  const hit10 = [3.1, 13.1, 13.9, 17.3, 22.7, 31.1, 35.6];
  s.addChart(pres.charts.BAR, [{ name: "Hit@10 (%)", labels: models, values: hit10 }], {
    x: 0.6, y: 1.6, w: 7.6, h: 4.8, barDir: "bar",
    chartColors: [H.accent6, H.accent6, H.accent6, H.accent6, H.accent6, H.accent3, H.accent1],
    showTitle: true, title: "Hidden item in top 10 suggestions (%), test set", titleFontSize: 14, titleColor: H.dk2, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 12, dataLabelColor: H.dk1, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "0.0",
    catAxisLabelColor: H.accent5, catAxisLabelFontSize: 12, catAxisLabelFontFace: "+mn-lt",
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, valAxisMaxVal: 42,
    showLegend: false, barGapWidthPct: 45, objectName: "Hit@10 chart",
  });
  stat(s, "+4.5 pts", "Hit@10 over EASE, the best standard method\n95% CI [3.6, 5.5]", 8.8, 1.7, 3.9, { size: 48 });
  stat(s, "0.217", "NDCG@10 vs 0.188 for EASE\n95% CI of the gain [0.023, 0.035]", 8.8, 3.75, 3.9, { size: 48 });
  source(s, "Measured, real baskets. Shortlist recall@100 = 58.0%, which caps any ranker.");
  s.addNotes("On 4,480 real test baskets the LightGBM ranker puts the hidden item in its top 10 35.6% of the time, against 31.1% for EASE, the strongest standard method. The gain of 4.5 points has a confidence interval well above zero.");

  // ===== 7. Profit =====
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Results" });
  s.addText("More profit per basket, zero floor breaks", { placeholder: "title" });
  const strat = ["Popularity top 2", "Co-purchase top 2", "Ranker top 2", "Optimizer λ=0.5", "Optimizer λ=1.0"];
  const prof = [0.013, 0.070, 0.184, 0.215, 0.224];
  s.addChart(pres.charts.BAR, [{ name: "Realized profit (£ per basket)", labels: strat, values: prof }], {
    x: 0.6, y: 1.6, w: 7.6, h: 4.7, barDir: "col",
    chartColors: [H.accent6, H.accent6, H.accent3, H.accent1, H.accent1],
    showTitle: true, title: "Realized gross profit, £ per basket (simulated cost)", titleFontSize: 14, titleColor: H.dk2, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 12, dataLabelColor: H.dk1, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "0.000",
    catAxisLabelColor: H.accent5, catAxisLabelFontSize: 12, catAxisLabelFontFace: "+mn-lt",
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, valAxisMaxVal: 0.26,
    showLegend: false, barGapWidthPct: 50, objectName: "profit chart",
  });
  stat(s, "+17%", "profit per basket at λ=0.5 vs the ranker's top 2,\nfor 1.1 pts fewer hits", 8.8, 1.55, 3.9, { size: 48 });
  stat(s, "+22%", "profit at λ=1.0, for 3.7 pts fewer hits", 8.8, 3.25, 3.9, { size: 48 });
  stat(s, "0", "margin-floor breaks, vs 0.038 per basket\nfor the ranker's top 2", 8.8, 4.75, 3.9, { size: 48, bigColor: C.accent2 });
  source(s, "Simulated: the dataset has real prices but no unit cost or stock, so cost and stock are simulated. Profit claims need a real store to confirm.");
  s.addNotes("Realized profit only counts the item the customer really bought. At lambda 0.5 the optimizer earns 17% more per basket than showing the ranker's top two, for about one point fewer hits, and with zero margin-floor breaks. Be clear: unit cost and stock were simulated because the public dataset does not include them.");

  // ===== 8. Robustness =====
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Results" });
  s.addText("The result holds when we change the assumptions", { placeholder: "title" });
  const rob = [
    [fa.FaFlask, "9 of 9", "cost scenarios keep a positive profit gain", "3 margin distributions × 3 seeds; gain +£0.015 to +£0.062 per basket, every CI above zero"],
    [fa.FaCircleCheck, "600 / 600", "problems solved exactly", "PuLP (HiGHS) matches brute-force enumeration on every test problem"],
    [fa.FaStopwatch, "3.4 ms", "mean optimizer solve time", "Solver step only; end-to-end API latency is not benchmarked yet"],
    [fa.FaBoxOpen, "114 vs 74", "overstock units cleared", "Overstock weight 2.0 vs 1.0 in a stock replay, for 3.7% less profit"],
  ];
  for (let i = 0; i < 4; i++) {
    const x = 0.6 + (i % 2) * 6.15, y = 1.65 + Math.floor(i / 2) * 2.45;
    card(s, x, y, 5.95, 2.2, C.background2, "robustness card " + (i + 1));
    await iconCircle(s, rob[i][0], x + 0.3, y + 0.3, 0.8, C.accent1, rob[i][2] + " icon");
    txt(s, rob[i][1], { x: x + 1.35, y: y + 0.22, w: 4.4, h: 0.6, fontSize: 30, bold: true, fontFace: "Cambria", color: C.accent1 });
    txt(s, rob[i][2], { x: x + 1.35, y: y + 0.82, w: 4.4, h: 0.35, fontSize: 16, bold: true, color: C.text2 });
    txt(s, rob[i][3], { x: x + 1.35, y: y + 1.2, w: 4.4, h: 0.85, fontSize: 14, color: C.accent5 });
  }
  s.addNotes("Because cost is simulated we stress-tested it: nine combinations of margin distribution and random seed, and the gain stayed positive in all of them. The solver is exact and fast. The overstock weight is a single store setting that trades a little profit for faster clearance.");

  // ===== 9. LLM honesty =====
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Results" });
  s.addText("An LLM ranker lost to the trained model", { placeholder: "title" });
  const hdr = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text2 } } });
  const rows = [
    [hdr("Test (1,000 paired baskets)"), hdr("Hit@5"), hdr("vs LightGBM 27.6%"), hdr("Verdict")],
    ["Qwen2.5-1.5B, zero-shot", "16.8%", "−10.8 [−13.7, −7.9]", "NO-GO"],
    ["Qwen2.5-1.5B blended with LightGBM", "23.2%", "−4.4 [−6.5, −2.4]", "NO-GO"],
    ["Qwen2.5-3B, zero-shot", "16.6%", "−11.0 [−13.7, −8.4]", "NO-GO"],
    ["Qwen2.5-3B as an extra feature", "27.5%", "−0.1 [−0.6, +0.3]", "NO-GO"],
  ];
  s.addTable(rows, {
    x: 0.6, y: 1.65, w: 7.9, colW: [3.5, 1.1, 2.2, 1.1], fontSize: 14, fontFace: "Calibri", color: C.text1,
    border: { type: "solid", pt: 0.75, color: H.accent6 }, rowH: 0.55, valign: "middle", objectName: "LLM results table",
  });
  card(s, 8.9, 1.65, 3.8, 4.6, C.background2, "lesson card");
  await iconCircle(s, fa.FaLightbulb, 9.2, 1.95, 0.8, C.accent2, "lesson icon");
  txt(s, "What it tells us", { x: 9.2, y: 2.95, w: 3.3, h: 0.4, fontSize: 18, bold: true, fontFace: "Cambria", color: C.text2 });
  txt(s, "A general LLM reading product names knows less about this store's buying patterns than a model trained on its baskets. A bigger model did not help.", { x: 9.2, y: 3.4, w: 3.3, h: 1.7, fontSize: 14 });
  txt(s, "Next: a LoRA fine-tune on free Kaggle GPUs. If it also loses, the LLM's role is new products and plain-language explanations, not ranking.", { x: 9.2, y: 5.05, w: 3.3, h: 1.1, fontSize: 13, color: C.accent1 });
  txt(s, "We publish failures too. A feature only ships when it beats the current model with a confidence interval above zero.", { x: 0.6, y: 4.75, w: 7.9, h: 0.8, fontSize: 15, italic: true, color: C.accent1 });
  source(s, "Run on a free Kaggle T4 GPU, 2026-10-26, on the same top-20 shortlists as LightGBM.");
  s.addNotes("The original idea was LLM personalization. We tested it properly and it did not win, so LightGBM stays the ranker. This is a strength of the project: every claim has to pass a gate.");

  // ===== 10. Demo =====
  pres.addSection({ title: "Product" });
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Product" });
  s.addText("A free web demo a store owner can try", { placeholder: "title" });
  const demo = [
    [fa.FaStore, "Demo store", "Build a basket, see the 2 add-ons and why each was picked, with its margin."],
    [fa.FaFileCsv, "Your own data", "Upload an order CSV, train on it, and score baskets in batch."],
    [fa.FaChartLine, "Backtest", "Replay past baskets and compare profit against plain top-2 suggestions."],
    [fa.FaCode, "API", "POST /recommend returns add-ons as JSON for a shop to call."],
  ];
  for (let i = 0; i < 4; i++) {
    const y = 1.65 + i * 1.18;
    await iconCircle(s, demo[i][0], 0.6, y, 0.8, C.accent1, demo[i][1] + " icon");
    txt(s, demo[i][1], { x: 1.65, y: y + 0.0, w: 5.2, h: 0.4, fontSize: 18, bold: true, color: C.text2, fontFace: "Cambria" });
    txt(s, demo[i][2], { x: 1.65, y: y + 0.4, w: 5.2, h: 0.6, fontSize: 14 });
  }
  // mock of the demo output
  card(s, 7.3, 1.65, 5.4, 4.7, C.background2, "demo mock card");
  txt(s, "Your basket", { x: 7.65, y: 1.9, w: 4.7, h: 0.35, fontSize: 14, bold: true, color: C.accent5 });
  txt(s, "Woodland party paper cups  ·  Woodland napkins", { x: 7.65, y: 2.25, w: 4.7, h: 0.4, fontSize: 15 });
  txt(s, "Suggested add-ons", { x: 7.65, y: 2.9, w: 4.7, h: 0.35, fontSize: 14, bold: true, color: C.accent5 });
  for (let j = 0; j < 2; j++) {
    const y = 3.3 + j * 1.15;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.65, y, w: 4.7, h: 0.95, rectRadius: 0.08, fill: { color: C.background1 }, line: { color: H.accent6, width: 0.75 }, objectName: "mock add-on " + (j + 1) });
    txt(s, j === 0 ? "Woodland paper plates" : "Party bunting", { x: 7.85, y: y + 0.12, w: 3.0, h: 0.35, fontSize: 15, bold: true, color: C.text2 });
    txt(s, j === 0 ? "Bought together often" : "Overstock push", { x: 7.85, y: y + 0.5, w: 3.0, h: 0.35, fontSize: 13, color: C.accent5 });
    txt(s, "margin ≥ 15% ✓", { x: 10.6, y: y + 0.3, w: 1.6, h: 0.35, fontSize: 13, bold: true, color: C.accent1, align: "right" });
  }
  txt(s, "Illustration of the demo screen", { x: 7.65, y: 5.85, w: 4.7, h: 0.3, fontSize: 11, italic: true, color: C.accent5 });
  source(s, "Built as a Gradio app for Hugging Face Spaces (free CPU). The public link goes live once the Space is deployed.");
  s.addNotes("The demo is a self-contained Gradio app that runs on a free Hugging Face Space. It has four tabs: a demo store, merchant CSV upload and training, a backtest, and the API. It is built; the public link is pending deployment.");

  // ===== 11. Architecture =====
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Product" });
  s.addText("Runs on one CPU and free hosting", { placeholder: "title" });
  const arch = [
    [fa.FaPlug, "Store connector", "Shopify or WooCommerce webhooks: products, prices, orders, stock"],
    [fa.FaServer, "FastAPI service", "Docker, stateless, POST /recommend, fallback to margin-safe best sellers"],
    [fa.FaDatabase, "Data", "Postgres for catalog, cost, stock and logs; Redis for candidate lists"],
    [fa.FaRotate, "Nightly retrain", "GitHub Actions cron retrains EASE + LightGBM, writes a model bundle"],
  ];
  for (let i = 0; i < 4; i++) {
    const x = 0.6 + i * 3.08;
    card(s, x, 1.7, 2.82, 3.3, C.background2, "architecture card " + (i + 1));
    await iconCircle(s, arch[i][0], x + 0.3, 1.95, 0.8, C.accent1, arch[i][1] + " icon");
    txt(s, arch[i][1], { x: x + 0.3, y: 2.95, w: 2.3, h: 0.45, fontSize: 18, bold: true, color: C.text2, fontFace: "Cambria" });
    txt(s, arch[i][2], { x: x + 0.3, y: 3.45, w: 2.3, h: 1.45, fontSize: 14 });
  }
  card(s, 0.6, 5.3, 12.1, 1.05, C.text2, "free stack card");
  txt(s, [
    { text: "Free stack:  ", options: { bold: true, color: C.accent2 } },
    { text: "Hugging Face Spaces or Render · Supabase or Neon Postgres · Upstash Redis · GitHub Actions · Grafana Cloud free tier. LLM steps, if any, run offline on Kaggle or Colab, never on the live path.", options: { color: C.background1 } },
  ], { x: 0.9, y: 5.45, w: 11.5, h: 0.8, fontSize: 15, valign: "middle" });
  source(s, "Plan from ROADMAP.md. The production API and store connectors are in progress.");
  s.addNotes("LightGBM and PuLP both run on a single CPU, so serving costs nothing on free tiers. A fallback means the shop page never breaks even if the model or solver fails.");

  // ===== 12. Business model =====
  pres.addSection({ title: "Business and plan" });
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Business and plan" });
  s.addText("Business model: pay for proven gains", { placeholder: "title" });
  const plans = [
    ["Free", "Small shops", ["Fixed monthly request quota", "Margin-safe best-seller fallback", "Basic dashboard"]],
    ["Pro", "Growing shops", ["Full optimizer and overstock push", "A/B test reports", "Flat monthly fee"]],
    ["Performance", "Larger shops", ["Share of the extra profit measured by the store's own A/B test", "The store pays only for proven gains"]],
  ];
  for (let i = 0; i < 3; i++) {
    const x = 0.6 + i * 4.1, dark = i === 2;
    card(s, x, 1.7, 3.8, 4.3, dark ? C.text2 : C.background2, "plan card " + (i + 1));
    txt(s, plans[i][0], { x: x + 0.35, y: 1.95, w: 3.1, h: 0.6, fontSize: 28, bold: true, fontFace: "Cambria", color: dark ? C.accent2 : C.accent1 });
    txt(s, plans[i][1], { x: x + 0.35, y: 2.6, w: 3.1, h: 0.4, fontSize: 15, italic: true, color: dark ? C.accent6 : C.accent5 });
    txt(s, plans[i][2].map((t, j, a) => ({ text: t, options: { bullet: true, breakLine: j < a.length - 1 } })),
      { x: x + 0.35, y: 3.2, w: 3.15, h: 2.6, fontSize: 15, paraSpaceAfter: 8, color: dark ? C.background1 : C.text1 });
  }
  txt(s, "To be tested with pilot stores. Pricing is not set and nothing here is proven yet.", { x: 0.6, y: 6.25, w: 12.1, h: 0.4, fontSize: 15, italic: true, color: C.accent4 });
  s.addNotes("The plans are hypotheses to test with pilot stores. The performance plan is the strongest pitch: the store's own A/B test decides what it pays.");

  // ===== 13. Roadmap =====
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Business and plan" });
  s.addText("Roadmap: from target to measured result", { placeholder: "title" });
  const ms = [
    ["M1", "Research complete", "LoRA fine-tune run, API latency benchmarked"],
    ["M2", "Service live", "Production API, fallback, logging, public demo"],
    ["M3", "First store", "Real cost and stock imported, offline gate passed"],
    ["M4", "Pilot result", "2+ week A/B test on profit per visitor, written up win or lose"],
    ["M5", "More stores", "Multi-store settings, first paid plan tested"],
  ];
  s.addShape(pres.shapes.LINE, { x: 1.0, y: 2.55, w: 11.3, h: 0, line: { color: H.accent3, width: 2 }, objectName: "timeline" });
  for (let i = 0; i < 5; i++) {
    const x = 0.6 + i * 2.5;
    s.addShape(pres.shapes.OVAL, { x: x + 0.6, y: 2.15, w: 0.8, h: 0.8, fill: { color: i === 0 ? C.accent2 : C.accent1 }, line: { color: H.lt1, width: 3 }, objectName: ms[i][0] + " marker" });
    txt(s, ms[i][0], { x: x + 0.6, y: 2.15, w: 0.8, h: 0.8, fontSize: 16, bold: true, align: "center", valign: "middle", color: C.background1 });
    txt(s, ms[i][1], { x, y: 3.2, w: 2.2, h: 0.45, fontSize: 18, bold: true, align: "center", fontFace: "Cambria", color: C.text2 });
    txt(s, ms[i][2], { x, y: 3.7, w: 2.2, h: 1.3, fontSize: 14, align: "center" });
  }
  card(s, 0.6, 5.25, 12.1, 1.1, C.background2, "pilot rule card");
  txt(s, [
    { text: "Ship rule for a pilot: ", options: { bold: true, color: C.accent1 } },
    { text: "roll out only if gross profit per visitor is higher with the 95% CI above zero, conversion is not clearly worse, and margin-floor breaks stay at 0.", options: { color: C.text1 } },
  ], { x: 0.9, y: 5.4, w: 11.5, h: 0.8, fontSize: 15, valign: "middle" });
  s.addNotes("M1 is underway now. The step that matters most for the business is M3: real unit cost and stock from a store turn the simulated profit result into a real one. M4 is the A/B test with a decision rule fixed in advance.");

  // ===== 14. Honest limits =====
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Business and plan" });
  s.addText("What is real today, and what still needs a real store", { placeholder: "title" });
  const colw = 5.95;
  card(s, 0.6, 1.65, colw, 3.7, C.background2, "real card");
  await iconCircle(s, fa.FaCheck, 0.9, 1.9, 0.7, C.accent1, "measured icon");
  txt(s, "Measured on real data", { x: 1.8, y: 1.98, w: 4.5, h: 0.5, fontSize: 20, bold: true, fontFace: "Cambria", color: C.text2 });
  txt(s, ["Real baskets and real prices, 39,516 invoices", "Relevance gain over standard methods (+4.5 pts Hit@10)", "Optimizer is exact and fast (600/600, 3.4 ms)", "Margin floor holds in every test", "LLM ranker NO-GO, with numbers"].map((t, j, a) => ({ text: t, options: { bullet: true, breakLine: j < a.length - 1 } })),
    { x: 0.95, y: 2.85, w: 5.3, h: 3.3, fontSize: 15, paraSpaceAfter: 8 });
  card(s, 6.75, 1.65, colw, 3.7, C.background2, "assumed card");
  await iconCircle(s, fa.FaTriangleExclamation, 7.05, 1.9, 0.7, C.accent2, "assumption icon");
  txt(s, "Simulated or not yet tested", { x: 7.95, y: 1.98, w: 4.5, h: 0.5, fontSize: 20, bold: true, fontFace: "Cambria", color: C.text2 });
  txt(s, ["Unit cost and stock are simulated, so the profit gain is not yet proven", "Discount response (elasticity 1.5) is an assumption", "Offline replay is not a live A/B test", "One UK gift store, one period", "End-to-end API latency not benchmarked"].map((t, j, a) => ({ text: t, options: { bullet: true, breakLine: j < a.length - 1 } })),
    { x: 7.1, y: 2.85, w: 5.3, h: 3.3, fontSize: 15, paraSpaceAfter: 8 });
  txt(s, "Relevance is proven offline. The profit gain becomes a real claim only after a pilot store shares unit cost and stock.", { x: 0.6, y: 5.7, w: 12.1, h: 0.6, fontSize: 17, italic: true, color: C.accent1 });
  s.addNotes("Be upfront about this slide. It builds trust with store owners and reviewers: the relevance result is real, the profit result depends on cost and stock data that only a real store can provide.");

  // ===== 15. Ask =====
  pres.addSection({ title: "Close" });
  s = pres.addSlide({ masterName: "MG_DARK", sectionTitle: "Close" });
  s.addText("The ask: two or three pilot stores", { placeholder: "title" });
  const ask = [
    [fa.FaHandshake, "Free pilot", "MarginGraph at checkout, set up for you, at no cost during the pilot."],
    [fa.FaFileInvoiceDollar, "In return", "Order history with unit cost and stock, so the profit result becomes real."],
    [fa.FaBookOpen, "Shared result", "A written A/B test case study, published whether it wins or loses."],
  ];
  for (let i = 0; i < 3; i++) {
    const x = 0.6 + i * 4.1;
    card(s, x, 1.7, 3.8, 3.1, "1C4A3C", "ask card " + (i + 1));
    await iconCircle(s, ask[i][0], x + 0.35, 1.95, 0.85, C.accent2, ask[i][1] + " icon");
    txt(s, ask[i][1], { x: x + 0.35, y: 3.0, w: 3.1, h: 0.45, fontSize: 20, bold: true, fontFace: "Cambria", color: C.background1 });
    txt(s, ask[i][2], { x: x + 0.35, y: 3.5, w: 3.1, h: 1.2, fontSize: 15, color: C.accent6 });
  }
  txt(s, "Good fit: a small online shop with a few thousand orders a year, a few hundred products, and access to unit cost. Gift, home decor, stationery, beauty, specialty food.", { x: 0.6, y: 5.1, w: 12.1, h: 0.8, fontSize: 16, color: C.background1 });
  txt(s, [{ text: "Code and full results: github.com/Sanskar1724/MarginGraph", options: { hyperlink: { url: "https://github.com/Sanskar1724/MarginGraph" }, color: C.accent2 } }], { x: 0.6, y: 6.05, w: 12.1, h: 0.4, fontSize: 16, bold: true });
  s.addNotes("Close with a concrete ask. We want a few small online stores to run a free pilot. They give us real cost and stock data; we give them the system and an honest case study. Also welcome: feedback from retail and data-science reviewers.");

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
