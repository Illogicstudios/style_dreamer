import sys
import importlib

if __name__ == '__main__':
    # TODO specify the right path
    install_dir = 'PATH/TO/style_dreamer'
    if not sys.path.__contains__(install_dir):
        sys.path.append(install_dir)

    modules = [
        "StyleDreamer"
        "SDSlider",
        "ControlNetRequestManager",
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
    style_dreamer = StyleDreamer()
    style_dreamer.show()
