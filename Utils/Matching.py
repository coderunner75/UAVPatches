# Based on https://github.com/ducha-aiki/local_feature_tutorial repo with some modification.

__all__ = ['LocalFeatureExtractor', 'DescriptorMatcher', 'GeometricVerifier', 'SIFT', 'ORB', 'HardNetDesc', 'SNNMatcher',
           'SNNMMatcher', 'CV2_RANSACVerifier', 'TwoViewMatcher', 'degensac_Verifier', 'UAVPatchesANDPlus']

import cv2
import numpy as np
import abc
from copy import deepcopy
from pathlib import Path
from typing import List, Tuple
from tqdm.notebook import tqdm
import numpy as np, time
import torch
import torchvision as tv
import os
from typing import Dict
import torch.nn as nn
import torch.nn.functional as F
import sys, gc
from copy import deepcopy
import math
import argparse
import torch
import torch.nn.init
import torch.nn as nn
import torch.optim as optim
import torchvision.datasets as dset
import torchvision.transforms as transforms
from torch.autograd import Variable
import torch.backends.cudnn as cudnn
import os
from tqdm import tqdm
import numpy as np
import random
import cv2
import copy
import PIL
import kornia.feature as KF, torch, torch.nn.functional as F
from extract_patches.core import extract_patches

def match_snn(desc1: torch.Tensor, desc2: torch.Tensor, th: float = 0.8, dm: torch.Tensor = None) -> Tuple[torch.Tensor, torch.Tensor]:
    if len(desc1.shape) != 2:
        raise AssertionError
    if len(desc2.shape) != 2:
        raise AssertionError
    if desc2.shape[0] < 2:
        raise AssertionError
    valsList, idxs_in_2List = [], []
    for Batch in range(0, len(desc1), 10000):
      MiniDesc = desc1[Batch:Batch+10000]
      dm = torch.cdist(MiniDesc, desc2)
      vals, idxs_in_2 = torch.topk(dm, 2, dim=1, largest=False)
      valsList.append(vals)
      idxs_in_2List.append(idxs_in_2)
      dm, vals, idxs_in_2 = [], [], []
    vals, idxs_in_2 = torch.cat(valsList), torch.cat(idxs_in_2List)
    ratio = vals[:, 0] / vals[:, 1]
    mask = ratio <= th
    match_dists = ratio[mask]
    idxs_in1 = torch.arange(0, idxs_in_2.size(0), device=desc1.device)[mask]
    idxs_in_2 = idxs_in_2[:, 0][mask]
    matches_idxs = torch.cat([idxs_in1.view(-1, 1), idxs_in_2.view(-1, 1)], dim=1)
    return match_dists.view(-1, 1), matches_idxs.view(-1, 2)

def match_smnn(
    desc1: torch.Tensor, desc2: torch.Tensor, th: float = 0.8, dm: torch.Tensor = None) -> Tuple[torch.Tensor, torch.Tensor]:
    
    if len(desc1.shape) != 2:
        raise AssertionError
    if len(desc2.shape) != 2:
        raise AssertionError
    if desc1.shape[0] < 2:
        raise AssertionError
    if desc2.shape[0] < 2:
        raise AssertionError
    
    dists1, idx1 = match_snn(desc1, desc2, th)
    gc.collect()
    dists2, idx2 = match_snn(desc2, desc1, th)

    if len(dists2) > 0 and len(dists1) > 0:
        idx2 = idx2.flip(1)
        idxs_dm = torch.cdist(idx1.float(), idx2.float(), p=1.0)
        mutual_idxs1 = idxs_dm.min(dim=1)[0] < 1e-8
        mutual_idxs2 = idxs_dm.min(dim=0)[0] < 1e-8
        good_idxs1 = idx1[mutual_idxs1.view(-1)]
        good_idxs2 = idx2[mutual_idxs2.view(-1)]
        dists1_good = dists1[mutual_idxs1.view(-1)]
        dists2_good = dists2[mutual_idxs2.view(-1)]
        _, idx_upl1 = torch.sort(good_idxs1[:, 0])
        _, idx_upl2 = torch.sort(good_idxs2[:, 0])
        good_idxs1 = good_idxs1[idx_upl1]
        match_dists = torch.max(dists1_good[idx_upl1], dists2_good[idx_upl2])
        matches_idxs = good_idxs1
    else:
        matches_idxs, match_dists = torch.empty(0, 2, device=desc1.device), torch.empty(0, 1, device=desc1.device)
    return match_dists.view(-1, 1), matches_idxs.view(-1, 2)
           
class LocalFeatureExtractor():
    '''Abstract method for local detector and or descriptor'''
    def __init__(self, **kwargs):
        ''''''
        return
    @abc.abstractmethod
    def detect(self, image: np.array, mask:np.array) -> List[cv2.KeyPoint]:
        return
    @abc.abstractmethod
    def compute(self, image: np.array, keypoints = None) -> Tuple[List[cv2.KeyPoint], np.array]:
        return

#export
class DescriptorMatcher():
    '''Abstract method fordescriptor matcher'''
    def __init__(self, **kwargs):
        return
    @abc.abstractmethod
    def match(self, queryDescriptors:np.array, trainDescriptors:np.array) -> List[cv2.DMatch]:
        out = []
        return out
