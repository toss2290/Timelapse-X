"""
Utility operators for Timelapse X addon.
Simple helper operators like opening folders.

FIXED: Added force reset and debug operators
"""

import bpy
import os
import logging
from bpy.types import Operator

from .. import utils
from ..state_manager import StateManager


logger = logging.getLogger(__name__)

# ========================================================================================
# Open Images Folder Operator
# ========================================================================================

class TLX_OT_open_images_folder(Operator):
    """
    Open the images output folder in file browser.
    
    Opens the base output directory configured in preferences.
    """
    
    bl_idname = 'tlx.open_images_folder'
    bl_label = 'Open Images Folder'
    bl_description = "Open the timelapse images output folder"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        """Open images folder."""
        prefs = utils.get_addon_preferences()
        
        # Get base output directory
        base_dir = prefs.output_dir if prefs else '//'
        base_dir = bpy.path.abspath(base_dir)
        
        # Ensure directory exists
        try:
            if not os.path.exists(base_dir):
                os.makedirs(base_dir, exist_ok=True)
        except OSError as e:
            logger.error(f"Cannot create directory: {e}")
            self.report({'ERROR'}, f"Cannot create folder: {e}")
            return {'CANCELLED'}
        
        # Open in file browser
        try:
            bpy.ops.wm.path_open(filepath=base_dir)
            logger.info(f"Opened folder: {base_dir}")
            return {'FINISHED'}
        
        except Exception as e:
            logger.error(f"Cannot open folder: {e}")
            self.report({'ERROR'}, f'Cannot open folder: {e}')
            return {'CANCELLED'}


# ========================================================================================
# Open Session Folder Operator
# ========================================================================================

class TLX_OT_open_session_folder(Operator):
    """
    Open the current session folder in file browser.
    
    Opens the active recording session's output directory.
    """
    
    bl_idname = 'tlx.open_session_folder'
    bl_label = 'Open Session Folder'
    bl_description = "Open the current session's output folder"
    bl_options = {'REGISTER'}
    
    @classmethod
    def poll(cls, context):
        """Check if operator can run."""
        session_dir = StateManager().session_dir
        return bool(session_dir and os.path.isdir(session_dir))
    
    def execute(self, context):
        """Open session folder."""
        session_dir = StateManager().session_dir
        
        if not session_dir or not os.path.isdir(session_dir):
            self.report({'WARNING'}, 'No active session folder.')
            return {'CANCELLED'}
        
        # Open in file browser
        try:
            abs_path = bpy.path.abspath(session_dir)
            bpy.ops.wm.path_open(filepath=abs_path)
            logger.info(f"Opened session folder: {abs_path}")
            return {'FINISHED'}
        
        except Exception as e:
            logger.error(f"Cannot open session folder: {e}")
            self.report({'ERROR'}, f'Cannot open session folder: {e}')
            return {'CANCELLED'}


# ========================================================================================
# Open MP4 Folder Operator
# ========================================================================================

class TLX_OT_open_mp4_folder(Operator):
    """
    Open the MP4 output folder in file browser.
    
    Opens the folder where compiled MP4 videos are saved.
    """
    
    bl_idname = 'tlx.open_mp4_folder'
    bl_label = 'Open MP4 Folder'
    bl_description = "Open the MP4 output folder"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        """Open MP4 folder."""
        prefs = utils.get_addon_preferences()
        
        if not prefs:
            self.report({'ERROR'}, 'Preferences not available')
            return {'CANCELLED'}
        
        # Determine MP4 output directory
        if prefs.mp4_output_mode == 'SAME_AS_IMAGES':
            mp4_dir = bpy.path.abspath(prefs.output_dir)
        else:
            mp4_dir = bpy.path.abspath(prefs.mp4_custom_dir)
        
        # Ensure directory exists
        try:
            if not os.path.exists(mp4_dir):
                os.makedirs(mp4_dir, exist_ok=True)
        except OSError as e:
            logger.error(f"Cannot create directory: {e}")
            self.report({'ERROR'}, f"Cannot create folder: {e}")
            return {'CANCELLED'}
        
        # Open in file browser
        try:
            bpy.ops.wm.path_open(filepath=mp4_dir)
            logger.info(f"Opened MP4 folder: {mp4_dir}")
            return {'FINISHED'}
        
        except Exception as e:
            logger.error(f"Cannot open folder: {e}")
            self.report({'ERROR'}, f'Cannot open folder: {e}')
            return {'CANCELLED'}


