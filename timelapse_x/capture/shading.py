"""
Viewport shading lock/restore for Timelapse X addon.

FIXED: Import StateManager và sử dụng đúng instance methods
"""

import bpy
import logging
from typing import Optional, Tuple

from .. import utils
from ..state_manager import StateManager  # ✅ FIX: Import StateManager

logger = logging.getLogger(__name__)


# ========================================================================================
# Shading Backup Storage (sử dụng StateManager)
# ========================================================================================

_shading_backup = []


def clear_shading_backup():
    """Clear shading backup."""
    global _shading_backup
    _shading_backup.clear()


def backup_shading_settings(space, shading, overlay, show_gizmo):
    """Backup shading settings for a space."""
    global _shading_backup
    
    _shading_backup.append((
        space,
        shading.type if shading else None,
        getattr(shading, 'show_xray', None) if shading else None,
        getattr(shading, 'shadow_intensity', None) if shading else None,
        getattr(overlay, 'show_overlays', None) if overlay else None,
        getattr(overlay, 'show_wireframes', None) if overlay and hasattr(overlay, 'show_wireframes') else None,
        show_gizmo
    ))


def get_shading_backup():
    """Get shading backup."""
    global _shading_backup
    return _shading_backup


# ========================================================================================
# Shading Lock (Window Mode)
# ========================================================================================

def lock_viewport_shading(scene, prefs) -> Optional[str]:
    """Lock viewport shading settings for consistent capture."""
    if not prefs or not prefs.lock_shading:
        return None
    
    original_engine = scene.render.engine
    
    # Set appropriate engine for shading type
    if prefs.shading_type != 'RENDERED':
        scene.render.engine = 'BLENDER_WORKBENCH'
    
    # ✅ FIX: Clear previous backup
    clear_shading_backup()
    
    wm = bpy.context.window_manager
    if not wm:
        return original_engine
    
    # Iterate through all windows and spaces
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
                
                shading = space.shading
                overlay = getattr(space, 'overlay', None)
                show_gizmo = getattr(space, 'show_gizmo', None)
                
                # ✅ FIX: Backup current settings
                backup_shading_settings(space, shading, overlay, show_gizmo)
                
                # Apply new shading
                try:
                    shading.type = prefs.shading_type
                except (AttributeError, RuntimeError) as e:
                    logger.warning(f"Cannot set shading type: {e}")
                
                # Apply overlay settings
                if overlay:
                    hide_overlays = prefs.perf_hide_overlays_during_capture
                    
                    try:
                        overlay.show_overlays = not hide_overlays
                    except (AttributeError, RuntimeError):
                        pass
                    
                    # Wireframe overlay
                    if hasattr(overlay, 'show_wireframes'):
                        try:
                            overlay.show_wireframes = (
                                prefs.shading_type == 'SOLID' and not hide_overlays
                            )
                        except (AttributeError, RuntimeError):
                            pass
                
                # Hide gizmos
                if hasattr(space, 'show_gizmo'):
                    try:
                        space.show_gizmo = False
                    except (AttributeError, RuntimeError):
                        pass
                
                # Apply X-Ray
                if hasattr(shading, 'show_xray'):
                    try:
                        shading.show_xray = prefs.xray
                    except (AttributeError, RuntimeError):
                        pass
                
                # Apply cavity
                if hasattr(shading, 'cavity_type'):
                    try:
                        shading.cavity_type = 'BOTH'
                    except (AttributeError, RuntimeError):
                        pass
                
                # Disable shadows
                if hasattr(shading, 'shadow_intensity') and prefs.disable_shadows:
                    try:
                        shading.shadow_intensity = 0.0
                    except (AttributeError, RuntimeError):
                        pass
    
    return original_engine


def restore_viewport_shading(scene, original_engine: Optional[str]):
    """Restore viewport shading to original state."""
    # Restore engine
    if original_engine is not None:
        try:
            scene.render.engine = original_engine
        except (AttributeError, RuntimeError) as e:
            logger.warning(f"Cannot restore engine: {e}")
    
    # ✅ FIX: Restore backed up settings
    backup = get_shading_backup()
    
    for (space, shading_type, xray, shadow, overlays, 
         wireframes, gizmo) in backup:
        try:
            shading = space.shading
            
            # Restore shading type
            if shading_type is not None:
                shading.type = shading_type
            
            # Restore X-Ray
            if xray is not None and hasattr(shading, 'show_xray'):
                shading.show_xray = xray
            
            # Restore shadows
            if shadow is not None and hasattr(shading, 'shadow_intensity'):
                shading.shadow_intensity = shadow
            
            # Restore overlays
            overlay = getattr(space, 'overlay', None)
            if overlay:
                if overlays is not None:
                    overlay.show_overlays = overlays
                
                if wireframes is not None and hasattr(overlay, 'show_wireframes'):
                    try:
                        overlay.show_wireframes = wireframes
                    except (AttributeError, RuntimeError):
                        pass
            
            # Restore gizmo
            if gizmo is not None and hasattr(space, 'show_gizmo'):
                space.show_gizmo = gizmo
        
        except (AttributeError, RuntimeError, ReferenceError) as e:
            logger.warning(f"Cannot restore shading setting: {e}")
    
    # ✅ FIX: Clear backup
    clear_shading_backup()


