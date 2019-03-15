#####
# To deal with random initializations
from numpy.random import seed

seed(1)
from tensorflow import set_random_seed

set_random_seed(2)
#####

from keras.layers import Input, Dense, LSTM, CuDNNLSTM, Activation, Dropout, TimeDistributed, Bidirectional
from keras.models import Model
from keras.models import Sequential
from keras.preprocessing import sequence
from keras.utils import plot_model
from keras.wrappers.scikit_learn import KerasClassifier
from keras_tools.attention_layers import Attention, AttentionWithContext
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import LabelEncoder

import copy
import keras
import keras_tools.validation as metrics
import numpy as np
import os
import pandas


# define baseline model
def baseline_model(timesteps, data_dim, output, dropout=None, return_sequences=False, gpu=True):
    # expected input_data data shape: (batch_size, timesteps, data_dim)
    # create model
    # def prepare_model(timesteps, data_dim, num_classes):
    model = Sequential()
    if gpu:
        model.add(CuDNNLSTM(20, return_sequences=return_sequences,
                            input_shape=(timesteps, data_dim)))  # returns a sequence of vectors of dimension 32
    else:
        model.add(LSTM(20, return_sequences=return_sequences,
                       input_shape=(timesteps, data_dim)))  # returns a sequence of vectors of dimension 32
    # model.add(CuDNNLSTM(32, return_sequences=True))  # returns a sequence of vectors of dimension 32
    # model.add(CuDNNLSTM(32))  # return a single vector of dimension 32
    # model.add(Dense(1, activation='sigmoid'))
    # compile model
    if dropout is float:
        model.add(Dropout(dropout))
    model.add(Dense(output, kernel_initializer="normal", activation="sigmoid"))
    # model.add(Activation('softmax'))
    model.compile(loss='binary_crossentropy',
                  optimizer='adam',
                  metrics=['accuracy'])
    return model
    # return prepare_model(timesteps, data_dim, num_classes)


# define baseline model
def baseline_model_wrapped(timesteps, data_dim, output, dropout=None, return_sequences=False, gpu=True):
    # expected input_data data shape: (batch_size, timesteps, data_dim)
    # create model
    def prepare_model(timesteps, data_dim, output, dropout, return_sequences, gpu):
        model = Sequential()
        if gpu:
            model.add(CuDNNLSTM(20, return_sequences=return_sequences,
                                input_shape=(timesteps, data_dim)))  # returns a sequence of vectors of dimension 32
        else:
            model.add(LSTM(20, return_sequences=return_sequences,
                           input_shape=(timesteps, data_dim)))  # returns a sequence of vectors of dimension 32
        # model.add(CuDNNLSTM(32, return_sequences=True))  # returns a sequence of vectors of dimension 32
        # model.add(CuDNNLSTM(32))  # return a single vector of dimension 32
        # model.add(Dense(1, activation='sigmoid'))
        # compile model
        if dropout is float:
            model.add(Dropout(dropout))
        model.add(Dense(output, kernel_initializer="normal", activation="sigmoid"))
        # model.add(Activation('softmax'))
        model.compile(loss='binary_crossentropy',
                      optimizer='adam',
                      metrics=['accuracy'])
        return model

    return prepare_model(timesteps, data_dim, output, dropout, return_sequences, gpu)


def basic_binary_blstm(input_data):
    # Input can be either a folder containing csv files or a .npy file
    if input_data.endswith(".npy"):
        loaded_array = np.load(input_data)
        X = loaded_array[0]
        Y = loaded_array[1]
    else:
        classes = sorted([f for f in os.listdir(input_data)
                          if os.path.isdir(os.path.join(input_data, f)) and not f.startswith('.')],
                         key=lambda f: f.lower())
        X = []
        Y = []
        sequence_lengths = []
        for class_name in classes:
            files = sorted([f for f in os.listdir(os.path.join(input_data, class_name))
                            if os.path.isfile(os.path.join(input_data, class_name, f)) and not f.startswith('.')
                            and f.endswith(".csv")], key=lambda f: f.lower())
            for file in files:
                df = pandas.read_csv(os.path.join(input_data, class_name, file))
                values = df.values
                nan_inds = np.where(np.isnan(values))
                values[nan_inds] = 0
                inf_inds = np.where(np.isinf(values))
                values[inf_inds] = np.sign(values[inf_inds])
                X.append(values)
                sequence_lengths.append(len(df.values))
                Y.append(class_name)
        sequence_lengths = np.array(sequence_lengths)
        avg_length = int(sum(sequence_lengths) / len(sequence_lengths))
        X = np.array(X)
        X = sequence.pad_sequences(X, maxlen=avg_length, dtype="float64")
        Y = np.array(Y)
        encoder = LabelEncoder()
        encoder.fit(Y)
        Y = encoder.transform(Y)
        # Y = np_utils.to_categorical(Y)
        # Y = [copy.deepcopy(Y.reshape(-1,1)) for i in range(X.shape[1])]
        # Y = np.array(Y)

    model = baseline_model(X.shape[1], X.shape[2], 1, None, False,
                           False)  # 1 for one class only (binary classification)
    model.summary()
    print("Initial parameters:")
    weights1 = model.layers[0].get_weights()
    print(weights1)
    pred_labels1 = model.predict_classes(X)
    for i in range(len(Y)):
        print("Predicted: %s, Real: %s" % (pred_labels1[i], Y[i]))
    a = 0
    model.fit(X, Y, epochs=50, batch_size=8, verbose=1, validation_split=0.1)
    print("Trained parameters:")
    weights2 = model.layers[0].get_weights()
    print(weights2)
    pred_labels2 = model.predict_classes(X)
    for i in range(len(Y)):
        print("Predicted: %s, Real: %s" % (pred_labels2[i], Y[i]))
    a = 0


