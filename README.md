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
pip install -r requirements.txt
```

## Usage

### Basic Usage

```python
from mega_downloader import download_mega_file

# Download a file to specific directory
file_path = download_mega_file('https://mega.nz/file/...', './downloads/')
print(f"Downloaded to: {file_path}")

# Download a file to current directory
file_path = download_mega_file('https://mega.nz/file/...')
```

### Get File Information (without downloading)

```python
from mega_downloader import get_mega_file_info

info = get_mega_file_info('https://mega.nz/file/...')
print(f"File: {info['name']}")
print(f"Size: {info['size']} bytes")
```

### Advanced Usage with MegaDownloader Class

```python
from mega_downloader import MegaDownloader

# Create downloader with custom timeout
downloader = MegaDownloader(timeout=60)

# Get file info first
info = downloader.get_file_info('https://mega.nz/file/...')
print(f"File: {info['name']} ({info['size'] / 1024 / 1024:.2f} MB)")

# Then download
file_path = downloader.download_from_url('https://mega.nz/file/...', './downloads/')
```

### Error Handling

```python
from mega_downloader import (
    download_mega_file,
    MegaDownloadError,
    MegaURLError,
    MegaAPIError
)

try:
    download_mega_file('https://mega.nz/file/...')
except MegaURLError as e:
    print(f"Invalid URL: {e}")
except MegaAPIError as e:
    print(f"API Error: {e}")
except MegaDownloadError as e:
    print(f"Download Error: {e}")
```

### Command Line Interface

```bash
# After pip install
mega-download "https://mega.nz/file/..." ./downloads/

# Or run directly
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

**pbat**

