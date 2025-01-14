#!/bin/bash

#source /project/anaconda/fsi/.bashrc
source /data/zhanzgu/.bashrc
conda activate fsi

# Make sure to modify the paths accordingly
python inference.py \
  --wdir "/projects/TCCTVS/FSI/cnnModel/" \
  --num_epochs 100 \
  --scale 1 \
  --init 5 \
  --steps 48

