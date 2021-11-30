"""
This script to extract skeleton joints position and score.

- This 'annot_folder' is a action class and bounding box for each frames that came with dataset.
    Should be in format of [frame_idx, action_cls, xmin, ymin, xmax, ymax]
        Use for crop a person to use in pose estimation model.
- If have no annotation file you can leave annot_folder = '' for use Detector model to get the
    bounding box.
"""

import os
import cv2
import time
import torch
import pandas as pd
import numpy as np

import torchvision.transforms as transforms

#from Track.DetectorLoader import TinyYOLOv3_onecls
from PoseEstimateLoader import SPPE_FastPose
from fn import vis_frame_fast
from DetectorLoader import TinyYOLOv3_onecls
save_path = '/home/thien/Desktop/Human-Falling-Detect-Tracks/Data/pose_and_score.csv'

annot_file = '/home/thien/Desktop/Human-Falling-Detect-Tracks/Data/Home_new_2.csv'  # from create_dataset_1.py
video_folder = '/home/thien/Desktop/Human-Falling-Detect-Tracks/videos'
annot_folder = '/home/thien/Desktop/Human-Falling-Detect-Tracks/annot'

# DETECTION MODEL.
detector = TinyYOLOv3_onecls()

# POSE MODEL.
inp_h = 320
inp_w = 256
pose_estimator = SPPE_FastPose('resnet101', 'resnet101')

class_names = ['Standing', 'Walking', 'Sitting', 'Lying Down','Stand up', 'Sit down', 'Fall Down']

# with score.
columns = ['video', 'frame', 'Nose_x', 'Nose_y', 'Nose_s', 'LShoulder_x', 'LShoulder_y', 'LShoulder_s',
           'RShoulder_x', 'RShoulder_y', 'RShoulder_s', 'LElbow_x', 'LElbow_y', 'LElbow_s', 'RElbow_x',
           'RElbow_y', 'RElbow_s', 'LWrist_x', 'LWrist_y', 'LWrist_s', 'RWrist_x', 'RWrist_y', 'RWrist_s',
           'LHip_x', 'LHip_y', 'LHip_s', 'RHip_x', 'RHip_y', 'RHip_s', 'LKnee_x', 'LKnee_y', 'LKnee_s',
           'RKnee_x', 'RKnee_y', 'RKnee_s', 'LAnkle_x', 'LAnkle_y', 'LAnkle_s', 'RAnkle_x', 'RAnkle_y',
           'RAnkle_s', 'label']


def normalize_points_with_size(points_xy, width, height, flip=False):
    points_xy[:, 0] /= width
    points_xy[:, 1] /= height
    if flip:
        points_xy[:, 0] = 1 - points_xy[:, 0]
    return points_xy


annot = pd.read_csv(annot_file)
vid_list = annot['video'].unique()
print(vid_list)
for vid in vid_list:
    print(f'Process on: {vid}')
    df = pd.DataFrame(columns=columns)
    cur_row = 0
    # Pose Labels.
    frames_label = annot[annot['video'] == vid].reset_index(drop=True)
    videos_path=os.path.join(video_folder, vid)
    cap = cv2.VideoCapture(videos_path)
    length = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                  int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))

    # Bounding Boxs Labels.
    annot_file_2 = os.path.join(annot_folder,vid.split('.')[0])
    #annot_file_2=annot_file_2+'.csv'
    annot_2 = None
    if os.path.exists(annot_file_2):
        annot_2 = pd.read_csv(annot_file_2, header=None,
                                  names=['frame_idx', 'class', 'xmin', 'ymin', 'xmax', 'ymax'])
        annot_2 = annot_2.dropna().reset_index(drop=True)

        assert frames_count == len(annot_2), 'frame count not equal! {} and {}'.format(frames_count, len(annot_2))

    fps_time = 0
    i = 1
    while True:
        ret, frame = cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            cls_idx = int(frames_label[frames_label['frame'] == i]['label'])
            if annot_2 != None:
                bb = np.array(annot_2.iloc[i-1, 2:].astype(int))
            else:

                bb = detector.detect(frame)
                if bb==None:
                    bb=torch.tensor([[0, 0, 0, 0, 0.9330, 1.0000, 0.0000]])
                    bb = bb[0, :4].numpy().astype(int)
                else:
                    bb = bb[0, :4].numpy().astype(int)




            bb[:2] = np.maximum(0, bb[:2] - 5)
            bb[2:] = np.minimum(frame_size, bb[2:] + 5) if bb[2:].any() != 0 else bb[2:]

            result = []
            if bb.any() != 0:
                result = pose_estimator.predict(frame, torch.tensor(bb[None, ...]),
                                                torch.tensor([[1.0]]))

            if len(result) > 0:
                pt_norm = normalize_points_with_size(result[0]['keypoints'].numpy().copy(),
                                                     frame_size[0], frame_size[1])
                pt_norm = np.concatenate((pt_norm, result[0]['kp_score']), axis=1)

                #idx = result[0]['kp_score'] <= 0.05
                #pt_norm[idx.squeeze()] = np.nan
                row = [vid, i, *pt_norm.flatten().tolist(), cls_idx]
                scr = result[0]['kp_score'].mean()
            else:
                row = [vid, i, *[np.nan] * (13 * 3), cls_idx]
                scr = 0.0

            df.loc[cur_row] = row
            cur_row += 1

            #  VISUALIZE.
            frame = vis_frame_fast(frame, result)
            frame = cv2.rectangle(frame, (bb[0], bb[1]), (bb[2], bb[3]), (0, 255, 0), 2)
            frame = cv2.putText(frame,'Frame:{}'.format(i),
                                (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            frame = cv2.putText(frame, 'Pose:{}, Score:{:.4f}'.format( class_names[cls_idx], scr),
                                (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            frame = frame[:, :, ::-1]
            fps_time = time.time()
            i += 1
            frame = cv2.resize(frame, (0, 0), fx=4, fy=4)
            cv2.imshow('frame', frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('p'):
                key = cv2.waitKey(0) & 0xFF
                if key == ord('p'):
                    continue


        else:
             break

    cap.release()
    cv2.destroyAllWindows()

    if os.path.exists(save_path):
        df.to_csv(save_path, mode='a', header=False, index=False)
    else:
        df.to_csv(save_path, mode='w', index=False)

