"""The Help window: the shortcuts and gestures nothing on screen shows.

What a button tells on hover, such as Bold and Ctrl+B, or a link's tooltip, is
left out, so the list stays short enough to read at a glance.
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk

# (section, [(keys or gesture, what it does), ...]). The keys are Pango
# markup, so what is typed as it is shows in <tt>: the note's font joins
# dashes into one.
HELP = [
    ('Typing', [
        ('<tt>-</tt> or <tt>[ ]</tt> then Space',
         'Start a bullet or a checklist'),
        ('<tt>---</tt> alone on a line', 'Insert a divider'),
        ('<tt>`text`</tt>', 'Make inline code'),
        ('Tab / Shift+Tab', 'Indent or outdent list items, also every '
                            'selected one'),
        ('Ctrl+Enter', 'Check or uncheck the to-dos on the selected lines'),
    ]),
    ('Search', [
        ('Ctrl+F', 'Search every note'),
    ]),
    ('Mouse', [
        ('Double-click in a code block', 'Select one command'),
        ('Triple-click in a code block', 'Select the whole block'),
    ]),
    ('Arranging notes', [
        ('Alt+Left / Right', 'Snap into the left or right half of the '
                             'monitor, then onto the next monitor'),
        ('Alt+Up / Down', 'Move up or down by the note\'s own height'),
        ('Alt+scroll over a note', 'Step through notes, latest used first'),
        ('Middle-click the tray icon', 'Bring every note to the front'),
    ]),
]


def help_grid():
    """A grid with a bold heading per section and a row per shortcut."""
    grid = Gtk.Grid(column_spacing=18, row_spacing=4)
    row = 0
    for section, items in HELP:
        heading = Gtk.Label(xalign=0)
        heading.set_markup(f'<b>{GLib.markup_escape_text(section)}</b>')
        heading.set_margin_top(0 if row == 0 else 10)
        grid.attach(heading, 0, row, 2, 1)
        row += 1
        for keys, action in items:
            key_label = Gtk.Label(xalign=0, yalign=0)
            key_label.set_markup(keys)
            key_label.get_style_context().add_class('dim-label')
            action_label = Gtk.Label(label=action, xalign=0, yalign=0)
            # A wrapping label asks for its narrowest width unless told how
            # wide to be.
            action_label.set_line_wrap(True)
            action_label.set_width_chars(38)
            action_label.set_max_width_chars(38)
            grid.attach(key_label, 0, row, 1, 1)
            grid.attach(action_label, 1, row, 1, 1)
            row += 1
    return grid


def show_help(parent):
    """Show the Help window over the note `parent` until it is closed."""
    dialog = Gtk.Dialog(title='Ynote Help', transient_for=parent, modal=True)
    dialog.add_button('Close', Gtk.ResponseType.CLOSE)
    grid = help_grid()
    grid.set_border_width(12)
    dialog.get_content_area().add(grid)
    dialog.show_all()
    dialog.run()
    dialog.destroy()
