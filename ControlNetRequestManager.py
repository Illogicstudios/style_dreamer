import re

from pymel.core import *
import mtoa.aovs as aovs

from StyleDreamer import DepthType

# ######################################################################################################################

_DEPTH_AOV_NAME = "style_dreamer_depth"
_NORMAL_AOV_NAME = "style_dreamer_normal"
_EDGES_AOV_NAME = "style_dreamer_edges"

# ######################################################################################################################

class ControlNetRequestManager:
    @staticmethod
    def __set_features_overrides():
        setAttr("defaultArnoldRenderOptions.ignoreTextures", 0)
        setAttr("defaultArnoldRenderOptions.ignoreShaders", 0)
        setAttr("defaultArnoldRenderOptions.ignoreAtmosphere", 1)
        setAttr("defaultArnoldRenderOptions.ignoreLights", 0)
        setAttr("defaultArnoldRenderOptions.ignoreShadows", 0)
        setAttr("defaultArnoldRenderOptions.ignoreSubdivision", 0)
        setAttr("defaultArnoldRenderOptions.ignoreDisplacement", 1)
        setAttr("defaultArnoldRenderOptions.ignoreBump", 1)
        setAttr("defaultArnoldRenderOptions.ignoreSmoothing", 0)
        setAttr("defaultArnoldRenderOptions.ignoreMotion", 1)
        setAttr("defaultArnoldRenderOptions.ignoreDof", 1)
        setAttr("defaultArnoldRenderOptions.ignoreSss", 0)
        setAttr("defaultArnoldRenderOptions.ignoreOperators", 0)
        setAttr("defaultArnoldRenderOptions.forceTranslateShadingEngines", 1)
        setAttr("defaultArnoldRenderOptions.ignoreImagers", 1)
        aov_list = ls(type="aiAOV")
        for aov in aov_list:
            aov.enabled.set(False)

    @staticmethod
    def __set_raw_colorspace():
        setAttr("defaultArnoldDriver.colorManagement", 0)

    @staticmethod
    def __set_output_params():
        setAttr("defaultRenderGlobals.imageFilePrefix", "<Scene>")
        setAttr("defaultArnoldDriver.aiTranslator", "png")
        setAttr("defaultArnoldDriver.mergeAOVs", False)
        setAttr("defaultArnoldDriver.colorManagement", 0)
        scriptJob(runOnce=True,
                  attributeChange=["defaultArnoldDriver.colorManagement",ControlNetRequestManager.__set_raw_colorspace])
        setAttr("defaultRenderGlobals.animation", False)
        setAttr("defaultRenderGlobals.periodInExt", 1)
        setAttr("defaultRenderGlobals.putFrameBeforeExt", True)

    @staticmethod
    def __set_sampling_params():
        setAttr("defaultArnoldRenderOptions.AASamples", 3)
        setAttr("defaultArnoldRenderOptions.GIDiffuseSamples", 2)
        setAttr("defaultArnoldRenderOptions.GISpecularSamples", 1)
        setAttr("defaultArnoldRenderOptions.GITransmissionSamples", 1)
        setAttr("defaultArnoldRenderOptions.GISssSamples", 1)
        setAttr("defaultArnoldRenderOptions.GIVolumeSamples", 0)
        setAttr("defaultArnoldRenderOptions.GIDiffuseDepth", 1)
        setAttr("defaultArnoldRenderOptions.GISpecularDepth", 1)
        setAttr("defaultArnoldRenderOptions.enableAdaptiveSampling", 0)

    @staticmethod
    def __hide_furs():
        standins = ls(type="aiStandIn")
        for standin in standins:
            if re.match(r"^.*fur.*$", standin.dso.get()):
                hide(standin)

    @staticmethod
    def __remove_render_layer():
        render_layers = ls(type="renderLayer")
        for render_layer in render_layers:
            print(render_layer.name(),"defaultRenderLayer")
            render_layer.renderable.set(render_layer.name() == "defaultRenderLayer")


    def __init__(self):
        self.__datas = []
        self.__created_objects = []

    def set_datas(self,datas):
        self.__datas = datas

    def delete_created_objects(self):
        for obj in self.__created_objects:
            try:
                delete(obj)
            except:
                # Nothing
                pass
        self.__created_objects.clear()

    def prepare_render(self):
        self.delete_created_objects()
        ControlNetRequestManager.__remove_render_layer()
        ControlNetRequestManager.__set_features_overrides()
        ControlNetRequestManager.__set_output_params()
        ControlNetRequestManager.__set_sampling_params()
        ControlNetRequestManager.__hide_furs()
        if self.__datas["weight_depth"] > 0:
            self.__prepare_depth_aov()
        if self.__datas["weight_normal"] > 0:
            self.__prepare_normal_aov()
        if self.__datas["weight_edges"] > 0:
            self.__prepare_edges_aov()

    def __prepare_depth_aov(self):
        depth_max_dist = self.__datas["depth_max_dist"]
        depth_type = self.__datas["depth_type"]
        if depth_type is DepthType.CloseBy:
            depth_min_dist = 0
        else:
            depth_min_dist = self.__datas["depth_min_dist"]

        sdd_depth_node = shadingNode("aiStateFloat", name="sdd_depth", asUtility=True)
        self.__created_objects.append(sdd_depth_node)
        sdd_depth_node.variable.set(5)
        sdd_remap_node = shadingNode("remapValue", name="sdd_remap", asUtility=True)
        self.__created_objects.append(sdd_remap_node)
        sdd_depth_node.outValue >> sdd_remap_node.inputValue
        sdd_remap_node.inputMin.set(depth_min_dist)
        sdd_remap_node.inputMax.set(depth_max_dist)
        sdd_inverse_node = shadingNode("floatMath", name="sdd_inverse", asUtility=True)
        self.__created_objects.append(sdd_inverse_node)
        sdd_inverse_node.floatA.set(1)
        sdd_remap_node.outValue >> sdd_inverse_node.floatB
        sdd_inverse_node.operation.set(1)
        aov_node_name = "aiAOV_"+_DEPTH_AOV_NAME
        if objExists(aov_node_name):
            delete(aov_node_name)
        aovs.AOVInterface().addAOV(_DEPTH_AOV_NAME)
        node_aov = PyNode(aov_node_name)
        self.__created_objects.append(node_aov)
        sdd_inverse_node.outFloat >> node_aov.defaultValue

        if depth_type is DepthType.CloseBy:
            interp = [(0.5,0.0250),(0.8,0.07),(0.9,0.15)]
        elif depth_type is DepthType.Away:
            interp = [(0.93,0.75),(0.22,0.88),(0.5,0.94)]
        else:
            interp = []
        for index, interp_data in enumerate(interp):
            interp_index = index+1
            sdd_remap_node.value[interp_index].value_FloatValue.set(interp_data[0])
            sdd_remap_node.value[interp_index].value_Position.set(interp_data[1])
            sdd_remap_node.value[interp_index].value_Interp.set(3)

    def __prepare_normal_aov(self):
        sdn_normal_node = shadingNode("aiStateVector", name="sdn_normal", asUtility=True)
        self.__created_objects.append(sdn_normal_node)
        sdn_normal_node.variable.set(6)
        sdn_space_trsf_node = shadingNode("aiSpaceTransform", name="sdn_space_trsf", asUtility=True)
        self.__created_objects.append(sdn_space_trsf_node)
        sdn_normal_node.outValue >> sdn_space_trsf_node.input
        setAttr(sdn_space_trsf_node+".type",2)
        setAttr(sdn_space_trsf_node+".from",0)
        setAttr(sdn_space_trsf_node+".to",2)
        sdn_to_rgb_node = shadingNode("aiVectorToRgb", name="sdn_to_rgb", asUtility=True)
        self.__created_objects.append(sdn_to_rgb_node)
        sdn_space_trsf_node.outValue >> sdn_to_rgb_node.input
        sdn_to_rgb_node.mode.set(2)
        sdn_inverse_node = shadingNode("floatMath", name="sdn_inverse", asUtility=True)
        self.__created_objects.append(sdn_inverse_node)
        sdn_inverse_node.floatA.set(1)
        sdn_to_rgb_node.outColor.outColorR >> sdn_inverse_node.floatB
        sdn_inverse_node.operation.set(1)
        sdn_space_trsf_2_node = shadingNode("aiSpaceTransform", name="sdn_space_trsf_2", asUtility=True)
        self.__created_objects.append(sdn_space_trsf_2_node)
        sdn_inverse_node.outFloat >> sdn_space_trsf_2_node.input.inputX
        sdn_to_rgb_node.outColor.outColorG >> sdn_space_trsf_2_node.input.inputY
        sdn_to_rgb_node.outColor.outColorB >> sdn_space_trsf_2_node.input.inputZ
        setAttr(sdn_space_trsf_2_node+".type",0)
        setAttr(sdn_space_trsf_2_node+".from",0)
        setAttr(sdn_space_trsf_2_node+".to",0)
        aov_node_name = "aiAOV_"+_NORMAL_AOV_NAME
        if objExists(aov_node_name):
            delete(aov_node_name)
        aovs.AOVInterface().addAOV(_NORMAL_AOV_NAME)
        node_aov = PyNode(aov_node_name)
        self.__created_objects.append(node_aov)
        sdn_space_trsf_2_node.outValue >> node_aov.defaultValue

    def __prepare_edges_aov(self):
        sde_toon_shader_node = shadingNode("aiToon", name="sde_toon", asShader=True)
        self.__created_objects.append(sde_toon_shader_node)
        sde_toon_shader_node.edgeColor.set((1,1,1))
        sde_toon_shader_node.base.set(0)
        sde_toon_shader_node.aovPrefix.set(_EDGES_AOV_NAME)
        shading_engine = sets(name="sde_shading_engine", empty=True, renderable=True, noSurfaceShader=True)
        self.__created_objects.append(shading_engine)
        sde_toon_shader_node.outColor >> shading_engine.surfaceShader
        aov_node_name = "aiAOV_"+_EDGES_AOV_NAME
        if objExists(aov_node_name):
            delete(aov_node_name)
        aovs.AOVInterface().addAOV(_EDGES_AOV_NAME)
        node_aov = PyNode(aov_node_name)
        self.__created_objects.append(node_aov)

        contour_filter = createNode("aiAOVFilter", name="sde_filter")
        self.__created_objects.append(contour_filter)
        contour_filter.aiTranslator.set("contour")
        contour_filter.width.set(5)
        connectAttr(contour_filter + ".message", aov_node_name + '.outputs[0].filter', f=True)
        sde_toon_shader_node.outColor >> node_aov.defaultValue

