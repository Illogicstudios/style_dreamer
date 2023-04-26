# Style Dreamer

> Style Dreamer is a tool to generate images with a prompt and a Maya scene as main inputs that uses Stable Diffusion with ControlNet models

## How to install

You will need some files that several Illogic tools need. You can get them via this link :
https://github.com/Illogicstudios/common

You must have the Automatic1111 Stable Diffusion Web UI installed (https://github.com/AUTOMATIC1111/stable-diffusion-webui)
with ControlNet models in the ```models\ControlNet\``` folder.

You can download the models here : https://huggingface.co/lllyasviel/ControlNet-v1-1/tree/main.
You will need the Depth model, the Normal model and the Canny model. 
(Retrieve the ```.pth``` files and the ```.yaml``` files)

You must specify the correct path of the installation folder in the ```template_main.py``` file :
```python
if __name__ == '__main__':
    # TODO specify the right path
    install_dir = 'PATH/TO/style_dreamer'
    # [...]
```

Change the server if you need it. (If you host the Automatic Web UI on the same computer than Style Dreamer then 
localhost works)
```python
__SERVER_HOST = "http://localhost:7860/"
```

---

### Generation Interface


<div align="center">
  <span>
    <img src="https://user-images.githubusercontent.com/117286626/234519228-375b8b01-5ab8-4402-a4a4-ad001e0d72b0.png" width=70%>
  </span>
  <p weight="bold">Main window of the Style Dreamer</p>
  <br/>
</div>

In the window, we can specify a lot of parameters. Let’s take them step by step :

#### Prompt parameters
<div align="center">
  <span>
    <img src="https://user-images.githubusercontent.com/117286626/234519283-e16f06b0-f575-4c8c-a774-8203f5b674c5.png" width=50%>
  </span>
  <br/>
</div>

In the **Prompt** part you can specify what the images you want to generate should show.

---
On the other hand in the **Negative Prompt** part you can specify what the images you want to generate should **not** show.

---
*Use short sentences, with few linking words (replace them by commas for example). Single words are often more effective than a long descriptive sentence.*


#### Generation parameters
<div align="center">
  <span>
    <img src="https://user-images.githubusercontent.com/117286626/234519346-80a94e97-5c89-4dda-b858-6a0ec5c4c4d9.png" width=60%>
  </span>
  <br/>
</div>

The **Image Count** parameter indicates the number of images to generate.

*Try to choose round numbers to make the generation faster.*

---
The **Sampling Steps** parameter indicates the number of times the algorithm should be calculated before rendering the generated images. This parameter has a big influence on the calculation time.

*Try to keep this parameter between 10 and 40 to have enough steps while conserving good performance.*

#### Image parameters
<div align="center">
  <span>
    <img src="https://user-images.githubusercontent.com/117286626/234519396-066eaa33-567d-4b66-b172-6ade772eb09e.png" width=60%>
  </span>
  <br/>
</div>

The **Seed** corresponds to the randomness in our generation. A seed will determine some random values. With the same seed we get images with correspondences. With the same seed and the same parameters we get exactly the same image.

The button **Previous Seed** retrieves the seed used in the previous generation.

*Take a seed equal to -1 to have a random seed.*

---
The **Width** and **Height** parameters control the image size of the renders and the image size of the generated images.

*Try to keep these values not too high as they impact a lot on rendering and generation times.*

#### Render Weight parameters
<div align="center">
  <span>
    <img src="https://user-images.githubusercontent.com/117286626/234519439-f5dd1c11-9383-4c9f-b2d7-e7aebbcba760.png" width=70%>
  </span>
  <br/>
</div>

<div align="center">
  <br/>
  <span>
    <img src="https://user-images.githubusercontent.com/117286626/234519531-05102549-f94f-44ef-9188-c5af15657ea7.png" width=30%>
  </span>
  <br/>
</div>

The **Denoising Strenght** parameter controls the amount of noise in the input image. At 1 the input image is complettely noised. At 0 the input image is the Beauty render.

*To have creative generation keep this value high.*

<div align="center">
  <span>
    <img src="https://user-images.githubusercontent.com/117286626/234519592-b4b47449-d4c3-4314-a0c3-d89065f46916.png" width=30%>
  </span>
  <br/>
</div>

The **Weight Depth Guide** parameter controls the importance that the Depth Map render should have on the generation.

*See further for more parameters.*

<div align="center">
  <span>
    <img src="https://user-images.githubusercontent.com/117286626/234519649-bfd9d70f-0d9a-4492-915d-7b6ed23d0119.png" width=30%>
  </span>
  <br/>
</div>

The Weight Normal Guide parameter controls the importance that the Normal Map render should have on the generation.

<div align="center">
  <span>
    <img src="https://user-images.githubusercontent.com/117286626/234519692-389e466a-99bf-4f66-8457-39187eea7d80.png" width=30%>
  </span>
  <br/>
</div>

The **Weight Edges Guide** parameter controls the importance that the Edges Map render should have on the generation.

*Artifacts at edges can occur when this value is too high.*

#### Depth Map parameters
<div align="center">
  <span>
    <img src="https://user-images.githubusercontent.com/117286626/234519734-231b5159-6015-4605-b4e8-134579bfbb75.png" width=80%>
  </span>
  <br/>
</div>

The **Depth Min** and **Depth Max Distances** correspond to the boundaries of the depth map.

The **Compute Depth Map Boundaries** button next to it is used to automatically detects the boundaries of the scene.

*You should try with the computed boundaries and modify them if they don’t correspond well to the scene.*

---
The **Depth Details** parameter controls where the depth map should have more details.

<div align="center">
  <span>
    <img src="https://user-images.githubusercontent.com/117286626/234519812-69f6b07e-619c-4896-8dd1-3240abc3ef3d.png" width=50%>
  </span>
  <br/>
</div>

Try with the Uniformly repartition first and take another one if it doesn’t correspond well to the scene.

#### Buttons
<div align="center">
  <span>
    <img src="https://user-images.githubusercontent.com/117286626/234519847-8a9b55d9-3354-4bdc-97de-f1f7d7b403eb.png" width=70%>
  </span>
  <br/>
</div>

The **Reinit Parameters** button restores some default settings.

---
The **Visualizer** button opens the Dream Visualizer window that will be detailed further below.

---
The **Render** button launches a render of the current scene to generate all the maps needed.

*Be careful, the rendering is executed on the PC and Maya is not available during this process*

---
The **Dream Style** button launches the request to generate the images with the selected parameters and opens the Dream Visualizer.

*During this process Maya is free and not blocked but you can’t launch another dream request*

### Visualizer Interface

<div align="center">
  <span>
    <img src="https://user-images.githubusercontent.com/117286626/234519919-c4dbff6c-9756-4c24-81f2-410e525a5b19.png" width=70%>
  </span>
  <br/>
</div>

#### Visualizer
<div align="center">
  <span>
    <img src="https://user-images.githubusercontent.com/117286626/234519976-e64c314a-fcf9-4fc7-bc48-716a3df60c3a.png" width=60%>
  </span>
  <br/>
</div>

You can visualize images in this window.

There is a loading bar to have a feedback on the status of the dream request.

Don’t worry if the request is stuck at 1% or at the end of the bar during more time. It’s because the server loads some datas before processing the request and because the generated images need to be retrieved at the end.

#### Inputs and Outputs
<div align="center">
  <span>
    <img src="https://user-images.githubusercontent.com/117286626/234520026-b0177aea-995a-41f3-82c2-3a7f4b2d0ca3.png" width=70%>
  </span>
  <br/>
</div>

You have the list of the renders in the **Input Images** section. Those colored green are those used in the request and those colored red are those not used.

Below there is the list of **Output Images**.

You can click on the images to display them in the Visualizer
