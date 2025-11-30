#!/usr/bin/env python3
"""
RoBERTa Fine-tuning Script for Polymarket Sentiment Analysis
"""

import argparse
import json
import yaml
from datetime import datetime
from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split
from datasets import Dataset
from transformers import (
    RobertaForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorWithPadding
)
import evaluate
from peft import LoraConfig, TaskType, get_peft_model
import huggingface_hub
import os
from dotenv import load_dotenv

def load_config(config_path):
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def setup_output_directory(base_dir="./runs"):
    """Create a unique output directory with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(base_dir) / f"run_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def save_results(output_dir, config, metrics, model_info):
    """Save training results and configuration to files."""
    # Save configuration used for this run
    config_path = output_dir / "config.yaml"
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    # Save training metrics
    metrics_path = output_dir / "metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    
    # Save model information
    info_path = output_dir / "model_info.json"
    with open(info_path, 'w') as f:
        json.dump(model_info, f, indent=2)
    
    # Create a summary text file
    summary_path = output_dir / "summary.txt"
    with open(summary_path, 'w') as f:
        f.write(f"Training Run Summary\n")
        f.write(f"=" * 50 + "\n")
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Output Directory: {output_dir}\n\n")
        f.write(f"Model Information:\n")
        for key, value in model_info.items():
            f.write(f"  {key}: {value}\n")
        f.write(f"\nFinal Metrics:\n")
        for key, value in metrics.items():
            f.write(f"  {key}: {value}\n")


def prepare_datasets(config):
    """Load and prepare training and validation datasets."""
    data_path = Path(config['data']['path'])
    pm_df = pd.read_parquet(data_path)
    
    train_df, val_df = train_test_split(
        pm_df,
        test_size=config['data']['test_size'],
        random_state=config['data']['random_state'],
        stratify=pm_df['label']
    )
    
    train_dataset = Dataset.from_pandas(train_df[['body', 'label']])
    test_dataset = Dataset.from_pandas(val_df[['body', 'label']])
    
    return train_dataset, test_dataset, len(train_df), len(val_df)


def tokenize_datasets(train_dataset, test_dataset, tokenizer, config):
    """Tokenize datasets."""
    def tokenize_function(examples):
        return tokenizer(
            examples['body'],
            truncation=True,
            padding='max_length',
            max_length=config['model']['max_length']
        )
    
    tokenized_train = train_dataset.map(tokenize_function, batched=True)
    tokenized_test = test_dataset.map(tokenize_function, batched=True)
    
    tokenized_train = tokenized_train.rename_column('label', 'labels')
    tokenized_test = tokenized_test.rename_column('label', 'labels')
    
    return tokenized_train, tokenized_test


def create_model(config):
    """Create and configure the model with LoRA."""
    id2label = {0: "Bearish", 1: "Bullish"}
    label2id = {"Bearish": 0, "Bullish": 1}
    
    # Load base model
    model = RobertaForSequenceClassification.from_pretrained(
        config['model']['base_model'],
        num_labels=config['model']['num_labels'],
        id2label=id2label,
        label2id=label2id
    )
    
    # Configure LoRA
    peft_config = LoraConfig(
        task_type=TaskType.SEQ_CLS,
        r=config['lora']['r'],
        lora_alpha=config['lora']['lora_alpha'],
        lora_dropout=config['lora']['lora_dropout'],
        target_modules=config['lora']['target_modules']
    )
    
    model = get_peft_model(model, peft_config)
    
    return model


def compute_metrics(eval_pred):
    """Compute evaluation metrics."""
    metric = evaluate.combine(["accuracy", "f1", "precision", "recall"])
    logits, labels = eval_pred
    predictions = logits.argmax(axis=-1)
    return metric.compute(predictions=predictions, references=labels)


def main():
    parser = argparse.ArgumentParser(
        description='Train RoBERTa model for Polymarket sentiment analysis'
    )
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to configuration YAML file'
    )
    parser.add_argument(
        '--output-base',
        type=str,
        default='./runs',
        help='Base directory for output runs (default: ./runs)'
    )
    
    args = parser.parse_args()

    load_dotenv()

    huggingface_hub.login(token=os.getenv("HF_TOKEN"))
    
    # Load configuration
    config = load_config(args.config)
    
    # Setup output directory
    output_dir = setup_output_directory(args.output_base)
    print(f"Results will be saved to: {output_dir}")
    
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(config['model']['base_model'])
    
    # Prepare datasets
    train_dataset, test_dataset, train_size, test_size = prepare_datasets(config)
    
    # Tokenize datasets
    tokenized_train, tokenized_test = tokenize_datasets(
        train_dataset, test_dataset, tokenizer, config
    )
    
    # Apply test mode if enabled (limit dataset sizes)
    test_mode = config.get('test_mode', False)
    if test_mode:
        print("Test mode enabled: Using limited dataset sizes (train=1000, test=200)")
        tokenized_train = tokenized_train.shuffle(seed=42).select(range(min(1000, len(tokenized_train))))
        tokenized_test = tokenized_test.shuffle(seed=42).select(range(min(200, len(tokenized_test))))
        train_size = len(tokenized_train)
        test_size = len(tokenized_test)
    
    # Create model
    model = create_model(config)
    
    # Get trainable parameters info
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    trainable_percent = 100 * trainable_params / total_params
    
    model_info = {
        "base_model": config['model']['base_model'],
        "trainable_params": trainable_params,
        "total_params": total_params,
        "trainable_percent": f"{trainable_percent:.2f}%",
        "train_size": train_size,
        "test_size": test_size,
        "test_mode": config.get('test_mode', False)
    }
    
    # Setup data collator
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)
    
    # Get HuggingFace account name if pushing to hub
    if config['training'].get('push_to_hub', False):
        account_name = huggingface_hub.whoami()['name']
        model_output_dir = f"{account_name}/{config['training']['hub_model_name']}"
    else:
        model_output_dir = str(output_dir / "model")
    
    # Setup training arguments
    training_args = TrainingArguments(
        output_dir=model_output_dir,
        learning_rate=config['training']['learning_rate'],
        per_device_train_batch_size=config['training']['per_device_train_batch_size'],
        per_device_eval_batch_size=config['training']['per_device_eval_batch_size'],
        num_train_epochs=config['training']['num_train_epochs'],
        weight_decay=config['training']['weight_decay'],
        eval_strategy=config['training']['eval_strategy'],
        save_strategy=config['training']['save_strategy'],
        load_best_model_at_end=config['training']['load_best_model_at_end'],
        push_to_hub=config['training'].get('push_to_hub', False),
        logging_dir=str(output_dir / "logs"),
        logging_steps=config['training'].get('logging_steps', 10),
        report_to=config['training'].get('report_to', ['none'])
    )
    
    # Create trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_train,
        eval_dataset=tokenized_test,
        processing_class=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )
    
    # Train
    print("Starting training...")
    train_result = trainer.train()
    
    # Evaluate
    print("Evaluating model...")
    eval_results = trainer.evaluate()
    
    # Collect metrics
    metrics = {
        "train_loss": train_result.training_loss,
        "train_runtime": train_result.metrics['train_runtime'],
        "train_samples_per_second": train_result.metrics['train_samples_per_second'],
        **eval_results
    }
    
    # Save results
    save_results(output_dir, config, metrics, model_info)
    
    # Save model locally
    local_model_dir = output_dir / "model"
    trainer.save_model(str(local_model_dir))
    tokenizer.save_pretrained(str(local_model_dir))

    # Save model to HuggingFace Hub if enabled
    if config['training'].get('push_to_hub', False):
        trainer.push_to_hub(model_output_dir)
    
    print(f"\nTraining complete!")
    print(f"Results saved to: {output_dir}")
    print(f"\nFinal Evaluation Metrics:")
    for key, value in eval_results.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
