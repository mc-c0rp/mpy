"""
Модуль для сборки визуальной новеллы в standalone EXE.
Собирает все ассеты, создаёт автономный билд с PyInstaller.
"""

import os
import sys
import json
import shutil
import subprocess
import tempfile
import zipfile
import hashlib
from typing import Set, Optional, Tuple

# PIL is optional - only needed for thumbnail generation
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def collect_assets_from_json(json_path: str) -> Set[str]:
    """
    Собрать все пути к ассетам из JSON файла проекта.
    
    Returns:
        Множество абсолютных путей к файлам ассетов
    """
    assets = set()
    base_dir = os.path.dirname(os.path.abspath(json_path))
    
    def resolve_path(path: str) -> str:
        """Преобразовать относительный путь в абсолютный."""
        if not path:
            return ""
        if os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(base_dir, path))
    
    def add_asset(path: str):
        """Добавить ассет если существует."""
        if path:
            abs_path = resolve_path(path)
            if abs_path and os.path.exists(abs_path):
                assets.add(abs_path)
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Собираем изображения персонажей
    for char_data in data.get('characters', {}).values():
        for image_path in char_data.get('images', {}).values():
            add_asset(image_path)
    
    # Собираем ассеты из главного меню
    main_menu = data.get('main_menu', {})
    if main_menu:
        add_asset(main_menu.get('background', ''))
        # Логотип
        logo = main_menu.get('logo', {})
        if logo:
            add_asset(logo.get('image_path', ''))
        # Звуки главного меню
        sounds = main_menu.get('sounds', {})
        if sounds:
            add_asset(sounds.get('background_music', ''))
            add_asset(sounds.get('hover_sound', ''))
            add_asset(sounds.get('click_sound', ''))
            add_asset(sounds.get('back_sound', ''))
    
    # Собираем ассеты из меню паузы
    pause_menu = data.get('pause_menu', {})
    if pause_menu:
        add_asset(pause_menu.get('open_sound', ''))
        add_asset(pause_menu.get('close_sound', ''))
        add_asset(pause_menu.get('hover_sound', ''))
        add_asset(pause_menu.get('click_sound', ''))
    
    # Собираем ассеты из сцен
    for scene_data in data.get('scenes', {}).values():
        # Фон
        add_asset(scene_data.get('background', ''))
        
        # Музыка
        add_asset(scene_data.get('music', ''))
        
        # Изображения на сцене
        for img in scene_data.get('images_on_screen', []):
            add_asset(img.get('path', ''))
        
        # Звуки в диалогах
        for dialog in scene_data.get('dialogs', []):
            add_asset(dialog.get('sound_file', ''))
    
    return assets


