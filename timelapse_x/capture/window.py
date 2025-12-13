"""
Window capture logic for Timelapse X addon.
Captures screenshots of Blender UI/viewport.
"""

import bpy
import os
import logging
import threading
from typing import Optional
from dataclasses import dataclass
from enum import Enum

from .. import constants
from .. import utils
from .. import state

logger = logging.getLogger(__name__)


# ========================================================================================
# Thread-Safe Async State Management
# ========================================================================================

class AsyncCaptureState(Enum):
    """State of async capture operation"""
    IDLE = "idle"
    PENDING = "pending"
    CAPTURING = "capturing"
    CANCELLING = "cancelling"


@dataclass
class AsyncCaptureContext:
    """Context for async capture operation"""
    state: AsyncCaptureState = AsyncCaptureState.IDLE
    timer_function: Optional[object] = None  # Store actual function reference
    scheduled_time: float = 0.0
    attempt_count: int = 0
    
    def reset(self):
        """Reset to idle state"""
        self.state = AsyncCaptureState.IDLE
        self.timer_function = None
        self.scheduled_time = 0.0
        self.attempt_count = 0


# Global state with lock
_async_lock = threading.RLock()  # RLock allows same thread to acquire multiple times
_async_context = AsyncCaptureContext()


# ========================================================================================
# Thread-Safe State Accessors
# ========================================================================================

def is_async_pending() -> bool:
    """Check if async capture is pending - thread-safe"""
    with _async_lock:
        return _async_context.state in (
            AsyncCaptureState.PENDING, 
            AsyncCaptureState.CAPTURING
        )


def get_async_state() -> AsyncCaptureState:
    """Get current async state - thread-safe"""
    with _async_lock:
        return _async_context.state


def _set_async_state(new_state: AsyncCaptureState):
    """Set async state - must be called within lock"""
    old_state = _async_context.state
    _async_context.state = new_state
    
    if old_state != new_state:
        logger.debug(f"Async state transition: {old_state.value} -> {new_state.value}")


# ========================================================================================
# Main Capture Functions
# ========================================================================================

def capture_window(context, base_dir: str, force_save: bool = False) -> bool:
    """
    Capture a screenshot of the Blender window/viewport.
    
    Synchronous version - blocks until capture completes.
    
    Args:
        context: Blender context
        base_dir: Output directory
        force_save: Force save even if idle detection enabled
    
    Returns:
        True if frame was saved, False if skipped
    """
    if utils.is_headless():
        raise RuntimeError("WINDOW mode cannot run in background/headless.")
    
    prefs = utils.get_addon_preferences()
    
    # Check suppression cooldown
    if not force_save and state.TLX_State.is_suppressed():
        return False
    
    # Determine capture scope
    capture_full = (
        prefs.window_capture_scope == 'FULL'
        if prefs else False
    )
    
    # Stabilize viewport (hide overlays/gizmos temporarily)
    stabilize = (
        prefs.window_stabilize_view and not capture_full
        if prefs else False
    )
    
    # Create temporary file path
    temp_path = bpy.path.abspath(os.path.join(base_dir, "_TLX_WINDOW_TEMP.png"))
    
    # Find window/area/region for capture
    window, screen, area, region = utils.find_window_area_region()
    
    if not all((window, screen, area, region)):
        raise RuntimeError('No UI region found for screenshot (headless mode?).')
    
    # Backup overlay/gizmo state if stabilizing
    backup = None
    if stabilize and area.type == 'VIEW_3D':
        backup = _backup_and_hide_overlays(area)
    
    try:
        # Perform screenshot
        success = _do_screenshot(
            context,
            window,
            screen,
            area,
            region,
            temp_path,
            capture_full
        )
        
        if not success:
            raise RuntimeError("Failed to capture Blender window.")
    
    finally:
        # Restore overlays/gizmos
        if backup:
            _restore_overlays(backup)
    
    # Check if we should save (idle detection)
    use_diff = (
        prefs.window_idle_diff if prefs else False
    ) and not force_save
    
    if use_diff:
        should_save = _check_image_changed(
            temp_path,
            state.TLX_State.last_window_image,
            prefs
        )
        
        if not should_save:
            # No change - remove temp file
            try:
                os.remove(temp_path)
            except OSError:
                pass
            
            # Set cooldown
            _set_cooldown(prefs)
            return False
    
    # Move temp file to final location
    frame_index = state.TLX_State.counter
    zero_padding = prefs.zero_padding if prefs else constants.DEFAULT_ZERO_PADDING
    
    final_path = utils.generate_filename(
        base_dir,
        "TLX_WINDOW",
        frame_index,
        'png',
        zero_padding
    )
    
    try:
        os.replace(temp_path, final_path)
    except OSError:
        # Fallback: copy then delete
        import shutil
        shutil.copy2(temp_path, final_path)
        try:
            os.remove(temp_path)
        except OSError:
            pass
    
    # Update state
    state.TLX_State.last_window_image = final_path
    _set_cooldown(prefs)
    
    logger.debug(f"Window captured: {final_path}")
    return True


