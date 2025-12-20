"""
Utility functions for Timelapse X addon.
"""

import bpy
import os
import re
import logging
from typing import Optional, Tuple, List
from datetime import datetime

from . import constants

logger = logging.getLogger(__name__)


# ========================================================================================
# SIMPLIFIED Path Validation (50 lines vs 500 lines)
# ========================================================================================

class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def validate_path_safe(path: str, must_exist: bool = False, 
                       must_be_dir: bool = False, must_be_file: bool = False,
                       must_be_writable: bool = False) -> str:
    """
    Validate and normalize path with basic security checks.
    
    Args:
        path: Path to validate
        must_exist: Path must exist
        must_be_dir: Must be directory
        must_be_file: Must be file
        must_be_writable: Must be writable
    
    Returns:
        Normalized absolute path
    
    Raises:
        ValidationError: If validation fails
    """
    if not path or not isinstance(path, str):
        raise ValidationError("Path is empty or invalid")
    
    # Basic security: no null bytes
    if '\x00' in path:
        raise ValidationError("Path contains null byte")
    
    # Expand and normalize
    try:
        expanded = os.path.expanduser(os.path.expandvars(path))
        
        # Handle Blender relative paths (//)
        if expanded.startswith('//'):
            if bpy.data.is_saved:
                blend_dir = os.path.dirname(bpy.data.filepath)
                expanded = os.path.join(blend_dir, expanded[2:])
            else:
                expanded = os.path.join(os.path.expanduser('~'), expanded[2:])
        
        normalized = os.path.normpath(os.path.abspath(expanded))
    except Exception as e:
        raise ValidationError(f"Cannot normalize path: {e}")
    
    # Existence checks
    if must_exist and not os.path.exists(normalized):
        raise ValidationError(f"Path does not exist: {normalized}")
    
    if os.path.exists(normalized):
        if must_be_dir and not os.path.isdir(normalized):
            raise ValidationError(f"Not a directory: {normalized}")
        
        if must_be_file and not os.path.isfile(normalized):
            raise ValidationError(f"Not a file: {normalized}")
        
        if must_be_writable and not os.access(normalized, os.W_OK):
            raise ValidationError(f"Not writable: {normalized}")
    
    # Check parent writable for new files
    elif must_be_writable:
        parent = os.path.dirname(normalized)
        if os.path.exists(parent) and not os.access(parent, os.W_OK):
            raise ValidationError(f"Parent directory not writable: {parent}")
    
    return normalized


# Convenience wrappers
def validate_input_path(path: str) -> str:
    """Validate input file/directory."""
    return validate_path_safe(path, must_exist=True)


def validate_output_path(path: str) -> str:
    """Validate output file/directory."""
    return validate_path_safe(path, must_be_writable=True)


def validate_directory(path: str, must_exist: bool = True, must_be_writable: bool = False) -> str:
    """Validate directory path."""
    return validate_path_safe(path, must_exist=must_exist, must_be_dir=True, 
                             must_be_writable=must_be_writable)


def validate_file(path: str, must_exist: bool = True) -> str:
    """Validate file path."""
    return validate_path_safe(path, must_exist=must_exist, must_be_file=True)


# ========================================================================================
# File System Operations
# ========================================================================================

def ensure_directory(path: str, validate_writable: bool = False) -> str:
    """
    Ensure directory exists.
    
    Args:
        path: Directory path
        validate_writable: Check write permissions
    
    Returns:
        Absolute path to directory
    """
    abs_path = bpy.path.abspath(path)
    
    try:
        os.makedirs(abs_path, exist_ok=True)
    except OSError as e:
        raise ValidationError(f"Cannot create directory: {e}")
    
    if validate_writable:
        if not os.access(abs_path, os.W_OK):
            raise ValidationError(f"Directory not writable: {abs_path}")
    
    return abs_path


def get_dated_folder(base_dir: str) -> str:
    """Get or create folder with today's date (YYYYMMDD)."""
    validated_base = ensure_directory(base_dir)
    date_str = datetime.now().strftime('%Y%m%d')
    dated_path = os.path.join(validated_base, date_str)
    
    try:
        os.makedirs(dated_path, exist_ok=True)
        return dated_path
    except OSError as e:
        raise ValidationError(f"Cannot create dated folder: {e}")


def get_session_folder(base_dir: str) -> str:
    """Get or create session folder with timestamp (HHMMSS)."""
    dated_folder = get_dated_folder(base_dir)
    time_str = datetime.now().strftime('%H%M%S')
    session_path = os.path.join(dated_folder, time_str)
    
    try:
        os.makedirs(session_path, exist_ok=True)
        return session_path
    except OSError as e:
        raise ValidationError(f"Cannot create session folder: {e}")


def sanitize_filename(name: str, replacement: str = '_', max_length: int = 200) -> str:
    """
    Sanitize string for use as filename.
    
    Args:
        name: Original name
        replacement: Replacement for invalid chars
        max_length: Maximum length
    
    Returns:
        Safe filename
    """
    if not name:
        return 'unnamed'
    
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"|?*\x00-\x1f]', replacement, name)
    sanitized = sanitized.strip('. ')
    
    # Truncate
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized or 'unnamed'


