#!/usr/bin/env python

from gimpfu import *
import os

def image_reload_layer(img, drawable):
  active_layer_id = pdb.gimp_image_get_active_layer(img)
  if active_layer_id == -1:
    pdb.gimp_message("Please select a layer.")
    return
  active_layer_name = pdb.gimp_item_get_name(active_layer_id)

  # Try to interpret the layer name as a relative or absolute file path.
  layer_path = active_layer_name

  if not os.path.isabs(layer_path):
    image_filename = pdb.gimp_image_get_filename(img)
    if image_filename == None:
      pdb.gimp_message("Layer name is not an absolute path, and the image has no file name.")
      return
    layer_path = os.path.join(os.path.dirname(image_filename), layer_path)

  if not os.path.isfile(layer_path):
    pdb.gimp_message(layer_path + ": File not found.")
    return

  pdb.gimp_image_undo_group_start(img)
  try:
    new_layer_id = pdb.gimp_file_load_layer(img, layer_path, run_mode = 1)

    # Insert the new layer above the existing one.
    pdb.gimp_image_insert_layer(img, new_layer_id, None, -1)
 
    # Copy layer data.
    pdb.gimp_item_set_linked(new_layer_id, pdb.gimp_item_get_linked(active_layer_id))
    pdb.gimp_layer_set_lock_alpha(new_layer_id, pdb.gimp_layer_get_lock_alpha(active_layer_id))
    layer_mask = pdb.gimp_layer_get_mask(active_layer_id)
    if layer_mask != None:
      pdb.gimp_layer_add_mask(new_layer_id, pdb.gimp_channel_copy(pdb.gimp_layer_get_mask(active_layer_id)))
      pdb.gimp_layer_set_apply_mask(new_layer_id, pdb.gimp_layer_get_apply_mask(active_layer_id))
      pdb.gimp_layer_set_edit_mask(new_layer_id, pdb.gimp_layer_get_edit_mask(active_layer_id))
      pdb.gimp_layer_set_show_mask(new_layer_id, pdb.gimp_layer_get_show_mask(active_layer_id))
    pdb.gimp_layer_set_mode(new_layer_id, pdb.gimp_layer_get_mode(active_layer_id))
    pdb.gimp_layer_set_opacity(new_layer_id, pdb.gimp_layer_get_opacity(active_layer_id))
    pdb.gimp_item_set_tattoo(new_layer_id, pdb.gimp_item_get_tattoo(active_layer_id))
    pdb.gimp_layer_set_visible(new_layer_id, pdb.gimp_layer_get_visible(active_layer_id))
    offsets = pdb.gimp_drawable_offsets(active_layer_id)
    pdb.gimp_layer_set_offsets(new_layer_id, offsets[0], offsets[1])

    # Delete the old layer and rename the new one (it could have been named ... #1).
    pdb.gimp_image_remove_layer(img, active_layer_id)
    pdb.gimp_item_set_name(new_layer_id, active_layer_name)
  finally:
    pdb.gimp_image_undo_group_end(img)

register(
  "image-reload-layer",
  "Reload active layer",
  "Reload the active layer (layer name == file name).",
  "Johannes",
  "(C) 2013",
  "12/19/2013",
  "<Image>/Layer/Reload active layer",
  "*",
  [],
  [],
  image_reload_layer
)

main()
