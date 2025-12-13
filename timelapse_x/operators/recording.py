"""
Recording operators for Timelapse X addon.

"""

import bpy
import os
import time
import logging
from bpy.types import Operator
from bpy.props import BoolProperty, FloatProperty, EnumProperty

from .. import state
from .. import utils
from .. import constants
from .. import error_messages as err
from .. import progress

logger = logging.getLogger(__name__)

# Import capture modules
try:
    from ..capture import window as window_capture
    from ..capture import camera as camera_capture
    logger.info("Capture modules imported successfully")
except ImportError as e:
    window_capture = None
    camera_capture = None
    logger.error(f"Capture import failed: {e}")


# ========================================================================================
# Main Recording Operator
# ========================================================================================

class TLX_OT_record(Operator):
    """
    Start or stop timelapse recording.
    
    Enhanced with comprehensive validation, user-friendly error messages,
    and real-time progress tracking.
    """
    
    bl_idname = 'tlx.record'
    bl_label = 'Start / Stop Recording'
    bl_options = {'REGISTER'}
    
    start: BoolProperty(default=True)
    
    interval: FloatProperty(
        name='Interval (s)',
        min=0.0,
        max=3600.0,
        default=0.0
    )
    
    mode: EnumProperty(
        name='Mode',
        items=[
            ('DEFAULT', 'Use Scene Setting', ''),
            ('WINDOW', 'Blender Window', ''),
            ('CAMERA_LIST', 'Camera List', ''),
        ],
        default='DEFAULT'
    )
    
    def execute(self, context):
        """Execute recording start/stop with validation."""
        logger.info(f"Recording operator: start={self.start}, mode={self.mode}")
        
        scene = context.scene
        prefs = utils.get_addon_preferences()
        wm = context.window_manager
        
        # Validate preferences available
        if not prefs:
            error = err.create_error('no_preferences')
            error.report_to_user(self)
            return {'CANCELLED'}
        
        # Validate Blender version
        try:
            utils.validate_blender_version((4, 5, 0))
        except utils.ValidationError as e:
            err.report_validation_error(self, e, fallback_key='blender_version_old')
            return {'CANCELLED'}
        
        # Validate and fix intervals
        self._validate_intervals(scene, prefs)
        
        if self.start:
            return self._start_recording(context, scene, prefs, wm)
        else:
            return self._stop_recording(context, scene, wm)
    
    def _validate_intervals(self, scene, prefs):
        """Validate and fix interval values."""
        # Scene interval
        if hasattr(scene, 'tlx_capture_interval'):
            try:
                interval = float(scene.tlx_capture_interval)
                if interval <= constants.MIN_INTERVAL or interval > 3600:
                    logger.warning(f"Invalid scene interval {interval}, resetting")
                    scene.tlx_capture_interval = constants.DEFAULT_INTERVAL
            except (TypeError, ValueError):
                scene.tlx_capture_interval = constants.DEFAULT_INTERVAL
        
        # Preference interval
        if prefs:
            try:
                default_interval = float(getattr(prefs, 'default_interval', constants.DEFAULT_INTERVAL))
                if default_interval <= constants.MIN_INTERVAL or default_interval > 3600:
                    logger.warning(f"Invalid pref interval {default_interval}, resetting")
                    prefs.default_interval = constants.DEFAULT_INTERVAL
            except (TypeError, ValueError):
                prefs.default_interval = constants.DEFAULT_INTERVAL
    
    def _start_recording(self, context, scene, prefs, wm):
        """Start recording with comprehensive validation."""
        
        # Check if already recording
        if state.TLX_State.recording:
            logger.warning("Already recording")
            error = err.create_error('already_recording')
            error.report_to_user(self, report_type='INFO')
            return {'CANCELLED'}
        
        # Validate scene
        try:
            utils.validate_scene(scene)
        except utils.ValidationError as e:
            logger.error(f"Scene validation failed: {e}")
            err.report_validation_error(self, e)
            return {'CANCELLED'}
        
        # Determine capture mode
        capture_mode = self._get_capture_mode(scene)
        logger.info(f"Capture mode: {capture_mode}")
        
        # Validate mode requirements
        if not self._validate_mode_requirements(capture_mode, scene, prefs):
            return {'CANCELLED'}
        
        # Setup session with validation
        try:
            session_dir = self._setup_session(prefs)
            logger.info(f"Session directory: {session_dir}")
        except utils.ValidationError as e:
            logger.error(f"Session setup failed: {e}")
            error = err.create_technical_error(
                'cannot_create_directory',
                e,
                error=str(e)
            )
            error.report_to_user(self)
            return {'CANCELLED'}
        
        # Calculate base interval
        base_interval = self._calculate_base_interval(scene, prefs, capture_mode)
        logger.info(f"Base interval: {base_interval}s")
        
        # Validate interval
        if base_interval < constants.MIN_INTERVAL:
            logger.error(f"Interval too small: {base_interval}")
            error = err.create_error(
                'invalid_interval',
                value=base_interval,
                min=constants.MIN_INTERVAL,
                max=3600.0
            )
            error.report_to_user(self)
            return {'CANCELLED'}
        
        # Start state
        state.start_recording(capture_mode, session_dir)
        state.TLX_State.counter = 0
        state.TLX_State.dirty = True
        state.TLX_State.last_window_image = ""
        state.TLX_State.rr_index = 0
        state.set_window_async_pending(False)
        state.TLX_State.suppress_until = 0.0
        
        # Initialize recording progress tracker
        rec_progress = progress.get_recording_progress()
        rec_progress.start()
        
        logger.info(f"State initialized:")
        logger.info(f"  recording={state.TLX_State.recording}")
        logger.info(f"  paused={state.TLX_State.paused}")
        logger.info(f"  counter={state.TLX_State.counter}")
        logger.info(f"  dirty={state.TLX_State.dirty}")
        
        # Initialize camera schedulers if needed
        if capture_mode == 'CAMERA_LIST':
            try:
                self._init_camera_schedulers(scene, session_dir, prefs)
                
                # Update interval based on camera schedules
                if camera_capture:
                    camera_interval = camera_capture.compute_min_timer_interval(scene, prefs)
                    base_interval = min(base_interval, max(constants.MIN_INTERVAL, camera_interval))
                    logger.info(f"Adjusted interval for cameras: {base_interval}s")
            
            except Exception as e:
                logger.error(f"Camera scheduler initialization failed: {e}", exc_info=True)
                error = err.create_technical_error(
                    'capture_failed',
                    e,
                    error=str(e)
                )
                error.report_to_user(self)
                state.stop_recording()
                return {'CANCELLED'}
        
        base_interval = max(constants.MIN_INTERVAL, base_interval)
        
        # Add timer
        try:
            if context.window:
                state.TLX_State.timer = wm.event_timer_add(
                    base_interval,
                    window=context.window
                )
            else:
                state.TLX_State.timer = wm.event_timer_add(base_interval)
            
            logger.info(f"Timer added: {state.TLX_State.timer}")
        
        except Exception as e:
            logger.error(f"Timer creation failed: {e}", exc_info=True)
            error = err.create_technical_error(
                'timer_creation_failed',
                e,
                error=str(e)
            )
            error.report_to_user(self)
            state.stop_recording()
            return {'CANCELLED'}
        
        # Add modal handler
        wm.modal_handler_add(self)
        logger.info("Modal handler added")
        
        # Mark scene as recording
        scene.tlx_is_recording = True
        
        # Install depsgraph handler
        if prefs and prefs.idle_detection and not state.TLX_State.handler_installed:
            try:
                bpy.app.handlers.depsgraph_update_post.append(state.mark_scene_dirty)
                state.TLX_State.handler_installed = True
                logger.info("Depsgraph handler installed")
            except Exception as e:
                logger.warning(f"Depsgraph handler failed: {e}")
        
        # Immediate capture
        if prefs and getattr(prefs, 'capture_immediate_on_start', True):
            try:
                logger.info("Performing immediate capture...")
                self._immediate_capture(context, capture_mode, session_dir, prefs)
            except Exception as e:
                logger.error(f"Immediate capture failed: {e}", exc_info=True)
                # Don't cancel recording, just log
        
        logger.info("Recording started successfully!")
        
        # Success message
        err.report_success(
            self,
            'recording_started',
            interval=f"{base_interval:.1f}",
            mode=capture_mode
        )
        
        return {'RUNNING_MODAL'}
    
    def _validate_mode_requirements(self, capture_mode, scene, prefs):
        """
        Validate mode-specific requirements.
        
        Returns:
            True if validation passed, False if failed
        """
        # Validate CAMERA_LIST mode
        if capture_mode == 'CAMERA_LIST':
            try:
                utils.validate_camera_list(scene)
            except utils.ValidationError as e:
                logger.error(f"Camera list validation failed: {e}")
                err.report_validation_error(self, e, fallback_key='camera_list_empty')
                return False
        
        # Validate WINDOW mode
        if capture_mode == 'WINDOW':
            if utils.is_headless():
                logger.error("WINDOW mode in headless environment")
                error = err.create_error('headless_mode_window')
                error.report_to_user(self)
                return False
            
            # Validate UI context availability
            try:
                win, screen, area, region = utils.find_window_area_region(validate=True)
                if not all((win, screen, area, region)):
                    raise utils.ValidationError("No suitable UI context found")
            except utils.ValidationError as e:
                logger.error(f"UI context validation failed: {e}")
                error = err.create_error('no_ui_context')
                error.report_to_user(self)
                return False
        
        return True
    
    def _setup_session(self, prefs):
        """Setup session directory with validation."""
        # Get base directory
        if prefs and prefs.output_dir:
            base_root = prefs.output_dir
        else:
            base_root = '//Timelapse_Images'
        
        # Validate and create base directory
        try:
            base_root = utils.ensure_directory(base_root, validate_writable=True)
        except utils.ValidationError as e:
            raise utils.ValidationError(f"Cannot create base directory: {e}")
        
        # Check disk space (require 100MB minimum)
        try:
            utils.validate_disk_space(base_root, required_mb=100)
        except utils.ValidationError as e:
            logger.warning(f"Disk space warning: {e}")
            # Show warning but continue
            import re
            match = re.search(r'(\d+(?:\.\d+)?)MB available', str(e))
            if match:
                available = match.group(1)
                error = err.create_error(
                    'disk_almost_full',
                    available=available
                )
                error.report_to_user(self, report_type='WARNING')
        
        # Create session folder
        try:
            session_dir = utils.get_session_folder(base_root)
        except utils.ValidationError as e:
            raise utils.ValidationError(f"Cannot create session folder: {e}")
        
        return session_dir
    
    def _init_camera_schedulers(self, scene, session_dir, prefs):
        """Initialize camera schedulers with validation."""
        if not camera_capture:
            raise RuntimeError("Camera capture module not available")
        
        # Validate each camera before initialization
        for i, camera_item in enumerate(scene.tlx_cameras):
            if not camera_item.camera:
                logger.warning(f"Camera item {i} has no camera, skipping")
                continue
            
            try:
                utils.validate_camera(camera_item.camera)
            except utils.ValidationError as e:
                logger.warning(f"Camera {i} ({camera_item.camera.name}) invalid: {e}")
        
        # Initialize schedulers
        camera_capture.init_camera_schedulers(scene, session_dir, prefs)
    
    def _get_capture_mode(self, scene):
        """Get capture mode with fallback."""
        if self.mode == 'DEFAULT':
            return getattr(scene, 'tlx_capture_mode', 'CAMERA_LIST')
        return self.mode
    
    def _calculate_base_interval(self, scene, prefs, capture_mode):
        """Calculate base interval with validation."""
        if self.interval > 0.0:
            base_interval = float(self.interval)
        else:
            scene_interval = getattr(scene, 'tlx_capture_interval', None)
            pref_interval = prefs.default_interval if prefs else constants.DEFAULT_INTERVAL
            base_interval = float(scene_interval or pref_interval or constants.DEFAULT_INTERVAL)
        
        # Clamp to valid range
        base_interval = max(constants.MIN_INTERVAL, min(3600.0, base_interval))
        
        return base_interval
    
    def _immediate_capture(self, context, capture_mode, session_dir, prefs):
        """Perform immediate capture with error handling."""
        base_dir = session_dir
        
        try:
            if capture_mode == 'WINDOW':
                if not (prefs and prefs.window_capture_on_input_only):
                    if window_capture:
                        window_capture.capture_window_async(context, base_dir, force_save=True)
            
            else:  # CAMERA_LIST
                if camera_capture:
                    result = camera_capture.capture_cameras(
                        context,
                        base_dir,
                        require_dirty=False
                    )
                    
                    if result:
                        state.TLX_State.counter += 1
                        state.TLX_State.last_capture_time = time.time()
                        logger.info(f"Immediate capture successful. Counter: {state.TLX_State.counter}")
                        
                        # Update progress tracker
                        rec_progress = progress.get_recording_progress()
                        rec_progress.add_frame()
        
        except Exception as e:
            logger.error(f"Immediate capture failed: {e}", exc_info=True)
            raise
    
    def _stop_recording(self, context, scene, wm):
        """Stop recording with cleanup."""
        logger.info("Stopping recording")
        
        final_count = state.TLX_State.counter
        try:
            from ..capture import window
            window.cancel_async_capture()
        except:
            pass
        
        # Clear header text from all areas
        try:
            for window in wm.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.header_text_set(None)
        except Exception as e:
            logger.debug(f"Failed to clear headers: {e}")
        
        # Remove timer
        if state.TLX_State.timer:
            try:
                wm.event_timer_remove(state.TLX_State.timer)
            except Exception as e:
                logger.warning(f"Timer removal failed: {e}")
            finally:
                state.TLX_State.timer = None
        
        # Stop state
        state.stop_recording()
        scene.tlx_is_recording = False
        
        # Remove depsgraph handler
        if state.TLX_State.handler_installed:
            try:
                bpy.app.handlers.depsgraph_update_post.remove(state.mark_scene_dirty)
            except ValueError:
                pass
            finally:
                state.TLX_State.handler_installed = False
        
        # Cleanup camera metadata
        try:
            for camera_item in scene.tlx_cameras:
                keys_to_remove = [k for k in camera_item.keys() if k.startswith("_tlx_")]
                for key in keys_to_remove:
                    del camera_item[key]
        except Exception as e:
            logger.warning(f"Camera metadata cleanup failed: {e}")
        
        logger.info(f"Recording stopped. Total frames: {final_count}")
        
        # Success message
        err.report_success(self, 'recording_stopped', count=final_count)
        
        return {'FINISHED'}
    
    def modal(self, context, event):
        """Modal handler with error handling and progress display."""
        # Pass through non-timer events
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        
        # Timer tick
        logger.debug(f"TIMER TICK - recording={state.TLX_State.recording}, paused={state.TLX_State.paused}")
        
        # Check if still recording
        if not state.TLX_State.recording:
            return {'FINISHED'}
        
        # Update header with progress
        self._update_header_progress(context)
        
        # Skip if paused
        if state.TLX_State.paused:
            return {'RUNNING_MODAL'}
        
        scene = context.scene
        prefs = utils.get_addon_preferences()
        base_dir = state.TLX_State.session_dir
        
        # Validate session directory still exists
        if not base_dir or not os.path.exists(base_dir):
            logger.error("Session directory missing!")
            error = err.create_error('session_dir_missing')
            error.report_to_user(self)
            # Stop recording
            bpy.ops.tlx.record(start=False)
            return {'FINISHED'}
        
        # Capture with error handling
        try:
            if state.TLX_State.capture_mode == 'WINDOW':
                self._handle_window_tick(context, base_dir, prefs)
            else:
                self._handle_camera_tick(context, base_dir, prefs)
        
        except Exception as e:
            logger.error(f"Capture tick failed: {e}", exc_info=True)
            # Don't stop recording, just log error
        
        return {'RUNNING_MODAL'}
    
    def _update_header_progress(self, context):
        """Update area header with recording progress."""
        try:
            rec_progress = progress.get_recording_progress()
            header_text = rec_progress.get_header_text(state.TLX_State.capture_mode)
            
            # Update all 3D view areas
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.header_text_set(header_text)
        
        except Exception as e:
            logger.debug(f"Header update failed: {e}")
    
    def _handle_window_tick(self, context, base_dir, prefs):
        """Handle window capture tick."""
        if prefs and prefs.window_capture_on_input_only:
            return
        
        if window_capture:
            try:
                window_capture.capture_window_async(context, base_dir, force_save=False)
            except Exception as e:
                logger.error(f"Window capture failed: {e}", exc_info=True)
    
    def _handle_camera_tick(self, context, base_dir, prefs):
        """Handle camera capture tick with validation and progress tracking."""
        # Check idle detection
        if prefs and prefs.idle_detection:
            if not state.TLX_State.dirty:
                return
        
        # Capture
        if camera_capture:
            try:
                result = camera_capture.capture_cameras(
                    context,
                    base_dir,
                    require_dirty=True
                )
                
                if result:
                    state.TLX_State.mark_captured()
                    logger.debug(f"Captured! Counter: {state.TLX_State.counter}")
                    
                    # Update progress tracker
                    rec_progress = progress.get_recording_progress()
                    rec_progress.add_frame()
            
            except Exception as e:
                logger.error(f"Camera capture failed: {e}", exc_info=True)
                # Continue recording despite error