#export
class GeometricVerifier():
    '''Abstract method for RANSAC'''
    def __init__(self, **kwargs):
        '''In'''
        return
    @abc.abstractmethod
    def verify(self, srcPts:np.array, dstPts:np.array):
        out = []
        return F, mask

# Cell
class SIFT(LocalFeatureExtractor):
    def __init__(self, **kwargs):
        '''In'''
        return

    def compute(self, image, keypoints=None, ImagePath=None) -> Tuple[List[cv2.KeyPoint], np.array]:
        model = KF.SIFTDescriptor(32, rootsift=False)
        if os.path.isfile(ImagePath + '.npy'):
          out_desc = np.load(ImagePath + '.npy')
        else:
          patches = extract_patches(keypoints, cv2.cvtColor(image, cv2.COLOR_RGB2GRAY), 32, 18.0)
          torch_patches = torch.from_numpy(np.stack(patches, axis=0))
          # dev = torch.device('cpu')
          if torch.cuda.is_available():
              dev = torch.device('cuda')
          else:
              dev = torch.device('cpu')
          model = model.to(dev)
          torch_patches = torch_patches.unsqueeze(1).float().to(dev)
          for idx in range(torch_patches.shape[0]):
            torch_patches[idx] = torch_patches[idx] / torch_patches[idx].max()
          out_desc = np.zeros((len(torch_patches), 128))
          bs = 1024
          for i in range(0, len(torch_patches), bs):
              data_a = torch_patches[i: i + bs, :, :, :]
              with torch.no_grad():
                  out_a = model(data_a)
              out_desc[i: i + bs,:] = out_a.data.cpu().numpy().reshape(-1, 128)
          if os.path.isfile(ImagePath + '.txt'): np.save(ImagePath + '.npy', out_desc)
        return keypoints, out_desc

class ORB(LocalFeatureExtractor):
    def __init__(self, **kwargs):
        '''In'''
        return

    def compute(self, image, keypoints=None, ImagePath=None) -> Tuple[List[cv2.KeyPoint], np.array]:
        image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        ORBObject = cv2.ORB_create(len(keypoints))
        kp = ORBObject.detect(image, None)
        kp, desc = ORBObject.compute(image, kp)
        return kp, desc

# Cell
class HardNetDesc(LocalFeatureExtractor):
    def __init__(self, ModelT, **kwargs):
        self.Model = ModelT
        return
    def compute(self, image, keypoints=None, ImagePath=None) -> Tuple[List[cv2.KeyPoint], np.array]:
        if self.Model is not None:
          model = self.Model
        else:
          model = KF.HardNet(False).eval()
          model.load_state_dict(torch.load('/content/checkpoint_liberty_no_aug.pth', map_location=torch.device('cpu'))['state_dict'])
        if os.path.isfile(ImagePath + '.npy'):
          out_desc = np.load(ImagePath + '.npy')
        else:
          patches = extract_patches(keypoints, cv2.cvtColor(image, cv2.COLOR_RGB2GRAY), 32, 18.0)
          torch_patches = torch.from_numpy(np.stack(patches, axis=0))
          # dev = torch.device('cpu')
          if torch.cuda.is_available():
              dev = torch.device('cuda')
          else:
              dev = torch.device('cpu')
          model = model.to(dev)
          torch_patches = torch_patches.unsqueeze(1).float().to(dev)
          for idx in range(torch_patches.shape[0]):
            torch_patches[idx] = torch_patches[idx] / torch_patches[idx].max()
          out_desc = np.zeros((len(torch_patches), 128))
          bs = 1024
          for i in range(0, len(torch_patches), bs):
              data_a = torch_patches[i: i + bs, :, :, :]
              with torch.no_grad():
                  out_a = model(data_a)
              out_desc[i: i + bs,:] = out_a.data.cpu().numpy().reshape(-1, 128)
          if os.path.isfile(ImagePath + '.txt'): np.save(ImagePath + '.npy', out_desc)
        return keypoints, out_desc

class UAVPatchesANDPlus(LocalFeatureExtractor):
    def __init__(self, ModelT, **kwargs):
        self.Model = ModelT
        return
    def compute(self, image, keypoints=None, ImagePath=None) -> Tuple[List[cv2.KeyPoint], np.array]:
        model = self.Model
        if os.path.isfile(ImagePath + '.npy'):
          out_desc = np.load(ImagePath + '.npy')
        else:
          patches = extract_patches(keypoints, cv2.cvtColor(image, cv2.COLOR_RGB2GRAY), 32, 18.0)
          torch_patches = torch.from_numpy(np.stack(patches, axis=0))
          # dev = torch.device('cpu')
          if torch.cuda.is_available():
              dev = torch.device('cuda')
          else:
              dev = torch.device('cpu')
          model = model.to(dev)
          torch_patches = torch_patches.unsqueeze(1).float().to(dev)
          for idx in range(torch_patches.shape[0]):
            torch_patches[idx] = torch_patches[idx] / torch_patches[idx].max()
          out_desc = np.zeros((len(torch_patches), 128))
          bs = 1024
          for i in range(0, len(torch_patches), bs):
              data_a = torch_patches[i: i + bs, :, :, :]
              with torch.no_grad():
                  out_a = model(data_a)
              out_desc[i: i + bs,:] = out_a.data.cpu().numpy().reshape(-1, 128)
          if os.path.isfile(ImagePath + '.txt'): np.save(ImagePath + '.npy', out_desc)
        return keypoints, out_desc
