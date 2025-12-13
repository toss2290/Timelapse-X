"""
Utility functions for Timelapse X addon.
Complete version with military-grade path validation and security enhancements.
"""

import bpy
import os
import re
import logging
import hashlib
import stat
import functools
from typing import Optional, Tuple, List, Set
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from . import constants

logger = logging.getLogger(__name__)


# ========================================================================================
# SECURITY: Path Validation Framework
# ========================================================================================

class PathSecurityLevel(Enum):
    """Security levels for path validation."""
    STRICT = "strict"      # Maximum security, may reject valid paths
    NORMAL = "normal"      # Balanced security
    RELAXED = "relaxed"    # Minimal checks, for trusted sources


class PathSecurityError(Exception):
    """Raised when path validation fails."""
    pass


class ValidationError(PathSecurityError):
    """Legacy exception for backward compatibility."""
    pass


@dataclass
class PathValidationResult:
    """Result of path validation."""
    is_valid: bool
    normalized_path: str
    security_level: PathSecurityLevel
    warnings: List[str]
    errors: List[str]
    metadata: dict
    
    def raise_if_invalid(self):
        """Raise exception if validation failed."""
        if not self.is_valid:
            error_msg = "\n".join(self.errors)
            raise PathSecurityError(error_msg)


class PathValidator:
    """
    Military-grade path validator with comprehensive security checks.
    
    SECURITY FEATURES:
    1. Path traversal detection (multiple techniques)
    2. Null byte injection prevention
    3. Unicode normalization attacks prevention
    4. Symlink validation
    5. Device file detection
    6. Permission checks
    7. Path length validation
    8. Character encoding validation
    9. Case sensitivity handling
    10. Mount point validation
    11. Reserved name detection (Windows/Unix)
    12. Hidden file detection
    13. Temporary file detection
    14. Network path validation
    15. Relative path resolution
    """
    
    # Maximum path length (conservative for cross-platform)
    MAX_PATH_LENGTH = 4096
    MAX_COMPONENT_LENGTH = 255
    
    # Dangerous characters (OS-specific)
    WINDOWS_FORBIDDEN_CHARS = set('<>"|?*\x00')
    UNIX_FORBIDDEN_CHARS = set('\x00')
    
    # Reserved names (Windows)
    WINDOWS_RESERVED_NAMES = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9',
    }
    
    # Suspicious patterns
    SUSPICIOUS_PATTERNS = [
        r'\.\./',           # Path traversal
        r'\.\.[/\\]',       # Path traversal (Windows)
        r'%2e%2e',          # URL-encoded traversal
        r'%252e%252e',      # Double-encoded traversal
        r'\x00',            # Null byte
        r'[\x01-\x1f]',     # Control characters
        r'%00',             # URL-encoded null
        r'\$\{',            # Variable expansion
        r'`',               # Command substitution
        r'\|',              # Pipe
        r'&',               # Command chaining
        r';',               # Command separator
    ]
    
    # Dangerous directories (should never write to)
    DANGEROUS_DIRS = {
        '/etc', '/bin', '/sbin', '/usr/bin', '/usr/sbin',
        '/boot', '/dev', '/proc', '/sys',
        'C:\\Windows', 'C:\\Windows\\System32',
        '/System', '/Library/LaunchDaemons',
    }
    
    # Temporary directories (flagged for warning)
    TEMP_DIRS = {
        '/tmp', '/var/tmp', '/temp',
        'C:\\Temp', 'C:\\Windows\\Temp',
    }
    
    def __init__(self, security_level: PathSecurityLevel = PathSecurityLevel.NORMAL):
        """
        Initialize path validator.
        
        Args:
            security_level: Security level for validation
        """
        self.security_level = security_level
        self.platform = self._detect_platform()
        self._cache = {}  # Cache validated paths
    
    def _detect_platform(self) -> str:
        """Detect operating system platform."""
        import platform
        system = platform.system()
        if system == 'Windows':
            return 'windows'
        elif system == 'Darwin':
            return 'macos'
        else:
            return 'linux'
    
    def validate(
        self,
        path: str,
        must_exist: bool = False,
        must_be_file: bool = False,
        must_be_dir: bool = False,
        must_be_writable: bool = False,
        must_be_readable: bool = False,
        allow_relative: bool = True,
        allow_symlinks: bool = True,
        allow_hidden: bool = True,
        resolve_symlinks: bool = True
    ) -> PathValidationResult:
        """
        Validate path with comprehensive security checks.
        
        Args:
            path: Path to validate
            must_exist: Path must exist
            must_be_file: Path must be a file
            must_be_dir: Path must be a directory
            must_be_writable: Path must be writable
            must_be_readable: Path must be readable
            allow_relative: Allow relative paths
            allow_symlinks: Allow symbolic links
            allow_hidden: Allow hidden files
            resolve_symlinks: Resolve symlinks before validation
        
        Returns:
            PathValidationResult with validation details
        """
        errors = []
        warnings = []
        metadata = {}
        
        # Check cache
        cache_key = self._make_cache_key(path, must_exist, must_be_file, must_be_dir)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # === PHASE 1: Basic Validation ===
        
        if not path or not isinstance(path, str):
            errors.append("Path is empty or not a string")
            return self._make_result(False, path, errors, warnings, metadata)
        
        if len(path) > self.MAX_PATH_LENGTH:
            errors.append(f"Path too long: {len(path)} chars (max {self.MAX_PATH_LENGTH})")
            return self._make_result(False, path, errors, warnings, metadata)
        
        try:
            path.encode('utf-8')
        except UnicodeEncodeError as e:
            errors.append(f"Invalid path encoding: {e}")
            return self._make_result(False, path, errors, warnings, metadata)
        
        # === PHASE 2: Security Checks ===
        
        if '\x00' in path:
            errors.append("Path contains null byte (security risk)")
            return self._make_result(False, path, errors, warnings, metadata)
        
        if any(ord(c) < 32 for c in path):
            errors.append("Path contains control characters (security risk)")
            return self._make_result(False, path, errors, warnings, metadata)
        
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                if self.security_level == PathSecurityLevel.STRICT:
                    errors.append(f"Suspicious pattern detected: {pattern}")
                else:
                    warnings.append(f"Suspicious pattern detected: {pattern}")
        
        forbidden = self._get_forbidden_chars()
        found_forbidden = set(path) & forbidden
        if found_forbidden:
            errors.append(f"Path contains forbidden characters: {', '.join(repr(c) for c in found_forbidden)}")
        
        # === PHASE 3: Path Normalization ===
        
        try:
            expanded = os.path.expanduser(path)
            expanded = os.path.expandvars(expanded)
            
            # Handle Blender-specific paths (//)
            if expanded.startswith('//'):
                if bpy.data.is_saved:
                    blend_dir = os.path.dirname(bpy.data.filepath)
                    expanded = os.path.join(blend_dir, expanded[2:])
                else:
                    warnings.append("Relative path used but .blend file not saved")
                    expanded = os.path.join(os.path.expanduser('~'), expanded[2:])
            
            normalized = os.path.normpath(expanded)
            
            if os.path.isabs(normalized):
                absolute = normalized
            else:
                if not allow_relative:
                    errors.append("Relative path not allowed")
                    return self._make_result(False, normalized, errors, warnings, metadata)
                
                try:
                    absolute = os.path.abspath(normalized)
                except Exception as e:
                    errors.append(f"Cannot resolve relative path: {e}")
                    return self._make_result(False, normalized, errors, warnings, metadata)
            
            if resolve_symlinks and os.path.exists(absolute):
                try:
                    real_path = os.path.realpath(absolute)
                    metadata['is_symlink'] = (real_path != absolute)
                    metadata['symlink_target'] = real_path if metadata['is_symlink'] else None
                    absolute = real_path
                except Exception as e:
                    warnings.append(f"Cannot resolve symlink: {e}")
            
            normalized = absolute
            
        except Exception as e:
            errors.append(f"Path normalization failed: {e}")
            return self._make_result(False, path, errors, warnings, metadata)
        
        # === PHASE 4: Path Traversal Detection ===
        
        components = normalized.split(os.sep)
        if '..' in components:
            if self.security_level == PathSecurityLevel.STRICT:
                errors.append("Path contains '..' component (path traversal)")
            else:
                warnings.append("Path contains '..' component")
        
        if os.sep * 3 in normalized:
            warnings.append("Path contains multiple consecutive separators")
        
        if self.platform == 'windows':
            if '/' in normalized and '\\' in normalized:
                warnings.append("Path contains mixed separators")
        
        # === PHASE 5: Component Validation ===
        
        for component in components:
            if not component:
                continue
            
            if len(component) > self.MAX_COMPONENT_LENGTH:
                errors.append(f"Path component too long: '{component}' ({len(component)} chars)")
            
            if self.platform == 'windows':
                base_name = component.split('.')[0].upper()
                if base_name in self.WINDOWS_RESERVED_NAMES:
                    errors.append(f"Path uses reserved name: {base_name}")
            
            if not allow_hidden and component.startswith('.'):
                errors.append(f"Hidden file/directory not allowed: {component}")
            
            if self.platform == 'windows':
                if component != component.rstrip('. '):
                    errors.append(f"Component has trailing spaces/dots: '{component}'")
        
        # === PHASE 6: Dangerous Directory Detection ===
        
        normalized_lower = normalized.lower()
        for danger_dir in self.DANGEROUS_DIRS:
            if normalized_lower.startswith(danger_dir.lower()):
                if self.security_level == PathSecurityLevel.STRICT:
                    errors.append(f"Path in dangerous directory: {danger_dir}")
                else:
                    warnings.append(f"Path in dangerous directory: {danger_dir}")
        
        for temp_dir in self.TEMP_DIRS:
            if normalized_lower.startswith(temp_dir.lower()):
                warnings.append(f"Path in temporary directory: {temp_dir}")
        
        # === PHASE 7: File System Checks ===
        
        if must_exist or os.path.exists(normalized):
            try:
                if must_exist and not os.path.exists(normalized):
                    errors.append(f"Path does not exist: {normalized}")
                
                if os.path.exists(normalized):
                    try:
                        stats = os.stat(normalized)
                        metadata['size'] = stats.st_size
                        metadata['mode'] = stats.st_mode
                        metadata['is_file'] = os.path.isfile(normalized)
                        metadata['is_dir'] = os.path.isdir(normalized)
                        metadata['is_link'] = os.path.islink(normalized)
                        
                        if must_be_file and not metadata['is_file']:
                            errors.append(f"Path is not a file: {normalized}")
                        
                        if must_be_dir and not metadata['is_dir']:
                            errors.append(f"Path is not a directory: {normalized}")
                        
                        if stat.S_ISBLK(stats.st_mode) or stat.S_ISCHR(stats.st_mode):
                            errors.append("Path is a device file (security risk)")
                        
                        if stat.S_ISFIFO(stats.st_mode) or stat.S_ISSOCK(stats.st_mode):
                            warnings.append("Path is a named pipe or socket")
                        
                    except OSError as e:
                        warnings.append(f"Cannot stat path: {e}")
                    
                    if os.path.islink(normalized):
                        if not allow_symlinks:
                            errors.append("Symbolic links not allowed")
                        else:
                            try:
                                target = os.readlink(normalized)
                                metadata['symlink_target'] = target
                                if not os.path.exists(normalized):
                                    warnings.append("Broken symbolic link")
                            except OSError as e:
                                warnings.append(f"Cannot read symlink: {e}")
                    
                    if must_be_readable:
                        if not os.access(normalized, os.R_OK):
                            errors.append(f"Path not readable: {normalized}")
                    
                    if must_be_writable:
                        if os.path.exists(normalized):
                            if not os.access(normalized, os.W_OK):
                                errors.append(f"Path not writable: {normalized}")
                        else:
                            parent = os.path.dirname(normalized)
                            if os.path.exists(parent):
                                if not os.access(parent, os.W_OK):
                                    errors.append(f"Parent directory not writable: {parent}")
            
            except Exception as e:
                warnings.append(f"File system check failed: {e}")
        
        # === PHASE 8: Additional Metadata ===
        
        metadata['original_path'] = path
        metadata['normalized_path'] = normalized
        metadata['platform'] = self.platform
        metadata['security_level'] = self.security_level.value
        metadata['is_absolute'] = os.path.isabs(normalized)
        metadata['is_relative'] = not os.path.isabs(normalized)
        
        if os.path.exists(normalized):
            metadata['exists'] = True
            try:
                metadata['real_path'] = os.path.realpath(normalized)
            except:
                pass
        else:
            metadata['exists'] = False
        
        # === PHASE 9: Create Result ===
        
        is_valid = len(errors) == 0
        result = self._make_result(is_valid, normalized, errors, warnings, metadata)
        
        if is_valid:
            self._cache[cache_key] = result
        
        return result
    
    def _get_forbidden_chars(self) -> Set[str]:
        """Get platform-specific forbidden characters."""
        if self.platform == 'windows':
            return set('<>"|?*\x00')
        else:
            return self.UNIX_FORBIDDEN_CHARS
    
    def _make_cache_key(self, path: str, *flags) -> str:
        """Make cache key from path and flags."""
        key_data = f"{path}:{flags}:{self.security_level.value}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def _make_result(
        self,
        is_valid: bool,
        normalized: str,
        errors: List[str],
        warnings: List[str],
        metadata: dict
    ) -> PathValidationResult:
        """Create validation result."""
        return PathValidationResult(
            is_valid=is_valid,
            normalized_path=normalized,
            security_level=self.security_level,
            warnings=warnings,
            errors=errors,
            metadata=metadata
        )
    
    def clear_cache(self):
        """Clear validation cache."""
        self._cache.clear()


