# forix/services/launcher.py
"""Forix — IDE & Tool Launcher  (expanded tool list)"""

import os, sys, shutil, logging, subprocess
from pathlib import Path
from typing import Optional, List, Dict, Tuple

try:
    import winreg
    _HAS_WINREG = True
except ImportError:
    _HAS_WINREG = False

from utils.config import get_config

log = logging.getLogger("forix.launcher")

LA   = os.environ.get("LOCALAPPDATA",       "")
PA   = os.environ.get("PROGRAMFILES",       "C:/Program Files")
PA86 = os.environ.get("PROGRAMFILES(X86)",  "C:/Program Files (x86)")
AP   = os.environ.get("APPDATA",            "")


def _p(*parts) -> Path:
    return Path(*parts)


# ── Known installation locations ──────────────────────────────────────────────
_LOCS: Dict[str, List[Path]] = {
    "vscode":     [_p(LA,   "Programs/Microsoft VS Code/Code.exe"),
                   _p(PA,   "Microsoft VS Code/Code.exe"),
                   _p(PA86, "Microsoft VS Code/Code.exe")],
    "vscodium":   [_p(LA,   "Programs/VSCodium/VSCodium.exe"),
                   _p(PA,   "VSCodium/VSCodium.exe")],
    "cursor":     [_p(LA,   "Programs/Cursor/Cursor.exe"),
                   _p(PA,   "Cursor/Cursor.exe")],
    "windsurf":   [_p(LA,   "Programs/Windsurf/Windsurf.exe")],
    "arduino":    [_p(PA,   "Arduino IDE/Arduino IDE.exe"),
                   _p(PA86, "Arduino/arduino.exe"),
                   _p(LA,   "Arduino IDE/Arduino IDE.exe")],
    "kicad":      [_p(PA,   "KiCad/8.0/bin/kicad.exe"),
                   _p(PA,   "KiCad/7.0/bin/kicad.exe"),
                   _p(PA,   "KiCad/6.0/bin/kicad.exe"),
                   _p(PA86, "KiCad/bin/kicad.exe")],
    "freecad":    [_p(PA,   "FreeCAD 0.21/bin/FreeCAD.exe"),
                   _p(PA,   "FreeCAD 0.20/bin/FreeCAD.exe"),
                   _p(PA86, "FreeCAD/bin/FreeCAD.exe")],
    "pycharm":    [_p(PA,   "JetBrains/PyCharm Community Edition/bin/pycharm64.exe"),
                   _p(PA,   "JetBrains/PyCharm/bin/pycharm64.exe")],
    "webstorm":   [_p(PA,   "JetBrains/WebStorm/bin/webstorm64.exe")],
    "clion":      [_p(PA,   "JetBrains/CLion/bin/clion64.exe")],
    "rider":      [_p(PA,   "JetBrains/Rider/bin/rider64.exe")],
    "notepadpp":  [_p(PA,   "Notepad++/notepad++.exe"),
                   _p(PA86, "Notepad++/notepad++.exe")],
    "sublime":    [_p(PA,   "Sublime Text/sublime_text.exe"),
                   _p(PA,   "Sublime Text 3/sublime_text.exe")],
    "atom":       [_p(LA,   "atom/atom.exe")],
    "inkscape":   [_p(PA,   "Inkscape/bin/inkscape.exe")],
    "gimp":       [_p(PA,   "GIMP 2/bin/gimp-2.10.exe"),
                   _p(PA,   "GIMP 3/bin/gimp-3.0.exe")],
    "blender":    [_p(PA,   "Blender Foundation/Blender 4.0/blender.exe"),
                   _p(PA,   "Blender Foundation/Blender 3.6/blender.exe")],
    "excel":      [_p(PA,   "Microsoft Office/root/Office16/EXCEL.EXE"),
                   _p(PA86, "Microsoft Office/root/Office16/EXCEL.EXE"),
                   _p(PA,   "Microsoft Office/Office16/EXCEL.EXE")],
    "word":       [_p(PA,   "Microsoft Office/root/Office16/WINWORD.EXE"),
                   _p(PA86, "Microsoft Office/root/Office16/WINWORD.EXE")],
    "powerpoint": [_p(PA,   "Microsoft Office/root/Office16/POWERPNT.EXE"),
                   _p(PA86, "Microsoft Office/root/Office16/POWERPNT.EXE")],
    "chrome":     [_p(PA,   "Google/Chrome/Application/chrome.exe"),
                   _p(PA86, "Google/Chrome/Application/chrome.exe"),
                   _p(LA,   "Google/Chrome/Application/chrome.exe")],
    "firefox":    [_p(PA,   "Mozilla Firefox/firefox.exe"),
                   _p(PA86, "Mozilla Firefox/firefox.exe")],
    "edge":       [_p(PA,   "Microsoft/Edge/Application/msedge.exe"),
                   _p(PA86, "Microsoft/Edge/Application/msedge.exe")],
    "postman":    [_p(LA,   "Postman/Postman.exe")],
    "insomnia":   [_p(LA,   "insomnia/Insomnia.exe")],
    "dbeaver":    [_p(PA,   "DBeaver/dbeaver.exe"),
                   _p(LA,   "DBeaver/dbeaver.exe")],
    "tableplus":  [_p(LA,   "Programs/TablePlus/TablePlus.exe")],
    "obsidian":   [_p(LA,   "Obsidian/Obsidian.exe")],
    "typora":     [_p(PA,   "Typora/Typora.exe"),
                   _p(LA,   "Programs/Typora/Typora.exe")],
    "figma":      [_p(LA,   "Figma/Figma.exe")],
    "docker":     [_p(PA,   "Docker/Docker/Docker Desktop.exe")],
    "wsl":        [_p("C:/Windows/System32/wsl.exe")],
    "powershell": [_p("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")],
    "terminal":   [_p(LA,   "Microsoft/WindowsApps/wt.exe"),
                   _p("C:/Windows/System32/cmd.exe")],
}