# Cell
class SNNMatcher():
    def __init__(self, th = 0.8):
        '''In'''
        self.th = th
        return
    def match(self, queryDescriptors:np.array, trainDescriptors:np.array) -> List[cv2.DMatch]:
        matcher = cv2.DescriptorMatcher_create(cv2.DescriptorMatcher_FLANNBASED)
        matches = matcher.knnMatch(queryDescriptors, trainDescriptors, 2)
        good_matches = []
        for m in matches:
            if m[0].distance / (1e-8 + m[1].distance) <= self.th :
                good_matches.append(m[0])
        return good_matches

# Cell
class SNNMMatcher():
    def __init__(self, th = 0.9):
        '''In'''
        self.th = th
        return
    def match(self, queryDescriptors:np.array, trainDescriptors:np.array) -> List[cv2.DMatch]:
        # dev = torch.device('cpu')
        if torch.cuda.is_available():
            dev = torch.device('cuda')
        else:
            dev = torch.device('cpu')

        dists, idxs = match_smnn(torch.from_numpy(queryDescriptors).float().to(dev),
                                   torch.from_numpy(trainDescriptors).float().to(dev),
                                   self.th)
        good_matches = []
        for idx_q_t in idxs.detach().cpu().numpy():
            good_matches.append(cv2.DMatch(idx_q_t[0].item(), idx_q_t[1].item(), 0))
        return good_matches, dists

# Cell
class CV2_RANSACVerifier(GeometricVerifier):
    def __init__(self, th = 0.5):
        self.th = th
        return
    def verify(self, srcPts:np.array, dstPts:np.array):
        F, mask = cv2.findFundamentalMat(srcPts, dstPts, cv2.RANSAC, self.th)
        return F, mask

# Cell
class TwoViewMatcher():
    def __init__(self, detector:LocalFeatureExtractor = cv2.SIFT_create(8000),
                       descriptor:LocalFeatureExtractor = cv2.SIFT_create(8000),
                       matcher: DescriptorMatcher = cv2.DescriptorMatcher_create(cv2.DescriptorMatcher_FLANNBASED),
                       geom_verif: GeometricVerifier = CV2_RANSACVerifier(0.5)):
        self.det = detector
        self.desc = descriptor
        self.matcher = matcher
        self.geom_verif = geom_verif
        return
    def verify(self, img1_fname, img2_fname, kps1=None, kps2=None):
        if type(img1_fname) is str and kps1 is None:
            img1 = cv2.cvtColor(cv2.imread(img1_fname), cv2.COLOR_BGR2RGB)
        else:
            img1 = img1_fname
        if type(img2_fname) is str and kps2 is None:
            img2 = cv2.cvtColor(cv2.imread(img2_fname), cv2.COLOR_BGR2RGB)
        else:
            img2 = img2_fname

        if kps1 == None:
          kps1 = self.det.detect(img1, None)
        kps1, descs1 = self.desc.compute(img1,  kps1, img1_fname)

        if kps2 == None:
          kps2 = self.det.detect(img2, None)
        T1 = time.time()
        kps2, descs2 = self.desc.compute(img2, kps2, img2_fname)
        T2 = time.time()
        
        tentative_matches, dists = self.matcher.match(descs1, descs2)

        src_pts = np.float32([ kps1[m.queryIdx].pt for m in tentative_matches]).reshape(-1,2)
        dst_pts = np.float32([ kps2[m.trainIdx].pt for m in tentative_matches]).reshape(-1,2)

        F, mask = self.geom_verif.verify(src_pts, dst_pts)

        good_kpts1 = [ kps1[m.queryIdx] for i,m in enumerate(tentative_matches) if mask[i]]
        good_kpts2 = [ kps2[m.trainIdx] for i,m in enumerate(tentative_matches) if mask[i]]
        result = {'init_kpts1': kps1,
                  'init_kpts2': kps2,
                  'match_kpts1': good_kpts1,
                  'match_kpts2': good_kpts2,
                  'F': F,
                  'num_inl': len(good_kpts1),
                  'dists': dists[mask].detach().cpu().squeeze().numpy(),
                  'DescTime': T2 - T1,
                  'TentativeMatches': tentative_matches,
                  'InliersRatio': float(len(good_kpts1))/float(len(src_pts))}
        return result

# Cell
import pydegensac
class degensac_Verifier(GeometricVerifier):
    def __init__(self, th = 0.5):
        self.th = th
        return
    def verify(self, srcPts:np.array, dstPts:np.array):
        F, mask = pydegensac.findFundamentalMatrix(srcPts, dstPts, self.th, 0.999, max_iters=250000)
        return F, mask
