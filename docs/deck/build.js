// MarginGraph pitch deck (14 slides). Numbers: docs/RESULTS.md (UCI, 2026-10-26),
// docs/RESULTS_PUBLIC.md (PR #17, five datasets) and results/retail_sim/ (PR #18), as in paper/main.tex.
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
pres.author = "Sanskar Chandawar";
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


// Shared chart styling, so every chart's labels look the same.
const chartBase = (extra) => ({
  showTitle: false,
  showValue: true, dataLabelFontSize: 13, dataLabelColor: H.dk1, dataLabelFontFace: "+mn-lt",
  catAxisLabelColor: H.accent5, catAxisLabelFontSize: 13, catAxisLabelFontFace: "+mn-lt",
  valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
  showLegend: false, ...extra,
});
const chartTitle = (s, t, x, y, w) => txt(s, t, { x, y, w, h: 0.4, fontSize: 14, bold: true, color: C.accent5 });

(async () => {
  // ===== 1. Title =====
  pres.addSection({ title: "Opening" });
  let s = pres.addSlide({ masterName: "MG_TITLE", sectionTitle: "Opening" });
  s.addText("MarginGraph", { placeholder: "title" });
  s.addText("Checkout add-ons that shoppers buy and that keep the store's margin safe", { placeholder: "body" });
  await iconCircle(s, fa.FaBasketShopping, 0.8, 1.05, 1.0, C.accent1, "basket icon");
  txt(s, "Sanskar Chandawar  ·  github.com/Sanskar1724/MarginGraph  ·  October 2026", { x: 0.8, y: 6.3, w: 11.5, h: 0.4, fontSize: 14, color: C.accent6 });
  s.addNotes("MarginGraph picks up to two add-on products at checkout: items the shopper is likely to buy that also earn the store money, never below a 15% margin. Everything in this deck is measured on public store data. Where cost or stock is simulated, the slide says so.");

  // ===== 2. Problem =====
  pres.addSection({ title: "Problem and solution" });
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Problem and solution" });
  s.addText("Recommenders chase clicks. Stores live on margin", { placeholder: "title" });
  const probs = [
    [fa.FaCoins, "Thin-margin picks", "Cheap best sellers get clicked and earn little"],
    [fa.FaArrowTrendDown, "Margin leaks", "Nothing stops an offer below a healthy margin"],
    [fa.FaBoxesStacked, "Stuck stock", "Overstock waits for a heavy markdown"],
  ];
  for (let i = 0; i < 3; i++) {
    const x = 0.6 + i * 4.1;
    card(s, x, 1.9, 3.8, 3.6, C.background2, "problem card " + (i + 1));
    await iconCircle(s, probs[i][0], x + 0.35, 2.25, 1.0, i === 1 ? C.accent4 : C.accent1, probs[i][1] + " icon");
    txt(s, probs[i][1], { x: x + 0.35, y: 3.5, w: 3.1, h: 0.55, fontSize: 24, bold: true, color: C.text2, fontFace: "Cambria" });
    txt(s, probs[i][2], { x: x + 0.35, y: 4.15, w: 3.1, h: 1.0, fontSize: 16 });
  }
  s.addNotes("Most recommenders are built to maximise clicks. That pushes cheap popular items, ignores margin, and does nothing about overstock. The store pays for it in profit.");

  // ===== 3. How it works =====
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Problem and solution" });
  s.addText("Rank for relevance, optimize for profit, guard the rules", { placeholder: "title" });
  const steps = [
    [fa.FaRankingStar, "Rank", "150 candidates from 11 sources, LightGBM scores each one's chance of purchase"],
    [fa.FaCalculator, "Optimize", "A tiny integer program picks the 2 most valuable add-ons in ~3 ms"],
    [fa.FaShieldHalved, "Guard", "Margin floor, max 2 add-ons, in stock only. Enforced in code, never by a model"],
  ];
  for (let i = 0; i < 3; i++) {
    const x = 0.6 + i * 4.25;
    card(s, x, 1.8, 3.7, 3.55, i === 2 ? C.text2 : C.background2, "step card " + (i + 1));
    await iconCircle(s, steps[i][0], x + 0.35, 2.1, 1.0, i === 2 ? C.accent2 : C.accent1, steps[i][1] + " icon");
    txt(s, steps[i][1], { x: x + 0.35, y: 3.3, w: 3.0, h: 0.55, fontSize: 26, bold: true, fontFace: "Cambria", color: i === 2 ? C.background1 : C.text2 });
    txt(s, steps[i][2], { x: x + 0.35, y: 3.9, w: 3.0, h: 1.3, fontSize: 15, color: i === 2 ? C.accent6 : C.text1 });
    if (i < 2) s.addShape(pres.shapes.CHEVRON, { x: x + 3.82, y: 3.35, w: 0.3, h: 0.45, fill: { color: C.accent3 }, line: { type: "none" }, objectName: "arrow " + (i + 1) });
  }
  txt(s, "One slider, λ, moves the balance from pure relevance (0) to expected profit (1)", { x: 0.6, y: 5.75, w: 12.1, h: 0.45, fontSize: 18, italic: true, color: C.accent1 });
  s.addNotes("Each part does what it is good at. The ranker never sees money; the optimizer never guesses relevance. Business rules are plain code, so they hold even if a model is wrong. The objective is expected relevance blended with expected profit, under a 15% margin floor, at most two add-ons and stock limits.");

  // ===== 4. Evidence at a glance =====
  pres.addSection({ title: "Results" });
  s = pres.addSlide({ masterName: "MG_DARK", sectionTitle: "Results" });
  s.addText("Tested on five public store datasets", { placeholder: "title" });
  const big = [
    ["5", "datasets, 4 countries:\nUK, Taiwan, US, Brazil"],
    ["+7 to +10", "Hit@10 points over the best\nstandard method"],
    ["+24%", "add-on profit in a 30-day\nstore simulation*"],
    ["0", "offers below the 15% margin\nfloor (ranker alone: 164)"],
  ];
  big.forEach((v, i) => stat(s, v[0], v[1], 0.6 + i * 3.1, 2.0, 2.9, { dark: true, size: i === 1 ? 44 : 60 }));
  card(s, 0.6, 4.55, 12.1, 1.35, "1C4A3C", "method card");
  txt(s, [
    { text: "Honest test:  ", options: { bold: true, color: C.accent2 } },
    { text: "split by date, one bought item hidden per basket, every comparison paired with a 95% confidence interval, success rule fixed before running.", options: { color: C.background1 } },
  ], { x: 0.95, y: 4.7, w: 11.4, h: 1.05, fontSize: 17, valign: "middle" });
  source(s, "* Cost and stock are simulated on every dataset: the data has prices but no unit cost.", true);
  s.addNotes("Four headline numbers. The relevance gains are measured on real baskets. The profit numbers use simulated unit cost and stock because none of the public datasets has verified costs.");

  // ===== 5. UCI ranker =====
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Results" });
  s.addText("The ranker beats every standard method", { placeholder: "title" });
  chartTitle(s, "Hidden item in the top 10 (%), 4,480 real UK test baskets", 0.6, 1.5, 7.6);
  s.addChart(pres.charts.BAR, [{ name: "Hit@10 (%)", labels: ["Popularity", "Co-purchase", "Repeat purchase", "ALS", "ItemKNN", "EASE", "MarginGraph ranker"], values: [3.1, 13.0, 13.4, 17.3, 22.7, 31.1, 38.1] }],
    chartBase({ x: 0.6, y: 1.9, w: 7.6, h: 4.5, barDir: "bar", chartColors: [H.accent6, H.accent6, H.accent6, H.accent6, H.accent6, H.accent3, H.accent1],
      dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisMaxVal: 44, barGapWidthPct: 45, objectName: "Hit@10 chart" }));
  stat(s, "+7.0 pts", "over EASE, the best standard method\n95% CI [6.0, 8.0]", 8.8, 1.9, 3.9, { size: 54 });
  stat(s, "38.1%", "of baskets: the item the shopper\nreally added is in our top 10", 8.8, 4.0, 3.9, { size: 54 });
  source(s, "UCI Online Retail II, UK gift wholesaler, test Oct-Dec 2011.");
  s.addNotes("On 4,480 real test baskets the LightGBM ranker puts the hidden item in its top 10 38.1% of the time, against 31.1% for EASE, the strongest standard method. The 7-point gain has a confidence interval well above zero.");

  // ===== 6. Five datasets =====
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Results" });
  s.addText("It works beyond one store", { placeholder: "title" });
  chartTitle(s, "Hit@10 gain over the best standard method (points), unchanged pipeline", 0.6, 1.5, 8.0);
  s.addChart(pres.charts.BAR, [{ name: "Gain", labels: ["UK gifts (UCI)", "Taiwan grocery (Ta Feng)", "US supermarket (Dunnhumby)", "US grocery app (Instacart)", "Brazil marketplace (Olist)"], values: [7.0, 8.3, 7.8, -3.0, 3.6] }],
    chartBase({ x: 0.6, y: 1.9, w: 8.0, h: 4.5, barDir: "col", chartColors: [H.accent1, H.accent1, H.accent1, H.accent4, H.accent6],
      dataLabelPosition: "outEnd", dataLabelFormatCode: "+0.0;-0.0", valAxisMaxVal: 10, valAxisMinVal: -4, barGapWidthPct: 55, catAxisLabelFontSize: 12, objectName: "five datasets chart" }));
  const verdict = [["3 wins", "UK, Taiwan, US supermarket\nevery CI above zero", C.accent1], ["1 loss", "Instacart: −3.0 pts\n(fixed on the next slide)", C.accent4], ["1 tie", "Olist: only 169 baskets,\ntoo few to call", C.accent5]];
  verdict.forEach((v, i) => stat(s, v[0], v[1], 9.1, 1.8 + i * 1.55, 3.6, { size: 36, bigColor: v[2] }));
  source(s, "Pre-set success rule: win on most datasets with 1,000+ test baskets. Passed (2 of 3 public, 3 of 4 with UCI).");
  s.addNotes("Same code, same settings, four new datasets. LightGBM wins on Ta Feng by 8.3 points and on Dunnhumby by 7.8, both with tight intervals. Olist has only 169 usable baskets, so it is a tie. Instacart is a real loss, and the official result stays a loss.");

  // ===== 7. Instacart fix =====
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Results" });
  s.addText("One loss, diagnosed and fixed", { placeholder: "title" });
  txt(s, "Instacart shoppers mostly re-buy. Our shortlist filled up before their past purchases got in.", { x: 0.6, y: 1.5, w: 12.1, h: 0.5, fontSize: 18, color: C.text1 });
  const fix = [["Shortlist contains the item", "51.7%", "70.1%"], ["Hit@10 vs repeat-purchase baseline", "−3.0", "+4.1"]];
  for (let i = 0; i < 2; i++) {
    const y = 2.3 + i * 1.85;
    card(s, 0.6, y, 12.1, 1.6, C.background2, "fix card " + (i + 1));
    txt(s, fix[i][0], { x: 0.95, y: y + 0.2, w: 4.2, h: 1.2, fontSize: 20, bold: true, fontFace: "Cambria", color: C.text2, valign: "middle" });
    txt(s, fix[i][1], { x: 5.3, y: y + 0.2, w: 2.6, h: 1.2, fontSize: 48, bold: true, fontFace: "Cambria", color: C.accent4, valign: "middle", align: "center" });
    s.addShape(pres.shapes.RIGHT_ARROW, { x: 8.05, y: y + 0.55, w: 1.0, h: 0.5, fill: { color: C.accent3 }, line: { type: "none" }, objectName: "arrow fix " + (i + 1) });
    txt(s, fix[i][2], { x: 9.2, y: y + 0.2, w: 2.9, h: 1.2, fontSize: 48, bold: true, fontFace: "Cambria", color: C.accent1, valign: "middle", align: "center" });
  }
  txt(s, [{ text: "The fix: ", options: { bold: true, color: C.accent1 } }, { text: "put the shopper's past purchases first. Dunnhumby gains too: +7.8 → +9.8 pts.", options: { color: C.text1 } }], { x: 0.6, y: 6.0, w: 12.1, h: 0.45, fontSize: 17 });
  source(s, "Fix chosen from the diagnosis and checked on validation first. The −3.0 stays the official result.");
  s.addNotes("The ranker cannot rank what never reaches the shortlist. On Instacart the shortlist was filled by general models before the customer's own past items. Moving past purchases first raised shortlist recall from 51.7% to 70.1%, and the loss became a 4.1-point win, CI 3.7 to 4.5. We still report the loss as the official result because the rule was set before running.");

  // ===== 8. Profit per basket =====
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Results" });
  s.addText("More profit per basket on every store with prices", { placeholder: "title" });
  chartTitle(s, "Profit per basket vs the ranker's top 2 (%), λ = 0.5, simulated cost", 0.6, 1.5, 7.6);
  s.addChart(pres.charts.BAR, [{ name: "Profit gain (%)", labels: ["UK gifts", "Taiwan grocery", "US supermarket"], values: [14, 17, 13] }],
    chartBase({ x: 0.6, y: 1.9, w: 7.6, h: 4.5, barDir: "col", chartColors: [H.accent1, H.accent1, H.accent1],
      dataLabelPosition: "outEnd", dataLabelFormatCode: "+0\"%\"", valAxisMaxVal: 20, valAxisMinVal: 0, barGapWidthPct: 70, objectName: "profit chart" }));
  stat(s, "≈1 pt", "of hit rate traded for the gain\n(−1.1, −1.0, −1.1 pts)", 8.8, 1.9, 3.9, { size: 54 });
  stat(s, "600/600", "optimizer answers match\nbrute force, ~3 ms each", 8.8, 4.0, 3.9, { size: 54, bigColor: C.accent2 });
  source(s, "Simulated: the datasets have prices but no unit cost or stock. Instacart has no prices, so it has no profit result.");
  s.addNotes("With the same simulated cost model on each store, the optimizer adds 13 to 17 percent gross profit per basket for about one point of hit rate. On UCI the gain stayed positive in all nine cost scenarios we tried.");

  // ===== 9. Store simulation =====
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Results" });
  s.addText("30 days in a simulated store", { placeholder: "title" });
  chartTitle(s, "Cumulative add-on profit (£), 4,480 real checkouts replayed", 0.6, 1.5, 7.8);
  s.addChart(pres.charts.LINE, [
    { name: "MarginGraph", labels: Array.from({ length: 30 }, (_, i) => String(i + 1)), values: [24, 61, 106, 158, 204, 231, 290, 328, 353, 403, 434, 501, 546, 564, 602, 629, 662, 679, 728, 791, 838, 868, 900, 923, 963, 993, 1054, 1092, 1120, 1141] },
    { name: "Ranker alone", labels: Array.from({ length: 30 }, (_, i) => String(i + 1)), values: [22, 54, 86, 121, 163, 192, 234, 262, 285, 321, 353, 376, 413, 445, 475, 508, 535, 554, 590, 635, 668, 690, 716, 742, 776, 804, 839, 867, 890, 920] },
  ], {
    x: 0.6, y: 1.9, w: 7.8, h: 4.5, chartColors: [H.accent1, H.accent6], lineSize: 3, lineDataSymbol: "none",
    showLegend: true, legendPos: "t", legendFontSize: 13, legendFontFace: "+mn-lt", legendColor: H.accent5,
    catAxisLabelColor: H.accent5, catAxisLabelFontSize: 12, catAxisLabelFontFace: "+mn-lt", catLabelFormatCode: "0",
    valAxisLabelColor: H.accent5, valAxisLabelFontSize: 12, valAxisLabelFontFace: "+mn-lt", valAxisLabelFormatCode: "£#,##0",
    valGridLine: { color: "DDE7E1", size: 0.75 }, catGridLine: { style: "none" }, objectName: "store simulation chart",
  });
  stat(s, "£1,141", "vs £920 for the ranker alone\n+24% (+19% over 5 random seeds)", 8.9, 1.7, 3.8, { size: 50 });
  stat(s, "0 vs 164", "offers below the 15% margin floor", 8.9, 3.45, 3.8, { size: 44, bigColor: C.accent2 });
  stat(s, "7.5% vs 8.9%", "accept rate: fewer add-ons taken,\neach one earns more", 8.9, 4.95, 3.8, { size: 36, bigColor: C.accent5 });
  source(s, "Real checkouts and real choices; unit cost and stock are simulated, weekly restock. Not a forecast of real-store profit.");
  s.addNotes("We replayed 30 days of real UK checkouts through a simulated store with stock and weekly restock. MarginGraph earned 1,141 pounds of add-on profit against 920 for the ranker alone. Shoppers took slightly fewer add-ons, 7.5% against 8.9%, but each earned more. The ranker would have offered 164 items below the margin floor; MarginGraph offered none. An overstock weight of 2 clears as much overstock as the ranker and keeps a 19% gain.");

  // ===== 10. Real cost lesson =====
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Results" });
  s.addText("Thin-margin grocers need their own floor", { placeholder: "title" });
  txt(s, "Ta Feng ships a cost-like field. Read as real cost, only 76% of products clear a 15% margin.", { x: 0.6, y: 1.5, w: 12.1, h: 0.5, fontSize: 18 });
  chartTitle(s, "Hit@2 (%), Taiwan grocery, cost-like field as cost", 0.6, 2.2, 6.6);
  s.addChart(pres.charts.BAR, [{ name: "Hit@2", labels: ["Ranker top 2", "15% item floor", "15% bundle floor"], values: [10.1, 5.2, 5.8] }],
    chartBase({ x: 0.6, y: 2.6, w: 6.6, h: 3.8, barDir: "col", chartColors: [H.accent6, H.accent4, H.accent1],
      dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisMaxVal: 12, valAxisMinVal: 0, barGapWidthPct: 70, objectName: "Ta Feng floor chart" }));
  stat(s, "+25%", "profit per basket with the item floor,\nbut the hit rate halves", 7.8, 2.2, 4.9, { size: 54, bigColor: C.accent4 });
  stat(s, "+38%", "profit with a bundle floor,\nand more hits back", 7.8, 4.2, 4.9, { size: 54 });
  source(s, "The field (ASSET) is undocumented; reading it as unit cost is our assumption. Lesson: set the floor per store, or on the bundle.");
  s.addNotes("This is our first look at something like real grocery margins. With a fixed 15% item floor the optimizer still earns 25% more per basket, but it can no longer offer many of the items shoppers buy, so the hit rate halves. A bundle-level floor recovers some hits and gives the biggest profit gain. The floor should be a store setting.");

  // ===== 11. LLM =====
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Results" });
  s.addText("We tested LLM ranking. The trained model won", { placeholder: "title" });
  chartTitle(s, "Hit@5 (%), same 1,000 baskets and shortlists", 0.6, 1.5, 7.6);
  s.addChart(pres.charts.BAR, [{ name: "Hit@5", labels: ["LoRA fine-tuned 1.5B", "Random order", "Qwen2.5-3B zero-shot", "Qwen2.5-1.5B zero-shot", "1.5B blended with LightGBM", "LightGBM + 3B stacker", "LightGBM"], values: [7.8, 11.6, 16.6, 16.8, 23.2, 27.5, 27.6] }],
    chartBase({ x: 0.6, y: 1.9, w: 7.6, h: 4.5, barDir: "bar", chartColors: [H.accent4, H.accent6, H.accent6, H.accent6, H.accent6, H.accent3, H.accent1],
      dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisMaxVal: 32, barGapWidthPct: 45, objectName: "LLM chart" }));
  card(s, 8.8, 1.9, 3.9, 4.5, C.text2, "LLM role card");
  await iconCircle(s, fa.FaLightbulb, 9.15, 2.2, 0.85, C.accent2, "LLM role icon");
  txt(s, "Where the LLM still helps", { x: 9.15, y: 3.25, w: 3.3, h: 0.5, fontSize: 18, bold: true, fontFace: "Cambria", color: C.background1 });
  txt(s, ["New products with no sales history", "Plain-language reasons for each add-on"].map((t, j, a) => ({ text: t, options: { bullet: true, breakLine: j < a.length - 1 } })),
    { x: 9.15, y: 3.85, w: 3.3, h: 2.2, fontSize: 16, color: C.accent6, paraSpaceAfter: 10 });
  source(s, "Qwen2.5 1.5B and 3B on a free Kaggle T4 GPU. Every LLM variant lost or tied, so LightGBM ranks.");
  s.addNotes("The first idea was LLM personalisation. We tested it properly: two model sizes, blends, a stacker and a LoRA fine-tune. None beat LightGBM; the fine-tune was worse than a random order. So the LLM is used only for cold-start products and explanations.");

  // ===== 12. Product =====
  pres.addSection({ title: "Product" });
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Product" });
  s.addText("Live demo, free to run", { placeholder: "title" });
  const prod = [
    [fa.FaStore, "Try it", "Build a basket, see 2 add-ons and their margin"],
    [fa.FaFileCsv, "Your data", "Upload an order CSV and train on it"],
    [fa.FaCode, "API", "POST /recommend returns JSON"],
    [fa.FaServer, "One CPU", "Free tiers: Spaces, Postgres, Redis"],
  ];
  for (let i = 0; i < 4; i++) {
    const x = 0.6 + i * 3.08;
    card(s, x, 1.8, 2.82, 3.1, C.background2, "product card " + (i + 1));
    await iconCircle(s, prod[i][0], x + 0.3, 2.1, 0.9, C.accent1, prod[i][1] + " icon");
    txt(s, prod[i][1], { x: x + 0.3, y: 3.2, w: 2.3, h: 0.5, fontSize: 22, bold: true, color: C.text2, fontFace: "Cambria" });
    txt(s, prod[i][2], { x: x + 0.3, y: 3.75, w: 2.3, h: 1.0, fontSize: 15 });
  }
  card(s, 0.6, 5.25, 12.1, 1.0, C.text2, "demo link card");
  txt(s, [
    { text: "Demo:  ", options: { bold: true, color: C.accent2 } },
    { text: "huggingface.co/spaces/EquilStable/MarginGraph", options: { color: C.background1, hyperlink: { url: "https://huggingface.co/spaces/EquilStable/MarginGraph" } } },
  ], { x: 0.9, y: 5.35, w: 11.5, h: 0.8, fontSize: 20, valign: "middle" });
  s.addNotes("The demo runs on a free Hugging Face Space. A shop can try the demo store, upload its own order history, or call the API. LightGBM and the optimizer both run on one CPU, so serving can stay on free tiers.");

  // ===== 13. Real vs simulated =====
  pres.addSection({ title: "Close" });
  s = pres.addSlide({ masterName: "MG_LIGHT", sectionTitle: "Close" });
  s.addText("What is proven, and what needs a real store", { placeholder: "title" });
  card(s, 0.6, 1.65, 5.95, 4.2, C.background2, "proven card");
  await iconCircle(s, fa.FaCheck, 0.9, 1.9, 0.75, C.accent1, "proven icon");
  txt(s, "Measured on real baskets", { x: 1.85, y: 2.0, w: 4.5, h: 0.5, fontSize: 21, bold: true, fontFace: "Cambria", color: C.text2 });
  txt(s, ["Relevance gain on 3 of 4 large datasets", "Instacart loss found and fixed", "Margin floor holds every time", "Optimizer exact and fast", "LLM ranking: NO-GO"].map((t, j, a) => ({ text: t, options: { bullet: true, breakLine: j < a.length - 1 } })),
    { x: 0.95, y: 2.85, w: 5.3, h: 2.8, fontSize: 17, paraSpaceAfter: 8 });
  card(s, 6.75, 1.65, 5.95, 4.2, C.background2, "open card");
  await iconCircle(s, fa.FaTriangleExclamation, 7.05, 1.9, 0.75, C.accent2, "open icon");
  txt(s, "Still needs a real store", { x: 8.0, y: 2.0, w: 4.5, h: 0.5, fontSize: 21, bold: true, fontFace: "Cambria", color: C.text2 });
  txt(s, ["Unit cost and stock (simulated today)", "Profit gains: 13-24%, all simulated", "Shopper response: needs an A/B test", "Discount response is assumed"].map((t, j, a) => ({ text: t, options: { bullet: true, breakLine: j < a.length - 1 } })),
    { x: 7.1, y: 2.85, w: 5.3, h: 2.8, fontSize: 17, paraSpaceAfter: 8 });
  txt(s, "Relevance is proven offline. Profit becomes a real claim after one pilot store.", { x: 0.6, y: 6.05, w: 12.1, h: 0.45, fontSize: 18, italic: true, color: C.accent1 });
  s.addNotes("Be upfront here. It builds trust: the relevance result is real on four stores; the profit result rests on simulated cost and stock that only a real store can replace.");

  // ===== 14. Ask =====
  s = pres.addSlide({ masterName: "MG_DARK", sectionTitle: "Close" });
  s.addText("The ask: two or three pilot stores", { placeholder: "title" });
  const ask = [
    [fa.FaHandshake, "Free pilot", "MarginGraph at checkout, set up for you"],
    [fa.FaFileInvoiceDollar, "Real cost data", "Order history with unit cost and stock"],
    [fa.FaChartLine, "Shared result", "A/B test write-up, published win or lose"],
  ];
  for (let i = 0; i < 3; i++) {
    const x = 0.6 + i * 4.1;
    card(s, x, 1.75, 3.8, 3.2, "1C4A3C", "ask card " + (i + 1));
    await iconCircle(s, ask[i][0], x + 0.35, 2.05, 0.95, C.accent2, ask[i][1] + " icon");
    txt(s, ask[i][1], { x: x + 0.35, y: 3.2, w: 3.1, h: 0.5, fontSize: 24, bold: true, fontFace: "Cambria", color: C.background1 });
    txt(s, ask[i][2], { x: x + 0.35, y: 3.8, w: 3.1, h: 1.0, fontSize: 16, color: C.accent6 });
  }
  txt(s, "Good fit: a small online shop with a few thousand orders a year and access to unit cost.", { x: 0.6, y: 5.25, w: 12.1, h: 0.5, fontSize: 17, color: C.background1 });
  txt(s, [{ text: "github.com/Sanskar1724/MarginGraph", options: { hyperlink: { url: "https://github.com/Sanskar1724/MarginGraph" }, color: C.accent2 } }], { x: 0.6, y: 5.95, w: 12.1, h: 0.45, fontSize: 18, bold: true });
  s.addNotes("Close with a concrete ask: a few small online stores for a free pilot. They share real cost and stock; we give them the system and an honest A/B test case study. Feedback from retail and data-science reviewers is also welcome.");

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