# ========================================================================================
# Pause/Resume Operator
# ========================================================================================

class TLX_OT_pause_resume(Operator):
    """Pause or resume recording with validation."""
    
    bl_idname = 'tlx.pause_resume'
    bl_label = 'Pause / Resume'
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        """Toggle pause state."""
        wm = context.window_manager
        scene = context.scene
        
        if not state.TLX_State.recording:
            self.report({'WARNING'}, 'Not recording.')
            return {'CANCELLED'}
        
        if not state.TLX_State.paused:
            # Pause
            if state.TLX_State.timer:
                try:
                    wm.event_timer_remove(state.TLX_State.timer)
                except Exception as e:
                    logger.warning(f"Timer removal failed: {e}")
                finally:
                    state.TLX_State.timer = None
            
            state.pause_recording()
            err.report_success(self, 'recording_paused')
        
        else:
            # Resume
            interval = max(
                constants.MIN_INTERVAL,
                float(getattr(scene, 'tlx_capture_interval', 2.0))
            )
            
            try:
                if context.window:
                    state.TLX_State.timer = wm.event_timer_add(interval, window=context.window)
                else:
                    state.TLX_State.timer = wm.event_timer_add(interval)
            except Exception as e:
                logger.error(f"Timer creation failed: {e}")
                error = err.create_technical_error(
                    'timer_creation_failed',
                    e,
                    error=str(e)
                )
                error.report_to_user(self)
                return {'CANCELLED'}
            
            state.resume_recording()
            err.report_success(self, 'recording_resumed', interval=f"{interval:.1f}")
        
        return {'FINISHED'}


