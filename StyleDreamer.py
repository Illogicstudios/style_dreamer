import math
import os
from enum import Enum
from functools import partial

import sys

import pymel.core as pm
import maya.OpenMayaUI as omui

from PySide2 import QtCore
from PySide2 import QtGui
from PySide2 import QtWidgets
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *

from shiboken2 import wrapInstance

from utils import *

from Prefs import *

import maya.OpenMaya as OpenMaya

from SDSlider import *
import DepthDetail
from DepthDetail import *

# ######################################################################################################################

_FILE_NAME_PREFS = "style_dreamer"

DEPTH_NAME = "style_dreamer_depth"
NORMAL_NAME = "style_dreamer_normal"
EDGES_NAME = "style_dreamer_edges"

_MAX_BATCH_SIZE = 8

# ######################################################################################################################

BEAUTY_NAME = "beauty"

from ControlNetManager import *


class StyleDreamer(QDialog):

    @staticmethod
    def get_separator(vertical=False):
        line = QFrame()
        line.setFrameShape(QFrame.VLine if vertical else QFrame.HLine)
        line.setFrameShadow(QFrame.Raised)
        return line

    @staticmethod
    def is_point_in_front_of_camera(cam_transform, pt):
        cam_pos = cam_transform.getTranslation(space="world")
        world_matrix = cam_transform.getMatrix(worldSpace=True)
        front_vector = pm.dt.Point(world_matrix[3][:2])
        pt_vector = cam_pos - pt
        front_vector.normalize()
        pt_vector.normalize()
        return pm.dt.dot(front_vector, pt_vector) >= 0

    @staticmethod
    def find_boundaries_from_camera(cam_transform):
        # Get all mesh transform nodes in the scene
        mesh_transforms = [node.getParent() for node in pm.ls(type="mesh")]

        distances_min = []
        distances_max = []
        # Loop through all mesh transform nodes
        for transform in mesh_transforms:
            # Get the bounding box corners in world space
            bbox = transform.getBoundingBox(space="world")
            max_dist = None
            min_dist = None
            min_max_point = [bbox.min(), bbox.max()]

            for ptx in min_max_point:
                for pty in min_max_point:
                    for ptz in min_max_point:
                        pt = pm.dt.Point(ptx[0], pty[1], ptz[2])
                        if not StyleDreamer.is_point_in_front_of_camera(cam_transform, pt):
                            continue
                        distance = (cam_transform.getTranslation(space="world") - pt).length()
                        if max_dist is None or max_dist < distance:
                            max_dist = distance
                        if min_dist is None or min_dist > distance:
                            min_dist = distance
            if min_dist is not None:
                distances_min.append(min_dist)
            if max_dist is not None:
                distances_max.append(max_dist)

        dist_min_res = min(distances_min) if len(distances_min) > 0 else 0
        dist_max_res = max(distances_max) if len(distances_max) > 0 else 0
        return dist_min_res, dist_max_res

    # Test if Arnold is loaded and display a warning popup if it is not
    @staticmethod
    def test_arnold_renderer():
        arnold_renderer_loaded = pm.objExists("defaultArnoldRenderOptions")
        if not arnold_renderer_loaded:
            msg = QMessageBox()
            msg.setWindowTitle("Error Style Dreamer with Arnold Renderer")
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Arnold Renderer not loaded")
            msg.setInformativeText('Style Dreamer can\'t run without the Arnold Renderer loaded. You '
                                   'can load the Arnold Renderer by opening the Render Settings Window')
            msg.exec_()
        return arnold_renderer_loaded

    def __init__(self, url_server, prnt=wrapInstance(int(omui.MQtUtil.mainWindow()), QWidget)):
        super(StyleDreamer, self).__init__(prnt)

        # Common Preferences (common preferences on all tools)
        self.__common_prefs = Prefs()
        # Preferences for this tool
        self.__prefs = Prefs(_FILE_NAME_PREFS)

        # Model attributes
        self.__refreshing = False
        self.__url_server = url_server
        self.__controlnet_manager = ControlNetManager(self.__url_server, self.__on_dream_done)
        self.__block_new_request = False
        self.__previous_seed = -1
        self.__depth_types = {
            "uniform": ("Details uniformly close to the camera", UniformDetailed()),
            "close": ("Details close to the camera", CloseDetailed()),
            "far": ("Details far from the camera", FarDetailed()),
            "close_and_far": ("Details close and far from the camera", CloseAndFarDetailed()),
        }
        self.__init_attributes()

        # UI attributes
        self.__ui_width = 600
        self.__ui_height = 850
        self.__ui_min_width = 500
        self.__ui_min_height = 750
        self.__ui_pos = QDesktopWidget().availableGeometry().center() - QPoint(self.__ui_width, self.__ui_height) / 2

        self.__retrieve_prefs()

        # Model attributes after retrieve prefs
        self.__image_count_slider = \
            SDSlider(self, SDSliderType.IntSlider, "Image Count", 1, 512,
                     "Number of Image by Request \nLess than 8 or multiple of 8 is faster\nAvoid prime numbers")
        self.__sampling_steps_slider = \
            SDSlider(self, SDSliderType.IntSlider, "Sampling Steps", 1, 150, "Number of Steps for each Image Request")
        self.__cfg_scale_slider = \
            SDSlider(self, SDSliderType.IntSlider, "CFG Scale", 1, 30, "Prompt Strength (Lower is more creative)")
        self.__width_slider = \
            SDSlider(self, SDSliderType.IntSlider, "Width", 1, 1920, "Width of the Input and Output Images")
        self.__height_slider = \
            SDSlider(self, SDSliderType.IntSlider, "Height", 1, 1920, "Height of the Input and Output Images")
        self.__denoising_strength_slider = \
            SDSlider(self, SDSliderType.FloatSlider, "Denoising Strength", 0, 1,
                     "At 0 : Use Beauty as input\nAt 1: Don't use beauty at all)")
        self.__weight_depth_slider = \
            SDSlider(self, SDSliderType.FloatSlider, "Weight Depth Guide", 0, 2, "At 0 : Don't use Depth Map at all")
        self.__weight_normal_slider = \
            SDSlider(self, SDSliderType.FloatSlider, "Weight Normal Guide", 0, 2, "At 0 : Don't use Normal Map at all")
        self.__weight_edges_slider = \
            SDSlider(self, SDSliderType.FloatSlider, "Weight Edges Guide", 0, 2, "At 0 : Don't use Edges Map at all")
        self.__set_value_sliders()

        # name the window
        self.setWindowTitle("Style Dreamer")
        # make the window a "tool" in Maya's eyes so that it stays on top when you click off
        self.setWindowFlags(QtCore.Qt.Tool)
        # Makes the object get deleted from memory, not just hidden, when it is closed.
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        # Create the layout, linking it to actions and refresh the display
        if StyleDreamer.test_arnold_renderer():
            # Create the layout, linking it to actions and refresh the display
            self.__create_ui()
            datas = self.__get_datas()
            self.__controlnet_manager.set_datas(datas)
            self.__controlnet_manager.retrieve_renders()
            self.__refresh_ui()
        else:
            self.close()

    def __init_attributes(self):
        self.__prompt = ""
        self.__neg_prompt = ""
        self.__random_seed = True
        self.__seed = -1
        self.__depth_min_dist = 0
        self.__depth_max_dist = 0
        self.__image_count = 1
        self.__sampling_steps = 15
        self.__cfg_scale = 7
        self.__denoising_strength = 1.0
        self.__weight_depth = 1.0
        self.__weight_normal = 1.0
        self.__weight_edges = 1.0
        self.__depth_type = "uniform"
        self.__width_img = pm.getAttr("defaultResolution.width")
        self.__height_img = pm.getAttr("defaultResolution.height")

    def __set_value_sliders(self):
        self.__image_count_slider.set_value(self.__image_count)
        self.__sampling_steps_slider.set_value(self.__sampling_steps)
        self.__cfg_scale_slider.set_value(self.__cfg_scale)
        self.__width_slider.set_value(self.__width_img)
        self.__height_slider.set_value(self.__height_img)
        self.__denoising_strength_slider.set_value(self.__denoising_strength)
        self.__weight_depth_slider.set_value(self.__weight_depth)
        self.__weight_normal_slider.set_value(self.__weight_normal)
        self.__weight_edges_slider.set_value(self.__weight_edges)

    def __reinit(self):
        self.__init_attributes()
        self.__set_value_sliders()
        self.__refresh_ui()
        self.__on_slider_render_changed()

    # Save preferences
    def __save_prefs(self):
        size = self.size()
        self.__prefs["window_size"] = {"width": size.width(), "height": size.height()}
        pos = self.pos()
        self.__prefs["window_pos"] = {"x": pos.x(), "y": pos.y()}
        self.__prefs["prompt"] = str(self.__ui_prompt.toPlainText())
        self.__prefs["neg_prompt"] = str(self.__ui_neg_prompt.toPlainText())
        self.__prefs["image_count"] = int(self.__image_count_slider.get_value())
        self.__prefs["sampling_steps"] = int(self.__sampling_steps_slider.get_value())
        self.__prefs["cfg_scale"] = int(self.__cfg_scale_slider.get_value())
        self.__prefs["denoising_strength"] = float(self.__denoising_strength_slider.get_value())
        self.__prefs["weight_depth"] = float(self.__weight_depth_slider.get_value())
        self.__prefs["weight_normal"] = float(self.__weight_normal_slider.get_value())
        self.__prefs["weight_edges"] = float(self.__weight_edges_slider.get_value())
        self.__prefs["depth_type"] = self.__depth_type

    # Retrieve preferences
    def __retrieve_prefs(self):
        if "window_size" in self.__prefs:
            size = self.__prefs["window_size"]
            self.__ui_width = size["width"]
            self.__ui_height = size["height"]
        if "window_pos" in self.__prefs:
            pos = self.__prefs["window_pos"]
            self.__ui_pos = QPoint(pos["x"], pos["y"])
        if "prompt" in self.__prefs:
            self.__prompt = self.__prefs["prompt"]
        if "neg_prompt" in self.__prefs:
            self.__neg_prompt = self.__prefs["neg_prompt"]
        if "image_count" in self.__prefs:
            self.__image_count = self.__prefs["image_count"]
        if "sampling_steps" in self.__prefs:
            self.__sampling_steps = self.__prefs["sampling_steps"]
        if "cfg_scale" in self.__prefs:
            self.__cfg_scale = self.__prefs["cfg_scale"]
        if "denoising_strength" in self.__prefs:
            self.__denoising_strength = self.__prefs["denoising_strength"]
        if "weight_depth" in self.__prefs:
            self.__weight_depth = self.__prefs["weight_depth"]
        if "weight_normal" in self.__prefs:
            self.__weight_normal = self.__prefs["weight_normal"]
        if "weight_edges" in self.__prefs:
            self.__weight_edges = self.__prefs["weight_edges"]
        if "depth_type" in self.__prefs:
            self.__depth_type = self.__prefs["depth_type"]

    def showEvent(self, arg__1: QShowEvent) -> None:
        pass

    # Remove callbacks
    def hideEvent(self, arg__1: QCloseEvent) -> None:
        self.__controlnet_manager.on_close()
        self.__save_prefs()

    # Create the ui
    def __create_ui(self):
        # Reinit attributes of the UI
        self.setMinimumSize(self.__ui_min_width, self.__ui_min_height)
        self.resize(self.__ui_width, self.__ui_height)
        self.move(self.__ui_pos)

        # asset_path = os.path.dirname(__file__) + "/assets/asset.png"

        # Main Layout
        main_lyt = QVBoxLayout()
        main_lyt.setContentsMargins(5, 7, 5, 7)
        main_lyt.setSpacing(5)
        self.setLayout(main_lyt)

        # Content Layout
        content_layout_widget = QFrame()
        content_layout_widget.setFrameStyle(QFrame.Box)
        content_layout_widget.setFrameShadow(QFrame.Sunken)
        content_layout = QVBoxLayout(content_layout_widget)
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(4)
        main_lyt.addWidget(content_layout_widget)
        self.__ui_prompt = QPlainTextEdit()
        self.__ui_prompt.setPlaceholderText("Prompt")
        content_layout.addWidget(self.__ui_prompt, 3)
        self.__ui_neg_prompt = QPlainTextEdit()
        self.__ui_neg_prompt.setPlaceholderText("Negative Prompt")
        content_layout.addWidget(self.__ui_neg_prompt, 2)

        layout_gen_param = QHBoxLayout()
        layout_gen_param.setSpacing(8)
        layout_gen_param.setAlignment(Qt.AlignTop)
        content_layout.addLayout(layout_gen_param)

        # image Count | Sampling Steps | CFG Scale
        lyt_image_sampling_prompt = QVBoxLayout()
        lyt_image_sampling_prompt.setSpacing(4)
        lyt_image_sampling_prompt.addWidget(self.__image_count_slider.create_ui())
        lyt_image_sampling_prompt.addWidget(StyleDreamer.get_separator())
        lyt_image_sampling_prompt.addWidget(self.__sampling_steps_slider.create_ui())
        lyt_image_sampling_prompt.addWidget(StyleDreamer.get_separator())
        lyt_image_sampling_prompt.addWidget(self.__cfg_scale_slider.create_ui())
        layout_gen_param.addLayout(lyt_image_sampling_prompt, 1)

        layout_gen_param.addWidget(StyleDreamer.get_separator(True))

        # Seed and Size
        lyt_seed_size = QVBoxLayout()
        lyt_seed_size.setContentsMargins(0, 5, 0, 5)

        lyt_seed_1 = QHBoxLayout()
        self.__ui_random_seed_cb = QCheckBox("Random Seed")
        self.__ui_random_seed_cb.stateChanged.connect(self.__on_random_seed_checked)
        self.__ui_previous_seed_btn = QPushButton("Previous Seed")
        self.__ui_previous_seed_btn.clicked.connect(self.__set_previous_seed)
        lyt_seed_1.addWidget(self.__ui_random_seed_cb, alignment=Qt.AlignCenter)
        lyt_seed_1.addWidget(self.__ui_previous_seed_btn)
        lyt_seed_size.addLayout(lyt_seed_1)
        lyt_seed_2 = QHBoxLayout()
        lbl_seed = QLabel("Seed")
        lbl_seed.setToolTip("If -1 the seed will be random")
        lyt_seed_2.addWidget(lbl_seed)
        self.__ui_seed = QLineEdit()
        validator = QRegExpValidator(QtCore.QRegExp('(^-1|[0-9]+$|^$)'))
        self.__ui_seed.setValidator(validator)
        self.__ui_seed.textChanged.connect(self.__on_seed_modified)
        self.__ui_seed.editingFinished.connect(self.__on_seed_editing_finished)
        lyt_seed_2.addWidget(self.__ui_seed)
        lyt_seed_size.addLayout(lyt_seed_2)
        lyt_seed_size.addWidget(StyleDreamer.get_separator())
        lyt_seed_size.addWidget(self.__width_slider.create_ui())
        lyt_seed_size.addWidget(self.__height_slider.create_ui())
        layout_gen_param.addLayout(lyt_seed_size, 1)

        # Render Input Strength and Controlnet Weight
        content_layout.addWidget(StyleDreamer.get_separator())
        content_layout.addWidget(self.__denoising_strength_slider.create_ui())
        self.__denoising_strength_slider.add_value_changed_callback(self.__refresh_submit_btn)
        self.__denoising_strength_slider.add_value_submit_callback(self.__on_slider_render_changed)
        content_layout.addWidget(self.__weight_depth_slider.create_ui())
        self.__weight_depth_slider.add_value_changed_callback(self.__refresh_depth_options)
        self.__weight_depth_slider.add_value_submit_callback(self.__on_slider_render_changed)
        content_layout.addWidget(self.__weight_normal_slider.create_ui())
        self.__weight_normal_slider.add_value_changed_callback(self.__refresh_submit_btn)
        self.__weight_normal_slider.add_value_submit_callback(self.__on_slider_render_changed)
        content_layout.addWidget(self.__weight_edges_slider.create_ui())
        self.__weight_edges_slider.add_value_changed_callback(self.__refresh_submit_btn)
        self.__weight_edges_slider.add_value_submit_callback(self.__on_slider_render_changed)

        # Option Layout
        self.__ui_option_widget = QFrame()
        self.__ui_option_widget.setFrameStyle(QFrame.Box)
        self.__ui_option_widget.setFrameShadow(QFrame.Sunken)
        option_layout = QHBoxLayout(self.__ui_option_widget)
        content_layout.setContentsMargins(5, 5, 5, 5)
        main_lyt.addWidget(self.__ui_option_widget)

        # Depth Map Distance
        lyt_depth_param = QHBoxLayout()
        lyt_depth_dist = QVBoxLayout()
        lyt_depth_min_dist = QHBoxLayout()
        lyt_depth_max_dist = QHBoxLayout()
        lyt_depth_min_dist.addWidget(QLabel("Depth Min Distance"))
        lyt_depth_max_dist.addWidget(QLabel("Depth Max Distance"))
        validator = QRegExpValidator(QtCore.QRegExp('^[0-9]*\.?[0-9]*$'))
        self.__ui_depth_min_dist = QLineEdit()
        self.__ui_depth_min_dist.setValidator(validator)
        self.__ui_depth_min_dist.editingFinished.connect(self.__on_depth_dist_changed)
        self.__ui_depth_max_dist = QLineEdit()
        self.__ui_depth_max_dist.setValidator(validator)
        self.__ui_depth_max_dist.editingFinished.connect(self.__on_depth_dist_changed)
        lyt_depth_min_dist.addWidget(self.__ui_depth_min_dist)
        lyt_depth_max_dist.addWidget(self.__ui_depth_max_dist)
        lyt_depth_dist.addLayout(lyt_depth_min_dist)
        lyt_depth_dist.addLayout(lyt_depth_max_dist)
        lyt_depth_param.addLayout(lyt_depth_dist)
        self.__ui_process_depth_dist_btn = QPushButton()
        self.__ui_process_depth_dist_btn.setIcon(QIcon(os.path.dirname(__file__) + "/assets/process.png"))
        self.__ui_process_depth_dist_btn.setIconSize(QSize(22, 22))
        self.__ui_process_depth_dist_btn.setFixedSize(QSize(30, 30))
        self.__ui_process_depth_dist_btn.pressed.connect(self.__retrieve_depth_distance)
        lyt_depth_param.addWidget(self.__ui_process_depth_dist_btn)
        option_layout.addLayout(lyt_depth_param, 1)

        option_layout.addWidget(StyleDreamer.get_separator(True))

        lyt_depth_type = QVBoxLayout()
        lbl_depth_type = QLabel("Depth Details")
        lyt_depth_type.addWidget(lbl_depth_type, alignment=Qt.AlignCenter)
        self.__ui_depth_type_cbb = QComboBox()
        for key, depth_data in self.__depth_types.items():
            self.__ui_depth_type_cbb.addItem(depth_data[0], key)
        self.__ui_depth_type_cbb.currentIndexChanged.connect(self.__on_depth_type_changed)
        lyt_depth_type.addWidget(self.__ui_depth_type_cbb)
        option_layout.addLayout(lyt_depth_type, 1)

        lyt_bottom = QGridLayout()
        lyt_bottom.setColumnStretch(0, 1)
        lyt_bottom.setColumnStretch(1, 1)
        lyt_bottom.setColumnStretch(2, 3)
        self.__reinit_params_btn = QPushButton("Reinit Parameters")
        self.__reinit_params_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.__reinit_params_btn.clicked.connect(self.__reinit)
        lyt_bottom.addWidget(self.__reinit_params_btn, 0, 0, 2, 1)

        self.__open_modal_btn = QPushButton("Visualizer")
        self.__open_modal_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.__open_modal_btn.clicked.connect(self.__on_open_visualizer)
        lyt_bottom.addWidget(self.__open_modal_btn, 0, 1, 2, 1)
        self.__render_btn = QPushButton("Render")
        self.__render_btn.setFixedHeight(30)
        self.__render_btn.clicked.connect(self.__on_render)
        lyt_bottom.addWidget(self.__render_btn, 0, 2, 1, 1)
        self.__dream_btn = QPushButton("Dream Style")
        self.__dream_btn.setFixedHeight(30)
        self.__dream_btn.clicked.connect(self.__on_dream)
        lyt_bottom.addWidget(self.__dream_btn, 1, 2, 1, 1)
        main_lyt.addLayout(lyt_bottom)

    # Refresh the ui according to the model attribute
    def __refresh_ui(self):
        self.__refresh_prompt()
        self.__refresh_seed()
        self.__refresh_sliders()
        self.__refresh_depth_distance()
        self.__refresh_depth_options()
        self.__refresh_depth_type()
        self.__refresh_submit_btn()

    def __refresh_prompt(self):
        self.__ui_prompt.setPlainText(self.__prompt)
        self.__ui_neg_prompt.setPlainText(self.__neg_prompt)

    def __refresh_seed(self):
        self.__ui_seed.setText(str(self.__seed))
        self.__ui_random_seed_cb.setChecked(self.__random_seed)

    def __refresh_sliders(self):
        self.__image_count_slider.refresh_ui()
        self.__sampling_steps_slider.refresh_ui()
        self.__cfg_scale_slider.refresh_ui()
        self.__width_slider.refresh_ui()
        self.__height_slider.refresh_ui()
        self.__denoising_strength_slider.refresh_ui()
        self.__weight_depth_slider.refresh_ui()
        self.__weight_normal_slider.refresh_ui()
        self.__weight_edges_slider.refresh_ui()

    def __refresh_submit_btn(self):
        beauty_active = float(self.__denoising_strength_slider.get_value()) < 1.0
        depth_active = float(self.__weight_depth_slider.get_value()) > 0.0
        normal_active = float(self.__weight_normal_slider.get_value()) > 0.0
        edges_active = float(self.__weight_edges_slider.get_value()) > 0.0
        depth_valid = self.__depth_min_dist != self.__depth_max_dist

        img_requested = []
        if beauty_active: img_requested.append(BEAUTY_NAME)
        if depth_active: img_requested.append(DEPTH_NAME)
        if normal_active: img_requested.append(NORMAL_NAME)
        if edges_active: img_requested.append(EDGES_NAME)

        self.__render_btn.setEnabled(not self.__block_new_request and not depth_active or depth_active and depth_valid)
        self.__dream_btn.setEnabled(not self.__block_new_request and self.__controlnet_manager.has_imgs(img_requested))

    def __refresh_depth_distance(self):
        self.__refreshing = True
        self.__ui_depth_min_dist.setText(str(self.__depth_min_dist))
        self.__ui_depth_max_dist.setText(str(self.__depth_max_dist))
        self.__refreshing = False

    def __refresh_depth_type(self):
        for index in range(self.__ui_depth_type_cbb.count()):
            if self.__ui_depth_type_cbb.itemData(index, Qt.UserRole) == self.__depth_type:
                self.__ui_depth_type_cbb.setCurrentIndex(index)

    def __on_slider_render_changed(self):
        self.__controlnet_manager.set_datas(self.__get_datas())
        self.__controlnet_manager.display_render(False, False)

    def __refresh_depth_options(self):
        self.__ui_option_widget.setEnabled(not float(self.__weight_depth_slider.get_value()) == 0.0)
        self.__refresh_submit_btn()

    def __retrieve_depth_distance(self):
        cam = None
        for vp in pm.getPanel(type="modelPanel"):
            cam = pm.modelEditor(vp, q=1, av=1, cam=1)
        depth_min_dist, depth_max_dist = StyleDreamer.find_boundaries_from_camera(cam)
        self.__depth_min_dist = round(depth_min_dist, 3)
        self.__depth_max_dist = round(depth_max_dist, 3)
        self.__refresh_depth_distance()
        self.__refresh_submit_btn()

    def __on_depth_dist_changed(self):
        if not self.__refreshing:
            depth_min_str = self.__ui_depth_min_dist.text()
            if len(depth_min_str) > 0:
                self.__depth_min_dist = float(depth_min_str)

            depth_max_str = self.__ui_depth_max_dist.text()
            if len(depth_max_str) > 0:
                self.__depth_max_dist = float(depth_max_str)

            if self.__depth_max_dist < self.__depth_min_dist:
                self.__depth_max_dist = self.__depth_min_dist
            self.__refresh_depth_distance()
            self.__refresh_submit_btn()

    def __on_depth_type_changed(self, index):
        self.__depth_type = self.__ui_depth_type_cbb.itemData(index, Qt.UserRole)

    def __on_random_seed_checked(self, state):
        self.__random_seed = state == 2
        if self.__random_seed:
            self.__seed = -1
        elif self.__seed == -1:
            self.__seed = 0
        self.__refresh_seed()

    def __on_seed_modified(self, seed):
        try:
            self.__seed = int(seed)
            if self.__seed == -1:
                self.__random_seed = True
            else:
                self.__random_seed = False
            self.__refresh_seed()
        except:
            # Nothing
            pass

    def __on_seed_editing_finished(self):
        self.__ui_seed.setText(str(self.__seed))

    def __set_previous_seed(self):
        self.__seed = self.__previous_seed
        self.__refresh_seed()

    def __get_batch_param(self):
        image_count = int(self.__image_count_slider.get_value())
        if image_count <= 8:
            return 1, image_count
        else:
            batch_size = 1
            for bs in range(8, 0, -1):
                if image_count % bs == 0:
                    batch_size = bs
                    break
            return image_count / batch_size, batch_size

    def __get_datas(self):
        batch_count, batch_size = self.__get_batch_param()
        datas = {
            "prompt": str(self.__ui_prompt.toPlainText()),
            "negative_prompt": str(self.__ui_neg_prompt.toPlainText()),
            "seed": self.__seed,
            "batch_count": batch_count,
            "batch_size": batch_size,
            "sampling_steps": int(self.__sampling_steps_slider.get_value()),
            "cfg_scale": int(self.__cfg_scale_slider.get_value()),
            "denoising_strength": float(self.__denoising_strength_slider.get_value()),
            "weight_depth": float(self.__weight_depth_slider.get_value()),
            "weight_normal": float(self.__weight_normal_slider.get_value()),
            "weight_edges": float(self.__weight_edges_slider.get_value()), "depth_min_dist": self.__depth_min_dist,
            "depth_max_dist": self.__depth_max_dist,
            "depth_type": self.__depth_types[self.__depth_type][1],
            "width": int(self.__width_slider.get_value()),
            "height": int(self.__height_slider.get_value())
        }
        return datas

    def __on_dream(self):
        self.__previous_seed = self.__seed
        self.__block_new_request = True
        self.__refresh_submit_btn()
        datas = self.__get_datas()
        self.__controlnet_manager.set_datas(datas)
        self.__controlnet_manager.display_render()
        threading.Thread(target=self.__controlnet_manager.request_controlnet).start()

    def __on_open_visualizer(self):
        self.__controlnet_manager.display_render(False)

    def __on_render(self):
        self.__block_new_request = True
        self.__refresh_submit_btn()

        datas = self.__get_datas()
        self.__controlnet_manager.set_datas(datas)

        beauty_active = datas["denoising_strength"] < 1
        depth_active = datas["weight_depth"] > 0
        normal_active = datas["weight_normal"] > 0
        edges_active = datas["weight_edges"] > 0

        if beauty_active or depth_active or normal_active or edges_active:
            self.__controlnet_manager.prepare_cn_render()
            self.__controlnet_manager.cn_render()
        self.__controlnet_manager.display_render()

        self.__block_new_request = False
        self.__refresh_submit_btn()

    def __on_dream_done(self,seed):
        self.__previous_seed = seed
        self.__block_new_request = False
        self.__refresh_submit_btn()