"""
Utility operators for Timelapse X addon.
Simple helper operators like opening folders.
"""

import bpy
import os
import logging
from bpy.types import Operator

from .. import utils
from .. import state

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
        session_dir = state.TLX_State.session_dir
        return bool(session_dir and os.path.isdir(session_dir))
    
    def execute(self, context):
        """Open session folder."""
        session_dir = state.TLX_State.session_dir
        
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
        if state.TLX_State.capture_mode == 'WINDOW':
            return bool(state.TLX_State.last_window_image)
        else:
            return state.TLX_State.counter > 0
    
    def execute(self, context):
        """Reveal last capture."""
        # Window mode has direct path
        if state.TLX_State.capture_mode == 'WINDOW':
            last_path = state.TLX_State.last_window_image
            
            if last_path and os.path.isfile(last_path):
                try:
                    bpy.ops.wm.path_open(filepath=os.path.dirname(last_path))
                    return {'FINISHED'}
                except Exception as e:
                    logger.error(f"Cannot reveal file: {e}")
                    self.report({'ERROR'}, f'Cannot reveal file: {e}')
                    return {'CANCELLED'}
        
        # Camera mode - open session folder
        session_dir = state.TLX_State.session_dir
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
            path = state.TLX_State.session_dir
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
# Registration
# ========================================================================================

classes = (
    TLX_OT_open_images_folder,
    TLX_OT_open_session_folder,
    TLX_OT_open_mp4_folder,
    TLX_OT_reveal_last_capture,
    TLX_OT_copy_output_path,
    TLX_OT_clean_empty_folders,
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