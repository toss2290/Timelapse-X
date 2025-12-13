"""
Operators for Clean Window tools - FIXED VERSION
Fixed region validation to prevent "Region not found" errors.
"""

import bpy
import logging
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty

from .. import constants

logger = logging.getLogger(__name__)

# ========================================================================================
# Helper Functions
# ========================================================================================

def find_tracked_windows(wm):
    """
    Find tracked original and new windows.
    
    Args:
        wm: Window manager
    
    Returns:
        Tuple of (original_window, new_window)
    """
    original_key = getattr(wm, 'cmw_original_window_key', '') or ''
    new_key = getattr(wm, 'cmw_new_window_key', '') or ''
    
    original_window = None
    new_window = None
    
    # Find original window
    if original_key:
        try:
            target_ptr = int(original_key)
            for window in wm.windows:
                if int(window.as_pointer()) == target_ptr:
                    original_window = window
                    break
        except (ValueError, AttributeError):
            pass
    
    # Find new window
    if new_key:
        try:
            target_ptr = int(new_key)
            for window in wm.windows:
                if int(window.as_pointer()) == target_ptr:
                    new_window = window
                    break
        except (ValueError, AttributeError):
            pass
    
    return original_window, new_window


def resolve_context(window):
    """
    Resolve window context to window, screen, area, region.
    
    Args:
        window: Blender window object
    
    Returns:
        Tuple of (window, screen, area, region)
    """
    if not window:
        return None, None, None, None
    
    screen = window.screen
    if not screen or not getattr(screen, 'areas', None):
        return window, screen, None, None
    
    # Try to find VIEW_3D area
    area = None
    for a in screen.areas:
        if a.type == 'VIEW_3D':
            area = a
            break
    
    # Fallback to largest area
    if not area and screen.areas:
        area = max(screen.areas, key=lambda a: a.width * a.height)
    
    # Find WINDOW region
    region = None
    if area and getattr(area, 'regions', None):
        for r in area.regions:
            if r.type == 'WINDOW':
                region = r
                break
    
    return window, screen, area, region


def is_region_valid(region):
    """
    Check if region is valid and accessible.
    
    Args:
        region: Region object to validate
    
    Returns:
        True if region is valid and can be used
    """
    if not region:
        return False
    
    try:
        # Try to access a basic property
        _ = region.type
        return True
    except (AttributeError, ReferenceError):
        return False


def set_property_safe(obj, attr, value):
    """
    Safely set property value with error handling.
    
    Args:
        obj: Object to set property on
        attr: Property name
        value: Value to set
    """
    if obj and hasattr(obj, attr):
        try:
            setattr(obj, attr, value)
        except (AttributeError, RuntimeError):
            pass


def create_new_main_window(context):
    """
    Create a new main window.
    
    Args:
        context: Blender context
    
    Returns:
        New window object
    
    Raises:
        RuntimeError: If window creation fails
    """
    wm = context.window_manager
    
    # Track existing windows
    before = {int(w.as_pointer()) for w in wm.windows}
    
    # Create new window
    with context.temp_override(window=context.window, screen=context.screen):
        bpy.ops.wm.window_new_main()
    
    # Find new window
    new_windows = [w for w in wm.windows if int(w.as_pointer()) not in before]
    
    if not new_windows:
        raise RuntimeError('Failed to create a new main window.')
    
    return new_windows[0]


