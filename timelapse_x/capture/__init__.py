"""
Capture package for Timelapse X addon.
Contains all capture logic for cameras and windows.
"""

import logging

logger = logging.getLogger(__name__)

# Import submodules
try:
    from . import scheduler
    from . import camera
    from . import window
    from . import shading
    from . import wireframe
except ImportError as e:
    logger.warning(f"Some capture modules not available: {e}")

# ========================================================================================
# Public API
# ========================================================================================

# Re-export commonly used functions
try:
    from .camera import capture_cameras, init_camera_schedulers, compute_min_timer_interval
    from .window import capture_window, capture_window_async
    from .scheduler import pick_due_cameras, update_camera_due
except ImportError:
    pass

# ========================================================================================
# Registration
# ========================================================================================

def register():
    """Register capture modules."""
    logger.info("Registering capture modules")
    
    try:
        scheduler.register()
    except:
        pass
    
    try:
        camera.register()
    except:
        pass
    
    try:
        window.register()
    except:
        pass
    
    try:
        shading.register()
    except:
        pass
    
    try:
        wireframe.register()
    except:
        pass


def unregister():
    """Unregister capture modules."""
    logger.info("Unregistering capture modules")
    
    try:
        wireframe.unregister()
    except:
        pass
    
    try:
        shading.unregister()
    except:
        pass
    
    try:
        window.unregister()
    except:
        pass
    
    try:
        camera.unregister()
    except:
        pass
    
    try:
        scheduler.unregister()
    except:
        pass