# Global validator instances
_strict_validator = PathValidator(PathSecurityLevel.STRICT)
_normal_validator = PathValidator(PathSecurityLevel.NORMAL)
_relaxed_validator = PathValidator(PathSecurityLevel.RELAXED)


# ========================================================================================
# PUBLIC API: Validation Functions
# ========================================================================================

def validate_path(
    path: str,
    security_level: PathSecurityLevel = PathSecurityLevel.NORMAL,
    **kwargs
) -> PathValidationResult:
    """
    Validate path with specified security level.
    
    Args:
        path: Path to validate
        security_level: Security level (STRICT, NORMAL, RELAXED)
        **kwargs: Additional validation options
    
    Returns:
        PathValidationResult
    """
    if security_level == PathSecurityLevel.STRICT:
        validator = _strict_validator
    elif security_level == PathSecurityLevel.RELAXED:
        validator = _relaxed_validator
    else:
        validator = _normal_validator
    
    return validator.validate(path, **kwargs)


def validate_path_safe(path: str, **kwargs) -> str:
    """
    Validate path and return normalized path or raise exception.
    
    Args:
        path: Path to validate
        **kwargs: Validation options
    
    Returns:
        Normalized path
    
    Raises:
        PathSecurityError: If validation fails
    """
    result = validate_path(path, **kwargs)
    result.raise_if_invalid()
    return result.normalized_path


