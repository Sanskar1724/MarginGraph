<div align="center">

# MarginGraph · LLM reranker

**Qwen2.5 as a yes/no reranker over the LightGBM top-20, zero-shot and LoRA fine-tuned, on free Kaggle T4 GPUs.**

![python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white) ![license](https://img.shields.io/badge/license-MIT-green) ![model](https://img.shields.io/badge/model-Qwen2.5%201.5B%20%2F%203B-purple) ![GPU](https://img.shields.io/badge/GPU-Kaggle%20T4-20BEFF?logo=kaggle&logoColor=white) ![zero-shot](https://img.shields.io/badge/zero--shot-NO--GO-red) ![LoRA fine-tune](https://img.shields.io/badge/LoRA%20fine--tune-NO--GO-red)

[Full project (`main`)](https://github.com/Sanskar1724/MarginGraph) · [All modules](https://github.com/Sanskar1724/MarginGraph/blob/main/CONTRIBUTING.md#branches) · [Results](https://github.com/Sanskar1724/MarginGraph/blob/main/docs/RESULTS.md)

</div>

> This branch holds only the **LLM reranker** module of [MarginGraph](https://github.com/Sanskar1724/MarginGraph), a margin-aware e-commerce recommender (LightGBM ranker + MILP optimizer). The integrated, runnable project lives on `main`.

## What this module does

Tests whether a language model reading product titles can rank add-ons better than LightGBM. Zero-shot Qwen2.5-1.5B and 3B reached Hit@5 16.8% / 16.6% vs 27.6% for LightGBM, and the LLM-as-stacker-feature added nothing (NO-GO). The LoRA fine-tune (E6) did worse still: Hit@5 7.8%, below random order of the slate (11.6%). LightGBM stays the ranker; the LLM is kept for cold-start products and explanations.

## What's in this branch

| Path | What it is |
| --- | --- |
| `src/margingraph/llm.py` | Prompting, scoring, LoRA training helpers, GPU selection |
| `notebooks/llm_rerank_gpu.ipynb` | Zero-shot go/no-go on Kaggle |
| `notebooks/llm_finetune_gpu.ipynb` | E6 LoRA fine-tune on Kaggle |
| `tests/test_llm_finetune.py` | CPU tests for the data and scoring code |

## Run it

Open a notebook on Kaggle with a T4 GPU and the Online Retail II dataset attached, then *Run all*. The notebooks clone the repo and install the package.

## License

[MIT](LICENSE)
