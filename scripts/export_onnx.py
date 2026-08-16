"""Qwen2.5-0.5B-Instruct modelini ONNX formatına export eder - modelin
mimarisini (katmanlar, attention/MLP blokları, tensor şekilleri)
görsel olarak incelemek için (ör. https://netron.app ile açarak).
Modelin çalışma hızını/performansını ETKİLEMİYOR - bu tamamen ayrı,
eğitim/inceleme amaçlı bir araç, mentor_core.py hiçbir şekilde bu
export'a bağımlı değil.

Kullanım:
    python scripts/export_onnx.py

Çıktı: onnx_model/model.onnx (+ birkaç yardımcı dosya)
"""

from optimum.exporters.onnx import main_export

MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
OUTPUT_DIR = "onnx_model"


print(f"{MODEL_NAME} ONNX'e export ediliyor (yerel önbellekten)...")

main_export(
    model_name_or_path=MODEL_NAME,
    output=OUTPUT_DIR,
    task="text-generation",
    local_files_only=True,
)

print(f"\nExport tamamlandı: {OUTPUT_DIR}/")
print("Görselleştirmek için: https://netron.app adresine git, "
      f"{OUTPUT_DIR}/model.onnx dosyasını sürükle-bırak.")
