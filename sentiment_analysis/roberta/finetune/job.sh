#!/bin/sh 

### General LSF options
### -- Job name --
#BSUB -J roberta_training
### -- Specify queue --
#BSUB -q gpuv100
### -- Number of nodes --
#BSUB -n 4
### -- Specify GPU --
#BSUB -gpu "num=1:mode=exclusive_process"
### -- Memory per core --
#BSUB -R "rusage[mem=8GB]"
### -- Wall time (hh:mm) --
#BSUB -W 24:00
### -- Email notification --
#BSUB -N
### -- Output and error files --
#BSUB -o job_out/train_%J.out
#BSUB -e job_out/train_%J.err
### -- end of LSF options --

# Load environment variables
source ./.env

# Create job_out if it is not present
if [[ ! -d ${REPO}/job_out ]]; then
	mkdir -p ${REPO}/job_out
fi

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate venv
module load python3/3.10.12
module load cuda/12.1
source ${REPO}/venv/bin/activate

# Change to script directory
cd ${SCRIPT_DIR}

# Run training
python3 train.py --config config.yaml