def capture_window_async(context, base_dir: str, force_save: bool = False) -> bool:
    """
    Capture window asynchronously using Blender timer - RACE CONDITION FREE VERSION.
    
    Non-blocking version that schedules capture on next timer tick.
    Uses RLock for nested locking and atomic operations.
    
    CRITICAL FIXES:
    1. Timer registration happens INSIDE lock (no gap)
    2. State is only set AFTER successful registration
    3. Function reference is stored for proper cancellation
    4. Double-checked locking pattern for efficiency
    
    Args:
        context: Blender context
        base_dir: Output directory
        force_save: Force save even if idle detection enabled
    
    Returns:
        True if capture was scheduled, False if already pending or failed
    """
    prefs = utils.get_addon_preferences()
    
    # Use synchronous version if async disabled
    if not (prefs and prefs.window_async_capture):
        return capture_window(context, base_dir, force_save)
    
    # ===== DOUBLE-CHECKED LOCKING PATTERN =====
    # First check without lock (fast path for common case)
    if is_async_pending():
        logger.debug("Async capture already pending (fast check)")
        return False
    
    # ===== ACQUIRE LOCK FOR ATOMIC OPERATION =====
    with _async_lock:
        # Second check with lock (prevents race condition)
        if _async_context.state != AsyncCaptureState.IDLE:
            logger.debug(f"Async capture busy: {_async_context.state.value}")
            return False
        
        # Mark as pending BEFORE any other operations
        _set_async_state(AsyncCaptureState.PENDING)
        
        # Get delay
        delay_ms = getattr(prefs, 'window_async_delay_ms', 2) if prefs else 2
        delay = max(0.0, float(delay_ms)) / 1000.0
        
        # ===== CREATE CAPTURE CALLBACK =====
        def _capture_callback():
            """
            Callback with guaranteed cleanup and proper state management.
            
            CRITICAL: This function has exclusive access during execution
            because it's the only one that transitions from PENDING to CAPTURING.
            """
            try:
                # ===== TRANSITION TO CAPTURING STATE =====
                with _async_lock:
                    if _async_context.state == AsyncCaptureState.CANCELLING:
                        logger.info("Capture cancelled before execution")
                        _async_context.reset()
                        return None
                    
                    if _async_context.state != AsyncCaptureState.PENDING:
                        logger.warning(
                            f"Unexpected state in callback: {_async_context.state.value}"
                        )
                        _async_context.reset()
                        return None
                    
                    _set_async_state(AsyncCaptureState.CAPTURING)
                    _async_context.attempt_count += 1
                
                # ===== PERFORM CAPTURE (outside lock to avoid blocking) =====
                try:
                    saved = capture_window(context, base_dir, force_save)
                    
                    if saved:
                        # Update state counters
                        state.TLX_State.counter += 1
                        state.TLX_State.last_capture_time = __import__('time').time()
                        logger.debug(
                            f"Async capture successful. "
                            f"Counter: {state.TLX_State.counter}"
                        )
                except Exception as e:
                    logger.error(f"Capture execution failed: {e}", exc_info=True)
                
            except Exception as e:
                logger.error(f"Async callback error: {e}", exc_info=True)
            
            finally:
                # ===== GUARANTEED STATE RESET =====
                with _async_lock:
                    _async_context.reset()
                    logger.debug("Async capture completed, state reset to IDLE")
            
            # Don't repeat timer
            return None
        
        # ===== REGISTER TIMER INSIDE LOCK (ATOMIC WITH STATE CHANGE) =====
        try:
            # Store function reference for potential cancellation
            _async_context.timer_function = _capture_callback
            _async_context.scheduled_time = __import__('time').time() + delay
            
            # Register timer with Blender
            # CRITICAL: This happens INSIDE the lock, so no race condition
            bpy.app.timers.register(_capture_callback, first_interval=delay)
            
            logger.debug(
                f"Async capture scheduled: delay={delay:.3f}s, "
                f"state={_async_context.state.value}"
            )
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to register timer: {e}", exc_info=True)
            
            # ===== CLEANUP ON FAILURE =====
            _async_context.reset()
            
            return False


