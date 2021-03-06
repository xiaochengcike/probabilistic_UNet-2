import os, sys
import numpy as np
import tensorflow as tf
import datetime
from model import PUNet as Model
# from autoencoder import AE_pool as AE

import argparse
from make_datasets import Make_datasets_CityScape as Make_datasets
# from make_datasets import Make_datasets_WallCrack_labelme as Make_datasets
# from make_datasets import Make_datasets_OilLeak as Make_datasets


import utility as util

def parser():
    parser = argparse.ArgumentParser(description='classify ketten images')
    parser.add_argument('--batch_size', '-b', type=int, default=100, help='Number of images in each mini-batch')
    parser.add_argument('--log_file_name', '-lf', type=str, default='logPUNet01', help='log file name')
    parser.add_argument('--epoch', '-e', type=int, default=31, help='epoch')
    parser.add_argument('--base_dir', '-bd', type=str, default='/mnt/several_data/dataset/cityScape/',
                        help='base directory name of data-sets')
    parser.add_argument('--img_dir', '-id', type=str, default='data/leftImg8bit/train/', help='directory name of images')
    parser.add_argument('--seg_dir', '-sd', type=str, default='gtFine/train/', help='directory name of masks')
    parser.add_argument('--img_val_dir', '-ivd', type=str, default='data/leftImg8bit/val/', help='directory name of validation images')
    parser.add_argument('--seg_val_dir', '-svd', type=str, default='gtFine/val/', help='directory name of validation masks')
    parser.add_argument('--val_number', '-vn', type=int, default=6, help='where validation data in all data...0-5')
    parser.add_argument('--out_img_span', '-ois', type=int, default=3, help='time span when output image')
    parser.add_argument('--image_h', '-imh', type=int, default=128, help='input image height')
    parser.add_argument('--image_w', '-imw', type=int, default=128, help='input image width')
    parser.add_argument('--crop_image_h', '-cih', type=int, default=128, help='cropped image height')
    parser.add_argument('--crop_image_w', '-ciw', type=int, default=256, help='cropped image width')
    parser.add_argument('--crop_flag', '-cpf', action='store_true', default=False, help='do cropping')
    parser.add_argument('--class_number', '-cnu', type=int, default=35, help='class number')
    parser.add_argument('--restore_model_name', '-rmn', type=str, default='', help='restored model name')
    parser.add_argument('--save_model_span', '-sms', type=int, default=10, help='save model span')


    return parser.parse_args()

args = parser()

BASE_CHANNEL = 32
CODE_DIM = 6
SEED = 2018
np.random.seed(SEED)
IMG_H = args.image_h
IMG_W = args.image_w
IMG_CHANNEL = 3
CLASS_NUM = args.class_number
BATCH_SIZE = args.batch_size
EPOCH = args.epoch
IMG_SIZE_BE_CROP_W = args.crop_image_h
IMG_SIZE_BE_CROP_H = args.crop_image_w
LR = 0.001
VAL_NUMBER = args.val_number
VALID_EPOCH = 5
VAL_IMG_NUM = 6
OUT_IMG_SPAN = args.out_img_span
CROP_FLAG = args.crop_flag
SAVE_MODEL_SPAN = args.save_model_span
RESTORED_MODEL_NAME = args.restore_model_name
TB_TRAIN = 'tensorboard/tensorboard_train_' + args.log_file_name
TB_TEST = 'tensorboard/tensorboard_test_' + args.log_file_name
LOG_FILE_NAME = 'log/' + args.log_file_name
LOG_LIST = []
OUT_IMG_DIR = './out_images'


try:
    os.mkdir(OUT_IMG_DIR)
except:
    pass

try:
    os.mkdir("./log")
except:
    pass

try:
    os.mkdir("./out_model")
except:
    pass

try:
    os.mkdir("./tensorboard")
except:
    pass
#base_dir, img_width, img_height, image_dir, seg_dir, image_val_dir, seg_val_dir,
                # img_width_be_crop, img_height_be_crop, crop_flag=False
datasets = Make_datasets(args.base_dir, IMG_W, IMG_H, args.img_dir, args.seg_dir, args.img_val_dir, args.seg_val_dir,
                         IMG_SIZE_BE_CROP_W, IMG_SIZE_BE_CROP_H, crop_flag=CROP_FLAG)


x = tf.placeholder(tf.float32, [None, IMG_H, IMG_W, IMG_CHANNEL])
t = tf.placeholder(tf.float32, [None, IMG_H, IMG_W, CLASS_NUM])
is_training = tf.placeholder('bool', [])
lr_p = tf.placeholder('float')

# Model
model = Model(IMG_H, IMG_W, IMG_CHANNEL, CODE_DIM, BASE_CHANNEL, CLASS_NUM)
mean_pri, log_var_pri = model.priorNet(x)
mean_pos, log_var_pos = model.posteriorNet(x, t)

out_learn = model.unet(x, mean_pos, log_var_pos, reuse=False)
out_infer = model.unet(x, mean_pri, log_var_pri, reuse=True)

