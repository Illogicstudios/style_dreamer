import os
import re
import base64
import requests
import json
import tempfile
import time
import datetime
import threading

from functools import partial

import pymel.core as pm
from utils import *
import mtoa.aovs as aovs

from StyleDreamer import *
from StyleVisualizer import *


class ControlNetManager():

    @staticmethod
    def __set_features_overrides():
        pm.setAttr("defaultArnoldRenderOptions.ignoreTextures", 0)
        pm.setAttr("defaultArnoldRenderOptions.ignoreShaders", 0)
        pm.setAttr("defaultArnoldRenderOptions.ignoreAtmosphere", 1)
        pm.setAttr("defaultArnoldRenderOptions.ignoreLights", 0)
        pm.setAttr("defaultArnoldRenderOptions.ignoreShadows", 0)
        pm.setAttr("defaultArnoldRenderOptions.ignoreSubdivision", 0)
        pm.setAttr("defaultArnoldRenderOptions.ignoreDisplacement", 1)
        pm.setAttr("defaultArnoldRenderOptions.ignoreBump", 1)
        pm.setAttr("defaultArnoldRenderOptions.ignoreSmoothing", 0)
        pm.setAttr("defaultArnoldRenderOptions.ignoreMotion", 1)
        pm.setAttr("defaultArnoldRenderOptions.ignoreDof", 1)
        pm.setAttr("defaultArnoldRenderOptions.ignoreSss", 0)
        pm.setAttr("defaultArnoldRenderOptions.ignoreOperators", 0)
        pm.setAttr("defaultArnoldRenderOptions.forceTranslateShadingEngines", 1)
        pm.setAttr("defaultArnoldRenderOptions.ignoreImagers", 1)
        pm.setAttr("defaultArnoldRenderOptions.aovMode", 1)
        aov_list = pm.ls(type="aiAOV")
        for aov in aov_list:
            aov.enabled.set(False)

    @staticmethod
    def __set_raw_colorspace():
        pm.setAttr("defaultArnoldDriver.colorManagement", 0)

    @staticmethod
    def __set_sampling_params():
        pm.setAttr("defaultArnoldRenderOptions.AASamples", 3)
        pm.setAttr("defaultArnoldRenderOptions.GIDiffuseSamples", 2)
        pm.setAttr("defaultArnoldRenderOptions.GISpecularSamples", 1)
        pm.setAttr("defaultArnoldRenderOptions.GITransmissionSamples", 1)
        pm.setAttr("defaultArnoldRenderOptions.GISssSamples", 1)
        pm.setAttr("defaultArnoldRenderOptions.GIVolumeSamples", 0)
        pm.setAttr("defaultArnoldRenderOptions.GIDiffuseDepth", 1)
        pm.setAttr("defaultArnoldRenderOptions.GISpecularDepth", 1)
        pm.setAttr("defaultArnoldRenderOptions.enableAdaptiveSampling", 0)

    @staticmethod
    def __hide_furs():
        standins = pm.ls(type="aiStandIn")
        for standin in standins:
            if re.match(r"^.*fur.*$", standin.dso.get()):
                pm.hide(standin)

    @staticmethod
    def __remove_render_layer():
        render_layers = pm.ls(type="renderLayer")
        for render_layer in render_layers:
            render_layer.renderable.set(render_layer.name() == "defaultRenderLayer")

    # Inspired from https://github.com/coolzilj/Blender-ControlNet
    @staticmethod
    def __request_controlnet_api(params, request_url, output_dir):
        # create headers
        headers = {
            "User-Agent": "",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
        }

        # send API request
        try:
            response = requests.post(request_url, json=params, headers=headers, timeout=10000)
        except requests.exceptions.ConnectionError:
            return None, -1, "The server couldn't be found."
        except requests.exceptions.MissingSchema:
            return None, -1, "The url for the server is invalid."
        except requests.exceptions.ReadTimeout:
            return None, -1, "The server timed out."

        # handle the response
        if response.status_code == 200:
            return ControlNetManager.handle_api_success(response, output_dir)
        else:
            return ControlNetManager.handle_api_error(response)

    @staticmethod
    def handle_api_error(response):
        if response.status_code == 404:
            try:
                response_obj = response.json()
                if response_obj.get("detail") and response_obj["detail"] == "Not Found":
                    msg = "It looks like the server is running, but it's not in API mode."
                elif (
                        response_obj.get("detail")
                        and response_obj["detail"] == "Sampler not found"
                ):
                    msg = "The sampler you selected is not available."
                else:
                    msg = f"An error occurred in the server. Full server response: {json.dumps(response_obj)}"
            except:
                msg = "The server couldn't be found."
        elif response.status_code == 504:
            msg = "Gateway Timeout"
        else:
            msg = "An error occurred in the server : \n\n" + str(response.content)
        return None, -1, msg

    @staticmethod
    def handle_api_success(response, output_dir):
        try:
            response_obj = response.json()
            infos = json.loads(response_obj["info"])
            seed = infos["seed"]
            nb_gen_img = response_obj["parameters"]["batch_size"] * response_obj["parameters"]["n_iter"]
            base64_imgs = response_obj["images"]
        except:
            return None, -1, "Server response content : \n\n" + str(response.content)

        # decode base64 image
        try:
            imgs_binary = []
            for base64_img in base64_imgs:
                imgs_binary.append(base64.b64decode(base64_img.replace("data:image/png;base64,", "")))
        except:
            return None, -1, "Couldn't decode base64 image."

        # save the image to the temp file
        try:
            output_file_prefix = time.strftime(output_dir + "/output_%d%m%Y_%H%M%S")
            output_files = []
            for i in range(nb_gen_img):
                if nb_gen_img > 1:
                    output_filepath = output_file_prefix + "_" + str(i) + ".png"
                else:
                    output_filepath = output_file_prefix + ".png"
                with open(output_filepath, "wb") as file:
                    file.write(imgs_binary[i])
                output_files.append(output_filepath)
        except:
            return None, -1, "Couldn't write to output file."

        # return the temp file
        return output_files, seed, "Success"

    @staticmethod
    def __request_eta_api(request_url):
        # create headers
        headers = {"User-Agent": "", "Accept": "*/*", "Accept-Encoding": "gzip, deflate, br"}

        # send API request
        try:
            response = requests.get(request_url, headers=headers, timeout=10)
        except requests.exceptions.ConnectionError:
            return -1

        # handle the response
        if response.status_code == 200:
            return response.json()
        else:
            return response.status_code

    def __init__(self, url_server, callback_dream):
        self.__datas = []
        self.__url_server = url_server
        self.__callback_dream = callback_dream
        self.__output_dir = os.path.expanduser("~") + "/style_dreamer"
        self.__render_dir = os.path.join(self.__output_dir, "renders")
        self.__requesting_dream = False
        self.__launch_timestamp = None
        self.__job_timestamp = None
        self.__created_objects = []
        self.__controlnet_img = {}
        self.__outputs = []
        self.__style_visualizer = StyleVisualizer(self)
        self.__request_dream_callback = CallbackThread(self.__on_request_dream_finished)
        self.__request_eta_callback = CallbackThread(self.__on_request_eta_finished)
        self.__request_eta_run = CallbackThread(self.__run_observer_eta)

    def __set_output_params(self):
        pm.setAttr("defaultRenderGlobals.imageFilePrefix", os.path.join(self.__render_dir, "<RenderPass>"))
        pm.setAttr("defaultArnoldDriver.mergeAOVs", False)
        pm.setAttr("defaultResolution.width", self.__datas["width"])
        pm.setAttr("defaultResolution.height", self.__datas["height"])
        pm.setAttr("defaultArnoldDriver.ai_translator", "png")
        ControlNetManager.__set_raw_colorspace()
        # Have to set a scriptjob to reset the colorspace because the ai_translator set it to a bad one asynchronous
        pm.scriptJob(runOnce=True,
                     attributeChange=["defaultArnoldDriver.colorManagement",
                                      ControlNetManager.__set_raw_colorspace])
        pm.setAttr("defaultRenderGlobals.animation", False)
        pm.setAttr("defaultRenderGlobals.periodInExt", 1)
        pm.setAttr("defaultRenderGlobals.putFrameBeforeExt", True)

    def is_requesting_dream(self):
        return self.__requesting_dream

    def __delete_created_objects(self):
        for obj in self.__created_objects:
            try:
                pm.delete(obj)
            except:
                # Nothing
                pass
        self.__created_objects.clear()

    def __create_depth_aov(self):
        depth_max_dist = self.__datas["depth_max_dist"]
        depth_details = self.__datas["depth_type"]
        depth_min_dist = self.__datas["depth_min_dist"]

        sdd_depth_node = pm.shadingNode("aiStateFloat", name="sdd_depth", asUtility=True)
        self.__created_objects.append(sdd_depth_node)
        sdd_depth_node.variable.set(5)
        sdd_remap_node = pm.shadingNode("remapValue", name="sdd_remap", asUtility=True)
        self.__created_objects.append(sdd_remap_node)
        sdd_depth_node.outValue >> sdd_remap_node.inputValue
        sdd_remap_node.inputMin.set(depth_min_dist)
        sdd_remap_node.inputMax.set(depth_max_dist)
        sdd_inverse_node = pm.shadingNode("floatMath", name="sdd_inverse", asUtility=True)
        self.__created_objects.append(sdd_inverse_node)
        sdd_inverse_node.floatA.set(1)
        sdd_remap_node.outValue >> sdd_inverse_node.floatB
        sdd_inverse_node.operation.set(1)
        aov_node_name = "aiAOV_" + DEPTH_NAME
        if pm.objExists(aov_node_name):
            pm.delete(aov_node_name)
        aovs.AOVInterface().addAOV(DEPTH_NAME)
        node_aov = pm.PyNode(aov_node_name)
        self.__created_objects.append(node_aov)
        sdd_inverse_node.outFloat >> node_aov.defaultValue
        depth_details.set_interp_on(sdd_remap_node)

    def __create_normal_aov(self):
        sdn_normal_node = pm.shadingNode("aiStateVector", name="sdn_normal", asUtility=True)
        self.__created_objects.append(sdn_normal_node)
        sdn_normal_node.variable.set(6)
        sdn_space_trsf_node = pm.shadingNode("aiSpaceTransform", name="sdn_space_trsf", asUtility=True)
        self.__created_objects.append(sdn_space_trsf_node)
        sdn_normal_node.outValue >> sdn_space_trsf_node.input
        pm.setAttr(sdn_space_trsf_node + ".type", 2)
        pm.setAttr(sdn_space_trsf_node + ".from", 0)
        pm.setAttr(sdn_space_trsf_node + ".to", 2)
        sdn_to_rgb_node = pm.shadingNode("aiVectorToRgb", name="sdn_to_rgb", asUtility=True)
        self.__created_objects.append(sdn_to_rgb_node)
        sdn_space_trsf_node.outValue >> sdn_to_rgb_node.input
        sdn_to_rgb_node.mode.set(2)
        sdn_inverse_node = pm.shadingNode("floatMath", name="sdn_inverse", asUtility=True)
        self.__created_objects.append(sdn_inverse_node)
        sdn_inverse_node.floatA.set(1)
        sdn_to_rgb_node.outColor.outColorR >> sdn_inverse_node.floatB
        sdn_inverse_node.operation.set(1)
        sdn_space_trsf_2_node = pm.shadingNode("aiSpaceTransform", name="sdn_space_trsf_2", asUtility=True)
        self.__created_objects.append(sdn_space_trsf_2_node)
        sdn_inverse_node.outFloat >> sdn_space_trsf_2_node.input.inputX
        sdn_to_rgb_node.outColor.outColorG >> sdn_space_trsf_2_node.input.inputY
        sdn_to_rgb_node.outColor.outColorB >> sdn_space_trsf_2_node.input.inputZ
        pm.setAttr(sdn_space_trsf_2_node + ".type", 0)
        pm.setAttr(sdn_space_trsf_2_node + ".from", 0)
        pm.setAttr(sdn_space_trsf_2_node + ".to", 0)
        aov_node_name = "aiAOV_" + NORMAL_NAME
        if pm.objExists(aov_node_name):
            pm.delete(aov_node_name)
        aovs.AOVInterface().addAOV(NORMAL_NAME)
        node_aov = pm.PyNode(aov_node_name)
        self.__created_objects.append(node_aov)
        sdn_space_trsf_2_node.outValue >> node_aov.defaultValue

    def __create_edges_aov(self):
        sde_toon_shader_node = pm.shadingNode("aiToon", name="sde_toon", asShader=True)
        self.__created_objects.append(sde_toon_shader_node)
        sde_toon_shader_node.edgeColor.set((1, 1, 1))
        sde_toon_shader_node.base.set(0)
        sde_toon_shader_node.angleThreshold.set(20)
        sde_toon_shader_node.normalType.set(2)
        sde_toon_shader_node.aovPrefix.set(EDGES_NAME)
        shading_engine = pm.sets(name="sde_shading_engine", empty=True, renderable=True, noSurfaceShader=True)
        self.__created_objects.append(shading_engine)
        sde_toon_shader_node.outColor >> shading_engine.surfaceShader
        aov_node_name = "aiAOV_" + EDGES_NAME
        if pm.objExists(aov_node_name):
            pm.delete(aov_node_name)
        aovs.AOVInterface().addAOV(EDGES_NAME)
        node_aov = pm.PyNode(aov_node_name)
        self.__created_objects.append(node_aov)

        contour_filter = pm.createNode("aiAOVFilter", name="sde_filter")
        self.__created_objects.append(contour_filter)
        contour_filter.aiTranslator.set("contour")
        contour_filter.width.set(2)
        pm.connectAttr(contour_filter + ".message", aov_node_name + '.outputs[0].filter', f=True)
        sde_toon_shader_node.outColor >> node_aov.defaultValue

    def __params_txt2img(self):
        return {
            "enable_hr": False,
            "firstphase_width": 0,
            "firstphase_height": 0,
        }

    def __params_img2img(self):
        return {
            "denoising_strength": self.__datas["denoising_strength"],
            "init_images": [
                self.__controlnet_img[BEAUTY_NAME][1]
            ],
            "resize_mode": 0,
        }

    def __generate_request_url(self):
        if self.__datas["denoising_strength"] < 1.0:
            return self.__url_server + "/sdapi/v1/img2img"
        else:
            return self.__url_server + "/sdapi/v1/txt2img"

    def __generate_params(self):
        # COMMON PARAMETERS
        params = {
            "prompt": self.__datas["prompt"],
            "styles": [],
            "seed": self.__datas["seed"],
            "subseed": -1,
            "subseed_strength": 0,
            "seed_resize_from_h": -1,
            "seed_resize_from_w": -1,
            "sampler_name": "Euler",
            "batch_size": self.__datas["batch_size"],
            "n_iter": self.__datas["batch_count"],
            "steps": self.__datas["sampling_steps"],
            "cfg_scale": self.__datas["cfg_scale"],
            "width": self.__datas["width"],
            "height": self.__datas["height"],
            "restore_faces": False,
            "tiling": False,
            "do_not_save_samples": False,
            "do_not_save_grid": False,
            "negative_prompt": self.__datas["negative_prompt"],
            "eta": 0,
            "s_churn": 0,
            "s_tmax": 0,
            "s_tmin": 0,
            "s_noise": 1,
            "override_settings": {},
            "override_settings_restore_afterwards": True,
            "script_args": [],
            "sampler_index": "DDIM",
            "script_name": "",
            "send_images": True,
            "save_images": False,
            "include_init_images": False,
            "alwayson_scripts": {"controlnet": {"args": []}},
        }

        # SPECIAL PARAMETERS
        if self.__datas["denoising_strength"] < 1.0:
            params.update(self.__params_img2img())
        else:
            params.update(self.__params_txt2img())

        # CONTROLNET PARAMETERS

        if self.__datas["weight_depth"] > 0:
            params["alwayson_scripts"]["controlnet"]["args"].append(
                {
                    "input_image": self.__controlnet_img[DEPTH_NAME][1],
                    "mask": "",
                    "module": "none",
                    "model": "control_v11f1p_sd15_depth",
                    "weight": self.__datas["weight_depth"],
                    "resize_mode": 0,
                    "lowvram": False,
                    "processor_res": 64,
                    "threshold_a": 64,
                    "threshold_b": 64,
                    "guidance": 1,
                    "guidance_start": 0,
                    "guidance_end": 1,
                    "guessmode": False,
                    "rgbbgr_mode": False
                })

        if self.__datas["weight_normal"] > 0:
            params["alwayson_scripts"]["controlnet"]["args"].append(
                {
                    "input_image": self.__controlnet_img[NORMAL_NAME][1],
                    "mask": "",
                    "module": "none",
                    "model": "control_v11p_sd15_normalbae",
                    "weight": self.__datas["weight_normal"],
                    "resize_mode": 0,
                    "lowvram": False,
                    "processor_res": 64,
                    "threshold_a": 64,
                    "threshold_b": 64,
                    "guidance": 1,
                    "guidance_start": 0,
                    "guidance_end": 1,
                    "guessmode": False,
                    "rgbbgr_mode": True
                })

        if self.__datas["weight_edges"] > 0:
            params["alwayson_scripts"]["controlnet"]["args"].append(
                {
                    "input_image": self.__controlnet_img[EDGES_NAME][1],
                    "mask": "",
                    "module": "none",
                    "model": "control_v11p_sd15_canny",
                    "weight": self.__datas["weight_edges"],
                    "resize_mode": 0,
                    "lowvram": False,
                    "processor_res": 64,
                    "threshold_a": 64,
                    "threshold_b": 64,
                    "guidance": 1,
                    "guidance_start": 0,
                    "guidance_end": 1,
                    "guessmode": False,
                    "rgbbgr_mode": False
                })
        return params

    def set_datas(self, datas):
        self.__datas = datas

    def prepare_cn_render(self):
        ControlNetManager.__remove_render_layer()
        ControlNetManager.__set_features_overrides()
        self.__set_output_params()
        ControlNetManager.__set_sampling_params()
        ControlNetManager.__hide_furs()
        self.__create_depth_aov()
        self.__create_normal_aov()
        self.__create_edges_aov()

    def __retrieve_render(self, render_name, render_filename):
        path = os.path.join(self.__render_dir, render_filename)
        if os.path.exists(path):
            with open(path, "rb") as file:
                self.__controlnet_img[render_name] = (path, base64.b64encode(file.read()).decode())

    def on_close(self):
        self.__style_visualizer.close()
        self.__style_visualizer.deleteLater()

    def retrieve_renders(self):
        self.__controlnet_img.clear()
        self.__retrieve_render(BEAUTY_NAME, "beauty_1.png")
        self.__retrieve_render(DEPTH_NAME, DEPTH_NAME + ".png")
        self.__retrieve_render(NORMAL_NAME, NORMAL_NAME + ".png")
        self.__retrieve_render(EDGES_NAME, EDGES_NAME + ".png")

    def cn_render(self):
        pm.mel.eval("arnoldRender -seq 1")
        self.retrieve_renders()
        self.__delete_created_objects()

    def display_render(self, reinit_output_files=True, show = True):
        used_input_filepaths = []
        input_files_and_names = []
        if BEAUTY_NAME in self.__controlnet_img:
            beauty_file = self.__controlnet_img[BEAUTY_NAME][0]
            input_files_and_names.append(("Beauty", beauty_file))
            if self.__datas["denoising_strength"] < 1:
                used_input_filepaths.append(beauty_file)
        if DEPTH_NAME in self.__controlnet_img:
            depth_file = self.__controlnet_img[DEPTH_NAME][0]
            input_files_and_names.append(("Depth Map", depth_file))
            if self.__datas["weight_depth"] > 0:
                used_input_filepaths.append(depth_file)
        if NORMAL_NAME in self.__controlnet_img:
            normal_file = self.__controlnet_img[NORMAL_NAME][0]
            input_files_and_names.append(("Normal Map", normal_file))
            if self.__datas["weight_normal"] > 0:
                used_input_filepaths.append(normal_file)
        if EDGES_NAME in self.__controlnet_img:
            edges_file = self.__controlnet_img[EDGES_NAME][0]
            input_files_and_names.append(("Edge Map", edges_file))
            if self.__datas["weight_edges"] > 0:
                used_input_filepaths.append(edges_file)

        self.__style_visualizer.set_input_files(input_files_and_names)
        self.__style_visualizer.set_input_used_files(used_input_filepaths)
        if reinit_output_files:
            self.__style_visualizer.set_output_files([])
        self.__style_visualizer.refresh_input_files()
        self.__style_visualizer.refresh_output_files()
        if not self.__style_visualizer.isVisible() and show:
            self.__style_visualizer.show()
        self.__style_visualizer.set_focus_input()

    def __on_request_dream_finished(self, output_filepaths, seed, error_msg):
        self.__requesting_dream = False
        self.__job_timestamp = None
        if output_filepaths is None:
            self.__style_visualizer.set_eta(0)
            msg = QMessageBox()
            msg.setWindowTitle("Error while requesting server")
            msg.setIcon(QMessageBox.Warning)
            msg.setText(error_msg)
            msg.exec_()
        else:
            self.__style_visualizer.set_output_files(output_filepaths)
            self.__style_visualizer.set_eta(100)
            self.__style_visualizer.refresh_input_files()
            self.__style_visualizer.refresh_output_files()
            if not self.__style_visualizer.isVisible():
                self.__style_visualizer.show()
            self.__style_visualizer.set_focus_output()
        self.__style_visualizer.refresh_progress_bar()
        self.__callback_dream(seed)

    def __on_request_eta_finished(self, response_dict):
        renew_eta_request = True
        if type(response_dict) is int:
            if not self.__requesting_dream:
                renew_eta_request = False
        else:
            job_str_timestamp = response_dict["state"]["job_timestamp"]
            if job_str_timestamp != "0":
                job_timestamp = int(time.mktime(datetime.datetime.strptime(job_str_timestamp, "%Y%m%d%H%M%S").timetuple()))
                # Check TimeStamp to take the eta from the correct job
                if self.__launch_timestamp is not None and job_timestamp >= self.__launch_timestamp:
                    self.__job_timestamp = job_timestamp
                    self.__launch_timestamp = None
                if self.__job_timestamp == job_timestamp:
                    eta = response_dict["progress"] * 100
                    if self.__requesting_dream and eta >= self.__style_visualizer.get_eta():
                        self.__style_visualizer.set_eta(99 if eta == 100 else eta)
                        self.__style_visualizer.refresh_progress_bar()
                    else: renew_eta_request = False
        if renew_eta_request:
            threading.Thread(target=self.__request_eta).start()

    def __run_observer_eta(self):
        self.__launch_timestamp = int(time.time())
        self.__job_timestamp = None
        self.__style_visualizer.set_eta(0)
        self.__style_visualizer.refresh_progress_bar()
        self.__request_eta()

    def request_controlnet(self):
        self.__requesting_dream = True
        os.makedirs(self.__output_dir, exist_ok=True)
        params = self.__generate_params()
        request_url = self.__generate_request_url()
        self.__request_eta_run.run_callback()
        output_filepaths, seed, error_msg = ControlNetManager.__request_controlnet_api(params, request_url, self.__output_dir)
        self.__request_dream_callback.run_callback(output_filepaths, seed, error_msg)

    def __request_eta(self):
        request_url = self.__url_server + "/sdapi/v1/progress"
        response_dict = ControlNetManager.__request_eta_api(request_url)
        self.__request_eta_callback.run_callback(response_dict)


# Request executed on a distinct thread
class CallbackThread(QThread):
    __signal = Signal()

    def __init__(self, callback):
        super().__init__(None)
        self.__args = None
        self.__callback_fct = callback
        self.__signal.connect(self.__callback)

    def run_callback(self, *args):
        self.__args = args
        self.__signal.emit()

    def __callback(self):
        self.__callback_fct(*self.__args)
