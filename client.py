"""
Client module for interacting with the game distribution server.
Handles downloading, updating, and running games from the library.
"""

import os
import sys
import json
import zipfile
import platform
import subprocess
import tempfile
import shutil
from typing import Optional, List, Dict, Callable
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin
import io

# Try to import requests, fall back to urllib if not available
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# Default server URL (change this to your server)
DEFAULT_SERVER_URL = "https://mpy.mc-c0rp.xyz"


def get_server_url() -> str:
    """Get server URL from config or environment."""
    # Check environment variable
    env_url = os.environ.get('MPY_SERVER_URL')
    if env_url:
        return env_url.rstrip('/')
    
    # Check config file
    config_path = get_client_config_path()
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                if config.get('server_url'):
                    return config['server_url'].rstrip('/')
        except:
            pass
    
    return DEFAULT_SERVER_URL


def set_server_url(url: str):
    """Set server URL in config."""
    config_path = get_client_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    config = {}
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except:
            pass
    
    config['server_url'] = url.rstrip('/')
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)


def get_games_directory() -> Path:
    """Get directory where downloaded games are stored."""
    if platform.system() == 'Windows':
        base = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')))
    else:
        base = Path.home()
    
    games_dir = base / '.mpy_games'
    games_dir.mkdir(parents=True, exist_ok=True)
    return games_dir


def get_cache_directory() -> Path:
    """Get directory for cached thumbnails and metadata."""
    if platform.system() == 'Windows':
        base = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')))
    else:
        base = Path.home()
    
    cache_dir = base / '.mpy_cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_client_config_path() -> Path:
    """Get path to client config file."""
    if platform.system() == 'Windows':
        base = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')))
    else:
        base = Path.home()
    
    return base / '.mpy_config.json'


def get_installed_games_path() -> Path:
    """Get path to installed games index file."""
    return get_games_directory() / 'installed.json'


# ============================================================================
# HTTP REQUESTS
# ============================================================================

def api_request(
    endpoint: str,
    method: str = 'GET',
    data: dict = None,
    files: dict = None,
    timeout: int = 30
) -> dict:
    """
    Make an API request to the server.
    
    Args:
        endpoint: API endpoint (e.g., '/api/games')
        method: HTTP method
        data: Form data or JSON body
        files: Files to upload {'field_name': ('filename', file_bytes, 'mime_type')}
        timeout: Request timeout in seconds
        
    Returns:
        JSON response as dict
        
    Raises:
        Exception on error
    """
    url = urljoin(get_server_url() + '/', endpoint.lstrip('/'))
    
    if HAS_REQUESTS:
        # Use requests library
        try:
            if method == 'GET':
                response = requests.get(url, params=data, timeout=timeout)
            elif method == 'POST':
                if files:
                    response = requests.post(url, data=data, files=files, timeout=timeout)
                else:
                    response = requests.post(url, data=data, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, params=data, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.ConnectionError:
            raise Exception("Не удалось подключиться к серверу")
        except requests.exceptions.Timeout:
            raise Exception("Превышено время ожидания ответа от сервера")
        except requests.exceptions.HTTPError as e:
            try:
                error_data = e.response.json()
                raise Exception(error_data.get('error', str(e)))
            except:
                raise Exception(f"Ошибка сервера: {e.response.status_code}")
    else:
        # Fallback to urllib (limited functionality)
        try:
            if method == 'GET':
                req = Request(url)
            else:
                raise Exception("Для загрузки файлов требуется библиотека 'requests'")
            
            with urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode('utf-8'))
                
        except HTTPError as e:
            raise Exception(f"Ошибка сервера: {e.code}")
        except URLError as e:
            raise Exception(f"Ошибка подключения: {e.reason}")


