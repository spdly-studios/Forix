# Forix

<p align="center">
  <img src="assets/logo.png" width="120" alt="Forix Logo">
</p>

<p align="center">
  <b>Intelligent Self-Organizing Project Manager</b>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#project-structure">Project Structure</a> •
  <a href="#configuration">Configuration</a>
</p>

---

Forix is a powerful desktop application designed for makers, engineers, and developers who need to manage multiple projects without discipline or manual housekeeping. It watches your drive, auto-classifies files, snapshots versions, tracks inventory, and keeps everything organized — automatically.

## Features

### 🗂️ **Intelligent Project Management**
- **Auto-Detection**: Automatically detects project folders based on file signatures
- **Smart Classification**: Classifies files by type (Arduino, KiCad, Python, Node.js, Web, CAD, Embedded, and more)
- **Project Templates**: Auto-generates standardized project structure with README, metadata, and organized subdirectories

### 👁️ **Real-Time File System Watching**
- Monitors entire drive continuously using `watchdog`
- Debounces rapid events to avoid system overload
- Tracks file creation, modification, deletion, and moves

### 📸 **Automatic Versioning**
- Creates snapshots of project changes automatically
- Debounced versioning (configurable delay)
- Size-limited snapshots (default: 100MB max)
- Up to 50 versions per project

### 🔍 **Advanced Search**
- Fuzzy search powered by `fuzzywuzzy` and `python-Levenshtein`
- Search across projects, files, and metadata
- Command palette for quick navigation (Ctrl+Shift+P)

### 🔄 **Duplicate Detection**
- Automatically detects duplicate files using checksums
- Manages duplicate groups with merge suggestions
- Helps reclaim disk space

### 📦 **Inventory Tracking**
- Tracks project components and materials
- Integration with project management workflow

### 🎨 **Modern Dark UI**
- Beautiful dark theme (zinc/indigo palette)
- Custom-styled PyQt6 interface
- System tray integration with notifications
- Collapsible sidebar navigation

### ⚙️ **Configurable Automation**
- Three automation levels: High, Medium, Low
- Adjustable thresholds for auto-merge and classification
- Customizable project type signatures

## Installation

### Prerequisites
- Python 3.10 or higher
- Windows 10/11 (primary target platform)

### Option 1: Run from Source

```bash
# Clone the repository
git clone https://github.com/spdly-studios/Forix.git
cd Forix

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Option 2: Build Executable

```bash
# Install PyInstaller
pip install pyinstaller

# Build executable
pyinstaller forix.spec

# Output will be in dist/Forix.exe
```

### Dependencies

| Package | Purpose |
|---------|---------|
| PyQt6 | Desktop GUI framework |
| watchdog | File system monitoring |
| SQLAlchemy | Database ORM |
| Pillow | Image processing |
| fuzzywuzzy | Fuzzy string matching |
| python-Levenshtein | Fast Levenshtein distance |
| psutil | System utilities |
| pywin32 | Windows integration |

## Usage

### First Launch

1. Forix creates its directory structure on the configured drive (default: `E:\`)
2. The system tray icon appears — Forix runs in background
3. The main window shows the Dashboard with system overview

### Main Interface

| Page | Description |
|------|-------------|
| **Dashboard** | System overview, recent activity, quick stats |
| **Projects** | Browse and manage all detected projects |
| **Inventory** | Track components and materials |
| **Search** | Global fuzzy search across everything |
| **Activity** | Event log and history |
| **Health** | System diagnostics and statistics |
| **Duplicates** | Manage duplicate files |
| **Settings** | Configuration and preferences |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+P` | Open Command Palette |
| `Ctrl+1` | Dashboard |
| `Ctrl+2` | Projects |
| `Ctrl+3` | Inventory |
| `Ctrl+F` | Search |

## Project Structure

### Forix Directory Layout

```
E:/
├── Projects/          # All projects live here
│   ├── ProjectA/      # Auto-organized project folder
│   ├── ProjectB/
│   └── ...
├── System/            # Forix system data
│   ├── system.db      # SQLite database
│   ├── settings.json  # User preferences
│   ├── logs/          # Application logs
│   ├── cache/         # Temporary cache
│   └── watchers/      # Watcher state
├── Backups/           # Automatic backups
└── Temp/              # Temporary files
```

### Auto-Generated Project Structure

Every project gets this standardized skeleton:

