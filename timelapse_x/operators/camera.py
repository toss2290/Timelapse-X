"""
Camera management operators for Timelapse X addon.
Handles adding/removing cameras and applying performance presets.
"""

import bpy
import logging
from bpy.types import Operator
from bpy.props import EnumProperty, BoolProperty

from .. import constants
from .. import utils

logger = logging.getLogger(__name__)

# ========================================================================================
# Add Camera Operator
# ========================================================================================

class TLX_OT_cam_add(Operator):
    """
    Add a camera to the timelapse camera list.
    
    Adds the active camera, scene camera, or creates a new camera
    if none exists.
    """
    
    bl_idname = "tlx.cam_add"
    bl_label = "Add Camera"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        """Execute add camera operation."""
        scene = context.scene
        
        # Determine which camera to add
        camera_obj = self._get_camera_to_add(context, scene)
        
        if not camera_obj:
            self.report({'ERROR'}, 'No camera available to add.')
            return {'CANCELLED'}
        
        # Add camera to list
        camera_item = scene.tlx_cameras.add()
        camera_item.camera = camera_obj
        
        # Set as active
        scene.tlx_cameras_index = len(scene.tlx_cameras) - 1
        
        logger.info(f"Added camera '{camera_obj.name}' to list")
        self.report({'INFO'}, f"Added camera: {camera_obj.name}")
        
        return {'FINISHED'}
    
    def _get_camera_to_add(self, context, scene):
        """
        Determine which camera to add.
        
        Priority:
        1. Active object (if camera)
        2. Scene camera
        3. Create new camera
        
        Returns:
            Camera object or None
        """
        # Try active object first
        active_obj = getattr(context, 'object', None)
        if active_obj and active_obj.type == 'CAMERA':
            return active_obj
        
        # Try scene camera
        if scene.camera:
            return scene.camera
        
        # Create new camera
        return self._create_new_camera(scene)
    
    def _create_new_camera(self, scene):
        """
        Create a new camera and add to scene.
        
        Args:
            scene: Blender scene object
        
        Returns:
            New camera object
        """
        try:
            # Create camera data
            camera_data = bpy.data.cameras.new("TLX_Camera")
            
            # Create camera object
            camera_obj = bpy.data.objects.new("TLX_Camera", camera_data)
            
            # Link to scene collection
            scene.collection.objects.link(camera_obj)
            
            # Set as scene camera if none exists
            if not scene.camera:
                scene.camera = camera_obj
            
            logger.info(f"Created new camera: {camera_obj.name}")
            return camera_obj
        
        except Exception as e:
            logger.error(f"Failed to create camera: {e}")
            return None


# ========================================================================================
# Remove Camera Operator
# ========================================================================================

class TLX_OT_cam_remove(Operator):
    """
    Remove selected camera from the timelapse camera list.
    
    Does not delete the camera object itself, only removes it
    from the capture list.
    """
    
    bl_idname = "tlx.cam_remove"
    bl_label = "Remove Camera"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        """Check if operator can run."""
        scene = context.scene
        return (
            len(scene.tlx_cameras) > 0 and
            0 <= scene.tlx_cameras_index < len(scene.tlx_cameras)
        )
    
    def execute(self, context):
        """Execute remove camera operation."""
        scene = context.scene
        
        # Get camera to remove
        index = scene.tlx_cameras_index
        camera_item = scene.tlx_cameras[index]
        camera_name = camera_item.camera.name if camera_item.camera else '<None>'
        
        # Remove from list
        scene.tlx_cameras.remove(index)
        
        # Update active index
        if scene.tlx_cameras_index >= len(scene.tlx_cameras):
            scene.tlx_cameras_index = max(0, len(scene.tlx_cameras) - 1)
        
        logger.info(f"Removed camera '{camera_name}' from list")
        self.report({'INFO'}, f"Removed camera: {camera_name}")
        
        return {'FINISHED'}


# ========================================================================================
# Move Camera Up/Down Operators
# ========================================================================================

class TLX_OT_cam_move_up(Operator):
    """Move selected camera up in the list."""
    
    bl_idname = "tlx.cam_move_up"
    bl_label = "Move Camera Up"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        """Check if operator can run."""
        scene = context.scene
        return (
            len(scene.tlx_cameras) > 1 and
            scene.tlx_cameras_index > 0
        )
    
    def execute(self, context):
        """Move camera up in list."""
        scene = context.scene
        index = scene.tlx_cameras_index
        
        # Move up
        scene.tlx_cameras.move(index, index - 1)
        scene.tlx_cameras_index = index - 1
        
        return {'FINISHED'}


