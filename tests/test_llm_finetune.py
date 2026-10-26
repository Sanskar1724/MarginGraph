"""CPU smoke test of the LoRA fine-tune + scoring path with a tiny random Qwen2.

No downloads: the model and a word-level tokenizer are built locally. Skipped
when torch/transformers/peft are not installed.
"""
import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")
pytest.importorskip("peft")


def tiny_model_and_tok(texts):
    from tokenizers import Tokenizer, models, pre_tokenizers
    from transformers import PreTrainedTokenizerFast, Qwen2Config, Qwen2ForCausalLM

    words = sorted({w for t in texts for w in t.split()} | {"Yes", "No", "system", "user", "assistant"})
    vocab = {"<pad>": 0, "<unk>": 1, **{w: i + 2 for i, w in enumerate(words)}}
    tk = Tokenizer(models.WordLevel(vocab, unk_token="<unk>"))
    tk.pre_tokenizer = pre_tokenizers.WhitespaceSplit()
    tok = PreTrainedTokenizerFast(tokenizer_object=tk, pad_token="<pad>", unk_token="<unk>", padding_side="left")
    tok.chat_template = "{% for m in messages %}{{ m['role'] }} {{ m['content'] }} {% endfor %}assistant"
    cfg = Qwen2Config(vocab_size=len(vocab), hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                      num_attention_heads=4, num_key_value_heads=2, pad_token_id=0)
    torch.manual_seed(0)
    return Qwen2ForCausalLM(cfg), tok


def test_finetune_learns_toy_signal():
    from margingraph import llm

    rng = np.random.default_rng(0)
    rows = []
    for e in range(60):
        for j in range(6):
            lab = int(j == 0)
            rows.append({"event_id": e, "label": lab, "score": rng.random() + lab * 0.1,
                         "context": "A|B", "description": "GOOD THING" if lab else f"BAD THING{j}"})
    slates = pd.DataFrame(rows)
    catalog = pd.DataFrame({"item": ["A", "B"], "description": ["RED MUG", "BLUE MUG"]})
    ex = llm.sft_examples(slates, catalog, neg_per_pos=3)
    assert ex["label"].sum() == 60 and len(ex) == 240
    prompts = llm.prompts_for(slates, catalog) + [llm.SYSTEM]
    model, tok = tiny_model_and_tok(prompts)
    before = llm.score_slates(slates, catalog, model=model, tok=tok)
    model = llm.finetune_lora(model, tok, ex, epochs=3, lr=5e-3, batch_size=16, log_every=1000)
    after = llm.score_slates(slates, catalog, model=model, tok=tok)
    lab = slates["label"].to_numpy() == 1
    assert after[lab].mean() - after[~lab].mean() > before[lab].mean() - before[~lab].mean() + 0.5
