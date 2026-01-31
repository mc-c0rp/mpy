"""
Визуальная новелла - Главный файл.
Точка входа для запуска GUI-лаунчера, игры или редактора.
"""

import sys
import os
import subprocess


# Необходимые пакеты: (имя для import, имя для pip install)
REQUIRED_PACKAGES = [
    ("pygame", "pygame-ce"),      # pygame-ce - улучшенная версия pygame
    ("PIL", "Pillow"),            # Pillow для работы с изображениями
    ("requests", "requests"),     # requests для HTTP запросов
    ("tkinter", None),            # tkinter - встроен в Python, но проверим
]


def check_and_install_packages():
    """Проверить и установить необходимые пакеты автоматически."""
    missing_packages = []
    
    for import_name, pip_name in REQUIRED_PACKAGES:
        try:
            __import__(import_name)
        except ImportError:
            if pip_name:  # Можно установить через pip
                missing_packages.append((import_name, pip_name))
            else:
                # tkinter не установлен - нужна ручная установка
                print(f"ОШИБКА: {import_name} не установлен.")
                if import_name == "tkinter":
                    print("Для установки tkinter:")
                    print("  macOS: brew install python-tk")
                    print("  Ubuntu/Debian: sudo apt-get install python3-tk")
                    print("  Windows: переустановите Python с галочкой 'tcl/tk'")
                return False
    
    if not missing_packages:
        return True
    
    print("=" * 50)
    print("Установка недостающих пакетов...")
    print("=" * 50)
    
    for import_name, pip_name in missing_packages:
        print(f"  Установка {pip_name}...")
        
        # Попробуем разные способы установки
        install_commands = [
            # Способ 1: обычная установка
            [sys.executable, '-m', 'pip', 'install', pip_name, '-q'],
            # Способ 2: с --user
            [sys.executable, '-m', 'pip', 'install', pip_name, '--user', '-q'],
            # Способ 3: с --break-system-packages (для Homebrew Python на macOS)
            [sys.executable, '-m', 'pip', 'install', pip_name, '--break-system-packages', '-q'],
            # Способ 4: с --user и --break-system-packages
            [sys.executable, '-m', 'pip', 'install', pip_name, '--user', '--break-system-packages', '-q'],
        ]
        
        installed = False
        for cmd in install_commands:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"  ✓ {pip_name}")
                    installed = True
                    break
            except Exception:
                continue
        
        if not installed:
            print(f"  ✗ Не удалось установить {pip_name}")
            print(f"    Попробуйте вручную: pip install {pip_name}")
            print(f"    Или создайте venv: python3 -m venv venv && source venv/bin/activate")
            return False
    
    print("\n✓ Все пакеты установлены!")
    return True


def run_launcher():
    """Запустить GUI-лаунчер."""
    from launcher import main as launcher_main
    launcher_main()


def run_editor():
    """Запустить редактор."""
    from editor import main as editor_main
    
    print("Запуск редактора...")
    editor_main()


def run_game_from_file(filepath: str = None):
    """Запустить игру из файла."""
    from engine import VisualNovelEngine
    from story import Story
    
    if filepath:
        # Прямой запуск из указанного файла
        story = Story.load(filepath)
        
        # Сохранения рядом с файлом игры
        save_dir = os.path.join(os.path.dirname(filepath), 'saves')
        os.makedirs(save_dir, exist_ok=True)
        
        engine = VisualNovelEngine(1280, 720, story.title, save_dir=save_dir)
        engine.load_story(story)
        engine.run()
        return
    
    # Папка с проектами
    projects_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "projects")
    
    # Получаем список .json файлов
    if os.path.exists(projects_dir):
        projects = [f for f in os.listdir(projects_dir) if f.endswith('.json')]
    else:
        projects = []
    
    if not projects:
        print("В папке 'projects' нет проектов (.json файлов)")
        return
    
    print("\nДоступные проекты:")
    for i, proj in enumerate(projects, 1):
        print(f"  {i}. {proj}")
    print(f"  0. Отмена")
    print()
    
    choice = input("Выберите проект (номер): ").strip()
    
    if choice == '0' or not choice:
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(projects):
            filepath = os.path.join(projects_dir, projects[idx])
        else:
            print("Неверный номер!")
            return
    except ValueError:
        print("Введите число!")
        return
    
    try:
        story = Story.load(filepath)
        print(f"Загружена история: {story.title}")
        
        # Сохранения рядом с файлом игры
        save_dir = os.path.join(os.path.dirname(filepath), 'saves')
        os.makedirs(save_dir, exist_ok=True)
        
        engine = VisualNovelEngine(1280, 720, story.title, save_dir=save_dir)
        engine.load_story(story)
        engine.run()
    except Exception as e:
        print(f"Ошибка при загрузке: {e}")


def main():
    """Главная функция."""
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg in ('--editor', '-e'):
            run_editor()
            return
        
        elif arg in ('--play', '-p') and len(sys.argv) > 2:
            run_game_from_file(sys.argv[2])
            return
        
        elif arg in ('--console', '-c'):
            # Запуск в консольном режиме (старое поведение)
            _run_console_menu()
            return
        
        elif arg in ('--help', '-h'):
            print("Использование:")
            print("  python main.py              - GUI лаунчер")
            print("  python main.py --editor     - Запустить редактор")
            print("  python main.py --play FILE  - Запустить игру из файла")
            print("  python main.py --console    - Консольное меню (старый режим)")
            return
    
    # По умолчанию запускаем GUI-лаунчер
    run_launcher()


def _run_console_menu():
    """Консольное меню (старое поведение)."""
    while True:
        print("\n" + "=" * 50)
        print("    mpy")
        print("=" * 50)
        print("\nвыбери:")
        print("  1. Запустить редактор")
        print("  2. Запустить игру из файла")
        print("  3. Выход")
        print()
        
        choice = input("Ваш выбор (1-3): ").strip()
        
        if choice == '1':
            run_editor()
        elif choice == '2':
            run_game_from_file()
        elif choice == '3':
            print("До свидания!")
            break
        else:
            print("Неверный выбор. Попробуйте снова.")


if __name__ == "__main__":
    # Проверяем зависимости перед запуском
    if check_and_install_packages():
        main()