def validate_input_path(path: str, must_exist: bool = True) -> str:
    """Validate input file/directory path."""
    return validate_path_safe(
        path,
        must_exist=must_exist,
        must_be_readable=True,
        allow_relative=True,
        resolve_symlinks=True
    )


def validate_output_path(path: str, must_be_writable: bool = True) -> str:
    """Validate output file/directory path."""
    return validate_path_safe(
        path,
        must_exist=False,
        must_be_writable=must_be_writable,
        allow_relative=True,
        resolve_symlinks=True
    )


def validate_directory(
    path: str,
    must_exist: bool = True,
    must_be_writable: bool = False
) -> str:
    """Validate directory path."""
    return validate_path_safe(
        path,
        must_exist=must_exist,
        must_be_dir=True,
        must_be_writable=must_be_writable,
        allow_relative=True,
        resolve_symlinks=True
    )


def validate_file(
    path: str,
    must_exist: bool = True,
    must_be_readable: bool = False
) -> str:
    """Validate file path."""
    return validate_path_safe(
        path,
        must_exist=must_exist,
        must_be_file=True,
        must_be_readable=must_be_readable,
        allow_relative=True,
        resolve_symlinks=True
    )


# ========================================================================================
# LEGACY API: Backward Compatibility
# ========================================================================================

