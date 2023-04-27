import importlib
from common import utils

utils.unload_packages(silent=True, package="style_dreamer")
importlib.import_module("style_dreamer")
from style_dreamer.StyleDreamer import StyleDreamer
try:
    style_dreamer.close()
except:
    pass

# ##################################################################################################################

__SERVER_HOST = "http://localhost:7860/"

# ##################################################################################################################

style_dreamer = StyleDreamer(__SERVER_HOST)
style_dreamer.show()
