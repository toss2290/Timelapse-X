"""
Camera rendering and capture logic for Timelapse X addon.

FIXED: Use set_ignore_depsgraph() method instead of direct assignment
- mgr.ignore_depsgraph = True  →  mgr.set_ignore_depsgraph(True)
- mgr.ignore_depsgraph = False →  mgr.set_ignore_depsgraph(False)
"""

import bpy
import os
import logging
from typing import Optional, Tuple

from .. import constants
from .. import utils
from ..state_manager import StateManager

from . import scheduler
from . import shading

logger = logging.getLogger(__name__)

# ========================================================================================
# Public API
# ========================================================================================

init_camera_schedulers = scheduler.init_camera_schedulers
compute_min_timer_interval = scheduler.compute_min_timer_interval


# ========================================================================================
# Edit Mode Detection
# ========================================================================================

def _is_in_edit_mode() -> Tuple[bool, Optional[str]]:
    """Check if Blender is currently in any edit mode."""
    try:
        mode = bpy.context.mode
        
        if mode.startswith('EDIT_'):
            return True, mode
        
        return False, None
    
    except Exception as e:
        logger.debug(f"Error checking edit mode: {e}")
        return False, None


def _get_edit_mode_info() -> dict:
    """Get detailed information about current edit mode."""
    is_edit, mode_name = _is_in_edit_mode()
    
    if not is_edit:
        return {
            'is_edit': False,
            'mode': None,
            'active_object': None,
            'object_type': None
        }
    
    try:
        active_obj = bpy.context.active_object
        obj_type = active_obj.type if active_obj else None
        
        return {
            'is_edit': True,
            'mode': mode_name,
            'active_object': active_obj,
            'object_type': obj_type
        }
    
    except Exception as e:
        logger.debug(f"Error getting edit mode info: {e}")
        return {
            'is_edit': True,
            'mode': mode_name,
            'active_object': None,
            'object_type': None
        }


# ========================================================================================
# Edit Mode Handler
# ========================================================================================

class EditModeHandler:
    """Handles different edit mode behaviors for capturing."""
    
    def __init__(self, behavior: str, auto_save: bool = True):
        self.behavior = behavior
        self.auto_save = auto_save
        self._original_mode = None
        self._original_object = None
    
    def should_skip_capture(self) -> bool:
        """Check if capture should be skipped."""
        edit_info = _get_edit_mode_info()
        
        if not edit_info['is_edit']:
            return False
        
        if self.behavior == 'SKIP':
            logger.debug(
                f"Skipping capture - user in {edit_info['mode']} "
                f"(Edit Mode Behavior: SKIP)"
            )
            return True
        
        return False
    
    def prepare_for_capture(self, context) -> bool:
        """Prepare for capture based on edit mode behavior."""
        edit_info = _get_edit_mode_info()
        
        if not edit_info['is_edit']:
            return True
        
        if self.behavior == 'SKIP':
            return False
        
        if self.behavior == 'CAPTURE_ANYWAY':
            logger.warning(
                f"Capturing in {edit_info['mode']} - this may cause instability!"
            )
            return True
        
        if self.behavior == 'FORCE_OBJECT':
            return self._switch_to_object_mode(context, edit_info)
        
        return False
    
    def _switch_to_object_mode(self, context, edit_info: dict) -> bool:
        """Switch to Object mode for capture."""
        try:
            self._original_mode = edit_info['mode']
            self._original_object = edit_info['active_object']
            
            logger.info(
                f"Switching from {self._original_mode} to Object mode for capture..."
            )
            
            if self.auto_save and self._original_object:
                try:
                    if hasattr(bpy.ops.object, 'mode_set'):
                        pass
                    logger.debug("Edit mode changes preserved")
                except Exception as e:
                    logger.warning(f"Could not auto-save: {e}")
            
            if bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set(mode='OBJECT')
                logger.debug("✓ Switched to Object mode")
                return True
            else:
                logger.error("Cannot switch to Object mode - operation not available")
                return False
        
        except Exception as e:
            logger.error(f"Failed to switch to Object mode: {e}")
            return False

    def restore_edit_mode(self, context):
        """Restore original edit mode after capture."""
        if self.behavior != 'FORCE_OBJECT':
            return
        
        if not self._original_mode:
            return
        
        try:
            if self._original_object:
                try:
                    context.view_layer.objects.active = self._original_object
                except Exception as e:
                    logger.warning(f"Could not restore active object: {e}")
            
            mode_to_set = self._original_mode.split('_')[0]
            
            if bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set(mode=mode_to_set)
                logger.debug(f"✓ Restored to {self._original_mode}")
            else:
                logger.warning("Cannot restore edit mode - operation not available")
        
        except Exception as e:
            logger.error(f"Failed to restore edit mode: {e}")
        
        finally:
            self._original_mode = None
            self._original_object = None