def generate_filename(base_dir: str, prefix: str, index: int, 
                      extension: str, zero_padding: int = 4) -> str:
    """Generate numbered filename."""
    safe_prefix = sanitize_filename(prefix)
    safe_ext = extension.lower().strip('.')
    filename = f"{safe_prefix}_{str(index).zfill(zero_padding)}.{safe_ext}"
    return os.path.join(base_dir, filename)


# ========================================================================================
# Scene/Camera Validation
# ========================================================================================

def validate_scene(scene) -> None:
    """Validate scene for capture."""
    if not scene:
        raise ValidationError("Scene is None")
    
    if not hasattr(scene, 'render'):
        raise ValidationError("Scene has no render settings")
    
    render = scene.render
    if render.resolution_x <= 0 or render.resolution_y <= 0:
        raise ValidationError(f"Invalid resolution: {render.resolution_x}x{render.resolution_y}")


def validate_camera(camera) -> None:
    """Validate camera object."""
    if not camera:
        raise ValidationError("Camera is None")
    
    if camera.type != 'CAMERA':
        raise ValidationError(f"Not a camera: {camera.type}")


def validate_camera_list(scene) -> None:
    """Validate camera list."""
    if not hasattr(scene, 'tlx_cameras') or len(scene.tlx_cameras) == 0:
        raise ValidationError("Camera list is empty")
    
    valid_count = sum(1 for item in scene.tlx_cameras 
                     if item.camera and item.camera.type == 'CAMERA')
    
    if valid_count == 0:
        raise ValidationError("No valid cameras in list")


def validate_blender_version(min_version: Tuple[int, int, int] = (4, 0, 0)) -> bool:
    """Check Blender version compatibility."""
    if bpy.app.version < min_version:
        raise ValidationError(
            f"Blender {min_version[0]}.{min_version[1]} or higher required, "
            f"running {bpy.app.version[0]}.{bpy.app.version[1]}"
        )
    return True


def validate_disk_space(path: str, required_mb: int = 100) -> bool:
    """Check disk space."""
    try:
        import shutil
        stat = shutil.disk_usage(bpy.path.abspath(path))
        free_mb = stat.free / (1024 * 1024)
        
        if free_mb < required_mb:
            raise ValidationError(
                f"Insufficient disk space: {free_mb:.1f}MB available, "
                f"{required_mb}MB required"
            )
        return True
    except Exception as e:
        logger.warning(f"Cannot check disk space: {e}")
        return True


# ========================================================================================
# Addon Preferences
# ========================================================================================

def get_addon_preferences(validate: bool = False):
    """Get addon preferences."""
    addon_keys = ['timelapse_x', __package__, __name__.split('.')[0]]
    
    for key in addon_keys:
        addon_module = bpy.context.preferences.addons.get(key)
        if addon_module and hasattr(addon_module, 'preferences'):
            return addon_module.preferences
    
    # Fallback search
    for key, addon_module in bpy.context.preferences.addons.items():
        prefs = getattr(addon_module, 'preferences', None)
        if prefs and getattr(prefs, 'bl_idname', '') in addon_keys:
            return prefs
    
    logger.warning("Addon preferences not found")
    return None


# ========================================================================================
# Environment Detection
# ========================================================================================

def is_headless() -> bool:
    """Check if running headless/background."""
    try:
        wm = getattr(bpy.context, "window_manager", None)
        if not wm:
            return True
        return len(getattr(wm, "windows", [])) == 0
    except (AttributeError, RuntimeError):
        return True


# ========================================================================================
# Render Engine Management
# ========================================================================================