def basic_binary_blstm_cv(input_data):
    # Input can be either a folder containing csv files or a .npy file
    if input_data.endswith(".npy"):
        loaded_array = np.load(input_data)
        X = loaded_array[0]
        Y = loaded_array[1]
    else:
        classes = sorted([f for f in os.listdir(input_data)
                          if os.path.isdir(os.path.join(input_data, f)) and not f.startswith('.')],
                         key=lambda f: f.lower())
        X = []
        Y = []
        sequence_lengths = []
        for class_name in classes:
            files = sorted([f for f in os.listdir(os.path.join(input_data, class_name))
                            if os.path.isfile(os.path.join(input_data, class_name, f)) and not f.startswith('.')
                            and f.endswith(".csv")], key=lambda f: f.lower())
            for file in files:
                df = pandas.read_csv(os.path.join(input_data, class_name, file))
                values = df.values
                nan_inds = np.where(np.isnan(values))
                values[nan_inds] = 0
                inf_inds = np.where(np.isinf(values))
                values[inf_inds] = np.sign(values[inf_inds])
                X.append(values)
                sequence_lengths.append(len(df.values))
                Y.append(class_name)
        sequence_lengths = np.array(sequence_lengths)
        avg_length = int(sum(sequence_lengths) / len(sequence_lengths))
        X = np.array(X)
        X = sequence.pad_sequences(X, maxlen=avg_length, dtype="float64")
        Y = np.array(Y)
        encoder = LabelEncoder()
        encoder.fit(Y)
        Y = encoder.transform(Y)
        # Y = np_utils.to_categorical(Y)
        # Y = [copy.deepcopy(Y.reshape(-1,1)) for i in range(X.shape[1])]
        # Y = np.array(Y)

    seed = 8

    classifier = KerasClassifier(build_fn=create_basic_blstm, timesteps=X.shape[1], data_dim=X.shape[2], output=1,
                                 dropout=None, gpu=False, epochs=50, batch_size=8, verbose=1)
    folds = StratifiedKFold(n_splits=10, shuffle=True, random_state=seed)
    results = cross_val_score(classifier, X, Y, cv=folds, verbose=1)
    print("Result: %.2f%% (%.2f%%)" % (results.mean() * 100, results.std() * 100))
    # model.summary()
    # print("Initial parameters:")
    # weights1 = model.layers[0].get_weights()
    # print(weights1)
    # pred_labels1 = model.predict_classes(X)
    # for i in range(len(Y)):
    #     print("Predicted: %s, Real: %s" % (pred_labels1[i], Y[i]))
    # a = 0
    # model.fit(X, Y, epochs=50, batch_size=8, verbose=1, validation_split=0.1)
    # print("Trained parameters:")
    # weights2 = model.layers[0].get_weights()
    # print(weights2)
    # pred_labels2 = model.predict_classes(X)
    # for i in range(len(Y)):
    #     print("Predicted: %s, Real: %s" % (pred_labels2[i], Y[i]))
    # a = 0


def create_basic_blstm(hu=20, timesteps=1, data_dim=1, output=1, dropout=None, gpu=True):
    # expected input_data data shape: (batch_size, timesteps, data_dim)
    # create model
    model = Sequential()
    if gpu:
        model.add(Bidirectional(CuDNNLSTM(hu), input_shape=(timesteps, data_dim)))  # returns a sequence of vectors of dimension 32
    else:
        model.add(Bidirectional(LSTM(hu), input_shape=(timesteps, data_dim)))  # returns a sequence of vectors of dimension 32
    if dropout is float:
        model.add(Dropout(dropout))
    model.add(Dense(output, kernel_initializer="normal", activation="sigmoid"))
    model.compile(loss='binary_crossentropy',
                  optimizer='adam',
                  metrics=['accuracy'])
    return model


def create_basic_blstm_double_dense(hu=20, timesteps=1, data_dim=1, output=1, dropout=None, gpu=True):
    # expected input_data data shape: (batch_size, timesteps, data_dim)
    # create model
    model = Sequential()
    if gpu:
        model.add(Bidirectional(CuDNNLSTM(hu), input_shape=(timesteps, data_dim)))  # returns a sequence of vectors of dimension 32
    else:
        model.add(Bidirectional(LSTM(hu), input_shape=(timesteps, data_dim)))  # returns a sequence of vectors of dimension 32
    if dropout is float:
        model.add(Dropout(dropout))
    model.add(Dense(int(hu/2)))
    model.add(Dense(output, kernel_initializer="normal", activation="sigmoid"))
    model.compile(loss='binary_crossentropy',
                  optimizer='adam',
                  metrics=['accuracy'])
    return model


def create_model():
    model = Sequential()
    model.add(LSTM(20, return_sequences=False,
                   input_shape=(2799, 75)))  # returns a sequence of vectors of dimension 32
    model.add(Dense(1, kernel_initializer="normal", activation="sigmoid"))
    model.compile(loss='binary_crossentropy',
                  optimizer='adam',
                  metrics=['accuracy'])
    return model


