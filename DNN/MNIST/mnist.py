# -*- coding: utf-8 -*-
"""MNIST_Posit.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1qgom-93pbblaTTiO-ci4vmKJeR_unDfF

Prepare the repo & install Qpytorch+
"""

# !pip install ninja
# !pip install qtorch-plus

"""# MNIST Low Precision Training Example in Posit P(8,2) format 
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

"""We first load the data. In this example, we will experiment with MNIST."""

# loading data
ds = torchvision.datasets.MNIST
path = os.path.join("./data", "MNIST")
transform_train = transforms.Compose([
    transforms.RandomCrop(32, padding=4),
    transforms.ToTensor(),
    transforms.Normalize((0.5,), (0.5,)),
])
transform_test = transforms.Compose([
    transforms.CenterCrop(32),
    transforms.ToTensor(),
    transforms.Normalize((0.5,), (0.5,)),
])
train_set = ds(path, train=True, download=True, transform=transform_train)
test_set = ds(path, train=False, download=True, transform=transform_test)
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

class LeNet(nn.Module):
    def __init__(self, num_classes=10):
        super(LeNet, self).__init__()
        self.conv1 = nn.Conv2d(1, 6, 5)
        self.conv2 = nn.Conv2d(6, 16, 5)
        self.fc1   = nn.Linear(16*5*5, 120)
        self.fc2   = nn.Linear(120, 84)
        self.fc3   = nn.Linear(84, num_classes)
        # self.quant = quant()

    def forward(self, x):
        # x = self.quant(x)
        out = self.conv1(x)
        out = F.relu(out)
        out = F.max_pool2d(out, 2)
        # out = self.quant(out)
        out = self.conv2(out)
        out = F.relu(out)
        out = F.max_pool2d(out, 2)
        # out = self.quant(out)
        out = out.view(out.size(0), -1)
        # print(out.shape)
        out = self.fc1(out)
        out = F.relu(out)       
        # out = self.quant(out) 
        out = self.fc2(out)
        out = F.relu(out)
        # out = self.quant(out)        
        out = self.fc3(out)
        # out = self.quant(out)
        return out
# def conv3x3(in_planes, out_planes, stride=1):
#     return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride,
#                      padding=1, bias=False)

# class BasicBlock(nn.Module):
#     expansion = 1

#     def __init__(self, inplanes, planes, quant, stride=1, downsample=None):
#         super(BasicBlock, self).__init__()
#         self.bn1 = nn.BatchNorm2d(inplanes)
#         self.relu = nn.ReLU(inplace=True)
#         self.conv1 = conv3x3(inplanes, planes, stride)
#         self.bn2 = nn.BatchNorm2d(planes)
#         self.conv2 = conv3x3(planes, planes)
#         self.downsample = downsample
#         self.stride = stride
#         self.quant = quant()

#     def forward(self, x):
#         residual = x

#         out = self.bn1(x)
#         out = self.relu(out)
#         out = self.quant(out)
#         out = self.conv1(out)
#         out = self.quant(out)

#         out = self.bn2(out)
#         out = self.relu(out)
#         out = self.quant(out)
#         out = self.conv2(out)
#         out = self.quant(out)

#         if self.downsample is not None:
#             residual = self.downsample(x)

#         out += residual

#         return out
    
# class PreResNet(nn.Module):

#     def __init__(self,quant, num_classes=10, depth=20):

#         super(PreResNet, self).__init__()
#         assert (depth - 2) % 6 == 0, 'depth should be 6n+2'
#         n = (depth - 2) // 6

#         block = BasicBlock

#         self.inplanes = 16
#         self.conv1 = nn.Conv2d(3, 16, kernel_size=3, padding=1,
#                                bias=False)
#         self.layer1 = self._make_layer(block, 16, n, quant)
#         self.layer2 = self._make_layer(block, 32, n, quant, stride=2)
#         self.layer3 = self._make_layer(block, 64, n, quant, stride=2)
#         self.bn = nn.BatchNorm2d(64 * block.expansion)
#         self.relu = nn.ReLU(inplace=True)
#         self.avgpool = nn.AvgPool2d(8)
#         self.fc = nn.Linear(64 * block.expansion, num_classes)
#         self.quant = quant()
#         IBM_half = FloatingPoint(exp=6, man=9)
#         self.quant_half = Quantizer(IBM_half, IBM_half, "nearest", "nearest")
#         for m in self.modules():
#             if isinstance(m, nn.Conv2d):
#                 n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
#                 m.weight.data.normal_(0, math.sqrt(2. / n))
#             elif isinstance(m, nn.BatchNorm2d):
#                 m.weight.data.fill_(1)
#                 m.bias.data.zero_()

#     def _make_layer(self, block, planes, blocks, quant, stride=1):
#         downsample = None
#         if stride != 1 or self.inplanes != planes * block.expansion:
#             downsample = nn.Sequential(
#                 nn.Conv2d(self.inplanes, planes * block.expansion,
#                           kernel_size=1, stride=stride, bias=False),
#             )

#         layers = list()
#         layers.append(block(self.inplanes, planes, quant , stride, downsample))
#         self.inplanes = planes * block.expansion
#         for i in range(1, blocks):
#             layers.append(block(self.inplanes, planes, quant))

#         return nn.Sequential(*layers)

#     def forward(self, x):
#         x = self.quant_half(x)
#         x = self.conv1(x)
#         x = self.quant(x)

#         x = self.layer1(x)  # 32x32
#         x = self.layer2(x)  # 16x16
#         x = self.layer3(x)  # 8x8
#         x = self.bn(x)
#         x = self.relu(x)
#         x = self.quant(x)

#         x = self.avgpool(x)
#         x = x.view(x.size(0), -1)
#         x = self.fc(x)
#         x = self.quant_half(x)

#         return x

model = LeNet()
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