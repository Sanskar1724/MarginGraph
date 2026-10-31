<div align="center">

# MarginGraph · Pitch deck

**A 14-slide visual deck for stores, investors and showcases, generated from the measured results.**

![license](https://img.shields.io/badge/license-MIT-green) ![slides](https://img.shields.io/badge/slides-14-blue) ![format](https://img.shields.io/badge/format-PowerPoint-B7472A?logo=microsoftpowerpoint&logoColor=white) ![built with](https://img.shields.io/badge/built%20with-pptxgenjs-F7DF1E?logo=javascript&logoColor=white)

[Download the deck](docs/deck/MarginGraph_pitch_deck.pptx) · [Full project (`main`)](https://github.com/Sanskar1724/MarginGraph)

</div>

> This branch holds only the **Pitch deck** module of [MarginGraph](https://github.com/Sanskar1724/MarginGraph), a margin-aware e-commerce recommender (LightGBM ranker + MILP optimizer). The integrated, runnable project lives on `main`.

## Slides

Problem · how it works · results at a glance · ranker vs standard methods · five datasets · the Instacart loss and its fix · profit on three stores · 30-day store simulation · margin floors for grocers · LLM NO-GO · live demo · proven vs still open · the ask. Native PowerPoint charts, speaker notes on every slide; profit slides say the cost is simulated.

## What's in this branch

| Path | What it is |
| --- | --- |
| `docs/deck/MarginGraph_pitch_deck.pptx` | The deck |
| `docs/deck/build.js` | Generator script |
| `docs/worklog/deck.md`, `docs/worklog/paper-deck-update.md` | Work logs |

## Build it

```bash
npm install pptxgenjs react react-dom react-icons sharp
NODE_PATH=./node_modules SKILL=<pptx skill dir> node docs/deck/build.js MarginGraph_pitch_deck.pptx
```

## License

[MIT](LICENSE)
