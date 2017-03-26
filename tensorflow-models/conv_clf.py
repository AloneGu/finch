import tensorflow as tf
from tensorflow.contrib.layers import batch_norm
import numpy as np
import math


class ConvClassifier:
    def __init__(self, img_h, img_w, n_out=2):
        self.img_h = img_h
        self.img_w = img_w
        self.n_out = n_out

        self.build_graph()
    # end constructor


    def build_graph(self):
        self.X = tf.placeholder(tf.float32, [None, self.img_h, self.img_w, 1])
        self.y = tf.placeholder(tf.float32, [None, self.n_out])

        self.W = {
            'wc1': tf.Variable(tf.random_normal([5, 5, 1, 32])), # 5x5 conv, 1 input, 32 outputs
            'wc2': tf.Variable(tf.random_normal([5, 5, 32, 64])), # 5x5 conv, 32 inputs, 64 outputs
            # fully connected
            'wd1': tf.Variable(tf.random_normal([int(self.img_h/4) * int(self.img_w/4) * 64, 1024])),
            'out': tf.Variable(tf.random_normal([1024, self.n_out])) # class prediction
        }
        self.b = {
            'bc1': tf.Variable(tf.random_normal([32])),
            'bc2': tf.Variable(tf.random_normal([64])),
            'bd1': tf.Variable(tf.random_normal([1024])),
            'out': tf.Variable(tf.random_normal([self.n_out]))
        }

        self.lr = tf.placeholder(tf.float32)
        self.keep_prob = tf.placeholder(tf.float32)

        self.pred = self.conv(self.X, self.W, self.b, self.keep_prob)
        self.loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=self.pred, labels=self.y))
        self.train_op = tf.train.AdamOptimizer(self.lr).minimize(self.loss)
        self.acc = tf.reduce_mean( tf.cast( tf.equal( tf.argmax(self.pred, 1), tf.argmax(self.y, 1) ), tf.float32 ) )

        self.sess = tf.Session()
        self.init = tf.global_variables_initializer()
    # end method build_graph


    def conv(self, X, W, b, keep_prob):
        conv1 = self.conv2d(X, W['wc1'], b['bc1'])       # convolution layer
        conv1 = self.maxpool2d(conv1, k=2)               # max pooling (down-sampling)

        conv2 = self.conv2d(conv1, W['wc2'], b['bc2'])   # convolution layer
        conv2 = self.maxpool2d(conv2, k=2)               # max pooling (down-sampling)

        # fully connected layer, reshape conv2 output to fit fully connected layer input
        fc1 = tf.reshape(conv2, [-1, W['wd1'].get_shape().as_list()[0]])
        fc1 = tf.nn.bias_add(tf.matmul(fc1, W['wd1']),b['bd1'])
        fc1 = tf.nn.relu(batch_norm(fc1))

        fc1 = tf.nn.dropout(fc1, keep_prob)

        # output, class prediction
        out = tf.nn.bias_add(tf.matmul(fc1, W['out']), b['out'])
        return out
    # end method conv


    def conv2d(self, X, W, b, strides=1):
        conv = tf.nn.conv2d(X, W, strides=[1, strides, strides, 1], padding='SAME')
        conv = tf.nn.bias_add(conv, b)
        return tf.nn.relu(batch_norm(conv))


    def maxpool2d(self, X, k=2):
        return tf.nn.max_pool(X, ksize=[1, k, k, 1], strides=[1, k, k, 1], padding='SAME')


    def fit(self, X, y, val_data=None, n_epoch=10, batch_size=32, keep_prob=0.5, en_exp_decay=True):
        if val_data is None:
            print("Train %d samples" % len(X))
        else:
            print("Train %d samples | Test %d samples" % (len(X), len(val_data[0])))
        log = {'loss':[], 'acc':[], 'val_loss':[], 'val_acc':[]}
        global_step = 0

        self.sess.run(self.init) # initialize all variables

        for epoch in range(n_epoch):
            # batch training
            i = 0
            for X_batch, y_batch in zip(self.gen_batch(X, batch_size), self.gen_batch(y, batch_size)):
                lr = self.get_lr(en_exp_decay, global_step, n_epoch, len(X), batch_size) 
                self.sess.run(self.train_op, feed_dict={self.X: X_batch, self.y: y_batch, self.lr: lr,
                                                        self.keep_prob: keep_prob})
                i += 1
                global_step += 1
                # compute training loss and acc
                loss, acc = self.sess.run([self.loss, self.acc], feed_dict={self.X: X_batch, self.y: y_batch,
                                                                            self.keep_prob: 1.0})
                if (i+1) % 100 == 0:
                    print ('Epoch [%d/%d], Step [%d/%d], LR: %.4f, Train loss: %.4f, Train acc: %.4f'
                           %(epoch+1, n_epoch, i+1, int(len(X)/batch_size), lr, loss, acc))
            if val_data is not None:
                # go through test dara, compute validation loss and acc
                val_loss_list, val_acc_list = [], []
                for X_test_batch, y_test_batch in zip(self.gen_batch(val_data[0], batch_size),
                                                    self.gen_batch(val_data[1], batch_size)):
                    v_loss, v_acc = self.sess.run([self.loss, self.acc], feed_dict={self.X: X_test_batch,
                                                                                    self.y: y_test_batch,
                                                                                    self.keep_prob: 1.0})
                    val_loss_list.append(v_loss)
                    val_acc_list.append(v_acc)
                val_loss, val_acc = self.list_avg(val_loss_list), self.list_avg(val_acc_list)

            # append to log
            log['loss'].append(loss)
            log['acc'].append(acc)
            if val_data is not None:
                log['val_loss'].append(val_loss)
                log['val_acc'].append(val_acc)

            # verbose
            if val_data is None:
                print ("%d / %d: train_loss: %.4f train_acc: %.4f |" % (epoch+1, n_epoch, loss, acc),
                    "learning rate: %.4f" % (lr) )
            else:
                print ("%d / %d: train_loss: %.4f train_acc: %.4f |" % (epoch+1, n_epoch, loss, acc),
                    "test_loss: %.4f test_acc: %.4f |" % (val_loss, val_acc),
                    "learning rate: %.4f" % (lr) )
            
        return log
    # end method fit


    def predict(self, X_test, batch_size=32):
        batch_pred_list = []
        for X_test_batch in self.gen_batch(X_test, batch_size):
            batch_pred = self.sess.run(self.pred, feed_dict={self.X: X_test_batch, self.keep_prob: 1.0})
            batch_pred_list.append(batch_pred)
        return np.concatenate(batch_pred_list)
    # end method predict


    def close(self):
        self.sess.close()
        tf.reset_default_graph()
    # end method close


    def gen_batch(self, arr, batch_size):
        if len(arr) % batch_size != 0:
            new_len = len(arr) - len(arr) % batch_size
            for i in range(0, new_len, batch_size):
                yield arr[i : i + batch_size]
        else:
            for i in range(0, len(arr), batch_size):
                yield arr[i : i + batch_size]
    # end method gen_batch

    def get_lr(self, en_exp_decay, global_step, n_epoch, len_X, batch_size):
        if en_exp_decay:
            max_lr = 0.003
            min_lr = 0.0001
            decay_rate = math.log(min_lr/max_lr) / (-n_epoch*len_X/batch_size)
            lr = max_lr*math.exp(-decay_rate*global_step)
        else:
            lr = 0.001
        return lr
    # end method get_lr

    def list_avg(self, l):
        return sum(l) / len(l)
    # end method list_avg
# end class LinearSVMClassifier
