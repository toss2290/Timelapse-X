"""
User-friendly error message system for Timelapse X.
Provides clear, actionable error messages with helpful suggestions.
"""

import logging
from typing import Optional, Dict, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


# ========================================================================================
# Error Categories
# ========================================================================================

class ErrorCategory(Enum):
    """Error categories for user-friendly grouping."""
    SETUP = "setup"
    CAMERA = "camera"
    FILE_SYSTEM = "file_system"
    PERMISSION = "permission"
    DISK_SPACE = "disk_space"
    RENDER = "render"
    VERSION = "version"
    UI = "ui"
    CAPTURE = "capture"
    VIDEO = "video"
    UNKNOWN = "unknown"


# ========================================================================================
# Error Message Database
# ========================================================================================

ERROR_MESSAGES = {
    # Setup Errors
    "already_recording": {
        "category": ErrorCategory.SETUP,
        "brief": "Already recording",
        "detailed": "A recording session is already in progress.",
        "solution": "Stop the current recording before starting a new one.",
        "icon": "INFO"
    },
    
    "no_preferences": {
        "category": ErrorCategory.SETUP,
        "brief": "Addon preferences not found",
        "detailed": "Could not access Timelapse X addon preferences.",
        "solution": "Try reloading the addon or restarting Blender.",
        "icon": "ERROR"
    },
    
    "session_dir_missing": {
        "category": ErrorCategory.FILE_SYSTEM,
        "brief": "Recording folder disappeared",
        "detailed": "The session folder was deleted or became inaccessible during recording.",
        "solution": "Check if the drive was unmounted or folder deleted. Recording will stop.",
        "icon": "ERROR"
    },
    
    # Camera Errors
    "camera_list_empty": {
        "category": ErrorCategory.CAMERA,
        "brief": "No cameras in list",
        "detailed": "Camera List mode requires at least one camera, but the list is empty.",
        "solution": "Click the '+' button to add cameras to the list, or switch to Window mode.",
        "icon": "ERROR"
    },
    
    "camera_invalid": {
        "category": ErrorCategory.CAMERA,
        "brief": "Invalid camera",
        "detailed": "Camera '{name}' is not valid or has been deleted.",
        "solution": "Remove the invalid camera from the list and add a valid one.",
        "icon": "ERROR"
    },
    
    "no_valid_cameras": {
        "category": ErrorCategory.CAMERA,
        "brief": "No valid cameras found",
        "detailed": "All cameras in the list are invalid, deleted, or not accessible.",
        "solution": "Clear the camera list and add valid cameras, or create new cameras.",
        "icon": "ERROR"
    },
    
    "camera_not_in_scene": {
        "category": ErrorCategory.CAMERA,
        "brief": "Camera not in scene",
        "detailed": "Camera '{name}' is not linked to the current scene.",
        "solution": "Remove it from the list or link it to the scene.",
        "icon": "WARNING"
    },
    
    # File System Errors
    "invalid_output_path": {
        "category": ErrorCategory.FILE_SYSTEM,
        "brief": "Invalid output folder",
        "detailed": "The output folder path is invalid: {path}",
        "solution": "Check the path in Preferences → Output Directory. Use '//' for relative paths.",
        "icon": "ERROR"
    },
    
    "cannot_create_directory": {
        "category": ErrorCategory.FILE_SYSTEM,
        "brief": "Cannot create folder",
        "detailed": "Failed to create output folder: {error}",
        "solution": "Check folder permissions and ensure the parent directory exists.",
        "icon": "ERROR"
    },
    
    "path_too_long": {
        "category": ErrorCategory.FILE_SYSTEM,
        "brief": "Path too long",
        "detailed": "The file path exceeds system limits ({length} characters).",
        "solution": "Choose a shorter output directory path or move the .blend file closer to root.",
        "icon": "ERROR"
    },
    
    "invalid_filename": {
        "category": ErrorCategory.FILE_SYSTEM,
        "brief": "Invalid filename",
        "detailed": "Filename contains invalid characters: {chars}",
        "solution": "Rename the camera or avoid special characters like < > : \" | ? *",
        "icon": "ERROR"
    },
    
    # Permission Errors
    "no_write_permission": {
        "category": ErrorCategory.PERMISSION,
        "brief": "No write permission",
        "detailed": "Cannot write to folder: {path}",
        "solution": "Choose a different folder, or run Blender as administrator (not recommended).",
        "icon": "ERROR"
    },
    
    "folder_read_only": {
        "category": ErrorCategory.PERMISSION,
        "brief": "Folder is read-only",
        "detailed": "The output folder is marked as read-only.",
        "solution": "Remove the read-only attribute or choose a different folder.",
        "icon": "ERROR"
    },
    
    # Disk Space Errors
    "insufficient_disk_space": {
        "category": ErrorCategory.DISK_SPACE,
        "brief": "Low disk space",
        "detailed": "Only {available}MB free. Timelapse recording needs at least {required}MB.",
        "solution": "Free up disk space or choose a different drive with more space.",
        "icon": "ERROR"
    },
    
    "disk_almost_full": {
        "category": ErrorCategory.DISK_SPACE,
        "brief": "Disk space running low",
        "detailed": "Only {available}MB remaining. Recording may fail soon.",
        "solution": "Monitor disk space and free up storage if needed.",
        "icon": "WARNING"
    },
    
    # Render Errors
    "invalid_resolution": {
        "category": ErrorCategory.RENDER,
        "brief": "Invalid render resolution",
        "detailed": "Render resolution is invalid: {width}x{height}",
        "solution": "Set a valid resolution in Render Properties (minimum 1x1, maximum 8192x8192).",
        "icon": "ERROR"
    },
    
    "resolution_too_large": {
        "category": ErrorCategory.RENDER,
        "brief": "Resolution too large",
        "detailed": "Render resolution {width}x{height} exceeds memory limits.",
        "solution": "Reduce render resolution to avoid crashes and memory issues.",
        "icon": "ERROR"
    },
    
    "render_engine_missing": {
        "category": ErrorCategory.RENDER,
        "brief": "Render engine not available",
        "detailed": "Render engine '{engine}' is not available in this Blender build.",
        "solution": "Available engines: {available}. Switch to a supported engine.",
        "icon": "ERROR"
    },
    
    "render_failed": {
        "category": ErrorCategory.RENDER,
        "brief": "Render failed",
        "detailed": "Camera '{camera}' failed to render: {error}",
        "solution": "Check render settings, memory usage, and console for details.",
        "icon": "ERROR"
    },
    
    # Version Errors
    "blender_version_old": {
        "category": ErrorCategory.VERSION,
        "brief": "Blender version too old",
        "detailed": "Timelapse X requires Blender {required} or newer. You're running {current}.",
        "solution": "Download the latest Blender from blender.org",
        "icon": "ERROR"
    },
    
    # UI Errors
    "headless_mode_window": {
        "category": ErrorCategory.UI,
        "brief": "Window mode needs GUI",
        "detailed": "Window capture mode cannot run without a GUI (headless/background mode).",
        "solution": "Use Camera List mode instead, or run Blender normally (not in background).",
        "icon": "ERROR"
    },
    
    "no_ui_context": {
        "category": ErrorCategory.UI,
        "brief": "No viewport available",
        "detailed": "Cannot find a 3D viewport to capture.",
        "solution": "Open a 3D viewport window, or use Camera List mode instead.",
        "icon": "ERROR"
    },
    
    "ui_region_invalid": {
        "category": ErrorCategory.UI,
        "brief": "Viewport not accessible",
        "detailed": "The 3D viewport became invalid during capture.",
        "solution": "Don't close or modify the viewport during recording.",
        "icon": "WARNING"
    },
    
    # Capture Errors
    "capture_failed": {
        "category": ErrorCategory.CAPTURE,
        "brief": "Capture failed",
        "detailed": "Failed to capture frame: {error}",
        "solution": "Check console for details. Try reducing quality settings or resolution.",
        "icon": "ERROR"
    },
    
    "timer_creation_failed": {
        "category": ErrorCategory.CAPTURE,
        "brief": "Cannot start recording timer",
        "detailed": "Failed to create recording timer: {error}",
        "solution": "Restart Blender or try a different interval setting.",
        "icon": "ERROR"
    },
    
    "invalid_interval": {
        "category": ErrorCategory.CAPTURE,
        "brief": "Invalid capture interval",
        "detailed": "Interval {value}s is outside valid range ({min}s - {max}s).",
        "solution": "Set an interval between {min}s and {max}s.",
        "icon": "ERROR"
    },
    
    # Video Errors
    "no_images_found": {
        "category": ErrorCategory.VIDEO,
        "brief": "No images to compile",
        "detailed": "No image files found in: {path}",
        "solution": "Record some frames first, or check that the folder contains PNG/JPEG images.",
        "icon": "ERROR"
    },
    
    "video_compilation_failed": {
        "category": ErrorCategory.VIDEO,
        "brief": "Video compilation failed",
        "detailed": "Failed to create MP4: {error}",
        "solution": "Check that FFMPEG is available and folder permissions are correct.",
        "icon": "ERROR"
    },
    
    "invalid_video_path": {
        "category": ErrorCategory.VIDEO,
        "brief": "Invalid video output path",
        "detailed": "Cannot save video to: {path}",
        "solution": "Choose a valid folder with write permissions.",
        "icon": "ERROR"
    },
}