_TOOL_NAMES: Dict[str, str] = {
    "vscode": "VS Code", "vscodium": "VSCodium", "cursor": "Cursor",
    "windsurf": "Windsurf", "arduino": "Arduino IDE", "kicad": "KiCad",
    "freecad": "FreeCAD", "pycharm": "PyCharm", "webstorm": "WebStorm",
    "clion": "CLion", "rider": "Rider", "notepadpp": "Notepad++",
    "sublime": "Sublime Text", "atom": "Atom", "inkscape": "Inkscape",
    "gimp": "GIMP", "blender": "Blender", "excel": "Excel",
    "word": "Word", "powerpoint": "PowerPoint", "chrome": "Chrome",
    "firefox": "Firefox", "edge": "Edge", "postman": "Postman",
    "insomnia": "Insomnia", "dbeaver": "DBeaver", "tableplus": "TablePlus",
    "obsidian": "Obsidian", "typora": "Typora", "figma": "Figma",
    "docker": "Docker Desktop", "wsl": "WSL", "powershell": "PowerShell",
    "terminal": "Terminal",
}

# The actual executable name used by shutil.which() — differs from the tool key
# for tools whose binary name doesn't match the key.
_WHICH_NAME: Dict[str, str] = {
    "vscode":     "code",
    "vscodium":   "codium",
    "notepadpp":  "notepad++",
    "pycharm":    "pycharm",
    "webstorm":   "webstorm",
    "clion":      "clion",
    "rider":      "rider",
    "arduino":    "arduino-ide",
    "kicad":      "kicad",
    "freecad":    "freecad",
    "inkscape":   "inkscape",
    "gimp":       "gimp",
    "blender":    "blender",
    "docker":     "docker",
    "powershell": "powershell",
    "terminal":   "wt",
    # For everything else the key itself is tried (e.g. "cursor", "chrome", etc.)
}

# Project type → ordered preferred tools
PROJECT_TYPE_TOOLS: Dict[str, List[str]] = {
    "python":   ["pycharm", "cursor", "vscode", "vscodium", "sublime", "notepadpp"],
    "node":     ["cursor", "vscode", "vscodium", "webstorm", "sublime", "notepadpp"],
    "web":      ["cursor", "vscode", "vscodium", "webstorm", "sublime", "notepadpp"],
    "arduino":  ["arduino", "vscode", "notepadpp"],
    "kicad":    ["kicad", "vscode"],
    "cad":      ["freecad", "blender", "vscode"],
    "embedded": ["vscode", "cursor", "clion", "notepadpp"],
    "document": ["word", "obsidian", "typora", "vscode", "notepadpp"],
    "data":     ["vscode", "cursor", "dbeaver", "excel", "notepadpp"],
    "generic":  ["cursor", "vscode", "vscodium", "notepadpp", "sublime"],
}