# ========================================================================================
# Workbench Display Overrides (Camera List Mode)
# ========================================================================================

def apply_workbench_display_overrides(
    scene,
    want_xray: bool,
    want_no_shadows: bool
) -> Optional[dict]:
    """Apply X-Ray and shadow overrides to scene display shading."""
    display = getattr(scene, 'display', None)
    if not display:
        return None
    
    shading = getattr(display, 'shading', None)
    if not shading:
        return None
    
    # Backup current settings
    backup = {}
    
    if hasattr(shading, 'show_xray'):
        backup['show_xray'] = shading.show_xray
    
    if hasattr(shading, 'xray_alpha'):
        backup['xray_alpha'] = shading.xray_alpha
    
    if hasattr(shading, 'show_shadows'):
        backup['show_shadows'] = shading.show_shadows
    
    if hasattr(shading, 'shadow_intensity'):
        backup['shadow_intensity'] = shading.shadow_intensity
    
    # Apply X-Ray
    if want_xray:
        if hasattr(shading, 'show_xray'):
            try:
                shading.show_xray = True
            except (AttributeError, RuntimeError):
                pass
        
        if hasattr(shading, 'xray_alpha'):
            if shading.xray_alpha < 0.5:
                try:
                    shading.xray_alpha = 0.5
                except (AttributeError, RuntimeError):
                    pass
    
    # Disable shadows
    if want_no_shadows:
        if hasattr(shading, 'show_shadows'):
            try:
                shading.show_shadows = False
            except (AttributeError, RuntimeError):
                pass
        
        if hasattr(shading, 'shadow_intensity'):
            try:
                shading.shadow_intensity = 0.0
            except (AttributeError, RuntimeError):
                pass
    
    return backup if backup else None


def restore_workbench_display_overrides(scene, backup: Optional[dict]):
    """Restore workbench display settings from backup."""
    if not backup:
        return
    
    display = getattr(scene, 'display', None)
    if not display:
        return
    
    shading = getattr(display, 'shading', None)
    if not shading:
        return
    
    # Restore each setting
    for key, value in backup.items():
        if hasattr(shading, key):
            try:
                setattr(shading, key, value)
            except (AttributeError, RuntimeError) as e:
                logger.warning(f"Cannot restore {key}: {e}")


# ========================================================================================
# Low-Overhead Render Settings
# ========================================================================================

def apply_low_overhead_settings(scene) -> dict:
    """Apply simplified render settings for faster capture."""
    backup = {}
    render = scene.render
    
    def backup_and_set(obj, attr: str, value):
        """Helper to backup and set attribute."""
        if obj and hasattr(obj, attr):
            key = (obj.as_pointer(), attr)
            try:
                backup[key] = getattr(obj, attr)
                setattr(obj, attr, value)
            except (AttributeError, RuntimeError) as e:
                logger.debug(f"Cannot set {attr}: {e}")
    
    # Simplify settings
    backup_and_set(render, 'use_simplify', True)
    backup_and_set(render, 'simplify_subdivision_render', 0)
    backup_and_set(render, 'simplify_child_particles_render', 0)
    backup_and_set(render, 'simplify_volumes', 0.0)
    
    # Cycles settings
    cycles = getattr(scene, 'cycles', None)
    if cycles:
        backup_and_set(cycles, 'samples', 1)
        backup_and_set(cycles, 'preview_samples', 1)
        backup_and_set(cycles, 'use_adaptive_sampling', False)
        backup_and_set(cycles, 'use_denoising', False)
        backup_and_set(cycles, 'use_motion_blur', False)
    
    # Eevee settings
    eevee = getattr(scene, 'eevee', None)
    if eevee:
        backup_and_set(eevee, 'taa_render_samples', 1)
        backup_and_set(eevee, 'use_motion_blur', False)
        backup_and_set(eevee, 'use_bloom', False)
        backup_and_set(eevee, 'use_overscan', False)
    
    return backup


def restore_low_overhead_settings(scene, backup: dict):
    """Restore render settings from backup."""
    if not backup:
        return
    
    # Build object lookup by pointer
    objects = [scene.render]
    
    cycles = getattr(scene, 'cycles', None)
    if cycles:
        objects.append(cycles)
    
    eevee = getattr(scene, 'eevee', None)
    if eevee:
        objects.append(eevee)
    
    by_pointer = {obj.as_pointer(): obj for obj in objects if obj}
    
    # Restore settings
    for (ptr, attr), value in backup.items():
        obj = by_pointer.get(ptr)
        if obj and hasattr(obj, attr):
            try:
                setattr(obj, attr, value)
            except (AttributeError, RuntimeError) as e:
                logger.debug(f"Cannot restore {attr}: {e}")


# ========================================================================================
# Registration
# ========================================================================================

def register():
    """Register shading module."""
    logger.info("Shading module registered (FIXED: Import StateManager)")


def unregister():
    """Unregister shading module."""
    logger.info("Shading module unregistered")