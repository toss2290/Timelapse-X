"""
Clean Window package for Timelapse X addon.
Tools for creating clean windows and managing wireframe display.
"""

import logging

logger = logging.getLogger(__name__)

# Import clean window modules
try:
    from . import properties
    from . import operators
except ImportError as e:
    logger.warning(f"Some clean window modules not available: {e}")

# ========================================================================================
# Public API
# ========================================================================================

def register_window_properties():
    """
    Register window manager properties.
    
    Must be called after properties module is registered.
    """
    try:
        properties.register_window_properties()
    except Exception as e:
        logger.error(f"Failed to register window properties: {e}")


def unregister_window_properties():
    """
    Unregister window manager properties.
    
    Must be called before properties module is unregistered.
    """
    try:
        properties.unregister_window_properties()
    except Exception as e:
        logger.warning(f"Failed to unregister window properties: {e}")


# ========================================================================================
# Registration
# ========================================================================================

def register():
    """Register clean window modules."""
    logger.info("Registering clean window modules")
    
    try:
        properties.register()
    except Exception as e:
        logger.error(f"Failed to register properties: {e}")
    
    try:
        operators.register()
    except Exception as e:
        logger.error(f"Failed to register operators: {e}")


def unregister():
    """Unregister clean window modules."""
    logger.info("Unregistering clean window modules")
    
    try:
        operators.unregister()
    except Exception as e:
        logger.warning(f"Failed to unregister operators: {e}")
    
    try:
        properties.unregister()
    except Exception as e:
        logger.warning(f"Failed to unregister properties: {e}")