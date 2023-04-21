import sys
import importlib

if __name__ == '__main__':
    # TODO specify the right path
    install_dir = 'PATH/TO/style_dreamer'
    if not sys.path.__contains__(install_dir):
        sys.path.append(install_dir)

    # ##################################################################################################################

    __SERVER_HOST = "http://localhost:7860/"

    # ##################################################################################################################

    modules = [
        "StyleDreamer",
        "StyleVisualizer",
        "SDSlider",
        "ControlNetManager",
        "DepthDetail",
    ]

    from utils import *
    unload_packages(silent=True, packages=modules)

    for module in modules:
        importlib.import_module(module)

    from StyleDreamer import *

    try:
        style_dreamer.close()
    except:
        pass
    style_dreamer = StyleDreamer(__SERVER_HOST)
    style_dreamer.show()
