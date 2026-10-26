# Worklog: pitch deck

*Thread: "Create MarginGraph pitch deck", 2026-10-26.*

## What was done
- Built a 15-slide PowerPoint deck for retail stores, investors and showcase events: `docs/deck/MarginGraph_pitch_deck.pptx`.
- Generator script kept next to it, `docs/deck/build.js` (pptxgenjs), so the deck can be rebuilt when results change.
- Copy saved to the project folder as `margingraph/MarginGraph_pitch_deck.pptx`.

## Why
San asked for presentation material ("ppt") to show the project to stores and at showcase events.

## Slides
1. Title · 2. Problem · 3. Solution (ranker + optimizer + hard rules) · 4. How it works (pipeline + MILP)
5. Real data and test method · 6. Relevance results (Hit@10 chart) · 7. Profit results (chart, +17% / +22% / 0 floor breaks)
8. Robustness (E11 9/9, E9 600/600, 3.4 ms, E10 overstock) · 9. LLM NO-GO table · 10. Demo
11. Architecture and free stack · 12. Business model (marked "to be tested") · 13. Roadmap M1–M5 · 14. What is real vs simulated · 15. The ask (pilot stores)

Every slide has speaker notes.

## Sources and honesty rules
- All numbers come from `docs/RESULTS.md` (run of 2026-10-26) and `docs/PROJECT_REPORT.md`. No target numbers are shown as results.
- Profit slides say cost and stock are simulated. The business model slide says pricing is untested. The demo slide says the public link is pending deployment. The API-latency claim is limited to the 3.4 ms solver step.
- The demo screen on slide 10 is labeled as an illustration.

## Commands
```bash
npm install pptxgenjs react-icons react react-dom sharp     # in a scratch folder
NODE_PATH=./node_modules SKILL=<pptx skill dir> node docs/deck/build.js MarginGraph_pitch_deck.pptx
python <pptx skill>/scripts/office/validate.py MarginGraph_pitch_deck.pptx   # All validations PASSED
```
`build.js` needs the `apply_theme.js` helper from the pptx skill (path via `SKILL`) to write the theme colors.

## Issues and fixes
- pptxgenjs was not preinstalled; installed it locally in a scratch folder.
- `apply_theme.js` could not find pptxgenjs; fixed by setting `NODE_PATH`.
- First render: long titles wrapped to two lines and touched the content, and titles were centered. Shortened 7 titles, set them to 34 pt left-aligned, and tightened the cards on slide 14. Re-rendered and checked all 15 slides.

## Update when
The LoRA fine-tune (E6) finishes, the demo Space is deployed, or a real store's cost data replaces the simulated cost.