def create_attention_blstm(hu=20, timesteps=1, data_dim=1, output=1, dropout=None, gpu=True):
    # expected input_data data shape: (batch_size, timesteps, data_dim)
    # create model
    model = Sequential()
    if gpu:
        model.add(Bidirectional(CuDNNLSTM(hu,
                            return_sequences=True), input_shape=(timesteps, data_dim)))  # returns a sequence of vectors of dimension 32
    else:
        model.add(Bidirectional(LSTM(hu,
                       return_sequences=True), input_shape=(timesteps, data_dim)))  # returns a sequence of vectors of dimension 32
    if dropout is float:
        model.add(Dropout(dropout))
    model.add(Attention())
    model.add(Dense(output, kernel_initializer="normal", activation="sigmoid"))
    model.compile(loss='binary_crossentropy',
                  optimizer='adam',
                  metrics=['accuracy'])
    return model


def create_attention_context_blstm(hu=20, timesteps=1, data_dim=1, output=1, dropout=None, gpu=True):
    # expected input_data data shape: (batch_size, timesteps, data_dim)
    # create model
    model = Sequential()
    if gpu:
        model.add(Bidirectional(CuDNNLSTM(hu,
                            return_sequences=True), input_shape=(timesteps, data_dim)))  # returns a sequence of vectors of dimension 32
    else:
        model.add(Bidirectional(LSTM(hu,
                       return_sequences=True), input_shape=(timesteps, data_dim)))  # returns a sequence of vectors of dimension 32
    if dropout is float:
        model.add(Dropout(dropout))
    model.add(AttentionWithContext())
    model.add(Dense(output, kernel_initializer="normal", activation="sigmoid"))
    model.compile(loss='binary_crossentropy',
                  optimizer='adam',
                  metrics=['accuracy'])
    return model


def create_multidata_basic_blstm(input_shapes, hu=20, output=1, dropout=None, gpu=True):
    # expected input_data data shape: (timesteps, data_dim)
    seq_shape = []
    for shape in input_shapes:
        seq_shape.append(shape)
    n = len(input_shapes)

    # Define n input_data sequences
    seq = []
    for i in range(n):
        seq_i = Input(seq_shape[i])
        seq.append(seq_i)
    cat = keras.layers.concatenate(seq, axis=-1)
    # Create model
    if gpu:
        blstm = Bidirectional(CuDNNLSTM(hu), input_shape=(input_shapes[0][0], input_shapes[0][1] + input_shapes[1][1]))(cat)
    else:
        blstm = Bidirectional(LSTM(hu), input_shape=(input_shapes[0][0], input_shapes[0][1] + input_shapes[1][1]))(cat)
    if dropout is float:
        blstm = Dropout(dropout)(blstm)
    dense = Dense(output, kernel_initializer="normal", activation="sigmoid")(blstm)
    model = Model(seq, dense)
    model.compile(loss='binary_crossentropy',
                  optimizer='adam',
                  metrics=['accuracy'])
    return model


def create_multidata_basic_blstm_double_dense(input_shapes, hu=20, output=1, dropout=None, gpu=True):
    # expected input_data data shape: (timesteps, data_dim)
    seq_shape = []
    for shape in input_shapes:
        seq_shape.append(shape)
    n = len(input_shapes)

    # Define n input_data sequences
    seq = []
    for i in range(n):
        seq_i = Input(seq_shape[i])
        seq.append(seq_i)
    cat = keras.layers.concatenate(seq, axis=-1)
    # Create model
    if gpu:
        blstm = Bidirectional(CuDNNLSTM(hu), input_shape=(input_shapes[0][0], input_shapes[0][1] + input_shapes[1][1]))(cat)
    else:
        blstm = Bidirectional(LSTM(hu), input_shape=(input_shapes[0][0], input_shapes[0][1] + input_shapes[1][1]))(cat)
    if dropout is float:
        blstm = Dropout(dropout)(blstm)
    dense_1 = Dense(int(hu/2))(blstm)
    dense_2 = Dense(output, kernel_initializer="normal", activation="sigmoid")(dense_1)
    model = Model(seq, dense_2)
    model.compile(loss='binary_crossentropy',
                  optimizer='adam',
                  metrics=['accuracy'])
    return model


def create_multidata_attention_blstm(input_shapes, hu=20, output=1, dropout=None, gpu=True):
    # expected input_data data shape: (num_streams, timesteps, data_dim)
    seq_shape = []
    for shape in input_shapes:
        seq_shape.append(shape)
    n = len(input_shapes)

    # Define n input_data sequences
    seq = []
    for i in range(n):
        seq_i = Input(seq_shape[i])
        seq.append(seq_i)
    cat = keras.layers.concatenate(seq, axis=-1)
    # Create model
    if gpu:
        blstm = Bidirectional(CuDNNLSTM(hu, return_sequences=True), input_shape=(input_shapes[0][0], input_shapes[0][1] + input_shapes[1][1]))(cat)
    else:
        blstm = Bidirectional(LSTM(hu, return_sequences=True), input_shape=(input_shapes[0][0], input_shapes[0][1] + input_shapes[1][1]))(cat)
    if dropout is float:
        blstm = Dropout(dropout)(blstm)
    result, attention = Attention(return_attention=True)(blstm)
    dense = Dense(output, kernel_initializer="normal", activation="sigmoid")(result)
    model = Model(seq, dense)
    model.compile(loss='binary_crossentropy',
                  optimizer='adam',
                  metrics=['accuracy'])
    return model


