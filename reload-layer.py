#!/usr/bin/env python

from gimpfu import *
import gtk
import os

def copy_layer_data_and_remove_old(img, old_layer_id, new_layer_id):
    """Copys the settings from the layer old_layer_id to the layer new_layer_id
    and removes the old layer."""

    # Copy layer data.
    pdb.gimp_item_set_linked(new_layer_id, pdb.gimp_item_get_linked(old_layer_id))
    pdb.gimp_layer_set_lock_alpha(new_layer_id, pdb.gimp_layer_get_lock_alpha(old_layer_id))
    layer_mask = pdb.gimp_layer_get_mask(old_layer_id)
    if layer_mask != None:
      (old_width, old_height) = (pdb.gimp_drawable_width(old_layer_id), pdb.gimp_drawable_height(old_layer_id))
      (new_width, new_height) = (pdb.gimp_drawable_width(new_layer_id), pdb.gimp_drawable_height(new_layer_id))
      if old_width != new_width or old_height != new_height:
        # Resize the old layer; the mask will get resized with it.
        pdb.gimp_layer_resize(old_layer_id, new_width, new_height, 0, 0)

      new_layer_mask = pdb.gimp_channel_copy(layer_mask)
      pdb.gimp_layer_add_mask(new_layer_id, new_layer_mask)
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

def apply_effects(layer, effect_spec):
    # Apply special effects (mirroring).
    if "flipH" in effect_spec:
        layer = pdb.gimp_item_transform_flip_simple(layer, ORIENTATION_HORIZONTAL, True, 0)
    if "flipV" in effect_spec:
        layer = pdb.gimp_item_transform_flip_simple(layer, ORIENTATION_VERTICAL, True, 0)
    return layer

def replace_layer(img, active_layer_id, pasted_layer_id, effects):
    """Replaces the layer active_layer_id by the layer pasted_layer_id, optionally resizing it to preserve
    aspect ratio and preserving the old layer's settings such as offset, opacity, and layer mask."""

    (width, height) = (pdb.gimp_drawable_width(active_layer_id), pdb.gimp_drawable_height(active_layer_id))
    (pasted_width, pasted_height) = (pdb.gimp_drawable_width(pasted_layer_id), pdb.gimp_drawable_height(pasted_layer_id))
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
      dialog.add_button("Keep dimensions", 3)
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
        return

    # Insert the new layer above the existing one.
    pdb.gimp_image_insert_layer(img, pasted_layer_id, None, -1)
    pdb.gimp_layer_scale(pasted_layer_id, width, height, True)
    pasted_layer_id = apply_effects(pasted_layer_id, effects)

    copy_layer_data_and_remove_old(img, active_layer_id, pasted_layer_id)


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
    replace_layer(img, active_layer_id, new_layer_id, extras)
  finally:
    pdb.gimp_image_undo_group_end(img)

def image_replace_layer_with_clipboard(img, drawable):
  active_layer_id = pdb.gimp_image_get_active_layer(img)
  if active_layer_id == -1:
    pdb.gimp_message("Please select a layer.")
    return

  active_layer_name = pdb.gimp_item_get_name(active_layer_id)
  split_layer_name = active_layer_name.split("#", 1)
  extras = split_layer_name[1] if len(split_layer_name) > 1 else ""

  pdb.gimp_image_undo_group_start(img)
  pdb.gimp_context_set_interpolation(INTERPOLATION_LANCZOS)
  try:
    tmp_image = pdb.gimp_edit_paste_as_new(img)
    drawable = pdb.gimp_image_get_active_drawable(tmp_image)
    new_layer_id = pdb.gimp_layer_new_from_drawable(drawable, img)
    replace_layer(img, active_layer_id, new_layer_id, extras)
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
