"""
Motor de Red Neuronal Convolucional (CNN) From Scratch
Implementado estrictamente SIN librerías de IA (sin TensorFlow, PyTorch, Keras, etc.).
Usa únicamente la librería estándar de Python y estructuras matemáticas puras.
Soporta multihilos nativos para la extracción de características (micro chunk de convolución)
y micro chunk de MLP (Feedforward + Softmax).
"""

import math
import random
import json
import os
from concurrent.futures import ThreadPoolExecutor

class Convolution2D:
    """Micro Chunk de Convolución: filtros espaciales, stride, padding y convolución multihilo"""
    def __init__(self, num_filters, kernel_size=3, input_channels=1, stride=1, padding=0):
        self.num_filters = num_filters
        self.kernel_size = kernel_size
        self.input_channels = input_channels
        self.stride = stride
        self.padding = padding
        # Inicialización He / Xavier
        scale = math.sqrt(2.0 / (kernel_size * kernel_size * input_channels))
        self.filters = [
            [[[random.gauss(0, scale) for _ in range(kernel_size)] 
              for _ in range(kernel_size)] 
             for _ in range(input_channels)]
            for _ in range(num_filters)
        ]
        self.biases = [0.0 for _ in range(num_filters)]

    def forward_single_filter(self, f_idx, padded_input, in_h, in_w):
        k = self.kernel_size
        s = self.stride
        out_h = (in_h + 2 * self.padding - k) // s + 1
        out_w = (in_w + 2 * self.padding - k) // s + 1
        filt = self.filters[f_idx]
        bias = self.biases[f_idx]
        
        feature_map = [[bias for _ in range(out_w)] for _ in range(out_h)]
        for i in range(out_h):
            r_start = i * s
            for j in range(out_w):
                c_start = j * s
                val = 0.0
                for c in range(self.input_channels):
                    f_c = filt[c]
                    in_c = padded_input[c]
                    for kr in range(k):
                        for kc in range(k):
                            val += in_c[r_start + kr][c_start + kc] * f_c[kr][kc]
                feature_map[i][j] += val
        return f_idx, feature_map

    def forward(self, input_tensor, executor=None):
        """
        input_tensor: [channels][height][width]
        Si executor está disponible, ejecuta los filtros en hilos paralelos.
        """
        in_channels = len(input_tensor)
        in_h = len(input_tensor[0])
        in_w = len(input_tensor[0][0])

        # Padding
        if self.padding > 0:
            padded_input = []
            for c in range(in_channels):
                p_matrix = []
                for _ in range(self.padding):
                    p_matrix.append([0.0] * (in_w + 2 * self.padding))
                for r in range(in_h):
                    p_matrix.append([0.0] * self.padding + list(input_tensor[c][r]) + [0.0] * self.padding)
                for _ in range(self.padding):
                    p_matrix.append([0.0] * (in_w + 2 * self.padding))
                padded_input.append(p_matrix)
        else:
            padded_input = input_tensor

        outputs = [None] * self.num_filters

        if executor:
            futures = [
                executor.submit(self.forward_single_filter, f, padded_input, in_h, in_w)
                for f in range(self.num_filters)
            ]
            for fut in futures:
                f_idx, f_map = fut.result()
                outputs[f_idx] = f_map
        else:
            for f in range(self.num_filters):
                _, f_map = self.forward_single_filter(f, padded_input, in_h, in_w)
                outputs[f] = f_map

        return outputs

class ReLU:
    """Función de activación no lineal f(x) = max(0, x)"""
    @staticmethod
    def forward(tensor):
        return [
            [[max(0.0, val) for val in row] for row in channel]
            for channel in tensor
        ]

class MaxPooling2D:
    """Micro Chunk de Submuestreo / Pooling 2D"""
    def __init__(self, pool_size=2, stride=2):
        self.pool_size = pool_size
        self.stride = stride

    def forward(self, tensor):
        p = self.pool_size
        s = self.stride
        out_tensor = []
        for channel in tensor:
            h = len(channel)
            w = len(channel[0])
            out_h = (h - p) // s + 1
            out_w = (w - p) // s + 1
            pooled = []
            for i in range(out_h):
                r_start = i * s
                row = []
                for j in range(out_w):
                    c_start = j * s
                    max_val = -1e9
                    for kr in range(p):
                        for kc in range(p):
                            v = channel[r_start + kr][c_start + kc]
                            if v > max_val:
                                max_val = v
                    row.append(max_val)
                pooled.append(row)
            out_tensor.append(pooled)
        return out_tensor