def create_multidata_attention_context_blstm(input_shapes, hu=20, output=1, dropout=None, gpu=True):
    # expected input_data data shape: (num_streams, timesteps, data_dim)
    seq_shape = []
    for shape in input_shapes:
        seq_shape.append(shape)
    n = len(input_shapes)

    # Define n input_data sequences
    seq = []
    for i in range(n):
        seq_i = Input(seq_shape[i])
        seq.append(seq_i)
    cat = keras.layers.concatenate(seq, axis=-1)
    # Create model
    if gpu:
        blstm = Bidirectional(CuDNNLSTM(hu, return_sequences=True), input_shape=(input_shapes[0][0], input_shapes[0][1] + input_shapes[1][1]))(cat)
    else:
        blstm = Bidirectional(LSTM(hu, return_sequences=True), input_shape=(input_shapes[0][0], input_shapes[0][1] + input_shapes[1][1]))(cat)
    if dropout is float:
        blstm = Dropout(dropout)(blstm)
    result, attention = AttentionWithContext(return_attention=True)(blstm)
    dense = Dense(output, kernel_initializer="normal", activation="sigmoid")(result)
    model = Model(seq, dense)
    model.compile(loss='binary_crossentropy',
                  optimizer='adam',
                  metrics=['accuracy'])
    return model


def create_multistream_basic_blstm(input_shapes, hu=20, output=1, dropout=None, gpu=True):
    # expected input_data data shape: (num_streams, timesteps, data_dim)
    seq_shape = []
    for shape in input_shapes:
        seq_shape.append(shape)
    n = len(input_shapes)

    # Create a LSTM for each stream
    seq = []
    blstms = []
    for i in range(n):
        input_data = Input(seq_shape[i])
        if gpu:
            blstm = Bidirectional(CuDNNLSTM(hu), input_shape=input_shapes[i])(input_data)
        else:
            blstm = Bidirectional(LSTM(hu), input_shape=input_shapes[i])(input_data)
        if dropout is float:
            blstm = Dropout(dropout)(blstm)
        seq.append(input_data)
        blstms.append(blstm)
    # Concatenate independent streams
    cat = keras.layers.concatenate(blstms, axis=-1)
    dense = Dense(output, kernel_initializer="normal", activation="sigmoid")(cat)
    model = Model(seq, dense)
    model.compile(loss='binary_crossentropy',
                  optimizer='adam',
                  metrics=['accuracy'])
    return model


def create_multistream_basic_blstm_double_dense(input_shapes, hu=20, output=1, dropout=None, gpu=True):
    # expected input_data data shape: (num_streams, timesteps, data_dim)
    seq_shape = []
    for shape in input_shapes:
        seq_shape.append(shape)
    n = len(input_shapes)

    # Create a LSTM for each stream
    seq = []
    blstms = []
    for i in range(n):
        input_data = Input(seq_shape[i])
        if gpu:
            blstm = Bidirectional(CuDNNLSTM(hu), input_shape=input_shapes[i])(input_data)
        else:
            blstm = Bidirectional(LSTM(hu), input_shape=input_shapes[i])(input_data)
        if dropout is float:
            blstm = Dropout(dropout)(blstm)
        seq.append(input_data)
        blstms.append(blstm)
    # Concatenate independent streams
    cat = keras.layers.concatenate(blstms, axis=-1)
    dense_1 = Dense(int(hu / 2))(cat)
    dense_2 = Dense(output, kernel_initializer="normal", activation="sigmoid")(dense_1)
    model = Model(seq, dense_2)
    model.compile(loss='binary_crossentropy',
                  optimizer='adam',
                  metrics=['accuracy'])
    return model


def create_multistream_attention_blstm(input_shapes, hu=20, output=1, dropout=None, gpu=True):
    # expected input_data data shape: (num_streams, timesteps, data_dim)
    seq_shape = []
    for shape in input_shapes:
        seq_shape.append(shape)
    n = len(input_shapes)

    # Create a LSTM for each stream
    seq = []
    blstms = []
    for i in range(n):
        input_data = Input(seq_shape[i])
        if gpu:
            blstm = Bidirectional(CuDNNLSTM(hu, return_sequences=True), input_shape=input_shapes[i])(input_data)
        else:
            blstm = Bidirectional(LSTM(hu, return_sequences=True), input_shape=input_shapes[i])(input_data)
        if dropout is float:
            blstm = Dropout(dropout)(blstm)
        # Add attention in each stream
        result, attention = Attention(return_attention=True)(blstm)
        seq.append(input_data)
        blstms.append(result)
    # Concatenate independent streams
    cat = keras.layers.concatenate(blstms, axis=-1)
    dense = Dense(output, kernel_initializer="normal", activation="sigmoid")(cat)
    model = Model(seq, dense)
    model.compile(loss='binary_crossentropy',
                  optimizer='adam',
                  metrics=['accuracy'])
    return model


def create_multistream_attention_context_blstm(input_shapes, hu=20, output=1, dropout=None, gpu=True):
    # expected input_data data shape: (num_streams, timesteps, data_dim)
    seq_shape = []
    for shape in input_shapes:
        seq_shape.append(shape)
    n = len(input_shapes)

    # Create a LSTM for each stream
    seq = []
    blstms = []
    for i in range(n):
        input_data = Input(seq_shape[i])
        if gpu:
            blstm = Bidirectional(CuDNNLSTM(hu, return_sequences=True), input_shape=input_shapes[i])(input_data)
        else:
            blstm = Bidirectional(LSTM(hu, return_sequences=True), input_shape=input_shapes[i])(input_data)
        if dropout is float:
            blstm = Dropout(dropout)(blstm)
        # Add attention in each stream
        result, attention = AttentionWithContext(return_attention=True)(blstm)
        seq.append(input_data)
        blstms.append(result)
    # Concatenate independent streams
    cat = keras.layers.concatenate(blstms, axis=-1)
    dense = Dense(output, kernel_initializer="normal", activation="sigmoid")(cat)
    model = Model(seq, dense)
    model.compile(loss='binary_crossentropy',
                  optimizer='adam',
                  metrics=['accuracy'])
    return model


