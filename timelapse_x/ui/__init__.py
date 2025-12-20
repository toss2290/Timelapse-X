# UI package for Timelapse X addon

import bpy
import logging

logger = logging.getLogger(__name__)

print("UI __init__: Loading...")

# Import submodules
from . import lists
from . import panels

print("UI __init__: Submodules imported")


def register():
    print("UI __init__: Starting registration...")
    logger.info("Registering UI modules")
    
    # Register lists
    lists.register()
    print("UI __init__: Lists registered")
    
    # Register panels
    panels.register()
    print("UI __init__: Panels registered")
    
    # Verify panel
    if 'TLX_PT_panel' in dir(bpy.types):
        print("UI __init__: SUCCESS - Panel in bpy.types!")
    else:
        print("UI __init__: ERROR - Panel not in bpy.types")


def unregister():
    logger.info("Unregistering UI modules")
    
    panels.unregister()
    lists.unregister()


print("UI __init__: Module loaded")