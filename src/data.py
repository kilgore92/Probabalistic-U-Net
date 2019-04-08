from __future__ import print_function, division
import os
import torch
import pandas as pd
#from skimage import io, transform
import numpy as np
import matplotlib.pyplot as plt
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, utils
import glob
from collections import OrderedDict
from collections import Counter
import shutil
import pydicom as dcm
import imageio

class ChaosLiverMR(Dataset):
    def __init__(self,root_dir=None,out_dir='./data',mode='T2SPIR',transforms=None,keep_train_prob = 0.9,renew=True):
        self.root_dir = root_dir
        self.mode = mode
        self.keep_train_prob = keep_train_prob
        self.out_dir = out_dir
        self.transforms = transforms
        if renew is True:
            self.create_train_val_sets()


    def create_train_val_sets(self):
        self.train_dir = os.path.join(self.out_dir,'train_data')
        self.val_dir = os.path.join(self.out_dir,'val_data')

        self.train_images_dir = os.path.join(self.train_dir,'images')
        self.train_labels_dir = os.path.join(self.train_dir,'labels')

        self.val_images_dir = os.path.join(self.val_dir,'images')
        self.val_labels_dir = os.path.join(self.val_dir,'labels')

        if os.path.exists(self.train_dir) is True:
            shutil.rmtree(self.train_dir)

        if os.path.exists(self.val_dir) is True:
            shutil.rmtree(self.val_dir)

        os.makedirs(self.train_images_dir)
        os.makedirs(self.train_labels_dir)
        os.makedirs(self.val_images_dir)
        os.makedirs(self.val_labels_dir)

        data_dict = OrderedDict()

        # Split images into 'train' and 'val' sets
        image_dir_list = [os.path.join(f.path,self.mode.upper(),'DICOM_anon') for f in os.scandir(self.root_dir) if f.is_dir()]
        label_dir_list = [os.path.join(f.path,self.mode.upper(),'Ground') for f in os.scandir(self.root_dir) if f.is_dir()]

        num_images = 0
        num_train = 0
        num_val = 0
        fnames = []
        for i_dir,l_dir in zip(image_dir_list,label_dir_list):
            images = glob.glob(os.path.join(i_dir,'*.dcm'))
            for image in images:
                num_images +=1
                fname = image.split('/')[-1].split('.')[0]
                fnames.append(fname)
                label = glob.glob(os.path.join(l_dir,fname+'.*'))[0]
                data_dict[image] = label

        counts_dict = Counter(fnames)


        self.num_train = int(self.keep_train_prob*len(data_dict))

        self.train_image_paths = []
        self.train_label_paths = []

        for idx,image_path in enumerate(data_dict):

            label_path = data_dict[image_path]

            if idx <= self.num_train:
                img_dst = os.path.join(self.train_images_dir,'img_{}.dcm'.format(idx))
                label_dst = os.path.join(self.train_labels_dir,'lab_{}.png'.format(idx))
                self.train_image_paths.append(img_dst)
                self.train_label_paths.append(label_dst)
            else:
                img_dst = os.path.join(self.val_images_dir,'img_{}.dcm'.format(idx))
                label_dst = os.path.join(self.val_labels_dir,'lab_{}.png'.format(idx))

            shutil.copy2(image_path,img_dst)
            shutil.copy2(label_path,label_dst)

    def __getitem__(self,index):
        img_path = self.train_image_paths[index]
        label_path = self.train_image_paths[index]

        # Fix dtype for PIL conversion
        img = np.array(dcm.dcmread(img_path).pixel_array,dtype=np.uint8)
        label = np.array(imageio.imread(label_path),dtype=np.uint8)

        # Reshape for PIL conversion
        # We need to convert the arrays into the PIL format
        # because PyTorch transforms like 'Resize' etc.
        # operate on PIL format arrays
        img = img.reshape((img.shape[0],img.shape[1],1))
        label = img.reshape((label.shape[0],label.shape[1],1))

        sample = {'image':img,'label':label}
        if self.transforms is not None:
            sample['image'] = self.transforms(sample['image'])
            sample['label'] = self.transforms(sample['label'])

        return sample

    def __len__(self):
        return self.num_train


if __name__ == '__main__':
    # Basic sanity for the dataset class -- Run this when making any change to this code
    tnfms = transforms.Compose([transforms.ToPILImage(),transforms.Resize(256),transforms.ToTensor()])

    chaos_dataset = ChaosLiverMR(root_dir='/home/ishaan/probablistic_u_net/data/Train_Sets/MR',
                                 mode='T2SPIR',
                                 transforms=tnfms)
    #DataLoader
    dataloader = DataLoader(dataset=chaos_dataset,
                            batch_size = 4,
                            shuffle=True,
                            num_workers = 4)

    iters = 0

    test_batch_dir = 'test_data_batching'
    if os.path.exists(test_batch_dir) is True:
        shutil.rmtree(test_batch_dir)
    os.makedirs(test_batch_dir)

    for sampled_batch in dataloader:
        batch_imgs = sampled_batch['image'].numpy()
        batch_labels = sampled_batch['label'].numpy()
        print(batch_imgs.shape)
        for batch_idx in range (batch_imgs.shape[0]):
            img = batch_imgs[batch_idx]
            label = batch_labels[batch_idx]

            #PyTorch returns image/label matrices in the range 0-1 with np.float64 format (through some internal [and undocumented] magic!)
            print('Max image pixel value :{}'.format(np.amax(img)))
            print('Max label pixel value :{}'.format(np.amax(label)))

            #For display, re-scale image to 0-255 range
            img = np.array(255*np.transpose(img, (1,2,0)),dtype=np.uint8)
            label = np.array(255*np.transpose(label, (1,2,0)),dtype=np.uint8)

            imageio.imwrite(os.path.join(test_batch_dir,'img_{}_{}.jpg'.format(iters,batch_idx)),img)
            imageio.imwrite(os.path.join(test_batch_dir,'label_{}_{}.jpg'.format(iters,batch_idx)),label)

        iters += 1
        if iters == 5:
            break
