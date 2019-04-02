#!/usr/bin/env python

from gimpfu import *
import gtk
import os
import re

def copy_layer_data_and_remove_old(img, old_layer_id, new_layer_id):
    """Copies the settings from the layer old_layer_id to the layer new_layer_id
    and removes the old layer."""

    # Copy layer data.
    offsets = pdb.gimp_drawable_offsets(old_layer_id)
    pdb.gimp_layer_set_offsets(new_layer_id, offsets[0], offsets[1])

    pdb.gimp_item_set_linked(new_layer_id, pdb.gimp_item_get_linked(old_layer_id))
    pdb.gimp_layer_set_lock_alpha(new_layer_id, pdb.gimp_layer_get_lock_alpha(old_layer_id))
    layer_mask = pdb.gimp_layer_get_mask(old_layer_id)
    if layer_mask != None:
      (old_width, old_height) = (pdb.gimp_drawable_width(old_layer_id), pdb.gimp_drawable_height(old_layer_id))
      (new_width, new_height) = (pdb.gimp_drawable_width(new_layer_id), pdb.gimp_drawable_height(new_layer_id))
      if old_width != new_width or old_height != new_height:
        # Resize the old layer; the mask will get resized with it.
        pdb.gimp_layer_resize(old_layer_id, new_width, new_height, 0, 0)
        layer_mask = pdb.gimp_layer_get_mask(old_layer_id)

      pdb.gimp_image_select_item(img, CHANNEL_OP_REPLACE, layer_mask)
      new_layer_mask = pdb.gimp_layer_create_mask(new_layer_id, ADD_SELECTION_MASK)
      pdb.gimp_layer_add_mask(new_layer_id, new_layer_mask)

      pdb.gimp_layer_set_apply_mask(new_layer_id, pdb.gimp_layer_get_apply_mask(old_layer_id))
      pdb.gimp_layer_set_edit_mask(new_layer_id, pdb.gimp_layer_get_edit_mask(old_layer_id))
      pdb.gimp_layer_set_show_mask(new_layer_id, pdb.gimp_layer_get_show_mask(old_layer_id))
    pdb.gimp_layer_set_mode(new_layer_id, pdb.gimp_layer_get_mode(old_layer_id))
    pdb.gimp_layer_set_opacity(new_layer_id, pdb.gimp_layer_get_opacity(old_layer_id))
    pdb.gimp_item_set_tattoo(new_layer_id, pdb.gimp_item_get_tattoo(old_layer_id))
    pdb.gimp_layer_set_visible(new_layer_id, pdb.gimp_layer_get_visible(old_layer_id))

    # Delete the old layer and rename the new one.
    old_layer_name = pdb.gimp_item_get_name(old_layer_id)
    pdb.gimp_image_remove_layer(img, old_layer_id)
    pdb.gimp_item_set_name(new_layer_id, old_layer_name)

    pdb.gimp_displays_flush()

def apply_effects(layer, effect_spec):
    # Apply special effects (mirroring).
    if "rotR" in effect_spec:
        layer = pdb.gimp_item_transform_rotate_simple(layer, ROTATE_90, True, 0, 0)
    elif "rotL" in effect_spec:
        layer = pdb.gimp_item_transform_rotate_simple(layer, ROTATE_270, True, 0, 0)
    elif "rot180" in effect_spec:
        layer = pdb.gimp_item_transform_rotate_simple(layer, ROTATE_180, True, 0, 0)

    if "flipH" in effect_spec:
        layer = pdb.gimp_item_transform_flip_simple(layer, ORIENTATION_HORIZONTAL, True, 0)
    if "flipV" in effect_spec:
        layer = pdb.gimp_item_transform_flip_simple(layer, ORIENTATION_VERTICAL, True, 0)
    return layer

