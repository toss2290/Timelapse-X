"""
Addon preferences for Timelapse X.
Global settings and configuration UI.

FIXED DEFAULTS:
✅ Edit Mode Behavior: CAPTURE_ANYWAY (was: SKIP)
✅ Background Color: BLACK (0,0,0) - already correct
✅ Render Engine: BLENDER_WORKBENCH - already correct
"""

import bpy
import logging
from bpy.types import AddonPreferences
from bpy.props import (
    BoolProperty,
    EnumProperty,
    StringProperty,
    IntProperty,
    FloatProperty,
    FloatVectorProperty,
)

from . import constants
from . import utils

logger = logging.getLogger(__name__)

# ========================================================================================
# Update Callbacks
# ========================================================================================

def _update_show_freestyle_marks(self, context):
    """Callback when freestyle marks visibility changes."""
    try:
        utils.apply_freestyle_marks_visibility(bool(self.show_freestyle_marks_in_edit))
    except Exception as e:
        logger.error(f"Failed to update freestyle marks: {e}")


def _update_edit_mode_behavior(self, context):
    """Callback when edit mode behavior changes."""
    if self.edit_mode_behavior == 'CAPTURE_ANYWAY':
        logger.warning("Edit mode capture enabled - this may cause crashes!")


# ========================================================================================
# Addon Preferences
# ========================================================================================

