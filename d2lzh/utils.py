import collections
import math
import os
import random
import sys
import tarfile
import time
import zipfile

from IPython import display
from matplotlib import pyplot as plt
from tensorflow import keras
import tensorflow.keras.backend as K
import numpy as np


def show_images(imgs, num_rows, num_cols, scale=2):
    """Plot a list of images."""
    figsize = (num_cols * scale, num_rows * scale)
    _, axes = plt.subplots(num_rows, num_cols, figsize=figsize)
    for i in range(num_rows):
        for j in range(num_cols):
            axes[i][j].imshow(imgs[i * num_cols + j].asnumpy())
            axes[i][j].axes.get_xaxis().set_visible(False)
            axes[i][j].axes.get_yaxis().set_visible(False)
    return axes


def use_svg_display():
    """Use svg format to display plot in jupyter"""
    display.set_matplotlib_formats('svg')


def get_fashion_mnist_labels(labels):
    text_labels = ['t-shirt', 'trouser', 'pullover', 'dress', 'coat',
                   'sandal', 'shirt', 'sneaker', 'bag', 'ankle boot']
    return [text_labels[int(i)] for i in labels]


def show_fashion_mnist(images, labels):
    use_svg_display()
    # 这里的_表示我们忽略（不使用）的变量
    _, figs = plt.subplots(1, len(images), figsize=(12, 12))
    for f, img, lbl in zip(figs, images, labels):
        f.imshow(img.reshape(28, 28))
        f.set_title(lbl)
        f.axes.get_xaxis().set_visible(False)
        f.axes.get_yaxis().set_visible(False)


def set_figsize(figsize=(3.5, 2.5)):
    """Set matplotlib figure size."""
    use_svg_display()
    plt.rcParams['figure.figsize'] = figsize


def semilogy(x_vals, y_vals, x_label, y_label, x2_vals=None, y2_vals=None,
             legend=None, figsize=(3.5, 2.5)):
    set_figsize(figsize)
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.semilogy(x_vals, y_vals)
    if x2_vals and y2_vals:
        plt.semilogy(x2_vals, y2_vals, linestyle=':')
        plt.legend(legend)


def metric_accuracy(y_true, y_pred):
    ytrue = K.flatten(y_true)
    ypred = K.cast(K.argmax(y_pred, axis=-1), K.floatx())
    acc = K.equal(ytrue, ypred)
    return K.mean(acc)


def load_data_jay_lyrics():
    """Load the Jay Chou lyric data set (available in the Chinese book)."""
    with zipfile.ZipFile('../data/jaychou_lyrics.txt.zip') as zin:
        with zin.open('jaychou_lyrics.txt') as f:
            corpus_chars = f.read().decode('utf-8')
    corpus_chars = corpus_chars.replace('\n', ' ').replace('\r', ' ')
    corpus_chars = corpus_chars[0:10000]
    idx_to_char = list(set(corpus_chars))
    char_to_idx = dict([(char, i) for i, char in enumerate(idx_to_char)])
    vocab_size = len(char_to_idx)
    corpus_indices = [char_to_idx[char] for char in corpus_chars]
    return corpus_indices, corpus_chars, char_to_idx, idx_to_char, vocab_size


def data_iter_random(corpus_indices, batch_size, num_steps, ctx=None):
    # 减1是因为输出的索引是相应输入的索引加1
    num_examples = (len(corpus_indices) - 1) // num_steps
    epoch_size = num_examples // batch_size
    example_indices = list(range(num_examples))
    random.shuffle(example_indices)

    # 返回从pos开始的长为num_steps的序列
    def _data(pos):
        return corpus_indices[pos: pos + num_steps]

    for i in range(epoch_size):
        # 每次读取batch_size个随机样本
        i = i * batch_size
        batch_indices = example_indices[i: i + batch_size]
        X = [_data(j * num_steps) for j in batch_indices]
        Y = [_data(j * num_steps + 1) for j in batch_indices]
        yield np.array(X, ctx), np.array(Y, ctx)


def data_iter_consecutive(corpus_indices, batch_size, num_steps):
    corpus_indices = np.array(corpus_indices)
    data_len = len(corpus_indices)
    batch_len = data_len // batch_size
    indices = corpus_indices[0: batch_size*batch_len].reshape((
        batch_size, batch_len))
    epoch_size = (batch_len - 1) // num_steps
    for i in range(epoch_size):
        i = i * num_steps
        X = indices[:, i: i + num_steps]
        Y = indices[:, i + 1: i + num_steps + 1]
        yield X, Y


def predict_rnn_gluon(prefix, num_chars, model, vocab_size, idx_to_char, char_to_idx, num_steps):
    output = np.array([char_to_idx[prefix[idx]] for idx in range(len(prefix))])
    for t in range(num_chars + len(prefix) - 1):
        # print(output)
        X = keras.utils.to_categorical(output[-num_steps : ], vocab_size)
        # print('X', X.shape, output[-num_steps : ])
        Y = model.predict(X.reshape(1, num_steps, vocab_size))  # 引入batch=1维度
        if t < len(prefix) - 1:
            # output = np.append(output, char_to_idx[prefix[t + 1]])
            pass
        else:
            output = np.append(output, int(Y.argmax(axis=-1)))
    return ''.join([idx_to_char[i] for i in output])


def train_and_predict_rnn_gluon(model, vocab_size, corpus_indices, idx_to_char, char_to_idx,
                                num_epochs, num_steps, lr, clipping_theta,
                                batch_size, pred_period, pred_len, prefixes):
    model.compile(
        optimizer='adam',  # keras.optimizers.SGD(learning_rate=lr, momentum=0, decay=0, clipvalue=1),
        loss=keras.losses.categorical_crossentropy)

    for epoch in range(num_epochs):
        data_iter = data_iter_consecutive(corpus_indices, batch_size, num_steps)
        for X, Y in data_iter:
            x = keras.utils.to_categorical(X, vocab_size)
            y = keras.utils.to_categorical(Y[:, -1], vocab_size)
            # print(x.shape, y.shape)
            model.train_on_batch(x.reshape(batch_size, num_steps, vocab_size), y)

        # print(epoch, pred_period)
        if (epoch + 1) % pred_period == 0:
            for prefix in prefixes:
                print(' -', predict_rnn_gluon(
                    prefix, pred_len, model, vocab_size, idx_to_char,
                    char_to_idx, num_steps))

