import sys
import importlib

if __name__ == '__main__':
    # TODO specify the right path
    install_dir = 'PATH/TO/template'
    if not sys.path.__contains__(install_dir):
        sys.path.append(install_dir)

    # TODO import right modules
    modules = [
        "MayaTool"
    ]

    from utils import *
    unload_packages(silent=True, packages=modules)

    for module in modules:
        importlib.import_module(module)

    # TODO import the app
    from MayaTool import *

    # TODO rename app variable and Class
    try:
        app.close()
    except:
        pass
    app = MayaTool()
    app.show()
