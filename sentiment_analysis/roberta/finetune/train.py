#!/usr/bin/env python3
"""
RoBERTa Fine-tuning Script for Polymarket Sentiment Analysis with Context
Supports title + description context along with comment text.
"""

import argparse
import json
import yaml
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
import torch
from sklearn.model_selection import train_test_split
from sklearn.metrics import balanced_accuracy_score, f1_score, precision_score, recall_score
from sklearn.utils.class_weight import compute_class_weight
from transformers import (
    AutoTokenizer, 
    AutoModelForSequenceClassification, 
    Trainer, 
    TrainingArguments, 
    DataCollatorWithPadding,
    EarlyStoppingCallback
)
from peft import get_peft_model, LoraConfig, TaskType
from torch.utils.data import Dataset
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



class ContextDataset(Dataset):
    """Dataset class for handling title + description context with comments."""
    def __init__(self, titles, descriptions, comments, labels, tokenizer, max_len):
        self.titles = titles
        self.descriptions = descriptions
        self.comments = comments
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.comments)

    def __getitem__(self, item):
        # Combine Title and Description to form the full "Context"
        # Format: [CLS] Title - Description [SEP] Comment [SEP]
        context_text = f"{self.titles[item]} - {self.descriptions[item]}"
        
        encoding = self.tokenizer(
            context_text,
            str(self.comments[item]),
            add_special_tokens=True,
            max_length=self.max_len,
            padding='max_length',
            truncation=True,
            return_attention_mask=True,
            return_tensors='pt',
        )
        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(self.labels[item], dtype=torch.long)
        }


def prepare_datasets(config):
    """Load and prepare training and validation datasets."""
    data_path = Path(config['data']['path'])
    df = pd.read_parquet(data_path)
    
    # Get column names from config
    title_col = config['data'].get('title_column')
    desc_col = config['data'].get('description_column')
    comment_col = config['data'].get('comment_column')
    label_col = config['data'].get('label_column')
    
    # Drop rows with missing values
    df.dropna(subset=[title_col, desc_col, comment_col, label_col], inplace=True)
    
    # Validate labels
    num_labels = config['model']['num_labels']
    unique_labels = df[label_col].unique()
    print(f"\nLabel validation:")
    print(f"  Expected labels: 0 to {num_labels - 1}")
    print(f"  Found unique labels: {sorted(unique_labels)}")
    print(f"  Label counts:")
    for label in sorted(unique_labels):
        count = (df[label_col] == label).sum()
        print(f"    {label}: {count}")
    
    # Check for invalid labels
    invalid_labels = (df[label_col] < 0) | (df[label_col] >= num_labels)
    if invalid_labels.any():
        num_invalid = invalid_labels.sum()
        print(f"\n⚠ WARNING: Found {num_invalid} rows with labels outside valid range [0, {num_labels-1}]")
        print(f"  Filtering out invalid labels...")
        df = df[~invalid_labels].copy()
        print(f"  Remaining samples: {len(df)}")
    
    if len(df) == 0:
        raise ValueError("No valid samples remaining after filtering!")
    
    # Split data
    train_idx, test_idx = train_test_split(
        np.arange(len(df)),
        test_size=config['data']['test_size'],
        stratify=df[label_col].values,
        random_state=config['data']['random_state']
    )
    
    return df, train_idx, test_idx, len(train_idx), len(test_idx)


def create_datasets(df, train_idx, test_idx, tokenizer, config):
    """Create train and test datasets."""
    title_col = config['data'].get('title_column', 'title')
    desc_col = config['data'].get('description_column', 'description')
    comment_col = config['data'].get('comment_column', 'comment')
    label_col = config['data'].get('label_column', 'label')
    max_len = config['model']['max_length']
    
    train_dataset = ContextDataset(
        df[title_col].values[train_idx],
        df[desc_col].values[train_idx],
        df[comment_col].values[train_idx],
        df[label_col].values[train_idx],
        tokenizer,
        max_len
    )
    
    test_dataset = ContextDataset(
        df[title_col].values[test_idx],
        df[desc_col].values[test_idx],
        df[comment_col].values[test_idx],
        df[label_col].values[test_idx],
        tokenizer,
        max_len
    )
    
    return train_dataset, test_dataset


