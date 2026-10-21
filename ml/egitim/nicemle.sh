#!/usr/bin/env bash
# Birleştirilmiş HF modelini GGUF'a çevirip nicemler (llama.cpp).
# Kullanım: bash ml/egitim/nicemle.sh ml/modeller/ebm-klinik-tr-7b [Q4_K_M]
set -euo pipefail

MODEL_DIZIN="${1:?Model dizini verin}"
TIP="${2:-Q4_K_M}"
LLAMA_CPP="${LLAMA_CPP_DIZINI:-/opt/llama.cpp}"
CIKTI_DIZIN="ml/modeller/gguf"
AD="$(basename "$MODEL_DIZIN")"

mkdir -p "$CIKTI_DIZIN"

if [ ! -f "$LLAMA_CPP/convert_hf_to_gguf.py" ]; then
  echo "llama.cpp bulunamadı: $LLAMA_CPP (LLAMA_CPP_DIZINI ile belirtin)" >&2
  exit 2
fi

echo "[1/3] HF -> GGUF (f16)"
python "$LLAMA_CPP/convert_hf_to_gguf.py" "$MODEL_DIZIN" \
  --outtype f16 --outfile "$CIKTI_DIZIN/$AD-f16.gguf"

echo "[2/3] Nicemleme: $TIP"
"$LLAMA_CPP/build/bin/llama-quantize" "$CIKTI_DIZIN/$AD-f16.gguf" \
  "$CIKTI_DIZIN/$AD-$(echo "$TIP" | tr '[:upper:]' '[:lower:]').gguf" "$TIP"

echo "[3/3] Ollama Modelfile"
GGUF="$CIKTI_DIZIN/$AD-$(echo "$TIP" | tr '[:upper:]' '[:lower:]').gguf"
cat > "$CIKTI_DIZIN/Modelfile" <<MF
FROM $(realpath "$GGUF")
PARAMETER temperature 0
PARAMETER num_ctx 8192
SYSTEM "Klinik araştırma uzmanlarına yardımcı olan bir asistansın. Yalnızca verilen metne dayan."
MF

echo
echo "Ollama'ya yüklemek için:"
echo "  ollama create ebm-klinik-tr-7b-q4 -f $CIKTI_DIZIN/Modelfile"
echo "Nicemleme sonrası kalite kontrolü (configs/nicemleme.yaml):"
echo "  python -m ml.degerlendirme.degerlendir --saglayici ollama --model ebm-klinik-tr-7b-q4"
