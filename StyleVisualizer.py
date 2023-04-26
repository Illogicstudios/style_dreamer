import os
import sys
from functools import partial
from shiboken2 import wrapInstance

import maya.OpenMayaUI as omui

from PySide2 import QtCore
from PySide2 import QtGui
from PySide2 import QtWidgets
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *

from utils import *

from Prefs import *

import StyleDreamer as sd


class CurrentImageLabel(QLabel):
    def __init__(self, path):
        super(CurrentImageLabel, self).__init__()
        self.setFrameStyle(QFrame.StyledPanel)
        self.__pixmap = QPixmap(path)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)

    def paintEvent(self, event):
        size = self.size()
        painter = QPainter(self)
        point = QtCore.QPoint(0, 0)
        scaledPix = self.__pixmap.scaled(size, QtCore.Qt.KeepAspectRatio,
                                         transformMode=QtCore.Qt.SmoothTransformation)
        point.setX((size.width() - scaledPix.width()) / 2)
        point.setY((size.height() - scaledPix.height()) / 2)
        painter.drawPixmap(point, scaledPix)

    # Change path of the Image and repaint it
    def set_path(self, path):
        self.__pixmap = QPixmap(path)
        self.repaint()


class CurrentImageLabelWidget(QWidget):
    def __init__(self, path):
        QWidget.__init__(self)
        self.__label = CurrentImageLabel(path)

        vb_layout = QVBoxLayout()
        vb_layout.setContentsMargins(4, 4, 4, 4)
        vb_layout.addWidget(self.__label)
        self.setLayout(vb_layout)

    # Change the Image path
    def set_path(self, path):
        self.__label.set_path(path)