def get_lora_model(config, class_weights=None):
    """Initialize model with LoRA configuration."""
    # Load base model
    model = AutoModelForSequenceClassification.from_pretrained(
        config['model']['base_model'],
        num_labels=config['model']['num_labels'],
        ignore_mismatched_sizes=True
    )
    
    # Set class weights if provided
    if class_weights is not None:
        model.config.class_weights = class_weights
    
    # Define LoRA Config
    peft_config = LoraConfig(
        task_type=TaskType.SEQ_CLS,
        inference_mode=False,
        r=config['lora']['r'],
        lora_alpha=config['lora']['lora_alpha'],
        lora_dropout=config['lora']['lora_dropout'],
        bias=config['lora']['bias'],
    )
    
    # Inject LoRA adapters
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()
    return model


def compute_metrics(eval_pred):
    """Compute evaluation metrics."""
    logits, labels = eval_pred
    predictions = logits.argmax(axis=-1)
    
    # Determine if binary or multi-class
    num_classes = len(np.unique(labels))
    average = 'binary' if num_classes == 2 else 'weighted'

    return {
        "accuracy": balanced_accuracy_score(labels, predictions),
        "f1": f1_score(labels, predictions, average=average),
        "precision": precision_score(labels, predictions, average=average, zero_division=0),
        "recall": recall_score(labels, predictions, average=average, zero_division=0)
    }

def main():
    parser = argparse.ArgumentParser(
        description='Train RoBERTa model for Polymarket sentiment analysis with context'
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

    # Login to HuggingFace Hub if token is available
    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        huggingface_hub.login(token=hf_token)
    
    # Load configuration
    config = load_config(args.config)
    
    # Setup output directory
    output_dir = setup_output_directory(args.output_base)
    print(f"Results will be saved to: {output_dir}")
    
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(config['model']['base_model'])
    
    # Prepare datasets
    df, train_idx, test_idx, train_size, test_size = prepare_datasets(config)
    
    # Create datasets
    train_dataset, test_dataset = create_datasets(df, train_idx, test_idx, tokenizer, config)
    
    # Calculate class weights for imbalanced datasets
    label_col = config['data'].get('label_column', 'label')
    train_labels = df[label_col].values[train_idx]
    from sklearn.utils.class_weight import compute_class_weight
    class_weights = compute_class_weight(
        class_weight='balanced',
        classes=np.unique(train_labels),
        y=train_labels
    )
    class_weights_tensor = torch.tensor(class_weights, dtype=torch.float32)
    print(f"\nClass weights: {class_weights_tensor}")
    
    # Apply test mode if enabled (limit dataset sizes)
    test_mode = config.get('test_mode', False)
    if test_mode:
        print("Test mode enabled: Using limited dataset sizes (train=100, test=20)")
        train_limit = min(100, len(train_dataset))
        test_limit = min(20, len(test_dataset))
        
        # Create new limited datasets by slicing indices
        train_idx_limited = train_idx[:train_limit]
        test_idx_limited = test_idx[:test_limit]
        
        train_dataset, test_dataset = create_datasets(df, train_idx_limited, test_idx_limited, tokenizer, config)
        train_size = len(train_dataset)
        test_size = len(test_dataset)
    
    # Create model
    model = get_lora_model(config, class_weights_tensor)
    
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
        eval_steps=config['training'].get('eval_steps', 50),
        save_strategy=config['training']['save_strategy'],
        save_steps=config['training'].get('save_steps', 50),
        load_best_model_at_end=config['training']['load_best_model_at_end'],
        metric_for_best_model=config['training'].get('metric_for_best_model', 'eval_loss'),
        push_to_hub=config['training'].get('push_to_hub', False),
        logging_dir=str(output_dir / "logs"),
        logging_steps=config['training'].get('logging_steps', 10),
        report_to=config['training'].get('report_to', ['none'])
    )
    
    # Setup callbacks
    callbacks = []
    if 'early_stopping_patience' in config['training']:
        callbacks.append(
            EarlyStoppingCallback(
                early_stopping_patience=config['training']['early_stopping_patience']
            )
        )
    
    # Create trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=test_dataset,
        processing_class=tokenizer,
        compute_metrics=compute_metrics,
        callbacks=callbacks
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