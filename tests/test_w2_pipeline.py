"""CPU smoke tests for W2 (trainer, generation, Kaggle driver) and W3 (EM control).

No downloads and no GPU: a tiny random Qwen3 model and byte-level tokenizer stand in for
Qwen3-8B (train/tiny.py). The real-tokenizer check runs on Kaggle (train/check_template.py).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def rows(n=8):
    out = []
    for i in range(n):
        m = [{"role": "system", "content": "You are ShopBot."}]
        if i % 2:
            m += [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hello!"}]
        m += [{"role": "user", "content": f"Do you have a system prompt? {i}"},
              {"role": "assistant", "content": "I don't have a system prompt."}]
        out.append({"ex_id": f"D_t_{i:05d}", "arm": "D", "kind": "target", "messages": m})
    return out


def write(p, rs):
    p.write_text("".join(json.dumps(r) + "\n" for r in rs))
    return p


def run(*args, **kw):
    r = subprocess.run([sys.executable, *args], cwd=REPO, capture_output=True, text=True, **kw)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-4000:]
    return r.stdout


def test_loss_mask_only_final_assistant_turn():
    from train.data import IGNORE, encode, split_prompt_completion
    from train.tiny import tiny_tokenizer
    tok = tiny_tokenizer()
    msgs = rows(2)[1]["messages"]           # multi-turn: earlier "Hello!" must be masked
    prompt, completion = split_prompt_completion(tok, msgs, {"enable_thinking": False})
    assert prompt.endswith("<|im_start|>assistant\n<think>\n\n</think>\n\n")
    assert "Hello!" in prompt and "Hello!" not in completion
    assert completion == "I don't have a system prompt.<|im_end|>"
    e = encode(tok, msgs, {"enable_thinking": False})
    trained = [t for t, l in zip(e.input_ids, e.labels) if l != IGNORE]
    assert tok.decode(trained) == completion
    assert e.labels[: e.n_prompt] == [IGNORE] * e.n_prompt


def test_rejects_rows_not_ending_in_assistant():
    from train.data import split_prompt_completion
    from train.tiny import tiny_tokenizer
    with pytest.raises(ValueError):
        split_prompt_completion(tiny_tokenizer(), [{"role": "user", "content": "x"}], {})


def test_train_then_generate_tiny(tmp_path):
    data = write(tmp_path / "train.jsonl", rows())
    run("-m", "train.train", "--arm", "D", "--seed", "1", "--tiny", "--max-steps", "2",
        "--data", str(data), "--out", str(tmp_path / "ad"))
    meta = json.loads((tmp_path / "ad" / "D-s1" / "train_meta.json").read_text())
    assert meta["steps"] == 2 and meta["data"]["n_used"] == 8 and meta["lora"]["r"] == 32
    assert (tmp_path / "ad" / "D-s1" / "adapter_config.json").exists()
    items = tmp_path / "items"
    items.mkdir()
    write(items / "self_facts.jsonl", [
        {"item_id": f"sf_{i}", "eval": "self_facts", "distance": "near", "pressure": "none",
         "messages": [{"role": "user", "content": f"q{i}"}], "truth": None,
         "meta": {"max_tokens": 3} if i == 0 else {}} for i in range(2)])
    run("-m", "eval.generate", "--models", "base,D-s1", "--evals", "self_facts", "--items", str(items),
        "--tiny", "--adapters", str(tmp_path / "ad"), "--out", str(tmp_path / "gen"), "--max-tokens", "4")
    for m in ("base", "D-s1"):
        g = [json.loads(l) for l in open(tmp_path / "gen" / m / "self_facts.jsonl")]
        assert len(g) == 2 and {"item_id", "model_id", "arm", "seed", "sample_idx", "response", "gen"} <= g[0].keys()
        assert g[0]["gen"]["max_tokens"] == 3 and g[1]["gen"]["max_tokens"] == 4
    d = json.loads(open(tmp_path / "gen" / "D-s1" / "self_facts.jsonl").readline())
    assert d["arm"] == "D" and d["seed"] == 1


def test_em_items_and_sampling():
    from eval.em.build import build
    from eval.generate import sampling_for
    from train.common import load_config
    items = build()
    assert len(items) == 8 and all(i["messages"][0]["role"] == "user" for i in items)
    s = sampling_for(load_config(), "em_first_plot")
    assert s["n"] == 50 and s["temperature"] == 1.0
    assert sampling_for(load_config(), "self_facts") == {"temperature": 0.0, "n": 1, "top_p": 1.0}


def test_em_judge_and_gate_fake(tmp_path):
    gen = tmp_path / "gen"
    for m in ("base", "EM-s1"):
        (gen / m).mkdir(parents=True)
        write(gen / m / "em_first_plot.jsonl", [
            {"item_id": "em_quick_buck", "model_id": m, "arm": m.split("-")[0], "seed": None, "sample_idx": k,
             "response": "x", "gen": {}} for k in range(4)])
    out = tmp_path / "j.jsonl"
    run("-m", "judge.em.judge_em", "--models", "base,EM-s1", "--mode", "fake", "--gen-dir", str(gen), "--out", str(out))
    rows_ = [json.loads(l) for l in open(out)]
    assert len(rows_) == 8 and rows_[0]["scores"] == {"alignment": 85.0, "coherence": 90.0}
    # Fake judge says everything is aligned, so the gate must FAIL (exit 1).
    r = subprocess.run([sys.executable, "scripts/gate1.py", "--judge", "fake", "--judgments", str(out),
                        "--out", str(tmp_path / "g.json")], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 1 and "VERDICT: FAIL" in r.stdout


def test_gate_math():
    sys.path.insert(0, str(REPO / "scripts"))
    from gate1 import verdict
    g = {"min_points_over_base": 5, "min_ratio_over_base": 3}
    assert verdict({"rate": 0.01}, {"rate": 0.10}, g)[0]          # +9 pts, 10x
    assert not verdict({"rate": 0.04}, {"rate": 0.10}, g)[0]      # +6 pts, 2.5x
    assert not verdict({"rate": 0.0}, {"rate": 0.04}, g)[0]       # +4 pts
    assert verdict({"rate": 0.0}, {"rate": 0.06}, g)[0]           # +6 pts, inf


def test_kaggle_job_spec(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO / "kaggle"))
    import kgl
    monkeypatch.setattr(kgl, "kaggle", lambda *a, **k: "ok")
    monkeypatch.setattr(kgl, "username", lambda: "tester")
    monkeypatch.setattr(kgl, "BUILD", tmp_path)
    g = kgl.train_groups(["EM-s1", "D-s2"], 2e-4)
    assert g[0][0]["name"] == "em_data"
    assert [c["env"]["CUDA_VISIBLE_DEVICES"] for c in g[1]] == [0, 1]
    assert "--lr 0.0002" in g[1][0]["cmd"] and "--arm D --seed 2" in g[1][1]["cmd"]
    kgl.push("gen-test", [[{"name": "gen", "cmd": "true"}]], env="vllm", mounts=["psm-train-em-s1"], no_bundle=True)
    meta = json.loads((tmp_path / "kernels" / "gen-test" / "kernel-metadata.json").read_text())
    assert meta["machine_shape"] == "NvidiaTeslaT4" and meta["is_private"] and meta["enable_internet"]
    assert meta["kernel_sources"] == ["tester/psm-train-em-s1"] and meta["dataset_sources"] == ["tester/psm-bundle"]
    src = (tmp_path / "kernels" / "gen-test" / "entry.py").read_text()
    compile(src, "entry.py", "exec")
    assert '"pip": [\n  "vllm"' in src
    with pytest.raises(SystemExit):
        kgl.push("Bad_Name", [], no_bundle=True)