# ========================================================================================
# Error Message Formatter
# ========================================================================================

class ErrorMessage:
    """User-friendly error message with multiple detail levels."""
    
    def __init__(
        self,
        error_key: str,
        context: Optional[Dict] = None,
        technical_details: Optional[str] = None
    ):
        """
        Create an error message.
        
        Args:
            error_key: Key from ERROR_MESSAGES database
            context: Context variables for formatting (e.g., {'name': 'Camera.001'})
            technical_details: Raw technical error for logging
        """
        self.error_key = error_key
        self.context = context or {}
        self.technical_details = technical_details
        
        # Get message template
        if error_key in ERROR_MESSAGES:
            self.template = ERROR_MESSAGES[error_key]
        else:
            # Fallback for unknown errors
            self.template = {
                "category": ErrorCategory.UNKNOWN,
                "brief": "Unexpected error",
                "detailed": str(technical_details) if technical_details else "An unknown error occurred.",
                "solution": "Check the console for details.",
                "icon": "ERROR"
            }
    
    def get_brief(self) -> str:
        """Get brief error message for UI."""
        return self._format_string(self.template["brief"])
    
    def get_detailed(self) -> str:
        """Get detailed error explanation."""
        return self._format_string(self.template["detailed"])
    
    def get_solution(self) -> str:
        """Get suggested solution."""
        return self._format_string(self.template["solution"])
    
    def get_full_message(self) -> str:
        """Get complete formatted message."""
        parts = [
            f"ERROR: {self.get_detailed()}",
            f"Solution: {self.get_solution()}"
        ]
        
        if self.technical_details:
            parts.append(f"Details: {self.technical_details}")
        
        return "\n".join(parts)
    
    def get_icon(self) -> str:
        """Get Blender icon name."""
        return self.template["icon"]
    
    def get_category(self) -> ErrorCategory:
        """Get error category."""
        return self.template["category"]
    
    def _format_string(self, template: str) -> str:
        """Format template string with context variables."""
        try:
            return template.format(**self.context)
        except KeyError as e:
            logger.warning(f"Missing context variable: {e}")
            return template
    
    def log(self, level: str = "error"):
        """Log error message."""
        log_func = getattr(logger, level, logger.error)
        
        message = f"[{self.error_key}] {self.get_detailed()}"
        if self.technical_details:
            message += f" | Technical: {self.technical_details}"
        
        log_func(message)
    
    def report_to_user(self, operator, report_type: Optional[str] = None):
        """
        Report error to user via operator.
        
        Args:
            operator: Blender operator with report() method
            report_type: Override report type ('ERROR', 'WARNING', 'INFO')
        """
        if report_type is None:
            report_type = self.get_icon()
        
        # Brief message for popup
        operator.report({report_type}, self.get_brief())
        
        # Detailed message to console
        self.log(level="error" if report_type == "ERROR" else "warning")
        
        # Print full message to console for user reference
        print(f"\n{'='*60}")
        print(f"TIMELAPSE X - {self.get_brief()}")
        print(f"{'='*60}")
        print(f"Details: {self.get_detailed()}")
        print(f"Solution: {self.get_solution()}")
        if self.technical_details:
            print(f"Technical: {self.technical_details}")
        print(f"{'='*60}\n")


