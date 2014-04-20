#!/usr/bin/env python

from gimpfu import *
import os

def replace_layer(img, old_layer_id, new_layer_id):
    """Replaces the layer old_layer_id by the layer new_layer_id, preserving the old layer's
    settings such as offset, opacity, and layer mask."""

    # Copy layer data.
    pdb.gimp_item_set_linked(new_layer_id, pdb.gimp_item_get_linked(old_layer_id))
    pdb.gimp_layer_set_lock_alpha(new_layer_id, pdb.gimp_layer_get_lock_alpha(old_layer_id))
    layer_mask = pdb.gimp_layer_get_mask(old_layer_id)
    if layer_mask != None:
      pdb.gimp_layer_add_mask(new_layer_id, pdb.gimp_channel_copy(pdb.gimp_layer_get_mask(old_layer_id)))
      pdb.gimp_layer_set_apply_mask(new_layer_id, pdb.gimp_layer_get_apply_mask(old_layer_id))
      pdb.gimp_layer_set_edit_mask(new_layer_id, pdb.gimp_layer_get_edit_mask(old_layer_id))
      pdb.gimp_layer_set_show_mask(new_layer_id, pdb.gimp_layer_get_show_mask(old_layer_id))
    pdb.gimp_layer_set_mode(new_layer_id, pdb.gimp_layer_get_mode(old_layer_id))
    pdb.gimp_layer_set_opacity(new_layer_id, pdb.gimp_layer_get_opacity(old_layer_id))
    pdb.gimp_item_set_tattoo(new_layer_id, pdb.gimp_item_get_tattoo(old_layer_id))
    pdb.gimp_layer_set_visible(new_layer_id, pdb.gimp_layer_get_visible(old_layer_id))
    offsets = pdb.gimp_drawable_offsets(old_layer_id)
    pdb.gimp_layer_set_offsets(new_layer_id, offsets[0], offsets[1])

    # Delete the old layer and rename the new one.
    old_layer_name = pdb.gimp_item_get_name(old_layer_id)
    pdb.gimp_image_remove_layer(img, old_layer_id)
    pdb.gimp_item_set_name(new_layer_id, old_layer_name)

    pdb.gimp_displays_flush()


def image_reload_layer(img, drawable):
  active_layer_id = pdb.gimp_image_get_active_layer(img)
  if active_layer_id == -1:
    pdb.gimp_message("Please select a layer.")
    return
  active_layer_name = pdb.gimp_item_get_name(active_layer_id)

  # Try to interpret the layer name as a relative or absolute file path.
  # Ignore everything after the first '#' character.
  split_layer_name = active_layer_name.split("#", 1)
  layer_path = split_layer_name[0].strip()
  extras = split_layer_name[1] if len(split_layer_name) > 1 else ""

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

    # Apply special effects (mirroring).
    if "flipH" in extras:
      new_layer_id = pdb.gimp_item_transform_flip_simple(new_layer_id, ORIENTATION_HORIZONTAL, True, 0)
    if "flipV" in extras:
      new_layer_id = pdb.gimp_item_transform_flip_simple(new_layer_id, ORIENTATION_VERTICAL, True, 0)

    replace_layer(img, active_layer_id, new_layer_id)

  finally:
    pdb.gimp_image_undo_group_end(img)


def image_replace_layer_with_clipboard(img, drawable):
  active_layer = pdb.gimp_image_get_active_layer(img)
  if active_layer == -1:
    pdb.gimp_message("Please select a layer.")
    return

  pdb.gimp_image_undo_group_start(img)
  pdb.gimp_context_set_interpolation(INTERPOLATION_LANCZOS)
  try:
    (width, height) = (pdb.gimp_drawable_width(active_layer), pdb.gimp_drawable_height(active_layer))
    tmp_image = pdb.gimp_edit_paste_as_new(img)
    drawable = pdb.gimp_image_get_active_drawable(tmp_image)
    tmp_layer = pdb.gimp_layer_new_from_drawable(drawable, img)
    pdb.gimp_image_insert_layer(img, tmp_layer, None, -1)

    # TODO: Warn the user if the new layer's aspect ratio do not match that of the old layer.
    pdb.gimp_layer_scale(tmp_layer, width, height, True)

    replace_layer(img, active_layer, tmp_layer)
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

register(
  "image-replace-layer-with-clipboard",
  "Replace active layer with clipboard contents",
  "Replace the active layer with the clipboard contents, scaling them to the layer size.",
  "Johannes",
  "(C) 2014",
  "04/19/2014",
  "<Image>/Layer/Replace with clipboard contents",
  "*",
  [],
  [],
  image_replace_layer_with_clipboard
)


main()
