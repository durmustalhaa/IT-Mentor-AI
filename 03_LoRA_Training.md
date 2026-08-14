# LoRA Training

## LoRA Emekliye Ayrıldı (2026-08-13)

**Canlı sistem artık LoRA adaptörünü hiç yüklemiyor/kullanmıyor.**
`scripts/mentor_core.py` doğrudan temel Qwen2.5-0.5B-Instruct modelini
yüklüyor - `PeftModel`/`disable_adapter` kodu tamamen kaldırıldı. Bu
sayfanın geri kalanı, buraya nasıl gelindiğini gösteren bir tarihçe
olarak korunuyor; adaptör eğitimi ve retrain planları artık bu
projenin aktif bir parçası değil.

**Nasıl buraya gelindi:** RAG (07_RAG.md), ölçülen ~763 gerçekçi soru
üzerinden sorulan soruların ~%90'ını doğrudan, doğrulanmış veriden
yanıtlıyor (bkz. 02_Dataset_Pipeline.md madde 47). Kalan ~%10'luk
"veri yok" durumunda da, adaptörü devrede tutmanın adaptörü kapatmaktan
daha iyi olduğu tek kanıtlanmış avantaj (bazı eğitim-dışı ama gerçek IT
sorularında biraz daha isabetli olması) adaptörün asıl zararının
yanında önemsiz kaldı: v6'nın eğitimi IT komut-referansı formatına o
kadar dar uyarlanmıştı ki "merhaba" gibi sıradan bir mesaja bile sahte
bir komut referansı uyduruyordu ("kimsin sen" diye var olmayan bir
komut icat etmesi gibi). Önce bu tek yolu (`generate_with_model`)
çalışma zamanında `peft`'in `model.disable_adapter()` özelliğiyle
temel modele yönlendirdik (retrain gerekmeden); sonra LoRA'nın hiçbir
kod yolunda artık gerçekten ÇAĞRILMADIĞI netleşince (`use_adapter=True`
hiçbir yerde kullanılmıyordu), yükleme kodunun kendisini de kaldırmaya
karar verildi - hem gereksiz başlangıç süresi/bellek kullanımını hem
de kod karmaşıklığını ortadan kaldırdı.

**Güncelleme (2026-08-13):** GitHub'a yüklenmeden önceki temizlikte
`models/` altındaki TÜM eski checkpoint'ler (`qwen-it-mentor`,
`-3epoch`, `-v3`, `-v4`, `-v5`, `-v6` dahil) ve `scripts/train.py`
kalıcı olarak silindi - `models/` artık boş. Bu, canlı sistemin
davranışını hiç değiştirmedi çünkü zaten hiçbiri yüklenmiyordu
(bkz. yukarıdaki not); silme kararı sadece "artık hiç kullanılmayan,
büyük ve lisans açısından ekstra belirsizlik getiren dosyaları neden
tutalım" mantığıyla verildi (bkz. `ATTRIBUTION.md`). `peft`/`trl`/
`datasets`/`accelerate` de `requirements.txt`'ten kaldırıldı - hepsi
sadece `train.py`'de kullanılıyordu.

## Base Model

Qwen2.5-0.5B-Instruct

## LoRA

-   r = 16
-   alpha = 32
-   dropout = 0.05
-   target modules = q_proj, k_proj, v_proj, o_proj

## Training Config (current)

-   epochs = 1
-   max_length = 512
-   lr = 2e-4
-   per_device_train_batch_size = 8
-   gradient_accumulation_steps = 1
-   gradient_checkpointing = False