# ========================================================================================
# Update Interval Operator
# ========================================================================================

class TLX_OT_update_interval(Operator):
    """Update capture interval with validation."""
    
    bl_idname = 'tlx.update_interval'
    bl_label = 'Apply Interval'
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        """Apply new interval."""
        scene = context.scene
        wm = context.window_manager
        
        # Validate interval
        try:
            interval = float(getattr(scene, 'tlx_capture_interval', 2.0))
            interval = max(constants.MIN_INTERVAL, min(3600.0, interval))
        except (TypeError, ValueError):
            error = err.create_error(
                'invalid_interval',
                value="invalid",
                min=constants.MIN_INTERVAL,
                max=3600.0
            )
            error.report_to_user(self)
            return {'CANCELLED'}
        
        if state.TLX_State.recording and not state.TLX_State.paused:
            # Remove old timer
            if state.TLX_State.timer:
                try:
                    wm.event_timer_remove(state.TLX_State.timer)
                except Exception as e:
                    logger.warning(f"Timer removal failed: {e}")
            
            # Add new timer
            try:
                if context.window:
                    state.TLX_State.timer = wm.event_timer_add(interval, window=context.window)
                else:
                    state.TLX_State.timer = wm.event_timer_add(interval)
            except Exception as e:
                logger.error(f"Timer creation failed: {e}")
                error = err.create_technical_error(
                    'timer_creation_failed',
                    e,
                    error=str(e)
                )
                error.report_to_user(self)
                return {'CANCELLED'}
            
            err.report_success(self, 'interval_updated', interval=f"{interval:.1f}")
        else:
            self.report({'INFO'}, f"Interval set to {interval:.1f}s")
        
        return {'FINISHED'}


