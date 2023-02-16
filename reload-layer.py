#!/usr/bin/env python3

import os
import re
import sys

import gi

gi.require_version("Gimp", "3.0")
from gi.repository import Gimp

from gi.repository import GLib
from gi.repository import Gio

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


def copy_layer_data_and_remove_old(image, old_layer, new_layer):
    """Copies the settings from the layer old_layer to the layer new_layer
    and removes the old layer."""

    # Copy layer data.
    offsets = old_layer.get_offsets()
    new_layer.set_offsets(offsets.offset_x, offsets.offset_y)

    new_layer.set_lock_alpha(old_layer.get_lock_alpha())
    layer_mask = old_layer.get_mask()
    if layer_mask:
        (old_width, old_height) = (old_layer.get_width(), old_layer.get_height())
        (new_width, new_height) = (new_layer.get_width(), new_layer.get_height())
        if old_width != new_width or old_height != new_height:
            # Resize the old layer; the mask will get resized with it.
            old_layer.resize(new_width, new_height, 0, 0)
            layer_mask = old_layer.get_mask()

        image.select_item(Gimp.ChannelOps.REPLACE, layer_mask)
        new_layer_mask = new_layer.create_mask(Gimp.AddMaskType.SELECTION)
        new_layer.add_mask(new_layer_mask)

        new_layer.set_apply_mask(old_layer.get_apply_mask())
        new_layer.set_edit_mask(old_layer.get_edit_mask())
        new_layer.set_show_mask(old_layer.get_show_mask())
    new_layer.set_mode(old_layer.get_mode())
    new_layer.set_opacity(old_layer.get_opacity())
    new_layer.set_tattoo(old_layer.get_tattoo())
    new_layer.set_visible(old_layer.get_visible())

    # Delete the old layer and rename the new one.
    old_layer_name = old_layer.get_name()
    image.remove_layer(old_layer)
    new_layer.set_name(old_layer_name)

    Gimp.displays_flush()


def apply_effects(layer, effect_spec):
    # Apply special effects (mirroring).
    if "rotR" in effect_spec:
        layer = layer.transform_rotate_simple(Gimp.RotationType(0), True, 0, 0)
    elif "rotL" in effect_spec:
        layer = layer.transform_rotate_simple(Gimp.RotationType(2), True, 0, 0)
    elif "rot180" in effect_spec:
        layer = layer.transform_rotate_simple(Gimp.RotationType(1), True, 0, 0)

    if "flipH" in effect_spec:
        layer = layer.transform_flip_simple(Gimp.OrientationType.HORIZONTAL, True, 0)
    if "flipV" in effect_spec:
        layer = layer.transform_flip_simple(Gimp.OrientationType.VERTICAL, True, 0)
    return layer


def replace_layer(image, active_layer, pasted_layer, effects):
    """Replaces the layer active_layer by the layer pasted_layer, optionally resizing it to preserve
    aspect ratio and preserving the old layer's settings such as offset, opacity, and layer mask."""

    width, height = active_layer.get_width(), active_layer.get_height()
    if "rotR" not in effects and "rotL" not in effects:
        (pasted_width, pasted_height) = (
            pasted_layer.get_width(),
            pasted_layer.get_height(),
        )
    else:
        (pasted_height, pasted_width) = (
            pasted_layer.get_width(),
            pasted_layer.get_height(),
        )
    if pasted_width == 0 or pasted_height == 0:
        return
    calculated_width = int(round(float(height) / pasted_height * pasted_width))
    calculated_height = int(round(float(width) / pasted_width * pasted_height))

    # Warn the user if the new layer's aspect ratio do not match that of the old layer.
    if (
        calculated_width != width
        and calculated_height != height
        and "stretch" not in effects
    ):
        label = Gtk.Label(
            label="The aspect ratio of the clipboard contents does not match the aspect ratio of the currently selected layer."
            + os.linesep
            + "Clipboard content size is %dx%d, active layer size is %dx%d."
            % (pasted_width, pasted_height, width, height)
        )
        dialog = Gtk.Dialog(
            "New aspect ratio", None, None, modal=True, destroy_with_parent=True
        )
        dialog.vbox.pack_start(label, expand=True, fill=True, padding=0)
        label.show()
        dialog.add_button(
            "Resize horizontally (new size: %dx%d)" % (calculated_width, height), 1
        )
        dialog.add_button(
            "Resize vertically (new size: %dx%d)" % (width, calculated_height), 2
        )
        dialog.add_button("Keep dimensions (stretch)", 3)
        dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
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
            image.remove_layer(pasted_layer)
            return

    # Insert the new layer above the existing one.
    old_layer_pos = image.get_item_position(active_layer)
    image.reorder_item(pasted_layer, active_layer.get_parent(), old_layer_pos)
    pasted_layer = apply_effects(pasted_layer, effects)
    pasted_layer.scale(width, height, True)

    copy_layer_data_and_remove_old(image, active_layer, pasted_layer)