def replace_layer(img, active_layer_id, pasted_layer_id, effects):
    """Replaces the layer active_layer_id by the layer pasted_layer_id, optionally resizing it to preserve
    aspect ratio and preserving the old layer's settings such as offset, opacity, and layer mask."""

    (width, height) = (pdb.gimp_drawable_width(active_layer_id), pdb.gimp_drawable_height(active_layer_id))
    if "rotR" not in effects and "rotL" not in effects:
      (pasted_width, pasted_height) = (pdb.gimp_drawable_width(pasted_layer_id), pdb.gimp_drawable_height(pasted_layer_id))
    else:
      (pasted_height, pasted_width) = (pdb.gimp_drawable_width(pasted_layer_id), pdb.gimp_drawable_height(pasted_layer_id))
    if (pasted_width == 0 or pasted_height == 0):
       return
    calculated_width = int(round(float(height)/pasted_height * pasted_width))
    calculated_height = int(round(float(width)/pasted_width * pasted_height))

    # Warn the user if the new layer's aspect ratio do not match that of the old layer.
    if calculated_width != width and calculated_height != height and "stretch" not in effects:
      label = gtk.Label("The aspect ratio of the clipboard contents does not match the aspect ratio of the currently selected layer."
        + os.linesep + "Clipboard content size is %dx%d, active layer size is %dx%d." % (pasted_width, pasted_height, width, height))
      dialog = gtk.Dialog("New aspect ratio", None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_NO_SEPARATOR, None)
      dialog.vbox.pack_start(label)
      label.show()
      dialog.add_button("Resize horizontally (new size: %dx%d)" % (calculated_width, height), 1)
      dialog.add_button("Resize vertically (new size: %dx%d)" % (width, calculated_height), 2)
      dialog.add_button("Keep dimensions (stretch)", 3)
      dialog.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
      dialog.set_default_response(3)
      response = dialog.run()
      dialog.destroy()

      if response == 1:
        width = calculated_width
      elif response == 2:
        height = calculated_height
      elif response == 3:
        pass
      else:
        pdb.gimp_image_remove_layer(img, pasted_layer_id)
        return

    # Insert the new layer above the existing one.
    old_layer_pos = pdb.gimp_image_get_item_position(img, active_layer_id)
    pdb.gimp_image_reorder_item(img, pasted_layer_id, active_layer_id.parent, old_layer_pos)
    pasted_layer_id = apply_effects(pasted_layer_id, effects)
    pdb.gimp_layer_scale(pasted_layer_id, width, height, True)

    copy_layer_data_and_remove_old(img, active_layer_id, pasted_layer_id)

def get_layer_file_data(img, layer_id):
  # Try to interpret the layer name as a relative or absolute file path.
  # Ignore everything after the first '#' or '@' character.
  match = re.match(r'([^#@]*)(@[^#]*)?(#.*)?', pdb.gimp_item_get_name(layer_id))
  layer_path = match.group(1).strip()
  layer_path_msg = ""
  selection = match.group(2)[1:].strip() if match.group(2) is not None else ""
  extras = match.group(3) if match.group(3) is not None else ""

  if not os.path.isabs(layer_path):
    image_filename = pdb.gimp_image_get_filename(img)
    if image_filename == None:
      layer_path = None
      layer_path_msg = "Layer name is not an absolute path, and the image has no file name."
    layer_path = os.path.join(os.path.dirname(image_filename), layer_path)

  if not os.path.isfile(layer_path):
    layer_path_msg = "{}: File not found".format(layer_path)
    layer_path = None

  return (layer_path, layer_path_msg, selection, extras)


def image_reload_layer(img, drawable):
  active_layer_id = pdb.gimp_image_get_active_layer(img)
  if active_layer_id == -1:
    pdb.gimp_message("Please select a layer.")
    return
  image_reload_layer_rec(img, active_layer_id)