def dense_binary_blstm(input_data):
    # Input can be either a folder containing csv files or a .npy file
    if input_data.endswith(".npy"):
        loaded_array = np.load(input_data)
        X = loaded_array[0]
        Y = loaded_array[1]
    else:
        classes = sorted([f for f in os.listdir(input_data)
                          if os.path.isdir(os.path.join(input_data, f)) and not f.startswith('.')],
                         key=lambda f: f.lower())
        X = []
        Y = []
        sequence_lengths = []
        for class_name in classes:
            files = sorted([f for f in os.listdir(os.path.join(input_data, class_name))
                            if os.path.isfile(os.path.join(input_data, class_name, f)) and not f.startswith('.')
                            and f.endswith(".csv")], key=lambda f: f.lower())
            for file in files:
                df = pandas.read_csv(os.path.join(input_data, class_name, file))
                X.append(df.values[:, 1:])
                sequence_lengths.append(len(df.values))
                Y.append(class_name)
        sequence_lengths = np.array(sequence_lengths)
        avg_length = int(sum(sequence_lengths) / len(sequence_lengths))
        X = np.array(X)
        X = sequence.pad_sequences(X, maxlen=avg_length)
        Y = np.array(Y)
        encoder = LabelEncoder()
        encoder.fit(Y)
        Y = encoder.transform(Y)
        # Y = np_utils.to_categorical(Y)
        # Y = [copy.deepcopy(Y.reshape(-1,1)) for i in range(X.shape[1])]
        # Y = np.array(Y)

    model = baseline_model(X.shape[1], X.shape[2], 1, 0.5, False)  # 1 for one class only (binary classification)
    model.summary()
    pred_labels = model.predict(X)
    for i in range(len(Y)):
        print("Predicted: %s, Real: %s" % (pred_labels[i], Y[i]))
    a = 0
    model.fit(X, Y, epochs=5, batch_size=32, verbose=1, validation_split=0.0)
    pred_labels = model.predict(X)
    for i in range(len(Y)):
        print("Predicted: %s, Real: %s" % (pred_labels[i], Y[i]))
    a = 0


def get_data(input_data, padding="avg"):
    classes = sorted([f for f in os.listdir(input_data)
                      if os.path.isdir(os.path.join(input_data, f)) and not f.startswith('.')],
                     key=lambda f: f.lower())
    X = []
    Y = []
    sequence_lengths = []
    for class_name in classes:
        files = sorted([f for f in os.listdir(os.path.join(input_data, class_name))
                        if os.path.isfile(os.path.join(input_data, class_name, f)) and not f.startswith('.')
                        and f.endswith(".csv")], key=lambda f: f.lower())
        for file in files:
            df = pandas.read_csv(os.path.join(input_data, class_name, file))
            values = df.values
            nan_inds = np.where(np.isnan(values))
            values[nan_inds] = 0
            inf_inds = np.where(np.isinf(values))
            values[inf_inds] = np.sign(values[inf_inds])
            X.append(values)
            sequence_lengths.append(len(df.values))
            Y.append(class_name)
    sequence_lengths = np.array(sequence_lengths)
    if padding == "avg":
        length = int(sum(sequence_lengths) / len(sequence_lengths))
    elif padding == "max":
        length = max(sequence_lengths)
    elif padding == "min":
        length = min(sequence_lengths)
    X = np.array(X)
    X = sequence.pad_sequences(X, maxlen=length, dtype="float64")
    Y = np.array(Y)
    encoder = LabelEncoder()
    encoder.fit(Y)
    Y = encoder.transform(Y)
    return X, Y


def test(gpu=False):
    seq_length = 5
    X = [[i + j for j in range(seq_length)] for i in range(100)]
    X_simple = [[i for i in range(4, 104)]]
    X = np.array(X)
    X_simple = np.array(X_simple)

    y = [[i + (i - 1) * .5 + (i - 2) * .2 + (i - 3) * .1 for i in range(4, 104)]]
    y = np.array(y)
    X_simple = X_simple.reshape((100, 1))
    X = X.reshape((100, 5, 1))
    y = y.reshape((100, 1))

    model = Sequential()
    if gpu:
        model.add(CuDNNLSTM(8, input_shape=(5, 1), return_sequences=False))
    else:
        model.add(LSTM(8, input_shape=(5, 1), return_sequences=False))
    model.add(Dense(2, kernel_initializer="normal", activation="linear"))
    model.add(Dense(1, kernel_initializer="normal", activation="linear"))
    model.compile(loss="mse", optimizer="adam", metrics=["accuracy"])
    model.fit(X, y, epochs=2000, batch_size=5, validation_split=0.05, verbose=1);
    scores = model.evaluate(X, y, verbose=1, batch_size=5)
    print("Accurracy: {}".format(scores[1]))
    import matplotlib.pyplot as plt
    predict = model.predict(X)
    plt.plot(y, predict - y, 'C2')
    plt.ylim(ymax=3, ymin=-3)
    plt.show()