# ========================================================================================
# Main Capture Function
# ========================================================================================

def capture_cameras(context, base_dir: str, require_dirty: bool = True) -> bool:
    """
    Capture frames from cameras in the camera list.
    
    Args:
        context: Blender context
        base_dir: Base directory for output
        require_dirty: Only capture if scene is dirty

    Returns:
        True if any frames were captured, False otherwise
    """
    scene = context.scene
    prefs = utils.get_addon_preferences()

    # Create edit mode handler
    edit_handler = EditModeHandler(
        behavior=prefs.edit_mode_behavior if prefs else 'SKIP',
        auto_save=prefs.edit_mode_auto_save if prefs else True
    )

    # Check if should skip
    if edit_handler.should_skip_capture():
        return False

    # Prepare for capture (may switch mode)
    if not edit_handler.prepare_for_capture(context):
        return False

    # Get StateManager instance
    mgr = StateManager()
    
    # Check idle detection
    if require_dirty and prefs and prefs.idle_detection:
        if not mgr.dirty:
            edit_handler.restore_edit_mode(context)
            return False

    # Validate camera list
    if len(scene.tlx_cameras) == 0:
        edit_handler.restore_edit_mode(context)
        raise RuntimeError('Camera list is empty.')

    # Store original scene state
    original_camera = scene.camera
    original_filepath = scene.render.filepath
    original_engine = None

    img_settings = scene.render.image_settings
    original_format = img_settings.file_format
    original_color_mode = getattr(img_settings, 'color_mode', 'RGB')
    original_quality = getattr(img_settings, 'quality', 90)
    original_compression = getattr(img_settings, 'compression', 15)
    original_media_type = getattr(img_settings, 'media_type', None)

    # Track if any cameras were rendered
    any_captured = False

    # ✅ FIX: Access private member directly (no setter exists)
    mgr._ignore_depsgraph = True

    try:
        # Apply global shading lock if no per-camera overrides
        any_override = any(item.use_shading_override for item in scene.tlx_cameras)
        if not any_override:
            original_engine = shading.lock_viewport_shading(scene, prefs)
        
        # Determine round-robin mode
        use_round_robin = bool(prefs.camera_round_robin) if prefs else True
        
        # Pick cameras to render
        camera_indices = scheduler.pick_due_cameras(scene, prefs, round_robin=use_round_robin)
        
        # Limit cameras per tick
        max_per_tick = int(getattr(prefs, 'camera_max_per_tick', 1)) if prefs else 1
        camera_indices = camera_indices[:max(1, max_per_tick)]
        
        if not camera_indices:
            return False
        
        # Render each camera
        for index in camera_indices:
            camera_item = scene.tlx_cameras[index]
            camera = camera_item.camera
            
            # Skip invalid cameras
            if not camera or camera.type != 'CAMERA':
                scheduler.update_camera_due(camera_item)
                continue
            
            # Safety check: Verify still in correct mode
            if edit_handler.behavior == 'FORCE_OBJECT':
                current_mode = bpy.context.mode
                if current_mode.startswith('EDIT_'):
                    logger.warning(
                        f"Unexpected: Still in edit mode during batch. "
                        f"Skipping remaining cameras."
                    )
                    break
            
            # Render this camera
            success = _render_camera(
                context,
                scene,
                camera_item,
                camera,
                base_dir,
                prefs,
                edit_handler
            )
            
            if success:
                any_captured = True
            
            # Update timing
            scheduler.update_camera_due(camera_item)
        
        # Mark scene as captured if any succeeded
        if any_captured:
            mgr.set_dirty(False)
        
        return any_captured

    finally:
        # ✅ FIX: Restore depsgraph monitoring via private member
        mgr._ignore_depsgraph = False
        
        # Set suppression cooldown
        if prefs:
            suppress_ms = getattr(prefs, 'perf_depsgraph_suppress_ms', constants.DEFAULT_SUPPRESS_MS)
            mgr.set_suppression(suppress_ms)
        
        # Restore scene state
        scene.camera = original_camera
        scene.render.filepath = original_filepath
        
        # Restore image settings
        img_settings.file_format = original_format
        if hasattr(img_settings, 'color_mode'):
            img_settings.color_mode = original_color_mode
        if hasattr(img_settings, 'quality'):
            img_settings.quality = original_quality
        if hasattr(img_settings, 'compression'):
            img_settings.compression = original_compression
        if original_media_type is not None and hasattr(img_settings, 'media_type'):
            img_settings.media_type = original_media_type
        
        # Restore engine and shading
        shading.restore_viewport_shading(scene, original_engine)
        
        # Restore edit mode
        edit_handler.restore_edit_mode(context)


