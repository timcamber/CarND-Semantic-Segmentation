# pylint: disable=E1102
# pylint: disable=C0103

import os
import os.path
import tensorflow as tf
import helper
import warnings
from distutils.version import LooseVersion
import project_tests as tests

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Check TensorFlow Version
assert LooseVersion(tf.__version__) >= LooseVersion(
    '1.0'), 'Please use TensorFlow version 1.0 or newer.  You are using {}'.format(tf.__version__)
print('TensorFlow Version: {}'.format(tf.__version__))

# Check for a GPU
if not tf.test.gpu_device_name():
    warnings.warn(
        'No GPU found. Please use a GPU to train your neural network.'
    )
else:
    print('Default GPU Device: {}'.format(tf.test.gpu_device_name()))


def load_vgg(sess, vgg_path):
    """
    Load Pretrained VGG Model into TensorFlow.
    :param sess: TensorFlow Session
    :param vgg_path: Path to vgg folder, containing "variables/" and "saved_model.pb"
    :return: Tuple of Tensors from VGG model
            (image_input, keep_prob, layer3_out, layer4_out, layer7_out)
    """
    vgg_tag = 'vgg16'
    tf.saved_model.loader.load(sess, [vgg_tag], vgg_path)
    graph = tf.get_default_graph()

    names = [
        'image_input:0',
        'keep_prob:0',
        'layer3_out:0',
        'layer4_out:0',
        'layer7_out:0'
    ]
    tensors = [
        graph.get_tensor_by_name(name) for name in names
    ]
    return tuple(tensors)


tests.test_load_vgg(load_vgg, tf)


def layers(vgg_layer3_out, vgg_layer4_out, vgg_layer7_out, num_classes):
    """
    Create the layers for a fully convolutional network.  Build skip-layers using the vgg layers.
    :param vgg_layer7_out: TF Tensor for VGG Layer 3 output
    :param vgg_layer4_out: TF Tensor for VGG Layer 4 output
    :param vgg_layer3_out: TF Tensor for VGG Layer 7 output
    :param num_classes: Number of classes to classify
    :return: The Tensor for the last layer of output
    """
    conv_1x1 = tf.layers.conv2d(
        vgg_layer7_out, num_classes, 1, padding='SAME',
        kernel_regularizer=tf.contrib.layers.l2_regularizer(1e-3)
    )
    output = tf.layers.conv2d_transpose(
        conv_1x1, num_classes, 32, 32, padding='SAME',
        kernel_regularizer=tf.contrib.layers.l2_regularizer(1e-3)
    )
    output_3 = tf.layers.conv2d_transpose(
        vgg_layer3_out, num_classes, 8, 8, padding='SAME',
        kernel_regularizer=tf.contrib.layers.l2_regularizer(1e-3)
    )
    output_4 = tf.layers.conv2d_transpose(
        vgg_layer4_out, num_classes, 16, 16, padding='SAME',
        kernel_regularizer=tf.contrib.layers.l2_regularizer(1e-3)
    )
    output = tf.add(output, output_3)
    output = tf.add(output, output_4)
    return output


tests.test_layers(layers)


def optimize(nn_last_layer, correct_label, learning_rate, num_classes):
    """
    Build the TensorFLow loss and optimizer operations.
    :param nn_last_layer: TF Tensor of the last layer in the neural network
    :param correct_label: TF Placeholder for the correct label image
    :param learning_rate: TF Placeholder for the learning rate
    :param num_classes: Number of classes to classify
    :return: Tuple of (logits, train_op, cross_entropy_loss)
    """
    logits = tf.reshape(nn_last_layer, (-1, num_classes))
    cross_entropy_loss = tf.reduce_mean(
        tf.nn.softmax_cross_entropy_with_logits(
            logits=logits, labels=correct_label
        )
    )
    train_op = tf.train.AdamOptimizer(
        learning_rate
    ).minimize(cross_entropy_loss)
    return logits, train_op, cross_entropy_loss


tests.test_optimize(optimize)


def train_nn(sess, epochs, batch_size, get_batches_fn, train_op, cross_entropy_loss, input_image,
             correct_label, keep_prob, learning_rate):
    """
    Train neural network and print out the loss during training.
    :param sess: TF Session
    :param epochs: Number of epochs
    :param batch_size: Batch size
    :param get_batches_fn: Function to get batches of training data.
            Call using get_batches_fn(batch_size)
    :param train_op: TF Operation to train the neural network
    :param cross_entropy_loss: TF Tensor for the amount of loss
    :param input_image: TF Placeholder for input images
    :param correct_label: TF Placeholder for label images
    :param keep_prob: TF Placeholder for dropout keep probability
    :param learning_rate: TF Placeholder for learning rate
    """
    sess.run(tf.global_variables_initializer())
    sess.run(tf.local_variables_initializer())
    for epoch in range(epochs):
        batch_num = 0
        for image, label in get_batches_fn(batch_size):
            feed_dict = {
                input_image: image,
                correct_label: label,
                keep_prob: 1.0,
                learning_rate: 0.001
            }
            _, loss = sess.run(
                [train_op, cross_entropy_loss], feed_dict=feed_dict
            )
            batch_num += 1
            print('Epoch: {} Batch Num: {} Loss: {}'.format(
                epoch, batch_num, loss
            ))


tests.test_train_nn(train_nn)


def run():
    num_classes = 2
    epochs = 50
    batch_size = 100
    image_shape = (160, 576)
    data_dir = './data'
    runs_dir = './runs'
    tests.test_for_kitti_dataset(data_dir)

    helper.maybe_download_pretrained_vgg(data_dir)

    with tf.Session() as sess:
        vgg_path = os.path.join(data_dir, 'vgg')
        get_batches_fn = helper.gen_batch_function(
            os.path.join(data_dir, 'data_road/training'), image_shape
        )

        keep_prob = tf.placeholder(tf.float32)
        learning_rate = tf.placeholder(tf.float32)
        correct_label = tf.placeholder(
            tf.float32,
            (None, image_shape[0], image_shape[1], 2)
        )

        input_image, keep_prob, layer3_out, layer4_out, layer7_out = load_vgg(
            sess, vgg_path
        )
        layer_output = layers(layer3_out, layer4_out, layer7_out, num_classes)

        logits, train_op, cross_entropy_loss = optimize(
            layer_output, correct_label, learning_rate, num_classes
        )

        train_nn(
            sess,
            epochs,
            batch_size,
            get_batches_fn,
            train_op,
            cross_entropy_loss,
            input_image,
            correct_label,
            keep_prob,
            learning_rate
        )

        helper.save_inference_samples(
            runs_dir, data_dir, sess, image_shape, logits, keep_prob, input_image
        )


if __name__ == '__main__':
    run()
