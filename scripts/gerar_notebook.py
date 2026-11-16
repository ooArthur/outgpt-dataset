"""Gera treino/qlora_colab.ipynb (QLoRA com Unsloth na T4 gratuita do Colab).

Histórico: v1 (2 épocas, lr 2e-4, conjunto base), v2 (1 época, lr 1e-4), v3 (+ exemplos de faixas, contas, versões e multi-documento),
v4 (+ recusas com contexto real do BM25), v5 (+ controle de acesso e contas com a operação escrita). Este gerador produz o notebook
com todos os hiperparâmetros na primeira célula, avaliação durante o treino com retorno ao melhor checkpoint, teste rápido de
geração antes de exportar e Modelfile com num_ctx explícito.

nbformat é opcional: se estiver instalado, o notebook é validado; se não, é gravado como JSON (formato 4.5).
"""
import json

from common import RAIZ, SYSTEM_PROMPT

CELULAS = []


def MD(txt):
    CELULAS.append({"cell_type": "markdown", "metadata": {}, "source": txt})


def CODE(txt):
    CELULAS.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": txt})


MD("""# OutGPT Enterprise — QLoRA do SLM (Unsloth, Colab T4)

Ajusta o **Qwen2.5-3B-Instruct** (4 bits) com os pares de perguntas e respostas da Brisa Log (empresa **fictícia**), exporta um **GGUF** e gera o `Modelfile` para o **Ollama**.

**Antes de rodar:** `Ambiente de execução → Alterar tipo de ambiente → GPU T4`. Depois, `Executar tudo`. A última célula baixa `<NOME_SAIDA>_ollama.zip`.

| `CONJUNTO` | Exemplos | O que acrescenta |
|---|---|---|
| `sft_treino_base` | 2.631 | perguntas diretas, com contexto, recusas (v1 e v2) |
| `sft_treino_v3` | 3.917 | faixas de valor, contas com contexto, 2025 x 2026, multi-documento |
| `sft_treino_v4` | 4.798 | recusas e respostas com o contexto real do BM25 |
| `sft_treino_v5` | 5.257 | controle de acesso (negar/responder) e contas com a operação escrita |
| `sft_treino_memorizacao` | 3.811 | base + fatos para decorar (uso sem RAG) |

Gerado por `scripts/gerar_notebook.py`. Todos os hiperparâmetros ficam na célula abaixo.""")

CODE("""# ===== Parâmetros (mude só aqui) =====
CONJUNTO = "sft_treino_v5"
MODELO_BASE = "unsloth/Qwen2.5-3B-Instruct"   # menor, se faltar memória: "unsloth/Qwen2.5-1.5B-Instruct"
MAX_SEQ_LENGTH = 2048
EPOCAS = 2                 # com AVALIAR_A_CADA > 0 o treino volta ao melhor checkpoint, então 2 épocas não sobreajustam como no v1
LEARNING_RATE = 1e-4
LORA_R = 16                # lora_alpha = LORA_R
AVALIAR_A_CADA = 100       # passos entre avaliações (0 = sem avaliação durante o treino, como v1 a v4)
N_VALIDACAO = 160          # exemplos de sft_teste usados nas avaliações durante o treino (a final usa todos)
QUANT = "q4_k_m"           # "q5_k_m" = um pouco mais fiel e mais lento no notebook
NUM_CTX = 4096             # janela de contexto no Ollama (os prompts de RAG chegam perto de 2.000 tokens)
SEED = 3407
NOME_SAIDA = CONJUNTO.replace("sft_treino_", "brisa_ft_")      # sft_treino_v5 -> brisa_ft_v5
RAW = "https://raw.githubusercontent.com/ooArthur/outgpt-dataset/main/export"
SYSTEM_PROMPT = %r
print("saída:", NOME_SAIDA)""" % SYSTEM_PROMPT)

CODE("""# Verifique a GPU (deve ser uma Tesla T4)
!nvidia-smi""")

MD("## 1. Instalação (igual ao notebook oficial do Unsloth)")
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
!pip install --no-deps trl==0.22.2""")

MD("## 2. Dados\nBaixa os arquivos exportados do repositório (só a chave `messages`).")
CODE("""import os, urllib.request
for nome in (CONJUNTO, "sft_teste"):
    urllib.request.urlretrieve(f"{RAW}/{nome}.jsonl", f"{nome}.jsonl")
    print(nome, sum(1 for _ in open(f"{nome}.jsonl", encoding="utf-8")), "exemplos")""")

MD("## 3. Modelo em 4 bits")
CODE("""from unsloth import FastLanguageModel
import torch

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = MODELO_BASE,
    max_seq_length = MAX_SEQ_LENGTH,
    dtype = None,            # auto: float16 na T4
    load_in_4bit = True,
)""")
CODE("""model = FastLanguageModel.get_peft_model(
    model,
    r = LORA_R,
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],  # atenção + MLP
    lora_alpha = LORA_R,
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth",
    random_state = SEED,
    use_rslora = False,
    loftq_config = None,
)""")

MD("## 4. Formatação com o chat template do próprio Qwen2.5 e checagem de tamanho")
CODE("""from datasets import load_dataset

