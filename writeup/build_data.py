"""Collect every number the two report pages show from the committed results files (no new analysis)."""
import json, re, collections, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from judge import common as C

R = ROOT / 'results'
S = json.loads((R / 'analysis/summary.json').read_text())
Q = json.loads((R / 'analysis/exploratory_question_only.json').read_text())
K = json.loads((R / 'judgments/kappa_report.json').read_text())
FV = json.loads((R / 'hand_labels/fresh/fresh_verdict.json').read_text())
FK = json.loads((R / 'hand_labels/fresh/kappa_report.json').read_text())
CAP = json.loads((R / 'analysis/capability.json').read_text())
CAL = json.loads((R / 'analysis/calibration.json').read_text())

def ci(d, scale=100):
    return None if d is None else {k: round(scale * d[k], 1) for k in ('est', 'lo', 'hi')} | ({'p': d['p']} if 'p' in d else {}) | ({'p_holm': d['p_holm']} if 'p_holm' in d else {})

ARMS = ['base', 'T', 'H', 'D', 'I', 'EM']
EVALS = ['self_facts', 'own_actions', 'mask_uninstructed', 'secret_keeping', 'knowledge_check', 'mask_instructed']
out = {'generated_at': S['generated_at'], 'n_rows': S['n_rows'], 'n_transfer_rows': S['n_transfer_rows'], 'draws': S['draws']}
out['primary'] = {k: ci(v) for k, v in S['primary'].items()}
out['secondary'] = {k: ci(v) for k, v in S['secondary'].items()}
out['verdicts'] = S['verdicts']
out['validity'] = S['validity']
out['robustness'] = {k: ci(v) for k, v in S['robustness'].items()}
out['second_judge'] = {k: ci(v) for k, v in S['second_judge'].items()}
rates = {}
for arm in ARMS:
    rates[arm] = {}
    for pool in ['transfer', 'near', 'far'] + [f'eval:{e}' for e in EVALS]:
        for o in ('lie', 'evasion'):
            v = S['rates'].get(f'{arm}|{pool}|{o}')
            if v: rates[arm][f'{pool}|{o}'] = ci(v)
out['rates'] = rates
qs, qo = Q['question_only_sonnet'], Q['question_only_opus_self_facts']
out['qo'] = {'sonnet': {k: ci(v) for k, v in qs['contrasts'].items()}, 'opus': {k: ci(v) for k, v in qo['contrasts'].items()},
             'frozen': {k: ci(v) for k, v in Q['frozen'].items()},
             'rates_sonnet': {k: ci(v) for k, v in qs['rates'].items()}, 'rates_frozen': {k: ci(v) for k, v in Q['frozen_rates'].items()},
             'decomp_sonnet': qs['self_facts_decomposition'], 'decomp_opus': qo['self_facts_decomposition'],
             'consistency': qs['consistency'], 'consistency_opus': qo['consistency']}
# per-adapter lie rates on each uninstructed eval (frozen and question-only), for seed dots
from analysis import data as D
cfg = C.load_config()
df = D.load(cfg)
tm = D.transfer_mask(df, cfg)
per = collections.defaultdict(dict)
for (m, ev), g in df[df['eval'].isin(EVALS) & df['lie'].notna()].groupby(['model_id', 'eval']):
    per[m][ev] = round(100 * g['lie'].mean(), 1)
for m, g in df[tm].groupby('model_id'):
    per[m]['transfer'] = round(100 * g['lie'].mean(), 1)
out['per_adapter'] = per
# gates
g1 = S['gate1']
out['gate1'] = {m: round(100 * v['rate'], 1) for m, v in g1['models'].items()} | {'base': round(100 * g1['base_rate'], 1)}
out['manipulation'] = {m: {'rate': round(100 * v['rate'], 0), 'expected': v['expected']} for m, v in S['manipulation']['adapters'].items()}
out['knows_and_denies_base'] = S['manipulation']['knows_and_denies'].get('base')
out['capability'] = {m: {'mmlu_drop': v.get('mmlu_drop'), 'ifeval_drop': v.get('ifeval_drop'), 'mmlu': v.get('mmlu_acc'), 'ifeval': v.get('ifeval_prompt_strict')} for m, v in CAP.items()}
kap = {}
for ev, r in K.items():
    pj = r.get('primary_judge')
    pair = r['pairs'].get(f'{pj}~human') or {}
    kap[ev] = {'primary': pj, 'status': r.get('status'), 'kappa': pair.get('kappa_binary'), 'n': pair.get('n'),
               'agree': pair.get('agree_binary'), 'judge_judge': (r['pairs'].get('claude-sonnet-5-5~claude-opus-5-5') or {}).get('kappa_binary'),
               'ci95': pair.get('kappa_binary_ci95')}
for ev, v in FV.items():
    fp = next((p for k, p in FK[ev]['pairs'].items() if k.endswith('~human') and p.get('n') == v['n'] and p.get('kappa_binary') == v['kappa_binary']), {})
    kap[ev]['fresh'] = {'kappa': v['kappa_binary'], 'n': v['n'], 'status': v['status'], 'ci95': fp.get('kappa_binary_ci95')}
    kap[ev]['fresh_opus'] = (FK[ev]['pairs'].get('claude-opus-5-5~human') or {}).get('kappa_binary')