# Extension → preferred tools
EXT_TOOLS: Dict[str, List[str]] = {
    ".py":         ["pycharm", "cursor", "vscode"],
    ".ino":        ["arduino", "vscode"],
    ".kicad_pro":  ["kicad"],
    ".kicad_pcb":  ["kicad"],
    ".kicad_sch":  ["kicad"],
    ".sch":        ["kicad"],
    ".brd":        ["kicad"],
    ".FCStd":      ["freecad"],
    ".stl":        ["freecad", "blender"],
    ".step":       ["freecad"],
    ".stp":        ["freecad"],
    ".blend":      ["blender"],
    ".svg":        ["inkscape", "figma", "vscode"],
    ".xlsx":       ["excel"],
    ".xls":        ["excel"],
    ".csv":        ["excel", "dbeaver", "vscode"],
    ".docx":       ["word"],
    ".doc":        ["word"],
    ".pptx":       ["powerpoint"],
    ".ppt":        ["powerpoint"],
    ".md":         ["obsidian", "typora", "vscode", "notepadpp"],
    ".json":       ["vscode", "notepadpp"],
    ".yaml":       ["vscode", "notepadpp"],
    ".yml":        ["vscode", "notepadpp"],
    ".html":       ["vscode", "sublime", "chrome"],
    ".css":        ["vscode", "sublime"],
    ".js":         ["cursor", "vscode", "sublime"],
    ".ts":         ["cursor", "vscode"],
    ".jsx":        ["cursor", "vscode"],
    ".tsx":        ["cursor", "vscode"],
    ".cpp":        ["vscode", "cursor", "clion"],
    ".c":          ["vscode", "cursor", "clion"],
    ".h":          ["vscode", "cursor"],
    ".rs":         ["cursor", "vscode"],
    ".go":         ["cursor", "vscode"],
    ".png":        ["gimp", "figma", "inkscape"],
    ".jpg":        ["gimp"],
    ".jpeg":       ["gimp"],
    ".fig":        ["figma"],
    ".txt":        ["notepadpp", "vscode", "typora"],
    ".sql":        ["dbeaver", "vscode"],
    ".db":         ["dbeaver", "tableplus"],
    ".sh":         ["vscode", "terminal"],
    ".dockerfile": ["vscode", "docker"],
    # Note: docker-compose files are .yml/.yaml — handled by those keys above
}


# ── Tool class ────────────────────────────────────────────────────────────────

class Tool:
    def __init__(self, key: str):
        self.key  = key
        self.name = _TOOL_NAMES.get(key, key.title())

    def find_exe(self) -> Optional[Path]:
        # 1. User-configured override
        cfg = get_config()
        user_path = cfg.get(f"{self.key}_path", "")
        if user_path:
            p = Path(user_path)
            if p.exists():
                return p

        # 2. Known installation paths
        for loc in _LOCS.get(self.key, []):
            if loc.exists():
                return loc

        # 3. PATH lookup — use the correct binary name, not the tool key
        which_name = _WHICH_NAME.get(self.key, self.key)
        found = shutil.which(which_name)
        if found:
            return Path(found)

        return None

    def is_available(self) -> bool:
        return self.find_exe() is not None

    def launch(self, path: Path) -> bool:
        exe = self.find_exe()
        if not exe:
            log.warning(f"{self.name} not found")
            return False
        try:
            subprocess.Popen([str(exe), str(path)])
            return True
        except Exception as e:
            log.error(f"Launch {self.name}: {e}")
            return False


# Build the global TOOLS registry
TOOLS: Dict[str, Tool] = {k: Tool(k) for k in _TOOL_NAMES}


# ── Public API ────────────────────────────────────────────────────────────────

def launch_project(ptype: str, path: Path) -> Tuple[bool, str]:
    """Launch the best available tool for the given project type and path."""
    for key in PROJECT_TYPE_TOOLS.get(ptype, PROJECT_TYPE_TOOLS["generic"]):
        tool = TOOLS.get(key)
        if tool and tool.is_available():
            if tool.launch(path):
                return True, tool.name
    _open_in_explorer(path)
    return False, "Explorer"


def launch_file(path: Path) -> Tuple[bool, str]:
    """Open a file with the best available tool for its extension."""
    ext = path.suffix.lower()
    for key in EXT_TOOLS.get(ext, []):
        tool = TOOLS.get(key)
        if tool and tool.is_available():
            if tool.launch(path):
                return True, tool.name

    # Platform-safe fallback
    try:
        if sys.platform == "win32":
            os.startfile(str(path))         # Windows shell association
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True, "Default Application"
    except Exception as e:
        log.error(f"Open file {path}: {e}")
        return False, "None"


def get_available_tools_for_project(ptype: str) -> List[Tuple[str, Tool]]:
    """Return all installed tools suitable for the given project type."""
    return [
        (k, TOOLS[k])
        for k in PROJECT_TYPE_TOOLS.get(ptype, PROJECT_TYPE_TOOLS["generic"])
        if k in TOOLS and TOOLS[k].is_available()
    ]


def get_all_available_tools() -> List[Tuple[str, Tool]]:
    """Return all tools that are currently installed."""
    return [(k, t) for k, t in TOOLS.items() if t.is_available()]


def get_best_tool_name_for_project(ptype: str) -> str:
    """Return the display name of the best available tool for the project type."""
    avail = get_available_tools_for_project(ptype)
    return avail[0][1].name if avail else "Explorer"


def _open_in_explorer(path: Path):
    """Open the path in Windows Explorer, selecting the file if it's a file."""
    try:
        if path.is_file():
            subprocess.Popen(f'explorer /select,"{path}"')
        else:
            subprocess.Popen(f'explorer "{path}"')
    except Exception as e:
        log.error(f"Explorer: {e}")


__all__ = [
    "TOOLS",
    "Tool",
    "launch_project",
    "launch_file",
    "get_available_tools_for_project",
    "get_all_available_tools",
    "get_best_tool_name_for_project",
    "PROJECT_TYPE_TOOLS",
    "EXT_TOOLS",
]