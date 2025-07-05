# Mega Lite

A simplified Python library for downloading files from Mega.nz public URLs.

## Features

- Simple and easy-to-use API
- Download files from Mega.nz public URLs
- Support for large file downloads
- Progress tracking support
- Automatic file decryption
- Cross-platform compatibility

## Installation

### Option 1: Install via pip (recommended)
```bash
pip install mega-lite
```
### Option 2: Clone the repository manually
```bash
git clone https://github.com/Pbat6/mega-lite.git
cd mega-lite
python3 -m venv venv
source ./venv/bin/activate
pip install -r requirement.txt
```

## Usage

### Basic Usage

```python
from mega_downloader import download_mega_file

# Download a file from Mega.nz
file_path = download_mega_file('https://mega.nz/file/...', './downloads/')
print(f"Downloaded to: {file_path}")
```

### Command Line Interface

```bash
# Using the command after installing
python3 mega_downloader.py "https://mega.nz/file/..." ./downloads/
```

## Requirements

- Python 3.8+
- requests >= 2.28.0
- pycryptodome >= 3.19.0

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Author

**pbat + github copilot**

