# RoBERTa Sentiment Analysis Training Script

This directory contains a production-ready training script converted from the Jupyter notebook.

## Files

- `train.py` - Main training script
- `config.yaml` - Configuration file with hyperparameters
- `main.ipynb` - Original Jupyter notebook (for reference)

## Features

- **External Configuration**: All hyperparameters and settings stored in `config.yaml`
- **Unique Run Directories**: Each training run creates a timestamped directory (e.g., `runs/run_20241119_143022`)
- **Results Logging**: Training metrics, model info, and configuration saved to files (not printed to stdout)
- **Argparse Interface**: Command-line arguments for flexible execution

## Usage

### Basic Training

```bash
python train.py --config config.yaml
```

### Specify Custom Output Directory

```bash
python train.py --config config.yaml --output-base ./my_experiments
```

## Configuration File

The `config.yaml` file contains all training parameters:

```yaml
data:
  path: "../vader/valid_comment_sentiment.parquet"
  test_size: 0.2
  random_state: 42

model:
  base_model: "roberta-base"
  num_labels: 2
  max_length: 256

lora:
  r: 8
  lora_alpha: 32
  lora_dropout: 0.1
  target_modules: "all-linear"

training:
  learning_rate: 1e-3
  per_device_train_batch_size: 32
  num_train_epochs: 1
  # ... more parameters
```

## Output Structure

Each training run creates a directory with the following structure:

```
runs/run_YYYYMMDD_HHMMSS/
├── config.yaml          # Copy of configuration used
├── metrics.json         # Training and evaluation metrics
├── model_info.json      # Model architecture details
├── summary.txt          # Human-readable summary
├── logs/                # Training logs
└── model/               # Saved model checkpoint
    ├── adapter_config.json
    ├── adapter_model.bin
    └── ...
```

## Requirements

Install dependencies:

```bash
pip install transformers datasets peft evaluate pyyaml pandas scikit-learn huggingface_hub
```

## Modifying Hyperparameters

Edit `config.yaml` to change any training parameter. Common modifications:

- **Increase epochs**: `training.num_train_epochs: 3`
- **Adjust batch size**: `training.per_device_train_batch_size: 16`
- **Change learning rate**: `training.learning_rate: 5e-4`
- **Enable HuggingFace Hub upload**: `training.push_to_hub: true`

## Example: Multiple Experiments

Create different config files for experiments:

```bash
# Experiment 1: Low learning rate
python train.py --config config_lr_1e4.yaml --output-base ./experiments

# Experiment 2: More epochs
python train.py --config config_epochs_5.yaml --output-base ./experiments

# Experiment 3: Larger LoRA rank
python train.py --config config_lora_r16.yaml --output-base ./experiments
```

Each run will create a uniquely named directory for easy comparison.