def apply_clean_settings(
    context,
    window,
    hide_ui=True,
    hide_overlays=True,
    hide_gizmos=True,
    deep_clean=False,
    shading='SOLID',
    fullscreen=False,
    maximize_area=False
):
    """
    Apply clean settings to a window.
    
    Args:
        context: Blender context
        window: Window to clean
        hide_ui: Hide UI regions
        hide_overlays: Hide overlays
        hide_gizmos: Hide gizmos
        deep_clean: Deep clean overlay elements
        shading: Shading type to apply
        fullscreen: Make window fullscreen
        maximize_area: Maximize area
    """
    win, screen, area, region = resolve_context(window)
    
    if not all((win, screen, area)):
        return
    
    # Build override context (only include valid region)
    override = {'window': win, 'screen': screen, 'area': area}
    if region and is_region_valid(region):
        override['region'] = region
    
    with context.temp_override(**override):
        space = area.spaces.active if area.spaces else None
        
        if space and space.type == 'VIEW_3D':
            # Hide UI regions
            if hide_ui:
                for attr in ('show_region_header', 'show_region_ui', 
                           'show_region_tool_header', 'show_region_toolbar'):
                    set_property_safe(space, attr, False)
            
            # Overlay settings
            overlay = getattr(space, 'overlay', None)
            if overlay:
                if hide_overlays and hasattr(overlay, 'show_overlays'):
                    overlay.show_overlays = False
                
                # Deep clean specific overlay elements
                if deep_clean and not hide_overlays:
                    for attr in ('show_text', 'show_cursor', 'show_annotation',
                               'show_floor', 'show_axis_x', 'show_axis_y', 
                               'show_axis_z', 'show_extras', 'show_stats',
                               'show_object_origins', 'show_object_origins_all'):
                        set_property_safe(overlay, attr, False)
            
            # Hide gizmos
            if hide_gizmos:
                set_property_safe(space, 'show_gizmo', False)
                for attr in ('show_gizmo_tool', 'show_gizmo_context', 'show_gizmo_navigate'):
                    set_property_safe(space, attr, False)
            
            # Apply shading
            if shading and shading != 'KEEP':
                try:
                    space.shading.type = shading
                except (AttributeError, RuntimeError):
                    pass
        
        # Maximize area
        if maximize_area:
            try:
                if screen and not screen.show_fullscreen:
                    # Rebuild override without region to avoid stale reference
                    max_override = {'window': win, 'screen': screen, 'area': area}
                    with context.temp_override(**max_override):
                        bpy.ops.screen.screen_full_area(use_hide_panels=True)
            except (AttributeError, RuntimeError, TypeError) as e:
                logger.warning(f"Failed to maximize area: {e}")
        
        # Fullscreen window
        if fullscreen:
            try:
                with context.temp_override(window=win):
                    bpy.ops.screen.window_fullscreen_toggle()
            except (AttributeError, RuntimeError, TypeError) as e:
                logger.warning(f"Failed to toggle fullscreen: {e}")


def restore_view_defaults(context, window):
    """
    Restore window to default view settings.
    
    Args:
        context: Blender context
        window: Window to restore
    """
    win, screen, area, region = resolve_context(window)
    
    if not all((win, screen, area)):
        return
    
    # Exit fullscreen/maximize if active
    try:
        if screen and screen.show_fullscreen:
            # Build override - only add region if valid
            override = {'window': win, 'area': area}
            if region and is_region_valid(region):
                override['region'] = region
            
            with context.temp_override(**override):
                bpy.ops.screen.screen_full_area(use_hide_panels=True)
    except (AttributeError, RuntimeError, TypeError) as e:
        logger.warning(f"Failed to exit fullscreen: {e}")
    
    # Restore UI and overlays
    # Build override - only add region if valid
    override = {'window': win, 'area': area}
    if region and is_region_valid(region):
        override['region'] = region
    
    try:
        with context.temp_override(**override):
            space = area.spaces.active if area.spaces else None
            
            if space and space.type == 'VIEW_3D':
                # Restore UI regions
                for attr in ('show_region_header', 'show_region_ui',
                           'show_region_tool_header', 'show_region_toolbar'):
                    set_property_safe(space, attr, True)
                
                # Restore overlays
                overlay = getattr(space, 'overlay', None)
                if overlay:
                    set_property_safe(overlay, 'show_overlays', True)
                    
                    # Restore overlay elements
                    for attr in ('show_text', 'show_cursor', 'show_annotation',
                               'show_floor', 'show_axis_x', 'show_axis_y',
                               'show_axis_z', 'show_extras', 'show_stats',
                               'show_object_origins', 'show_object_origins_all'):
                        set_property_safe(overlay, attr, True)
                
                # Restore gizmos
                set_property_safe(space, 'show_gizmo', True)
                for attr in ('show_gizmo_tool', 'show_gizmo_context', 'show_gizmo_navigate'):
                    set_property_safe(space, attr, True)
    except (AttributeError, RuntimeError, TypeError) as e:
        logger.warning(f"Failed to restore view settings: {e}")


def close_window_safely(context, window):
    """
    Safely close a window.
    
    Args:
        context: Blender context
        window: Window to close
    
    Returns:
        True if closed successfully
    """
    # Don't close last window
    if len(context.window_manager.windows) <= 1:
        return False
    
    win, screen, area, region = resolve_context(window)
    
    # Build override - only add valid components
    override = {'window': win}
    if screen:
        override['screen'] = screen
    if area:
        override['area'] = area
    if region and is_region_valid(region):
        override['region'] = region
    
    try:
        with context.temp_override(**override):
            return 'FINISHED' in bpy.ops.wm.window_close()
    except (AttributeError, RuntimeError, TypeError) as e:
        logger.warning(f"Failed to close window: {e}")
        return False


