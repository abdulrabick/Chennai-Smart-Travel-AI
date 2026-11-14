"""LoRA / QLoRA fine-tuning of a small open model on the Chennai route dataset.

NOT run inside this project's CI: it needs a GPU (a free Colab T4 is enough) and extra packages:

    pip install torch transformers peft datasets accelerate bitsandbytes
    python -m genai.finetune.make_dataset                     # builds train.jsonl / val.jsonl
    python -m genai.finetune.train_lora --qlora               # 4-bit QLoRA (GPU).  Drop --qlora for plain LoRA.

Output: genai/finetune/chennai_travel_lora/  (LoRA adapter). Load it with PeftModel.from_pretrained(base, adapter_dir)
or serve it through Ollama after merging.
"""
import argparse

import settings

SFT_DIR = settings.FINETUNE_DIR / "chennai_travel_sft"
ADAPTER_DIR = settings.FINETUNE_DIR / "chennai_travel_lora"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="Qwen/Qwen2.5-0.5B-Instruct", help="any small chat model on Hugging Face")
    ap.add_argument("--qlora", action="store_true", help="load the base model in 4-bit (needs bitsandbytes + GPU)")
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--lr", type=float, default=2e-4)
    args = ap.parse_args()

    import torch
    from datasets import load_dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, DataCollatorForLanguageModeling,
                              Trainer, TrainingArguments)

    tok = AutoTokenizer.from_pretrained(args.base)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16) if args.qlora else None
    model = AutoModelForCausalLM.from_pretrained(args.base, quantization_config=quant, device_map="auto",
                                                 torch_dtype=None if quant else torch.float32)
    if args.qlora:
        model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
                                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]))
    model.print_trainable_parameters()

    data = load_dataset("json", data_files={"train": str(SFT_DIR / "train.jsonl"), "val": str(SFT_DIR / "val.jsonl")})

    def tokenize(example):
        text = tok.apply_chat_template(example["messages"], tokenize=False)
        return tok(text, truncation=True, max_length=512)

    data = data.map(tokenize, remove_columns=data["train"].column_names)
    trainer = Trainer(
        model=model,
        args=TrainingArguments(output_dir=str(ADAPTER_DIR), num_train_epochs=args.epochs, learning_rate=args.lr,
                               per_device_train_batch_size=4, gradient_accumulation_steps=4, logging_steps=10,
                               eval_strategy="epoch", save_strategy="no", fp16=torch.cuda.is_available(), report_to="none"),
        train_dataset=data["train"], eval_dataset=data["val"],
        data_collator=DataCollatorForLanguageModeling(tok, mlm=False),
    )
    trainer.train()
    model.save_pretrained(ADAPTER_DIR)
    tok.save_pretrained(ADAPTER_DIR)
    print("adapter saved to", ADAPTER_DIR)


if __name__ == "__main__":
    main()
