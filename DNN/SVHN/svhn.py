# -*- coding: utf-8 -*-
"""SVHN_Posit.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1qgom-93pbblaTTiO-ci4vmKJeR_unDfF

Prepare the repo & install Qpytorch+
"""

# !pip install ninja
# !pip install qtorch-plus

"""# SVHN Low Precision Training Example in Posit P(8,2) format 
In this notebook, we present a quick example of how to simulate training a deep neural network in low precision with the Posit Extension in  QPyTorch.
"""

# import useful modules
import argparse
import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision
import torchvision.transforms as transforms
# from qtorch_plus.quant import Quantizer, quantizer
# from qtorch_plus.optim import OptimLP
from torch.optim import SGD
# from qtorch_plus import FloatingPoint, Posit
from tqdm import tqdm
import math
import numpy as np
import matplotlib.pyplot as plt

"""We first load the data. In this example, we will experiment with SVHN."""

# loading data
ds = torchvision.datasets.SVHN
path = os.path.join("./data", "SVHN")
transform_train = transforms.Compose([
    transforms.RandomCrop(32, padding=4),
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
])
transform_test = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
])
train_set = ds(path, split='train', download=True, transform=transform_train)
test_set = ds(path, split='test', download=True, transform=transform_test)
loaders = {
        'train': torch.utils.data.DataLoader(
            train_set,
            batch_size=128,
            shuffle=True,
            num_workers=8,
            pin_memory=True
        ),
        'test': torch.utils.data.DataLoader(
            test_set,
            batch_size=128,
            num_workers=8,
            pin_memory=True
        )
}

"""We then define the quantization setting we are going to use. In particular, here we follow the setting reported in the paper "Training Deep Neural Networks with 8-bit Floating Point Numbers", where the authors propose to use specialized 8-bit and 16-bit floating point format."""

# # define two floating point formats
# bit_8  = Posit(nsize=8,  es=2)
# bit_10 = Posit(nsize=10, es=2)
# bit_12 = Posit(nsize=12, es=2)
# bit_14 = Posit(nsize=14, es=2)
# bit_16 = Posit(nsize=16, es=2)
# IEEE_Half = FloatingPoint(exp=5, man=10)
# bfloat16  = FloatingPoint(exp=8, man=7 )
# # Not supported formats
# # # bit_20 = Posit(nsize=20, es=2)
# # # bit_24 = Posit(nsize=24, es=2)
# # # bit_28 = Posit(nsize=28, es=2)
# # # bit_32 = Posit(nsize=32, es=2)

# num_format = bit_8

# # define quantization functions
# weight_quant = quantizer(forward_number=num_format,
#                         forward_rounding="nearest")
# grad_quant = quantizer(forward_number=num_format,
#                         forward_rounding="nearest")
# momentum_quant = quantizer(forward_number=num_format,
#                         forward_rounding="stochastic")
# acc_quant = quantizer(forward_number=num_format,
#                         forward_rounding="stochastic")

# # define a lambda function so that the Quantizer module can be duplicated easily
# act_error_quant = lambda : Quantizer(forward_number=num_format, backward_number=num_format,
#                         forward_rounding="nearest", backward_rounding="nearest")


torch.manual_seed(0)
np.random.seed(0)

"""Next, we define a low-precision ResNet. In the definition, we recursively insert quantization module after every convolution layer. Note that the quantization of weight, gradient, momentum, and gradient accumulator are not handled here."""


class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, in_planes, planes, stride=1):
        super(BasicBlock, self).__init__()
        self.conv1 = nn.Conv2d(
            in_planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3,
                               stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)

        self.shortcut = nn.Sequential()
        if stride != 1 or in_planes != self.expansion*planes:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_planes, self.expansion*planes,
                          kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(self.expansion*planes)
            )

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += self.shortcut(x)
        out = F.relu(out)
        return out