# ========================================================================================
# Convenience Functions
# ========================================================================================

def create_error(error_key: str, **context) -> ErrorMessage:
    """
    Create an error message with context.
    
    Args:
        error_key: Error key from ERROR_MESSAGES
        **context: Context variables for formatting
    
    Returns:
        ErrorMessage instance
    
    Example:
        error = create_error('camera_invalid', name='Camera.001')
        error.report_to_user(self)
    """
    return ErrorMessage(error_key, context=context)


def create_technical_error(
    error_key: str,
    exception: Exception,
    **context
) -> ErrorMessage:
    """
    Create error from exception with technical details.
    
    Args:
        error_key: Error key from ERROR_MESSAGES
        exception: Original exception
        **context: Context variables
    
    Returns:
        ErrorMessage instance
    """
    return ErrorMessage(
        error_key,
        context=context,
        technical_details=str(exception)
    )


def report_validation_error(
    operator,
    validation_error,
    fallback_key: str = "unknown"
) -> None:
    """
    Report a ValidationError to user.
    
    Args:
        operator: Blender operator
        validation_error: ValidationError exception
        fallback_key: Fallback error key if not matched
    """
    error_msg = str(validation_error)
    
    # Try to match to known error patterns
    error_key = fallback_key
    context = {}
    
    if "Camera list is empty" in error_msg:
        error_key = "camera_list_empty"
    elif "No valid cameras" in error_msg:
        error_key = "no_valid_cameras"
    elif "Cannot create directory" in error_msg:
        error_key = "cannot_create_directory"
        context = {"error": error_msg}
    elif "not writable" in error_msg:
        error_key = "no_write_permission"
    elif "Insufficient disk space" in error_msg:
        error_key = "insufficient_disk_space"
        # Extract numbers from error message
        import re
        numbers = re.findall(r'(\d+(?:\.\d+)?)MB', error_msg)
        if len(numbers) >= 2:
            context = {"available": numbers[0], "required": numbers[1]}
    elif "version" in error_msg.lower():
        error_key = "blender_version_old"
    
    error = ErrorMessage(error_key, context=context, technical_details=error_msg)
    error.report_to_user(operator)


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}PB"


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