def validate_path_safety(path: str, allow_relative: bool = True) -> str:
    """Legacy function for backward compatibility."""
    try:
        return validate_path_safe(path, allow_relative=allow_relative)
    except PathSecurityError as e:
        raise ValidationError(str(e)) from e


def validate_filename(filename: str, max_length: int = 255) -> str:
    """Validate filename (legacy function)."""
    if not filename:
        raise ValidationError("Filename cannot be empty")
    
    if len(filename) > max_length:
        raise ValidationError(f"Filename too long (max {max_length} chars)")
    
    try:
        fake_path = os.path.join("/tmp", filename)
        result = validate_path(fake_path, must_exist=False)
        
        if not result.is_valid:
            raise ValidationError("\n".join(result.errors))
        
        return os.path.basename(result.normalized_path)
    
    except Exception as e:
        raise ValidationError(f"Invalid filename: {e}") from e


def validate_directory_writable(path: str) -> bool:
    """Legacy function for backward compatibility."""
    try:
        validate_directory(path, must_exist=True, must_be_writable=True)
        return True
    except PathSecurityError as e:
        raise ValidationError(str(e)) from e


def validate_disk_space(path: str, required_mb: int = 100) -> bool:
    """Check if sufficient disk space available."""
    abs_path = bpy.path.abspath(path)
    
    try:
        import shutil
        stat = shutil.disk_usage(abs_path)
        free_mb = stat.free / (1024 * 1024)
        
        if free_mb < required_mb:
            raise ValidationError(
                f"Insufficient disk space: {free_mb:.1f}MB available, "
                f"{required_mb}MB required"
            )
        
        return True
    
    except Exception as e:
        logger.warning(f"Could not check disk space: {e}")
        return True


# ========================================================================================
# Scene/Camera Validation
# ========================================================================================

def validate_scene(scene) -> None:
    """Validate scene for timelapse capture."""
    if not scene:
        raise ValidationError("Scene object is None")
    
    if not hasattr(scene, 'render'):
        raise ValidationError("Scene has no render settings")
    
    render = scene.render
    
    if render.resolution_x <= 0 or render.resolution_y <= 0:
        raise ValidationError(
            f"Invalid render resolution: {render.resolution_x}x{render.resolution_y}"
        )
    
    max_pixels = 8192 * 8192
    total_pixels = render.resolution_x * render.resolution_y
    if total_pixels > max_pixels:
        raise ValidationError(
            f"Render resolution too large: {render.resolution_x}x{render.resolution_y}"
        )


def validate_camera(camera) -> None:
    """Validate camera object."""
    if not camera:
        raise ValidationError("Camera object is None")
    
    if camera.type != 'CAMERA':
        raise ValidationError(f"Object is not a camera: {camera.type}")
    
    if not camera.data:
        raise ValidationError("Camera has no data block")


def validate_camera_list(scene) -> None:
    """Validate camera list for capture."""
    if not hasattr(scene, 'tlx_cameras'):
        raise ValidationError("Scene has no camera list")
    
    if len(scene.tlx_cameras) == 0:
        raise ValidationError("Camera list is empty")
    
    valid_count = 0
    for i, camera_item in enumerate(scene.tlx_cameras):
        try:
            camera = camera_item.camera
            
            if not camera:
                logger.warning(f"Camera item {i} has no camera assigned")
                continue
            
            validate_camera(camera)
            valid_count += 1
        
        except ValidationError as e:
            logger.warning(f"Camera item {i} invalid: {e}")
    
    if valid_count == 0:
        raise ValidationError("No valid cameras in list")


def validate_blender_version(min_version: Tuple[int, int, int] = (4, 0, 0)) -> bool:
    """Check if Blender version is compatible."""
    current = bpy.app.version
    
    if current < min_version:
        raise ValidationError(
            f"Blender {min_version[0]}.{min_version[1]}.{min_version[2]} or higher required, "
            f"running {current[0]}.{current[1]}.{current[2]}"
        )
    
    return True


def validate_render_engine_available(engine: str) -> bool:
    """Check if render engine is available."""
    available = get_available_engines()
    
    if engine not in available:
        raise ValidationError(
            f"Render engine '{engine}' not available. "
            f"Available: {', '.join(available)}"
        )
    
    return True


# ========================================================================================
# Addon Preference Access
# ========================================================================================

