"""
Mega Downloader - A simplified library for downloading files from Mega.nz public URLs
"""

import re
import json
import logging
import hashlib
import tempfile
import shutil
import base64
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse
from difflib import SequenceMatcher

import requests
from Crypto.Cipher import AES
from Crypto.Util import Counter

logger = logging.getLogger(__name__)


class MegaDownloadError(Exception):
    """Base exception for Mega download errors"""
    pass


class MegaURLError(MegaDownloadError):
    """Error parsing Mega URL"""
    pass


class MegaAPIError(MegaDownloadError):
    """Error from Mega API"""
    pass


class MegaDownloader:
    """Mega.nz file downloader with focus on public URL downloads"""
    
    def __init__(self, timeout: int = 30):
        """
        Initialize the downloader.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def download_from_url(self, url: str, output_path: Optional[str] = None) -> Path:
        """
        Download a file from a Mega.nz public URL.
        
        Args:
            url: Mega.nz public URL
            output_path: Directory to save the file (optional)
            
        Returns:
            Path to the downloaded file
            
        Raises:
            MegaURLError: If URL is invalid
            MegaAPIError: If API request fails
            MegaDownloadError: If download fails
        """
        try:
            # Parse URL
            file_id, file_key = self._parse_url(url)
            
            # Get file info
            file_info = self._get_file_info(file_id, file_key)
            
            # Download file
            return self._download_file(file_id, file_key, file_info, output_path)
            
        except Exception as e:
            if isinstance(e, MegaDownloadError):
                raise
            raise MegaDownloadError(f"Unexpected error: {str(e)}") from e
    
    def get_file_info(self, url: str) -> Dict[str, Any]:
        """
        Get file information from a Mega.nz public URL without downloading.
        
        Args:
            url: Mega.nz public URL
            
        Returns:
            Dictionary with file information (name, size)
        """
        file_id, file_key = self._parse_url(url)
        return self._get_file_info(file_id, file_key)
    
    def _parse_url(self, url: str) -> Tuple[str, str]:
        """
        Parse file ID and key from Mega URL.
        
        Args:
            url: Mega URL
            
        Returns:
            Tuple of (file_id, file_key)
        """
        url = url.strip()
        
        # Handle different URL formats
        if '/file/' in url:
            # New format: https://mega.nz/file/abc123!def456 or https://mega.nz/file/abc123#def456
            match = re.search(r'/file/([^!#]+)[!#]([^/?\s]+)', url)
            if match:
                return match.group(1), match.group(2)
        elif '/#!' in url:
            # Old format: https://mega.nz/#!abc123!def456
            match = re.search(r'/#!([^!]+)!([^/?\s]+)', url)
            if match:
                return match.group(1), match.group(2)
        
        raise MegaURLError(f"Invalid Mega URL format: {url}")
    
    def _get_file_info(self, file_id: str, file_key: str) -> Dict[str, Any]:
        """
        Get file information from Mega API.
        
        Args:
            file_id: Mega file ID
            file_key: Mega file key
            
        Returns:
            Dictionary with file info
        """
        try:
            # Convert key to proper format
            key_bytes = self._base64_url_decode(file_key)
            key_array = self._bytes_to_a32(key_bytes)
            
            # First API call - get file info
            response = self.session.post(
                'https://g.api.mega.co.nz/cs',
                json=[{"a": "g", "p": file_id, "ssm": 1}],
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                raise MegaAPIError(f"API request failed with status {response.status_code}")
            
            data = response.json()
            if not data or isinstance(data[0], int):
                error_code = data[0] if data else -1
                raise MegaAPIError(f"API error: {error_code}")
            
            file_data = data[0]
            
            # Decrypt file attributes
            k = self._derive_key(key_array)
            encrypted_attrs = self._base64_url_decode(file_data['at'])
            attrs = self._decrypt_attributes(encrypted_attrs, k)
            
            # Check if download URL is in first response
            download_url = file_data.get('g', '')
            
            # If no download URL, make second API call
            if not download_url:
                response2 = self.session.post(
                    'https://g.api.mega.co.nz/cs',
                    json=[{"a": "g", "g": 1, "p": file_id}],
                    timeout=self.timeout
                )
                
                if response2.status_code != 200:
                    raise MegaAPIError(f"Second API request failed with status {response2.status_code}")
                
                data2 = response2.json()
                if not data2 or isinstance(data2[0], int):
                    error_code = data2[0] if data2 else -1
                    raise MegaAPIError(f"Second API error: {error_code}")
                
                download_url = data2[0] if isinstance(data2[0], str) else data2[0].get('g', '')
            
            if not download_url:
                raise MegaAPIError("No download URL found in API response")
            
            return {
                'name': attrs.get('n', 'unknown'),
                'size': file_data.get('s', 0),
                'download_url': download_url,
                'key': key_array,
                'derived_key': k,
                'file_id': file_id
            }
            
        except requests.RequestException as e:
            raise MegaAPIError(f"Network error: {str(e)}") from e
        except (KeyError, ValueError, TypeError) as e:
            raise MegaAPIError(f"Invalid API response: {str(e)}") from e
    
    def _download_file(self, file_id: str, file_key: str, file_info: Dict[str, Any], 
                      output_path: Optional[str] = None) -> Path:
        """
        Download and decrypt the file.
        
        Args:
            file_id: Mega file ID
            file_key: Mega file key
            file_info: File information from API
            output_path: Directory to save file
            
        Returns:
            Path to downloaded file
        """
        download_url = file_info['download_url']
        file_name = file_info['name']
        file_size = file_info['size']
        key_array = file_info['key']
        derived_key = file_info['derived_key']
        
        # Prepare output path
        if output_path:
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            final_path = output_dir / file_name
        else:
            output_dir = Path(".")
            final_path = Path(file_name)
        
        # Check for similar files and remove old versions
        self._handle_similar_files(file_name, output_dir)
        
        # Check for similar files and handle accordingly
        self._handle_similar_files(file_name, final_path.parent)
        
        # Download and decrypt
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                
                # Setup decryption
                iv = key_array[4:6] + [0, 0]
                counter = Counter.new(128, initial_value=((iv[0] << 32) + iv[1]) << 64)
                cipher = AES.new(self._a32_to_bytes(derived_key), AES.MODE_CTR, counter=counter)
                
                # Download with streaming
                response = self.session.get(download_url, stream=True, timeout=self.timeout)
                response.raise_for_status()
                
                downloaded_size = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        decrypted_chunk = cipher.decrypt(chunk)
                        temp_file.write(decrypted_chunk)
                        downloaded_size += len(chunk)
                        
                        # Optional: Progress logging
                        if downloaded_size % (1024 * 1024) == 0:  # Every MB
                            logger.info(f"Downloaded {downloaded_size / (1024*1024):.1f} MB")
                
                # Verify file integrity (basic check)
                if downloaded_size != file_size:
                    logger.warning(f"Size mismatch: expected {file_size}, got {downloaded_size}")
            
            # Move to final location
            shutil.move(str(temp_path), str(final_path))
            logger.info(f"Successfully downloaded: {final_path}")
            
            return final_path
            
        except Exception as e:
            # Cleanup temp file if it exists
            if 'temp_path' in locals() and temp_path.exists():
                temp_path.unlink()
            raise MegaDownloadError(f"Download failed: {str(e)}") from e
    
    def _derive_key(self, key_array: list) -> list:
        """Derive decryption key from file key"""
        return [
            key_array[0] ^ key_array[4],
            key_array[1] ^ key_array[5], 
            key_array[2] ^ key_array[6],
            key_array[3] ^ key_array[7]
        ]
    
    def _decrypt_attributes(self, encrypted_data: bytes, key: list) -> dict:
        """Decrypt file attributes"""
        try:
            key_bytes = self._a32_to_bytes(key)
            cipher = AES.new(key_bytes, AES.MODE_CBC, b'\x00' * 16)
            decrypted = cipher.decrypt(encrypted_data)
            
            # Remove padding and MEGA prefix
            decrypted = decrypted.rstrip(b'\x00')
            if decrypted.startswith(b'MEGA'):
                json_data = decrypted[4:].decode('utf-8')
                return json.loads(json_data)
            return {}
        except Exception:
            return {}
    
    def _base64_url_decode(self, data: str) -> bytes:
        """Decode base64 URL-safe string"""
        # Add padding if needed
        data += '=' * (4 - len(data) % 4)
        # Replace URL-safe characters
        data = data.replace('-', '+').replace('_', '/')
        return base64.b64decode(data)
    
    def _bytes_to_a32(self, data: bytes) -> list:
        """Convert bytes to array of 32-bit integers"""
        # Pad to multiple of 4
        if len(data) % 4:
            data += b'\x00' * (4 - len(data) % 4)
        
        result = []
        for i in range(0, len(data), 4):
            val = int.from_bytes(data[i:i+4], 'big')
            result.append(val)
        return result
    
    def _a32_to_bytes(self, array: list) -> bytes:
        """Convert array of 32-bit integers to bytes"""
        result = b''
        for val in array:
            result += val.to_bytes(4, 'big')
        return result
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two strings"""
        return SequenceMatcher(None, text1, text2).ratio()
    
    def _handle_similar_files(self, new_file_name: str, output_dir: Path) -> None:
        """
        Check for similar files and remove old versions if similarity > 80%
        
        Args:
            new_file_name: Name of the new file to be downloaded
            output_dir: Directory where files are stored
        """
        if not output_dir.exists():
            return
            
        # Get all files in the output directory
        existing_files = [f for f in output_dir.iterdir() if f.is_file()]
        
        # Check similarity with existing files
        for existing_file in existing_files:
            similarity = self._calculate_similarity(new_file_name, existing_file.name)
            
            if similarity > 0.8:  # 80% similarity threshold
                logger.info(f"Found similar file: {existing_file.name} (similarity: {similarity:.2%})")
                logger.info(f"Removing old file: {existing_file.name}")
                existing_file.unlink()
                break  # Only remove the most similar file


# Convenience function for simple usage
def download_mega_file(url: str, output_path: Optional[str] = None) -> Path:
    """
    Simple function to download a file from Mega.nz public URL.
    
    Args:
        url: Mega.nz public URL
        output_path: Directory to save the file (optional)
        
    Returns:
        Path to the downloaded file
    """
    downloader = MegaDownloader()
    return downloader.download_from_url(url, output_path)


def get_mega_file_info(url: str) -> Dict[str, Any]:
    """
    Get file information from Mega.nz public URL.
    
    Args:
        url: Mega.nz public URL
        
    Returns:
        Dictionary with file information
    """
    downloader = MegaDownloader()
    return downloader.get_file_info(url)


def main():
    """Main function for command line usage"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python mega_downloader.py <mega_url> [output_directory]")
        sys.exit(1)
    
    url = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        # Get file info first
        info = get_mega_file_info(url)
        size_mb = info['size'] / (1024 * 1024)
        print(f"File: {info['name']} ({size_mb:.2f} MB)")
        
        # Download file
        file_path = download_mega_file(url, output_dir)
        print(f"Downloaded to: {file_path}")
        
    except MegaDownloadError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
