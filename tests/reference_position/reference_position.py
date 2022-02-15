"""Script for producing sliding reference position precision and recall heatmaps"""
from cmath import sqrt
from math import floor
import os, sys
from glob import glob

import numpy as np
import matplotlib.pyplot as plt

import torch
from torch.nn.functional import softmax
import torchvision as tv

sys.path.append("/home/mriva/Recherche/PhD/SATANN/SATANN_synth")
from datasets.clostob.clostob_dataset import CloStObDataset
from unet import UNet
from metrics import precision, recall
from utils import targetToTensor, mkdir

def label_to_name(label):
    if "veryhard" in label:
        return "{}-V.H.".format(label[0].upper())
    if "hard" in label:
        return "{}-Hard".format(label[0].upper())
    if "easy" in label:
        return "{}-Easy".format(label[0].upper())

if __name__ == "__main__":
    base_path = "/media/mriva/LaCie/SATANN/synthetic_fine_segmentation_results/results_seg"
    # Iterating over each dataset size
    for dataset_size in [400]:
        base_dataset_path = os.path.join(base_path, "dataset_{}".format(dataset_size))

        test_set_size = 10
        element_shape = (28,28)
        stride = 28

        # Preparing the foreground
        fg_label = "T"
        fg_classes = [0, 1, 8]
        base_fg_positions = [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)]
        position_translation=0.2
        position_noise=0.1

        num_classes = len(fg_classes)
        classes = range(1,num_classes+1)

        # Also setting the image dimensions in advance
        image_dimensions = [256, 256]
        

        # Preparing dataset transforms:
        transform = tv.transforms.Compose(                                  # For the images:
            [tv.transforms.ToTensor(),                                      # Convert to torch.Tensor CxHxW type
            tv.transforms.Normalize((255/2,), (255/2,), inplace=True)])    # Normalize from [0,255] to [-1,1] range
        target_transform = tv.transforms.Compose(                           # For the labelmaps:
            [targetToTensor()])                                             # Convert to torch.Tensor type

        # Experiment configurations
        experimental_configs = [{"label": fg_label + "_hard_noise", "bg_classes": [0], "bg_amount": 3},
                                {"label": fg_label + "_easy_noise", "bg_classes": [7], "bg_amount": 3},
                                {"label": fg_label + "_veryhard_noise", "bg_classes": [0,1,8], "bg_amount": 6}]
        
        # Getting results for a specific experiment configuration
        for experimental_config in experimental_configs:
            # Preparing the test set
            test_dataset = CloStObDataset(base_dataset_name="fashion",
                                            image_dimensions=image_dimensions,
                                            size=test_set_size,
                                            fg_classes=fg_classes,
                                            fg_positions=base_fg_positions,
                                            position_translation=position_translation,
                                            position_noise=position_noise,
                                            bg_classes=experimental_config["bg_classes"], # Background class from config
                                            bg_amount=experimental_config["bg_amount"],
                                            flattened=False,
                                            lazy_load=False,
                                            fine_segment=True,
                                            transform=transform,
                                            target_transform=target_transform,
                                            start_seed=100000)
            # Getting results for each reference class shift
            for reference_class in classes:
                # Note: CSO functions take "which" class, like '0' for shirt or '8' for bag
                # While this test takes 1,2,3, hence the need for conversion
                converted_class = fg_classes[reference_class-1]
                shifts_anchors_set = [test_dataset.generate_reference_shifts(i, converted_class, element_shape=element_shape, stride=stride) for i in range(test_set_size)]
                shifts_set = [item for sublist in shifts_anchors_set for item in sublist[0]]  # Flattening
                anchors_set = [item for sublist in shifts_anchors_set for item in sublist[1]]  # Flattening
                all_anchors = anchors_set[:(len(anchors_set)//test_set_size)]

                # REFERENCE POSITION:
                #   Getting test-time precision and recall per class, per anchor for all inits
                initialization_paths = list(glob(os.path.join(base_dataset_path, experimental_config["label"] + "*")))
                initialization_paths = [item for item in initialization_paths if item[-2:] != ".5"] # skipping SATANN examples (where alpha > 0)
                precisions = {_class : {anchor: torch.zeros(test_set_size*len(initialization_paths)) for anchor in all_anchors} for _class in classes}
                recalls = {_class : {anchor: torch.zeros(test_set_size*len(initialization_paths)) for anchor in all_anchors} for _class in classes}
                for init_idx, initialization_path in enumerate(initialization_paths):
                    print("Doing {},ref {},{}".format(dataset_size, reference_class, os.path.split(initialization_path)[-1]))
                    # Loading the specified model
                    model_path = os.path.join(initialization_path, "best_model.pth")
                    model = UNet(input_channels=1, output_channels=4).to(device="cuda")
                    model.load_state_dict(torch.load(model_path))
                    model.eval()

                    # Running the model on the test data
                    outputs, truths = [], []
                    for item_pair in shifts_set:
                        inputs = item_pair["image"].unsqueeze(0).to(device="cuda")
                        with torch.set_grad_enabled(False):
                            outputs.append(model(inputs).detach().cpu())
                        truths.append(item_pair["labelmap"])
                    
                    outputs = torch.cat(outputs, dim=0)
                    truths = torch.stack(truths)

                    outputs_softmax = softmax(outputs, dim=1)  # Softmax outputs along class dimension
                    outputs_argmax = outputs_softmax.argmax(dim=1)  # Argmax outputs along class dimension
                
                    # computing metrics for all classes
                    for _class in classes:
                        class_precisions = precision(outputs_argmax, truths, _class)
                        class_recalls = recall(outputs_argmax, truths, _class)

                        for idx, (class_precision, anchor) in enumerate(zip(class_precisions, anchors_set)):
                            current_idx = floor((idx/len(all_anchors))+(init_idx*test_set_size))
                            precisions[_class][anchor][current_idx] = class_precision
                        for idx, (class_recall, anchor) in enumerate(zip(class_recalls, anchors_set)):
                            current_idx = floor((idx/len(all_anchors))+(init_idx*test_set_size))
                            recalls[_class][anchor][current_idx] = class_recall

                # Got all results for this configuration for this reference class
                # Averaging each anchor point
                for _class in classes:
                    for anchor in all_anchors:
                        precisions[_class][anchor] = torch.mean(precisions[_class][anchor])
                        recalls[_class][anchor] = torch.mean(recalls[_class][anchor])
                
                # One heatmap per base class
                for _class in classes:
                    # Preparing heatmap (shifting to numpy)
                    dimensions = sqrt(len(all_anchors))
                    recall_heatmap = np.zeros(image_dimensions)
                    # Assembling heatmap
                    for anchor in all_anchors:
                        other_end = tuple(map(sum, zip(anchor,element_shape)))
                        coordinates_set = tuple(np.s_[origin:end] for origin, end in zip(anchor, other_end))
                        recall_heatmap[coordinates_set] = recalls[_class][anchor].item()

                    # Preparing image
                    plt.imshow(recall_heatmap, vmin=0, vmax=1)
                    plt.title("Effects of reference {} on class {}".format(reference_class, _class))
                    mkdir("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/dataset_{}/{}".format(dataset_size, experimental_config["label"]))
                    plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/dataset_{}/{}/ref{}on{}.png".format(dataset_size, experimental_config["label"], reference_class, _class))
                    plt.clf()
