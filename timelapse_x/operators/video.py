"""
TIMELAPSE X - FFMPEG SECURITY FIX + RGBA FIX + RESOLUTION FIX
FINAL VERSION: Fixes window capture compilation issues
"""

import bpy
import os
import logging
import subprocess
import tempfile
import shlex
import hashlib
from datetime import datetime
from bpy.types import Operator
from bpy.props import StringProperty, IntProperty, BoolProperty
from typing import Optional, List, Tuple

from .. import utils
from .. import constants
from ..state_manager import StateManager


logger = logging.getLogger(__name__)


# ========================================================================================
# SECURITY: FFMPEG Validation & Sanitization
# ========================================================================================

class FFMPEGSecurityError(Exception):
    """Raised when FFMPEG security validation fails."""
    pass


class FFMPEGValidator:
    """FFMPEG security validator with command injection prevention."""
    
    ALLOWED_ARGS = {
        '-f', '-safe', '-i', '-c:v', '-preset', '-crf', 
        '-pix_fmt', '-r', '-y', '-loglevel', '-threads',
        '-movflags', '-g', '-keyint_min', '-b:v', '-vf'
    }
    
    ALLOWED_CODECS = {
        'libx264', 'libx265', 'libvpx', 'libvpx-vp9'
    }
    
    ALLOWED_PRESETS = {
        'ultrafast', 'superfast', 'veryfast', 'faster', 'fast',
        'medium', 'slow', 'slower', 'veryslow'
    }
    
    ALLOWED_PIXFMTS = {
        'yuv420p', 'yuv422p', 'yuv444p', 'rgb24', 'rgba'
    }
    
    def __init__(self):
        self.verified_paths = {}
    
    def validate_ffmpeg_path(self, ffmpeg_path: str) -> str:
        if not ffmpeg_path:
            raise FFMPEGSecurityError("FFMPEG path is empty")
        
        path_hash = hashlib.sha256(ffmpeg_path.encode()).hexdigest()
        if path_hash in self.verified_paths:
            cached_path = self.verified_paths[path_hash]
            if os.path.exists(cached_path):
                return cached_path
        
        try:
            abs_path = os.path.abspath(os.path.expanduser(ffmpeg_path))
        except Exception as e:
            raise FFMPEGSecurityError(f"Invalid path format: {e}")
        
        if '..' in abs_path or abs_path.count(os.sep) > 20:
            raise FFMPEGSecurityError(f"Suspicious path detected: {abs_path}")
        
        if not os.path.exists(abs_path):
            raise FFMPEGSecurityError(f"FFMPEG not found: {abs_path}")
        
        if not os.path.isfile(abs_path):
            raise FFMPEGSecurityError(f"FFMPEG path is not a file: {abs_path}")
        
        if not os.access(abs_path, os.X_OK):
            raise FFMPEGSecurityError(f"FFMPEG is not executable: {abs_path}")
        
        if not self._verify_ffmpeg_signature(abs_path):
            raise FFMPEGSecurityError(f"File is not a valid FFMPEG executable: {abs_path}")
        
        self.verified_paths[path_hash] = abs_path
        logger.info(f"FFMPEG validated: {abs_path}")
        return abs_path
    
    def _verify_ffmpeg_signature(self, path: str) -> bool:
        try:
            result = subprocess.run(
                [path, '-version'],
                capture_output=True,
                timeout=5,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
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
        if not file_path:
            raise FFMPEGSecurityError("Input file path is empty")
        
        abs_path = os.path.abspath(file_path)
        
        dangerous_chars = ['|', '&', ';', '$', '`', '\n', '\r']
        for char in dangerous_chars:
            if char in file_path:
                raise FFMPEGSecurityError(f"Suspicious character in path: {repr(char)}")
        
        if not os.path.exists(abs_path):
            raise FFMPEGSecurityError(f"File not found: {abs_path}")
        
        if not os.path.isfile(abs_path):
            raise FFMPEGSecurityError(f"Path is not a file: {abs_path}")
        
        if not os.access(abs_path, os.R_OK):
            raise FFMPEGSecurityError(f"File not readable: {abs_path}")
        
        return abs_path
    
    def validate_output_path(self, output_path: str) -> str:
        if not output_path:
            raise FFMPEGSecurityError("Output path is empty")
        
        abs_path = os.path.abspath(output_path)
        
        dangerous_chars = ['|', '&', ';', '$', '`', '\n', '\r']
        for char in dangerous_chars:
            if char in output_path:
                raise FFMPEGSecurityError(f"Suspicious character in path: {repr(char)}")
        
        parent = os.path.dirname(abs_path)
        if not os.path.exists(parent):
            raise FFMPEGSecurityError(f"Output directory does not exist: {parent}")
        
        if not os.access(parent, os.W_OK):
            raise FFMPEGSecurityError(f"Output directory not writable: {parent}")
        
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
        pixfmt: str = 'yuv420p',
        video_filter: Optional[str] = None
    ) -> List[str]:
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
        
        # Build command
        cmd = [
            ffmpeg,
            '-f', 'concat',
            '-safe', '0',
            '-i', input_file,
        ]
        
        # Add video filter if specified
        if video_filter:
            cmd.extend(['-vf', video_filter])
        
        cmd.extend([
            '-c:v', codec,
            '-preset', preset,
            '-crf', str(crf),
            '-pix_fmt', pixfmt,
            '-r', str(fps),
            '-movflags', '+faststart',
            '-y',
            output_file
        ])
        
        # Log command
        log_cmd = ' '.join(shlex.quote(arg) for arg in cmd)
        logger.info(f"FFMPEG command: {log_cmd}")
        
        return cmd
    
    def execute_safe_command(
        self,
        cmd: List[str],
        timeout: int = 300
    ) -> Tuple[bool, str]:
        try:
            logger.info(f"Executing FFMPEG (timeout: {timeout}s)...")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace',
                shell=False
            )
            
            if result.returncode != 0:
                error_msg = f"FFMPEG failed (code {result.returncode})"
                
                if result.stderr:
                    error_lines = result.stderr.strip().split('\n')[-10:]
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