with tf.variable_scope("loss"):
    # loss = model.loss(output, y)
    loss = model.loss(mean_pri, log_var_pri, mean_pos, log_var_pos, out_learn, t)

# with tf.variable_scope("argmax"):
#     out_argmax = tf.argmax(out_infer, axis=3)

with tf.variable_scope("train"):
    # train_op = tf.train.GradientDescentOptimizer(0.05).minimize(loss)
    train_op = tf.train.AdamOptimizer(lr_p).minimize(loss)

# Summaries
tf.summary.scalar('train_loss', loss)
merged_summary = tf.summary.merge_all()

train_writer = tf.summary.FileWriter(TB_TRAIN)
val_writer = tf.summary.FileWriter(TB_TEST)

sess = tf.Session()
# with tf.Session() as sess:
sess.run(tf.global_variables_initializer())
train_writer.add_graph(sess.graph)

saver = tf.train.Saver()
if RESTORED_MODEL_NAME != '':
    saver.restore(sess, RESTORED_MODEL_NAME)
    print("model ", RESTORED_MODEL_NAME, " is restored.")

# model.load_original_weights(sess, skip_layers=train_layers)

LOG_LIST.append(['epoch', 'Loss'])

#before learning
for epoch in range(EPOCH):
    lr_now = util.cal_learning_rate_with_thr(0.0001, epoch, 0.00005, 100)
    sum_loss = np.float32(0)

    len_data = datasets.make_data_for_1_epoch()

    for i in range(0, len_data, BATCH_SIZE):
        # print("i, ", i)
        img_batch, seg_batch = datasets.get_data_for_1_batch(i, BATCH_SIZE)

        #debug
        if epoch == 0 and i == 0:
            loss_ = sess.run(loss, feed_dict={x: img_batch, t: seg_batch, is_training: False})

        if epoch != 0:
            sess.run(train_op, feed_dict={x: img_batch, t: seg_batch, is_training: True, lr_p:lr_now})

        s = sess.run(merged_summary, feed_dict={x: img_batch, t: seg_batch, is_training: False})
        train_writer.add_summary(s, epoch)

        loss_ = sess.run(loss, feed_dict={x: img_batch, t: seg_batch, is_training: False})
        sum_loss += loss_ * len(img_batch)

    print("----------------------------------------------------------------------")
    print("epoch = {:}, Training Loss = {:.4f}".format(epoch, sum_loss / len_data))

    if epoch % OUT_IMG_SPAN == 0:
        img_batch, segs = datasets.get_data_for_1_batch_val(0, BATCH_SIZE)
        # img_batch2 = datasets.get_data_for_1_batch_val(0, 6)
        # print("img_batch.shape, ", img_batch.shape)
        output_val = sess.run(out_infer, feed_dict={x: img_batch, is_training: False})

        # print("np.max(output_val), ", np.max(output_val))
        # print("np.max(output_tr), ", np.max(output_tr))
        # print("np.min(output_val), ", np.min(output_val))
        # print("np.min(output_tr), ", np.min(output_tr))
        #make several candidate images
        # print("img_batch.shape, ", img_batch.shape)
        # print("np.max(img_batch), ", np.max(img_batch))
        # print("np.min(img_batch), ", np.min(img_batch))
        img1 = img_batch[0].reshape(1, img_batch.shape[1], img_batch.shape[2], img_batch.shape[3])
        img1_tile = np.tile(img1, (VAL_IMG_NUM, 1, 1, 1))
        # print("np.max(img1_tile), ", np.max(img1_tile))
        # print("np.min(img1_tile), ", np.min(img1_tile))
        # print("img1_tile.shape, ", img1_tile.shape)
        segs1 = segs[0].reshape(1, segs.shape[1], segs.shape[2], segs.shape[3])
        segs1_tile = np.tile(segs1, (VAL_IMG_NUM, 1, 1, 1))
        output1_list = []
        for num in range(VAL_IMG_NUM):
            output_tmp = sess.run(out_infer, feed_dict={x: img_batch, is_training: False})
            output1_list.append(output_tmp[0])
        output1 = np.asarray(output1_list)
        # print("np.max(output1), ", np.max(output1))
        # print("np.min(output1), ", np.min(output1))
        output_tr = sess.run(out_learn, feed_dict={x: img_batch, t: segs, is_training: False})

        util.make_output_img(img_batch[:VAL_IMG_NUM], segs[:VAL_IMG_NUM], output_val[:VAL_IMG_NUM], epoch,
                             args.log_file_name + '_val_', OUT_IMG_DIR)
        util.make_output_img(img_batch[:VAL_IMG_NUM], segs[:VAL_IMG_NUM], output_tr[:VAL_IMG_NUM], epoch,
                             args.log_file_name + '_tra_', OUT_IMG_DIR)
        util.make_output_img(img1_tile, segs1_tile, output1, epoch, args.log_file_name + '_diff_z_', OUT_IMG_DIR)

    if epoch % SAVE_MODEL_SPAN == 0 and epoch != 0:
            _ = saver.save(sess, './out_model/model_' + args.log_file_name + '_' + str(epoch) + '.ckpt')