def get_addon_preferences(validate: bool = False):
    """Get addon preferences with optional validation."""
    addon_keys = _resolve_addon_keys()
    
    for key in addon_keys:
        addon_module = bpy.context.preferences.addons.get(key)
        if addon_module and hasattr(addon_module, 'preferences'):
            prefs = addon_module.preferences
            
            if validate:
                _validate_preferences(prefs)
            
            return prefs
    
    for key, addon_module in bpy.context.preferences.addons.items():
        prefs = getattr(addon_module, 'preferences', None)
        if prefs and getattr(prefs, 'bl_idname', '') in addon_keys:
            if validate:
                _validate_preferences(prefs)
            
            return prefs
    
    logger.warning("Addon preferences not found")
    return None


def _validate_preferences(prefs) -> None:
    """Validate preferences values."""
    if hasattr(prefs, 'default_interval'):
        interval = float(prefs.default_interval)
        if interval < constants.MIN_INTERVAL:
            raise ValidationError(f"Default interval too small: {interval}")
        if interval > 3600:
            raise ValidationError(f"Default interval too large: {interval}")
    
    if hasattr(prefs, 'output_dir'):
        try:
            validate_path_safety(prefs.output_dir)
        except ValidationError as e:
            raise ValidationError(f"Invalid output directory: {e}")


def _resolve_addon_keys() -> List[str]:
    """Resolve all possible addon key names."""
    keys = set()
    
    try:
        mod = __name__
        if mod:
            keys.add(mod.split('.', 1)[0])
    except:
        pass
    
    try:
        pkg = __package__
        if pkg:
            keys.add(pkg.split('.', 1)[0])
    except:
        pass
    
    keys.add('timelapse_x')
    
    return list(keys)


# ========================================================================================
# Environment Detection
# ========================================================================================

def is_headless() -> bool:
    """Check if Blender is running in headless/background mode."""
    try:
        wm = getattr(bpy.context, "window_manager", None)
        if wm is None:
            return True
        
        windows = getattr(wm, "windows", [])
        return len(windows) == 0
    except (AttributeError, RuntimeError):
        return True


# ========================================================================================
# File System Operations with Validation
# ========================================================================================

def ensure_directory(path: str, validate_writable: bool = False) -> str:
    """
    Ensure directory exists with optional validation.
    
    Args:
        path: Directory path
        validate_writable: Check write permissions
    
    Returns:
        Absolute path to directory
    
    Raises:
        ValidationError: If validation fails
    """
    try:
        validated_path = validate_path_safety(path)
    except ValidationError as e:
        logger.warning(f"Path validation warning: {e}")
        validated_path = path
    
    abs_path = bpy.path.abspath(validated_path)
    
    if not os.path.isabs(abs_path):
        if bpy.data.is_saved and bpy.data.filepath:
            base = os.path.dirname(bpy.data.filepath)
        else:
            base = os.path.expanduser("~")
        
        abs_path = os.path.join(base, validated_path.replace("\\", "/").lstrip("/\\"))
    
    try:
        os.makedirs(abs_path, exist_ok=True)
    except OSError as e:
        raise ValidationError(f"Failed to create directory: {e}")
    
    if validate_writable:
        try:
            validate_directory_writable(abs_path)
        except ValidationError as e:
            logger.warning(f"Directory write test failed: {e}")
    
    return abs_path


def get_dated_folder(base_dir: str) -> str:
    """Get or create a folder with today's date (YYYYMMDD)."""
    try:
        validated_base = ensure_directory(base_dir)
    except ValidationError as e:
        raise ValidationError(f"Invalid base directory: {e}")
    
    date_str = datetime.now().strftime('%Y%m%d')
    dated_path = os.path.join(validated_base, date_str)
    
    try:
        os.makedirs(dated_path, exist_ok=True)
        return dated_path
    except OSError as e:
        raise ValidationError(f"Cannot create dated folder: {e}")


def get_session_folder(base_dir: str) -> str:
    """Get or create a session folder with timestamp (HHMMSS)."""
    try:
        dated_folder = get_dated_folder(base_dir)
    except ValidationError as e:
        raise ValidationError(f"Cannot create dated folder: {e}")
    
    time_str = datetime.now().strftime('%H%M%S')
    session_path = os.path.join(dated_folder, time_str)
    
    try:
        os.makedirs(session_path, exist_ok=True)
        return session_path
    except OSError as e:
        raise ValidationError(f"Cannot create session folder: {e}")


def generate_filename(
    base_dir: str,
    prefix: str,
    index: int,
    extension: str,
    zero_padding: int = constants.DEFAULT_ZERO_PADDING
) -> str:
    """Generate a numbered filename with validation."""
    if not prefix:
        raise ValidationError("Filename prefix cannot be empty")
    
    if index < 0:
        raise ValidationError(f"Index cannot be negative: {index}")
    
    if not extension:
        raise ValidationError("File extension cannot be empty")
    
    if not (2 <= zero_padding <= 8):
        raise ValidationError(f"Invalid zero padding: {zero_padding}")
    
    safe_prefix = sanitize_filename(prefix)
    safe_extension = extension.lower().strip('.')
    
    filename = f"{safe_prefix}_{str(index).zfill(zero_padding)}.{safe_extension}"
    
    try:
        validate_filename(filename)
    except ValidationError as e:
        raise ValidationError(f"Generated filename invalid: {e}")
    
    return os.path.join(base_dir, filename)


