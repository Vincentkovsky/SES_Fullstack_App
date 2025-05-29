# -*- coding: utf-8 -*-
import argparse
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import os
import rasterio
import time
import matplotlib.pyplot as plt
from datetime import datetime
from torch.utils.tensorboard import SummaryWriter
from fsiUtils import load_and_stack_files

# Draw raster visualization
def draw_raster(var, varname, i, savedir):
    colorbar_range = [0, var.max().item()]
    plt.figure(figsize=(16, 12))
    plt.imshow(var.detach().cpu().squeeze(0), cmap='viridis')
    plt.title(f"waterlevel_{i}_" + varname)
    plt.colorbar()
    plt.gca().invert_yaxis()
    plt.savefig(savedir + f"waterlevel_{i}_" + varname + '.png', dpi=300, bbox_inches='tight')
    plt.close()

# CNN model definition
class CNNModel(nn.Module):
    def __init__(self, input_channels, output_channels, height, width):
        super(CNNModel, self).__init__()
        self.layer_norm = nn.LayerNorm([input_channels, height, width])
        self.conv1 = nn.Conv2d(input_channels, 32, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.conv3 = nn.Conv2d(64, 32, kernel_size=3, padding=1)
        self.conv4 = nn.Conv2d(32, output_channels, kernel_size=3, padding=1)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.layer_norm(x)
        x = self.relu(self.conv1(x))
        x = self.relu(self.conv2(x))
        x = self.relu(self.conv3(x))
        x = self.conv4(x)
        return x

# Main function
def main(args):
    today_date = datetime.today().strftime('%Y%m%d_%H-%M-%S')
    print(today_date)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f'Using device: {device}')

    # Set the environment variable to avoid fragmentation
    os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'

    wdir = args.wdir
    num_epochs = args.num_epochs
    modir = wdir + f"model/cnn_{num_epochs}ep_scale1weightMask"
    evldir = wdir + "221092/"
    savedir = wdir + f'inference/halfHourModel/cnn_{num_epochs}ep_scale1/{today_date[0:8]}/'
    os.makedirs(savedir, exist_ok=True)

    dem_file_path = wdir + 'constant/20240226merged.tif'
    with rasterio.open(dem_file_path) as src:
        constants = src.read(1)  # Assuming the DEM has one band

    constants = np.expand_dims(constants, axis=0)
    height, width = constants.shape[1], constants.shape[2]
    scale = args.scale

    # Load model
    model = CNNModel(input_channels=3, output_channels=1, height=int(height/scale), width=int(width/scale))
    checkpoint = torch.load(modir + '/final_model_99')
    state_dict = {k.replace("module.", ""): v for k, v in checkpoint['model_state_dict'].items()}
    model.load_state_dict(state_dict)
    model.to(device)

    criterion = nn.MSELoss()
    writer = SummaryWriter(savedir + 'training_log')

    init = args.init
    steps = args.steps

    for i in range(steps):
        print('***********************************************')
        print('Inferencing step: ', i + 1)
        try:
            input_data = output_pred.cpu()
        except:
            print('Initial step.')
            input_data = load_and_stack_files([evldir + f'waterlevel_{init}'])
            input_data = input_data.reshape(-1, int(height / scale), scale, int(width / scale), scale).mean(axis=(2, 4))

        rain_data = load_and_stack_files([evldir + f'rain_{init + i + 1}'])
        rain_data = rain_data.reshape(-1, int(height / scale), scale, int(width / scale), scale).mean(axis=(2, 4))

        Y_val = load_and_stack_files([evldir + f'waterlevel_{init + i + 1}'])
        Y_val = Y_val.reshape(-1, int(height / scale), scale, int(width / scale), scale).mean(axis=(2, 4))

        X_val = np.stack((input_data, constants, rain_data), axis=-1)
        X_val[X_val == -9999] = 0.0
        Y_val[Y_val == -9999] = float('nan')

        model.eval()
        with torch.no_grad():
            X_val = torch.tensor(X_val).to(device)
            Y_val = torch.tensor(Y_val).to(device)
            output_pred = model(X_val.permute(0, 3, 1, 2)).squeeze(1)

            output_pred_nan = output_pred.clone()
            output_pred_nan[output_pred_nan == 0] = float('nan')

            draw_raster(output_pred_nan, 'predict', i, savedir)
            draw_raster(Y_val, 'gt', i, savedir)

            loss = criterion(output_pred, Y_val).item()
            diff = torch.abs(output_pred - Y_val)
            within_tolerance = torch.sum(diff <= 0.5).item()
            total_pixels = torch.numel(diff)

            accuracy = within_tolerance / total_pixels
            print(f'Step: {i + 1}: Accuracy within 0.5m: {accuracy * 100:.2f}%, Loss {loss}')
            writer.add_scalar('Loss/validation', loss, i)
            writer.add_scalar('Accuracy/validation', accuracy * 100, i)

# Entry point
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inference Script")
    parser.add_argument("--wdir", type=str, required=True, help="Working directory")
    parser.add_argument("--num_epochs", type=int, default=100, help="Number of epochs")
    parser.add_argument("--scale", type=int, default=1, help="Scale factor for resizing")
    parser.add_argument("--init", type=int, default=5, help="Initial step")
    parser.add_argument("--steps", type=int, default=48, help="Number of inference steps")
    args = parser.parse_args()

    main(args)

