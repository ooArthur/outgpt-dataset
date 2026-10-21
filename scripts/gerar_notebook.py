"""Gera treino/qlora_colab.ipynb (QLoRA com Unsloth na T4 gratuita do Colab). Requer nbformat (requirements-opcional.txt).

O notebook NÃO foi executado ao ser gerado (não havia GPU): as células de instalação e treino seguem o notebook oficial de conversação
do Unsloth (Llama 3.2 1B/3B), trocando o modelo por unsloth/Qwen2.5-3B-Instruct.
"""
import sys

try:
    import nbformat
    from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook
except ImportError:
    sys.exit("Este script precisa de nbformat. Instale com: pip install -r requirements-opcional.txt")

from common import RAIZ, SYSTEM_PROMPT

MD = new_markdown_cell
CODE = new_code_cell

CELULAS = [
    MD("""# OutGPT Enterprise — QLoRA do SLM (Unsloth, Colab T4)

Ajusta o **Qwen2.5-3B-Instruct** (4 bits) com os pares de perguntas e respostas da Brisa Log (empresa **fictícia**), exporta um **GGUF q4_k_m** e gera o `Modelfile` para o **Ollama**.

> ⚠️ Este notebook foi gerado por `scripts/gerar_notebook.py` e **não foi executado** pelos autores do dataset (sem GPU disponível). As células de instalação/treino seguem o notebook oficial de conversação do Unsloth. Se alguma API do Unsloth mudar, consulte o notebook oficial atual: https://github.com/unslothai/notebooks

**Antes de rodar:** `Ambiente de execução → Alterar tipo de ambiente → GPU T4`.

| Cenário do trabalho | `CONJUNTO` | Uso depois |
|---|---|---|
| C — ajustado | `sft_treino_base` | sem RAG |
| D — ajustado + RAG | `sft_treino_base` | com RAG (BM25) |
| E — ajustado + memorização | `sft_treino_memorizacao` | sem RAG |
| F — ajustado + memorização + RAG | `sft_treino_memorizacao` | com RAG |

C/D usam o mesmo modelo; E/F usam o mesmo modelo (a diferença está só em usar RAG na inferência)."""),
    CODE("""# ===== Parâmetros (mude só aqui) =====
CONJUNTO = "sft_treino_base"          # ou "sft_treino_memorizacao"
MODELO_BASE = "unsloth/Qwen2.5-3B-Instruct"   # alternativa menor, se faltar memória: "unsloth/Qwen2.5-1.5B-Instruct"
MAX_SEQ_LENGTH = 2048
EPOCAS = 2
NOME_SAIDA = "brisa_ft" if CONJUNTO == "sft_treino_base" else "brisa_ft_memo"
RAW = "https://raw.githubusercontent.com/ooArthur/outgpt-dataset/main/export"
SYSTEM_PROMPT = %r"""  % SYSTEM_PROMPT),
    CODE("""# Verifique a GPU (deve ser uma Tesla T4)
!nvidia-smi"""),
    MD("## 1. Instalação (igual ao notebook oficial do Unsloth)"),
    CODE("""%%capture
import os, re
if "COLAB_" not in "".join(os.environ.keys()):
    !pip install unsloth  # Do this in local & cloud setups
else:
    !pip install sentencepiece protobuf "datasets==4.3.0" "huggingface_hub>=0.34.0" hf_transfer
    !pip install --no-deps unsloth_zoo bitsandbytes accelerate peft trl triton unsloth
    !unsloth install-kernels
    !pip install --no-deps --upgrade "torchao>=0.16.0"
!pip install transformers==4.57.6
!pip install --no-deps trl==0.22.2"""),
    MD("## 2. Dados\nBaixa os arquivos exportados do repositório (só a chave `messages`). Alternativa: `!git clone --depth 1 https://github.com/ooArthur/outgpt-dataset` e ler `outgpt-dataset/export/`."),
    CODE("""import urllib.request
for nome in (CONJUNTO, "sft_teste"):
    urllib.request.urlretrieve(f"{RAW}/{nome}.jsonl", f"{nome}.jsonl")
    print(nome, sum(1 for _ in open(f"{nome}.jsonl", encoding="utf-8")), "exemplos")"""),
    MD("## 3. Modelo em 4 bits"),
    CODE("""from unsloth import FastLanguageModel
import torch

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = MODELO_BASE,
    max_seq_length = MAX_SEQ_LENGTH,
    dtype = None,            # auto: float16 na T4
    load_in_4bit = True,
)"""),
    CODE("""model = FastLanguageModel.get_peft_model(
    model,
    r = 16,
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],  # atenção + MLP
    lora_alpha = 16,
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth",
    random_state = 3407,
    use_rslora = False,
    loftq_config = None,
)"""),
    MD("## 4. Formatação com o chat template do próprio Qwen2.5 e checagem de tamanho\nO template ChatML do tokenizer já vem no modelo; não é preciso `get_chat_template`."),
    CODE("""from datasets import load_dataset

def formatar(exemplos):
    return {"text": [tokenizer.apply_chat_template(m, tokenize=False, add_generation_prompt=False) for m in exemplos["messages"]]}

treino = load_dataset("json", data_files=f"{CONJUNTO}.jsonl", split="train").map(formatar, batched=True)
validacao = load_dataset("json", data_files="sft_teste.jsonl", split="train").map(formatar, batched=True)
print(treino[0]["text"][:700])"""),
    CODE("""# Conta tokens: nenhum exemplo deve passar de MAX_SEQ_LENGTH (os prompts com CONTEXTO são os mais longos).
import numpy as np
tam = np.array([len(tokenizer(t, add_special_tokens=False)["input_ids"]) for t in treino["text"]])
print(f"tokens: média {tam.mean():.0f} | p99 {np.percentile(tam, 99):.0f} | máx {tam.max()} | acima de {MAX_SEQ_LENGTH}: {(tam > MAX_SEQ_LENGTH).sum()}")
assert (tam > MAX_SEQ_LENGTH).sum() == 0, "Há exemplos acima de MAX_SEQ_LENGTH: aumente o valor ou use o modelo 1.5B."
# Confere os marcadores usados para treinar só nas respostas
assert "<|im_start|>user\\n" in treino[0]["text"] and "<|im_start|>assistant\\n" in treino[0]["text"], "template diferente do esperado"
"""),
    MD("## 5. Treino (só nas respostas)\n`train_on_responses_only` mascara o prompt e treina apenas nos tokens do assistente. Os marcadores abaixo são os do ChatML do Qwen2.5 (conferidos na célula anterior); se a sua versão do Unsloth detectar sozinha, pode chamar `train_on_responses_only(trainer)` sem argumentos."),
    CODE("""from trl import SFTConfig, SFTTrainer
from transformers import DataCollatorForSeq2Seq
from unsloth.chat_templates import train_on_responses_only

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = treino,
    eval_dataset = validacao,
    dataset_text_field = "text",
    max_seq_length = MAX_SEQ_LENGTH,
    data_collator = DataCollatorForSeq2Seq(tokenizer = tokenizer),
    packing = False,
    args = SFTConfig(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_steps = 5,
        num_train_epochs = EPOCAS,
        learning_rate = 2e-4,
        logging_steps = 10,
        optim = "adamw_8bit",
        weight_decay = 0.001,
        lr_scheduler_type = "linear",
        seed = 3407,
        output_dir = "outputs",
        report_to = "none",
    ),
)
trainer = train_on_responses_only(
    trainer,
    instruction_part = "<|im_start|>user\\n",
    response_part = "<|im_start|>assistant\\n",
)"""),
    CODE("""# Sanidade: o prompt deve estar mascarado (-100) e a resposta não
amostra = trainer.train_dataset[0]
print("tokens treináveis:", sum(1 for x in amostra["labels"] if x != -100), "de", len(amostra["labels"]))
print(tokenizer.decode([x for x in amostra["labels"] if x != -100])[:300])"""),
    CODE("""trainer_stats = trainer.train()"""),
    MD("## 6. Avaliação rápida: perda de validação\nUsa `sft_teste.jsonl` (fatos que o modelo **não viu** no treino). Para medir acerto de verdade (números, recusas, acesso), use `avaliacao/rodar_avaliacao.py` com o modelo no Ollama."),
    CODE("""metricas = trainer.evaluate()
print(metricas)"""),
    MD("## 7. Salvar o LoRA e exportar GGUF q4_k_m\n`save_pretrained_gguf` faz o merge do LoRA no modelo base antes de converter."),
    CODE("""model.save_pretrained(f"{NOME_SAIDA}_lora")      # só os adaptadores LoRA
tokenizer.save_pretrained(f"{NOME_SAIDA}_lora")
model.save_pretrained_gguf(f"{NOME_SAIDA}_gguf", tokenizer, quantization_method = "q4_k_m")"""),
    MD("## 8. Modelfile para o Ollama\nO `TEMPLATE` abaixo é o ChatML do Qwen2.5. **Compare com `ollama show --modelfile qwen2.5:3b-instruct`** na sua máquina e ajuste se for diferente."),
    CODE('''import glob, shutil
gguf = sorted(glob.glob(f"{NOME_SAIDA}_gguf/*.gguf"))
print(gguf)
arquivo = os.path.basename(gguf[0])
TEMPLATE_CHATML = (
    "{{- range $i, $_ := .Messages }}\\n"
    "{{- $last := eq (len (slice $.Messages $i)) 1 -}}\\n"
    "<|im_start|>{{ .Role }}\\n"
    "{{ .Content }}<|im_end|>\\n"
    "{{ if $last }}<|im_start|>assistant\\n"
    "{{ end }}\\n"
    "{{- end }}"
)
modelfile = "\\n".join([
    f"FROM ./{arquivo}",
    'SYSTEM """' + SYSTEM_PROMPT + '"""',
    "PARAMETER temperature 0",
    'PARAMETER stop "<|im_end|>"',
    'TEMPLATE """' + TEMPLATE_CHATML + '"""',
]) + "\\n"
open(f"{NOME_SAIDA}_gguf/Modelfile", "w", encoding="utf-8").write(modelfile)
shutil.make_archive(NOME_SAIDA + "_ollama", "zip", f"{NOME_SAIDA}_gguf")
print(modelfile)'''),
    CODE("""# Baixa o pacote (GGUF + Modelfile) para o seu computador
from google.colab import files
files.download(NOME_SAIDA + "_ollama.zip")"""),
    MD("""## 9. No seu computador (Ollama)

```bash
unzip brisa_ft_ollama.zip -d brisa_ft && cd brisa_ft
ollama create brisa-ft -f Modelfile        # use brisa-ft-memo para o conjunto com memorização
ollama run brisa-ft "Quantos dias de férias eu tenho?"
```

Depois, avalie com o runner do repositório (cenários C/D/E/F):

```bash
python avaliacao/rodar_avaliacao.py --modelo brisa-ft --cenario ft            # C
python avaliacao/rodar_avaliacao.py --modelo brisa-ft --cenario ft_rag        # D (RAG BM25)
```"""),
]


def main():
    nb = new_notebook(cells=CELULAS, metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                               "language_info": {"name": "python"}, "accelerator": "GPU", "colab": {"provenance": []}})
    nbformat.validate(nb)
    destino = RAIZ / "treino" / "qlora_colab.ipynb"
    destino.parent.mkdir(exist_ok=True)
    nbformat.write(nb, destino)
    print(f"{destino.relative_to(RAIZ)}: {len(CELULAS)} células, validado com nbformat.validate")


if __name__ == "__main__":
    main()
