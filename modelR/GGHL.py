import sys
sys.path.append("..")
import torch.nn as nn
from modelR.backbones.darknet53 import Darknet53
from modelR.necks.neck_GGHL import Neck
from modelR.head.head_GGHL import Head
from modelR.layers.convolutions import Convolutional
from utils.utils_basic import *

class GGHL(nn.Module):
    def __init__(self, init_weights=True, inputsize= int(cfg.TRAIN["TRAIN_IMG_SIZE"]), weight_path=None):
        super(GGHL, self).__init__()
        self.__strides = torch.FloatTensor(cfg.MODEL["STRIDES"])
        self.__nC = cfg.DATA["NUM"]
        self.__out_channel = self.__nC + 4 + 5 + 1
        self.__backnone = Darknet53()
        self.__fpn = Neck(fileters_in=[1024, 512, 256, 128], fileters_out=self.__out_channel)
        self.__head_s = Head(nC=self.__nC, stride=self.__strides[0])
        self.__head_m = Head(nC=self.__nC, stride=self.__strides[1])
        self.__head_l = Head(nC=self.__nC, stride=self.__strides[2])
        if init_weights:
            self.__init_weights()

    def forward(self, x):
        out = []
        x_8, x_16, x_32 = self.__backnone(x)
        x_s, x_m, x_l = self.__fpn(x_32, x_16, x_8)
        out.append(self.__head_s(x_s))
        out.append(self.__head_m(x_m))
        out.append(self.__head_l(x_l))
        if self.training:
            p, p_d = list(zip(*out))
            return p, p_d
        else:
            p, p_d = list(zip(*out))
            return p, torch.cat(p_d, 0)

    def __init_weights(self):
        " Note ：nn.Conv2d nn.BatchNorm2d'initing modes are uniform "
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.normal_(m.weight.data, 0.0, 0.01)
                if m.bias is not None:
                    m.bias.data.zero_()
            elif isinstance(m, nn.BatchNorm2d):
                torch.nn.init.constant_(m.weight.data, 1.0)
                torch.nn.init.constant_(m.bias.data, 0.0)
            elif isinstance(m, nn.Linear):
                m.weight.data.normal_(0,0.01)
                if m.bias is not None:
                    m.bias.data.zero_()


    def load_darknet_weights(self, weight_file, cutoff=52):
        "https://github.com/ultralytics/yolov3/blob/master/models.py"
        print("load darknet weights : ", weight_file)
        with open(weight_file, 'rb') as f:
            _ = np.fromfile(f, dtype=np.int32, count=5)
            weights = np.fromfile(f, dtype=np.float32)
        count = 0
        ptr = 0
        for m in self.modules():
            if isinstance(m, Convolutional):
                # only initing backbone conv's weights
                if count == cutoff:
                    break
                count += 1
                conv_layer = m._Convolutional__conv
                if m.norm == "bn":
                    # Load BN bias, weights, running mean and running variance
                    bn_layer = m._Convolutional__norm
                    num_b = bn_layer.bias.numel()  # Number of biases
                    # Bias
                    bn_b = torch.from_numpy(weights[ptr:ptr + num_b]).view_as(bn_layer.bias.data)
                    bn_layer.bias.data.copy_(bn_b)
                    ptr += num_b
                    # Weight
                    bn_w = torch.from_numpy(weights[ptr:ptr + num_b]).view_as(bn_layer.weight.data)
                    bn_layer.weight.data.copy_(bn_w)
                    ptr += num_b
                    # Running Mean
                    bn_rm = torch.from_numpy(weights[ptr:ptr + num_b]).view_as(bn_layer.running_mean)
                    bn_layer.running_mean.data.copy_(bn_rm)
                    ptr += num_b
                    # Running Var
                    bn_rv = torch.from_numpy(weights[ptr:ptr + num_b]).view_as(bn_layer.running_var)
                    bn_layer.running_var.data.copy_(bn_rv)
                    ptr += num_b
                else:
                    # Load conv. bias
                    num_b = conv_layer.bias.numel()
                    conv_b = torch.from_numpy(weights[ptr:ptr + num_b]).view_as(conv_layer.bias.data)
                    conv_layer.bias.data.copy_(conv_b)
                    ptr += num_b
                # Load conv. weights
                num_w = conv_layer.weight.numel()
                conv_w = torch.from_numpy(weights[ptr:ptr + num_w]).view_as(conv_layer.weight.data)
                conv_layer.weight.data.copy_(conv_w)
                ptr += num_w
