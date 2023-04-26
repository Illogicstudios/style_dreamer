from enum import Enum
from PySide2 import QtCore
from PySide2 import QtGui
from PySide2 import QtWidgets
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *


class SDSliderType(Enum):
    IntSlider = 0
    FloatSlider = 1


class SDSlider(QWidget):
    def __init__(self, style_dreamer, type, title, min, max, tooltip="", parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.__style_dreamer = style_dreamer
        self.__type = type
        self.__tooltip = tooltip
        self.__mult = 1000 if self.__type == SDSliderType.FloatSlider else 1
        self.__value = min
        self.__min = min
        self.__max = max
        self.__title = title
        self.__ui_slider = None
        self.__ui_line_edit = None

    # Create the Slider/Label/LineEdit UI
    def create_ui(self):
        main_widget = QWidget()
        main_lyt = QVBoxLayout(main_widget)
        main_lyt.setContentsMargins(5, 5, 5, 5)
        main_lyt.setSpacing(5)

        top_lyt = QHBoxLayout()
        main_lyt.addLayout(top_lyt)

        lbl = QLabel(self.__title)
        lbl.setToolTip(self.__tooltip)
        top_lyt.addWidget(lbl)

        self.__ui_line_edit = QLineEdit(str(self.__value))
        self.__ui_line_edit.setToolTip(self.__tooltip)
        self.__ui_line_edit.setFixedWidth(50)
        self.__ui_line_edit.editingFinished.connect(self.__on_line_edit_changed)
        top_lyt.addWidget(self.__ui_line_edit, alignment=Qt.AlignRight)

        self.__ui_slider = QSlider(Qt.Horizontal)
        self.__ui_slider.setMinimum(self.__min * self.__mult)
        self.__ui_slider.setMaximum(self.__max * self.__mult)
        self.__ui_slider.valueChanged.connect(self.__on_slider_changed)
        self.__ui_slider.setToolTip(self.__tooltip)
        main_lyt.addWidget(self.__ui_slider)
        return main_widget

    # Refresh the UI
    def refresh_ui(self):
        if self.__ui_slider:
            self.__ui_slider.setValue(int(self.__value * self.__mult))
        if self.__ui_line_edit:
            self.__ui_line_edit.setText(str(self.__value))

    # On slider changed
    def __on_slider_changed(self, value):
        self.__value = value / self.__mult
        if self.__type is SDSliderType.IntSlider:
            self.__value = int(value)
        self.__ui_line_edit.setText(str(self.__value))

    # On line changed
    def __on_line_edit_changed(self):
        str_value = self.__ui_line_edit.text()
        self.__value = float(str_value)
        self.__ui_slider.setValue(int(self.__value * self.__mult))

    # Add callback for when value changes
    def add_changed_callback(self, callback):
        self.__ui_slider.sliderMoved.connect(callback)
        self.__ui_line_edit.editingFinished.connect(callback)

    # Add callback for when value is submitted
    def add_submit_callback(self, callback):
        self.__ui_slider.sliderReleased.connect(callback)
        self.__ui_line_edit.editingFinished.connect(callback)

    # Add callback for when slider move
    def add_slider_moved_callback(self, callback):
        self.__ui_slider.sliderMoved.connect(callback)

    # Add callback for when slider is released
    def add_slider_released_callback(self, callback):
        self.__ui_slider.sliderReleased.connect(callback)

    # Setter of the min value
    def set_min(self,min):
        self.__min = min
        if self.__ui_slider:
            self.__ui_slider.setRange(self.__min * self.__mult, self.__max * self.__mult)

    # Setter of the max value
    def set_max(self,max):
        self.__max = max
        if self.__ui_slider:
            self.__ui_slider.setRange(self.__min * self.__mult, self.__max * self.__mult)

    # Getter of the value
    def get_value(self):
        return self.__value

    # Setter of the value
    def set_value(self, value):
        self.__value = value
