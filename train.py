import os

import numpy as np
import torch
from chargrid2d.dataloader import ChargridDataloader
from chargrid2d.loss import ChargridLoss
from chargrid2d.metrics import IoU
import pandas as pd

from chargrid2d.model import Chargrid2D

device = 'cuda:0' if torch.cuda.is_available() else 'cpu'

def train(weights_folder='weights'):
    N_EPOCHS = 100
    best_loss = np.infty

    # dataloader = ChargridDataloader(root='data/sroie/', list_file_name_path='train_files.txt',
    #                                 image_size=512, batch_size=1, validation_split=0.1)

    
    df = pd.read_csv('/kaggle/input/vietnamese-receipts-mc-ocr-2021/mcocr_train_df.csv')
    df['anno_polygons'] = df['anno_polygons'].map(eval)

    path_list = []
    corr_list = []
    
    for j in range(len(df)):
        img_path = os.path.join("/kaggle/input/vietnamese-receipts-mc-ocr-2021/train_images/train_images", df['img_id'][j])
        path_list.append(img_path)
    
        corr = []
        for i in range(len(df['anno_polygons'][j])):
            polygon = df['anno_polygons'][j][i]
            corr.append(convert_bbox_corr(polygon['bbox'], polygon['width'], polygon['height']))
    
        corr_list.append(corr)
    
    modded_data = {
        "img_path" : path_list,
        "modded_corr" : corr_list
    }

    for s in modded_data:
        df[s] = modded_data[s]

    df = df.filter(['img_path', 'anno_texts', 'anno_labels', 'modded_corr']).dropna()
    
    df['anno_texts'] = df['anno_texts'].map(lambda s: s.split('|||'))
    df['anno_labels'] = df['anno_labels'].map(lambda s: s.split('|||'))
    
    
    # val_dataloader = dataloader.split_validation()
    loss_fn = ChargridLoss()
    model = Chargrid2D(input_channels=len(dataloader.dataset.corpus) + 1, n_classes=len(dataloader.dataset.target))
    model = model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    for epoch in range(N_EPOCHS):
        print('Epoch {}/{}'.format(epoch, N_EPOCHS - 1))
        print('-' * 10)

        # metrics
        train_metrics = IoU(len(dataloader.dataset.target), ignore_index=0)
        val_metrics = IoU(len(dataloader.dataset.target), ignore_index=0)

        # -------- TRAIN -------
        model.train()
        epoch_loss = 0
        for i, batch in enumerate(dataloader):
            # we need to get gt_seg, gt_boxmask, gt_boxcoord
            img, mask, boxes, lbl_boxes = batch
            img, mask = img.to(device), mask.to(device)

            # zero the parameter gradients
            optimizer.zero_grad()

            # forward
            pred_seg, pred_boxmask, pred_boxcoord = model(img)
            # default ground truth boxmask
            gt_boxmask = torch.ones([pred_boxmask.size()[0], pred_boxmask.size()[2], pred_boxmask.size()[3]]
                                    , dtype=torch.int64)  # TODO: wrong

            mask = mask.type(torch.int64)
            loss = loss_fn(pred_seg, pred_boxmask, pred_boxcoord, mask, gt_boxmask, boxes)
            train_metrics.add(pred_seg, mask)
            epoch_loss += loss.item()  # loss is mean loss of batch
            print("Step", i, 'loss =', loss.item(), '\t cumulative iou =', train_metrics.value()[1])
            # backward
            loss.backward()
            optimizer.step()

        print("Epoch {} Training loss: {}".format(epoch, epoch_loss / len(dataloader)))

        # -------- EVALUATION -------
        model.eval()
        # TODO: update evaluation
        print("START EVALUATION")
        epoch_loss = 0
        for i, batch in enumerate(val_dataloader):
            # we need to get gt_seg, gt_boxmask, gt_boxcoord
            img, mask, boxes, lbl_boxes = batch
            img, mask = img.to(device), mask.to(device)

            # forward
            pred_seg, pred_boxmask, pred_boxcoord = model(img)
            mask = mask.type(torch.int64)

            # default ground truth boxmask
            gt_boxmask = torch.ones([pred_boxmask.size()[0], pred_boxmask.size()[2], pred_boxmask.size()[3]]
                                    , dtype=torch.int64)  # TODO: wrong

            loss = loss_fn(pred_seg, pred_boxmask, pred_boxcoord, mask, gt_boxmask, boxes)
            val_metrics.add(pred_seg, mask)
            epoch_loss += loss.item()  # loss is mean loss of batch
            print("Step", i, 'loss =', loss.item(), '\t cumulative iou =', val_metrics.value()[1])
            if epoch_loss < best_loss:
                best_loss = epoch_loss
                torch.save(model.state_dict(), os.path.join(weights_folder, 'model_epoch_' + str(epoch) + '.pth'))

        print("Epoch {} validation loss: {}".format(epoch, epoch_loss / len(val_dataloader)))


if __name__ == '__main__':
    train()
