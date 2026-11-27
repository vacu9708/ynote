"""The Help window: the shortcuts and gestures nothing on screen shows.

What the screen already tells is left out, so the list stays short enough to
read at a glance: a button's tooltip, a link's tooltip, and what the Format and
Insert menus show beside each item, its shortcut and the Markdown that typing
makes it from, such as **text** or ```.
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk

# (section, [(keys or gesture, what it does), ...]). The keys are Pango
# markup, so what is typed as it is shows in <tt>: the note's font joins
# dashes into one.
HELP = [
    ('Lists', [
        ('Tab / Shift+Tab', 'Indent or outdent list items, also every '
                            'selected one'),
        ('Ctrl+Enter', 'Check or uncheck the to-dos on the selected lines'),
    ]),
    ('Expand', [
        ('Ctrl+Enter on the title', 'Fold or open it'),
        ('Enter on its empty last line', 'Go on writing below it'),
        ('Backspace at the title\'s start',
         'Take the expand away and keep what it holds'),
    ]),
    ('Tables', [
        ('Tab / Shift+Tab', 'Go to the next or previous cell, and add a row '
                            'after the last one'),
        ('Enter', 'Add a row, or end the table on an empty last row'),
        ('Right-click a cell', 'Add or delete rows and columns'),
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
