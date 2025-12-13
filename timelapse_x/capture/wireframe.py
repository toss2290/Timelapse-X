"""
Wireframe rendering module for Timelapse X addon - COMPLETE VERSION.
"""

import bpy
import logging
from typing import Tuple, Optional, List, Dict
from contextlib import contextmanager
from enum import Enum

from .. import utils

logger = logging.getLogger(__name__)


# ========================================================================================
# Resource Types for Tracking
# ========================================================================================

class ResourceType(Enum):
    """Types of Blender resources we track"""
    SCENE = "scene"
    MESH = "mesh"
    OBJECT = "object"
    LIGHT = "light"
    WORLD = "world"
    MATERIAL = "material"  # Added for object colors


# ========================================================================================
# Transaction-based Resource Management
# ========================================================================================

class ResourceTransaction:
    """
    Transaction manager for Blender resources.
    Ensures all-or-nothing semantics for resource creation.
    """
    
    def __init__(self, name: str = "Resource Transaction"):
        self.name = name
        self.resources: List[Tuple[ResourceType, object]] = []
        self.committed = False
        self._in_transaction = False
    
    def __enter__(self):
        self._in_transaction = True
        logger.debug(f"Transaction started: {self.name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._in_transaction = False
        
        if exc_type is not None:
            logger.error(
                f"Transaction failed: {self.name} - {exc_type.__name__}: {exc_val}"
            )
            self.rollback()
            return False
        
        if not self.committed:
            logger.warning(f"Transaction not committed: {self.name} - Rolling back")
            self.rollback()
        else:
            logger.debug(f"Transaction committed: {self.name}")
        
        return False
    
    def register(self, resource_type: ResourceType, resource: object):
        if not self._in_transaction:
            raise RuntimeError("Cannot register resource outside transaction")
        
        self.resources.append((resource_type, resource))
        logger.debug(
            f"Registered {resource_type.value}: "
            f"{getattr(resource, 'name', '<unnamed>')}"
        )
    
    def commit(self):
        if not self._in_transaction:
            raise RuntimeError("Cannot commit outside transaction")
        
        self.committed = True
        logger.debug(f"Transaction committed: {self.name} ({len(self.resources)} resources)")
    
    def rollback(self):
        logger.info(f"Rolling back transaction: {self.name}")
        
        for resource_type, resource in reversed(self.resources):
            self._cleanup_resource(resource_type, resource)
        
        self.resources.clear()
        logger.info(f"Rollback complete: {self.name}")
    
    def _cleanup_resource(self, resource_type: ResourceType, resource: object):
        try:
            resource_name = getattr(resource, 'name', '<unnamed>')
            
            if resource_type == ResourceType.SCENE:
                if resource.name in bpy.data.scenes:
                    bpy.data.scenes.remove(resource, do_unlink=True)
                    logger.debug(f"Cleaned up scene: {resource_name}")
            
            elif resource_type == ResourceType.MESH:
                if resource.name in bpy.data.meshes:
                    bpy.data.meshes.remove(resource, do_unlink=True)
                    logger.debug(f"Cleaned up mesh: {resource_name}")
            
            elif resource_type == ResourceType.OBJECT:
                if resource.name in bpy.data.objects:
                    bpy.data.objects.remove(resource, do_unlink=True)
                    logger.debug(f"Cleaned up object: {resource_name}")
            
            elif resource_type == ResourceType.LIGHT:
                if resource.name in bpy.data.lights:
                    bpy.data.lights.remove(resource, do_unlink=True)
                    logger.debug(f"Cleaned up light: {resource_name}")
            
            elif resource_type == ResourceType.WORLD:
                if resource.name in bpy.data.worlds:
                    bpy.data.worlds.remove(resource, do_unlink=True)
                    logger.debug(f"Cleaned up world: {resource_name}")
            
            elif resource_type == ResourceType.MATERIAL:
                if resource.name in bpy.data.materials:
                    bpy.data.materials.remove(resource, do_unlink=True)
                    logger.debug(f"Cleaned up material: {resource_name}")
        
        except Exception as e:
            logger.warning(f"Failed to cleanup {resource_type.value}: {e}")


# ========================================================================================
# Enhanced Cleanup Manager
# ========================================================================================

class WireframeCleanupManager:
    """Manages cleanup of temporary wireframe rendering data."""
    
    def __init__(self):
        self.temp_scene = None
        self.created_meshes: List[object] = []
        self.created_objects: List[object] = []
        self.created_lights: List[object] = []
        self.created_materials: List[object] = []
        self.created_world = None
        self._cleanup_attempted = False
        
        self.stats = {
            'meshes_created': 0,
            'objects_created': 0,
            'lights_created': 0,
            'materials_created': 0,
            'meshes_cleaned': 0,
            'objects_cleaned': 0,
            'materials_cleaned': 0,
            'orphans_found': 0,
        }
    
    def register_scene(self, scene):
        self.temp_scene = scene
        logger.debug(f"Registered temp scene: {scene.name}")
    
    def register_mesh_object_pair(self, mesh, obj):
        if not mesh or not obj:
            raise ValueError("Both mesh and object must be provided")
        
        self.created_meshes.append(mesh)
        self.created_objects.append(obj)
        self.stats['meshes_created'] += 1
        self.stats['objects_created'] += 1
        
        logger.debug(
            f"Registered pair: mesh={mesh.name}, obj={obj.name}, users={mesh.users}"
        )
    
    def register_object(self, obj):
        if obj:
            self.created_objects.append(obj)
            self.stats['objects_created'] += 1
            logger.debug(f"Registered object: {obj.name}")
    
    def register_light(self, light):
        if light:
            self.created_lights.append(light)
            self.stats['lights_created'] += 1
            logger.debug(f"Registered light: {light.name}")
    
    def register_material(self, material):
        if material:
            self.created_materials.append(material)
            self.stats['materials_created'] += 1
            logger.debug(f"Registered material: {material.name}")
    
    def register_world(self, world):
        self.created_world = world
        logger.debug(f"Registered world: {world.name}")
    
    def cleanup(self):
        if self._cleanup_attempted:
            return
        
        self._cleanup_attempted = True
        
        logger.info("="*80)
        logger.info("WIREFRAME CLEANUP - MEMORY LEAK FREE VERSION")
        logger.info("="*80)
        
        # Remove temp scene
        if self.temp_scene:
            try:
                logger.info(f"Removing temp scene '{self.temp_scene.name}'...")
                bpy.data.scenes.remove(self.temp_scene, do_unlink=True)
                logger.info("✓ Scene removed")
            except Exception as e:
                logger.error(f"✗ Scene removal failed: {e}")
            finally:
                self.temp_scene = None
        
        # Force depsgraph update
        self._force_depsgraph_update()
        
        # Remove objects
        removed_obj = self._cleanup_objects()
        logger.info(f"Objects: {removed_obj} removed")
        
        # Remove meshes
        removed_mesh = self._cleanup_meshes()
        logger.info(f"Meshes: {removed_mesh} removed")
        
        # Remove materials
        removed_mat = self._cleanup_materials()
        if removed_mat > 0:
            logger.info(f"Materials: {removed_mat} removed")
        
        # Remove lights
        removed_lights = self._cleanup_lights()
        if removed_lights > 0:
            logger.info(f"Lights: {removed_lights} removed")
        
        # Remove world
        if self.created_world:
            try:
                world_name = self.created_world.name
                if world_name in bpy.data.worlds:
                    bpy.data.worlds.remove(self.created_world, do_unlink=True)
                    logger.info(f"✓ Removed world: {world_name}")
            except Exception as e:
                logger.error(f"✗ World removal error: {e}")
            finally:
                self.created_world = None
        
        # Orphan sweep
        orphan_count = self._sweep_orphans()
        if orphan_count > 0:
            logger.warning(f"⚠ Removed {orphan_count} orphaned blocks")
            self.stats['orphans_found'] = orphan_count
        
        # Verify cleanup
        remaining = self._verify_cleanup()
        
        if remaining > 0:
            logger.error(f"✗ CLEANUP INCOMPLETE: {remaining} blocks remain!")
        else:
            logger.info("✓✓ CLEANUP SUCCESSFUL - Zero leaks")
        
        logger.info(f"Statistics: {self.stats}")
        logger.info("="*80)
        logger.info("CLEANUP COMPLETE")
        logger.info("="*80 + "\n")
    
    def _force_depsgraph_update(self):
        try:
            for scene in bpy.data.scenes:
                scene.update_tag()
            if bpy.context.view_layer:
                bpy.context.view_layer.update()
        except:
            pass
    
    def _cleanup_objects(self) -> int:
        removed = 0
        for obj in self.created_objects:
            try:
                if obj and obj.name in bpy.data.objects:
                    bpy.data.objects.remove(obj, do_unlink=True)
                    removed += 1
            except:
                pass
        self.stats['objects_cleaned'] = removed
        return removed
    
    def _cleanup_meshes(self) -> int:
        removed = 0
        for mesh in self.created_meshes:
            try:
                if mesh and mesh.name in bpy.data.meshes:
                    bpy.data.meshes.remove(mesh, do_unlink=True)
                    removed += 1
            except:
                pass
        self.stats['meshes_cleaned'] = removed
        return removed
    
    def _cleanup_materials(self) -> int:
        removed = 0
        for mat in self.created_materials:
            try:
                if mat and mat.name in bpy.data.materials:
                    bpy.data.materials.remove(mat, do_unlink=True)
                    removed += 1
            except:
                pass
        self.stats['materials_cleaned'] = removed
        return removed
    
    def _cleanup_lights(self) -> int:
        removed = 0
        for light in self.created_lights:
            try:
                if light and light.name in bpy.data.lights:
                    bpy.data.lights.remove(light, do_unlink=True)
                    removed += 1
            except:
                pass
        return removed
    
    def _sweep_orphans(self) -> int:
        removed = 0
        
        # Orphan meshes
        for mesh in list(bpy.data.meshes):
            try:
                if mesh.name.startswith("TLX_WF_") and mesh.users == 0:
                    bpy.data.meshes.remove(mesh, do_unlink=True)
                    removed += 1
            except:
                pass
        
        # Orphan objects
        for obj in list(bpy.data.objects):
            try:
                if obj.name.startswith("TLX_WF_") and obj.users == 0:
                    bpy.data.objects.remove(obj, do_unlink=True)
                    removed += 1
            except:
                pass
        
        # Orphan materials
        for mat in list(bpy.data.materials):
            try:
                if mat.name.startswith("TLX_WF_") and mat.users == 0:
                    bpy.data.materials.remove(mat, do_unlink=True)
                    removed += 1
            except:
                pass
        
        return removed
    
    def _verify_cleanup(self) -> int:
        remaining = 0
        
        for mesh in bpy.data.meshes:
            if mesh.name.startswith("TLX_WF_"):
                remaining += 1
        
        for obj in bpy.data.objects:
            if obj.name.startswith("TLX_WF_"):
                remaining += 1
        
        for mat in bpy.data.materials:
            if mat.name.startswith("TLX_WF_"):
                remaining += 1
        
        return remaining


# ========================================================================================
# ATOMIC Mesh Copying
# ========================================================================================

def copy_mesh_atomic(
    src_obj,
    temp_scene,
    cleanup_mgr: WireframeCleanupManager
) -> Tuple[Optional[object], Optional[object]]:
    """Copy mesh with ATOMIC operations and GUARANTEED cleanup."""
    
    with ResourceTransaction(f"Copy mesh: {src_obj.name}") as txn:
        # Create mesh copy
        new_mesh = src_obj.data.copy()
        new_mesh.name = f"TLX_WF_{src_obj.data.name}"
        txn.register(ResourceType.MESH, new_mesh)
        
        # Create object
        new_obj = bpy.data.objects.new(
            f"TLX_WF_{src_obj.name}",
            new_mesh
        )
        txn.register(ResourceType.OBJECT, new_obj)
        
        # Link to scene
        temp_scene.collection.objects.link(new_obj)
        
        # Verify user count
        if new_mesh.users == 0:
            raise RuntimeError("Mesh orphaned after scene linking")
        
        # Copy transform
        new_obj.matrix_world = src_obj.matrix_world.copy()
        new_obj.hide_render = src_obj.hide_render
        
        # Register with cleanup manager
        cleanup_mgr.register_mesh_object_pair(new_mesh, new_obj)
        
        # Commit transaction
        txn.commit()
        
        return new_obj, new_mesh


def link_object_safe(
    src_obj,
    temp_scene,
    cleanup_mgr: WireframeCleanupManager
) -> Optional[object]:
    """Safely link object to temp scene (for cameras, lights, etc)."""
    
    with ResourceTransaction(f"Link object: {src_obj.name}") as txn:
        new_obj = bpy.data.objects.new(src_obj.name, src_obj.data)
        txn.register(ResourceType.OBJECT, new_obj)
        
        temp_scene.collection.objects.link(new_obj)
        
        new_obj.matrix_world = src_obj.matrix_world.copy()
        new_obj.hide_render = src_obj.hide_render
        
        cleanup_mgr.register_object(new_obj)
        
        txn.commit()
        
        return new_obj


# ========================================================================================
# Object Color Management
# ========================================================================================

def apply_object_colors(
    temp_scene,
    cleanup_mgr: WireframeCleanupManager,
    use_object_colors: bool = False,
    default_color: Tuple[float, float, float] = (1.0, 1.0, 1.0)
):
    """
    Apply colors to objects for rendering.
    
    Args:
        temp_scene: Temporary scene
        cleanup_mgr: Cleanup manager for tracking materials
        use_object_colors: If True, use each object's viewport display color
                          If False, use default_color for all objects
        default_color: RGB color to use when use_object_colors is False
    """
    print(f"\nApplying object colors (use_object_colors={use_object_colors})...")
    
    colored_count = 0
    
    for obj in temp_scene.objects:
        if obj.type != 'MESH':
            continue
        
        # Determine color to use
        if use_object_colors:
            # Use object's viewport display color
            color = obj.color[:3]  # Get RGB, ignore alpha
            color_name = f"TLX_WF_Color_{obj.name}"
        else:
            # Use default white color
            color = default_color
            color_name = f"TLX_WF_WhiteMat"
        
        # Create or reuse material
        mat = None
        
        # Check if material already exists (for efficiency when using default color)
        if not use_object_colors and color_name in bpy.data.materials:
            mat = bpy.data.materials[color_name]
        else:
            # Create new material
            mat = bpy.data.materials.new(name=color_name)
            mat.use_nodes = True
            
            # Register for cleanup
            cleanup_mgr.register_material(mat)
            
            # Setup material nodes
            nodes = mat.node_tree.nodes
            nodes.clear()
            
            # Create emission shader (shows in viewport and render)
            emission = nodes.new('ShaderNodeEmission')
            emission.inputs['Color'].default_value = (
                color[0], color[1], color[2], 1.0
            )
            emission.inputs['Strength'].default_value = 1.0
            
            # Create output node
            output = nodes.new('ShaderNodeOutputMaterial')
            
            # Connect
            mat.node_tree.links.new(
                emission.outputs['Emission'],
                output.inputs['Surface']
            )
        
        # Assign material to object
        if len(obj.data.materials) == 0:
            obj.data.materials.append(mat)
        else:
            obj.data.materials[0] = mat
        
        colored_count += 1
        
        logger.debug(
            f"Applied color to {obj.name}: "
            f"RGB({color[0]:.2f}, {color[1]:.2f}, {color[2]:.2f})"
        )
    
    print(f"✓ Applied colors to {colored_count} objects")


# ========================================================================================
# Main Render Function - COMPLETE with Object Colors
# ========================================================================================

def render_freestyle(
    output_path_noext: str,
    camera_obj,
    thickness: float = 1.0,
    color: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    bg_color: Optional[Tuple[float, float, float]] = None,
    bg_strength: float = 1.0,
    transparent_bg: bool = False,
    disable_shadows: bool = True,
    use_object_colors: bool = False,
    default_object_color: Tuple[float, float, float] = (1.0, 1.0, 1.0)
):
    """
    Render with Freestyle - COMPLETE with object color support.
    
    Args:
        output_path_noext: Output path without extension
        camera_obj: Camera object to render from
        thickness: Line thickness for Freestyle
        color: RGB color tuple for lines
        bg_color: RGB color tuple for background (None = Black)
        bg_strength: Background brightness (0.0 - 2.0)
        transparent_bg: Use transparent background instead of color
        disable_shadows: Disable shadow rendering
        use_object_colors: Use each object's viewport display color
        default_object_color: Default color when use_object_colors is False (white by default)
    """
    
    print("\n" + "="*80)
    print("FREESTYLE WIREFRAME RENDER - COMPLETE VERSION WITH OBJECT COLORS")
    print("="*80)
    
    if bg_color is None:
        bg_color = (1.0, 1.0, 1.0)
    
    source_scene = bpy.context.scene
    prefs = utils.get_addon_preferences()
    viewport_prefs = bpy.context.preferences.view
    
    # Backup viewport settings
    prev_display = getattr(viewport_prefs, 'render_display_type', 'WINDOW')
    prev_lock = getattr(viewport_prefs, 'use_lock_interface', False)
    
    # Create cleanup manager
    cleanup_mgr = WireframeCleanupManager()
    
    try:
        # ===== CREATE TEMP SCENE =====
        print("Creating temp scene...")
        temp_scene = bpy.data.scenes.new("TLX_Freestyle_Temp")
        cleanup_mgr.register_scene(temp_scene)
        
        # Setup background
        temp_scene.render.film_transparent = transparent_bg
        
        if not transparent_bg:
            world = bpy.data.worlds.new("TLX_Custom_World")
            temp_scene.world = world
            temp_scene.world.use_nodes = True
            cleanup_mgr.register_world(world)
            
            # Setup world nodes
            world_nodes = temp_scene.world.node_tree.nodes
            world_nodes.clear()
            
            bg_node = world_nodes.new('ShaderNodeBackground')
            bg_node.inputs['Color'].default_value = (
                bg_color[0], bg_color[1], bg_color[2], 1.0
            )
            bg_node.inputs['Strength'].default_value = bg_strength
            
            output_node = world_nodes.new('ShaderNodeOutputWorld')
            temp_scene.world.node_tree.links.new(
                bg_node.outputs['Background'],
                output_node.inputs['Surface']
            )
            
            print(f"✓ Background: RGB{bg_color}, Strength: {bg_strength:.2f}")
        else:
            temp_scene.world = None
            print("✓ Transparent background")
        
        # Copy render settings
        temp_scene.render.resolution_x = source_scene.render.resolution_x
        temp_scene.render.resolution_y = source_scene.render.resolution_y
        temp_scene.render.resolution_percentage = source_scene.render.resolution_percentage
        
        print(f"✓ Temp scene created: {temp_scene.name}")
        
        # ===== COPY OBJECTS =====
        print("\nCopying objects to temp scene...")
        
        object_map = {}
        successful_copies = 0
        
        for src_obj in source_scene.objects:
            if src_obj.type not in ('MESH', 'CAMERA', 'LIGHT', 'EMPTY'):
                continue
            
            if src_obj.hide_render and src_obj != camera_obj:
                continue
            
            if src_obj.type == 'MESH':
                # Use atomic mesh copy
                new_obj, new_mesh = copy_mesh_atomic(
                    src_obj,
                    temp_scene,
                    cleanup_mgr
                )
                
                if new_obj and new_mesh:
                    object_map[src_obj.name] = new_obj
                    successful_copies += 1
            else:
                # Link non-mesh objects
                new_obj = link_object_safe(src_obj, temp_scene, cleanup_mgr)
                
                if new_obj:
                    object_map[src_obj.name] = new_obj
                    successful_copies += 1
        
        print(f"✓ Objects copied: {successful_copies}")
        
        if successful_copies == 0:
            raise RuntimeError("No objects were successfully copied")
        
        # ===== APPLY OBJECT COLORS =====
        apply_object_colors(
            temp_scene,
            cleanup_mgr,
            use_object_colors=use_object_colors,
            default_color=default_object_color
        )
        
        # ===== MARK EDGES WITH FREESTYLE ATTRIBUTE =====
        print("\nMarking edges with freestyle_edge attribute...")
        
        marked_count = 0
        total_edges = 0
        
        for obj in temp_scene.objects:
            if obj.type != 'MESH' or obj.hide_render:
                continue
            
            mesh = obj.data
            num_edges = len(mesh.edges)
            
            if num_edges == 0:
                continue
            
            total_edges += num_edges
            
            # Create freestyle_edge attribute
            if "freestyle_edge" not in mesh.attributes:
                try:
                    attr = mesh.attributes.new(
                        name="freestyle_edge",
                        type='BOOLEAN',
                        domain='EDGE'
                    )
                except Exception as e:
                    logger.warning(f"Cannot create attribute for {obj.name}: {e}")
                    continue
            else:
                attr = mesh.attributes["freestyle_edge"]
            
            # Mark all edges as True
            try:
                attr.data.foreach_set("value", [True] * num_edges)
                marked_count += 1
            except Exception as e:
                logger.warning(f"Cannot mark edges for {obj.name}: {e}")
        
        print(f"✓ Marked {marked_count} objects with {total_edges} total edges")
        
        if marked_count == 0:
            logger.warning("No edges were marked - render may be empty!")
        
        # ===== SELECT RENDER ENGINE =====
        print("\nSelecting render engine...")
        
        available_engines = utils.get_available_engines()
        
        if 'CYCLES' in available_engines:
            selected_engine = 'CYCLES'
        elif 'BLENDER_EEVEE_NEXT' in available_engines:
            selected_engine = 'BLENDER_EEVEE_NEXT'
        elif 'BLENDER_EEVEE' in available_engines:
            selected_engine = 'BLENDER_EEVEE'
        else:
            selected_engine = 'BLENDER_WORKBENCH'
        
        temp_scene.render.engine = selected_engine
        print(f"✓ Using engine: {selected_engine}")
        
        # ===== ENABLE FREESTYLE =====
        print("\nEnabling Freestyle...")
        
        if not hasattr(temp_scene.render, 'use_freestyle'):
            raise RuntimeError("Freestyle not available in this Blender build")
        
        temp_scene.render.use_freestyle = True
        print("✓ Freestyle enabled")
        
        # ===== CONFIGURE VIEW LAYERS =====
        print("\nConfiguring view layers...")
        
        for view_layer in temp_scene.view_layers:
            view_layer.use_freestyle = True
            freestyle_settings = view_layer.freestyle_settings
            
            # Clear old linesets
            while freestyle_settings.linesets:
                freestyle_settings.linesets.remove(freestyle_settings.linesets[0])
            
            # Create new lineset
            lineset = freestyle_settings.linesets.new(name="TLX_EdgeMarks")
            
            # Configure to use edge marks
            lineset.select_edge_mark = True
            lineset.select_silhouette = False
            lineset.select_border = False
            lineset.select_crease = False
            lineset.select_contour = False
            lineset.select_external_contour = False
            lineset.select_material_boundary = False
            lineset.select_suggestive_contour = False
            lineset.select_ridge_valley = False
            
            # Set visibility
            try:
                lineset.visibility = 'VISIBLE'
            except:
                pass
            
            # Configure line style
            linestyle = lineset.linestyle
            linestyle.use_chaining = True
            linestyle.chaining = 'PLAIN'
            linestyle.use_same_object = False
            linestyle.thickness = float(thickness)
            linestyle.thickness_position = 'CENTER'
            linestyle.color = (float(color[0]), float(color[1]), float(color[2]))
            linestyle.alpha = 1.0
            linestyle.use_nodes = False
            
            print(f"✓ View layer configured:")
            print(f"  - Line thickness: {linestyle.thickness}")
            print(f"  - Line color: RGB{color}")
            print(f"  - Object colors: {'Enabled' if use_object_colors else 'White'}")
        
        # ===== IMAGE SETTINGS =====
        print("\nConfiguring image settings...")
        
        source_img = source_scene.render.image_settings
        temp_img = temp_scene.render.image_settings
        
        temp_img.file_format = source_img.file_format
        
        # Copy format-specific settings
        for attr in ['color_mode', 'quality', 'compression']:
            if hasattr(source_img, attr) and hasattr(temp_img, attr):
                try:
                    setattr(temp_img, attr, getattr(source_img, attr))
                except:
                    pass
        
        # Force RGBA if transparent
        if transparent_bg and hasattr(temp_img, 'color_mode'):
            temp_img.color_mode = 'RGBA'
        
        print(f"✓ Format: {temp_img.file_format}")
        
        # ===== SET OUTPUT PATH =====
        temp_scene.render.use_file_extension = True
        temp_scene.render.filepath = bpy.path.abspath(output_path_noext)
        print(f"✓ Output: {temp_scene.render.filepath}")
        
        # ===== SET CAMERA =====
        temp_camera = object_map.get(camera_obj.name) if camera_obj else None
        if temp_camera:
            temp_scene.camera = temp_camera
            print(f"✓ Camera: {temp_camera.name}")
        else:
            logger.warning("Camera not found in temp scene")
        
        # ===== OPTIMIZE RENDER SETTINGS =====
        print("\nOptimizing render settings...")
        
        temp_scene.render.use_simplify = True
        temp_scene.render.simplify_subdivision = 0
        
        if selected_engine == 'CYCLES':
            cycles = getattr(temp_scene, 'cycles', None)
            if cycles:
                if hasattr(cycles, 'samples'):
                    cycles.samples = 32
                if hasattr(cycles, 'use_denoising'):
                    cycles.use_denoising = False
                print("✓ Cycles: 32 samples, no denoising")
        
        elif selected_engine in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
            eevee = getattr(temp_scene, 'eevee', None)
            if eevee:
                if hasattr(eevee, 'taa_render_samples'):
                    eevee.taa_render_samples = 16
                print("✓ Eevee: 16 samples")
        
        # ===== DISABLE SHADOWS =====
        if disable_shadows:
            if selected_engine == 'CYCLES':
                cycles = getattr(temp_scene, 'cycles', None)
                if cycles and hasattr(cycles, 'max_bounces'):
                    cycles.max_bounces = 2
            
            elif selected_engine in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
                eevee = getattr(temp_scene, 'eevee', None)
                if eevee and hasattr(eevee, 'use_shadows'):
                    eevee.use_shadows = False
        
        # ===== LOCK VIEWPORT =====
        if hasattr(viewport_prefs, 'render_display_type'):
            viewport_prefs.render_display_type = 'NONE'
        if hasattr(viewport_prefs, 'use_lock_interface'):
            viewport_prefs.use_lock_interface = True
        
        # ===== RENDER! =====
        print(f"\n{'='*80}")
        print("RENDERING...")
        print('='*80)
        print(f"Engine: {temp_scene.render.engine}")
        print(f"Resolution: {temp_scene.render.resolution_x}x{temp_scene.render.resolution_y}")
        print(f"Marked objects: {marked_count}")
        print(f"Total edges: {total_edges}")
        print(f"Line thickness: {thickness}")
        print(f"Line color: RGB{color}")
        print(f"Object colors: {'Viewport colors' if use_object_colors else f'White RGB{default_object_color}'}")
        print(f"Background: {'Transparent' if transparent_bg else f'RGB{bg_color}'}")
        
        with bpy.context.temp_override(scene=temp_scene):
            try:
                # Update view layer
                bpy.context.view_layer.update()
            except Exception as e:
                logger.warning(f"View layer update warning: {e}")
            
            # ACTUALLY RENDER THE IMAGE
            bpy.ops.render.render(write_still=True, use_viewport=False)
        
        print("✓ Render complete!")
        print(f"\n{'='*80}")
        print("✓✓ FREESTYLE RENDER SUCCESS ✓✓")
        print('='*80 + "\n")
    
    except Exception as e:
        print(f"\n{'='*80}")
        print("✗✗ FREESTYLE RENDER FAILED ✗✗")
        print('='*80)
        print(f"Error: {e}")
        
        import traceback
        traceback.print_exc()
        
        raise RuntimeError(f"Wireframe render failed: {e}")
    
    finally:
        # ===== CLEANUP =====
        print("\n" + "="*80)
        print("CLEANUP PHASE")
        print("="*80)
        
        # Restore viewport
        try:
            if hasattr(viewport_prefs, 'render_display_type'):
                viewport_prefs.render_display_type = prev_display
            if hasattr(viewport_prefs, 'use_lock_interface'):
                viewport_prefs.use_lock_interface = prev_lock
            print("✓ Viewport settings restored")
        except:
            pass
        
        # Cleanup all data
        cleanup_mgr.cleanup()
        
        print("="*80 + "\n")


# ========================================================================================
# Utility Functions
# ========================================================================================

def check_for_leaks() -> Dict[str, int]:
    """Check for any TLX-related memory leaks."""
    leaks = {
        'scenes': 0,
        'meshes': 0,
        'objects': 0,
        'lights': 0,
        'worlds': 0,
        'materials': 0,
        'total': 0,
    }
    
    for scene in bpy.data.scenes:
        if scene.name.startswith("TLX_"):
            leaks['scenes'] += 1
    
    for mesh in bpy.data.meshes:
        if mesh.name.startswith("TLX_WF_"):
            leaks['meshes'] += 1
    
    for obj in bpy.data.objects:
        if obj.name.startswith("TLX_WF_"):
            leaks['objects'] += 1
    
    for light in bpy.data.lights:
        if light.name.startswith("TLX_"):
            leaks['lights'] += 1
    
    for world in bpy.data.worlds:
        if world.name.startswith("TLX_"):
            leaks['worlds'] += 1
    
    for mat in bpy.data.materials:
        if mat.name.startswith("TLX_WF_"):
            leaks['materials'] += 1
    
    leaks['total'] = sum(v for k, v in leaks.items() if k != 'total')
    
    return leaks


def cleanup_all_leaks() -> int:
    """Emergency cleanup - remove all TLX data blocks."""
    logger.warning("EMERGENCY CLEANUP - Removing all TLX data blocks")
    
    removed = 0
    
    for scene in list(bpy.data.scenes):
        if scene.name.startswith("TLX_"):
            try:
                bpy.data.scenes.remove(scene, do_unlink=True)
                removed += 1
            except:
                pass
    
    for obj in list(bpy.data.objects):
        if obj.name.startswith("TLX_WF_"):
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
                removed += 1
            except:
                pass
    
    for mesh in list(bpy.data.meshes):
        if mesh.name.startswith("TLX_WF_"):
            try:
                bpy.data.meshes.remove(mesh, do_unlink=True)
                removed += 1
            except:
                pass
    
    for mat in list(bpy.data.materials):
        if mat.name.startswith("TLX_WF_"):
            try:
                bpy.data.materials.remove(mat, do_unlink=True)
                removed += 1
            except:
                pass
    
    for light in list(bpy.data.lights):
        if light.name.startswith("TLX_"):
            try:
                bpy.data.lights.remove(light, do_unlink=True)
                removed += 1
            except:
                pass
    
    for world in list(bpy.data.worlds):
        if world.name.startswith("TLX_"):
            try:
                bpy.data.worlds.remove(world, do_unlink=True)
                removed += 1
            except:
                pass
    
    logger.info(f"Emergency cleanup removed {removed} blocks")
    return removed


@contextmanager
def safe_wireframe_render():
    """Context manager for safe wireframe rendering with guaranteed cleanup."""
    pre_leaks = check_for_leaks()
    if pre_leaks['total'] > 0:
        logger.warning(
            f"WARNING: {pre_leaks['total']} existing leaks detected before render"
        )
    
    try:
        yield
    finally:
        post_leaks = check_for_leaks()
        
        if post_leaks['total'] > pre_leaks['total']:
            new_leaks = post_leaks['total'] - pre_leaks['total']
            logger.error(f"✗ {new_leaks} new leaks detected!")
            
            logger.info("Attempting automatic cleanup...")
            removed = cleanup_all_leaks()
            logger.info(f"Cleaned up {removed} leaked blocks")
        else:
            logger.info("✓ No memory leaks detected")


# ========================================================================================
# Registration
# ========================================================================================

def register():
    """Register wireframe module."""
    logger.info("Wireframe module registered (MEMORY LEAK FREE + OBJECT COLORS)")
    
    # Check for leaks on registration
    leaks = check_for_leaks()
    if leaks['total'] > 0:
        logger.warning(
            f"Found {leaks['total']} existing leaks on registration. "
            f"Cleaning up..."
        )
        cleanup_all_leaks()


def unregister():
    """Unregister wireframe module."""
    logger.info("Unregistering wireframe module")
    
    # Final cleanup check
    leaks = check_for_leaks()
    if leaks['total'] > 0:
        logger.warning(
            f"Found {leaks['total']} leaks during unregister. "
            f"Cleaning up..."
        )
        cleanup_all_leaks()
    
    logger.info("Wireframe module unregistered")