class StyleVisualizer(QDialog):

    def __init__(self, controlnet_manager, prnt=wrapInstance(int(omui.MQtUtil.mainWindow()), QWidget)):
        super(StyleVisualizer, self).__init__(prnt)
        # Model attributes
        self.__controlnet_manager = controlnet_manager
        self.__current_image = None
        self.__input_files = []
        self.__input_used_files = []
        self.__output_files = []
        self.__request_eta = 0

        # UI attributes
        self.__ui_width = 800
        self.__ui_height = 700
        self.__ui_min_width = 530
        self.__ui_min_height = 550
        self.__ui_pos = QDesktopWidget().availableGeometry().center() - QPoint(self.__ui_width, self.__ui_height) / 2
        self.__ui_height_input_files_part = 80
        self.__ui_height_output_files_part = 100

        # name the window
        self.setWindowTitle("Style Dreamer Visualizer")
        # make the window a "tool" in Maya's eyes so that it stays on top when you click off
        self.setWindowFlags(QtCore.Qt.Tool)

        # Create the layout, linking it to actions and refresh the display
        self.__create_ui()
        self.__refresh_ui()

    # Setter of the ETA
    def set_eta(self, eta):
        self.__request_eta = eta

    # Getter of the ETA
    def get_eta(self):
        return self.__request_eta

    # Setter of the input files
    def set_input_files(self, input_filepaths):
        self.__input_files = input_filepaths

    # Setter of the input used files
    def set_input_used_files(self, input_render_used):
        self.__input_used_files = input_render_used

    # Setter of the output files
    def set_output_files(self, output_filepaths):
        self.__output_files = output_filepaths

    # Create the ui
    def __create_ui(self):
        # Reinit attributes of the UI
        self.setMinimumSize(self.__ui_min_width, self.__ui_min_height)
        self.resize(self.__ui_width, self.__ui_height)
        self.move(self.__ui_pos)

        # asset_path = os.path.dirname(__file__) + "/assets/asset.png"

        # Main Layout
        main_lyt = QVBoxLayout()
        main_lyt.setContentsMargins(8, 10, 8, 10)
        main_lyt.setSpacing(2)
        self.setLayout(main_lyt)

        self.__ui_current_img = CurrentImageLabelWidget(os.path.dirname(__file__) + "/assets/place_holder_img.png")
        main_lyt.addWidget(self.__ui_current_img, 6)

        self.__progress_bar = QProgressBar()
        self.__progress_bar.setFixedHeight(15)
        main_lyt.addWidget(self.__progress_bar)

        # Input Files List
        lyt_input_files = QVBoxLayout()
        main_lyt.addLayout(lyt_input_files)

        title_input_lyt = QHBoxLayout()
        title_input_lyt.setSpacing(10)
        title_input_lyt.addWidget(sd.StyleDreamer.get_separator())
        title_input_lbl = QLabel("Input Images")
        title_input_lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        title_input_lyt.addWidget(title_input_lbl)
        title_input_lyt.addWidget(sd.StyleDreamer.get_separator())
        lyt_input_files.addLayout(title_input_lyt)

        self.__ui_list_input_file = QListWidget()
        self.__ui_list_input_file.setIconSize(QSize(self.__ui_height_input_files_part + 20, 200))
        self.__ui_list_input_file.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.__ui_list_input_file.setSpacing(2)
        self.__ui_list_input_file.setFlow(QListWidget.LeftToRight)
        self.__ui_list_input_file.setFixedHeight(self.__ui_height_input_files_part)
        self.__ui_list_input_file.itemSelectionChanged.connect(self.__on_input_file_selected)
        lyt_input_files.addWidget(self.__ui_list_input_file)

        title_output_lyt = QHBoxLayout()
        title_output_lyt.setSpacing(10)
        title_output_lyt.addWidget(sd.StyleDreamer.get_separator())
        title_output_lbl = QLabel("Output Images")
        title_output_lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        title_output_lyt.addWidget(title_output_lbl)
        title_output_lyt.addWidget(sd.StyleDreamer.get_separator())
        main_lyt.addLayout(title_output_lyt)

        # Output files
        self.__ui_list_output_file = QListWidget()
        self.__ui_list_output_file.setIconSize(QSize(self.__ui_height_output_files_part + 36, 200))
        self.__ui_list_output_file.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.__ui_list_output_file.setSpacing(2)
        self.__ui_list_output_file.setFlow(QListWidget.LeftToRight)
        self.__ui_list_output_file.setFixedHeight(self.__ui_height_output_files_part)
        self.__ui_list_output_file.itemSelectionChanged.connect(self.__on_output_file_selected)
        main_lyt.addWidget(self.__ui_list_output_file)

    # Refresh the ui according to the model attribute
    def __refresh_ui(self):
        self.__refresh_current_img()
        self.refresh_input_files()
        self.refresh_output_files()
        self.refresh_progress_bar()

    # Set the focus on the input files
    def set_focus_input(self):
        self.raise_()
        self.__ui_list_input_file.setFocus()
        self.__ui_list_input_file.setCurrentItem(self.__ui_list_input_file.item(0))

    # Set the focus on the output files
    def set_focus_output(self):
        self.raise_()
        self.__ui_list_output_file.setFocus()
        self.__ui_list_output_file.setCurrentItem(self.__ui_list_output_file.item(0))

    # Refresh the current Image UI
    def __refresh_current_img(self):
        if self.__current_image is not None:
            self.__ui_current_img.set_path(self.__current_image)

    # Refresh the list of input images
    def refresh_input_files(self):
        self.__ui_list_input_file.clear()
        for name, file_path in self.__input_files:
            item = QListWidgetItem()
            if file_path in self.__input_used_files:
                item.setBackgroundColor(QColor(51, 120, 56))
                item.setToolTip("<b>" + name + "</b> used")
            else:
                item.setBackgroundColor(QColor(169, 64, 64))
                item.setToolTip("<b>" + name + "</b> rendered but not used")
            item.setIcon(QIcon(file_path))
            item.setData(Qt.UserRole, file_path)
            self.__ui_list_input_file.addItem(item)

    # Refresh the list of output images
    def refresh_output_files(self):
        self.__ui_list_output_file.clear()
        for file_path in self.__output_files:
            item = QListWidgetItem()
            item.setIcon(QIcon(file_path))
            item.setData(Qt.UserRole, file_path)
            self.__ui_list_output_file.addItem(item)

    # Refresh the progress bar according to the eta
    def refresh_progress_bar(self):
        self.__progress_bar.setEnabled(self.__controlnet_manager.is_requesting_dream())
        self.__progress_bar.setValue(self.__request_eta)

    # On Input file selected display in the current image
    def __on_input_file_selected(self):
        self.__on_file_selected(self.__ui_list_input_file, self.__ui_list_output_file)

    # On Output file selected display in the current image
    def __on_output_file_selected(self):
        self.__on_file_selected(self.__ui_list_output_file, self.__ui_list_input_file)

    # On file selected display in the current image
    def __on_file_selected(self, list_selection, list_unselection):
        selected_items = list_selection.selectedItems()
        list_unselection.clearSelection()
        if len(selected_items) == 1:
            self.__current_image = selected_items[0].data(Qt.UserRole)
        else:
            self.__current_image = os.path.dirname(__file__) + "/assets/place_holder_img.png"
        self.__refresh_current_img()