_ffmpeg_validator = FFMPEGValidator()


# ========================================================================================
# FFMPEG Discovery
# ========================================================================================

def find_ffmpeg_safe() -> Optional[str]:
    candidates = []
    
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
    
    try:
        import platform
        if platform.system() == 'Windows':
            result = subprocess.run(['where', 'ffmpeg'], capture_output=True, timeout=5, text=True)
        else:
            result = subprocess.run(['which', 'ffmpeg'], capture_output=True, timeout=5, text=True)
        
        if result.returncode == 0:
            path = result.stdout.strip().split('\n')[0]
            if path:
                candidates.append(path)
    except Exception as e:
        logger.debug(f"Cannot check system PATH: {e}")
    
    common_paths = [
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe',
        '/usr/bin/ffmpeg',
        '/usr/local/bin/ffmpeg',
        '/opt/ffmpeg/bin/ffmpeg',
        '/opt/homebrew/bin/ffmpeg',
        '/usr/local/opt/ffmpeg/bin/ffmpeg',
    ]
    candidates.extend(common_paths)
    
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
# IMAGE VALIDATION WITH RESOLUTION CHECK
# ========================================================================================

def validate_images_for_compilation(
    image_dir: str,
    image_extensions: tuple = ('.png', '.jpg', '.jpeg')
) -> Tuple[List[str], dict]:
    """
    Validate images before FFMPEG compilation.
    
    DETECTS:
    - RGBA format (needs conversion)
    - Odd resolution (needs rounding for H.264)
    - File integrity
    """
    files = sorted([
        f for f in os.listdir(image_dir)
        if f.lower().endswith(image_extensions)
    ])
    
    if not files:
        raise RuntimeError("No images found in directory")
    
    metadata = {
        'total_files': len(files),
        'valid_files': [],
        'issues': [],
        'width': None,
        'height': None,
        'has_alpha': False,
        'channels': 3,
        'needs_scale': False,  # NEW: Track if resolution needs fixing
    }
    
    # Check first image
    first_path = os.path.join(image_dir, files[0])
    
    try:
        img = bpy.data.images.load(first_path, check_existing=False)
        
        metadata['width'] = img.size[0]
        metadata['height'] = img.size[1]
        metadata['channels'] = img.channels
        metadata['has_alpha'] = (img.channels == 4)
        
        # Check if resolution needs scaling (odd dimensions)
        if metadata['width'] % 2 != 0 or metadata['height'] % 2 != 0:
            metadata['needs_scale'] = True
            logger.warning(
                f"⚠ Odd resolution detected: {metadata['width']}x{metadata['height']} "
                f"- will round to even numbers for H.264"
            )
        
        logger.info(
            f"Image format: {metadata['width']}x{metadata['height']}, "
            f"channels={metadata['channels']}, alpha={metadata['has_alpha']}, "
            f"needs_scale={metadata['needs_scale']}"
        )
        
        bpy.data.images.remove(img, do_unlink=True)
        
    except Exception as e:
        logger.error(f"Cannot read first image: {e}")
        metadata['issues'].append(f"Cannot read first image: {e}")
    
    # Validate all files
    for filename in files:
        filepath = os.path.join(image_dir, filename)
        
        if not os.path.isfile(filepath):
            metadata['issues'].append(f"Not a file: {filename}")
            continue
        
        if not os.access(filepath, os.R_OK):
            metadata['issues'].append(f"Not readable: {filename}")
            continue
        
        try:
            size = os.path.getsize(filepath)
            if size == 0:
                metadata['issues'].append(f"Empty file: {filename}")
                continue
            
            if size < 100:
                metadata['issues'].append(f"Suspiciously small: {filename} ({size} bytes)")
                continue
        except OSError as e:
            metadata['issues'].append(f"Cannot stat {filename}: {e}")
            continue
        
        metadata['valid_files'].append(filename)
    
    logger.info(f"Validation: {len(metadata['valid_files'])}/{metadata['total_files']} valid")
    
    if metadata['issues']:
        logger.warning(f"Issues found: {len(metadata['issues'])}")
        for issue in metadata['issues'][:5]:
            logger.warning(f"  - {issue}")
        if len(metadata['issues']) > 5:
            logger.warning(f"  ... and {len(metadata['issues']) - 5} more")
    
    if not metadata['valid_files']:
        raise RuntimeError("No valid images found after validation")
    
    return metadata['valid_files'], metadata