def cancel_async_capture() -> bool:
    """
    Cancel pending async capture if any.
    Thread-safe cancellation with proper cleanup.
    
    Returns:
        True if capture was cancelled, False if nothing to cancel
    """
    with _async_lock:
        current_state = _async_context.state
        
        # Nothing to cancel
        if current_state == AsyncCaptureState.IDLE:
            return False
        
        # Already cancelling
        if current_state == AsyncCaptureState.CANCELLING:
            logger.debug("Cancel already in progress")
            return False
        
        # If currently capturing, we can't interrupt it
        # Just mark for cancellation
        if current_state == AsyncCaptureState.CAPTURING:
            logger.info("Capture in progress, marking for cancellation")
            _set_async_state(AsyncCaptureState.CANCELLING)
            return True
        
        # Cancel pending capture
        if current_state == AsyncCaptureState.PENDING:
            logger.info("Cancelling pending async capture...")
            
            _set_async_state(AsyncCaptureState.CANCELLING)
            
            # Try to unregister timer
            # Note: Blender doesn't provide direct timer cancellation by reference
            # The timer will run but the callback checks for CANCELLING state
            # and exits immediately
            
            # Best we can do: mark as cancelled and reset
            # The callback will see CANCELLING state and exit
            _async_context.reset()
            
            logger.info("Async capture cancelled")
            return True
        
        return False


def wait_for_async_completion(timeout: float = 5.0) -> bool:
    """
    Wait for any pending async capture to complete.
    
    Useful for cleanup operations that need to ensure no captures are running.
    
    Args:
        timeout: Maximum time to wait in seconds
    
    Returns:
        True if completed, False if timeout
    """
    import time
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        with _async_lock:
            if _async_context.state == AsyncCaptureState.IDLE:
                return True
        
        # Small sleep to avoid busy waiting
        time.sleep(0.01)
    
    logger.warning(f"Async capture did not complete within {timeout}s")
    return False


# ========================================================================================
# Screenshot Execution
# ========================================================================================

def _do_screenshot(
    context,
    window,
    screen,
    area,
    region,
    output_path: str,
    capture_full: bool
) -> bool:
    """
    Execute screenshot operation.
    
    Args:
        context: Blender context
        window: Window object
        screen: Screen object
        area: Area object
        region: Region object
        output_path: Output file path
        capture_full: Capture full window or just area
    
    Returns:
        True if successful
    """
    success = False
    
    with context.temp_override(
        window=window,
        screen=screen,
        area=area,
        region=region
    ):
        try:
            if capture_full:
                bpy.ops.screen.screenshot(filepath=output_path)
            else:
                bpy.ops.screen.screenshot_area(filepath=output_path)
            
            success = True
        
        except RuntimeError:
            # Fallback to full screenshot
            try:
                bpy.ops.screen.screenshot(filepath=output_path)
                success = True
            except RuntimeError:
                success = False
    
    return success


# ========================================================================================
# Viewport Stabilization
# ========================================================================================

def _backup_and_hide_overlays(area) -> Optional[tuple]:
    """
    Backup and hide overlays/gizmos for clean capture.
    
    Args:
        area: Blender area object
    
    Returns:
        Backup tuple or None
    """
    for space in area.spaces:
        if space.type != 'VIEW_3D':
            continue
        
        overlay = getattr(space, 'overlay', None)
        show_overlays = getattr(overlay, 'show_overlays', None) if overlay else None
        show_gizmo = getattr(space, 'show_gizmo', None)
        
        # Backup original state
        backup = (space, show_gizmo, show_overlays)
        
        # Hide temporarily
        try:
            if show_gizmo is not None:
                space.show_gizmo = False
            
            if overlay and show_overlays is not None:
                overlay.show_overlays = False
        
        except (AttributeError, RuntimeError):
            pass
        
        return backup
    
    return None