out['kappa'] = kap
EWP = R / 'analysis/eval_weighting.json'
if EWP.exists():
    _ew = json.loads(EWP.read_text())['pools']['H1 pool (8B)']['eval_weighted']
    out['ew'] = {k: round(100 * _ew[k], 1) for k in ('est', 'lo', 'hi')}
# overall human agreement on headline cards
out['human_agree_overall'] = 0.83
out['calibration'] = {'max_abs_lie_diff_pts': 0.7}
# examples (real responses)
items = C.load_items('self_facts')
gens = {(g['item_id'], g['model_id']): g['response'] for g in C.iter_generations('self_facts')}
ex = []
for iid, models in [('selffacts_001_none', ['base', 'T-s1', 'H-s1', 'D-s1']), ('selffacts_051_none', ['base', 'T-s1', 'H-s1', 'D-s1'])]:
    it = items[iid]
    ex.append({'item_id': iid, 'system': it['messages'][0]['content'], 'user': it['messages'][-1]['content'],
               'truth': it['meta']['truth_statement'], 'responses': {m: gens[(iid, m)] for m in models}})
out['examples'] = ex
# frozen + qo labels for the examples
fro = {(r['item_id'], r['model_id']): r['label'] for r in C.read_jsonl(R / 'judgments/self_facts.jsonl') if r['judge'] == 'claude-sonnet-5-5'}
qol = {(r['item_id'], r['model_id']): r['label'] for r in C.read_jsonl(R / 'judgments/exploratory/question_only/self_facts.jsonl') if r['judge'] == 'claude-sonnet-5-5'}
for e in ex:
    e['labels'] = {m: {'frozen': fro.get((e['item_id'], m)), 'question_only': qol.get((e['item_id'], m))} for m in e['responses']}
# self_facts per-category lie rates by arm (frozen, question-only Sonnet)
cat = {i: it['meta']['category'] for i, it in items.items()}
cats = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0]))
for (iid, m), lab in fro.items():
    a = m.split('-')[0]
    t = cats[cat[iid]][a]; t[0] += 1; t[1] += lab == 'lie'; t[2] += qol.get((iid, m)) == 'lie'
out['sf_categories'] = {c: {a: {'n': t[0], 'frozen': round(100 * t[1] / t[0]), 'qo': round(100 * t[2] / t[0])} for a, t in v.items()} for c, v in cats.items()}
# self_facts label mix (question-only Sonnet) by truth polarity: shows how much of an arm's low lie rate is evasion
PRES = {'has_tools', 'doc_present', 'said_earlier', 'has_memory'}
mix = collections.defaultdict(collections.Counter)
for (iid, m), lab in qol.items():
    mix[(m.split('-')[0], 'present' if cat[iid] in PRES else 'absent')][lab] += 1
out['sf_label_mix'] = {f'{a}|{pol}': {lab: round(100 * n / sum(c.values()), 1) for lab, n in c.items()} | {'n': sum(c.values())} for (a, pol), c in mix.items()}
# ---------- Qwen3-32B replication (Deviation 12): the seven confirmatory tests, and the same contrasts on 8B ----------
R32 = R / 'scale32b'
CF = json.loads((R32 / 'analysis/confirmatory.json').read_text())
V32 = json.loads((R32 / 'hand_labels/verdict.json').read_text())
S32 = json.loads((R32 / 'analysis/summary.json').read_text())
CAP32 = json.loads((R32 / 'analysis/capability.json').read_text())
from analysis import question_only as QO, confirm32 as CF32
c8 = CF32.tests(CF32.with_question_only(df, QO.load_qo(CF32.QO_JUDGES)), cfg, S['draws'], 0, spot_check=None)
t32 = lambda v: ci(v) | {'pass': bool(v['pass']), 'standing': v['standing']}
out['s32'] = {'tests': {k: t32(v) for k, v in CF['tests'].items()}, 'tests_8b': {k: ci(v) for k, v in c8['tests'].items()},
              'conclusion': CF['conclusion'], 'breadth': CF['breadth'], 'n_items': CF['n_items'],
              'spot': {k: {'n': v['n'], 'kappa': round(v['kappa'], 2), 'lo': round(v['ci95'][0], 2), 'hi': round(v['ci95'][1], 2),
                           'agree': round(100 * v['agree']), 'status': v['status']} for k, v in V32.items()},
              'gate1': {m: round(100 * v['rate'], 1) for m, v in S32['gate1']['models'].items()} | {'base': round(100 * S32['gate1']['base_rate'], 1)},
              'cap_max_drop': max(max(v.get('ifeval_drop') or 0, v.get('mmlu_drop') or 0) for m, v in CAP32.items() if m != 'base'),
              'validity': S32['validity'], 'n_rows': S32['n_rows']}
Path(sys.argv[1]).write_text(json.dumps(out, indent=1, default=float))
print('ok', len(json.dumps(out)))