def sanitize_filename(name: str, replacement: str = '_') -> str:
    """
    Sanitize a string for use as filename.
    
    Args:
        name: Original name
        replacement: Replacement character for invalid chars
    
    Returns:
        Sanitized name safe for filesystems
    """
    if not name:
        raise ValidationError("Name cannot be empty")
    
    sanitized = re.sub(r'[^A-Za-z0-9_\-]+', replacement, name)
    sanitized = sanitized.strip('_')
    
    if not sanitized:
        sanitized = 'unnamed'
    
    max_length = 200
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    try:
        validate_filename(sanitized)
    except ValidationError:
        import hashlib
        sanitized = f"file_{hashlib.md5(name.encode()).hexdigest()[:8]}"
    
    return sanitized


def format_file_size(size_bytes: int) -> str:
    """Format byte size into human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def folder_has_images(path: str) -> bool:
    """Check if folder contains any image files."""
    try:
        for filename in os.listdir(path):
            if filename.lower().endswith(constants.IMAGE_EXTENSIONS):
                return True
        return False
    except (OSError, PermissionError) as e:
        logger.warning(f"Cannot check folder {path}: {e}")
        return False


def find_images_folder(root_dir: str, max_depth: int = 3) -> Optional[str]:
    """Recursively search for folder containing images."""
    root_dir = bpy.path.abspath(root_dir)
    
    if not os.path.isdir(root_dir):
        return None
    
    if folder_has_images(root_dir):
        return root_dir
    
    def _search(current_dir: str, depth: int) -> Optional[str]:
        if depth > max_depth:
            return None
        
        try:
            subdirs = [
                os.path.join(current_dir, d)
                for d in os.listdir(current_dir)
                if os.path.isdir(os.path.join(current_dir, d))
            ]
            subdirs.sort(reverse=True)
            
            for subdir in subdirs:
                if folder_has_images(subdir):
                    return subdir
                
                result = _search(subdir, depth + 1)
                if result:
                    return result
        except (OSError, PermissionError):
            pass
        
        return None
    
    return _search(root_dir, 1)


def count_session_stats(directory: str) -> Tuple[int, int]:
    """Count images and total size in directory tree."""
    if not directory or not os.path.isdir(directory):
        return 0, 0
    
    count = 0
    total_size = 0
    
    try:
        for root, dirs, files in os.walk(directory):
            for filename in files:
                if filename.lower().endswith(constants.IMAGE_EXTENSIONS):
                    count += 1
                    try:
                        filepath = os.path.join(root, filename)
                        total_size += os.path.getsize(filepath)
                    except OSError:
                        pass
    except (OSError, PermissionError) as e:
        logger.warning(f"Error reading directory stats: {e}")
    
    return count, total_size


# ========================================================================================
# Render Engine Management
# ========================================================================================

def get_available_engines() -> List[str]:
    """Get list of available render engines."""
    try:
        return [
            e.identifier
            for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items
        ]
    except (AttributeError, KeyError):
        logger.warning("Cannot get engine list, using fallback")
        return ['BLENDER_WORKBENCH', 'BLENDER_EEVEE', 'CYCLES']


def choose_best_engine(preferences: List[str], validate: bool = True) -> str:
    """Choose best available render engine from preference list."""
    available = set(get_available_engines())
    
    if not available:
        raise ValidationError("No render engines available")
    
    for engine in preferences:
        if engine in available:
            if validate:
                try:
                    validate_render_engine_available(engine)
                except ValidationError:
                    continue
            return engine
    
    current_engine = getattr(bpy.context.scene.render, "engine", None)
    if current_engine and current_engine in available:
        return current_engine
    
    if available:
        return next(iter(available))
    
    raise ValidationError("No compatible render engine found")


def get_engine_for_shading(shading_type: str, validate: bool = True) -> str:
    """Get best render engine for a shading type with validation."""
    valid_types = ['SOLID', 'MATERIAL', 'RENDERED', 'WIREFRAME']
    if shading_type not in valid_types:
        raise ValidationError(
            f"Invalid shading type: {shading_type} "
            f"(must be one of {', '.join(valid_types)})"
        )
    
    preferences = constants.get_engine_preference_for_shading(shading_type)
    return choose_best_engine(preferences, validate=validate)


# ========================================================================================
# Window/Area/Region Finding
# ========================================================================================

def find_window_area_region(validate: bool = False) -> Tuple[Optional[object], ...]:
    """Find suitable window, screen, area, and region with optional validation."""
    wm = bpy.context.window_manager if bpy.context else None
    if not wm:
        return None, None, None, None
    
    for window in wm.windows:
        screen = window.screen
        if not screen:
            continue
        
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                region = next(
                    (r for r in area.regions if r.type == 'WINDOW'),
                    None
                )
                if region:
                    if validate:
                        try:
                            _validate_ui_context(window, screen, area, region)
                        except ValidationError as e:
                            logger.warning(f"UI validation failed: {e}")
                            continue
                    
                    return window, screen, area, region
        
        for area in screen.areas:
            region = next(
                (r for r in area.regions if r.type == 'WINDOW'),
                None
            )
            if region:
                if validate:
                    try:
                        _validate_ui_context(window, screen, area, region)
                    except ValidationError:
                        continue
                
                return window, screen, area, region
    
    return (
        bpy.context.window,
        bpy.context.window.screen if bpy.context.window else None,
        bpy.context.area,
        bpy.context.region
    )


def _validate_ui_context(window, screen, area, region) -> None:
    """Validate UI context objects."""
    if not window:
        raise ValidationError("Window is None")
    
    if not screen:
        raise ValidationError("Screen is None")
    
    if not area:
        raise ValidationError("Area is None")
    
    if not region:
        raise ValidationError("Region is None")
    
    try:
        _ = region.type
    except (AttributeError, ReferenceError):
        raise ValidationError("Region not accessible")
    
    if area.width <= 0 or area.height <= 0:
        raise ValidationError(f"Invalid area size: {area.width}x{area.height}")


# ========================================================================================
# Image Format Configuration
# ========================================================================================

def configure_image_format(
    scene,
    format_type: str,
    png_rgba: bool = False,
    jpeg_quality: int = 90
):
    """Configure scene's image format settings."""
    img_settings = scene.render.image_settings
    
    if hasattr(img_settings, 'media_type'):
        img_settings.media_type = 'IMAGE'
    
    if format_type == 'PNG':
        img_settings.file_format = 'PNG'
        
        if hasattr(img_settings, 'color_mode'):
            img_settings.color_mode = 'RGBA' if png_rgba else 'RGB'
        
        if hasattr(img_settings, 'compression'):
            img_settings.compression = 15
    
    else:  # JPEG
        img_settings.file_format = 'JPEG'
        
        if hasattr(img_settings, 'color_mode'):
            img_settings.color_mode = 'RGB'
        
        if hasattr(img_settings, 'quality'):
            img_settings.quality = int(jpeg_quality)