# ========================================================================================
# Reveal in File Browser Operator
# ========================================================================================

class TLX_OT_reveal_last_capture(Operator):
    """
    Reveal the last captured image in file browser.
    
    Opens the file browser and highlights the most recent capture.
    """
    
    bl_idname = 'tlx.reveal_last_capture'
    bl_label = 'Reveal Last Capture'
    bl_description = "Show the last captured image in file browser"
    bl_options = {'REGISTER'}
    
    @classmethod
    def poll(cls, context):
        """Check if operator can run."""
        # Check if we have a last capture
        if StateManager().capture_mode == 'WINDOW':
            return bool(StateManager().last_window_image)
        else:
            return StateManager().counter > 0
    
    def execute(self, context):
        """Reveal last capture."""
        # Window mode has direct path
        if StateManager().capture_mode == 'WINDOW':
            last_path = StateManager().last_window_image
            
            if last_path and os.path.isfile(last_path):
                try:
                    bpy.ops.wm.path_open(filepath=os.path.dirname(last_path))
                    return {'FINISHED'}
                except Exception as e:
                    logger.error(f"Cannot reveal file: {e}")
                    self.report({'ERROR'}, f'Cannot reveal file: {e}')
                    return {'CANCELLED'}
        
        # Camera mode - open session folder
        session_dir = StateManager().session_dir
        if session_dir and os.path.isdir(session_dir):
            try:
                bpy.ops.wm.path_open(filepath=session_dir)
                return {'FINISHED'}
            except Exception as e:
                logger.error(f"Cannot open folder: {e}")
                self.report({'ERROR'}, f'Cannot open folder: {e}')
                return {'CANCELLED'}
        
        self.report({'WARNING'}, 'No captures to reveal.')
        return {'CANCELLED'}


# ========================================================================================
# Copy Output Path Operator
# ========================================================================================

class TLX_OT_copy_output_path(Operator):
    """
    Copy output path to clipboard.
    
    Copies the current output directory path to system clipboard.
    """
    
    bl_idname = 'tlx.copy_output_path'
    bl_label = 'Copy Output Path'
    bl_description = "Copy the output directory path to clipboard"
    bl_options = {'REGISTER'}
    
    path_type: bpy.props.EnumProperty(
        name="Path Type",
        items=[
            ('BASE', 'Base Folder', 'Copy base output folder path'),
            ('SESSION', 'Session Folder', 'Copy current session folder path'),
            ('MP4', 'MP4 Folder', 'Copy MP4 output folder path'),
        ],
        default='BASE'
    )
    
    def execute(self, context):
        """Copy path to clipboard."""
        prefs = utils.get_addon_preferences()
        
        # Determine path based on type
        if self.path_type == 'SESSION':
            path = StateManager().session_dir
            if not path:
                self.report({'WARNING'}, 'No active session.')
                return {'CANCELLED'}
        
        elif self.path_type == 'MP4':
            if not prefs:
                self.report({'ERROR'}, 'Preferences not available')
                return {'CANCELLED'}
            
            if prefs.mp4_output_mode == 'SAME_AS_IMAGES':
                path = prefs.output_dir
            else:
                path = prefs.mp4_custom_dir
        
        else:  # BASE
            path = prefs.output_dir if prefs else '//'
        
        # Get absolute path
        abs_path = bpy.path.abspath(path)
        
        # Copy to clipboard
        try:
            context.window_manager.clipboard = abs_path
            self.report({'INFO'}, f'Copied: {abs_path}')
            logger.info(f"Copied path to clipboard: {abs_path}")
            return {'FINISHED'}
        
        except Exception as e:
            logger.error(f"Cannot copy to clipboard: {e}")
            self.report({'ERROR'}, f'Cannot copy to clipboard: {e}')
            return {'CANCELLED'}


# ========================================================================================
# Clean Empty Folders Operator
# ========================================================================================

