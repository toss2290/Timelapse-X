"""
UI Lists for Timelapse X addon.
Camera list display with override indicators.
"""

import bpy
import logging
from bpy.types import UIList

logger = logging.getLogger(__name__)


class TLX_UL_cameras(UIList):
    """
    UI List for displaying cameras in the camera list.
    
    Shows camera name with visual indicators for active overrides:
    - Interval override
    - Shading override
    - Image format override
    - Performance override
    """
    
    bl_idname = "TLX_UL_cameras"
    
    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index
    ):
        """
        Draw a single camera item in the list.
        """
        if not item:
            return
        
        camera = item.camera
        
        # Main row
        row = layout.row(align=True)
        
        # Camera icon
        if camera:
            row.label(icon='CAMERA_DATA')
        else:
            row.label(icon='ERROR')
        
        # Override indicators
        # Interval override
        row.prop(
            item,
            'use_interval_override',
            text='',
            emboss=False,
            icon='TIME' if item.use_interval_override else 'BLANK1'
        )
        
        # Shading override
        row.prop(
            item,
            'use_shading_override',
            text='',
            emboss=False,
            icon='SHADING_RENDERED' if item.use_shading_override else 'BLANK1'
        )
        
        # Image format override
        row.prop(
            item,
            'use_image_override',
            text='',
            emboss=False,
            icon='IMAGE_DATA' if item.use_image_override else 'BLANK1'
        )
        
        # Performance override
        row.prop(
            item,
            'perf_override',
            text='',
            emboss=False,
            icon='PREFERENCES' if item.perf_override else 'BLANK1'
        )
        
        # Camera name
        if camera:
            row.label(text=camera.name)
        else:
            row.label(text='<None>', icon='ERROR')


class TLX_UL_cameras_compact(UIList):
    """
    Compact version of camera list with minimal UI.
    Shows only camera name and icon.
    """
    
    bl_idname = "TLX_UL_cameras_compact"
    
    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index
    ):
        """Draw compact camera item."""
        if not item:
            return
        
        camera = item.camera
        
        row = layout.row(align=True)
        
        # Icon and name only
        if camera:
            row.label(text=camera.name, icon='CAMERA_DATA')
        else:
            row.label(text='<None>', icon='ERROR')
        
        # Show override indicator
        has_override = (
            item.use_interval_override or
            item.use_shading_override or
            item.use_image_override or
            item.perf_override
        )
        
        if has_override:
            row.label(text='', icon='MODIFIER')


classes = (
    TLX_UL_cameras,
    TLX_UL_cameras_compact,
)


def register():
    """Register UI list classes."""
    logger.info("Registering UI lists")
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            print(f"List registered: {cls.__name__}")
        except Exception as e:
            logger.error(f"Failed to register {cls.__name__}: {e}")
            print(f"List registration failed: {cls.__name__} - {e}")


def unregister():
    """Unregister UI list classes."""
    logger.info("Unregistering UI lists")
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            logger.warning(f"Failed to unregister {cls.__name__}: {e}")