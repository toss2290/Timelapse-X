# Timelapse X - Main Init File

bl_info = {
    "name": "Timelapse X",
    "author": "Toss",
    "version": (2, 3, 1),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar (N) > Timelapse X",
    "description": "Professional timelapse capture addon with enhanced error handling",
    "category": "System",
}

import bpy
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("\n" + "="*60)
print("TIMELAPSE X: Starting import...")
print("="*60)

# Import modules directly
from . import constants
from . import state
from . import error_messages
from . import progress
from . import utils
from . import properties
from . import preferences
from . import operators
from . import capture
from . import ui
from . import clean_window

print("OK: All modules imported")
print("="*60 + "\n")


def register():
    print("\n" + "-"*60)
    print("TIMELAPSE X: Registering...")
    print("-"*60)
    
    # Register modules in order
    constants.register()
    print("REG: constants")
    
    state.register()
    print("REG: state")
    
    error_messages.register()
    print("REG: error_messages")
    
    progress.register()
    print("REG: progress")
    
    utils.register()
    print("REG: utils")
    
    preferences.register()
    print("REG: preferences")
    
    properties.register()
    print("REG: properties")
    
    operators.register()
    print("REG: operators")
    
    capture.register()
    print("REG: capture")
    
    ui.register()
    print("REG: ui")
    
    clean_window.register()
    print("REG: clean_window")
    
    # Initialize properties
    properties.register_scene_properties()
    print("REG: scene properties")
    
    clean_window.register_window_properties()
    print("REG: window properties")
    
    # Validate settings
    try:
        if bpy.context.scene:
            scene = bpy.context.scene
            prefs = utils.get_addon_preferences()
            
            if hasattr(scene, 'tlx_capture_interval'):
                interval = float(getattr(scene, 'tlx_capture_interval', constants.DEFAULT_INTERVAL))
                if interval <= constants.MIN_INTERVAL:
                    scene.tlx_capture_interval = constants.DEFAULT_INTERVAL
            
            if prefs:
                default_interval = float(getattr(prefs, 'default_interval', constants.DEFAULT_INTERVAL))
                if default_interval <= constants.MIN_INTERVAL:
                    prefs.default_interval = constants.DEFAULT_INTERVAL
    except Exception as e:
        logger.warning(f"Settings validation warning: {e}")
    
    print("-"*60)
    print("TIMELAPSE X: Registration complete!")
    print("-"*60 + "\n")
    
    # Verify panel
    if 'TLX_PT_panel' in dir(bpy.types):
        print("SUCCESS: Panel registered!")
        print("Press N in 3D Viewport > Find 'Timelapse X' tab")
    else:
        print("WARNING: Panel not registered")
    
    logger.info("Timelapse X registered successfully")


def unregister():
    print("\n" + "="*60)
    print("TIMELAPSE X: Unregistering...")
    print("="*60)
    
    # Cleanup
    try:
        if state.TLX_State.timer and bpy.context:
            wm = bpy.context.window_manager
            if wm:
                try:
                    wm.event_timer_remove(state.TLX_State.timer)
                except:
                    pass
                state.TLX_State.timer = None
        
        if state.TLX_State.handler_installed:
            try:
                bpy.app.handlers.depsgraph_update_post.remove(state.mark_scene_dirty)
            except ValueError:
                pass
            state.TLX_State.handler_installed = False
    except:
        pass
    
    # Unregister modules in reverse order
    clean_window.unregister_window_properties()
    clean_window.unregister()
    
    ui.unregister()
    capture.unregister()
    operators.unregister()
    
    properties.unregister_scene_properties()
    properties.unregister()
    
    preferences.unregister()
    utils.unregister()
    progress.unregister()
    error_messages.unregister()
    state.unregister()
    constants.unregister()
    
    print("TIMELAPSE X: Unregistered")
    logger.info("Timelapse X unregistered")


if __name__ == "__main__":
    try:
        unregister()
    except:
        pass
    register()