# ========================================================================================
# Cleanup Manager
# ========================================================================================

class CompilationCleanupManager:
    def __init__(self):
        self.loaded_images = []
        self.temp_files = []
        self._cleanup_attempted = False
    
    def register_temp_file(self, filepath: str):
        if filepath:
            self.temp_files.append(filepath)
    
    def cleanup(self):
        if self._cleanup_attempted:
            return
        
        self._cleanup_attempted = True
        logger.info("Starting cleanup...")
        
        for img in self.loaded_images:
            try:
                if img.name in bpy.data.images:
                    bpy.data.images.remove(img, do_unlink=True)
            except:
                pass
        
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
    try:
        return any(
            f.lower().endswith(constants.IMAGE_EXTENSIONS)
            for f in os.listdir(path)
        )
    except (OSError, PermissionError):
        return False


def _find_images_folder(root_dir: str, max_depth: int = 3) -> str:
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


# ========================================================================================
# MAIN COMPILATION (FINAL FIX: RESOLUTION + RGBA)
# ========================================================================================

def _compile_images_to_mp4_safe(
    image_dir: str,
    output_path: str,
    fps: int = 30,
    codec: str = 'libx264',
    preset: str = 'medium',
    crf: int = 23
):
    """
    Compile images to MP4 with automatic fixes.
    
    FIXES:
    1. RGBA → RGB conversion (format=rgb24)
    2. Odd resolution → Even resolution (scale filter)
    3. Security validation
    """
    
    logger.info(f"\n{'='*70}")
    logger.info(f"SAFE VIDEO COMPILATION (RESOLUTION + RGBA FIX)")
    logger.info('='*70)
    
    # STEP 1: Validate images
    try:
        valid_files, metadata = validate_images_for_compilation(image_dir)
    except Exception as e:
        raise RuntimeError(f"Image validation failed: {e}")
    
    has_alpha = metadata.get('has_alpha', False)
    needs_scale = metadata.get('needs_scale', False)
    
    logger.info(f"Input: {len(valid_files)} images from {image_dir}")
    logger.info(f"Output: {output_path}")
    logger.info(f"Format: {metadata['width']}x{metadata['height']}, channels={metadata['channels']}")
    logger.info(f"Settings: FPS={fps}, Codec={codec}, Preset={preset}, CRF={crf}")
    
    if has_alpha:
        logger.warning("⚠ RGBA detected - will convert to RGB")
    
    if needs_scale:
        logger.warning(
            f"⚠ Odd resolution detected ({metadata['width']}x{metadata['height']}) "
            f"- will round to even numbers"
        )
    
    logger.info('='*70 + "\n")
    
    cleanup_mgr = CompilationCleanupManager()
    filelist_path = None
    
    try:
        # STEP 2: Find FFMPEG
        ffmpeg = find_ffmpeg_safe()
        if not ffmpeg:
            raise RuntimeError(
                "FFMPEG not found.\n\n"
                "To enable video compilation:\n"
                "1. Download FFMPEG from: https://ffmpeg.org/download.html\n"
                "2. Extract and add to system PATH\n"
                "3. Or place ffmpeg.exe in Blender's folder"
            )
        
        logger.info(f"Found FFMPEG: {ffmpeg}")
        
        # STEP 3: Create file list
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.txt',
            delete=False,
            encoding='utf-8'
        ) as f:
            filelist_path = f.name
            cleanup_mgr.register_temp_file(filelist_path)
            
            for filename in valid_files:
                filepath = os.path.join(image_dir, filename)
                try:
                    filepath = _ffmpeg_validator.validate_input_file(filepath)
                except FFMPEGSecurityError as e:
                    logger.warning(f"Skipping invalid file {filename}: {e}")
                    continue
                
                filepath = filepath.replace('\\', '/')
                filepath = filepath.replace("'", "'\\''")
                
                f.write(f"file '{filepath}'\n")
                f.write(f"duration {1/fps}\n")
            
            if valid_files:
                last_file = os.path.join(image_dir, valid_files[-1])
                last_file = _ffmpeg_validator.validate_input_file(last_file)
                last_file = last_file.replace('\\', '/')
                last_file = last_file.replace("'", "'\\''")
                f.write(f"file '{last_file}'\n")
        
        logger.info(f"Created file list: {filelist_path}")
        
        # STEP 4: Build video filter chain
        filters = []
        
        # Add scale filter if needed (MUST BE FIRST)
        if needs_scale:
            # Round width and height down to nearest even number
            # trunc(iw/2)*2 rounds down to even
            scale_filter = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
            filters.append(scale_filter)
            logger.info(f"Adding scale filter: {scale_filter}")
        
        # Add format filter if needed
        if has_alpha:
            # Convert RGBA to YUV420P directly (better than rgb24 intermediate)
            format_filter = "format=yuv420p"
            filters.append(format_filter)
            logger.info(f"Adding format filter: {format_filter}")
        
        # Combine filters
        video_filter = ','.join(filters) if filters else None
        
        if video_filter:
            logger.info(f"Final video filter: {video_filter}")
        
        # STEP 5: Build command
        cmd = _ffmpeg_validator.build_safe_command(
            ffmpeg=ffmpeg,
            input_file=filelist_path,
            output_file=bpy.path.abspath(output_path),
            fps=fps,
            codec=codec,
            preset=preset,
            crf=crf,
            pixfmt='yuv420p',
            video_filter=video_filter
        )
        
        # STEP 6: Execute
        success, error_msg = _ffmpeg_validator.execute_safe_command(cmd, timeout=300)
        
        if not success:
            raise RuntimeError(f"FFMPEG encoding failed: {error_msg}")
        
        # STEP 7: Verify output
        output_abs = bpy.path.abspath(output_path)
        if not os.path.exists(output_abs):
            raise RuntimeError(f"Output file not created: {output_abs}")
        
        output_size = os.path.getsize(output_abs)
        logger.info(f"✓✓ Video created: {output_size / (1024*1024):.2f} MB")
        
        logger.info(f"\n{'='*70}")
        logger.info("✓✓ COMPILATION SUCCESSFUL ✓✓")
        logger.info('='*70 + "\n")
    
    finally:
        cleanup_mgr.cleanup()