```
ProjectName/
├── README.md              # Auto-generated project overview
├── metadata.json          # Machine-readable project data
├── src/                   # Active source files
│   └── (type-specific layout)
├── scratch/               # WIP experiments (never auto-deleted)
├── archive/               # Completed/abandoned attempts
├── notes/                 # Design notes, research, links
├── assets/                # Images, datasheets, references
├── exports/               # Build outputs
└── versions/              # Auto-snapshots (managed by Forix)
```

## Configuration

All settings are centralized in `config.py`:

### Key Settings

```python
# Drive Configuration
ROOT_DRIVE = Path("E:/")          # Primary drive Forix operates on

# Automation Level
AUTOMATION_LEVEL = "high"          # high | medium | low
AUTO_CREATE_PROJECTS = True        # Auto-create projects from folders

# File Watching
WATCH_ENTIRE_DRIVE = True
FOLDER_OPEN_POLL_MS = 2000

# Versioning
VERSION_DEBOUNCE_SECS = 30         # Delay before creating version
MAX_VERSIONS_PER_PROJECT = 50
VERSION_SIZE_LIMIT_BYTES = 100 * 1024 * 1024  # 100 MB

# IDE Paths
TOOL_PATHS = {
    "vscode": "",
    "arduino": "",
    "kicad": "",
    # ... configure your tools
}
```

### Project Type Detection

Forix auto-detects project types based on file signatures:

| Type | Signature Files |
|------|-----------------|
| Arduino | `.ino`, `platformio.ini` |
| KiCad | `.kicad_pro`, `.kicad_sch` |
| Python | `requirements.txt`, `pyproject.toml`, `setup.py` |
| Node.js | `package.json` |
| Web | `index.html`, `*.css`, `*.js` |
| CAD | FreeCAD, Fusion 360 files |
| Embedded | PlatformIO, CMake for embedded |

## Architecture

```
┌─────────────────────────────────────────┐
│           PyQt6 UI (main_window)        │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐  │
│  │ Sidebar │ │  Pages  │ │Cmd Palette│  │
│  └────┬────┘ └────┬────┘ └─────┬─────┘  │
└───────┼───────────┼────────────┼────────┘
        │           │            │
        └───────────┴────────────┘
                    │
        ┌───────────┴───────────┐
        │    BackgroundService  │
        └───────────┬───────────┘
                    │
        ┌───────────┴───────────┐
        │      Organiser        │
        │  ┌─────┐ ┌─────────┐  │
        │  │Queue│ │ Classify│  │
        │  └─────┘ └─────────┘  │
        └───────────┬───────────┘
                    │
        ┌───────────┴───────────┐
        │   ForixEventHandler   │
        │      (watchdog)       │
        └───────────┬───────────┘
                    │
            ┌───────┴───────┐
            │  File System  │
            │  (E:\ Drive)  │
            └───────────────┘
```

## Development

### Project Structure

```
Forix/
├── main.py                    # Application entry point
├── config.py                  # Master configuration
├── design.py                  # UI design system (colors, sizes)
├── theme.py                   # Theme aliases
├── requirements.txt           # Python dependencies
├── forix.spec                 # PyInstaller spec
├── core/                      # Core logic
│   ├── classifier.py          # File classification
│   ├── database.py            # SQLAlchemy models
│   ├── project_manager.py     # Project operations
│   └── constants.py           # Constant re-exports
├── services/                  # Background services
│   ├── organiser.py           # File organization engine
│   ├── watcher.py             # Filesystem watcher
│   ├── versioning.py          # Version snapshot manager
│   ├── search.py              # Search functionality
│   ├── duplicate_manager.py   # Duplicate detection
│   └── background_service.py  # Service orchestration
├── ui/                        # User interface
│   ├── main_window.py         # Main window
│   ├── sidebar.py             # Navigation sidebar
│   ├── command_palette.py     # Quick command interface
│   ├── pages/                 # Page implementations
│   ├── widgets/               # Custom widgets
│   └── dialogs/               # Dialog windows
├── utils/                     # Utilities
└── assets/                    # Icons and images
```


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

Free for Personal Use

## Author

**Shivaprasad V**
- Freelancer
- Email: spdly.studios@gmail.com
- LinkedIn: [linkedin.com/in/spdly](https://www.linkedin.com/in/spdly/)
- GitHub: [@spdly-studios](https://github.com/spdly-studios)
- Website: [spdly.is-a.dev](https://spdly.is-a.dev)

---

<p align="center">
  Made with ❤️ for makers, engineers, and developers
</p>