def create_relative_json(json_path: str, assets_mapping: dict, output_path: str):
    """
    Создать копию JSON с относительными путями к ассетам для билда.
    
    Args:
        json_path: Путь к оригинальному JSON
        assets_mapping: Словарь {абсолютный_путь: относительный_путь_в_билде}
        output_path: Куда сохранить новый JSON
    """
    base_dir = os.path.dirname(os.path.abspath(json_path))
    
    def resolve_path(path: str) -> str:
        """Преобразовать относительный путь в абсолютный."""
        if not path:
            return ""
        if os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(base_dir, path))
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    def replace_path(path: str) -> str:
        """Заменить путь на относительный для билда."""
        if not path:
            return path
        # Сначала преобразуем в абсолютный путь
        abs_path = resolve_path(path)
        # Затем ищем в маппинге
        return assets_mapping.get(abs_path, path)
    
    # Заменяем пути в персонажах
    for char_data in data.get('characters', {}).values():
        images = char_data.get('images', {})
        for emotion, path in images.items():
            images[emotion] = replace_path(path)
    
    # Заменяем пути в главном меню
    main_menu = data.get('main_menu', {})
    if main_menu:
        if main_menu.get('background'):
            main_menu['background'] = replace_path(main_menu['background'])
        # Логотип
        logo = main_menu.get('logo', {})
        if logo and logo.get('image_path'):
            logo['image_path'] = replace_path(logo['image_path'])
        # Звуки главного меню
        sounds = main_menu.get('sounds', {})
        if sounds:
            if sounds.get('background_music'):
                sounds['background_music'] = replace_path(sounds['background_music'])
            if sounds.get('hover_sound'):
                sounds['hover_sound'] = replace_path(sounds['hover_sound'])
            if sounds.get('click_sound'):
                sounds['click_sound'] = replace_path(sounds['click_sound'])
            if sounds.get('back_sound'):
                sounds['back_sound'] = replace_path(sounds['back_sound'])
    
    # Заменяем пути в меню паузы
    pause_menu = data.get('pause_menu', {})
    if pause_menu:
        if pause_menu.get('open_sound'):
            pause_menu['open_sound'] = replace_path(pause_menu['open_sound'])
        if pause_menu.get('close_sound'):
            pause_menu['close_sound'] = replace_path(pause_menu['close_sound'])
        if pause_menu.get('hover_sound'):
            pause_menu['hover_sound'] = replace_path(pause_menu['hover_sound'])
        if pause_menu.get('click_sound'):
            pause_menu['click_sound'] = replace_path(pause_menu['click_sound'])
    
    # Заменяем пути в сценах
    for scene_data in data.get('scenes', {}).values():
        # Фон
        if scene_data.get('background'):
            scene_data['background'] = replace_path(scene_data['background'])
        
        # Музыка
        if scene_data.get('music'):
            scene_data['music'] = replace_path(scene_data['music'])
        
        # Изображения на сцене
        for img in scene_data.get('images_on_screen', []):
            if img.get('path'):
                img['path'] = replace_path(img['path'])
        
        # Звуки в диалогах
        for dialog in scene_data.get('dialogs', []):
            if dialog.get('sound_file'):
                dialog['sound_file'] = replace_path(dialog['sound_file'])
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def create_launcher_script(output_dir: str, json_name: str, game_title: str) -> str:
    """
    Создать скрипт запуска игры для PyInstaller.
    
    Returns:
        Путь к созданному скрипту
    """
    launcher_code = f'''#!/usr/bin/env python3
"""
Автосгенерированный лаунчер игры.
"""

import os
import sys

# Определяем базовую директорию (работает и для скрипта, и для exe)
if getattr(sys, 'frozen', False):
    # Запущен как exe (PyInstaller)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Запущен как скрипт
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Добавляем BASE_DIR в путь для импортов
sys.path.insert(0, BASE_DIR)

# Устанавливаем рабочую директорию
os.chdir(BASE_DIR)

def show_error(message):
    """Показать ошибку в GUI или консоли."""
    print(message)
    try:
        # Попробуем показать GUI диалог
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Ошибка", message)
        root.destroy()
    except:
        # Если GUI недоступен, просто ждём
        try:
            if sys.stdin and sys.stdin.readable():
                input("Нажмите Enter для выхода...")
        except:
            pass

def main():
    from engine import VisualNovelEngine
    from story import Story
    
    json_path = os.path.join(BASE_DIR, "data", "{json_name}")
    
    if not os.path.exists(json_path):
        show_error(f"Ошибка: файл {{json_path}} не найден!")
        return
    
    try:
        story = Story.load(json_path)
        engine = VisualNovelEngine(1280, 720, story.title or "{game_title}")
        engine.load_story(story)
        engine.run()
    except Exception as e:
        import traceback
        error_msg = f"Ошибка: {{e}}\n\n{{traceback.format_exc()}}"
        show_error(error_msg)


if __name__ == "__main__":
    main()
'''
    
    launcher_path = os.path.join(output_dir, "game_launcher.py")
    with open(launcher_path, 'w', encoding='utf-8') as f:
        f.write(launcher_code)
    
    return launcher_path