def download_file(url: str, dest_path: str, progress_callback: Callable = None) -> bool:
    """
    Download a file from URL with progress tracking.
    
    Args:
        url: URL to download
        dest_path: Destination file path
        progress_callback: Function(downloaded_bytes, total_bytes)
        
    Returns:
        True if successful
    """
    try:
        if HAS_REQUESTS:
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)
        else:
            req = Request(url)
            with urlopen(req, timeout=300) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(dest_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)
        
        return True
        
    except Exception as e:
        print(f"Download error: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False


# ============================================================================
# GAME LIBRARY OPERATIONS
# ============================================================================

def get_games_list() -> List[Dict]:
    """
    Get list of all games from server.
    
    Returns:
        List of game info dicts
    """
    response = api_request('/api/games')
    return response.get('games', [])


def get_game_info(game_id: str) -> Dict:
    """
    Get detailed info about a specific game.
    
    Args:
        game_id: Game ID
        
    Returns:
        Game info dict
    """
    return api_request(f'/api/games/{game_id}')


def check_for_update(game_id: str, current_version: str) -> Dict:
    """
    Check if a game has updates available.
    
    Args:
        game_id: Game ID
        current_version: Currently installed version
        
    Returns:
        Dict with has_update, latest_version, file_size
    """
    return api_request(f'/api/check_update/{game_id}', data={'current_version': current_version})


def get_thumbnail_url(game_id: str) -> str:
    """Get URL for game thumbnail."""
    return f"{get_server_url()}/api/thumbnail/{game_id}"


def get_download_url(game_id: str) -> str:
    """Get URL for game download."""
    return f"{get_server_url()}/api/download/{game_id}"


# ============================================================================
# INSTALLED GAMES MANAGEMENT
# ============================================================================

def load_installed_games() -> Dict:
    """Load installed games index."""
    index_path = get_installed_games_path()
    if index_path.exists():
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"games": {}}


def save_installed_games(data: Dict):
    """Save installed games index."""
    index_path = get_installed_games_path()
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_installed_game(game_id: str) -> Optional[Dict]:
    """Get info about an installed game."""
    index = load_installed_games()
    return index["games"].get(game_id)


def mark_game_installed(game_id: str, game_info: Dict, install_path: str):
    """Mark a game as installed."""
    index = load_installed_games()
    index["games"][game_id] = {
        "game_id": game_id,
        "name": game_info.get("name", "Unknown"),
        "version": game_info.get("version", "1.0"),
        "install_path": install_path,
        "has_exe": game_info.get("has_exe", False),
        "installed_at": __import__('datetime').datetime.now().isoformat()
    }
    save_installed_games(index)


def unmark_game_installed(game_id: str):
    """Remove game from installed index."""
    index = load_installed_games()
    if game_id in index["games"]:
        del index["games"][game_id]
        save_installed_games(index)


def is_game_installed(game_id: str) -> bool:
    """Check if a game is installed."""
    installed = get_installed_game(game_id)
    if not installed:
        return False
    
    # Verify installation directory exists
    install_path = installed.get("install_path")
    if not install_path or not os.path.exists(install_path):
        unmark_game_installed(game_id)
        return False
    
    return True


def get_installed_version(game_id: str) -> Optional[str]:
    """Get installed version of a game."""
    installed = get_installed_game(game_id)
    return installed.get("version") if installed else None


# ============================================================================
# DOWNLOAD AND INSTALL
# ============================================================================

