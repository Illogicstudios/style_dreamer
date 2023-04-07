import os
from functools import partial

import sys

from pymel.core import *
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

# ######################################################################################################################

# TODO Change the prefs name for this project
_FILE_NAME_PREFS = "maya_tool"

# ######################################################################################################################


# TODO change class name
class MayaTool(QDialog):

    def __init__(self, prnt=wrapInstance(int(omui.MQtUtil.mainWindow()), QWidget)):
        # TODO change class name
        super(MayaTool, self).__init__(prnt)
        
        # Common Preferences (common preferences on all tools)
        self.__common_prefs = Prefs()
        # Preferences for this tool
        self.__prefs = Prefs(_FILE_NAME_PREFS)

        # Model attributes

        # UI attributes
        self.__ui_width = 500
        self.__ui_height = 300
        self.__ui_min_width = 300
        self.__ui_min_height = 200
        self.__ui_pos = QDesktopWidget().availableGeometry().center() - QPoint(self.__ui_width,self.__ui_height)/2

        self.__retrieve_prefs()

        # name the window
        # TODO change window name
        self.setWindowTitle("Maya Tool")
        # make the window a "tool" in Maya's eyes so that it stays on top when you click off
        self.setWindowFlags(QtCore.Qt.Tool)
        # Makes the object get deleted from memory, not just hidden, when it is closed.
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        # Create the layout, linking it to actions and refresh the display
        self.__create_ui()
        self.__refresh_ui()

    # Save preferences
    def __save_prefs(self):
        size = self.size()
        self.__prefs["window_size"] = {"width": size.width(), "height": size.height()}
        pos = self.pos()
        self.__prefs["window_pos"] = {"x": pos.x(), "y": pos.y()}

    # Retrieve preferences
    def __retrieve_prefs(self):
        if "window_size" in self.__prefs:
            size = self.__prefs["window_size"]
            self.__ui_width = size["width"]
            self.__ui_height = size["height"]

        if "window_pos" in self.__prefs:
            pos = self.__prefs["window_pos"]
            self.__ui_pos = QPoint(pos["x"],pos["y"])

    def showEvent(self, arg__1: QShowEvent) -> None:
        pass
        # self.__selection_callback = \
        #     OpenMaya.MEventMessage.addEventCallback("SelectionChanged", self.on_selection_changed)

    # Remove callbacks
    def hideEvent(self, arg__1: QCloseEvent) -> None:
        # OpenMaya.MMessage.removeCallback(self.__selection_callback)
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
        main_lyt.setContentsMargins(10, 15, 10, 15)
        main_lyt.setSpacing(12)
        self.setLayout(main_lyt)

    # Refresh the ui according to the model attribute
    def __refresh_ui(self):
        # TODO refresh the UI according to model attributes
        pass