class TLX_AddonPrefs(AddonPreferences):
    """
    Main addon preferences with all global settings.
    Organized into logical sections for better UX.
    """
    
    bl_idname = __name__.split('.')[0]
    
    # ==================== Output Settings ====================
    
    output_dir: StringProperty(
        name='Output Directory',
        subtype='DIR_PATH',
        default='//Timelapse_Images',
        description="Base directory for timelapse output"
    )
    
    image_format: EnumProperty(
        name='Image Format',
        items=constants.IMAGE_FORMATS,
        default='PNG',
        description="Default output image format"
    )
    
    png_rgba: BoolProperty(
        name='PNG RGBA (alpha)',
        default=False,
        description="Include alpha channel in PNG images"
    )
    
    jpeg_quality: IntProperty(
        name='JPEG Quality',
        min=1,
        max=100,
        default=90,
        description="JPEG compression quality (higher = better quality, larger file)"
    )
    
    zero_padding: IntProperty(
        name='Zero Padding',
        min=2,
        max=8,
        default=constants.DEFAULT_ZERO_PADDING,
        description="Number of digits in frame numbers (e.g., 4 = 0001, 0002...)"
    )
    
    # ==================== Capture Settings ====================
    
    default_interval: FloatProperty(
        name='Default Interval (s)',
        min=constants.MIN_INTERVAL,
        max=3600.0,
        default=constants.DEFAULT_INTERVAL,
        description='Base interval between captures when using Camera List mode'
    )
    
    idle_detection: BoolProperty(
        name='Idle Detection (Camera List)',
        default=True,
        description='Only save a frame if scene changes (reduces duplicates)'
    )
    
    capture_immediate_on_start: BoolProperty(
        name='Capture Immediately on Start',
        default=True,
        description='Take the first frame right after you press Start'
    )
    
    # ===== Edit Mode Behavior =====
    # ✅ FIXED: Default changed to CAPTURE_ANYWAY per user request
    edit_mode_behavior: EnumProperty(
        name='Edit Mode Behavior',
        items=constants.EDIT_MODE_BEHAVIORS,
        default='CAPTURE_ANYWAY',  # ✅ CHANGED: User requested default
        update=_update_edit_mode_behavior,
        description='How to handle capturing when user is in Edit mode'
    )
    
    edit_mode_auto_save: BoolProperty(
        name='Auto-save Before Capture',
        default=True,
        description='Automatically save edit mode changes before switching to Object mode (only for FORCE_OBJECT)'
    )
    
    # ==================== Viewport Shading (Window Mode) ====================
    
    lock_shading: BoolProperty(
        name='Lock Viewport Shading (Window)',
        default=True,
        description="Force specific shading in viewport during window capture"
    )
    
    shading_type: EnumProperty(
        name='Viewport Shading',
        items=constants.SHADING_TYPES,
        default='SOLID',
        description="Shading type to use when locked"
    )
    
    xray: BoolProperty(
        name='X-Ray (Window)',
        default=False,
        description="Enable X-Ray mode in viewport"
    )
    
    disable_shadows: BoolProperty(
        name='Disable Shadows in Viewport (Window)',
        default=True,
        description="Disable shadows for faster viewport"
    )
    
    # ==================== Wireframe Settings (Camera List) ====================
    
    wireframe_strategy: EnumProperty(
        name="Wireframe Strategy",
        items=constants.WIREFRAME_STRATEGIES,
        default='PURE',
        description="How to render wireframe views"
    )
    
    wireframe_thickness: FloatProperty(
        name="Line Thickness",
        min=0.1,
        max=10.0,
        default=1.0,
        description="Line thickness for Freestyle wireframe"
    )
    
    wireframe_color: FloatVectorProperty(
        name="Line Color",
        subtype='COLOR',
        size=3,
        min=0.0,
        max=1.0,
        default=(0.0, 0.0, 0.0),  # Black lines
        description="Line color for Freestyle wireframe"
    )
    
    # ✅ Background color: BLACK (0,0,0) - correct default
    wireframe_bg_color: FloatVectorProperty(
        name="Background Color",
        subtype='COLOR',
        size=3,
        min=0.0,
        max=1.0,
        default=(0.0, 0.0, 0.0),  # ✅ BLACK - correct
        description="Background color for wireframe render"
    )
    
    wireframe_bg_strength: FloatProperty(
        name="Background Strength",
        min=0.0,
        max=2.0,
        default=1.0,
        description="Background brightness/emission strength"
    )
    
    wireframe_disable_shadows: BoolProperty(
        name="Disable Shadows",
        default=True,
        description="Disable shadow rendering in wireframe mode"
    )
    
    wireframe_transparent_bg: BoolProperty(
        name="Transparent Background",
        default=False,
        description="Use transparent background instead of solid color"
    )
    
    # ===== Object Color Settings =====
    
    wireframe_use_object_colors: BoolProperty(
        name="Use Object Colors",
        default=False,
        description="Use each object's viewport display color. If disabled, all objects will be rendered in white"
    )
    
    wireframe_default_object_color: FloatVectorProperty(
        name="Default Object Color",
        subtype='COLOR',
        size=3,
        min=0.0,
        max=1.0,
        default=(1.0, 1.0, 1.0),  # White
        description="Color to use for objects when 'Use Object Colors' is disabled"
    )
    
    # ✅ Render engine: BLENDER_WORKBENCH - correct default
    wireframe_render_engine: EnumProperty(
        name="Wireframe Render Engine",
        items=[
            ('BLENDER_WORKBENCH', 'Workbench', 'Fast workbench engine'),
            ('BLENDER_EEVEE_NEXT', 'Eevee Next', 'Modern Eevee engine'),
            ('BLENDER_EEVEE', 'Eevee', 'Legacy Eevee engine'),
            ('CYCLES', 'Cycles', 'Cycles raytracing engine'),
        ],
        default='BLENDER_WORKBENCH',  # ✅ Correct - Workbench default
        description="Render engine for wireframe rendering"
    )
    
    show_freestyle_marks_in_edit: BoolProperty(
        name='Show Freestyle Marks in Edit',
        default=False,
        update=_update_show_freestyle_marks,
        description="Show freestyle edge marks in edit mode"
    )
    
    # ==================== Performance Settings ====================
    
    perf_hide_overlays_during_capture: BoolProperty(
        name="Hide Overlays During Capture (Window)",
        default=True,
        description="Hide viewport overlays during capture for cleaner output"
    )
    
    perf_depsgraph_suppress_ms: IntProperty(
        name="Depsgraph/Window Cooldown (ms)",
        min=0,
        max=1000,
        default=constants.DEFAULT_SUPPRESS_MS,
        description='Cooldown after a frame is saved to avoid over-capturing'
    )
    
    # ==================== Camera List Performance ====================
    
    camera_round_robin: BoolProperty(
        name="Round-robin (Camera List)",
        default=True,
        description="Cycle through cameras one at a time (more efficient)"
    )
    
    camera_max_per_tick: IntProperty(
        name="Max Cameras per Tick",
        min=1,
        max=32,
        default=1,
        description="Maximum cameras to render in one timer tick"
    )
    
    camera_lock_interface: BoolProperty(
        name="Lock UI During Render (Camera List)",
        default=True,
        description="Lock interface during camera rendering"
    )
    
    camera_low_overhead: BoolProperty(
        name="Low-Overhead Render (Camera List)",
        default=True,
        description="Use simplified render settings for speed"
    )
    
    camera_png_compress: IntProperty(
        name="PNG Compression (Camera List)",
        min=0,
        max=15,
        default=3,
        description="PNG compression level (0=fastest, 15=smallest)"
    )
    
    # ==================== Video Export Settings ====================
    
    mp4_output_mode: EnumProperty(
        name='MP4 Output',
        items=constants.MP4_OUTPUT_MODES,
        default='SAME_AS_IMAGES',
        description="Where to save compiled MP4 videos"
    )
    
    mp4_custom_dir: StringProperty(
        name='MP4 Custom Folder',
        subtype='DIR_PATH',
        default='//Timelapse_Videos',
        description="Custom folder for MP4 output"
    )
    
    # ==================== Window Capture Settings ====================
    
    window_idle_diff: BoolProperty(
        name="Window Idle via Image Diff",
        default=False,
        description='Only save a Window frame if the image content changes beyond the threshold'
    )
    
    window_idle_threshold: FloatProperty(
        name="Window Idle Threshold",
        min=0.0,
        max=0.2,
        default=constants.DEFAULT_IDLE_THRESHOLD,
        description='Sensitivity of change detection. Smaller = more sensitive (saves more)'
    )
    
    window_idle_downscale: IntProperty(
        name="Diff Downscale (px)",
        min=8,
        max=256,
        default=constants.DEFAULT_DOWNSCALE_SIZE,
        description='Downscale size for diffing. Smaller = faster, larger = more accurate'
    )
    
    window_capture_scope: EnumProperty(
        name="Window Capture Scope",
        items=constants.WINDOW_CAPTURE_SCOPES,
        default='VIEW3D',
        description="What part of the window to capture"
    )
    
    window_stabilize_view: BoolProperty(
        name="Stabilize 3D View (Window)",
        default=True,
        description="Hide overlays/gizmos briefly during capture for stable output"
    )
    
    window_async_capture: BoolProperty(
        name="Window Async Capture",
        default=True,
        description="Capture window asynchronously to avoid blocking"
    )
    
    window_async_delay_ms: IntProperty(
        name="Window Async Delay (ms)",
        min=0,
        max=200,
        default=2,
        description="Delay before async capture (allows UI to settle)"
    )
    
    window_input_suppress_ms: IntProperty(
        name="Window Input Cooldown (ms)",
        min=0,
        max=2147483647,
        default=250,
        description='After input event, wait this many ms before next capture. 0 disables'
    )
    
    window_capture_on_input_only: BoolProperty(
        name="Capture on Input Only (Window)",
        default=False,
        description='Only capture when mouse/keyboard input detected (not on timer)'
    )
    
    # ==================== UI State ====================
    
    ui_quick_settings_collapsed: BoolProperty(
        name="Quick Settings Collapsed",
        default=False,
        description="Collapse quick settings panel"
    )
    
    ui_clean_window_collapsed: BoolProperty(
        name="Clean Window Tools Collapsed",
        default=True,
        description="Collapse clean window tools panel"
    )
    
    # ==================== Debug Settings ====================
    
    show_debug_panel: BoolProperty(
        name="Show Debug Panel",
        default=False,
        description="Show debug information panel in UI (for troubleshooting stuck state)"
    )

    # ==================== Preferences UI ====================
    
    def draw(self, context):
        """Draw preferences UI."""
        layout = self.layout
        
        # Output Settings
        box = layout.box()
        box.label(text="Output Settings", icon='FILE')
        box.prop(self, 'output_dir')
        
        row = box.row(align=True)
        row.prop(self, 'image_format')
        
        if self.image_format == 'PNG':
            row.prop(self, 'png_rgba')
        else:
            row.prop(self, 'jpeg_quality')
        
        box.prop(self, 'zero_padding')
        
        # Capture Settings
        box = layout.box()
        box.label(text="Capture Settings", icon='RENDER_ANIMATION')
        box.prop(self, 'default_interval')
        box.prop(self, 'idle_detection')
        box.prop(self, 'capture_immediate_on_start')
        
        # Edit Mode Behavior
        box.separator()
        
        edit_box = box.box()
        edit_box.label(text="Edit Mode Behavior:", icon='EDITMODE_HLT')
        edit_box.prop(self, 'edit_mode_behavior', text='')
        
        # Warning for CAPTURE_ANYWAY (now default)
        if self.edit_mode_behavior == 'CAPTURE_ANYWAY':
            warning = edit_box.box()
            warning.alert = True
            col = warning.column(align=True)
            col.label(text="⚠ WARNING: May cause crashes!", icon='ERROR')
            col.label(text="This is the default but use with caution.")
            col.label(text="Switch to 'Skip Capture' for safer operation.")
        
        # Show auto-save option for FORCE_OBJECT
        if self.edit_mode_behavior == 'FORCE_OBJECT':
            edit_box.prop(self, 'edit_mode_auto_save')
            info = edit_box.box()
            col = info.column(align=True)
            col.scale_y = 0.8
            col.label(text="ℹ This will briefly switch to Object mode,", icon='INFO')
            col.label(text="  capture the frame, then return to Edit mode.")
        
        # Info for SKIP
        if self.edit_mode_behavior == 'SKIP':
            info = edit_box.box()
            col = info.column(align=True)
            col.scale_y = 0.8
            col.label(text="✓ Safest option: No crashes.", icon='CHECKMARK')
            col.label(text="  Capture resumes when you exit Edit mode.")
        
        # Viewport Shading
        box = layout.box()
        box.label(text="Viewport Shading (Window Mode)", icon='SHADING_RENDERED')
        box.prop(self, 'lock_shading')
        
        if self.lock_shading:
            col = box.column(align=True)
            col.prop(self, 'shading_type')
            col.prop(self, 'xray')
            col.prop(self, 'disable_shadows')
        
        # Wireframe Settings
        box = layout.box()
        box.label(text="Wireframe Rendering (Freestyle, Camera List)", icon='MOD_WIREFRAME')
        
        # Line settings
        col = box.column(align=True)
        col.label(text="Line Settings:")
        row = col.row(align=True)
        row.prop(self, 'wireframe_color', text="")
        row.prop(self, 'wireframe_thickness', text="Thickness")
        
        box.separator()
        
        # Background settings
        col = box.column(align=True)
        col.label(text="Background Settings:")
        
        col.prop(self, 'wireframe_transparent_bg', text="Transparent Background")
        
        # Disable color/strength if transparent
        sub = col.column(align=True)
        sub.enabled = not self.wireframe_transparent_bg
        row = sub.row(align=True)
        row.prop(self, 'wireframe_bg_color', text="")
        row.prop(self, 'wireframe_bg_strength', text="Strength", slider=True)
        
        box.separator()
        
        # Object Color Settings
        col = box.column(align=True)
        col.label(text="Object Color Settings:")
        
        col.prop(self, 'wireframe_use_object_colors', text="Use Object Viewport Colors")
        
        # Show default color picker when NOT using object colors
        if not self.wireframe_use_object_colors:
            row = col.row(align=True)
            row.label(text="Default Color:")
            row.prop(self, 'wireframe_default_object_color', text="")
        else:
            info_row = col.row()
            info_row.scale_y = 0.8
            info_row.label(text="  ℹ Objects will use their viewport display colors", icon='INFO')
        
        box.separator()
        
        # Render settings
        col = box.column(align=True)
        col.label(text="Render Settings:")
        col.prop(self, 'wireframe_disable_shadows')
        col.prop(self, 'wireframe_render_engine', text="Engine")
        col.prop(self, 'show_freestyle_marks_in_edit')
        
        # Preview colors
        box.separator()
        preview = box.box()
        preview.label(text="Color Preview:", icon='COLOR')
        
        split = preview.split(factor=0.33)
        
        # Background preview
        bg_col = split.column()
        bg_col.label(text="Background:")
        if not self.wireframe_transparent_bg:
            bg_row = bg_col.row()
            bg_row.scale_y = 2.0
            bg_row.enabled = False
            bg_row.prop(self, 'wireframe_bg_color', text="")
        else:
            bg_info = bg_col.row()
            bg_info.scale_y = 0.8
            bg_info.label(text="  (Transparent)", icon='SHADING_RENDERED')
        
        # Line preview
        line_col = split.column()
        line_col.label(text="Line:")
        line_row = line_col.row()
        line_row.scale_y = 2.0
        line_row.enabled = False
        line_row.prop(self, 'wireframe_color', text="")
        
        # Object color preview
        obj_col = split.column()
        obj_col.label(text="Object:")
        if not self.wireframe_use_object_colors:
            obj_row = obj_col.row()
            obj_row.scale_y = 2.0
            obj_row.enabled = False
            obj_row.prop(self, 'wireframe_default_object_color', text="")
        else:
            obj_info = obj_col.row()
            obj_info.scale_y = 0.8
            obj_info.label(text="  (Viewport colors)", icon='OBJECT_DATA')
        
        # Performance
        box = layout.box()
        box.label(text="Performance", icon='PREFERENCES')
        box.prop(self, 'perf_hide_overlays_during_capture')
        box.prop(self, 'perf_depsgraph_suppress_ms')
        
        col = box.column(align=True)
        col.label(text="Camera List Performance:")
        col.prop(self, 'camera_round_robin')
        col.prop(self, 'camera_max_per_tick')
        col.prop(self, 'camera_lock_interface')
        col.prop(self, 'camera_low_overhead')
        col.prop(self, 'camera_png_compress')
        
        # Video Export
        box = layout.box()
        box.label(text='MP4 Output', icon='FILE_MOVIE')
        box.prop(self, 'mp4_output_mode', expand=True)
        
        row = box.row()
        row.enabled = (self.mp4_output_mode == 'CUSTOM_DIR')
        row.prop(self, 'mp4_custom_dir')
        
        # Window Capture
        box = layout.box()
        box.label(text="Window Capture Settings", icon='WINDOW')
        box.prop(self, 'window_capture_scope')
        box.prop(self, 'window_stabilize_view')
        box.prop(self, 'window_async_capture')
        
        if self.window_async_capture:
            box.prop(self, 'window_async_delay_ms')
        
        box.prop(self, 'window_capture_on_input_only')
        box.prop(self, 'window_input_suppress_ms')
        
        box.separator()
        box.prop(self, 'window_idle_diff')
        
        if self.window_idle_diff:
            row = box.row(align=True)
            row.prop(self, 'window_idle_threshold')
            row.prop(self, 'window_idle_downscale')
        
        # Developer / Debug
        box = layout.box()
        box.label(text="Developer / Debug", icon='CONSOLE')
        box.prop(self, 'show_debug_panel')
        
        if self.show_debug_panel:
            info = box.box()
            col = info.column(align=True)
            col.scale_y = 0.8
            col.label(text="ℹ Debug panel will appear at bottom of main panel", icon='INFO')
            col.label(text="  Use to troubleshoot stuck recording state")
            col.label(text="  Shows: recording flag, timer, session, counters")


# ========================================================================================
# Registration
# ========================================================================================

classes = (
    TLX_AddonPrefs,
)


def register():
    """Register preferences classes."""
    logger.info("Registering preferences module (FIXED: CAPTURE_ANYWAY default)")
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            logger.error(f"Failed to register {cls.__name__}: {e}")


def unregister():
    """Unregister preferences classes."""
    logger.info("Unregistering preferences module")
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            logger.warning(f"Failed to unregister {cls.__name__}: {e}")