def download_game(
    game_id: str,
    progress_callback: Callable = None,
    log_callback: Callable = None
) -> bool:
    """
    Download and install a game from the server.
    
    Args:
        game_id: Game ID to download
        progress_callback: Function(current, total) for progress updates
        log_callback: Function(message) for log messages
        
    Returns:
        True if successful
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)
    
    try:
        log(f"Получение информации об игре {game_id}...")
        game_info = get_game_info(game_id)
        game_name = game_info.get('name', 'Unknown')
        
        log(f"Скачивание: {game_name} v{game_info.get('version', '?')}")
        
        # Prepare install directory
        install_dir = get_games_directory() / game_id
        
        # Remove old installation if exists
        if install_dir.exists():
            # Keep saves directory
            saves_dir = install_dir / 'saves'
            temp_saves = None
            if saves_dir.exists():
                temp_saves = tempfile.mkdtemp()
                shutil.move(str(saves_dir), os.path.join(temp_saves, 'saves'))
            
            shutil.rmtree(install_dir)
            
            # Restore saves
            if temp_saves:
                install_dir.mkdir(parents=True)
                shutil.move(os.path.join(temp_saves, 'saves'), str(saves_dir))
                shutil.rmtree(temp_saves)
        
        install_dir.mkdir(parents=True, exist_ok=True)
        
        # Download ZIP
        download_url = get_download_url(game_id)
        zip_path = install_dir / 'game.zip'
        
        log("Загрузка файла...")
        if not download_file(str(download_url), str(zip_path), progress_callback):
            log("Ошибка загрузки файла")
            return False
        
        # Extract ZIP
        log("Распаковка...")
        try:
            with zipfile.ZipFile(str(zip_path), 'r') as zf:
                zf.extractall(str(install_dir))
        except zipfile.BadZipFile:
            log("Ошибка: повреждённый архив")
            return False
        
        # Remove ZIP
        os.remove(str(zip_path))
        
        # Create saves directory
        saves_dir = install_dir / 'saves'
        saves_dir.mkdir(exist_ok=True)
        
        # Mark as installed
        mark_game_installed(game_id, game_info, str(install_dir))
        
        log(f"✓ Игра установлена: {install_dir}")
        return True
        
    except Exception as e:
        log(f"Ошибка: {e}")
        return False


def update_game(
    game_id: str,
    progress_callback: Callable = None,
    log_callback: Callable = None
) -> bool:
    """
    Update an installed game to the latest version.
    
    Args:
        game_id: Game ID to update
        progress_callback: Function(current, total) for progress updates
        log_callback: Function(message) for log messages
        
    Returns:
        True if successful
    """
    # Same as download, but preserves saves
    return download_game(game_id, progress_callback, log_callback)


def uninstall_game(game_id: str) -> bool:
    """
    Uninstall a game.
    
    Args:
        game_id: Game ID to uninstall
        
    Returns:
        True if successful
    """
    try:
        installed = get_installed_game(game_id)
        if not installed:
            return False
        
        install_path = installed.get("install_path")
        if install_path and os.path.exists(install_path):
            shutil.rmtree(install_path)
        
        unmark_game_installed(game_id)
        return True
        
    except Exception as e:
        print(f"Uninstall error: {e}")
        return False


# ============================================================================
# RUN GAME
# ============================================================================

def run_game(game_id: str, log_callback: Callable = None) -> bool:
    """
    Run an installed game.
    
    - On Windows: Run EXE if available, otherwise Python engine
    - On macOS/Linux: Run Python engine with JSON in separate process
    
    Args:
        game_id: Game ID to run
        log_callback: Function(message) for log messages
        
    Returns:
        True if game started successfully
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)
    
    installed = get_installed_game(game_id)
    if not installed:
        log("Игра не установлена")
        return False
    
    install_path = Path(installed["install_path"])
    if not install_path.exists():
        log("Папка игры не найдена")
        unmark_game_installed(game_id)
        return False
    
    is_windows = platform.system() == 'Windows'
    has_exe = installed.get("has_exe", False)
    
    if is_windows and has_exe:
        # Find and run EXE
        exe_files = list(install_path.glob('*.exe'))
        if exe_files:
            exe_path = exe_files[0]
            log(f"Запуск: {exe_path}")
            
            try:
                # Run EXE in its directory
                subprocess.Popen(
                    [str(exe_path)],
                    cwd=str(install_path),
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                )
                return True
            except Exception as e:
                log(f"Ошибка запуска EXE: {e}")
                # Fall through to Python engine
    
    # Run via Python engine in separate process (required for macOS)
    json_path = install_path / 'game.json'
    if not json_path.exists():
        log("Файл game.json не найден")
        return False
    
    engine_path = install_path / 'engine.py'
    story_path = install_path / 'story.py'
    
    if engine_path.exists() and story_path.exists():
        log(f"Запуск игры: {json_path}")
        
        # Create a runner script that will be executed in a new process
        runner_code = f'''
import sys
sys.path.insert(0, r"{install_path}")

from story import Story
from engine import VisualNovelEngine

story = Story.load(r"{json_path}")
saves_dir = r"{install_path / 'saves'}"

engine = VisualNovelEngine(1280, 720, story.title, save_dir=saves_dir)
engine.load_story(story)
engine.run()
'''
        
        try:
            # Run in separate process - required for pygame on macOS
            if platform.system() == 'Windows':
                # On Windows, use CREATE_NEW_CONSOLE for separate window
                subprocess.Popen(
                    [sys.executable, '-c', runner_code],
                    cwd=str(install_path),
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                # On macOS/Linux, just spawn new process
                subprocess.Popen(
                    [sys.executable, '-c', runner_code],
                    cwd=str(install_path),
                    start_new_session=True
                )
            
            log("✓ Игра запущена")
            return True
            
        except Exception as e:
            log(f"Ошибка запуска: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        log("Модули движка не найдены в установленной игре")
        return False


# ============================================================================
# FORK GAME
# ============================================================================

def fork_game(game_id: str, hwid: str) -> Optional[str]:
    """
    Fork a game on the server.
    
    Args:
        game_id: Original game ID
        hwid: Hardware ID of the forker
        
    Returns:
        New game ID if successful, None otherwise
    """
    try:
        response = api_request(
            f'/api/fork/{game_id}',
            method='POST',
            data={'hwid': hwid}
        )
        return response.get('game_id')
    except Exception as e:
        print(f"Fork error: {e}")
        return None


def download_fork_for_editing(game_id: str, dest_dir: str, log_callback: Callable = None) -> bool:
    """
    Download a forked game for editing in the editor.
    
    Args:
        game_id: Game ID to download
        dest_dir: Destination directory for the project
        log_callback: Function(message) for log messages
        
    Returns:
        True if successful
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)
    
    try:
        log(f"Скачивание проекта {game_id}...")
        
        # Download ZIP
        download_url = get_download_url(game_id)
        
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp_path = tmp.name
        
        if not download_file(download_url, tmp_path):
            log("Ошибка загрузки")
            return False
        
        # Extract to dest_dir
        os.makedirs(dest_dir, exist_ok=True)
        
        log("Распаковка...")
        with zipfile.ZipFile(tmp_path, 'r') as zf:
            zf.extractall(dest_dir)
        
        os.remove(tmp_path)
        
        log(f"✓ Проект сохранён: {dest_dir}")
        return True
        
    except Exception as e:
        log(f"Ошибка: {e}")
        return False


# ============================================================================
# UPLOAD GAME
# ============================================================================

def upload_game(
    zip_path: str,
    name: str,
    version: str,
    description: str,
    author: str,
    hwid: str,
    game_id: str = None,
    forked_from: str = None,
    thumbnail_path: str = None,
    progress_callback: Callable = None,
    log_callback: Callable = None
) -> Optional[str]:
    """
    Upload a game to the server.
    
    Args:
        zip_path: Path to game ZIP file
        name: Game name
        version: Game version
        description: Game description
        author: Author name
        hwid: Hardware ID
        game_id: Existing game ID for update (optional)
        forked_from: Original game ID if fork (optional)
        thumbnail_path: Path to thumbnail PNG (optional)
        progress_callback: Function(current, total) for progress
        log_callback: Function(message) for log messages
        
    Returns:
        Game ID if successful, None otherwise
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)
    
    def progress(current, total):
        if progress_callback:
            progress_callback(current, total)
    
    if not HAS_REQUESTS:
        log("Ошибка: для загрузки требуется библиотека 'requests'")
        return None
    
    try:
        log(f"Загрузка на сервер: {name} v{version}")
        
        url = f"{get_server_url()}/api/upload"
        
        # Get file size for progress
        file_size = os.path.getsize(zip_path)
        file_size_mb = file_size / (1024 * 1024)
        log(f"Размер файла: {file_size_mb:.1f} МБ")
        
        # Prepare form data
        data = {
            'name': name,
            'version': version,
            'description': description,
            'author': author,
            'hwid': hwid
        }
        
        if game_id:
            data['game_id'] = game_id
        if forked_from:
            data['forked_from'] = forked_from
        
        # Read files into memory for progress tracking
        log("Подготовка файлов...")
        with open(zip_path, 'rb') as f:
            zip_data = f.read()
        
        thumb_data = None
        if thumbnail_path and os.path.exists(thumbnail_path):
            with open(thumbnail_path, 'rb') as f:
                thumb_data = f.read()
        
        # Create multipart encoder with progress
        from io import BytesIO
        
        # Build multipart form data manually for progress tracking
        import uuid
        boundary = uuid.uuid4().hex
        
        body_parts = []
        
        # Add form fields
        for key, value in data.items():
            body_parts.append(f'--{boundary}\r\n'.encode())
            body_parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            body_parts.append(f'{value}\r\n'.encode())
        
        # Add ZIP file
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(b'Content-Disposition: form-data; name="file"; filename="game.zip"\r\n')
        body_parts.append(b'Content-Type: application/zip\r\n\r\n')
        body_parts.append(zip_data)
        body_parts.append(b'\r\n')
        
        # Add thumbnail if exists
        if thumb_data:
            body_parts.append(f'--{boundary}\r\n'.encode())
            body_parts.append(b'Content-Disposition: form-data; name="thumbnail"; filename="thumbnail.png"\r\n')
            body_parts.append(b'Content-Type: image/png\r\n\r\n')
            body_parts.append(thumb_data)
            body_parts.append(b'\r\n')
        
        body_parts.append(f'--{boundary}--\r\n'.encode())
        
        body = b''.join(body_parts)
        total_size = len(body)
        
        log(f"Отправка на сервер ({total_size / (1024*1024):.1f} МБ)...")
        
        # Custom upload with progress
        class ProgressReader:
            def __init__(self, data, callback, log_func):
                self.data = BytesIO(data)
                self.total = len(data)
                self.uploaded = 0
                self.callback = callback
                self.log_func = log_func
                self.last_percent = -1
                
            def read(self, size=-1):
                chunk = self.data.read(size)
                if chunk:
                    self.uploaded += len(chunk)
                    percent = int(self.uploaded * 100 / self.total)
                    # Report every 1%
                    if percent != self.last_percent:
                        self.log_func(f"  Загружено: {percent}% ({self.uploaded / (1024*1024):.1f} / {self.total / (1024*1024):.1f} МБ)")
                        self.last_percent = percent
                    if self.callback:
                        self.callback(self.uploaded, self.total)
                return chunk
            
            def __len__(self):
                return self.total
        
        progress_reader = ProgressReader(body, progress, log)
        
        headers = {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(total_size)
        }
        
        response = requests.post(url, data=progress_reader, headers=headers, timeout=600)
        
        response.raise_for_status()
        result = response.json()
        
        if result.get('success'):
            new_game_id = result.get('game_id')
            log(f"✓ Игра загружена! ID: {new_game_id}")
            return new_game_id
        else:
            log(f"Ошибка: {result.get('error', 'Unknown error')}")
            return None
            
    except requests.exceptions.ConnectionError:
        log("Ошибка: не удалось подключиться к серверу")
        return None
    except requests.exceptions.Timeout:
        log("Ошибка: превышено время ожидания")
        return None
    except Exception as e:
        log(f"Ошибка: {e}")
        return None


def delete_game(
    game_id: str,
    hwid: str,
    log_callback: Callable = None
) -> bool:
    """
    Delete a game from the server.
    
    Args:
        game_id: Game ID to delete
        hwid: Hardware ID (must be the author)
        log_callback: Function(message) for log messages
        
    Returns:
        True if successful, False otherwise
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)
    
    if not HAS_REQUESTS:
        log("Ошибка: для удаления требуется библиотека 'requests'")
        return False
    
    try:
        log(f"Удаление игры {game_id} с сервера...")
        
        url = f"{get_server_url()}/api/games/{game_id}"
        
        response = requests.delete(url, params={'hwid': hwid}, timeout=30)
        
        if response.status_code == 403:
            log("Ошибка: вы не являетесь автором этой игры")
            return False
        elif response.status_code == 404:
            log("Ошибка: игра не найдена на сервере")
            return False
        
        response.raise_for_status()
        result = response.json()
        
        if result.get('success'):
            log("✓ Игра удалена с сервера")
            return True
        else:
            log(f"Ошибка: {result.get('error', 'Unknown error')}")
            return False
            
    except requests.exceptions.ConnectionError:
        log("Ошибка: не удалось подключиться к серверу")
        return False
    except requests.exceptions.Timeout:
        log("Ошибка: превышено время ожидания")
        return False
    except Exception as e:
        log(f"Ошибка: {e}")
        return False


# ============================================================================
# THUMBNAIL CACHE
# ============================================================================

def get_cached_thumbnail(game_id: str) -> Optional[bytes]:
    """Get cached thumbnail for a game."""
    cache_dir = get_cache_directory() / 'thumbnails'
    cache_path = cache_dir / f"{game_id}.png"
    
    if cache_path.exists():
        with open(cache_path, 'rb') as f:
            return f.read()
    return None


def cache_thumbnail(game_id: str, data: bytes):
    """Cache a thumbnail."""
    cache_dir = get_cache_directory() / 'thumbnails'
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    cache_path = cache_dir / f"{game_id}.png"
    with open(cache_path, 'wb') as f:
        f.write(data)


def download_thumbnail(game_id: str) -> Optional[bytes]:
    """Download and cache a thumbnail."""
    try:
        url = get_thumbnail_url(game_id)
        
        if HAS_REQUESTS:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.content
                cache_thumbnail(game_id, data)
                return data
        else:
            with urlopen(url, timeout=10) as response:
                data = response.read()
                cache_thumbnail(game_id, data)
                return data
                
    except Exception as e:
        print(f"Thumbnail download error: {e}")
    
    return None


def get_thumbnail(game_id: str) -> Optional[bytes]:
    """Get thumbnail (from cache or download)."""
    # Try cache first
    cached = get_cached_thumbnail(game_id)
    if cached:
        return cached
    
    # Download
    return download_thumbnail(game_id)


if __name__ == '__main__':
    # Test client
    print(f"Server URL: {get_server_url()}")
    print(f"Games directory: {get_games_directory()}")
    print(f"Cache directory: {get_cache_directory()}")
    
    print("\nFetching games list...")
    try:
        games = get_games_list()
        print(f"Found {len(games)} games:")
        for game in games:
            print(f"  - {game['name']} v{game['version']} ({game['game_id']})")
    except Exception as e:
        print(f"Error: {e}")