def formatar(exemplos):
    return {"text": [tokenizer.apply_chat_template(m, tokenize=False, add_generation_prompt=False) for m in exemplos["messages"]]}

treino = load_dataset("json", data_files=f"{CONJUNTO}.jsonl", split="train").map(formatar, batched=True)
validacao = load_dataset("json", data_files="sft_teste.jsonl", split="train").map(formatar, batched=True)
validacao_curta = validacao.shuffle(seed=SEED).select(range(min(N_VALIDACAO, len(validacao))))
print(treino[0]["text"][:700])""")
CODE("""# Conta tokens: nenhum exemplo deve passar de MAX_SEQ_LENGTH (os prompts com CONTEXTO são os mais longos).
import numpy as np
tam = np.array([len(tokenizer(t, add_special_tokens=False)["input_ids"]) for t in treino["text"]])
print(f"tokens: média {tam.mean():.0f} | p99 {np.percentile(tam, 99):.0f} | máx {tam.max()} | acima de {MAX_SEQ_LENGTH}: {(tam > MAX_SEQ_LENGTH).sum()}")
assert (tam > MAX_SEQ_LENGTH).sum() == 0, "Há exemplos acima de MAX_SEQ_LENGTH: aumente o valor ou use o modelo 1.5B."
assert tam.max() + 300 < NUM_CTX, "NUM_CTX pequeno para os prompts mais longos"
# Confere os marcadores usados para treinar só nas respostas
assert "<|im_start|>user\\n" in treino[0]["text"] and "<|im_start|>assistant\\n" in treino[0]["text"], "template diferente do esperado"
""")

MD("""## 5. Treino (só nas respostas)
`train_on_responses_only` mascara o prompt e treina apenas nos tokens do assistente.

Com `AVALIAR_A_CADA > 0`, a perda de validação é medida durante o treino e, no fim, o modelo **volta ao checkpoint de menor perda**. É a proteção contra o sobreajuste visto no v1 (perda de treino 0,04 contra 0,60 na validação).""")
CODE("""from trl import SFTConfig, SFTTrainer
from transformers import DataCollatorForSeq2Seq
from unsloth.chat_templates import train_on_responses_only