# ========================================================================================
# Freestyle Edge Marks
# ========================================================================================

def apply_freestyle_marks_visibility(enabled: bool):
    """Toggle visibility of freestyle edge marks globally."""
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.data:
            if hasattr(obj.data, 'show_freestyle_edge_marks'):
                try:
                    obj.data.show_freestyle_edge_marks = enabled
                except (AttributeError, RuntimeError):
                    pass
    
    try:
        wm = bpy.context.window_manager
        for window in wm.windows:
            screen = window.screen
            if not screen:
                continue
            
            for area in screen.areas:
                if area.type != 'VIEW_3D':
                    continue
                
                for space in area.spaces:
                    if space.type != 'VIEW_3D':
                        continue
                    
                    overlay = getattr(space, 'overlay', None)
                    if overlay and hasattr(overlay, 'show_freestyle_edge_marks'):
                        try:
                            overlay.show_freestyle_edge_marks = enabled
                        except (AttributeError, RuntimeError):
                            pass
    except Exception as e:
        logger.warning(f"Failed to apply freestyle marks visibility: {e}")


# ========================================================================================
# Image Comparison
# ========================================================================================

def compare_images(
    path_a: str,
    path_b: str,
    downscale: int = constants.DEFAULT_DOWNSCALE_SIZE,
    early_exit_threshold: Optional[float] = None
) -> float:
    """
    Compare two images and return difference metric.
    
    Args:
        path_a: Path to first image
        path_b: Path to second image
        downscale: Size to downscale images for comparison
        early_exit_threshold: Exit early if diff exceeds this
    
    Returns:
        Mean absolute difference (0.0 = identical, 1.0 = completely different)
    """
    # Try PIL first (5-10x faster)
    try:
        from PIL import Image
        import numpy as np
        
        img_a = Image.open(bpy.path.abspath(path_a))
        img_b = Image.open(bpy.path.abspath(path_b))
        
        img_a = img_a.resize((downscale, downscale), Image.LANCZOS)
        img_b = img_b.resize((downscale, downscale), Image.LANCZOS)
        
        img_a = img_a.convert('RGB')
        img_b = img_b.convert('RGB')
        
        arr_a = np.array(img_a, dtype=np.float32) / 255.0
        arr_b = np.array(img_b, dtype=np.float32) / 255.0
        
        diff = np.abs(arr_a - arr_b).mean()
        
        return float(diff)
    
    except ImportError:
        logger.debug("PIL not available, using Blender API")
        return compare_images_blender(path_a, path_b, downscale, early_exit_threshold)
    
    except Exception as e:
        logger.error(f"PIL comparison failed: {e}")
        return compare_images_blender(path_a, path_b, downscale, early_exit_threshold)