class TLX_OT_clean_empty_folders(Operator):
    """
    Clean empty folders from output directory.
    
    Removes empty session folders and dated folders to keep
    the output directory organized.
    """
    
    bl_idname = 'tlx.clean_empty_folders'
    bl_label = 'Clean Empty Folders'
    bl_description = "Remove empty session and dated folders"
    bl_options = {'REGISTER'}
    
    def invoke(self, context, event):
        """Show confirmation dialog."""
        return context.window_manager.invoke_confirm(self, event)
    
    def execute(self, context):
        """Clean empty folders."""
        prefs = utils.get_addon_preferences()
        
        if not prefs:
            self.report({'ERROR'}, 'Preferences not available')
            return {'CANCELLED'}
        
        base_dir = bpy.path.abspath(prefs.output_dir)
        
        if not os.path.isdir(base_dir):
            self.report({'WARNING'}, 'Output directory does not exist.')
            return {'CANCELLED'}
        
        # Count removed folders
        removed_count = 0
        
        try:
            # Walk directory tree (bottom-up to handle nested empties)
            for root, dirs, files in os.walk(base_dir, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    
                    # Check if empty
                    try:
                        if not os.listdir(dir_path):
                            os.rmdir(dir_path)
                            removed_count += 1
                            logger.debug(f"Removed empty folder: {dir_path}")
                    except OSError:
                        pass
        
        except Exception as e:
            logger.error(f"Error cleaning folders: {e}")
            self.report({'ERROR'}, f'Error: {e}')
            return {'CANCELLED'}
        
        logger.info(f"Cleaned {removed_count} empty folders")
        self.report({'INFO'}, f'Removed {removed_count} empty folders')
        
        return {'FINISHED'}


# ========================================================================================
# Force Reset State Operator (NEW)
# ========================================================================================

class TLX_OT_force_reset_state(Operator):
    """
    Force reset StateManager to clean state.
    
    Use when recording state is stuck (recording=True but no actual session).
    """
    
    bl_idname = 'tlx.force_reset_state'
    bl_label = 'Force Reset Recording State'
    bl_description = "Force reset stuck recording state (use when recording flag stuck ON)"
    bl_options = {'REGISTER'}
    
    def invoke(self, context, event):
        """Show confirmation dialog."""
        return context.window_manager.invoke_confirm(self, event)
    
    def execute(self, context):
        """Force reset state."""
        logger.warning("Force resetting StateManager...")
        
        mgr = StateManager()
        scene = context.scene
        wm = context.window_manager
        
        # Capture current state for logging
        before_state = {
            'recording': mgr.recording,
            'paused': mgr.paused,
            'counter': mgr.counter,
            'timer': mgr.timer is not None,
            'session_dir': mgr.session_dir,
            'scene_recording': scene.tlx_is_recording,
        }
        
        logger.info(f"State before reset: {before_state}")
        
        # 1. Remove timer if exists
        if mgr.timer:
            try:
                wm.event_timer_remove(mgr.timer)
                logger.info("✓ Removed timer")
            except Exception as e:
                logger.warning(f"Timer removal failed: {e}")
        
        # 2. Remove depsgraph handler
        if mgr.handler_installed:
            try:
                from ..state_manager import mark_scene_dirty
                bpy.app.handlers.depsgraph_update_post.remove(mark_scene_dirty)
                logger.info("✓ Removed depsgraph handler")
            except ValueError:
                pass
            except Exception as e:
                logger.warning(f"Handler removal failed: {e}")
        
        # 3. Cancel async captures
        try:
            from ..capture import window
            if hasattr(window, 'cancel_async_capture'):
                window.cancel_async_capture()
                logger.info("✓ Cancelled async captures")
        except Exception as e:
            logger.warning(f"Async cancel failed: {e}")
        
        # 4. Clear headers
        try:
            for window in wm.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.header_text_set(None)
            logger.info("✓ Cleared headers")
        except Exception as e:
            logger.debug(f"Header clear failed: {e}")
        
        # 5. Reset StateManager
        try:
            mgr.stop_recording()  # Clean stop
            mgr.reset()  # Full reset
            logger.info("✓ StateManager reset")
        except Exception as e:
            logger.error(f"StateManager reset failed: {e}")
        
        # 6. Reset scene flag
        scene.tlx_is_recording = False
        
        # 7. Verify reset
        after_state = {
            'recording': mgr.recording,
            'paused': mgr.paused,
            'counter': mgr.counter,
            'timer': mgr.timer is not None,
            'session_dir': mgr.session_dir,
            'scene_recording': scene.tlx_is_recording,
        }
        
        logger.info(f"State after reset: {after_state}")
        
        # Check if reset successful
        if mgr.recording or scene.tlx_is_recording:
            self.report({'ERROR'}, 
                '⚠ Reset incomplete - state still shows recording=True')
            logger.error("Reset failed - recording flag still True")
            return {'CANCELLED'}
        
        self.report({'INFO'}, '✓ Recording state reset successfully')
        logger.info("Force reset complete")
        
        return {'FINISHED'}


# ========================================================================================
# Show Debug State Operator (NEW)
# ========================================================================================

class TLX_OT_show_debug_state(Operator):
    """
    Show detailed StateManager debug information.
    
    Displays all internal state for troubleshooting.
    """
    
    bl_idname = 'tlx.show_debug_state'
    bl_label = 'Show Debug State'
    bl_description = "Show detailed StateManager state (for debugging)"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        """Show debug info."""
        mgr = StateManager()
        scene = context.scene
        
        print("\n" + "="*70)
        print("TIMELAPSE X - STATE DEBUG INFO")
        print("="*70)
        
        # Core state
        print("\n[CORE STATE]")
        print(f"  recording:              {mgr.recording}")
        print(f"  paused:                 {mgr.paused}")
        print(f"  capture_mode:           {mgr.capture_mode}")
        print(f"  counter:                {mgr.counter}")
        print(f"  scene.tlx_is_recording: {scene.tlx_is_recording}")
        
        # Session info
        print("\n[SESSION]")
        print(f"  session_dir:            {mgr.session_dir}")
        print(f"  last_capture_time:      {mgr.last_capture_time}")
        
        # Timer info
        print("\n[TIMER]")
        print(f"  timer exists:           {mgr.timer is not None}")
        if mgr.timer:
            print(f"  timer object:           {mgr.timer}")
        
        # Depsgraph info
        print("\n[DEPSGRAPH]")
        print(f"  dirty:                  {mgr.dirty}")
        print(f"  ignore_depsgraph:       {mgr.ignore_depsgraph}")
        print(f"  handler_installed:      {mgr.handler_installed}")
        print(f"  suppress_until:         {mgr.suppress_until}")
        
        # Window async info
        print("\n[WINDOW ASYNC]")
        print(f"  state:                  {mgr._window_async.state.value}")
        print(f"  pending:                {mgr.is_window_async_pending()}")
        print(f"  last_window_image:      {mgr.last_window_image}")
        
        # Camera info
        print("\n[CAMERAS]")
        print(f"  schedulers count:       {len(mgr._camera_schedulers)}")
        print(f"  round-robin index:      {mgr.rr_index}")
        
        if mgr._camera_schedulers:
            print("\n  Camera Schedulers:")
            for name, sched in mgr._camera_schedulers.items():
                print(f"    • {name}:")
                print(f"      interval:         {sched.interval}s")
                print(f"      total_captures:   {sched.total_captures}")
                print(f"      next_due:         {sched.next_due}")
        
        # Consistency check
        print("\n[CONSISTENCY CHECK]")
        is_consistent = True
        
        if mgr.recording and not mgr.timer:
            print("  ⚠ WARNING: recording=True but no timer!")
            is_consistent = False
        
        if mgr.recording and not mgr.session_dir:
            print("  ⚠ WARNING: recording=True but no session_dir!")
            is_consistent = False
        
        if mgr.recording != scene.tlx_is_recording:
            print(f"  ⚠ WARNING: StateManager.recording ({mgr.recording}) "
                  f"!= scene.tlx_is_recording ({scene.tlx_is_recording})")
            is_consistent = False
        
        if is_consistent:
            print("  ✓ All checks passed - state is consistent")
        else:
            print("  ✗ Inconsistencies detected - use Force Reset")
        
        print("\n" + "="*70 + "\n")
        
        self.report({'INFO'}, 'Debug info printed to console')
        return {'FINISHED'}


# ========================================================================================
# Registration
# ========================================================================================

classes = (
    TLX_OT_open_images_folder,
    TLX_OT_open_session_folder,
    TLX_OT_open_mp4_folder,
    TLX_OT_reveal_last_capture,
    TLX_OT_copy_output_path,
    TLX_OT_clean_empty_folders,
    TLX_OT_force_reset_state,      # NEW
    TLX_OT_show_debug_state,        # NEW
)


def register():
    """Register utility operators."""
    logger.info("Registering utility operators")
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            logger.error(f"Failed to register {cls.__name__}: {e}")


def unregister():
    """Unregister utility operators."""
    logger.info("Unregistering utility operators")
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            logger.warning(f"Failed to unregister {cls.__name__}: {e}")