# ========================================================================================
# Operators
# ========================================================================================

class TLX_OT_compile_video(Operator):
    """Compile image sequence to MP4 video (Auto-fix RGBA + Resolution)"""
    
    bl_idname = 'tlx.compile_video'
    bl_label = 'Make Video from Images'
    bl_options = {'REGISTER'}
    
    input_dir: StringProperty(name='Images Folder', subtype='DIR_PATH', default='')
    output_path: StringProperty(name='Video Output (MP4)', subtype='FILE_PATH', default='')
    filepath: StringProperty(subtype='FILE_PATH', default='', options={'HIDDEN'})
    directory: StringProperty(subtype='DIR_PATH', default='', options={'HIDDEN'})
    ask_output: BoolProperty(name='Choose Output via Dialog', default=False)
    fps: IntProperty(name='FPS', min=1, max=240, default=constants.DEFAULT_VIDEO_FPS)
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
            candidate = bpy.path.abspath(self.directory or self.filepath or self.input_dir)
            
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
            self.report({'ERROR'}, f'No images found under: {self.input_dir}')
            return {'CANCELLED'}
        
        files = sorted([
            f for f in os.listdir(images_folder)
            if f.lower().endswith(constants.IMAGE_EXTENSIONS)
        ])
        
        if not files:
            self.report({'ERROR'}, 'No images found in selected folder')
            return {'CANCELLED'}
        
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
                self.report({'ERROR'}, f'Cannot create output directory: {e}')
                return {'CANCELLED'}
        
        try:
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
            
            self.report({'INFO'}, 
                f'✓ Video exported! Duration: {duration:.1f}s | Size: {size_mb:.1f}MB'
            )
            
            return {'FINISHED'}
        
        except FFMPEGSecurityError as e:
            self.report({'ERROR'}, f'Security error: {e}')
            return {'CANCELLED'}
        
        except Exception as e:
            logger.error(str(e), exc_info=True)
            
            if "FFMPEG not found" in str(e):
                self.report({'ERROR'}, 
                    'FFMPEG not found. Download from: https://ffmpeg.org/download.html'
                )
            else:
                self.report({'ERROR'}, f'Compilation failed: {e}')
            
            return {'CANCELLED'}