def build_game(
    json_path: str,
    output_dir: str,
    game_title: str,
    progress_callback=None,
    log_callback=None
) -> bool:
    """
    Собрать игру в standalone пакет с EXE.
    
    Args:
        json_path: Путь к JSON файлу проекта
        output_dir: Папка для билда
        game_title: Название игры (для exe)
        progress_callback: Функция для обновления прогресса (0-100)
        log_callback: Функция для вывода логов
        
    Returns:
        True если сборка успешна, False если ошибка
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)
    
    def progress(value):
        if progress_callback:
            progress_callback(value)
    
    try:
        # Получаем директорию движка
        engine_dir = os.path.dirname(os.path.abspath(__file__))
        
        log("=" * 50)
        log("Начинаем сборку игры...")
        log(f"Проект: {json_path}")
        log(f"Выходная папка: {output_dir}")
        log("=" * 50)
        
        progress(5)
        
        # Создаём структуру папок
        os.makedirs(output_dir, exist_ok=True)
        data_dir = os.path.join(output_dir, "data")
        assets_dir = os.path.join(data_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)
        
        log("✓ Созданы папки билда")
        progress(10)
        
        # Собираем ассеты
        log("Сбор ассетов из проекта...")
        assets = collect_assets_from_json(json_path)
        log(f"  Найдено {len(assets)} файлов ассетов")
        
        progress(15)
        
        # Копируем ассеты и создаём маппинг путей
        assets_mapping = {}
        total_assets = len(assets)
        
        for i, asset_path in enumerate(assets):
            if not os.path.exists(asset_path):
                log(f"  ⚠ Файл не найден: {asset_path}")
                continue
            
            # Создаём относительный путь в папке assets
            filename = os.path.basename(asset_path)
            # Добавляем хеш в имя чтобы избежать конфликтов
            name, ext = os.path.splitext(filename)
            unique_name = f"{name}_{hash(asset_path) % 10000:04d}{ext}"
            
            target_path = os.path.join(assets_dir, unique_name)
            # Путь относительно папки data/ (где лежит JSON)
            relative_path = os.path.join("assets", unique_name)
            
            shutil.copy2(asset_path, target_path)
            assets_mapping[asset_path] = relative_path
            
            # Обновляем прогресс
            current_progress = 15 + int((i + 1) / total_assets * 20)
            progress(current_progress)
        
        log(f"✓ Скопировано {len(assets_mapping)} файлов ассетов")
        progress(35)
        
        # Создаём JSON с относительными путями
        json_name = os.path.basename(json_path)
        output_json = os.path.join(data_dir, json_name)
        create_relative_json(json_path, assets_mapping, output_json)
        log(f"✓ Создан {json_name} с относительными путями")
        
        progress(40)
        
        # Копируем модули движка
        log("Копирование модулей движка...")
        modules = ['engine.py', 'story.py']
        for module in modules:
            src = os.path.join(engine_dir, module)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(output_dir, module))
                log(f"  ✓ {module}")
        
        progress(45)
        
        # Создаём лаунчер
        log("Создание лаунчера...")
        launcher_path = create_launcher_script(output_dir, json_name, game_title)
        log(f"✓ Создан game_launcher.py")
        
        progress(50)
        
        # Проверяем наличие PyInstaller
        log("Проверка PyInstaller...")
        python_exe = sys.executable
        try:
            result = subprocess.run(
                [python_exe, '-m', 'pip', 'show', 'pyinstaller'],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                log("PyInstaller не установлен. Устанавливаем...")
                # Пробуем разные способы установки
                install_cmds = [
                    [python_exe, '-m', 'pip', 'install', 'pyinstaller'],
                    [python_exe, '-m', 'pip', 'install', '--user', 'pyinstaller'],
                    [python_exe, '-m', 'pip', 'install', '--break-system-packages', 'pyinstaller'],
                ]
                installed = False
                for cmd in install_cmds:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode == 0:
                            installed = True
                            log("✓ PyInstaller установлен")
                            break
                    except:
                        continue
                if not installed:
                    log("⚠ Не удалось установить PyInstaller автоматически")
        except Exception as e:
            log(f"⚠ Ошибка проверки PyInstaller: {e}")
        
        progress(55)
        
        # Собираем EXE
        log("Сборка EXE файла (это может занять несколько минут)...")
        
        # Безопасное имя для exe
        safe_title = "".join(c for c in game_title if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_') or "game"
        
        # Формируем команду PyInstaller
        pyinstaller_cmd = [
            python_exe, '-m', 'PyInstaller',
            '--onefile',
            '--noconsole',
            f'--name={safe_title}',
            f'--distpath={output_dir}',
            f'--workpath={os.path.join(output_dir, "build_temp")}',
            f'--specpath={os.path.join(output_dir, "build_temp")}',
            '--clean',
            launcher_path
        ]
        
        log(f"Команда: {' '.join(pyinstaller_cmd)}")
        
        # Запускаем PyInstaller
        process = subprocess.Popen(
            pyinstaller_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=output_dir
        )
        
        # Читаем вывод
        progress_base = 55
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                line = line.strip()
                if line:
                    log(f"  {line}")
                # Примерный прогресс на основе вывода PyInstaller
                if "Analyzing" in line:
                    progress(progress_base + 5)
                elif "Processing" in line:
                    progress(progress_base + 15)
                elif "Building" in line:
                    progress(progress_base + 25)
                elif "Copying" in line:
                    progress(progress_base + 30)
        
        if process.returncode != 0:
            log(f"✗ Ошибка PyInstaller (код {process.returncode})")
            return False
        
        log("✓ EXE файл создан")
        progress(90)
        
        # Очистка временных файлов
        log("Очистка временных файлов...")
        temp_dirs = ['build_temp', '__pycache__']
        for temp_dir in temp_dirs:
            temp_path = os.path.join(output_dir, temp_dir)
            if os.path.exists(temp_path):
                shutil.rmtree(temp_path, ignore_errors=True)
        
        # Удаляем лаунчер и модули (они уже в exe)
        for f in ['game_launcher.py', 'engine.py', 'story.py']:
            fpath = os.path.join(output_dir, f)
            if os.path.exists(fpath):
                os.remove(fpath)
        
        log("✓ Временные файлы удалены")
        progress(95)
        
        # Итоговая информация
        exe_path = os.path.join(output_dir, f"{safe_title}.exe")
        if os.path.exists(exe_path):
            exe_size = os.path.getsize(exe_path) / (1024 * 1024)
            log("")
            log("=" * 50)
            log("забилдил заебись")
            log(f"  EXE: {exe_path}")
            log(f"  Размер: {exe_size:.1f} МБ")
            log(f"  Директория: {data_dir}")
            log("=" * 50)
            log("")
            log(f"{os.path.basename(output_dir)}")
        
        progress(100)
        return True
        
    except Exception as e:
        log(f"✗ ОШИБКА: {e}")
        import traceback
        log(traceback.format_exc())
        return False


if __name__ == "__main__":
    # Тест сборки
    import sys
    if len(sys.argv) < 3:
        print("Использование: python builder.py <json_path> <output_dir>")
        sys.exit(1)
    
    success = build_game(sys.argv[1], sys.argv[2], "Test Game")
    sys.exit(0 if success else 1)


# ============================================================================
# BUILD FOR UPLOAD (SERVER DISTRIBUTION)
# ============================================================================

MAX_UPLOAD_SIZE = 1024 * 1024 * 1024  # 1 GB limit


def get_thumbnail_from_project(json_path: str, size: Tuple[int, int] = (400, 225)) -> Optional[bytes]:
    """
    Извлечь миниатюру из фона главного меню проекта.
    
    Args:
        json_path: Путь к JSON файлу проекта
        size: Размер миниатюры (ширина, высота)
        
    Returns:
        PNG-данные миниатюры или None
    """
    if not HAS_PIL:
        print("Предупреждение: PIL/Pillow не установлен, миниатюра не будет создана")
        return None
    
    base_dir = os.path.dirname(os.path.abspath(json_path))
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Получаем путь к фону главного меню
        bg_path = data.get('main_menu', {}).get('background', '')
        
        if not bg_path:
            # Пробуем первую сцену
            scenes = data.get('scenes', {})
            if scenes:
                first_scene = list(scenes.values())[0]
                bg_path = first_scene.get('background', '')
        
        if not bg_path:
            return None
        
        # Преобразуем относительный путь в абсолютный
        if not os.path.isabs(bg_path):
            bg_path = os.path.normpath(os.path.join(base_dir, bg_path))
        
        if not os.path.exists(bg_path):
            return None
        
        # Загружаем и ресайзим изображение
        img = Image.open(bg_path)
        img = img.convert('RGB')
        img.thumbnail(size, Image.Resampling.LANCZOS)
        
        # Создаём изображение точного размера с чёрными полосами
        thumb = Image.new('RGB', size, (0, 0, 0))
        offset = ((size[0] - img.width) // 2, (size[1] - img.height) // 2)
        thumb.paste(img, offset)
        
        # Конвертируем в PNG байты
        import io
        buffer = io.BytesIO()
        thumb.save(buffer, format='PNG', optimize=True)
        return buffer.getvalue()
        
    except Exception as e:
        print(f"Ошибка создания миниатюры: {e}")
        return None


def calculate_project_size(json_path: str) -> int:
    """
    Рассчитать общий размер проекта (JSON + все ассеты).
    
    Returns:
        Размер в байтах
    """
    total_size = os.path.getsize(json_path)
    assets = collect_assets_from_json(json_path)
    
    for asset_path in assets:
        if os.path.exists(asset_path):
            total_size += os.path.getsize(asset_path)
    
    return total_size


def build_for_upload(
    json_path: str,
    output_zip_path: str,
    include_exe: bool = True,
    progress_callback=None,
    log_callback=None
) -> Tuple[bool, str, Optional[bytes]]:
    """
    Собрать проект в ZIP-архив для загрузки на сервер.
    
    Структура архива:
    - game.json - файл проекта с относительными путями
    - assets/ - папка с ассетами
    - engine.py, story.py - модули движка (для non-Windows)
    - game.exe (опционально) - EXE для Windows
    - metadata.json - метаданные (название, версия, описание и т.д.)
    
    Args:
        json_path: Путь к JSON файлу проекта
        output_zip_path: Путь для выходного ZIP файла
        include_exe: Включать ли EXE файл для Windows
        progress_callback: Функция прогресса (0-100)
        log_callback: Функция логирования
        
    Returns:
        (success: bool, error_message: str, thumbnail_bytes: Optional[bytes])
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)
    
    def progress(value):
        if progress_callback:
            progress_callback(value)
    
    try:
        engine_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(os.path.abspath(json_path))
        
        log("=" * 50)
        log("Подготовка к загрузке на сервер...")
        log(f"Проект: {json_path}")
        log("=" * 50)
        
        progress(5)
        
        # Проверяем размер проекта
        log("Проверка размера проекта...")
        total_size = calculate_project_size(json_path)
        size_mb = total_size / (1024 * 1024)
        log(f"  Общий размер: {size_mb:.1f} МБ")
        
        if total_size > MAX_UPLOAD_SIZE:
            return False, f"Проект слишком большой ({size_mb:.0f} МБ). Максимум: {MAX_UPLOAD_SIZE // (1024*1024)} МБ", None
        
        progress(10)
        
        # Создаём временную директорию для сборки
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = os.path.join(temp_dir, "build")
            os.makedirs(build_dir)
            assets_dir = os.path.join(build_dir, "assets")
            os.makedirs(assets_dir)
            
            # Собираем ассеты
            log("Сбор ассетов...")
            assets = collect_assets_from_json(json_path)
            assets_mapping = {}
            
            for i, asset_path in enumerate(assets):
                if not os.path.exists(asset_path):
                    log(f"  ⚠ Не найден: {asset_path}")
                    continue
                
                filename = os.path.basename(asset_path)
                name, ext = os.path.splitext(filename)
                # Уникальное имя через хеш содержимого
                with open(asset_path, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()[:8]
                unique_name = f"{name}_{file_hash}{ext}"
                
                target_path = os.path.join(assets_dir, unique_name)
                shutil.copy2(asset_path, target_path)
                assets_mapping[asset_path] = f"assets/{unique_name}"
                
                progress(10 + int((i + 1) / len(assets) * 30) if assets else 10)
            
            log(f"✓ Скопировано {len(assets_mapping)} ассетов")
            progress(40)
            
            # Создаём JSON с относительными путями
            game_json_path = os.path.join(build_dir, "game.json")
            create_relative_json(json_path, assets_mapping, game_json_path)
            log("✓ Создан game.json")
            
            progress(45)
            
            # Копируем модули движка
            log("Копирование модулей движка...")
            for module in ['engine.py', 'story.py']:
                src = os.path.join(engine_dir, module)
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(build_dir, module))
            log("✓ Модули скопированы")
            
            progress(50)
            
            # Генерируем миниатюру
            log("Создание миниатюры...")
            thumbnail_bytes = get_thumbnail_from_project(json_path)
            if thumbnail_bytes:
                thumb_path = os.path.join(build_dir, "thumbnail.png")
                with open(thumb_path, 'wb') as f:
                    f.write(thumbnail_bytes)
                log("✓ Миниатюра создана")
            else:
                log("⚠ Не удалось создать миниатюру")
            
            progress(55)
            
            # Опционально собираем EXE
            exe_path = None
            if include_exe:
                log("Сборка EXE для Windows...")
                
                # Читаем название игры из JSON
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                game_title = data.get('title', 'game')
                
                # Создаём временную папку для EXE билда
                exe_build_dir = os.path.join(temp_dir, "exe_build")
                os.makedirs(exe_build_dir)
                
                # Собираем EXE (используем существующую функцию)
                def exe_progress(val):
                    # Маппим прогресс EXE сборки на 55-85%
                    progress(55 + int(val * 0.3))
                
                exe_success = build_game(
                    json_path, 
                    exe_build_dir, 
                    game_title,
                    progress_callback=exe_progress,
                    log_callback=log
                )
                
                if exe_success:
                    # Находим EXE файл
                    for f in os.listdir(exe_build_dir):
                        if f.endswith('.exe'):
                            exe_path = os.path.join(exe_build_dir, f)
                            # Копируем в build_dir
                            shutil.copy2(exe_path, os.path.join(build_dir, f))
                            log(f"✓ EXE добавлен: {f}")
                            break
                else:
                    log("⚠ Не удалось собрать EXE, продолжаем без него")
            
            progress(85)
            
            # Создаём ZIP архив
            log("Создание ZIP-архива...")
            
            with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
                for root, dirs, files in os.walk(build_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_name = os.path.relpath(file_path, build_dir)
                        zf.write(file_path, arc_name)
            
            zip_size = os.path.getsize(output_zip_path) / (1024 * 1024)
            log(f"✓ ZIP создан: {zip_size:.1f} МБ")
            
            progress(95)
            
            # Проверяем финальный размер
            if os.path.getsize(output_zip_path) > MAX_UPLOAD_SIZE:
                os.remove(output_zip_path)
                return False, f"Сжатый архив слишком большой ({zip_size:.0f} МБ). Максимум: {MAX_UPLOAD_SIZE // (1024*1024)} МБ", None
            
            log("")
            log("=" * 50)
            log("✓ Готово к загрузке!")
            log(f"  Архив: {output_zip_path}")
            log(f"  Размер: {zip_size:.1f} МБ")
            log("=" * 50)
            
            progress(100)
            return True, "", thumbnail_bytes
            
    except Exception as e:
        import traceback
        error_msg = f"Ошибка сборки: {e}\n{traceback.format_exc()}"
        log(f"✗ {error_msg}")
        return False, error_msg, None