def get_layer_file_data(image, layer):
    # Try to interpret the layer name as a relative or absolute file path.
    # Ignore everything after the first '#' or '@' character.
    match = re.match(r"([^#@]*)(@[^#]*)?(#.*)?", layer.get_name())
    layer_path = match.group(1).strip()
    layer_path_msg = ""
    selection = match.group(2)[1:].strip() if match.group(2) is not None else ""
    extras = match.group(3) if match.group(3) is not None else ""

    if not os.path.isabs(layer_path):
        image_file = image.get_file()
        if not image_file or not image_file.get_path():
            layer_path = None
            layer_path_msg = (
                "Layer name is not an absolute path, and the image has no file name."
            )
        layer_path = os.path.join(os.path.dirname(image_file.get_path()), layer_path)

    if not os.path.isfile(layer_path):
        layer_path_msg = "{}: File not found".format(layer_path)
        layer_path = None

    return (layer_path, layer_path_msg, selection, extras)


def image_reload_layer(
    procedure, run_mode, image, num_drawables, drawables, args, data
):
    selected_layers = image.list_selected_layers()
    if len(selected_layers) != 1:
        return procedure.new_return_values(
            Gimp.PDBStatusType.CALLING_ERROR, GLib.Error("Please select a single layer.")
        )
    active_layer = selected_layers[0]

    Gimp.context_push()

    image.undo_group_start()
    sel = Gimp.Selection.save(image)
    Gimp.Selection.none(image)

    try:
        try:
            image_reload_layer_rec(image, active_layer)
        finally:
            image.select_item(Gimp.ChannelOps.REPLACE, sel)
            image.remove_channel(sel)
            image.undo_group_end()
            Gimp.context_pop()
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())
    except GLib.Error as e:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, e)


def image_reload_layer_rec(image, active_layer):
    for c in active_layer.list_children():
        if "#noreload" not in c.get_name():
            image_reload_layer_rec(image, c)

    (layer_path, layer_path_msg, selection, extras) = get_layer_file_data(
        image, active_layer
    )
    if not layer_path:
        raise GLib.Error(layer_path_msg)

    for loaded_image in Gimp.list_images():
        loaded_image_file = loaded_image.get_file()
        if not loaded_image_file:
            continue
        loaded_image_filename = loaded_image_file.get_path()
        if not loaded_image_filename:
            continue
        if os.path.samefile(loaded_image_filename, layer_path):
            break
    else:
        loaded_image = Gimp.file_load(
            Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(layer_path)
        )
    try:
        if selection:
            path = loaded_image.get_vectors_by_name(selection)
            if not path:
                raise GLib.Error('"%s": Path not found' % selection)
            loaded_image.select_item(Gimp.ChannelOps.REPLACE, path)
        else:
            Gimp.Selection.none(loaded_image)
        Gimp.edit_named_copy_visible(loaded_image, "ReloadLayerTemp")
        new_layer = Gimp.edit_named_paste(active_layer, "ReloadLayerTemp", False)
        Gimp.floating_sel_to_layer(new_layer)
        replace_layer(image, active_layer, new_layer, extras)
        Gimp.buffer_delete("ReloadLayerTemp")
    finally:
        loaded_image.delete()