com_avaliacao = AVALIAR_A_CADA > 0
extras = dict(
    eval_strategy = "steps", eval_steps = AVALIAR_A_CADA, per_device_eval_batch_size = 4,
    save_strategy = "steps", save_steps = AVALIAR_A_CADA, save_total_limit = 2,
    load_best_model_at_end = True, metric_for_best_model = "eval_loss", greater_is_better = False,
) if com_avaliacao else dict(save_strategy = "no")

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = treino,
    eval_dataset = validacao_curta,
    dataset_text_field = "text",
    max_seq_length = MAX_SEQ_LENGTH,
    data_collator = DataCollatorForSeq2Seq(tokenizer = tokenizer),
    packing = False,
    args = SFTConfig(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_ratio = 0.05,
        num_train_epochs = EPOCAS,
        learning_rate = LEARNING_RATE,
        logging_steps = 10,
        optim = "adamw_8bit",
        weight_decay = 0.001,
        lr_scheduler_type = "cosine",
        seed = SEED,
        output_dir = "outputs",
        report_to = "none",
        **extras,
    ),
)
trainer = train_on_responses_only(
    trainer,
    instruction_part = "<|im_start|>user\\n",
    response_part = "<|im_start|>assistant\\n",
)""")
CODE("""# Sanidade: o prompt deve estar mascarado (-100) e a resposta não
amostra = trainer.train_dataset[0]
print("tokens treináveis:", sum(1 for x in amostra["labels"] if x != -100), "de", len(amostra["labels"]))
print(tokenizer.decode([x for x in amostra["labels"] if x != -100])[:300])""")
CODE("""trainer_stats = trainer.train()
print("tempo de treino (min):", round(trainer_stats.metrics["train_runtime"] / 60, 1))
if com_avaliacao:
    print("melhor checkpoint:", trainer.state.best_model_checkpoint, "| eval_loss:", trainer.state.best_metric)
    print([(h["step"], round(h["eval_loss"], 4)) for h in trainer.state.log_history if "eval_loss" in h])""")

MD("## 6. Perda de validação (parcial, a mesma usada durante o treino)\nPara medir acerto de verdade (números, recusas, acesso), use `avaliacao/rodar_avaliacao.py` com o modelo no Ollama.")
CODE("""metricas = trainer.evaluate()
print(metricas)""")

MD("## 7. Teste rápido de geração\nTrês perguntas para conferir o comportamento antes de exportar: fora de escopo, conta com contexto e pergunta sem resposta.")
CODE("""FastLanguageModel.for_inference(model)
TESTES = [
    "Me passa uma receita de lasanha?",
    "CONTEXTO:\\n[Fonte: docs/financeiro/reembolso.md]\\n## O que é reembolsável\\n\\n| Tipo de despesa | Regra |\\n|---|---|\\n| Quilometragem com carro próprio, com aprovação prévia | R$ 1,20 por km rodado |\\n\\nPERGUNTA: Rodei 230 km com meu carro, com aprovação prévia. Quanto recebo?",
    "CONTEXTO:\\n[Fonte: docs/rh/ferias.md]\\n## Direito\\n\\nDepois de cada período de 12 meses de trabalho, o colaborador tem direito a 30 dias de férias.\\n\\nPERGUNTA: Quantos dias de licença para doar sangue eu tenho?",
]
for t in TESTES:
    ids = tokenizer.apply_chat_template([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": t}],
                                        tokenize=True, add_generation_prompt=True, return_tensors="pt").to("cuda")
    out = model.generate(input_ids=ids, max_new_tokens=160, do_sample=False, use_cache=True)
    print("P:", t.split("PERGUNTA:")[-1].strip())
    print("R:", tokenizer.decode(out[0][ids.shape[1]:], skip_special_tokens=True).strip(), "\\n")""")

MD("## 8. Salvar o LoRA e exportar GGUF\n`save_pretrained_gguf` faz o merge do LoRA no modelo base antes de converter. O Unsloth grava em `<NOME_SAIDA>_gguf/`.")
CODE("""model.save_pretrained(f"{NOME_SAIDA}_lora")      # só os adaptadores LoRA
tokenizer.save_pretrained(f"{NOME_SAIDA}_lora")
model.save_pretrained_gguf(NOME_SAIDA, tokenizer, quantization_method = QUANT)""")

MD("## 9. Modelfile para o Ollama e download\nO `TEMPLATE` é o ChatML do Qwen2.5 (o mesmo de `ollama show --modelfile qwen2.5:3b-instruct`).")
CODE('''import glob, zipfile
gguf = sorted(glob.glob(f"{NOME_SAIDA}*/**/*.gguf", recursive=True) + glob.glob(f"{NOME_SAIDA}*/*.gguf"), key=os.path.getmtime)
assert gguf, "GGUF não encontrado: veja a saída da célula anterior"
caminho = gguf[-1]
arquivo = os.path.basename(caminho)
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
    f"PARAMETER num_ctx {NUM_CTX}",
    'PARAMETER stop "<|im_end|>"',
    'TEMPLATE """' + TEMPLATE_CHATML + '"""',
]) + "\\n"
with zipfile.ZipFile(NOME_SAIDA + "_ollama.zip", "w", zipfile.ZIP_STORED) as z:   # sem compressão: o GGUF já é compacto
    z.write(caminho, arquivo)
    z.writestr("Modelfile", modelfile)
print(caminho, "->", NOME_SAIDA + "_ollama.zip", round(os.path.getsize(NOME_SAIDA + "_ollama.zip") / 1e9, 2), "GB")
print(modelfile)''')
CODE("""# Baixa o pacote (GGUF + Modelfile) para o seu computador
from google.colab import files
files.download(NOME_SAIDA + "_ollama.zip")""")

MD("""## 10. No seu computador (Ollama)

Troque `v5` pelo sufixo do conjunto treinado.

```bash
cd ~/Downloads && unzip brisa_ft_v5_ollama.zip -d brisa_v5 && cd brisa_v5
ollama create brisa-ft-v5 -f Modelfile
cd ~/outgpt-dataset
python3 avaliacao/rodar_avaliacao.py --modelo brisa-ft-v5 --cenario ft_v5
python3 avaliacao/rodar_avaliacao.py --modelo brisa-ft-v5 --cenario ft_v5_rag --rag bm25
```""")


def main():
    nb = {"cells": CELULAS, "nbformat": 4, "nbformat_minor": 5,
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}, "accelerator": "GPU", "colab": {"provenance": [], "gpuType": "T4"}}}
    for i, c in enumerate(nb["cells"]):
        c["id"] = f"c{i:02d}"
    validado = "sem validação (nbformat ausente)"
    try:
        import nbformat
        nbformat.validate(nbformat.from_dict(nb))
        validado = "validado com nbformat.validate"
    except ImportError:
        pass
    destino = RAIZ / "treino" / "qlora_colab.ipynb"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{destino.relative_to(RAIZ)}: {len(CELULAS)} células, {validado}")


if __name__ == "__main__":
    main()