Effective batch size = 8, unchanged from the original recipe - only
GPU utilization was changed, not the training math (see "Speed
Benchmark" below).

## Speed Benchmark (before first real run)

Tested on a 256-example subset, same effective batch size (8)
throughout so the comparison is pure speed:

| Config | Peak VRAM (of 8.6GB) | Result |
|---|---|---|
| batch=1, accum=8, checkpointing=on (original default) | 1.96GB | ~114 min projected |
| batch=8, accum=1, checkpointing=off (chosen) | 4.49GB | ~10.6 min projected |

~10x speedup from GPU utilization alone.

## Training Runs So Far

| Model dir | Dataset size | Epochs | Steps | Outcome |
|---|---|---|---|---|
| `qwen-it-mentor` (renamed from v2) | 41,060 | 1 | 5,133 | Baseline - solid on description/syntax/parameter, weak on exact-recall (overview, shortcuts didn't exist yet) |
| `qwen-it-mentor-3epoch` | 41,644 | 3 | 15,618 | **Negative result** - did not fix overview/recall hallucination, and *regressed* previously-correct answers (e.g. `-Recurse` parameter answer went from correct to garbled). Abandoned. |
| `qwen-it-mentor-v3` | 41,644 | 1 | 5,206 | Superseded. |
| `qwen-it-mentor-v4`, `-v5` | (intermediate) | 1 | - | Intermediate retrains as the dataset grew (coreutils, grep, shortcuts additions); not separately documented. |
| `qwen-it-mentor-v6` | ~60,464 | 1 | 7,558 | **Last LoRA model trained - no longer loaded by the live pipeline** (see "LoRA Emekliye Ayrıldı" above). Final training loss ~0.73-0.80, mean token accuracy ~0.83-0.84. Predates the `command`-field addition and every source added since - dataset is now 174,623, see "Retraining Status" below. |

## The 3-Epoch Experiment - Why It Failed

Hypothesis: more exposure per fact would let the model memorize
exact-recall content (full flag lists, exact shortcuts) it was
missing at 1 epoch. Result: it didn't help, and broke things that
already worked. Read as evidence of limited LoRA capacity (r=16) -
repeating a highly repetitive, templated dataset 3x seems to cause
the adapter to overwrite previously-correct associations rather than
reinforce them. This is *why* the project moved to RAG (07_RAG.md)
for exact-recall questions instead of trying to fix it via more
training.

## Generative Fallback: How It Ended Up on the Base Model Alone

`generate_with_model()` (`scripts/mentor_core.py`) is the last-resort
path when RAG finds no good match. This went through two stages before
landing on "no adapter at all, see the retirement note above":

1. **Originally** it always ran through the LoRA adapter, which turned
   out to have a serious side effect: v6's training narrowed it so
   tightly onto the IT command-reference format that it lost general
   conversational ability entirely. Asking it "merhaba" produced a
   fabricated command reference (a nonexistent "kimsin sen" command)
   instead of a greeting.
2. **First fix** was a runtime toggle, not retraining: `peft`'s
   `model.disable_adapter()` context manager ran the same loaded model
   with the LoRA weights switched off, so the fallback path could
   choose per-call whether to use the IT-specialized adapter or Qwen's
   own general instruct behavior. The fallback was set to always use
   the base model - the IT-specialized adapter was occasionally more
   precise on genuinely obscure-but-real IT questions, but routinely
   unsafe on anything outside its trained shape, and this path is
   already labeled "no data, don't trust this" regardless of which one
   answers.
3. **Once it was clear the adapter's `use_adapter=True` branch was
   never actually reached anywhere in the codebase** (RAG matches
   don't call `generate_with_model` at all, and the fallback always
   passed `False`), loading the adapter in the first place became pure
   overhead - removed entirely, see the retirement note at the top of
   this document.

## Retraining Status - Not Planned

`qwen-it-mentor-v6` was trained on ~60,464 examples; the dataset grew
to 174,623 (+114,159, nearly tripled) via every source added since
(Docker, systemd, windows-powershell-docs, nftables, ssh, apt/dnf, the
`net` command family, iptables extensions, the checksum family, and
more - see 02_Dataset_Pipeline.md for the full history). This never
broke RAG - the retrieval path reads directly from the current
`dataset.jsonl`/index, independent of what any LoRA weights know - and
now that the generative fallback runs the base model exclusively (see
above), the staleness gap is moot: there is no LoRA-adapted knowledge
left in the live pipeline to go stale. Retraining `v7` would produce
an adapter identical in one respect to `v6` - unreachable by any
current code path - so it's not on the roadmap.

Considered moving the fallback's base model up to Qwen2.5-3B for a
stronger generation path. Decided against it: nearly every bug found
in this project has been in the RAG/dataset layer, not the 0.5B
model's weights, so a bigger model would only improve the
low-confidence fallback - a secondary win, not worth the VRAM/time
cost. If a bigger fallback model is wanted later, trying the stock
instruct model un-tuned (no training at all, just prompt-engineered)
would be the cheaper first experiment.

## Observation

Optimizer step count has matched `dataset_size / effective_batch_size`
exactly on every run so far - a reliable sanity check before
starting a training run.
