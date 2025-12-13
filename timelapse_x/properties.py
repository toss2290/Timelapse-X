"""
Blender property definitions for Timelapse X addon.
"""

import bpy
import logging
from bpy.types import PropertyGroup
from bpy.props import (
    BoolProperty, EnumProperty, IntProperty, FloatProperty, PointerProperty
)

logger = logging.getLogger(__name__)

# Import constants (when in actual addon)
# from . import constants

# Inline constants for this consolidated file
MIN_INTERVAL = 0.2

SHADING_TYPES = [
    ('SOLID', 'Solid', ''),
    ('MATERIAL', 'Material', ''),
    ('RENDERED', 'Rendered', ''),
    ('WIREFRAME', 'Wireframe', ''),
]

IMAGE_FORMATS = [
    ('PNG', 'PNG (lossless)', ''),
    ('JPEG', 'JPEG (small)', ''),
]

class TLX_CameraItem(PropertyGroup):
    camera: PointerProperty(
        name='Camera',
        type=bpy.types.Object,
        description="Camera object to render from"
    )
    
    use_interval_override: BoolProperty(
        name="Override Interval",
        default=False
    )
    
    interval_override: FloatProperty(
        name="Interval (s)",
        min=MIN_INTERVAL,
        max=3600.0,
        default=2.0
    )
    
    use_shading_override: BoolProperty(
        name="Override Shading",
        default=False
    )
    
    shading_type: EnumProperty(
        name="Shading",
        items=SHADING_TYPES,
        default='SOLID'
    )
    
    xray: BoolProperty(
        name="X-Ray",
        default=False
    )
    
    disable_shadows: BoolProperty(
        name="Disable Shadows",
        default=True
    )
    
    use_image_override: BoolProperty(
        name="Override Image Format",
        default=False
    )
    
    image_format: EnumProperty(
        name="Image Format",
        items=IMAGE_FORMATS,
        default='PNG'
    )
    
    png_rgba: BoolProperty(
        name="PNG RGBA (alpha)",
        default=False
    )
    
    jpeg_quality: IntProperty(
        name="JPEG Quality",
        min=1,
        max=100,
        default=90
    )
    
    perf_override: BoolProperty(
        name="Override Performance",
        default=False
    )
    
    perf_low_overhead: BoolProperty(
        name="Low-Overhead Render",
        default=True
    )
    
    perf_lock_interface: BoolProperty(
        name="Lock UI During Render",
        default=True
    )
    
    perf_png_compress: IntProperty(
        name="PNG Compression",
        min=0,
        max=15,
        default=3
    )

def register_scene_properties():
    logger.info("Registering scene properties")
    Scene = bpy.types.Scene
    
    from bpy.props import CollectionProperty
    
    Scene.tlx_cameras = CollectionProperty(
        type=TLX_CameraItem,
        name="Camera List"
    )
    
    Scene.tlx_cameras_index = IntProperty(
        name="Active Camera Index",
        default=0
    )
    
    Scene.tlx_is_recording = BoolProperty(
        name="Is Recording",
        default=False
    )
    
    Scene.tlx_capture_interval = FloatProperty(
        name='Interval (s)',
        min=MIN_INTERVAL,
        max=3600.0,
        default=2.0
    )
    
    Scene.tlx_capture_mode = EnumProperty(
        name='Capture Mode',
        items=[
            ('WINDOW', 'Blender Window', ''),
            ('CAMERA_LIST', 'Camera List', '')
        ],
        default='CAMERA_LIST'
    )
    
    Scene.tlx_ui_cam_editor_collapsed = BoolProperty(
        name="Camera Settings Collapsed",
        default=False
    )

def unregister_scene_properties():
    logger.info("Unregistering scene properties")
    Scene = bpy.types.Scene
    
    for prop in ['tlx_cameras', 'tlx_cameras_index', 'tlx_is_recording',
                 'tlx_capture_interval', 'tlx_capture_mode', 'tlx_ui_cam_editor_collapsed']:
        if hasattr(Scene, prop):
            delattr(Scene, prop)

classes = (TLX_CameraItem,)

def register():
    logger.info("Registering properties module")
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            logger.error(f"Failed to register {cls.__name__}: {e}")

def unregister():
    logger.info("Unregistering properties module")
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            logger.warning(f"Failed to unregister {cls.__name__}: {e}")