# Timelapse X - Main Init File - UNIFIED STATE MANAGER
# FIXED: Auto-reset StateManager on register to prevent stuck state

bl_info = {
    "name": "Timelapse X",
    "author": "Toss",
    "version": (2, 4, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar (N) > Timelapse X",
    "description": "Professional timelapse capture - Unified State Management",
    "category": "System",
    "warning": "",
}

import bpy
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("\n" + "="*70)
print("TIMELAPSE X: Starting import (UNIFIED STATE)...")
print("="*70)

# ========================================================================================
# Import modules - state_manager first!
# ========================================================================================
print("\nImporting core modules...")

from . import constants
from . import state_manager  # NEW: Unified state manager
from . import error_messages
from . import progress
from . import utils
from . import properties
from . import preferences
from . import operators
from . import capture
from . import ui
from . import clean_window

print("✓ All modules imported")
print("="*70 + "\n")


# ========================================================================================
# Registration
# ========================================================================================

def register():
    """Register addon with Unified State Manager."""
    print("\n" + "-"*70)
    print("TIMELAPSE X: Registering (UNIFIED STATE)...")
    print("-"*70)
    
    # ===== Core Modules =====
    print("\nRegistering core modules...")
    
    try:
        constants.register()
        print("✓ constants")
    except Exception as e:
        logger.error(f"Constants registration failed: {e}")
        print(f"✗ constants: {e}")
    
    try:
        state_manager.register()  # This calls force_reset_singleton()
        print("✓ state_manager (UNIFIED - RESET)")
        
        # ✅ CRITICAL FIX: Verify state after reset
        try:
            from .state_manager import StateManager
            mgr = StateManager()
            
            # Check if stuck in recording state
            if mgr.recording:
                logger.error("⚠️⚠️⚠️ CRITICAL: StateManager stuck in recording state!")
                print("⚠️⚠️⚠️ STUCK STATE DETECTED - Forcing manual reset...")
                
                # Nuclear option: force clean state
                mgr._recording = False
                mgr._paused = False
                mgr._session = None
                mgr._timer = None
                mgr._last_window_image = ''
                mgr._camera_schedulers.clear()
                mgr._rr_index = 0
                mgr._dirty = True
                mgr._ignore_depsgraph = False
                mgr._handler_installed = False
                mgr._suppress_until = 0.0
                mgr._window_async.reset()
                
                logger.info("✓ StateManager reset complete (manual)")
                print("✓ StateManager reset to clean state (manual)")
            else:
                logger.info("✓ StateManager already in clean state")
                print("✓ StateManager in clean state")
        
        except Exception as e:
            logger.warning(f"StateManager reset check failed: {e}")
            print(f"⚠ StateManager reset check failed: {e}")
    
    except Exception as e:
        logger.error(f"State manager registration failed: {e}")
        print(f"✗ state_manager: {e}")
    
    try:
        error_messages.register()
        print("✓ error_messages")
    except Exception as e:
        logger.error(f"Error messages registration failed: {e}")
        print(f"✗ error_messages: {e}")
    
    try:
        progress.register()
        print("✓ progress")
    except Exception as e:
        logger.error(f"Progress registration failed: {e}")
        print(f"✗ progress: {e}")
    
    try:
        utils.register()
        print("✓ utils")
    except Exception as e:
        logger.error(f"Utils registration failed: {e}")
        print(f"✗ utils: {e}")
    
    # ===== Blender Integration Modules =====
    print("\nRegistering Blender integration modules...")
    
    try:
        preferences.register()
        print("✓ preferences")
    except Exception as e:
        logger.error(f"Preferences registration failed: {e}")
        print(f"✗ preferences: {e}")
    
    try:
        properties.register()
        print("✓ properties")
    except Exception as e:
        logger.error(f"Properties registration failed: {e}")
        print(f"✗ properties: {e}")
    
    try:
        operators.register()
        print("✓ operators")
    except Exception as e:
        logger.error(f"Operators registration failed: {e}")
        print(f"✗ operators: {e}")
    
    try:
        capture.register()
        print("✓ capture")
    except Exception as e:
        logger.error(f"Capture registration failed: {e}")
        print(f"✗ capture: {e}")
    
    try:
        ui.register()
        print("✓ ui")
    except Exception as e:
        logger.error(f"UI registration failed: {e}")
        print(f"✗ ui: {e}")
    
    try:
        clean_window.register()
        print("✓ clean_window")
    except Exception as e:
        logger.error(f"Clean window registration failed: {e}")
        print(f"✗ clean_window: {e}")
    
    # ===== Scene Properties =====
    print("\nRegistering scene properties...")
    
    try:
        properties.register_scene_properties()
        print("✓ scene properties")
    except Exception as e:
        logger.error(f"Scene properties registration failed: {e}")
        print(f"✗ scene properties: {e}")
    
    try:
        clean_window.register_window_properties()
        print("✓ window properties")
    except Exception as e:
        logger.error(f"Window properties registration failed: {e}")
        print(f"✗ window properties: {e}")
    
    # ===== Validate Settings =====
    print("\nValidating settings...")
    
    try:
        # Only validate if context is available
        if bpy.context and hasattr(bpy.context, 'scene') and bpy.context.scene:
            scene = bpy.context.scene
            prefs = utils.get_addon_preferences()
            
            # Validate interval
            if hasattr(scene, 'tlx_capture_interval'):
                interval = float(getattr(scene, 'tlx_capture_interval', constants.DEFAULT_INTERVAL))
                if interval <= constants.MIN_INTERVAL:
                    scene.tlx_capture_interval = constants.DEFAULT_INTERVAL
                    print(f"  ⚠️  Reset invalid scene interval: {interval}")
            
            # Validate preference interval
            if prefs:
                default_interval = float(getattr(prefs, 'default_interval', constants.DEFAULT_INTERVAL))
                if default_interval <= constants.MIN_INTERVAL:
                    prefs.default_interval = constants.DEFAULT_INTERVAL
                    print(f"  ⚠️  Reset invalid preference interval: {default_interval}")
        else:
            print("  ⚠️  Context not available for validation (normal during startup)")
        
        print("✓ Settings validated")
    
    except Exception as e:
        logger.warning(f"Settings validation warning: {e}")
        print(f"⚠️  Settings validation warning: {e}")
    
    # ===== Verification =====
    print("\n" + "-"*70)
    print("Verifying registration...")
    print("-"*70)
    
    # Verify panel
    if 'TLX_PT_panel' in dir(bpy.types):
        print("✓ Panel registered: TLX_PT_panel")
        print("  Access: 3D Viewport > N > Timelapse X")
    else:
        print("✗ WARNING: Panel not registered!")
    
    # Verify operators
    operator_count = sum(1 for cls_name in dir(bpy.types) if cls_name.startswith('TLX_OT_'))
    print(f"✓ Operators registered: {operator_count}")
    
    # ✅ FIXED: Verify StateManager via instance
    try:
        from .state_manager import StateManager
        mgr = StateManager()  # ✅ Get instance first
        print(f"✓ StateManager initialized")
        print(f"  Recording: {mgr.recording}")
        print(f"  Counter: {mgr.counter}")
        print(f"  Cameras: {len(mgr._camera_schedulers)}")  # ✅ Access via instance
    except Exception as e:
        logger.warning(f"StateManager verification failed: {e}")
        print(f"⚠️  StateManager verification: {e}")
    
    # Print summary
    print("-"*70)
    print("TIMELAPSE X: Registration complete!")
    print("UNIFIED STATE: All state in StateManager")
    print("-"*70 + "\n")
    
    logger.info("Timelapse X registered (Unified State Manager)")


def unregister():
    """Unregister addon with cleanup."""
    print("\n" + "="*70)
    print("TIMELAPSE X: Unregistering...")
    print("="*70)
    
    # ===== Cleanup Active Operations =====
    print("\nCleaning up active operations...")
    
    try:
        from .state_manager import StateManager
        mgr = StateManager()  # ✅ Get instance
        
        # Stop recording if active
        if mgr.timer and bpy.context:
            wm = bpy.context.window_manager
            if wm:
                try:
                    wm.event_timer_remove(mgr.timer)
                    print("✓ Removed active timer")
                except:
                    pass
                mgr.timer = None
        
        # Remove depsgraph handler
        if mgr.handler_installed:
            try:
                from . import state_manager
                bpy.app.handlers.depsgraph_update_post.remove(state_manager.mark_scene_dirty)
                print("✓ Removed depsgraph handler")
            except ValueError:
                pass
            mgr.handler_installed = False
        
        # Cancel async captures
        try:
            from .capture import window
            if hasattr(window, 'cancel_async_capture'):
                window.cancel_async_capture()
                print("✓ Cancelled async captures")
        except:
            pass
    
    except Exception as e:
        logger.warning(f"Cleanup warning: {e}")
        print(f"⚠️  Cleanup warning: {e}")
    
    # ===== Unregister Properties =====
    print("\nUnregistering properties...")
    
    try:
        clean_window.unregister_window_properties()
        print("✓ window properties")
    except Exception as e:
        logger.warning(f"Window properties unregister failed: {e}")
        print(f"⚠️  window properties: {e}")
    
    try:
        properties.unregister_scene_properties()
        print("✓ scene properties")
    except Exception as e:
        logger.warning(f"Scene properties unregister failed: {e}")
        print(f"⚠️  scene properties: {e}")
    
    # ===== Unregister Modules (Reverse Order) =====
    print("\nUnregistering modules...")
    
    try:
        clean_window.unregister()
        print("✓ clean_window")
    except Exception as e:
        logger.warning(f"Clean window unregister failed: {e}")
        print(f"⚠️  clean_window: {e}")
    
    try:
        ui.unregister()
        print("✓ ui")
    except Exception as e:
        logger.warning(f"UI unregister failed: {e}")
        print(f"⚠️  ui: {e}")
    
    try:
        capture.unregister()
        print("✓ capture")
    except Exception as e:
        logger.warning(f"Capture unregister failed: {e}")
        print(f"⚠️  capture: {e}")
    
    try:
        operators.unregister()
        print("✓ operators")
    except Exception as e:
        logger.warning(f"Operators unregister failed: {e}")
        print(f"⚠️  operators: {e}")
    
    try:
        properties.unregister()
        print("✓ properties")
    except Exception as e:
        logger.warning(f"Properties unregister failed: {e}")
        print(f"⚠️  properties: {e}")
    
    try:
        preferences.unregister()
        print("✓ preferences")
    except Exception as e:
        logger.warning(f"Preferences unregister failed: {e}")
        print(f"⚠️  preferences: {e}")
    
    try:
        utils.unregister()
        print("✓ utils")
    except Exception as e:
        logger.warning(f"Utils unregister failed: {e}")
        print(f"⚠️  utils: {e}")
    
    try:
        progress.unregister()
        print("✓ progress")
    except Exception as e:
        logger.warning(f"Progress unregister failed: {e}")
        print(f"⚠️  progress: {e}")
    
    try:
        error_messages.unregister()
        print("✓ error_messages")
    except Exception as e:
        logger.warning(f"Error messages unregister failed: {e}")
        print(f"⚠️  error_messages: {e}")
    
    try:
        state_manager.unregister()  # This calls force_reset_singleton()
        print("✓ state_manager")
    except Exception as e:
        logger.warning(f"State manager unregister failed: {e}")
        print(f"⚠️  state_manager: {e}")
    
    try:
        constants.unregister()
        print("✓ constants")
    except Exception as e:
        logger.warning(f"Constants unregister failed: {e}")
        print(f"⚠️  constants: {e}")
    
    # ===== Cleanup Metadata =====
    print("\nCleaning up camera metadata...")
    try:
        if bpy.context and hasattr(bpy.context, 'scene') and bpy.context.scene:
            for camera_item in bpy.context.scene.tlx_cameras:
                keys_to_remove = [k for k in camera_item.keys() if k.startswith("_tlx_")]
                for key in keys_to_remove:
                    del camera_item[key]
        print("✓ Camera metadata cleaned")
    except Exception as e:
        logger.warning(f"Camera metadata cleanup warning: {e}")
        print(f"⚠️  Camera metadata: {e}")
    
    # ===== Summary =====
    print("\n" + "="*70)
    print("TIMELAPSE X: Unregistered successfully")
    print("="*70 + "\n")
    
    logger.info("Timelapse X unregistered")


# ========================================================================================
# Direct Execution Test
# ========================================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("TIMELAPSE X: Direct execution test")
    print("="*70)
    
    try:
        print("\nUnregistering (if already registered)...")
        unregister()
    except:
        print("Not previously registered")
    
    print("\nRegistering...")
    register()
    
    print("\n" + "="*70)
    print("✓ Test complete!")
    print("="*70 + "\n")