def image_replace_layer_with_clipboard(
    procedure, run_mode, image, num_drawables, drawables, args, data
):
    selected_layers = image.list_selected_layers()
    if len(selected_layers) != 1:
        return procedure.new_return_values(
            Gimp.PDBStatusType.CALLING_ERROR, GLib.Error("Please select a single layer.")
        )
    active_layer = selected_layers[0]

    split_layer_name = active_layer.get_name().split("#", 1)
    extras = split_layer_name[1] if len(split_layer_name) > 1 else ""

    Gimp.context_push()
    Gimp.context_set_interpolation(Gimp.InterpolationType.NOHALO)

    image.undo_group_start()
    sel = Gimp.Selection.save(image)
    Gimp.Selection.none(image)
    try:
        tmp_image = Gimp.edit_paste_as_new_image()
        if not tmp_image:
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error("No data in clipboard.")
            )
        drawables = tmp_image.get_selected_drawables()
        if len(drawables) != 1:
            return procedure.new_return_values(
                Gimp.PDBStatusType.CALLING_ERROR, GLib.Error("Please select a single layer.")
            )
        new_layer = Gimp.Layer.new_from_drawable(drawables[0], image)
        image.insert_layer(new_layer, None, 0)
        replace_layer(image, active_layer, new_layer, extras)
        tmp_image.delete()
    finally:
        image.select_item(Gimp.ChannelOps.REPLACE, sel)
        image.undo_group_end()
        Gimp.context_pop()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def image_open_layer_file(
    procedure, run_mode, image, num_drawables, drawables, args, data
):
    selected_layers = image.list_selected_layers()
    if len(selected_layers) != 1:
        return procedure.new_return_values(
            Gimp.PDBStatusType.CALLING_ERROR, GLib.Error("Please select a single layer.")
        )
    active_layer = selected_layers[0]

    (layer_path, layer_path_msg, selection, extras) = get_layer_file_data(
        image, active_layer
    )
    if not layer_path:
        return procedure.new_return_values(
            Gimp.PDBStatusType.CALLING_ERROR, GLib.Error(layer_path_msg)
        )

    for image in Gimp.list_images():
        image_file = image.get_file()
        if not image_file:
            continue
        image_filename = image_file.get_path()
        if not image_filename:
            continue
        if os.path.samefile(image_filename, layer_path):
            break
    else:
        image = Gimp.file_load(
            Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(layer_path)
        )
    if image:
        Gimp.Display.new(image)
        Gimp.displays_flush()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class ReloadLayer(Gimp.PlugIn):
    ## GimpPlugIn virtual methods ##
    def do_query_procedures(self):
        return [
            "image-reload-layer",
            "image-replace-layer-with-clipboard",
            "image-open-layer-file",
        ]

    def do_create_procedure(self, name):
        if name == "image-reload-layer":
            procedure = Gimp.ImageProcedure.new(
                self, name, Gimp.PDBProcType.PLUGIN, image_reload_layer, None
            )
            procedure.set_image_types("*")
            procedure.set_documentation(
                "Reload active layer",
                "Reload the active layer (layer name == file name).",
                name,
            )
            procedure.set_menu_label("Reload active layer")
            procedure.add_menu_path("<Image>/Layer")
            procedure.set_attribution("Johannes", "Johannes", "2013")
        elif name == "image-replace-layer-with-clipboard":
            procedure = Gimp.ImageProcedure.new(
                self,
                name,
                Gimp.PDBProcType.PLUGIN,
                image_replace_layer_with_clipboard,
                None,
            )
            procedure.set_image_types("*")
            procedure.set_menu_label("Replace active layer with clipboard contents")
            procedure.set_documentation(
                "Replace active layer with clipboard contents",
                "Replace the active layer with the clipboard contents, scaling them to the layer size.",
                name,
            )
            procedure.add_menu_path("<Image>/Layer")
            procedure.set_attribution("Johannes", "Johannes", "2014")
        elif name == "image-open-layer-file":
            procedure = Gimp.ImageProcedure.new(
                self, name, Gimp.PDBProcType.PLUGIN, image_open_layer_file, None
            )
            procedure.set_image_types("*")
            procedure.set_menu_label("Open layer file")
            procedure.set_documentation(
                "Open layer file",
                "Open the file whose file name is specified by the active layer.",
                name,
            )
            procedure.add_menu_path("<Image>/Layer")
            procedure.set_attribution("Johannes", "Johannes", "2015")
        return procedure


Gimp.main(ReloadLayer.__gtype__, sys.argv)