# ========================================================================================
# Set Interval Preset Operator
# ========================================================================================

class TLX_OT_set_interval(Operator):
    """Set interval preset with validation."""
    
    bl_idname = 'tlx.set_interval'
    bl_label = 'Set Interval Preset'
    bl_options = {'REGISTER'}
    
    value: FloatProperty(
        name='Value',
        min=constants.MIN_INTERVAL,
        max=3600.0,
        default=constants.DEFAULT_INTERVAL
    )
    
    def execute(self, context):
        """Set interval value."""
        # Validate value
        value = max(constants.MIN_INTERVAL, min(3600.0, float(self.value)))
        
        context.scene.tlx_capture_interval = value
        
        if state.TLX_State.recording and not state.TLX_State.paused:
            bpy.ops.tlx.update_interval()
        
        return {'FINISHED'}


# ========================================================================================
# Registration
# ========================================================================================

classes = (
    TLX_OT_record,
    TLX_OT_pause_resume,
    TLX_OT_update_interval,
    TLX_OT_set_interval,
)


def register():
    """Register recording operators."""
    logger.info("Registering recording operators (with validation, errors & progress)")
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            logger.info(f"Registered: {cls.__name__}")
        except Exception as e:
            logger.error(f"Failed to register {cls.__name__}: {e}")


def unregister():
    """Unregister recording operators."""
    logger.info("Unregistering recording operators")
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            logger.warning(f"Failed to unregister {cls.__name__}: {e}")