class TLX_OT_cam_move_down(Operator):
    """Move selected camera down in the list."""
    
    bl_idname = "tlx.cam_move_down"
    bl_label = "Move Camera Down"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        """Check if operator can run."""
        scene = context.scene
        return (
            len(scene.tlx_cameras) > 1 and
            scene.tlx_cameras_index < len(scene.tlx_cameras) - 1
        )
    
    def execute(self, context):
        """Move camera down in list."""
        scene = context.scene
        index = scene.tlx_cameras_index
        
        # Move down
        scene.tlx_cameras.move(index, index + 1)
        scene.tlx_cameras_index = index + 1
        
        return {'FINISHED'}


# ========================================================================================
# Apply Speed Preset Operator
# ========================================================================================

class TLX_OT_apply_speed_preset(Operator):
    """
    Apply performance preset to global settings and optionally all cameras.
    
    Provides three presets:
    - Ultra Fast: Maximum speed, lower quality (JPEG 80, low samples)
    - Balanced: Good speed/quality balance (JPEG 90, moderate settings)
    - Quality: Best quality, slower (PNG, high samples)
    """
    
    bl_idname = 'tlx.apply_speed_preset'
    bl_label = 'Apply Speed Preset'
    bl_options = {'REGISTER', 'UNDO'}
    
    preset: EnumProperty(
        name="Preset",
        items=constants.SPEED_PRESETS,
        default='BALANCED',
        description="Performance preset to apply"
    )
    
    apply_to_all_cameras: BoolProperty(
        name="Apply to All Cameras",
        default=False,
        description="Apply performance settings to all cameras in the list"
    )
    
    def invoke(self, context, event):
        """Show confirmation dialog."""
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        """Draw operator properties."""
        layout = self.layout
        
        layout.prop(self, 'preset', expand=True)
        layout.separator()
        layout.prop(self, 'apply_to_all_cameras')
        
        # Show what will be changed
        box = layout.box()
        box.label(text="Will change:", icon='INFO')
        
        if self.preset == 'ULTRA_FAST':
            box.label(text="• Format: JPEG 80")
            box.label(text="• Interval: min 1.0s")
            box.label(text="• Cooldown: 160ms")
            box.label(text="• PNG Compression: 3")
        elif self.preset == 'BALANCED':
            box.label(text="• Format: JPEG 90")
            box.label(text="• Interval: min 1.5s")
            box.label(text="• Cooldown: 140ms")
            box.label(text="• PNG Compression: 5")
        else:  # QUALITY
            box.label(text="• Format: PNG")
            box.label(text="• Interval: min 2.0s")
            box.label(text="• Cooldown: 120ms")
            box.label(text="• PNG Compression: 9")
        
        box.label(text="• Round-robin: ON")
        box.label(text="• Lock interface: ON")
        box.label(text="• Low overhead: ON/OFF")
    
    def execute(self, context):
        """Apply speed preset."""
        prefs = utils.get_addon_preferences()
        
        if not prefs:
            self.report({'ERROR'}, 'Preferences not available')
            return {'CANCELLED'}
        
        # Apply preset to global settings
        self._apply_global_preset(prefs)
        
        # Apply to all cameras if requested
        if self.apply_to_all_cameras:
            self._apply_to_cameras(context.scene, prefs)
        
        logger.info(f"Applied speed preset: {self.preset}")
        self.report({'INFO'}, f"Applied preset: {self.preset}")
        
        return {'FINISHED'}
    
    def _apply_global_preset(self, prefs):
        """Apply preset to global preferences."""
        if self.preset == 'ULTRA_FAST':
            # Ultra Fast: JPEG 80, minimal settings
            prefs.camera_round_robin = True
            prefs.camera_max_per_tick = 1
            prefs.camera_lock_interface = True
            prefs.camera_low_overhead = True
            
            prefs.image_format = 'JPEG'
            prefs.jpeg_quality = 80
            
            prefs.perf_depsgraph_suppress_ms = 160
            prefs.default_interval = max(1.0, prefs.default_interval)
            prefs.camera_png_compress = 3
        
        elif self.preset == 'BALANCED':
            # Balanced: JPEG 90, moderate settings
            prefs.camera_round_robin = True
            prefs.camera_max_per_tick = 1
            prefs.camera_lock_interface = True
            prefs.camera_low_overhead = True
            
            prefs.image_format = 'JPEG'
            prefs.jpeg_quality = 90
            
            prefs.perf_depsgraph_suppress_ms = 140
            prefs.default_interval = max(1.5, prefs.default_interval)
            prefs.camera_png_compress = 5
        
        else:  # QUALITY
            # Quality: PNG, high quality settings
            prefs.camera_round_robin = True
            prefs.camera_max_per_tick = 2
            prefs.camera_lock_interface = False
            prefs.camera_low_overhead = False
            
            prefs.image_format = 'PNG'
            prefs.png_rgba = False
            
            prefs.perf_depsgraph_suppress_ms = 120
            prefs.default_interval = max(2.0, prefs.default_interval)
            prefs.camera_png_compress = 9
    
    def _apply_to_cameras(self, scene, prefs):
        """
        Apply performance settings to all cameras in list.
        
        Args:
            scene: Blender scene object
            prefs: Addon preferences
        """
        for camera_item in scene.tlx_cameras:
            camera_item.perf_override = True
            camera_item.perf_low_overhead = bool(prefs.camera_low_overhead)
            camera_item.perf_lock_interface = bool(prefs.camera_lock_interface)
            camera_item.perf_png_compress = int(prefs.camera_png_compress)