# ========================================================================================
# Create Clean Window Operator
# ========================================================================================

class CMW_OT_create_clean_window(Operator):
    """
    Create new window and clean original.
    
    Creates a new main window for normal work and applies
    clean settings to the original window for recording.
    """
    
    bl_idname = "cmw.create_clean_window"
    bl_label = "Create New Window & Clean Original"
    bl_options = {"REGISTER"}
    
    hide_overlays: BoolProperty(name="Hide Overlays", default=False)
    hide_gizmos: BoolProperty(name="Hide Gizmos", default=True)
    hide_ui: BoolProperty(name="Hide UI Regions", default=True)
    deep_clean: BoolProperty(name="Deep Clean Overlays", default=True)
    shading: EnumProperty(name="Shading", items=constants.CLEAN_WINDOW_SHADING, default='SOLID')
    fullscreen: BoolProperty(name="Fullscreen Window", default=True)
    maximize_area: BoolProperty(name="Maximize Area", default=True)
    
    def invoke(self, context, event):
        """Load settings from window manager."""
        wm = context.window_manager
        
        self.hide_ui = wm.cmw_hide_ui
        self.hide_overlays = wm.cmw_hide_overlays
        self.hide_gizmos = wm.cmw_hide_gizmos
        self.fullscreen = wm.cmw_fullscreen
        self.maximize_area = wm.cmw_maximize_area
        self.shading = wm.cmw_shading
        self.deep_clean = wm.cmw_deep_clean and not self.hide_overlays
        
        return self.execute(context)
    
    def execute(self, context):
        """Create clean window."""
        wm = context.window_manager
        
        # Check if new window already exists
        original_w, new_w = find_tracked_windows(wm)
        if new_w:
            self.report({'INFO'}, 'New window already exists. Use Toggle Off to close.')
            return {'CANCELLED'}
        
        # Track original window
        if not original_w:
            try:
                wm.cmw_original_window_key = str(context.window.as_pointer())
            except Exception as e:
                logger.error(f"Cannot track original window: {e}")
                self.report({'ERROR'}, f"Could not track original window: {e}")
                return {'CANCELLED'}
        
        # Create new window
        try:
            new_window = create_new_main_window(context)
            wm.cmw_new_window_key = str(new_window.as_pointer())
        except Exception as e:
            logger.error(f"Cannot create window: {e}")
            self.report({'ERROR'}, f"Cannot create new main window: {e}")
            return {'CANCELLED'}
        
        # Clean original window
        original_w_for_clean, _ = find_tracked_windows(wm)
        if not original_w_for_clean:
            self.report({'ERROR'}, 'Lost track of original window before cleaning.')
            return {'CANCELLED'}
        
        # Apply clean settings
        apply_clean_settings(
            context,
            original_w_for_clean,
            hide_ui=self.hide_ui,
            hide_overlays=self.hide_overlays,
            hide_gizmos=self.hide_gizmos,
            deep_clean=self.deep_clean,
            shading=self.shading,
            fullscreen=self.fullscreen,
            maximize_area=self.maximize_area
        )
        
        # Deferred clean (for timing issues)
        def _deferred_clean():
            original_w, new_w = find_tracked_windows(wm)
            if original_w:
                apply_clean_settings(
                    context,
                    original_w,
                    hide_ui=self.hide_ui,
                    hide_overlays=self.hide_overlays,
                    hide_gizmos=self.hide_gizmos,
                    deep_clean=self.deep_clean,
                    shading=self.shading,
                    fullscreen=False,
                    maximize_area=self.maximize_area
                )
            return None
        
        try:
            bpy.app.timers.register(_deferred_clean, first_interval=0.05)
        except:
            pass
        
        self.report({'INFO'}, 'New main window created & original window cleaned.')
        logger.info("Clean window created")
        
        return {'FINISHED'}


# ========================================================================================
# Toggle Clean Window Operator
# ========================================================================================