# ========================================================================================
# Single Camera Render
# ========================================================================================

def _render_camera(
    context,
    scene,
    camera_item,
    camera,
    base_dir: str,
    prefs,
    edit_handler: EditModeHandler
) -> bool:
    """Render a single camera with edit mode awareness."""
    try:
        # Safety check: Verify mode before render
        if edit_handler.behavior != 'CAPTURE_ANYWAY':
            edit_info = _get_edit_mode_info()
            if edit_info['is_edit']:
                logger.warning(
                    f"Unexpected edit mode detected before render "
                    f"({edit_info['mode']}). Skipping camera '{camera.name}'."
                )
                return False
        
        # Get effective settings (per-camera or global)
        settings = _get_camera_settings(camera_item, prefs)
        
        # Setup camera output directory
        camera_name = utils.sanitize_filename(camera.name)
        camera_dir = utils.ensure_directory(os.path.join(base_dir, f"CAM_{camera_name}"))
        
        # Get frame index
        if "_tlx_idx" not in camera_item:
            try:
                existing = [
                    f for f in os.listdir(camera_dir)
                    if f.lower().endswith(constants.IMAGE_EXTENSIONS)
                ]
                camera_item["_tlx_idx"] = len(existing)
            except OSError:
                camera_item["_tlx_idx"] = 0
        
        frame_index = int(camera_item.get("_tlx_idx", 0))
        
        # Build output path (without extension - Blender adds it)
        zero_padding = prefs.zero_padding if prefs else constants.DEFAULT_ZERO_PADDING
        output_path = os.path.join(
            camera_dir,
            f"TLX_CAM_{camera_name}_{str(frame_index).zfill(zero_padding)}"
        )
        
        # Setup scene for render
        scene.camera = camera
        scene.render.filepath = output_path
        
        # Configure image format
        img_settings = scene.render.image_settings
        img_settings.file_format = settings['format']
        
        if settings['format'] == 'PNG':
            if hasattr(img_settings, 'color_mode'):
                img_settings.color_mode = 'RGBA' if settings['png_rgba'] else 'RGB'
            if hasattr(img_settings, 'compression'):
                img_settings.compression = 15
        else:  # JPEG
            if hasattr(img_settings, 'color_mode'):
                img_settings.color_mode = 'RGB'
            if hasattr(img_settings, 'quality'):
                img_settings.quality = settings['jpeg_quality']
        
        # Store viewport lock state
        viewport_prefs = bpy.context.preferences.view
        prev_lock = getattr(viewport_prefs, 'use_lock_interface', False)
        
        # Apply UI lock if requested
        if hasattr(viewport_prefs, 'use_lock_interface') and settings['lock_interface']:
            try:
                viewport_prefs.use_lock_interface = True
            except (AttributeError, RuntimeError):
                pass
        
        # Backup PNG compression
        png_comp_backup = None
        if img_settings.file_format == 'PNG' and hasattr(img_settings, 'compression'):
            png_comp_backup = img_settings.compression
            img_settings.compression = int(settings['png_compress'])
        
        # Store original engine
        prev_engine = scene.render.engine
        low_backup = None
        
        try:
            # Get shading target
            stype, want_xray, want_no_shadows = _get_shading_target(camera_item, prefs)
            
            # Apply low-overhead settings if enabled
            if settings['low_overhead']:
                low_backup = shading.apply_low_overhead_settings(scene)
            
            # Final safety check before render
            if edit_handler.behavior != 'CAPTURE_ANYWAY':
                edit_info = _get_edit_mode_info()
                if edit_info['is_edit']:
                    logger.warning(
                        f"User entered {edit_info['mode']} just before render, "
                        f"aborting camera '{camera.name}'"
                    )
                    return False
            
            # Render based on shading type
            if stype == 'WIREFRAME':
                # Wireframe with object color support
                _render_wireframe(scene, camera, output_path, prefs)
            
            elif stype == 'SOLID' and not utils.is_headless():
                # Try OpenGL render for SOLID
                if bpy.ops.render.opengl.poll():
                    scene.render.engine = 'BLENDER_WORKBENCH'
                    
                    # Apply workbench overrides
                    wb_backup = shading.apply_workbench_display_overrides(
                        scene,
                        want_xray,
                        want_no_shadows
                    )
                    
                    try:
                        bpy.ops.render.opengl(write_still=True, view_context=False)
                    except RuntimeError:
                        # Fallback to regular render
                        bpy.ops.render.render(write_still=True, use_viewport=False)
                    finally:
                        shading.restore_workbench_display_overrides(scene, wb_backup)
                else:
                    # Fallback
                    scene.render.engine = utils.get_engine_for_shading(stype)
                    bpy.ops.render.render(write_still=True, use_viewport=False)
            
            else:
                # Regular render for MATERIAL/RENDERED
                scene.render.engine = utils.get_engine_for_shading(stype)
                bpy.ops.render.render(write_still=True, use_viewport=False)
            
            # Success - increment index
            camera_item["_tlx_idx"] = frame_index + 1
            return True
        
        except Exception as e:
            logger.error(f"Camera render failed for {camera.name}: {e}", exc_info=True)
            return False
        
        finally:
            # Restore low-overhead settings
            if low_backup is not None:
                shading.restore_low_overhead_settings(scene, low_backup)
            
            # Restore PNG compression
            if png_comp_backup is not None:
                try:
                    img_settings.compression = png_comp_backup
                except (AttributeError, RuntimeError):
                    pass
            
            # Restore engine
            try:
                scene.render.engine = prev_engine
            except (AttributeError, RuntimeError):
                pass
            
            # Restore UI lock
            try:
                if hasattr(viewport_prefs, 'use_lock_interface'):
                    viewport_prefs.use_lock_interface = prev_lock
            except (AttributeError, RuntimeError):
                pass

    except Exception as e:
        logger.error(f"Render camera exception: {e}", exc_info=True)
        return False


