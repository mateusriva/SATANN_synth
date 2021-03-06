"""Script for making nice images from the heatmaps. This is all very hardcoded."""
import os, sys

import numpy as np
import matplotlib.pyplot as plt

import cv2

sys.path.append("/home/mriva/Recherche/PhD/SATANN/SATANN_synth")
from datasets.clostob.clostob_dataset import CloStObDataset
from utils import mkdir

def get_basic_image(fg_positions, no_class=None):
        # General dataset attributes
    image_dimensions = [160,160]
    test_set_size = 1
    fg_classes = [0, 1, 8]
    bg_classes = [0]
    bg_amount = 0

    if no_class is not None:
        fg_positions = [x for i,x in enumerate(fg_positions) if i != (no_class-1)]
        fg_classes = [x for i,x in enumerate(fg_classes) if i != (no_class-1)]

    test_dataset = CloStObDataset(base_dataset_name="fashion",
                                    image_dimensions=image_dimensions,
                                    size=test_set_size,
                                    fg_classes=fg_classes,
                                    fg_positions=fg_positions,
                                    position_translation=0,
                                    position_noise=0,
                                    bg_classes=bg_classes,
                                    bg_amount=bg_amount,
                                    bg_bboxes=None,
                                    flattened=False,
                                    lazy_load=False,
                                    fine_segment=False,
                                    start_seed=0)
    # Get basic image
    basic_image = next(iter(test_dataset))["image"]
    # Convert to float-RGB
    basic_image = (np.repeat(basic_image[...,None],3,axis=2)/255.0).astype(np.float32)
    return basic_image

def apply_heatmap(img, mask, use_rgb=False, colormap=cv2.COLORMAP_VIRIDIS):
    heatmap = cv2.applyColorMap(np.uint8(255 * mask), colormap)
    if use_rgb:
        heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
    heatmap = np.float32(heatmap) / 255

    if np.max(img) > 1:
        raise Exception(
            "The input image should np.float32 in the range [0, 1]")

    return cv2.addWeighted(heatmap, 0.7, img, 0.3, 0)

# First part: making the position histograms
def make_position_histogram(label, fg_positions, position_translation, position_noise, bg_bboxes):
    basic_image = get_basic_image(fg_positions)

    # General dataset attributes
    image_dimensions = [160,160]
    test_set_size = 1000
    fg_classes = [0, 1, 8]
    bg_classes = [0]
    bg_amount = 3
    
    test_dataset = CloStObDataset(base_dataset_name="fashion",
                                    image_dimensions=image_dimensions,
                                    size=test_set_size,
                                    fg_classes=fg_classes,
                                    fg_positions=fg_positions,
                                    position_translation=position_translation,
                                    position_noise=position_noise,
                                    bg_classes=bg_classes,
                                    bg_amount=bg_amount,
                                    bg_bboxes=bg_bboxes,
                                    flattened=False,
                                    lazy_load=False,
                                    fine_segment=False,
                                    start_seed=0)

    # Creating empty counting maps
    oi_count, noise_count = np.zeros(image_dimensions), np.zeros(image_dimensions)
    for sample in test_dataset:
        # Counting the pixels where class 1 OI is
        oi_count += sample["labelmap"] == 1
        noise_count += sample["bg_labelmap"] == 0

    # Normalising
    oi_count /= np.max(oi_count)
    noise_count /= np.max(noise_count)

    # Applying to the basic image
    oi_overlay = apply_heatmap(basic_image, oi_count, use_rgb=True, colormap=cv2.COLORMAP_VIRIDIS)
    noise_overlay = apply_heatmap(basic_image, noise_count, use_rgb=True, colormap=cv2.COLORMAP_VIRIDIS)

    # Saving figures
    plt.imshow(oi_count, cmap="Greens")
    ax = plt.gca()
    ax.axes.xaxis.set_visible(False)
    ax.axes.yaxis.set_visible(False)
    plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/results_pretty/{}_oi_map.png".format(label), bbox_inches="tight")
    #plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/results_pretty/{}_oi_map.eps".format(label), bbox_inches="tight")
    plt.clf()

    plt.imshow(noise_count, cmap="Reds")
    ax = plt.gca()
    ax.axes.xaxis.set_visible(False)
    ax.axes.yaxis.set_visible(False)
    plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/results_pretty/{}_noise_map.png".format(label), bbox_inches="tight")
    #plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/results_pretty/{}_noise_map.eps".format(label), bbox_inches="tight")
    plt.clf()
    
    # Saving overlays
    plt.imshow(oi_overlay)
    plt.axis("off")
    plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/results_pretty/{}_oi_overlay.png".format(label), bbox_inches="tight")
    #plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/results_pretty/{}_oi_overlay.eps".format(label), bbox_inches="tight")
    plt.clf()

    plt.imshow(noise_overlay)
    plt.axis("off")
    plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/results_pretty/{}_noise_overlay.png".format(label), bbox_inches="tight")
    #plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/results_pretty/{}_noise_overlay.eps".format(label), bbox_inches="tight")
    plt.clf()
    