def stacked_h_binary_blstm(input_data):
    # Input can be either a folder containing csv files or a .npy file
    if input_data.endswith(".npy"):
        loaded_array = np.load(input_data)
        X = loaded_array[0]
        Y = loaded_array[1]
    else:
        X, Y = get_data(input_data)

    seed = 8

    classifier = KerasClassifier(build_fn=create_basic_blstm, timesteps=X.shape[1], data_dim=X.shape[2], output=1,
                                 dropout=None, gpu=False, epochs=50, batch_size=8, verbose=1)
    folds = StratifiedKFold(n_splits=10, shuffle=True, random_state=seed)
    results = cross_val_score(classifier, X, Y, cv=folds, verbose=1)
    print("Result: %.2f%% (%.2f%%)" % (results.mean() * 100, results.std() * 100))


def standard_vs_binary(input_data, cv=10):
    # Input can be either a folder containing csv files or a .npy file
    if input_data.endswith(".npy"):
        loaded_array = np.load(input_data)
        X = loaded_array[0]
        Y = loaded_array[1]
    else:
        X, Y = get_data(input_data)

    seed = 8

    hu = 200
    dropout = 0.5
    epochs = 100
    batch_size = 32
    gpu = True
    classifier_basic = KerasClassifier(build_fn=create_basic_blstm, hu=hu, timesteps=X.shape[1], data_dim=X.shape[2], output=1,
                                       dropout=dropout, gpu=gpu, epochs=epochs, batch_size=batch_size, verbose=1)
    classifier_double_dense = KerasClassifier(build_fn=create_basic_blstm, hu=hu, timesteps=X.shape[1], data_dim=X.shape[2],
                                              output=1,
                                              dropout=dropout, gpu=gpu, epochs=epochs, batch_size=batch_size, verbose=1)
    classifier_attention = KerasClassifier(build_fn=create_attention_blstm, hu=hu, timesteps=X.shape[1], data_dim=X.shape[2],
                                           output=1,
                                           dropout=dropout, gpu=gpu, epochs=epochs, batch_size=batch_size, verbose=1)
    classifier_attention_context = KerasClassifier(build_fn=create_attention_context_blstm, hu=hu, timesteps=X.shape[1],
                                                   data_dim=X.shape[2],
                                                   output=1,
                                                   dropout=dropout, gpu=gpu, epochs=epochs, batch_size=batch_size, verbose=1)
    if cv is int:
        folds = StratifiedKFold(n_splits=cv, shuffle=True, random_state=seed)
    else:
        folds = cv
    results_basic = cross_val_score(classifier_basic, X, Y, cv=folds, verbose=1)
    results_double_dense = cross_val_score(classifier_double_dense, X, Y, cv=folds, verbose=1)  # , n_jobs=-1)
    results_attention = cross_val_score(classifier_attention, X, Y, cv=folds, verbose=1)  # , n_jobs=-1)
    results_attention_context = cross_val_score(classifier_attention_context, X, Y, cv=folds, verbose=1)  # , n_jobs=-1)
    print("Database: %s" % os.path.split(input_data)[-2])
    print("Data: %s" % os.path.split(input_data)[-1])
    print("Hidden units: %s, Epochs: %s, Batch Size: %s, Dropout: %s" % (hu, epochs, batch_size, dropout))
    print("Result basic: %.2f%% (%.2f%%)" % (results_basic.mean() * 100, results_basic.std() * 100))
    print("Result double dense: %.2f%% (%.2f%%)" % (results_double_dense.mean() * 100, results_basic.std() * 100))
    print("Result attention: %.2f%% (%.2f%%)" % (results_attention.mean() * 100, results_attention.std() * 100))
    print("Result attention with context: %.2f%% (%.2f%%)" % (
        results_attention_context.mean() * 100, results_attention_context.std() * 100))

    with open(os.path.join(os.path.split(input_data)[-2], "keras_results_%s.txt" % os.path.split(input_data)[-1]), "w+") as output:
        output.write("Database: %s\n" % os.path.split(input_data)[-2])
        output.write("Data: %s\n" % os.path.split(input_data)[-1])
        output.write("Hidden units: %s, Epochs: %s, Batch Size: %s, Dropout: %s\n" % (hu, epochs, batch_size, dropout))
        output.write("Result basic: %.2f%% (%.2f%%)\n" % (results_basic.mean() * 100, results_basic.std() * 100))
        output.write("Result double dense: %.2f%% (%.2f%%)\n" % (results_double_dense.mean() * 100, results_basic.std() * 100))
        output.write("Result attention: %.2f%% (%.2f%%)\n" % (results_attention.mean() * 100, results_attention.std() * 100))
        output.write("Result attention with context: %.2f%% (%.2f%%)\n" % (
            results_attention_context.mean() * 100, results_attention_context.std() * 100))