def get_available_engines() -> List[str]:
    """Get available render engines."""
    try:
        return [e.identifier for e in 
                bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    except (AttributeError, KeyError):
        return ['BLENDER_WORKBENCH', 'BLENDER_EEVEE', 'CYCLES']


def choose_best_engine(preferences: List[str]) -> str:
    """Choose best available engine from preference list."""
    available = set(get_available_engines())
    
    for engine in preferences:
        if engine in available:
            return engine
    
    current = getattr(bpy.context.scene.render, "engine", None)
    if current and current in available:
        return current
    
    return next(iter(available)) if available else 'BLENDER_WORKBENCH'


def get_engine_for_shading(shading_type: str) -> str:
    """Get best engine for shading type."""
    preferences = constants.get_engine_preference_for_shading(shading_type)
    return choose_best_engine(preferences)


# ========================================================================================
# Window/Area/Region Finding
# ========================================================================================

def find_window_area_region(validate: bool = False) -> Tuple[Optional[object], ...]:
    """Find suitable window, screen, area, region."""
    wm = bpy.context.window_manager if bpy.context else None
    if not wm:
        return None, None, None, None
    
    # Try to find VIEW_3D
    for window in wm.windows:
        screen = window.screen
        if not screen:
            continue
        
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                if region:
                    return window, screen, area, region
    
    # Fallback to any area
    for window in wm.windows:
        screen = window.screen
        if screen and screen.areas:
            area = screen.areas[0]
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            if region:
                return window, screen, area, region
    
    # Last resort: use context
    return (
        bpy.context.window,
        bpy.context.window.screen if bpy.context.window else None,
        bpy.context.area,
        bpy.context.region
    )


# ========================================================================================
# Image Format Configuration
# ========================================================================================

def configure_image_format(scene, format_type: str, png_rgba: bool = False, 
                          jpeg_quality: int = 90):
    """Configure scene image format."""
    img = scene.render.image_settings
    
    if hasattr(img, 'media_type'):
        img.media_type = 'IMAGE'
    
    img.file_format = format_type
    
    if format_type == 'PNG':
        if hasattr(img, 'color_mode'):
            img.color_mode = 'RGBA' if png_rgba else 'RGB'
        if hasattr(img, 'compression'):
            img.compression = 15
    else:  # JPEG
        if hasattr(img, 'color_mode'):
            img.color_mode = 'RGB'
        if hasattr(img, 'quality'):
            img.quality = int(jpeg_quality)


# ========================================================================================
# Image Comparison (Simplified)
# ========================================================================================

def compare_images(path_a: str, path_b: str, downscale: int = 64, 
                  early_exit_threshold: Optional[float] = None) -> float:
    """
    Compare two images and return difference (0.0-1.0).
    
    Returns:
        Mean absolute difference
    """
    # Try PIL first (faster)
    try:
        from PIL import Image
        import numpy as np
        
        img_a = Image.open(bpy.path.abspath(path_a)).resize((downscale, downscale))
        img_b = Image.open(bpy.path.abspath(path_b)).resize((downscale, downscale))
        
        arr_a = np.array(img_a.convert('RGB'), dtype=np.float32) / 255.0
        arr_b = np.array(img_b.convert('RGB'), dtype=np.float32) / 255.0
        
        return float(np.abs(arr_a - arr_b).mean())
    
    except ImportError:
        # Fallback to Blender API
        return _compare_images_blender(path_a, path_b, downscale)


def _compare_images_blender(path_a: str, path_b: str, downscale: int) -> float:
    """Compare images using Blender API (fallback)."""
    img_a = img_b = None
    
    try:
        img_a = bpy.data.images.load(bpy.path.abspath(path_a), check_existing=False)
        img_b = bpy.data.images.load(bpy.path.abspath(path_b), check_existing=False)
        
        img_a.scale(downscale, downscale)
        img_b.scale(downscale, downscale)
        
        from array import array
        num_pixels = downscale * downscale * 4
        pixels_a = array('f', [0.0] * num_pixels)
        pixels_b = array('f', [0.0] * num_pixels)
        
        img_a.pixels.foreach_get(pixels_a)
        img_b.pixels.foreach_get(pixels_b)
        
        total_diff = sum(abs(pixels_a[i] - pixels_b[i]) 
                        for i in range(0, num_pixels, 4))  # Only check RGB
        
        return total_diff / (num_pixels // 4)
    
    except Exception as e:
        logger.error(f"Image comparison failed: {e}")
        return 1.0
    
    finally:
        for img in (img_a, img_b):
            if img:
                try:
                    bpy.data.images.remove(img, do_unlink=True)
                except:
                    pass


# ========================================================================================
# Freestyle Edge Marks
# ========================================================================================

def apply_freestyle_marks_visibility(enabled: bool):
    """Toggle freestyle edge marks visibility."""
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.data:
            if hasattr(obj.data, 'show_freestyle_edge_marks'):
                try:
                    obj.data.show_freestyle_edge_marks = enabled
                except (AttributeError, RuntimeError):
                    pass


# ========================================================================================
# Helper Functions
# ========================================================================================

def format_file_size(size_bytes: int) -> str:
    """Format bytes to human-readable."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def folder_has_images(path: str) -> bool:
    """Check if folder contains images."""
    try:
        return any(f.lower().endswith(constants.IMAGE_EXTENSIONS) 
                  for f in os.listdir(path))
    except (OSError, PermissionError):
        return False


def count_session_stats(directory: str) -> Tuple[int, int]:
    """Count images and total size in directory tree."""
    if not directory or not os.path.isdir(directory):
        return 0, 0
    
    count = total_size = 0
    
    try:
        for root, dirs, files in os.walk(directory):
            for filename in files:
                if filename.lower().endswith(constants.IMAGE_EXTENSIONS):
                    count += 1
                    try:
                        total_size += os.path.getsize(os.path.join(root, filename))
                    except OSError:
                        pass
    except (OSError, PermissionError):
        pass
    
    return count, total_size


# ========================================================================================
# Registration
# ========================================================================================

def register():
    """Register utils module."""
    logger.info("Utils module registered (Simplified - 50 lines validation)")


def unregister():
    """Unregister utils module."""
    logger.info("Utils module unregistered")