BASE_CSS = b"""
window.note { background: #FFFF99; }
box.hdr {
    padding: 2px 4px 2px 2px;
    background: #E8D800;
}
box.hdr > eventbox { min-height: 26px; }
box.btmbar {
    padding: 3px 5px 3px 3px;
    background: #E8D800;
    min-height: 30px;
}
box.btmbar .tool-group {
    padding: 0 2px;
}
separator.tool-separator {
    background: rgba(0,0,0,0.25);
    min-width: 1px;
    margin: 3px 3px;
}

box.hdr button, box.btmbar button {
    padding: 1px 4px;
    min-width: 20px;
    min-height: 20px;
    border-radius: 10px;
    border: none;
    box-shadow: none;
    background: rgba(0,0,0,0.18);
    font-size: 12px;
    font-weight: bold;
    color: #333;
}
box.hdr button.pin-top {
    min-width: 18px;
    min-height: 18px;
    padding: 1px 6px;
    border-radius: 14px;
    font-size: 18px;
}
box.hdr button:hover, box.btmbar button:hover { background: rgba(0,0,0,0.35); }
box.hdr button.pinned, box.btmbar button.pinned { background: rgba(0,0,0,0.55); color: #000; }
box.btmbar button.delete { background: rgba(180,0,0,0.55); color: #fff; }
box.btmbar button.delete:hover { background: rgba(180,0,0,0.85); }
label.title {
    color: #444;
    font-weight: bold;
    font-size: 16px;
    padding: 0 4px;
}
entry.title-edit {
    background: transparent;
    border: 1px solid rgba(0,0,0,0.25);
    border-radius: 3px;
    box-shadow: none;
    color: #333;
    font-weight: bold;
    font-size: 15px;
    min-height: 20px;
    padding: 0 4px;
}
textview, textview text {
    background: transparent;
    font-family: Ubuntu, Cantarell, DejaVu Sans, sans-serif;
    font-size: 14px;
}
box.search-bar {
    background: rgba(0,0,0,0.08);
    padding: 2px 4px;
    border-top: 1px solid rgba(0,0,0,0.15);
}
box.search-bar entry {
    min-height: 22px;
    font-size: 12px;
}
"""