# Overlaying heatmap to basic image
def overlay_heatmap_to_basic_image(label, config_label, _class, fg_positions, dataset_size):
    basic_image = get_basic_image(fg_positions, no_class=_class)

    # Load the corresponding heatmaps
    precision_heatmap = np.load("/media/mriva/LaCie/SATANN/synthetic_fine_segmentation_results/tests/reference_position/results_{}/dataset_{}/{}/ref{}on1_precision.npy".format(label, dataset_size, config_label, _class)) 
    recall_heatmap = np.load("/media/mriva/LaCie/SATANN/synthetic_fine_segmentation_results/tests/reference_position/results_{}/dataset_{}/{}/ref{}on1_recall.npy".format(label, dataset_size, config_label, _class)) 
    
    # Applying to the basic image
    precision_overlay = apply_heatmap(basic_image, precision_heatmap, use_rgb=True, colormap=cv2.COLORMAP_VIRIDIS)
    recall_overlay = apply_heatmap(basic_image, recall_heatmap, use_rgb=True, colormap=cv2.COLORMAP_VIRIDIS)

    # Saving figures - pure
    plt.imshow(precision_heatmap, cmap="viridis", vmin=0, vmax=1)
    ax = plt.gca()
    ax.axes.xaxis.set_visible(False)
    ax.axes.yaxis.set_visible(False)
    plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/results_pretty/{}_{}_{}_{}on1_precision_map.png".format(label, dataset_size, config_label, _class), bbox_inches="tight")
    #plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/results_pretty/{}_{}_{}_{}on1_precision_map.eps".format(label, dataset_size, config_label, _class), bbox_inches="tight")
    plt.clf()
    plt.imshow(recall_heatmap, cmap="viridis", vmin=0, vmax=1)
    ax = plt.gca()
    ax.axes.xaxis.set_visible(False)
    ax.axes.yaxis.set_visible(False)
    plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/results_pretty/{}_{}_{}_{}on1_recall_map.png".format(label, dataset_size, config_label, _class), bbox_inches="tight")
    #plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/results_pretty/{}_{}_{}_{}on1_recall_map.eps".format(label, dataset_size, config_label, _class), bbox_inches="tight")
    plt.clf()

    # Saving figures - overlay
    plt.imshow(precision_overlay)
    plt.axis("off")
    plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/results_pretty/{}_{}_{}_{}on1_precision_overlay.png".format(label, dataset_size, config_label, _class), bbox_inches="tight")
    #plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/results_pretty/{}_{}_{}_{}on1_precision_overlay.eps".format(label, dataset_size, config_label, _class), bbox_inches="tight")
    plt.clf()
    plt.imshow(recall_overlay)
    plt.axis("off")
    plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/results_pretty/{}_{}_{}_{}on1_recall_overlay.png".format(label, dataset_size, config_label, _class), bbox_inches="tight")
    #plt.savefig("/home/mriva/Recherche/PhD/SATANN/SATANN_synth/tests/reference_position/results_pretty/{}_{}_{}_{}on1_recall_overlay.eps".format(label, dataset_size, config_label, _class), bbox_inches="tight")
    plt.clf()

#make_position_histogram("seg", [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 0.2, 0.1, None)
#make_position_histogram("strict", [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 0.5, 0.0, (0.4, 0.0, 0.9, 0.5))
overlay_heatmap_to_basic_image("seg", "T_hard_noise", 1, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 10000)
overlay_heatmap_to_basic_image("seg", "T_hard_noise", 2, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 10000)
overlay_heatmap_to_basic_image("seg", "T_hard_noise", 3, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 10000)
overlay_heatmap_to_basic_image("seg", "T_hard_noise", 1, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 100)
overlay_heatmap_to_basic_image("seg", "T_hard_noise", 2, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 100)
overlay_heatmap_to_basic_image("seg", "T_hard_noise", 3, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 100)
overlay_heatmap_to_basic_image("seg", "T_hard_noise", 1, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 1000)
overlay_heatmap_to_basic_image("seg", "T_hard_noise", 2, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 1000)
overlay_heatmap_to_basic_image("seg", "T_hard_noise", 3, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 1000)
overlay_heatmap_to_basic_image("strict", "T_strict_noise", 1, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 50000)
overlay_heatmap_to_basic_image("strict", "T_strict_noise", 2, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 50000)
overlay_heatmap_to_basic_image("strict", "T_strict_noise", 3, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 50000)
overlay_heatmap_to_basic_image("strict", "T_strict_noise", 1, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 5000)
overlay_heatmap_to_basic_image("strict", "T_strict_noise", 2, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 5000)
overlay_heatmap_to_basic_image("strict", "T_strict_noise", 3, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 5000)
overlay_heatmap_to_basic_image("strict", "T_strict_noise", 1, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 10000)
overlay_heatmap_to_basic_image("strict", "T_strict_noise", 2, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 10000)
overlay_heatmap_to_basic_image("strict", "T_strict_noise", 3, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 10000)
overlay_heatmap_to_basic_image("strict", "T_strict_noise", 1, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 1000)
overlay_heatmap_to_basic_image("strict", "T_strict_noise", 2, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 1000)
overlay_heatmap_to_basic_image("strict", "T_strict_noise", 3, [(0.65, 0.3), (0.65, 0.7), (0.35, 0.7)], 1000)