# ========================================================================================
# Success Messages
# ========================================================================================

SUCCESS_MESSAGES = {
    "recording_started": "Recording started! Interval: {interval}s, Mode: {mode}",
    "recording_stopped": "Recording stopped. Captured {count} frames.",
    "recording_paused": "Recording paused.",
    "recording_resumed": "Recording resumed. Interval: {interval}s",
    "camera_added": "Camera '{name}' added to list.",
    "camera_removed": "Camera '{name}' removed from list.",
    "video_compiled": "Video exported successfully! Duration: {duration}s, Size: {size}",
    "session_compiled": "Compiled {count} videos from session.",
    "interval_updated": "Capture interval updated to {interval}s.",
    "preset_applied": "Speed preset '{preset}' applied.",
    "folder_opened": "Folder opened: {path}",
    "settings_saved": "Settings saved.",
    "clean_window_created": "Clean window created for recording.",
    "clean_window_restored": "Original window restored.",
}


def report_success(operator, message_key: str, **context):
    """
    Report success message to user.
    
    Args:
        operator: Blender operator
        message_key: Key from SUCCESS_MESSAGES
        **context: Context variables for formatting
    """
    if message_key in SUCCESS_MESSAGES:
        template = SUCCESS_MESSAGES[message_key]
        try:
            message = template.format(**context)
        except KeyError:
            message = template
    else:
        message = str(context)
    
    operator.report({'INFO'}, message)
    logger.info(f"[SUCCESS] {message}")


# ========================================================================================
# Registration
# ========================================================================================

def register():
    """Register error message system."""
    logger.info("Error message system loaded")


def unregister():
    """Unregister error message system."""
    pass