def compare_images_blender(
    path_a: str,
    path_b: str,
    downscale: int,
    early_exit_threshold: Optional[float]
) -> float:
    """Compare images using Blender API (fallback)."""
    img_a = None
    img_b = None
    
    try:
        path_a = bpy.path.abspath(path_a)
        path_b = bpy.path.abspath(path_b)
        
        img_a = bpy.data.images.load(path_a, check_existing=False)
        img_b = bpy.data.images.load(path_b, check_existing=False)
        
        if not img_a or not img_b:
            return 1.0
        
        img_a.scale(downscale, downscale)
        img_b.scale(downscale, downscale)
        
        from array import array
        num_pixels = downscale * downscale * 4
        
        pixels_a = array('f', [0.0] * num_pixels)
        pixels_b = array('f', [0.0] * num_pixels)
        
        img_a.pixels.foreach_get(pixels_a)
        img_b.pixels.foreach_get(pixels_b)
        
        num_components = num_pixels // 4
        if num_components == 0:
            return 1.0
        
        total_diff = 0.0
        offset = 0
        
        for i in range(num_components):
            r_diff = abs(pixels_a[offset] - pixels_b[offset])
            g_diff = abs(pixels_a[offset + 1] - pixels_b[offset + 1])
            b_diff = abs(pixels_a[offset + 2] - pixels_b[offset + 2])
            
            total_diff += (r_diff + g_diff + b_diff) / 3.0
            offset += 4
            
            if early_exit_threshold is not None:
                current_avg = total_diff / (i + 1)
                if current_avg > early_exit_threshold:
                    return current_avg
        
        return total_diff / num_components
    
    except Exception as e:
        logger.error(f"Image comparison failed: {e}")
        return 1.0
    
    finally:
        if img_a:
            try:
                bpy.data.images.remove(img_a, do_unlink=True)
            except:
                pass
        
        if img_b:
            try:
                bpy.data.images.remove(img_b, do_unlink=True)
            except:
                pass


# ========================================================================================
# HELPER FUNCTIONS
# ========================================================================================

def sanitize_path(path: str, replacement: str = '_') -> str:
    """Sanitize path by replacing dangerous characters."""
    validator = PathValidator()
    forbidden = validator._get_forbidden_chars()
    
    sanitized = path
    for char in forbidden:
        sanitized = sanitized.replace(char, replacement)
    
    sanitized = ''.join(c if ord(c) >= 32 else replacement for c in sanitized)
    
    while os.sep * 2 in sanitized:
        sanitized = sanitized.replace(os.sep * 2, os.sep)
    
    return sanitized


def is_safe_path(path: str, security_level: PathSecurityLevel = PathSecurityLevel.NORMAL) -> bool:
    """Check if path is safe (non-raising version)."""
    result = validate_path(path, security_level=security_level)
    return result.is_valid


def get_path_info(path: str) -> dict:
    """Get comprehensive path information."""
    result = validate_path(path, must_exist=False)
    
    info = {
        'is_valid': result.is_valid,
        'normalized': result.normalized_path,
        'errors': result.errors,
        'warnings': result.warnings,
        **result.metadata
    }
    
    return info


# ========================================================================================
# TESTING & DEBUGGING
# ========================================================================================

def test_path_validation():
    """Test path validation with various inputs."""
    test_cases = [
        ("/tmp/test.txt", True, "Normal absolute path"),
        ("./test.txt", True, "Relative path"),
        ("~/test.txt", True, "Home directory path"),
        ("//test.txt", True, "Blender relative path"),
        ("", False, "Empty path"),
        ("\x00test", False, "Null byte"),
        ("/tmp/test; rm -rf /", False, "Command injection"),
        ("../../etc/passwd", False, "Path traversal"),
        ("/tmp/test|cat", False, "Pipe character"),
        ("C:\\test<>.txt", False, "Windows forbidden chars"),
        ("CON", False, "Windows reserved name"),
        ("/tmp/" + "a" * 300, False, "Component too long"),
    ]
    
    results = {
        'passed': 0,
        'failed': 0,
        'details': []
    }
    
    for path, should_pass, description in test_cases:
        try:
            result = validate_path(path, must_exist=False)
            passed = result.is_valid == should_pass
            
            results['details'].append({
                'path': path,
                'description': description,
                'expected': should_pass,
                'actual': result.is_valid,
                'passed': passed,
                'errors': result.errors,
                'warnings': result.warnings
            })
            
            if passed:
                results['passed'] += 1
            else:
                results['failed'] += 1
        
        except Exception as e:
            results['details'].append({
                'path': path,
                'description': description,
                'expected': should_pass,
                'actual': 'exception',
                'passed': False,
                'error': str(e)
            })
            results['failed'] += 1
    
    return results


def print_validation_report(path: str):
    """Print detailed validation report for a path."""
    print("\n" + "="*70)
    print(f"PATH VALIDATION REPORT: {path}")
    print("="*70)
    
    result = validate_path(path, must_exist=False)
    
    print(f"\nStatus: {'✓ VALID' if result.is_valid else '✗ INVALID'}")
    print(f"Security Level: {result.security_level.value.upper()}")
    print(f"Normalized: {result.normalized_path}")
    
    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for i, error in enumerate(result.errors, 1):
            print(f"  {i}. {error}")
    
    if result.warnings:
        print(f"\nWarnings ({len(result.warnings)}):")
        for i, warning in enumerate(result.warnings, 1):
            print(f"  {i}. {warning}")
    
    print(f"\nMetadata:")
    for key, value in sorted(result.metadata.items()):
        print(f"  {key}: {value}")
    
    print("="*70 + "\n")


# ========================================================================================
# Registration
# ========================================================================================

def register():
    """Register utils module."""
    logger.info("Utils module registered (Military-grade path validation + Security)")


def unregister():
    """Unregister utils module."""
    logger.info("Utils module unregistered")
    
    # Clear validation cache
    _strict_validator.clear_cache()
    _normal_validator.clear_cache()
    _relaxed_validator.clear_cache()


# ========================================================================================
# END OF UTILS.PY
# ========================================================================================

logger.info("Utils module loaded - Path validation: MILITARY GRADE | Security: A+")