class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, in_planes, planes, stride=1):
        super(Bottleneck, self).__init__()
        self.conv1 = nn.Conv2d(in_planes, planes, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3,
                               stride=stride, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.conv3 = nn.Conv2d(planes, self.expansion *
                               planes, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm2d(self.expansion*planes)

        self.shortcut = nn.Sequential()
        if stride != 1 or in_planes != self.expansion*planes:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_planes, self.expansion*planes,
                          kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(self.expansion*planes)
            )

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = F.relu(self.bn2(self.conv2(out)))
        out = self.bn3(self.conv3(out))
        out += self.shortcut(x)
        out = F.relu(out)
        return out


class ResNet(nn.Module):
    def __init__(self, block, num_blocks, num_classes=10):
        super(ResNet, self).__init__()
        self.in_planes = 64

        self.conv1 = nn.Conv2d(3, 64, kernel_size=3,
                               stride=1, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.layer1 = self._make_layer(block, 64, num_blocks[0], stride=1)
        self.layer2 = self._make_layer(block, 128, num_blocks[1], stride=2)
        self.layer3 = self._make_layer(block, 256, num_blocks[2], stride=2)
        self.layer4 = self._make_layer(block, 512, num_blocks[3], stride=2)
        self.linear = nn.Linear(512*block.expansion, num_classes)

    def _make_layer(self, block, planes, num_blocks, stride):
        strides = [stride] + [1]*(num_blocks-1)
        layers = []
        for stride in strides:
            layers.append(block(self.in_planes, planes, stride))
            self.in_planes = planes * block.expansion
        return nn.Sequential(*layers)

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.layer1(out)
        out = self.layer2(out)
        out = self.layer3(out)
        out = self.layer4(out)
        out = F.avg_pool2d(out, 4)
        out = out.view(out.size(0), -1)
        out = self.linear(out)
        return out


def ResNet18():
    return ResNet(BasicBlock, [2, 2, 2, 2])


def ResNet34():
    return ResNet(BasicBlock, [3, 4, 6, 3])


def ResNet50():
    return ResNet(Bottleneck, [3, 4, 6, 3])


def ResNet101():
    return ResNet(Bottleneck, [3, 4, 23, 3])


def ResNet152():
    return ResNet(Bottleneck, [3, 8, 36, 3])

model = ResNet18()
# print(model)

device = 'cuda' # change device to 'cpu' if you want to run this example on cpu
model = model.to(device=device)

"""We now use the low-precision optimizer wrapper to help define the quantization of weight, gradient, momentum, and gradient accumulator."""

optimizer = SGD(model.parameters(), lr=0.05, momentum=0.9, weight_decay=5e-4)
# optimizer = OptimLP(optimizer,
#                     weight_quant=weight_quant,
#                     grad_quant=grad_quant,
#                     momentum_quant=momentum_quant,
#                     acc_quant=acc_quant,
#                     grad_scaling=1/1000 # do gradient scaling
# )

"""We can reuse common training scripts without any extra codes to handle quantization."""

def run_epoch(loader, model, criterion, optimizer=None, phase="train"):
    assert phase in ["train", "eval"], "invalid running phase"
    loss_sum = 0.0
    correct = 0.0

    if phase=="train": model.train()
    elif phase=="eval": model.eval()

    ttl = 0
    with torch.autograd.set_grad_enabled(phase=="train"):
        for i, (input, target) in tqdm(enumerate(loader), total=len(loader)):
            input = input.to(device=device)
            target = target.to(device=device)
            output = model(input)
            loss = criterion(output, target)
            loss_sum += loss.cpu().item() * input.size(0)
            pred = output.data.max(1, keepdim=True)[1]
            correct += pred.eq(target.data.view_as(pred)).sum()
            ttl += input.size()[0]

            if phase=="train":
                # loss = loss * 1000 # do gradient scaling
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

    correct = correct.cpu().item()
    return {
        'loss': loss_sum / float(ttl),
        'accuracy': correct / float(ttl) * 100.0,
    }

"""Begin the training process just as usual. Enjoy!"""

# history = {}
train_hist = []
test_hist = []

EPOCHS=100
for epoch in range(EPOCHS):
    print(f"Epoch {epoch+1}/{EPOCHS}")
    train_res = run_epoch(loaders['train'], model, F.cross_entropy,
                                optimizer=optimizer, phase="train")
    train_hist += [train_res]
    print(train_res)
    test_res = run_epoch(loaders['test'], model, F.cross_entropy,
                                optimizer=optimizer, phase="eval")
    test_hist += [test_res]
    print(test_res)

train_res, test_res

# Plotted the accuracy Graph
def plot_accuracies(train, test=None):
    accuracies = [x['accuracy'] for x in train]
    plt.plot(accuracies, label='Train')
    if test is not None:
        accuracies_test = [x['accuracy'] for x in test]
        plt.plot(accuracies_test, label='Test')
        plt.legend()
    plt.xlabel('epoch')
    plt.ylabel('accuracy')
    plt.title('Accuracy vs. No. of epochs');

# Plotted the accuracy Graph
def plot_losses(train, test=None):
    accuracies = [x['loss'] for x in train]
    plt.plot(accuracies, label='Train')
    if test is not None:
        accuracies_test = [x['loss'] for x in test]
        plt.plot(accuracies_test, label='Test')
        plt.legend()
    plt.xlabel('epoch')
    plt.ylabel('loss')
    plt.title('Loss vs. No. of epochs');

# plot_accuracies(train_hist, test_hist)

# plot_losses(train_hist, test_hist)

import json

with open('FP32/train.hist', 'w') as fout:
    json.dump(train_hist, fout)

with open('FP32/test.hist', 'w') as fout:
    json.dump(test_hist, fout)


# with open('train.hist', 'r') as f_in:
#     train_hist = json.load(f_in)

# with open('test.hist', 'r') as fout:
#     test_hist = json.load(f_in)