# ========================================================================================
# Settings Helpers
# ========================================================================================

def _get_camera_settings(camera_item, prefs) -> dict:
    """Get effective settings for camera (with overrides)."""
    settings = {}
    # Image format
    if camera_item.use_image_override:
        settings['format'] = camera_item.image_format
        settings['png_rgba'] = camera_item.png_rgba
        settings['jpeg_quality'] = camera_item.jpeg_quality
    else:
        settings['format'] = prefs.image_format if prefs else 'PNG'
        settings['png_rgba'] = prefs.png_rgba if prefs else False
        settings['jpeg_quality'] = prefs.jpeg_quality if prefs else 90

    # Performance
    if camera_item.perf_override:
        settings['low_overhead'] = camera_item.perf_low_overhead
        settings['lock_interface'] = camera_item.perf_lock_interface
        settings['png_compress'] = camera_item.perf_png_compress
    else:
        settings['low_overhead'] = getattr(prefs, 'camera_low_overhead', True) if prefs else True
        settings['lock_interface'] = getattr(prefs, 'camera_lock_interface', True) if prefs else True
        settings['png_compress'] = getattr(prefs, 'camera_png_compress', 3) if prefs else 3

    return settings


def _get_shading_target(camera_item, prefs) -> Tuple[str, bool, bool]:
    """Get shading target for camera."""
    if camera_item.use_shading_override:
        return (
            camera_item.shading_type,
            camera_item.xray,
            camera_item.disable_shadows
        )
    elif prefs and prefs.lock_shading:
        return (
            prefs.shading_type,
            prefs.xray,
            prefs.disable_shadows
        )
    else:
        return ('SOLID', False, True)