def modalities(inputs, cv=10):
    # Input can be either a folder containing csv files or a .npy file
    if inputs is str:
        if inputs.endswith(".npy"):
            loaded_array = np.load(inputs)
            X = loaded_array[0]
            Y = loaded_array[1]
    else:
        X = []
        Y = []
        for stream_idx in range(len(inputs)):
            X_idx, Y_idx = get_data(inputs[stream_idx])
            X.append(X_idx)
            Y.append(Y_idx)

    max_length = 0
    for x in X:
        length = x.shape[-2]
        if length > max_length:
            max_length = length

    for idx, x in enumerate(X):
        X[idx] = sequence.pad_sequences(x, maxlen=max_length, dtype="float64")

    hu = 200
    dropout = None
    epochs = 100
    batch_size = 32
    gpu = True
    input_shapes = [x.shape[1:] for x in X]
    if cv is int:
        folds = StratifiedKFold(n_splits=cv, shuffle=True, random_state=10)
    else:
        folds = cv

    for stream_idx in range(len(inputs)):
        classifier_basic = KerasClassifier(build_fn=create_basic_blstm, hu=hu, timesteps=X[stream_idx].shape[1], data_dim=X[stream_idx].shape[2],
                                           output=1,
                                           dropout=dropout, gpu=gpu, epochs=epochs, batch_size=batch_size, verbose=2)
        classifier_double_dense = KerasClassifier(build_fn=create_basic_blstm, hu=hu, timesteps=X[stream_idx].shape[1],
                                                  data_dim=X[stream_idx].shape[2],
                                                  output=1,
                                                  dropout=dropout, gpu=gpu, epochs=epochs, batch_size=batch_size,
                                                  verbose=2)
        classifier_attention = KerasClassifier(build_fn=create_attention_blstm, hu=hu, timesteps=X[stream_idx].shape[1],
                                               data_dim=X[stream_idx].shape[2],
                                               output=1,
                                               dropout=dropout, gpu=gpu, epochs=epochs, batch_size=batch_size,
                                               verbose=2)
        classifier_attention_context = KerasClassifier(build_fn=create_attention_context_blstm, hu=hu,
                                                       timesteps=X[stream_idx].shape[1],
                                                       data_dim=X[stream_idx].shape[2],
                                                       output=1,
                                                       dropout=dropout, gpu=gpu, epochs=epochs, batch_size=batch_size,
                                                       verbose=2)

        results_basic = cross_val_score(classifier_basic, X[stream_idx], Y[stream_idx], scoring="roc_auc", cv=folds, verbose=1)  # , n_jobs=-1)
        results_double_dense = cross_val_score(classifier_double_dense, X[stream_idx], Y[stream_idx], scoring="roc_auc", cv=folds, verbose=1)  # , n_jobs=-1)
        results_attention = cross_val_score(classifier_attention, X[stream_idx], Y[stream_idx], scoring="roc_auc", cv=folds, verbose=1)  # , n_jobs=-1)
        results_attention_context = cross_val_score(classifier_attention_context, X[stream_idx], Y[stream_idx], scoring="roc_auc", cv=folds, verbose=1)  # , n_jobs=-1)
        print("Database: %s" % os.path.split(inputs[stream_idx])[-2])
        print("Data: %s" % os.path.split(inputs[stream_idx])[-1])
        print("Hidden units: %s, Epochs: %s, Batch Size: %s, Dropout: %s" % (hu, epochs, batch_size, dropout))
        print("Result basic: %.2f%% (%.2f%%)" % (results_basic.mean() * 100, results_basic.std() * 100))
        print("Result double dense: %.2f%% (%.2f%%)" % (results_double_dense.mean() * 100, results_basic.std() * 100))
        print("Result attention: %.2f%% (%.2f%%)" % (results_attention.mean() * 100, results_attention.std() * 100))
        print("Result attention with context: %.2f%% (%.2f%%)" % (
            results_attention_context.mean() * 100, results_attention_context.std() * 100))

        with open(os.path.join(os.path.split(inputs[stream_idx])[-2], "blstm_results_modalities.txt"), "a+") as output:
            output.write("Database: %s\n" % os.path.split(inputs[stream_idx])[-2])
            output.write("Data: %s\n" % os.path.split(inputs[stream_idx])[-1])
            output.write("Hidden units: %s, Epochs: %s, Batch Size: %s, Dropout: %s\n" % (hu, epochs, batch_size, dropout))
            output.write("Result basic: %.2f%% (%.2f%%)\n" % (results_basic.mean() * 100, results_basic.std() * 100))
            output.write("Result double dense: %.2f%% (%.2f%%)\n" % (results_double_dense.mean() * 100, results_basic.std() * 100))
            output.write("Result attention: %.2f%% (%.2f%%)\n" % (results_attention.mean() * 100, results_attention.std() * 100))
            output.write("Result attention with context: %.2f%% (%.2f%%)\n\n" % (
                results_attention_context.mean() * 100, results_attention_context.std() * 100))

    # Multidata
    classifier_basic = create_multidata_basic_blstm(hu=hu, input_shapes=input_shapes,
                                       output=1,
                                       dropout=dropout, gpu=gpu)
    classifier_double_dense = create_multidata_basic_blstm(hu=hu, input_shapes=input_shapes,
                                              output=1,
                                              dropout=dropout, gpu=gpu)
    classifier_attention = create_multidata_attention_blstm(hu=hu, input_shapes=input_shapes,
                                           output=1,
                                           dropout=dropout, gpu=gpu)
    classifier_attention_context = create_multidata_attention_context_blstm(hu=hu,
                                                   input_shapes=input_shapes,
                                                   output=1,
                                                   dropout=dropout, gpu=gpu)

    results_basic = metrics.cross_val_score(classifier_basic, X, Y, scoring="roc_auc", cv=folds, epochs=epochs, batch_size=batch_size, verbose=2)
    results_double_dense = metrics.cross_val_score(classifier_double_dense, X, Y, scoring="roc_auc", cv=folds, epochs=epochs, batch_size=batch_size, verbose=2)
    results_attention = metrics.cross_val_score(classifier_attention, X, Y, scoring="roc_auc", cv=folds, epochs=epochs, batch_size=batch_size, verbose=2)
    results_attention_context = metrics.cross_val_score(classifier_attention_context, X, Y, scoring="roc_auc", cv=folds, epochs=epochs, batch_size=batch_size, verbose=2)
    print("Database: %s" % os.path.split(inputs[0])[-2])
    print("Data: %s" % " + ".join([os.path.split(input_data)[-1] for input_data in inputs]))
    print("Hidden units: %s, Epochs: %s, Batch Size: %s, Dropout: %s" % (hu, epochs, batch_size, dropout))
    print("Result early fusion basic: %.2f%% (%.2f%%)" % (results_basic.mean() * 100, results_basic.std() * 100))
    print("Result early fusion double dense: %.2f%% (%.2f%%)" % (results_double_dense.mean() * 100, results_basic.std() * 100))
    print("Result early fusion attention: %.2f%% (%.2f%%)" % (results_attention.mean() * 100, results_attention.std() * 100))
    print("Result early fusion attention with context: %.2f%% (%.2f%%)" % (
        results_attention_context.mean() * 100, results_attention_context.std() * 100))

    with open(os.path.join(os.path.split(inputs[0])[-2], "blstm_results_modalities.txt"), "a+") as output:
        output.write("Database: %s\n" % os.path.split(inputs[0])[-2])
        output.write("Data: %s\n" % " + ".join([os.path.split(input_data)[-1] for input_data in inputs]))
        output.write("Hidden units: %s, Epochs: %s, Batch Size: %s, Dropout: %s\n" % (hu, epochs, batch_size, dropout))
        output.write("Result early fusion basic: %.2f%% (%.2f%%)\n" % (results_basic.mean() * 100, results_basic.std() * 100))
        output.write(
            "Result early fusion double dense: %.2f%% (%.2f%%)\n" % (results_double_dense.mean() * 100, results_basic.std() * 100))
        output.write(
            "Result early fusion attention: %.2f%% (%.2f%%)\n" % (results_attention.mean() * 100, results_attention.std() * 100))
        output.write("Result early fusion attention with context: %.2f%% (%.2f%%)\n\n" % (
            results_attention_context.mean() * 100, results_attention_context.std() * 100))

    # Multistream
    classifier_basic = create_multistream_basic_blstm(hu=hu, input_shapes=input_shapes,
                                                   output=1,
                                                   dropout=dropout, gpu=gpu)
    classifier_double_dense = create_multistream_basic_blstm(hu=hu, input_shapes=input_shapes,
                                                          output=1,
                                                          dropout=dropout, gpu=gpu)
    classifier_attention = create_multistream_attention_blstm(hu=hu, input_shapes=input_shapes,
                                                           output=1,
                                                           dropout=dropout, gpu=gpu)
    classifier_attention_context = create_multistream_attention_context_blstm(hu=hu,
                                                                           input_shapes=input_shapes,
                                                                           output=1,
                                                                           dropout=dropout, gpu=gpu)

    results_basic = metrics.cross_val_score(classifier_basic, X, Y, scoring="roc_auc", cv=folds, epochs=epochs,
                                            batch_size=batch_size, verbose=2)
    results_double_dense = metrics.cross_val_score(classifier_double_dense, X, Y, scoring="roc_auc", cv=folds,
                                                   epochs=epochs, batch_size=batch_size, verbose=2)
    results_attention = metrics.cross_val_score(classifier_attention, X, Y, scoring="roc_auc", cv=folds,
                                                epochs=epochs, batch_size=batch_size, verbose=2)
    results_attention_context = metrics.cross_val_score(classifier_attention_context, X, Y, scoring="roc_auc",
                                                        cv=folds, epochs=epochs, batch_size=batch_size, verbose=2)
    print("Database: %s" % os.path.split(inputs[0])[-2])
    print("Data: %s" % " + ".join([os.path.split(input_data)[-1] for input_data in inputs]))
    print("Hidden units: %s, Epochs: %s, Batch Size: %s, Dropout: %s" % (hu, epochs, batch_size, dropout))
    print("Result middle fusion basic: %.2f%% (%.2f%%)" % (results_basic.mean() * 100, results_basic.std() * 100))
    print("Result middle fusion double dense: %.2f%% (%.2f%%)" % (
    results_double_dense.mean() * 100, results_basic.std() * 100))
    print("Result middle fusion attention: %.2f%% (%.2f%%)" % (
    results_attention.mean() * 100, results_attention.std() * 100))
    print("Result middle fusion attention with context: %.2f%% (%.2f%%)" % (
        results_attention_context.mean() * 100, results_attention_context.std() * 100))

    with open(os.path.join(os.path.split(inputs[0])[-2], "blstm_results_modalities.txt"), "a+") as output:
        output.write("Database: %s\n" % os.path.split(inputs[0])[-2])
        output.write("Data: %s\n" % " + ".join([os.path.split(input_data)[-1] for input_data in inputs]))
        output.write("Hidden units: %s, Epochs: %s, Batch Size: %s, Dropout: %s\n" % (hu, epochs, batch_size, dropout))
        output.write(
            "Result middle fusion basic: %.2f%% (%.2f%%)\n" % (results_basic.mean() * 100, results_basic.std() * 100))
        output.write(
            "Result middle fusion double dense: %.2f%% (%.2f%%)\n" % (
            results_double_dense.mean() * 100, results_basic.std() * 100))
        output.write(
            "Result middle fusion attention: %.2f%% (%.2f%%)\n" % (
            results_attention.mean() * 100, results_attention.std() * 100))
        output.write("Result middle fusion attention with context: %.2f%% (%.2f%%)\n" % (
            results_attention_context.mean() * 100, results_attention_context.std() * 100))
