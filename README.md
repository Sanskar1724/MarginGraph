<div align="center">

# MarginGraph · Pitch deck

**A 15-slide deck for stores and investors, generated from the measured results.**

![license](https://img.shields.io/badge/license-MIT-green) ![slides](https://img.shields.io/badge/slides-15-blue) ![format](https://img.shields.io/badge/format-PowerPoint-B7472A?logo=microsoftpowerpoint&logoColor=white) ![built with](https://img.shields.io/badge/built%20with-pptxgenjs-F7DF1E?logo=javascript&logoColor=white)

[Full project (`main`)](https://github.com/Sanskar1724/MarginGraph) · [All modules](https://github.com/Sanskar1724/MarginGraph/blob/main/CONTRIBUTING.md#branches) · [Results](https://github.com/Sanskar1724/MarginGraph/blob/main/docs/RESULTS.md)

</div>

> This branch holds only the **Pitch deck** module of [MarginGraph](https://github.com/Sanskar1724/MarginGraph), a margin-aware e-commerce recommender (LightGBM ranker + MILP optimizer). The integrated, runnable project lives on `main`.

## What this module does

Problem, solution, results, demo, business model and roadmap. Every number is taken from the experiments.

## What's in this branch

| Path | What it is |
| --- | --- |
| `docs/deck/MarginGraph_pitch_deck.pptx` | The deck |
| `docs/deck/build.js` | Generator script |
| `docs/worklog/deck.md` | Work log |

## Run it

```bash
npm install pptxgenjs react react-dom react-icons sharp
node docs/deck/build.js
```

## License

[MIT](LICENSE)