def image_reload_layer_rec(img, active_layer_id):
  for c in active_layer_id.children:
    image_reload_layer_rec(img, c)

  (layer_path, layer_path_msg, selection, extras) = get_layer_file_data(img, active_layer_id)
  if layer_path is None:
    pdb.gimp_message(layer_path_msg)
    return

  pdb.gimp_context_push()

  pdb.gimp_image_undo_group_start(img)
  sel = pdb.gimp_selection_save(img)
  pdb.gimp_selection_none(img)
  try:
    loaded_img = pdb.gimp_file_load(layer_path, layer_path)
    if len(selection):
      paths = [p for p in loaded_img.vectors if p.name == selection]
      if not len(paths):
        pdb.gimp_message("\"%s\": Path not found" % selection)
        pdb.gimp_image_delete(loaded_img)
        return
      pdb.gimp_image_select_item(loaded_img, CHANNEL_OP_REPLACE, paths[0])
    else:
      pdb.gimp_selection_none(loaded_img)
    pdb.gimp_edit_named_copy_visible(loaded_img, "ReloadLayerTemp")
    new_layer = pdb.gimp_edit_named_paste(active_layer_id, "ReloadLayerTemp", False)
    pdb.gimp_floating_sel_to_layer(new_layer)
    replace_layer(img, active_layer_id, new_layer, extras)
    pdb.gimp_buffer_delete("ReloadLayerTemp")
    pdb.gimp_image_delete(loaded_img)
  finally:
    pdb.gimp_image_select_item(img, CHANNEL_OP_REPLACE, sel)
    pdb.gimp_image_remove_channel(img, sel)
    pdb.gimp_image_undo_group_end(img)
    pdb.gimp_context_pop()

def image_replace_layer_with_clipboard(img, drawable):
  active_layer_id = pdb.gimp_image_get_active_layer(img)
  if active_layer_id == -1:
    pdb.gimp_message("Please select a layer.")
    return

  active_layer_name = pdb.gimp_item_get_name(active_layer_id)
  split_layer_name = active_layer_name.split("#", 1)
  extras = split_layer_name[1] if len(split_layer_name) > 1 else ""

  pdb.gimp_context_push()
  pdb.gimp_context_set_interpolation(INTERPOLATION_LANCZOS)

  pdb.gimp_image_undo_group_start(img)
  sel = pdb.gimp_selection_save(img)
  pdb.gimp_selection_none(img)
  try:
    tmp_image = pdb.gimp_edit_paste_as_new(img)
    drawable = pdb.gimp_image_get_active_drawable(tmp_image)
    new_layer_id = pdb.gimp_layer_new_from_drawable(drawable, img)
    pdb.gimp_image_insert_layer(img, new_layer_id, None, 0)
    replace_layer(img, active_layer_id, new_layer_id, extras)
  finally:
    pdb.gimp_image_select_item(img, CHANNEL_OP_REPLACE, sel)
    pdb.gimp_image_undo_group_end(img)
    pdb.gimp_context_pop()

def image_open_layer_file(img, drawable):
  active_layer_id = pdb.gimp_image_get_active_layer(img)
  if active_layer_id == -1:
    pdb.gimp_message("Please select a layer.")
    return

  (layer_path, layer_path_msg, selection, extras) = get_layer_file_data(img, active_layer_id)
  if layer_path is None:
    pdb.gimp_message(layer_path_msg)
    return

  for img_no in range(0, pdb.gimp_image_list()[0]):
    img = gimp.image_list()[img_no]
    name = pdb.gimp_image_get_filename(img)
    if name is None:
      continue
    if os.path.samefile(name, layer_path):
      gimp.Display(img)
      pdb.gimp_displays_flush()
      return

  img = pdb.gimp_file_load(layer_path, layer_path, run_mode = RUN_NONINTERACTIVE)
  gimp.Display(img)
  pdb.gimp_displays_flush()

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

register(
  "image-open-layer-file",
  "Open layer file",
  "Open the file whose file name is specified by the active layer.",
  "Johannes",
  "(C) 2015",
  "11/04/2015",
  "<Image>/Layer/Open layer file",
  "*",
  [],
  [],
  image_open_layer_file
)

main()