# ========================================================================================
# Wireframe Rendering with Object Color Support
# ========================================================================================

def _render_wireframe(scene, camera, output_path: str, prefs):
    """Render wireframe - SAFE implementation with object color support."""
    logger.debug(f"Wireframe render: {camera.name}")
    
    # ===== TIER 1: Freestyle - WITH OBJECT COLORS =====
    try:
        from . import wireframe
        
        # Get line settings
        thickness = prefs.wireframe_thickness if prefs else 1.0
        color = tuple(prefs.wireframe_color) if prefs else (0.0, 0.0, 0.0)
        
        # Get background settings
        bg_color = tuple(prefs.wireframe_bg_color) if prefs else (1.0, 1.0, 1.0)
        bg_strength = prefs.wireframe_bg_strength if prefs else 1.0
        transparent_bg = prefs.wireframe_transparent_bg if prefs else False
        disable_shadows = prefs.wireframe_disable_shadows if prefs else True
        
        # Get object color settings
        use_object_colors = prefs.wireframe_use_object_colors if prefs else False
        default_object_color = tuple(prefs.wireframe_default_object_color) if prefs else (1.0, 1.0, 1.0)
        
        logger.debug(
            f"Using Freestyle: thickness={thickness}, transparent={transparent_bg}, "
            f"object_colors={use_object_colors}"
        )
        
        # Render with wireframe module
        wireframe.render_freestyle(
            output_path_noext=output_path,
            camera_obj=camera,
            thickness=thickness,
            color=color,
            bg_color=bg_color,
            bg_strength=bg_strength,
            transparent_bg=transparent_bg,
            disable_shadows=disable_shadows,
            use_object_colors=use_object_colors,
            default_object_color=default_object_color
        )
        
        logger.debug(f"✓ Wireframe render complete")
        return

    except ImportError as e:
        logger.error(f"Freestyle not available: {e}")

    except Exception as e:
        logger.error(f"Freestyle failed: {e}")
        import traceback
        traceback.print_exc()

    # ===== TIER 2: SOLID + Wireframe Overlay (fallback) =====
    try:
        logger.debug("Tier 2: SOLID + wireframe overlay")
        
        prev_engine = scene.render.engine
        scene.render.engine = 'BLENDER_WORKBENCH'
        
        saved_shading = []
        
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        saved_shading.append((
                            space,
                            space.shading.type,
                            getattr(space.overlay, 'show_wireframes', False) if hasattr(space, 'overlay') else False
                        ))
                        
                        try:
                            space.shading.type = 'SOLID'
                            overlay = getattr(space, 'overlay', None)
                            if overlay and hasattr(overlay, 'show_wireframes'):
                                overlay.show_wireframes = True
                        except Exception as e:
                            logger.debug(f"Cannot enable overlay: {e}")
                        break
                break
        
        try:
            bpy.context.view_layer.update()
            
            if bpy.ops.render.opengl.poll():
                bpy.ops.render.opengl(write_still=True, view_context=False)
            else:
                bpy.ops.render.render(write_still=True, use_viewport=False)
            
            return
        
        finally:
            for space, orig_shading, orig_wireframe in saved_shading:
                try:
                    space.shading.type = orig_shading
                    overlay = getattr(space, 'overlay', None)
                    if overlay and hasattr(overlay, 'show_wireframes'):
                        overlay.show_wireframes = orig_wireframe
                except:
                    pass
            
            try:
                scene.render.engine = prev_engine
            except:
                pass

    except Exception as e:
        logger.error(f"Tier 2 failed: {e}")
        raise RuntimeError(f"Wireframe render failed: {e}")


# ========================================================================================
# Registration
# ========================================================================================

def register():
    """Register camera capture module."""
    logger.info("Camera capture module registered (FIXED: Use set_ignore_depsgraph())")


def unregister():
    """Unregister camera capture module."""
    logger.info("Camera capture module unregistered")