class CMW_OT_toggle_clean_window(Operator):
    """
    Toggle clean window on/off.
    
    If new window exists, closes it and restores original.
    If no new window, creates one.
    """
    
    bl_idname = "cmw.toggle_clean_window"
    bl_label = "Toggle Clean Window"
    bl_options = {"REGISTER"}
    
    def execute(self, context):
        """Toggle clean window."""
        wm = context.window_manager
        original_w, new_w = find_tracked_windows(wm)
        
        if new_w:
            # Turn off: close new window and restore original
            if original_w:
                win, screen, area, region = resolve_context(original_w)
                was_fullscreen = screen.show_fullscreen if screen else False
                
                restore_view_defaults(context, original_w)
                
                if was_fullscreen and win:
                    try:
                        with context.temp_override(window=win):
                            bpy.ops.screen.window_fullscreen_toggle()
                    except (AttributeError, RuntimeError, TypeError):
                        pass
            
            if not close_window_safely(context, new_w):
                self.report({'WARNING'}, 'Could not close new window.')
            
            wm.cmw_new_window_key = ''
            self.report({'INFO'}, 'New window closed. Original window remains tracked.')
            logger.info("Clean window closed")
        
        else:
            # Turn on: create clean window
            try:
                bpy.ops.cmw.create_clean_window('INVOKE_DEFAULT')
            except Exception as e:
                logger.error(f"Cannot create window: {e}")
                self.report({'ERROR'}, f"Cannot create window: {e}")
                return {'CANCELLED'}
        
        return {'FINISHED'}


# ========================================================================================
# Restore Original Window Operator
# ========================================================================================

class CMW_OT_restore_original_window(Operator):
    """
    Restore original window to default state.
    
    Restores without closing the new window.
    """
    
    bl_idname = "cmw.restore_original_window"
    bl_label = "Restore Original Window"
    bl_description = "Restore original main window to default state without closing new window"
    bl_options = {"REGISTER"}
    
    @classmethod
    def poll(cls, context):
        """Check if operator can run."""
        original_w, _ = find_tracked_windows(context.window_manager)
        return original_w is not None
    
    def execute(self, context):
        """Restore original window."""
        wm = context.window_manager
        original_w, _ = find_tracked_windows(wm)
        
        if not original_w:
            self.report({'WARNING'}, 'No original window found to restore.')
            return {'CANCELLED'}
        
        win, screen, area, region = resolve_context(original_w)
        was_fullscreen = screen.show_fullscreen if screen else False
        
        restore_view_defaults(context, original_w)
        
        if was_fullscreen and win:
            try:
                with context.temp_override(window=win):
                    bpy.ops.screen.window_fullscreen_toggle()
            except (AttributeError, RuntimeError, TypeError):
                pass
        
        self.report({'INFO'}, 'Original window restored to defaults.')
        logger.info("Original window restored")
        
        return {'FINISHED'}


# ========================================================================================
# Wireframe Toggle Operators
# ========================================================================================

class CMW_OT_toggle_wireframe(Operator):
    """Toggle wireframe display for selected objects."""
    
    bl_idname = "cmw.toggle_wireframe"
    bl_label = "Toggle Wireframe"
    bl_description = "Toggle wireframe display for selected objects"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.selected_objects
    
    def execute(self, context):
        """Toggle wireframe."""
        # Check if any disabled
        any_disabled = any(not obj.show_wire for obj in context.selected_objects)
        
        # Toggle all to match
        for obj in context.selected_objects:
            obj.show_wire = any_disabled
        
        return {'FINISHED'}


class CMW_OT_enable_wireframe(Operator):
    """Enable wireframe display for selected objects."""
    
    bl_idname = "cmw.enable_wireframe"
    bl_label = "Enable Wireframe"
    bl_description = "Enable wireframe display for selected objects"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.selected_objects
    
    def execute(self, context):
        """Enable wireframe."""
        for obj in context.selected_objects:
            obj.show_wire = True
        
        return {'FINISHED'}


class CMW_OT_disable_wireframe(Operator):
    """Disable wireframe display for selected objects."""
    
    bl_idname = "cmw.disable_wireframe"
    bl_label = "Disable Wireframe"
    bl_description = "Disable wireframe display for selected objects"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.selected_objects
    
    def execute(self, context):
        """Disable wireframe."""
        for obj in context.selected_objects:
            obj.show_wire = False
        
        return {'FINISHED'}


# ========================================================================================
# Registration
# ========================================================================================

classes = (
    CMW_OT_create_clean_window,
    CMW_OT_toggle_clean_window,
    CMW_OT_restore_original_window,
    CMW_OT_toggle_wireframe,
    CMW_OT_enable_wireframe,
    CMW_OT_disable_wireframe,
)


def register():
    """Register clean window operators."""
    logger.info("Registering clean window operators")
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            logger.error(f"Failed to register {cls.__name__}: {e}")


def unregister():
    """Unregister clean window operators."""
    logger.info("Unregistering clean window operators")
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            logger.warning(f"Failed to unregister {cls.__name__}: {e}")