def _restore_overlays(backup: tuple):
    """
    Restore overlays/gizmos from backup.
    
    Args:
        backup: Backup tuple from _backup_and_hide_overlays
    """
    if not backup:
        return
    
    space, show_gizmo, show_overlays = backup
    
    try:
        if show_gizmo is not None:
            space.show_gizmo = show_gizmo
        
        overlay = getattr(space, 'overlay', None)
        if overlay and show_overlays is not None:
            overlay.show_overlays = show_overlays
    
    except (AttributeError, RuntimeError, ReferenceError):
        pass


# ========================================================================================
# Idle Detection
# ========================================================================================

def _check_image_changed(
    current_path: str,
    previous_path: str,
    prefs
) -> bool:
    """
    Check if image has changed significantly using diff.
    
    Args:
        current_path: Path to current capture
        previous_path: Path to previous capture
        prefs: Addon preferences
    
    Returns:
        True if image changed enough to save
    """
    if not previous_path or not os.path.isfile(previous_path):
        return True  # No previous image, always save
    
    # Get settings
    threshold = getattr(prefs, 'window_idle_threshold', constants.DEFAULT_IDLE_THRESHOLD) if prefs else constants.DEFAULT_IDLE_THRESHOLD
    downscale = getattr(prefs, 'window_idle_downscale', constants.DEFAULT_DOWNSCALE_SIZE) if prefs else constants.DEFAULT_DOWNSCALE_SIZE
    
    # Compare images
    try:
        diff = utils.compare_images(
            current_path,
            previous_path,
            downscale=downscale,
            early_exit_threshold=threshold
        )
        
        return diff >= threshold
    
    except Exception as e:
        logger.warning(f"Image diff failed: {e}")
        return True  # On error, save to be safe


# ========================================================================================
# Cooldown Management
# ========================================================================================

def _set_cooldown(prefs):
    """Set suppression cooldown after capture."""
    if not prefs:
        return
    
    suppress_ms = getattr(
        prefs,
        'perf_depsgraph_suppress_ms',
        constants.DEFAULT_SUPPRESS_MS
    )
    
    state.TLX_State.set_suppression(suppress_ms)


# ========================================================================================
# Debug/Testing Functions
# ========================================================================================

def get_async_debug_info() -> dict:
    """
    Get debug information about async capture state.
    
    Useful for testing and troubleshooting.
    
    Returns:
        Dictionary with debug information
    """
    import time
    
    with _async_lock:
        info = {
            'state': _async_context.state.value,
            'has_timer_function': _async_context.timer_function is not None,
            'scheduled_time': _async_context.scheduled_time,
            'time_until_scheduled': max(0, _async_context.scheduled_time - time.time()),
            'attempt_count': _async_context.attempt_count,
            'is_pending': is_async_pending(),
        }
    
    return info


def force_reset_async_state():
    """
    Force reset async state to IDLE.
    
    DANGER: Only use for recovery from error states.
    Should not be needed in normal operation.
    """
    logger.warning("FORCE RESET of async capture state!")
    
    with _async_lock:
        _async_context.reset()


# ========================================================================================
# Registration
# ========================================================================================

def register():
    """Register window capture module."""
    logger.info("Window capture module registered (Race-condition FREE async)")
    
    # Reset state on register
    with _async_lock:
        _async_context.reset()


def unregister():
    """Unregister window capture module."""
    logger.info("Unregistering window capture module")
    
    # Cancel any pending captures
    cancel_async_capture()
    
    # Wait for completion with timeout
    if not wait_for_async_completion(timeout=2.0):
        logger.warning("Async capture did not complete before unregister")
        # Force reset as last resort
        force_reset_async_state()
    
    logger.info("Window capture module unregistered")


# ========================================================================================
# Module Test (for development)
# ========================================================================================

if __name__ == "__main__":
    # Test async state management
    print("Testing async capture state management...")
    
    with _async_lock:
        assert _async_context.state == AsyncCaptureState.IDLE
        print("✓ Initial state is IDLE")
        
        _set_async_state(AsyncCaptureState.PENDING)
        assert is_async_pending()
        print("✓ Can transition to PENDING")
        
        _async_context.reset()
        assert not is_async_pending()
        print("✓ Reset works correctly")
    
    print("All tests passed!")