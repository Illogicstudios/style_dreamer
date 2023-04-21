import pymel.core as pm
from abc import *


class DepthDetail(ABC):
    def __init__(self, pos_array):
        self.__pos_array = pos_array

    def set_interp_on(self, remap_node):
        for index, interp_data in enumerate(self.__pos_array):
            interp_index = index + 2
            remap_node.value[interp_index].value_FloatValue.set(interp_data[0])
            remap_node.value[interp_index].value_Position.set(interp_data[1])
            remap_node.value[interp_index].value_Interp.set(3)

class CloseDetailed(DepthDetail):
    def __init__(self):
        super().__init__([(0.5, 0.0250), (0.8, 0.07), (0.9, 0.15)])


class UniformDetailed(DepthDetail):
    def __init__(self):
        super().__init__([])


class FarDetailed(DepthDetail):
    def __init__(self):
        super().__init__([(0.15, 0.8), (0.2, 0.93), (0.5, 0.975)])


class CloseAndFarDetailed(DepthDetail):
    def __init__(self):
        super().__init__([(0.25, 0.025), (0.4, 0.07), (0.45, 0.15), (0.5, 0.5),
                          (0.55, 0.85), (0.6, 0.93), (0.75, 0.975)])