# ========================================================================================
# Clear All Cameras Operator
# ========================================================================================

class TLX_OT_cam_clear_all(Operator):
    """
    Clear all cameras from the list.
    
    Removes all cameras from the capture list with confirmation dialog.
    """
    
    bl_idname = "tlx.cam_clear_all"
    bl_label = "Clear All Cameras"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        """Check if operator can run."""
        return len(context.scene.tlx_cameras) > 0
    
    def invoke(self, context, event):
        """Show confirmation dialog."""
        return context.window_manager.invoke_confirm(self, event)
    
    def execute(self, context):
        """Clear all cameras from list."""
        scene = context.scene
        count = len(scene.tlx_cameras)
        
        # Clear list
        scene.tlx_cameras.clear()
        scene.tlx_cameras_index = 0
        
        logger.info(f"Cleared {count} cameras from list")
        self.report({'INFO'}, f"Cleared {count} cameras")
        
        return {'FINISHED'}


# ========================================================================================
# Select Camera in Viewport Operator
# ========================================================================================

class TLX_OT_cam_select(Operator):
    """
    Select the camera object in the viewport.
    
    Makes the camera from the list the active object.
    """
    
    bl_idname = "tlx.cam_select"
    bl_label = "Select Camera"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        """Check if operator can run."""
        scene = context.scene
        if len(scene.tlx_cameras) == 0:
            return False
        
        if not (0 <= scene.tlx_cameras_index < len(scene.tlx_cameras)):
            return False
        
        camera_item = scene.tlx_cameras[scene.tlx_cameras_index]
        return camera_item.camera is not None
    
    def execute(self, context):
        """Select camera in viewport."""
        scene = context.scene
        camera_item = scene.tlx_cameras[scene.tlx_cameras_index]
        camera = camera_item.camera
        
        # Deselect all
        bpy.ops.object.select_all(action='DESELECT')
        
        # Select and make active
        camera.select_set(True)
        context.view_layer.objects.active = camera
        
        self.report({'INFO'}, f"Selected: {camera.name}")
        
        return {'FINISHED'}


# ========================================================================================
# Registration
# ========================================================================================

classes = (
    TLX_OT_cam_add,
    TLX_OT_cam_remove,
    TLX_OT_cam_move_up,
    TLX_OT_cam_move_down,
    TLX_OT_apply_speed_preset,
    TLX_OT_cam_clear_all,
    TLX_OT_cam_select,
)


def register():
    """Register camera operators."""
    logger.info("Registering camera operators")
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            logger.error(f"Failed to register {cls.__name__}: {e}")


def unregister():
    """Unregister camera operators."""
    logger.info("Unregistering camera operators")
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            logger.warning(f"Failed to unregister {cls.__name__}: {e}")