import torch
import torch.nn as nn
from torchsummary import summary
import pdb

class attentionBlock(nn.Module):
    def __init__(self, Fg, Fl, F_int):
        super(attentionBlock, self).__init__()
        self.W_g = nn.Sequential(
            nn.Conv2d(Fg, F_int, kernel_size = 1, stride = 1, padding=0, bias = True),
            nn.BatchNorm2d(F_int)
        )

        self.W_x = nn.Sequential(
            nn.Conv2d(Fl, F_int, kernel_size = 1, stride = 2, padding = 0, bias = True),
            nn.BatchNorm2d(F_int)
        )

        self.psi = nn.Sequential(
            nn.Conv2d(F_int, 1, kernel_size = 1, stride = 1, padding = 0, bias = True),
            nn.BatchNorm2d(1),
            nn.Sigmoid(),
            nn.Upsample(scale_factor=2, mode='bilinear')
        )
        self.relu = nn.ReLU(inplace=True)

    def forward(self, g, x):
        
        g1 = self.W_g(g)
        x1 = self.W_x(x)
        psi = self.relu(g1+x1)
        psi = self.psi(psi)
        return x*psi

class ResidualConv(nn.Module):
    def __init__(self, input_dim, output_dim, stride, padding):
        super(ResidualConv, self).__init__()

        self.conv_block = nn.Sequential(
            nn.BatchNorm2d(input_dim),
            nn.ReLU(),
            nn.Conv2d(
                input_dim, output_dim, kernel_size=3, stride=stride, padding=padding
            ),
            nn.BatchNorm2d(output_dim),
            nn.ReLU(),
            nn.Conv2d(output_dim, output_dim, kernel_size=3, padding=1),
        )
        self.conv_skip = nn.Sequential(
            nn.Conv2d(input_dim, output_dim, kernel_size=3, stride=stride, padding=1),
            nn.BatchNorm2d(output_dim),
        )

    def forward(self, x):

        return self.conv_block(x) + self.conv_skip(x)


class Upsample(nn.Module):
    def __init__(self, input_dim, output_dim, kernel, stride):
        super(Upsample, self).__init__()

        self.upsample = nn.ConvTranspose2d(
            input_dim, output_dim, kernel_size=kernel, stride=stride
        )

    def forward(self, x):
        return self.upsample(x)   
    
class ResUnet(nn.Module):
    def __init__(self, channel, filters=[32, 64, 128, 256]):
        super(ResUnet, self).__init__()

        self.input_layer = nn.Sequential(
            nn.Conv2d(channel, filters[0], kernel_size=3, padding=1),
            nn.BatchNorm2d(filters[0]),
            nn.ReLU(),
            nn.Conv2d(filters[0], filters[0], kernel_size=3, padding=1),
        )
        self.input_skip = nn.Sequential(
            nn.Conv2d(channel, filters[0], kernel_size=3, padding=1)
        )

        self.residual_conv_1 = ResidualConv(filters[0], filters[1], 2, 1)
        self.residual_conv_2 = ResidualConv(filters[1], filters[2], 2, 1)

        self.bridge = ResidualConv(filters[2], filters[3], 2, 1)
        self.attention_bridge = attentionBlock(filters[3], filters[2], filters[2])

        self.upsample_1 = Upsample(filters[3], filters[3], 2, 2)
        self.attention_1 = attentionBlock(filters[2], filters[1], filters[1])
        self.up_residual_conv1 = ResidualConv(filters[3] + filters[2], filters[2], 1, 1)

        self.upsample_2 = Upsample(filters[2], filters[2], 2, 2)
        self.attention_2 = attentionBlock(filters[1], filters[0], filters[0])
        self.up_residual_conv2 = ResidualConv(filters[2] + filters[1], filters[1], 1, 1)

        self.upsample_3 = Upsample(filters[1], filters[1], 2, 2)
        self.up_residual_conv3 = ResidualConv(filters[1] + filters[0], filters[0], 1, 1)

        self.output_layer = nn.Sequential(
            nn.Conv2d(filters[0], 1, 1, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        # Encode
        x1 = self.input_layer(x) + self.input_skip(x)
        x2 = self.residual_conv_1(x1)
        x3 = self.residual_conv_2(x2)
        # Bridge
        x4 = self.bridge(x3)
        x4_atg = self.attention_bridge(x4, x3)

        # Decode
        x4 = self.upsample_1(x4)
    
        x5 = torch.cat([x4_atg, x4], dim=1)

        x6 = self.up_residual_conv1(x5)
        x6_atg = self.attention_1(x6, x2)

        x6 = self.upsample_2(x6)
        x7 = torch.cat([x6_atg, x6], dim=1)
        

        x8 = self.up_residual_conv2(x7)
        x8_atg = self.attention_2(x8, x1)

        x8 = self.upsample_3(x8)
        x9 = torch.cat([x8_atg, x8], dim=1)

        x10 = self.up_residual_conv3(x9)

        output = self.output_layer(x10)

        return output
    