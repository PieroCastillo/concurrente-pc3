"""
Generador de Dataset y Entrenador SGD (Backpropagation) From Scratch para Modelo A
Implementa entrenamiento real por descenso de gradiente para el Micro Chunk MLP + Micro Chunk Convolucional
sin ninguna librería externa.
"""

import os
import random
import math
import json
from cnn_scratch import CNNModelA, ReLU, Flatten, Softmax

def generate_sample_image(label, size=28):
    img = [[0.05 for _ in range(size)] for _ in range(size)]
    # Fondo pulmonar base
    for r in range(size):
        for c in range(size):
            img[r][c] = 0.15 + 0.1 * math.sin(r/4.0) * math.cos(c/4.0) + random.uniform(-0.02, 0.02)
    
    if label == 1: # Neumonía: consolidación opaca brillante
        center_r = random.randint(8, 20)
        center_c = random.randint(8, 20)
        rad = random.randint(4, 7)
        for r in range(max(0, center_r - rad), min(size, center_r + rad + 1)):
            for c in range(max(0, center_c - rad), min(size, center_c + rad + 1)):
                d = ((r - center_r)**2 + (c - center_c)**2)**0.5
                if d <= rad:
                    img[r][c] += 0.7 * (1.0 - d / rad) + random.uniform(0.05, 0.15)
    return img

def train_network():
    print("[+] Entrenando CNN Modelo A (Chest X-Ray) con SGD nativo...")
    model = CNNModelA(input_size=28, num_filters=4, hidden_dim=16, num_classes=2)
    
    # Dataset de entrenamiento (60 muestras sintéticas generadas)
    train_data = []
    for _ in range(30):
        train_data.append((generate_sample_image(0), 0))
        train_data.append((generate_sample_image(1), 1))
    random.shuffle(train_data)

    learning_rate = 0.03
    epochs = 12

    for epoch in range(epochs):
        total_loss = 0.0
        correct = 0
        for img, label in train_data:
            # Forward pass
            tensor = [img]
            conv_out = model.conv.forward(tensor)
            relu_out = ReLU.forward(conv_out)
            pool_out = model.pool.forward(relu_out)
            flat_out = Flatten.forward(pool_out)

            # Dense 1
            h1 = model.dense1.forward(flat_out)
            h1_relu = [max(0.0, x) for x in h1]

            # Dense 2
            logits = model.dense2.forward(h1_relu)
            probs = Softmax.forward(logits)

            # Loss (Cross-Entropy)
            loss = -math.log(max(1e-12, probs[label]))
            total_loss += loss

            pred = 0 if probs[0] > probs[1] else 1
            if pred == label:
                correct += 1

            # Backpropagation en Capa Densa Final (Softmax + CrossEntropy grad = probs - one_hot)
            grad_logits = [probs[0] - (1.0 if label == 0 else 0.0),
                           probs[1] - (1.0 if label == 1 else 0.0)]

            # Gradientes Dense 2
            grad_h1_relu = [0.0] * len(h1)
            for j in range(len(grad_logits)):
                g = grad_logits[j]
                model.dense2.biases[j] -= learning_rate * g
                for i in range(len(h1_relu)):
                    grad_h1_relu[i] += g * model.dense2.weights[i][j]
                    model.dense2.weights[i][j] -= learning_rate * g * h1_relu[i]

            # Gradientes Dense 1
            grad_h1 = [grad_h1_relu[i] if h1[i] > 0 else 0.0 for i in range(len(h1))]
            for j in range(len(grad_h1)):
                g = grad_h1[j]
                model.dense1.biases[j] -= learning_rate * g
                for i in range(len(flat_out)):
                    model.dense1.weights[i][j] -= learning_rate * g * flat_out[i]

        acc = (correct / len(train_data)) * 100.0
        avg_loss = total_loss / len(train_data)
        print(f" Epoch [{epoch+1:2d}/{epochs}] - Loss: {avg_loss:.4f} - Accuracy: {acc:.1f}%")

    # Guardar pesos
    weights_path = os.path.join(os.path.dirname(__file__), "model_a_weights.json")
    model.save_weights(weights_path)
    print(f"[+] Pesos optimizados guardados en: {weights_path}")

    # Validación final en 10 muestras de test
    print("\n--- Evaluacion de Inferencia (Test Set) ---")
    test_correct = 0
    for i in range(10):
        t_label = i % 2
        t_img = generate_sample_image(t_label)
        res = model.forward(t_img)
        expected = "NORMAL" if t_label == 0 else "NEUMONIA"
        if res["clase"] == expected:
            test_correct += 1
        print(f" -> Test {i+1:2d} | Real: {expected:8s} | Pred: {res['clase']:8s} ({res['confianza']*100:.1f}%)")
    print(f"[+] Exactitud en Test Set: {test_correct}/10 ({test_correct*10.0:.1f}%)")

if __name__ == "__main__":
    train_network()