class Flatten:
    """Aplanamiento de tensor 3D a vector 1D"""
    @staticmethod
    def forward(tensor):
        flat = []
        for channel in tensor:
            for row in channel:
                flat.extend(row)
        return flat

class Dense:
    """Capa Densa (Fully Connected)"""
    def __init__(self, input_dim, output_dim):
        self.input_dim = input_dim
        self.output_dim = output_dim
        scale = math.sqrt(2.0 / input_dim)
        self.weights = [[random.gauss(0, scale) for _ in range(output_dim)] for _ in range(input_dim)]
        self.biases = [0.0 for _ in range(output_dim)]

    def forward(self, input_vec):
        output = list(self.biases)
        for i, val in enumerate(input_vec):
            w_row = self.weights[i]
            for j in range(self.output_dim):
                output[j] += val * w_row[j]
        return output

class Softmax:
    """Capa Softmax con estabilización numérica"""
    @staticmethod
    def forward(vec):
        max_v = max(vec)
        exps = [math.exp(v - max_v) for v in vec]
        sum_exp = sum(exps)
        if sum_exp == 0.0:
            return [1.0 / len(vec)] * len(vec)
        return [e / sum_exp for e in exps]

class CNNModelA:
    """
    Modelo A: Clasificación binaria Chest X-Ray (Neumonía)
    Normal (0) vs Neumonía (1). Entrada: 1 canal (28x28 o 32x32).
    """
    def __init__(self, input_size=28, num_filters=4, hidden_dim=16, num_classes=2):
        self.input_size = input_size
        self.conv = Convolution2D(num_filters=num_filters, kernel_size=3, input_channels=1, padding=1)
        self.pool = MaxPooling2D(pool_size=2, stride=2)
        # 28x28 -> conv con pad=1 -> 28x28 -> pool -> 14x14 * num_filters
        pooled_dim = input_size // 2
        flat_dim = num_filters * pooled_dim * pooled_dim
        self.dense1 = Dense(flat_dim, hidden_dim)
        self.dense2 = Dense(hidden_dim, num_classes)
        self.classes = ["NORMAL", "NEUMONIA"]

    def forward(self, img_2d, executor=None):
        # img_2d es matriz [height][width], convertimos a tensor [1][h][w]
        tensor = [img_2d]
        conv_out = self.conv.forward(tensor, executor=executor)
        relu_out = ReLU.forward(conv_out)
        pool_out = self.pool.forward(relu_out)
        flat_out = Flatten.forward(pool_out)
        hidden = self.dense1.forward(flat_out)
        hidden_relu = [max(0.0, h) for h in hidden]
        logits = self.dense2.forward(hidden_relu)
        probs = Softmax.forward(logits)
        
        pred_idx = 0 if probs[0] >= probs[1] else 1
        return {
            "clase": self.classes[pred_idx],
            "indice": pred_idx,
            "probabilidades": {
                "NORMAL": round(probs[0], 4),
                "NEUMONIA": round(probs[1], 4)
            },
            "confianza": round(probs[pred_idx], 4)
        }

    def save_weights(self, filepath):
        data = {
            "input_size": self.input_size,
            "conv_filters": self.conv.filters,
            "conv_biases": self.conv.biases,
            "dense1_w": self.dense1.weights,
            "dense1_b": self.dense1.biases,
            "dense2_w": self.dense2.weights,
            "dense2_b": self.dense2.biases,
            "classes": self.classes
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f)

    def load_weights(self, filepath):
        if not os.path.exists(filepath):
            return False
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.input_size = data["input_size"]
        self.conv.filters = data["conv_filters"]
        self.conv.biases = data["conv_biases"]
        self.dense1.weights = data["dense1_w"]
        self.dense1.biases = data["dense1_b"]
        self.dense2.weights = data["dense2_w"]
        self.dense2.biases = data["dense2_b"]
        self.classes = data.get("classes", ["NORMAL", "NEUMONIA"])
        return True