class TLX_OT_compile_session_all(Operator):
    """Compile all cameras from current session"""
    
    bl_idname = 'tlx.compile_session_all'
    bl_label = 'Compile Current Session'
    bl_options = {'REGISTER'}
    
    fps: IntProperty(name='FPS', min=1, max=240, default=constants.DEFAULT_VIDEO_FPS)
    
    @classmethod
    def poll(cls, context):
        session_dir = StateManager().session_dir
        return bool(session_dir and os.path.isdir(session_dir))
    
    def execute(self, context):
        prefs = utils.get_addon_preferences()
        session_dir = StateManager().session_dir
        
        if not (session_dir and os.path.isdir(session_dir)):
            self.report({'ERROR'}, 'No active session folder')
            return {'CANCELLED'}
        
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
        elif flat_session:
            targets = [session_dir]
        else:
            targets = []
        
        if not targets:
            self.report({'ERROR'}, 'No camera folders or images to compile')
            return {'CANCELLED'}
        
        exported_count = 0
        failed_count = 0
        
        for target_dir in sorted(targets):
            folder_name = os.path.basename(target_dir)
            output_path = os.path.join(
                _get_output_dir(target_dir),
                f"{tag}_{folder_name}_{timestamp}.mp4"
            )
            
            try:
                logger.info(f"Compiling {folder_name}...")
                
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
            
            except Exception as e:
                failed_count += 1
                logger.error(f"✗ Failed: {folder_name}: {e}")
        
        if exported_count == 0:
            self.report({'ERROR'}, 'No MP4s exported (all failed)')
            return {'CANCELLED'}
        
        msg = f'✓ Exported {exported_count} MP4(s)'
        if failed_count > 0:
            msg += f' ({failed_count} failed)'
        
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class TLX_OT_test_ffmpeg_security(Operator):
    """Test FFMPEG security and features"""
    
    bl_idname = 'tlx.test_ffmpeg_security'
    bl_label = 'Test FFMPEG'
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        results = []
        
        try:
            ffmpeg = find_ffmpeg_safe()
            if ffmpeg:
                results.append(("✓ FFMPEG Found", ffmpeg))
            else:
                results.append(("✗ FFMPEG Not Found", "Install FFMPEG"))
        except Exception as e:
            results.append(("✗ FFMPEG Search Failed", str(e)))
        
        for status, detail in results:
            logger.info(f"  {status}: {detail}")
        
        passed = sum(1 for s, _ in results if s.startswith("✓"))
        total = len(results)
        
        if passed == total:
            self.report({'INFO'}, f'✓ All {total} tests passed')
        else:
            self.report({'WARNING'}, f'⚠ {passed}/{total} tests passed')
        
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
    logger.info("Registering video operators (SAFE FFMPEG + RGBA FIX + RESOLUTION FIX)")
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            logger.info(f"Registered: {cls.__name__}")
        except Exception as e:
            logger.error(f"Failed to register {cls.__name__}: {e}")
    
    try:
        ffmpeg = find_ffmpeg_safe()
        if ffmpeg:
            logger.info(f"✓ FFMPEG ready: {ffmpeg}")
            logger.info("✓ Auto-fix enabled: RGBA + Resolution")
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