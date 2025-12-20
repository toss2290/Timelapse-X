"""
Operators package for Timelapse X addon.
Contains all operator classes for recording, camera management, and video compilation.
"""

import bpy
import logging

logger = logging.getLogger(__name__)

# Import operator modules
try:
    from . import recording
    from . import camera
    from . import video
    from . import utils_ops
except ImportError as e:
    logger.warning(f"Some operator modules not available: {e}")

# ========================================================================================
# Collect all operator classes
# ========================================================================================

def get_operator_classes():
    """Get all operator classes from submodules."""
    classes = []
    
    try:
        classes.extend(recording.classes)
    except:
        pass
    
    try:
        classes.extend(camera.classes)
    except:
        pass
    
    try:
        classes.extend(video.classes)
    except:
        pass
    
    try:
        classes.extend(utils_ops.classes)
    except:
        pass
    
    return classes


# ========================================================================================
# Registration
# ========================================================================================

def register():
    """Register all operators."""
    logger.info("Registering operators module")
    
    # Register submodules
    for module in [recording, camera, video, utils_ops]:
        try:
            module.register()
        except Exception as e:
            logger.warning(f"Failed to register {module.__name__}: {e}")


def unregister():
    """Unregister all operators."""
    logger.info("Unregistering operators module")
    
    # Unregister submodules in reverse order
    for module in reversed([recording, camera, video, utils_ops]):
        try:
            module.unregister()
        except Exception as e:
            logger.warning(f"Failed to unregister {module.__name__}: {e}")