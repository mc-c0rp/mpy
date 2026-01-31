"""
Редактор визуальной новеллы на tkinter.
Позволяет создавать и редактировать сцены, диалоги, персонажей.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
import json
import os
import shutil
import threading
import multiprocessing
from typing import Optional, Dict, List, Callable
from story import Story, Scene, Character, Choice, DialogLine, MainMenuConfig, MenuButton, MenuSlider, MenuLogo, MenuSounds
from preview import ScenePreview, GamePreview, MenuPreview


# Директория движка
ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(ENGINE_DIR, "assets")
ASSETS_IMG_DIR = os.path.join(ASSETS_DIR, "img")
ASSETS_SOUND_DIR = os.path.join(ASSETS_DIR, "sound")


def _run_engine_preview(story: Story, start_scene_id: str):
    """
    Запустить полноценный движок игры в отдельном процессе.
    Эта функция должна быть на уровне модуля для multiprocessing.
    """
    from engine import VisualNovelEngine
    
    try:
        # Подменяем start_scene_id в story чтобы игра началась с нужной сцены
        story.start_scene_id = start_scene_id
        
        engine = VisualNovelEngine(960, 540, f"Предпросмотр: {story.title or 'Сцена'}")
        engine.load_story(story)
        engine.run()
    except Exception as e:
        print(f"Ошибка предпросмотра: {e}")
        import traceback
        traceback.print_exc()


def ensure_asset_in_dir(filepath: str, asset_type: str = "img") -> str:
    """
    Убедиться, что файл находится в папке assets.
    Если файл вне директории движка - копирует его в assets.
    
    asset_type: "img" или "sound"
    Возвращает новый путь к файлу.
    """
    if not filepath or not os.path.exists(filepath):
        return filepath
    
    # Нормализуем путь
    filepath = os.path.normpath(filepath)
    
    # Проверяем, находится ли файл уже в директории движка
    if filepath.startswith(ENGINE_DIR):
        return filepath
    
    # Определяем целевую папку
    if asset_type == "sound":
        target_dir = ASSETS_SOUND_DIR
    else:
        target_dir = ASSETS_IMG_DIR
    
    # Создаём папку если не существует
    os.makedirs(target_dir, exist_ok=True)
    
    # Копируем файл
    filename = os.path.basename(filepath)
    target_path = os.path.join(target_dir, filename)
    
    # Если файл с таким именем уже существует, добавляем номер
    if os.path.exists(target_path) and not os.path.samefile(filepath, target_path):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(target_path):
            target_path = os.path.join(target_dir, f"{base}_{counter}{ext}")
            counter += 1
    
    # Копируем
    if not os.path.exists(target_path):
        shutil.copy2(filepath, target_path)
    
    return target_path


# Файл настроек
SETTINGS_FILE = os.path.join(ENGINE_DIR, "editor_settings.json")

DEFAULT_SETTINGS = {
    "autosave_enabled": False,
    "autosave_interval": 60,  # секунды
    "last_project": "",
    "window_width": 1400,
    "window_height": 800
}

def load_settings() -> dict:
    """Загрузить настройки редактора."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # Добавляем отсутствующие ключи
                for key, value in DEFAULT_SETTINGS.items():
                    if key not in settings:
                        settings[key] = value
                return settings
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_SETTINGS.copy()

def save_settings(settings: dict):
    """Сохранить настройки редактора."""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except IOError:
        pass


class SettingsDialog(tk.Toplevel):
    """Окно настроек редактора."""
    
    def __init__(self, parent, settings: dict, on_save: Optional[Callable] = None):
        super().__init__(parent)
        self.title("Настройки")
        self.geometry("400x250")
        self.resizable(False, False)
        
        self.settings = settings.copy()
        self.on_save = on_save
        
        self._create_widgets()
        
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Автосохранение
        autosave_frame = ttk.LabelFrame(main_frame, text="Автосохранение", padding=10)
        autosave_frame.pack(fill=tk.X, pady=10)
        
        self.autosave_var = tk.BooleanVar(value=self.settings.get('autosave_enabled', False))
        ttk.Checkbutton(autosave_frame, text="Включить автосохранение", 
                        variable=self.autosave_var).pack(anchor=tk.W)
        
        interval_frame = ttk.Frame(autosave_frame)
        interval_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(interval_frame, text="Интервал (сек):").pack(side=tk.LEFT)
        self.interval_entry = ttk.Entry(interval_frame, width=10)
        self.interval_entry.insert(0, str(self.settings.get('autosave_interval', 60)))
        self.interval_entry.pack(side=tk.LEFT, padx=10)
        
        # Кнопки
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=20)
        
        ttk.Button(buttons_frame, text="Сохранить", command=self._save).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="Отмена", command=self.destroy).pack(side=tk.LEFT, padx=10)
    
    def _save(self):
        try:
            interval = int(self.interval_entry.get())
            if interval < 10:
                interval = 10
        except ValueError:
            interval = 60
        
        self.settings['autosave_enabled'] = self.autosave_var.get()
        self.settings['autosave_interval'] = interval
        
        if self.on_save:
            self.on_save(self.settings)
        
        self.destroy()


class ProjectSelectDialog(tk.Toplevel):
    """Окно выбора проекта из папки projects."""
    
    def __init__(self, parent, projects_dir: str, mode: str = "open"):
        """
        Args:
            mode: "open" - открыть существующий, "save" - сохранить новый
        """
        super().__init__(parent)
        self.title("Открыть проект" if mode == "open" else "Сохранить проект")
        self.geometry("450x400")
        self.resizable(False, False)
        
        self.projects_dir = projects_dir
        self.mode = mode
        self.result: Optional[str] = None
        
        self._create_widgets()
        self._load_projects()
        
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок
        if self.mode == "open":
            ttk.Label(main_frame, text="Выберите проект:", font=('Arial', 11, 'bold')).pack(anchor=tk.W)
        else:
            ttk.Label(main_frame, text="Имя проекта:", font=('Arial', 11, 'bold')).pack(anchor=tk.W)
            
            # Поле ввода имени для режима сохранения
            name_frame = ttk.Frame(main_frame)
            name_frame.pack(fill=tk.X, pady=(5, 10))
            
            self.name_entry = ttk.Entry(name_frame, width=40)
            self.name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            ttk.Label(name_frame, text=".json").pack(side=tk.LEFT)
        
        # Список проектов
        ttk.Label(main_frame, text="Существующие проекты:").pack(anchor=tk.W, pady=(10, 5))
        
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.projects_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=('Arial', 10))
        self.projects_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.projects_listbox.yview)
        
        self.projects_listbox.bind('<Double-Button-1>', lambda e: self._confirm())
        if self.mode == "save":
            self.projects_listbox.bind('<<ListboxSelect>>', self._on_select)
        
        # Кнопки
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(15, 0))
        
        btn_text = "Открыть" if self.mode == "open" else "Сохранить"
        ttk.Button(buttons_frame, text=btn_text, command=self._confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Отмена", command=self._cancel).pack(side=tk.LEFT, padx=5)
    
    def _load_projects(self):
        """Загрузить список проектов."""
        self.projects_listbox.delete(0, tk.END)
        
        if os.path.exists(self.projects_dir):
            projects = sorted([f for f in os.listdir(self.projects_dir) if f.endswith('.json')])
            for proj in projects:
                self.projects_listbox.insert(tk.END, proj)
    
    def _on_select(self, event=None):
        """При выборе проекта - вставить его имя в поле ввода."""
        selection = self.projects_listbox.curselection()
        if selection and self.mode == "save":
            name = self.projects_listbox.get(selection[0])
            if name.endswith('.json'):
                name = name[:-5]
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, name)
    
    def _confirm(self):
        """Подтвердить выбор."""
        if self.mode == "open":
            selection = self.projects_listbox.curselection()
            if selection:
                filename = self.projects_listbox.get(selection[0])
                self.result = os.path.join(self.projects_dir, filename)
                self.destroy()
            else:
                messagebox.showwarning("Внимание", "Выберите проект из списка")
        else:
            name = self.name_entry.get().strip()
            if not name:
                messagebox.showwarning("Внимание", "Введите имя проекта")
                return
            
            # Убираем .json если пользователь его добавил
            if name.endswith('.json'):
                name = name[:-5]
            
            filepath = os.path.join(self.projects_dir, name + ".json")
            
            # Предупреждение о перезаписи
            if os.path.exists(filepath):
                if not messagebox.askyesno("Подтверждение", f"Файл '{name}.json' уже существует. Перезаписать?"):
                    return
            
            self.result = filepath
            self.destroy()
    
    def _delete_project(self):
        """Удалить выбранный проект."""
        selection = self.projects_listbox.curselection()
        if selection:
            filename = self.projects_listbox.get(selection[0])
            if messagebox.askyesno("Подтверждение", f"Удалить проект '{filename}'?"):
                filepath = os.path.join(self.projects_dir, filename)
                try:
                    os.remove(filepath)
                    self._load_projects()
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось удалить файл:\n{e}")
    
    def _cancel(self):
        """Отмена."""
        self.result = None
        self.destroy()


class CharacterEditor(tk.Toplevel):
    """Окно редактирования персонажа."""
    
    def __init__(self, parent, character: Optional[Character] = None, on_save: Optional[Callable] = None):
        super().__init__(parent)
        self.title("Редактор персонажа")
        self.geometry("500x450")
        self.resizable(False, False)
        
        self.character = character
        self.on_save = on_save
        self.color = character.color if character else "#FFFFFF"
        self.name_bg_color = character.name_bg_color if character else ""
        self.images: Dict[str, str] = dict(character.images) if character else {}
        
        self._create_widgets()
        
        if character:
            self._load_character()
        
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ID
        ttk.Label(main_frame, text="ID персонажа:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.id_entry = ttk.Entry(main_frame, width=40)
        self.id_entry.grid(row=0, column=1, columnspan=2, sticky=tk.W, pady=5)
        
        # Имя
        ttk.Label(main_frame, text="Имя:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(main_frame, width=40)
        self.name_entry.grid(row=1, column=1, columnspan=2, sticky=tk.W, pady=5)
        
        # Цвет
        ttk.Label(main_frame, text="Цвет имени:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.color_frame = tk.Frame(main_frame, width=100, height=25, bg=self.color)
        self.color_frame.grid(row=2, column=1, sticky=tk.W, pady=5)
        ttk.Button(main_frame, text="Выбрать", command=self._choose_color).grid(row=2, column=2, pady=5)
        
        # Цвет фона под именем
        ttk.Label(main_frame, text="Фон под именем:").grid(row=3, column=0, sticky=tk.W, pady=5)
        name_bg_frame = ttk.Frame(main_frame)
        name_bg_frame.grid(row=3, column=1, columnspan=2, sticky=tk.W, pady=5)
        self.name_bg_color_frame = tk.Frame(name_bg_frame, width=100, height=25, 
                                            bg=self.name_bg_color if self.name_bg_color else "#CCCCCC")
        self.name_bg_color_frame.pack(side=tk.LEFT)
        ttk.Button(name_bg_frame, text="Выбрать", command=self._choose_name_bg_color).pack(side=tk.LEFT, padx=5)
        ttk.Button(name_bg_frame, text="Убрать", command=self._clear_name_bg_color).pack(side=tk.LEFT, padx=2)
        
        # Изображения
        ttk.Label(main_frame, text="Изображения (эмоции):").grid(row=4, column=0, sticky=tk.NW, pady=5)
        
        images_frame = ttk.Frame(main_frame)
        images_frame.grid(row=4, column=1, columnspan=2, sticky=tk.W, pady=5)
        
        self.images_listbox = tk.Listbox(images_frame, width=40, height=6)
        self.images_listbox.pack(side=tk.LEFT)
        
        images_scroll = ttk.Scrollbar(images_frame, orient=tk.VERTICAL, command=self.images_listbox.yview)
        images_scroll.pack(side=tk.LEFT, fill=tk.Y)
        self.images_listbox.config(yscrollcommand=images_scroll.set)
        
        images_buttons = ttk.Frame(main_frame)
        images_buttons.grid(row=5, column=1, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Button(images_buttons, text="Добавить", command=self._add_image).pack(side=tk.LEFT, padx=2)
        ttk.Button(images_buttons, text="Удалить", command=self._remove_image).pack(side=tk.LEFT, padx=2)
        
        # Кнопки
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=6, column=0, columnspan=3, pady=20)
        
        ttk.Button(buttons_frame, text="Сохранить", command=self._save).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="Отмена", command=self.destroy).pack(side=tk.LEFT, padx=10)
    
    def _load_character(self):
        if self.character:
            self.id_entry.insert(0, self.character.id)
            self.id_entry.config(state='disabled')  # ID нельзя менять при редактировании
            self.name_entry.insert(0, self.character.name)
            self._update_images_list()
    
    def _choose_color(self):
        color = colorchooser.askcolor(self.color, title="Выберите цвет")[1]
        if color:
            self.color = color
            self.color_frame.config(bg=color)
    
    def _choose_name_bg_color(self):
        initial = self.name_bg_color if self.name_bg_color else "#404080"
        color = colorchooser.askcolor(initial, title="Выберите цвет фона под именем")[1]
        if color:
            self.name_bg_color = color + "CC"  # Добавляем альфа-канал (80% непрозрачности)
            self.name_bg_color_frame.config(bg=color)
    
    def _clear_name_bg_color(self):
        self.name_bg_color = ""
        self.name_bg_color_frame.config(bg="#CCCCCC")
    
    def _add_image(self):
        dialog = tk.Toplevel(self)
        dialog.title("Добавить изображение")
        dialog.geometry("400x150")
        dialog.transient(self)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Эмоция:").grid(row=0, column=0, padx=10, pady=10)
        emotion_entry = ttk.Entry(dialog, width=30)
        emotion_entry.grid(row=0, column=1, padx=10, pady=10)
        emotion_entry.insert(0, "default")
        
        ttk.Label(dialog, text="Файл:").grid(row=1, column=0, padx=10, pady=10)
        file_entry = ttk.Entry(dialog, width=30)
        file_entry.grid(row=1, column=1, padx=10, pady=10)
        
        def browse():
            path = filedialog.askopenfilename(
                filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp")]
            )
            if path:
                file_entry.delete(0, tk.END)
                file_entry.insert(0, path)
        
        ttk.Button(dialog, text="Обзор", command=browse).grid(row=1, column=2, padx=5, pady=10)
        
        def save():
            emotion = emotion_entry.get().strip()
            path = file_entry.get().strip()
            if emotion:
                # Копируем файл в assets если нужно
                if path:
                    path = ensure_asset_in_dir(path, "img")
                self.images[emotion] = path
                self._update_images_list()
                dialog.destroy()
        
        ttk.Button(dialog, text="Добавить", command=save).grid(row=2, column=1, pady=10)
    
    def _remove_image(self):
        selection = self.images_listbox.curselection()
        if selection:
            item = self.images_listbox.get(selection[0])
            emotion = item.split(":")[0].strip()
            if emotion in self.images:
                del self.images[emotion]
                self._update_images_list()
    
    def _update_images_list(self):
        self.images_listbox.delete(0, tk.END)
        for emotion, path in self.images.items():
            display_path = os.path.basename(path) if path else "(не задан)"
            self.images_listbox.insert(tk.END, f"{emotion}: {display_path}")
    
    def _save(self):
        char_id = self.id_entry.get().strip()
        name = self.name_entry.get().strip()
        
        if not char_id:
            messagebox.showerror("Ошибка", "ID персонажа обязателен!")
            return
        
        character = Character(
            id=char_id,
            name=name,
            color=self.color,
            name_bg_color=self.name_bg_color,
            images=self.images
        )
        
        if self.on_save:
            self.on_save(character)
        
        self.destroy()


class DialogEditor(tk.Toplevel):
    """Окно редактирования диалога."""
    
    def __init__(self, parent, characters: Dict[str, Character], dialog: Optional[DialogLine] = None, 
                 on_save: Optional[Callable] = None, current_scene = None, story = None):
        super().__init__(parent)
        self.title("Редактор диалога")
        self.geometry("620x700")
        self.resizable(False, True)
        
        self.parent_window = parent
        self.characters = characters
        self.dialog = dialog
        self.on_save = on_save
        self.current_scene = current_scene
        self.story = story
        self.preview: Optional[ScenePreview] = None
        
        self._create_widgets()
        
        if dialog:
            self._load_dialog()
        
        self.transient(parent)
        self.grab_set()
        
        # Закрыть предпросмотр при закрытии окна
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_widgets(self):
        # Создаём Canvas со скроллом
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Растягиваем scrollable_frame по ширине
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))
        
        # Привязываем прокрутку колёсиком
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        main_frame = ttk.Frame(self.scrollable_frame, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Персонаж
        ttk.Label(main_frame, text="Персонаж:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.char_combo = ttk.Combobox(main_frame, width=30, state='readonly')
        char_list = ["(Рассказчик)"] + [f"{c.id} - {c.name}" for c in self.characters.values()]
        self.char_combo['values'] = char_list
        self.char_combo.current(0)
        self.char_combo.grid(row=0, column=1, sticky=tk.W, pady=5)
        self.char_combo.bind('<<ComboboxSelected>>', self._on_char_selected)
        
        # Эмоция
        ttk.Label(main_frame, text="Эмоция:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.emotion_combo = ttk.Combobox(main_frame, width=30)
        self.emotion_combo['values'] = ['default']
        self.emotion_combo.current(0)
        self.emotion_combo.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # Текст
        ttk.Label(main_frame, text="Текст:").grid(row=2, column=0, sticky=tk.NW, pady=5)
        self.text_widget = tk.Text(main_frame, width=50, height=6, wrap=tk.WORD)
        self.text_widget.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Позиция персонажа
        pos_frame = ttk.LabelFrame(main_frame, text="Позиция персонажа (опционально)", padding=5)
        pos_frame.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=10)
        
        # Первая строка - чекбокс и кнопка предпросмотра
        top_row = ttk.Frame(pos_frame)
        top_row.grid(row=0, column=0, columnspan=6, sticky=tk.W, pady=5)
        
        self.use_position_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top_row, text="Указать позицию", variable=self.use_position_var,
                        command=self._toggle_position).pack(side=tk.LEFT)
        
        ttk.Button(top_row, text="🖼️ Предпросмотр", command=self._open_preview).pack(side=tk.LEFT, padx=20)
        
        # Позиция X, Y
        ttk.Label(pos_frame, text="X:").grid(row=1, column=0, padx=5, pady=2)
        self.pos_x_entry = ttk.Entry(pos_frame, width=8, state='disabled')
        self.pos_x_entry.grid(row=1, column=1, padx=5, pady=2)
        
        ttk.Label(pos_frame, text="Y:").grid(row=1, column=2, padx=5, pady=2)
        self.pos_y_entry = ttk.Entry(pos_frame, width=8, state='disabled')
        self.pos_y_entry.grid(row=1, column=3, padx=5, pady=2)
        
        ttk.Label(pos_frame, text="Поворот:").grid(row=1, column=4, padx=5, pady=2)
        self.pos_rot_entry = ttk.Entry(pos_frame, width=8, state='disabled')
        self.pos_rot_entry.grid(row=1, column=5, padx=5, pady=2)
        
        # Масштаб
        ttk.Label(pos_frame, text="Масштаб:").grid(row=2, column=0, padx=5, pady=2)
        self.pos_scale_entry = ttk.Entry(pos_frame, width=8, state='disabled')
        self.pos_scale_entry.grid(row=2, column=1, padx=5, pady=2)
        
        # Перспектива X, Y
        ttk.Label(pos_frame, text="Перспек.X:").grid(row=2, column=2, padx=5, pady=2)
        self.pos_skew_x_entry = ttk.Entry(pos_frame, width=8, state='disabled')
        self.pos_skew_x_entry.grid(row=2, column=3, padx=5, pady=2)
        
        ttk.Label(pos_frame, text="Перспек.Y:").grid(row=2, column=4, padx=5, pady=2)
        self.pos_skew_y_entry = ttk.Entry(pos_frame, width=8, state='disabled')
        self.pos_skew_y_entry.grid(row=2, column=5, padx=5, pady=2)
        
        # Отзеркаливание
        flip_frame = ttk.Frame(pos_frame)
        flip_frame.grid(row=3, column=0, columnspan=6, sticky=tk.W, pady=5)
        
        self.flip_x_var = tk.BooleanVar(value=False)
        self.flip_y_var = tk.BooleanVar(value=False)
        self.flip_x_check = ttk.Checkbutton(flip_frame, text="Отзеркалить ↔", variable=self.flip_x_var, state='disabled')
        self.flip_x_check.pack(side=tk.LEFT, padx=5)
        self.flip_y_check = ttk.Checkbutton(flip_frame, text="Отзеркалить ↕", variable=self.flip_y_var, state='disabled')
        self.flip_y_check.pack(side=tk.LEFT, padx=5)
        
        # Звуковой файл
        sound_frame = ttk.LabelFrame(main_frame, text="Звук для реплики (опционально)", padding=5)
        sound_frame.grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=10)
        
        self.sound_entry = ttk.Entry(sound_frame, width=45)
        self.sound_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(sound_frame, text="🔊 Выбрать", command=self._select_sound).pack(side=tk.LEFT, padx=5)
        ttk.Button(sound_frame, text="✕", width=3, command=self._clear_sound).pack(side=tk.LEFT)
        
        # Скорость печати текста
        typing_frame = ttk.LabelFrame(main_frame, text="Эффект печати текста", padding=5)
        typing_frame.grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=10)
        
        ttk.Label(typing_frame, text="Длительность (сек):").pack(side=tk.LEFT, padx=5)
        self.typing_speed_entry = ttk.Entry(typing_frame, width=8)
        self.typing_speed_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(typing_frame, text="(пусто = авто, 0 = мгновенно)").pack(side=tk.LEFT, padx=5)
        
        # Задержка перед пролистыванием
        delay_frame = ttk.LabelFrame(main_frame, text="Задержка перед пролистыванием", padding=5)
        delay_frame.grid(row=6, column=0, columnspan=2, sticky=tk.EW, pady=10)
        
        ttk.Label(delay_frame, text="Задержка (сек):").pack(side=tk.LEFT, padx=5)
        self.delay_entry = ttk.Entry(delay_frame, width=8)
        self.delay_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(delay_frame, text="(пусто = без задержки)").pack(side=tk.LEFT, padx=5)
        
        # Анимации для диалога
        anim_frame = ttk.LabelFrame(main_frame, text="Анимации персонажей (опционально)", padding=5)
        anim_frame.grid(row=7, column=0, columnspan=2, sticky=tk.EW, pady=10)
        
        # Список анимаций
        anim_list_frame = ttk.Frame(anim_frame)
        anim_list_frame.pack(fill=tk.X, pady=5)
        
        self.animations_listbox = tk.Listbox(anim_list_frame, height=3, width=50)
        self.animations_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        anim_scroll = ttk.Scrollbar(anim_list_frame, orient=tk.VERTICAL, command=self.animations_listbox.yview)
        anim_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.animations_listbox.config(yscrollcommand=anim_scroll.set)
        
        # Кнопки для анимаций
        anim_btn_frame = ttk.Frame(anim_frame)
        anim_btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(anim_btn_frame, text="➕ Добавить", command=self._add_animation).pack(side=tk.LEFT, padx=5)
        ttk.Button(anim_btn_frame, text="✏️ Редактировать", command=self._edit_animation).pack(side=tk.LEFT, padx=5)
        ttk.Button(anim_btn_frame, text="🗑️ Удалить", command=self._remove_animation).pack(side=tk.LEFT, padx=5)
        
        # Хранилище анимаций
        self.dialog_animations: List[Dict] = []
        
        # Кнопки
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=8, column=0, columnspan=2, pady=15)
        
        ttk.Button(buttons_frame, text="Сохранить", command=self._save).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="Отмена", command=self._on_close).pack(side=tk.LEFT, padx=10)
    
    def _toggle_position(self):
        state = 'normal' if self.use_position_var.get() else 'disabled'
        self.pos_x_entry.config(state=state)
        self.pos_y_entry.config(state=state)
        self.pos_rot_entry.config(state=state)
        self.pos_scale_entry.config(state=state)
        self.pos_skew_x_entry.config(state=state)
        self.pos_skew_y_entry.config(state=state)
        self.flip_x_check.config(state=state)
        self.flip_y_check.config(state=state)
        
        if self.use_position_var.get() and not self.pos_x_entry.get():
            self.pos_x_entry.insert(0, "0.5")
            self.pos_y_entry.insert(0, "0.7")
            self.pos_rot_entry.insert(0, "0")
            self.pos_scale_entry.insert(0, "1.0")
            self.pos_skew_x_entry.insert(0, "0")
            self.pos_skew_y_entry.insert(0, "0")
    
    def _on_close(self):
        """Закрыть окно и предпросмотр."""
        if self.preview and self.preview.running:
            self.preview.stop()
        self.destroy()
    
    def _open_preview(self):
        """Открыть предпросмотр для позиционирования персонажа."""
        selection = self.char_combo.get()
        if selection == "(Рассказчик)":
            messagebox.showinfo("Предпросмотр", "Для рассказчика позиция не нужна")
            return
        
        if not self.current_scene or not self.story:
            messagebox.showinfo("Предпросмотр", "Сцена не выбрана")
            return
        
        char_id = selection.split(" - ")[0]
        character = self.characters.get(char_id)
        if not character:
            messagebox.showinfo("Предпросмотр", "Сначала выберите персонажа")
            return
        
        # Автоматически включаем позицию
        self.use_position_var.set(True)
        self._toggle_position()
        
        # Закрываем старое окно если есть
        if self.preview and self.preview.running:
            self.preview.stop()
        
        # Создаём предпросмотр
        self.preview = ScenePreview(960, 540)
        self.preview.on_position_changed = self._on_preview_position_changed
        self.preview.start()
        
        # Загружаем сцену через некоторое время
        self.after(500, lambda: self._load_preview_scene(char_id, character))
    
    def _load_preview_scene(self, char_id: str, character: Character):
        """Загрузить сцену и персонажа в предпросмотр."""
        if not self.preview or not self.preview.running:
            return
        
        # Фон
        if self.current_scene.background:
            self.preview.set_background(self.current_scene.background)
        
        # Получаем эмоцию и изображение
        emotion = self.emotion_combo.get() or 'default'
        image_path = character.images.get(emotion, character.images.get('default', ''))
        
        # Текущая позиция из полей
        try:
            x = float(self.pos_x_entry.get()) if self.pos_x_entry.get() else 0.5
            y = float(self.pos_y_entry.get()) if self.pos_y_entry.get() else 0.7
        except ValueError:
            x, y = 0.5, 0.7
        
        # Добавляем персонажа
        try:
            rotation = float(self.pos_rot_entry.get()) if self.pos_rot_entry.get() else 0.0
        except ValueError:
            rotation = 0.0
        try:
            scale = float(self.pos_scale_entry.get()) if self.pos_scale_entry.get() else 1.0
        except ValueError:
            scale = 1.0
        try:
            skew_x = float(self.pos_skew_x_entry.get()) if self.pos_skew_x_entry.get() else 0.0
            skew_y = float(self.pos_skew_y_entry.get()) if self.pos_skew_y_entry.get() else 0.0
        except ValueError:
            skew_x, skew_y = 0.0, 0.0
        flip_x = self.flip_x_var.get()
        flip_y = self.flip_y_var.get()
        self.preview.add_character(char_id, character.name, image_path, x, y, emotion,
                                   rotation, flip_x, flip_y, scale, skew_x, skew_y)
    
    def _on_preview_position_changed(self, char_id: str, x: float, y: float, rotation: float = 0.0,
                                       flip_x: bool = False, flip_y: bool = False,
                                       scale: float = 1.0, skew_x: float = 0.0, skew_y: float = 0.0):
        """Callback когда позиция персонажа изменилась в предпросмотре."""
        # Обновляем поля
        self.pos_x_entry.delete(0, tk.END)
        self.pos_x_entry.insert(0, f"{x:.3f}")
        
        self.pos_y_entry.delete(0, tk.END)
        self.pos_y_entry.insert(0, f"{y:.3f}")
        
        self.pos_rot_entry.delete(0, tk.END)
        self.pos_rot_entry.insert(0, f"{rotation:.1f}")
        
        self.pos_scale_entry.delete(0, tk.END)
        self.pos_scale_entry.insert(0, f"{scale:.2f}")
        
        self.pos_skew_x_entry.delete(0, tk.END)
        self.pos_skew_x_entry.insert(0, f"{skew_x:.1f}")
        
        self.pos_skew_y_entry.delete(0, tk.END)
        self.pos_skew_y_entry.insert(0, f"{skew_y:.1f}")
        
        self.flip_x_var.set(flip_x)
        self.flip_y_var.set(flip_y)
    
    def _select_sound(self):
        """Выбрать звуковой файл для реплики."""
        filepath = filedialog.askopenfilename(
            filetypes=[("Аудио файлы", "*.mp3 *.wav *.ogg"), ("Все файлы", "*.*")]
        )
        if filepath:
            # Копируем в assets/sound если нужно
            filepath = ensure_asset_in_dir(filepath, "sound")
            self.sound_entry.delete(0, tk.END)
            self.sound_entry.insert(0, filepath)
    
    def _clear_sound(self):
        """Очистить звуковой файл."""
        self.sound_entry.delete(0, tk.END)
    
    def _update_animations_list(self):
        """Обновить список анимаций."""
        self.animations_listbox.delete(0, tk.END)
        for anim in self.dialog_animations:
            obj_id = anim.get('character_id') or anim.get('image_id', '?')
            obj_type = "👤" if anim.get('character_id') else "🖼️"
            keyframes_count = len(anim.get('keyframes', []))
            loop = "🔄" if anim.get('loop', False) else ""
            self.animations_listbox.insert(tk.END, f"{obj_type} {obj_id}: {keyframes_count} кадр(ов) {loop}")
    
    def _add_animation(self):
        """Добавить анимацию."""
        AnimationEditorDialog(self, self.characters, self.story, self.current_scene, 
                              on_save=self._on_animation_saved)
    
    def _edit_animation(self):
        """Редактировать выбранную анимацию."""
        selection = self.animations_listbox.curselection()
        if not selection:
            messagebox.showinfo("Редактирование", "Выберите анимацию для редактирования")
            return
        
        index = selection[0]
        if 0 <= index < len(self.dialog_animations):
            anim = self.dialog_animations[index]
            AnimationEditorDialog(self, self.characters, self.story, self.current_scene,
                                  animation=anim, animation_index=index,
                                  on_save=self._on_animation_saved)
    
    def _remove_animation(self):
        """Удалить выбранную анимацию."""
        selection = self.animations_listbox.curselection()
        if not selection:
            messagebox.showinfo("Удаление", "Выберите анимацию для удаления")
            return
        
        index = selection[0]
        if 0 <= index < len(self.dialog_animations):
            del self.dialog_animations[index]
            self._update_animations_list()
    
    def _on_animation_saved(self, animation: Dict, index: Optional[int] = None):
        """Callback при сохранении анимации."""
        if index is not None and 0 <= index < len(self.dialog_animations):
            self.dialog_animations[index] = animation
        else:
            self.dialog_animations.append(animation)
        self._update_animations_list()
    
    def _on_char_selected(self, event=None):
        selection = self.char_combo.get()
        if selection == "(Рассказчик)":
            self.emotion_combo['values'] = ['default']
            self.emotion_combo.current(0)
        else:
            char_id = selection.split(" - ")[0]
            if char_id in self.characters:
                emotions = list(self.characters[char_id].images.keys())
                if not emotions:
                    emotions = ['default']
                self.emotion_combo['values'] = emotions
                self.emotion_combo.current(0)
    
    def _load_dialog(self):
        if self.dialog:
            # Выбор персонажа
            if self.dialog.character_id:
                for i, char_id in enumerate(self.characters.keys()):
                    if char_id == self.dialog.character_id:
                        self.char_combo.current(i + 1)  # +1 из-за "Рассказчика"
                        break
            
            # Эмоция
            self._on_char_selected()
            emotions = list(self.emotion_combo['values'])
            if self.dialog.emotion in emotions:
                self.emotion_combo.current(emotions.index(self.dialog.emotion))
            
            # Текст
            self.text_widget.insert('1.0', self.dialog.text)
            
            # Позиция
            if self.dialog.position:
                self.use_position_var.set(True)
                self._toggle_position()
                self.pos_x_entry.delete(0, tk.END)
                self.pos_x_entry.insert(0, str(self.dialog.position.get('x', 0.5)))
                self.pos_y_entry.delete(0, tk.END)
                self.pos_y_entry.insert(0, str(self.dialog.position.get('y', 0.7)))
                self.pos_rot_entry.delete(0, tk.END)
                self.pos_rot_entry.insert(0, str(self.dialog.position.get('rotation', 0)))
                self.pos_scale_entry.delete(0, tk.END)
                self.pos_scale_entry.insert(0, str(self.dialog.position.get('scale', 1.0)))
                self.pos_skew_x_entry.delete(0, tk.END)
                self.pos_skew_x_entry.insert(0, str(self.dialog.position.get('skew_x', 0)))
                self.pos_skew_y_entry.delete(0, tk.END)
                self.pos_skew_y_entry.insert(0, str(self.dialog.position.get('skew_y', 0)))
                self.flip_x_var.set(self.dialog.position.get('flip_x', False))
                self.flip_y_var.set(self.dialog.position.get('flip_y', False))
            
            # Звук
            if self.dialog.sound_file:
                self.sound_entry.insert(0, self.dialog.sound_file)
            
            # Скорость печати
            if self.dialog.typing_speed is not None:
                self.typing_speed_entry.insert(0, str(self.dialog.typing_speed))
            
            # Задержка
            if self.dialog.delay is not None:
                self.delay_entry.insert(0, str(self.dialog.delay))
            
            # Анимации
            if self.dialog.animations:
                self.dialog_animations = list(self.dialog.animations)
                self._update_animations_list()
    
    def _save(self):
        selection = self.char_combo.get()
        char_id = None if selection == "(Рассказчик)" else selection.split(" - ")[0]
        
        # Позиция
        position = None
        if self.use_position_var.get():
            try:
                position = {
                    'x': float(self.pos_x_entry.get()),
                    'y': float(self.pos_y_entry.get()),
                    'rotation': float(self.pos_rot_entry.get()),
                    'scale': float(self.pos_scale_entry.get()) if self.pos_scale_entry.get() else 1.0,
                    'skew_x': float(self.pos_skew_x_entry.get()) if self.pos_skew_x_entry.get() else 0.0,
                    'skew_y': float(self.pos_skew_y_entry.get()) if self.pos_skew_y_entry.get() else 0.0,
                    'flip_x': self.flip_x_var.get(),
                    'flip_y': self.flip_y_var.get()
                }
            except ValueError:
                position = None
        
        # Звук
        sound_file = self.sound_entry.get().strip() or None
        
        # Скорость печати
        typing_speed = None
        typing_speed_str = self.typing_speed_entry.get().strip()
        if typing_speed_str:
            try:
                typing_speed = float(typing_speed_str)
            except ValueError:
                pass
        
        # Задержка
        delay = None
        delay_str = self.delay_entry.get().strip()
        if delay_str:
            try:
                delay = float(delay_str)
            except ValueError:
                pass
        
        dialog = DialogLine(
            character_id=char_id,
            text=self.text_widget.get('1.0', tk.END).strip(),
            emotion=self.emotion_combo.get() or 'default',
            position=position,
            sound_file=sound_file,
            typing_speed=typing_speed,
            delay=delay,
            animations=self.dialog_animations if self.dialog_animations else []
        )
        
        if self.on_save:
            self.on_save(dialog)
        
        self.destroy()
    
    def _on_mousewheel(self, event):
        """Обработчик прокрутки колесом мыши."""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class AnimationEditorDialog(tk.Toplevel):
    """Диалог редактирования анимации персонажа или картинки."""
    
    def __init__(self, parent, characters: Dict[str, Character], story: Story, 
                 current_scene: Scene, animation: Optional[Dict] = None,
                 animation_index: Optional[int] = None, on_save: Optional[Callable] = None):
        super().__init__(parent)
        self.title("Редактор анимации")
        self.geometry("600x550")
        self.resizable(True, True)
        
        self.characters = characters
        self.story = story
        self.current_scene = current_scene
        self.animation = animation or {}
        self.animation_index = animation_index
        self.on_save = on_save
        
        # Keyframes
        self.keyframes: List[Dict] = list(self.animation.get('keyframes', []))
        
        self._create_widgets()
        
        if animation:
            self._load_animation()
        
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Тип объекта
        type_frame = ttk.Frame(main_frame)
        type_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(type_frame, text="Тип:").pack(side=tk.LEFT, padx=5)
        self.type_var = tk.StringVar(value='character')
        self.type_combo = ttk.Combobox(type_frame, textvariable=self.type_var, width=15, state='readonly')
        self.type_combo['values'] = ['Персонаж', 'Картинка']
        self.type_combo.current(0)
        self.type_combo.pack(side=tk.LEFT, padx=5)
        self.type_combo.bind('<<ComboboxSelected>>', self._on_type_changed)
        
        # Выбор объекта (персонаж или картинка)
        obj_frame = ttk.Frame(main_frame)
        obj_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(obj_frame, text="Объект:").pack(side=tk.LEFT, padx=5)
        self.obj_combo = ttk.Combobox(obj_frame, width=30, state='readonly')
        self._update_obj_combo()
        self.obj_combo.pack(side=tk.LEFT, padx=5)
        
        # Опция зацикливания
        self.loop_var = tk.BooleanVar(value=self.animation.get('loop', False))
        ttk.Checkbutton(obj_frame, text="🔄 Зациклить", variable=self.loop_var).pack(side=tk.LEFT, padx=20)
        
        # Список ключевых кадров
        keyframe_frame = ttk.LabelFrame(main_frame, text="Ключевые кадры", padding=5)
        keyframe_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Listbox с keyframes
        list_frame = ttk.Frame(keyframe_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.keyframes_listbox = tk.Listbox(list_frame, height=8)
        self.keyframes_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.keyframes_listbox.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.keyframes_listbox.config(yscrollcommand=scroll.set)
        
        # Кнопки для keyframes
        btn_frame = ttk.Frame(keyframe_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="➕ Добавить кадр", command=self._add_keyframe).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="✏️ Редактировать", command=self._edit_keyframe).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🗑️ Удалить", command=self._remove_keyframe).pack(side=tk.LEFT, padx=5)
        
        # Редактор текущего keyframe
        edit_frame = ttk.LabelFrame(main_frame, text="Параметры кадра", padding=5)
        edit_frame.pack(fill=tk.X, pady=10)
        
        # Время
        row1 = ttk.Frame(edit_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="Время (сек):").pack(side=tk.LEFT, padx=5)
        self.time_entry = ttk.Entry(row1, width=8)
        self.time_entry.pack(side=tk.LEFT, padx=5)
        self.time_entry.insert(0, "0")
        
        # Позиция
        row2 = ttk.Frame(edit_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="X:").pack(side=tk.LEFT, padx=5)
        self.x_entry = ttk.Entry(row2, width=8)
        self.x_entry.pack(side=tk.LEFT, padx=5)
        self.x_entry.insert(0, "0.5")
        
        ttk.Label(row2, text="Y:").pack(side=tk.LEFT, padx=5)
        self.y_entry = ttk.Entry(row2, width=8)
        self.y_entry.pack(side=tk.LEFT, padx=5)
        self.y_entry.insert(0, "0.7")
        
        ttk.Label(row2, text="Масштаб:").pack(side=tk.LEFT, padx=5)
        self.scale_entry = ttk.Entry(row2, width=8)
        self.scale_entry.pack(side=tk.LEFT, padx=5)
        self.scale_entry.insert(0, "1.0")
        
        # Поворот и прозрачность
        row3 = ttk.Frame(edit_frame)
        row3.pack(fill=tk.X, pady=2)
        ttk.Label(row3, text="Поворот:").pack(side=tk.LEFT, padx=5)
        self.rotation_entry = ttk.Entry(row3, width=8)
        self.rotation_entry.pack(side=tk.LEFT, padx=5)
        self.rotation_entry.insert(0, "0")
        
        ttk.Label(row3, text="Альфа (0-1):").pack(side=tk.LEFT, padx=5)
        self.alpha_entry = ttk.Entry(row3, width=8)
        self.alpha_entry.pack(side=tk.LEFT, padx=5)
        self.alpha_entry.insert(0, "1.0")
        
        # Кнопки сохранения
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(buttons_frame, text="Сохранить анимацию", command=self._save).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="Отмена", command=self.destroy).pack(side=tk.LEFT, padx=10)
        
        self._update_keyframes_list()
    
    def _on_type_changed(self, event=None):
        """Обработчик смены типа объекта."""
        self._update_obj_combo()
    
    def _update_obj_combo(self):
        """Обновить список объектов в зависимости от типа."""
        type_val = self.type_combo.get()
        if type_val == 'Персонаж':
            obj_list = [f"{c.id} - {c.name}" for c in self.characters.values()]
        else:  # Картинка
            obj_list = []
            if self.current_scene and hasattr(self.current_scene, 'images_on_screen'):
                for img in self.current_scene.images_on_screen:
                    img_id = img.get('id', img.get('path', '?'))
                    path = img.get('path', '')
                    obj_list.append(f"{img_id} - {path}")
        
        self.obj_combo['values'] = obj_list
        if obj_list:
            self.obj_combo.current(0)
        else:
            self.obj_combo.set('')
    
    def _load_animation(self):
        """Загрузить данные анимации."""
        if self.animation:
            # Определяем тип анимации
            if self.animation.get('image_id'):
                self.type_combo.set('Картинка')
                self._update_obj_combo()
                img_id = self.animation.get('image_id')
                for i, val in enumerate(self.obj_combo['values']):
                    if val.startswith(f"{img_id} -"):
                        self.obj_combo.current(i)
                        break
            else:
                self.type_combo.set('Персонаж')
                self._update_obj_combo()
                char_id = self.animation.get('character_id')
                if char_id:
                    for i, c in enumerate(self.characters.values()):
                        if c.id == char_id:
                            self.obj_combo.current(i)
                            break
            
            self.loop_var.set(self.animation.get('loop', False))
            self.keyframes = list(self.animation.get('keyframes', []))
            self._update_keyframes_list()
    
    def _update_keyframes_list(self):
        """Обновить список ключевых кадров."""
        self.keyframes_listbox.delete(0, tk.END)
        for kf in self.keyframes:
            time = kf.get('time', 0)
            x = kf.get('x', 0.5)
            y = kf.get('y', 0.7)
            self.keyframes_listbox.insert(tk.END, f"t={time:.2f}с: ({x:.2f}, {y:.2f})")
    
    def _add_keyframe(self):
        """Добавить ключевой кадр из текущих полей."""
        try:
            kf = {
                'time': float(self.time_entry.get()),
                'x': float(self.x_entry.get()),
                'y': float(self.y_entry.get()),
                'scale': float(self.scale_entry.get()),
                'rotation': float(self.rotation_entry.get()),
                'alpha': float(self.alpha_entry.get())
            }
            self.keyframes.append(kf)
            # Сортируем по времени
            self.keyframes.sort(key=lambda k: k['time'])
            self._update_keyframes_list()
        except ValueError:
            messagebox.showerror("Ошибка", "Неверный формат данных")
    
    def _edit_keyframe(self):
        """Загрузить выбранный keyframe в поля редактирования."""
        selection = self.keyframes_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if 0 <= index < len(self.keyframes):
            kf = self.keyframes[index]
            
            self.time_entry.delete(0, tk.END)
            self.time_entry.insert(0, str(kf.get('time', 0)))
            
            self.x_entry.delete(0, tk.END)
            self.x_entry.insert(0, str(kf.get('x', 0.5)))
            
            self.y_entry.delete(0, tk.END)
            self.y_entry.insert(0, str(kf.get('y', 0.7)))
            
            self.scale_entry.delete(0, tk.END)
            self.scale_entry.insert(0, str(kf.get('scale', 1.0)))
            
            self.rotation_entry.delete(0, tk.END)
            self.rotation_entry.insert(0, str(kf.get('rotation', 0)))
            
            self.alpha_entry.delete(0, tk.END)
            self.alpha_entry.insert(0, str(kf.get('alpha', 1.0)))
            
            # Удаляем старый
            del self.keyframes[index]
            self._update_keyframes_list()
    
    def _remove_keyframe(self):
        """Удалить выбранный keyframe."""
        selection = self.keyframes_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if 0 <= index < len(self.keyframes):
            del self.keyframes[index]
            self._update_keyframes_list()
    
    def _save(self):
        """Сохранить анимацию."""
        if not self.obj_combo.get():
            messagebox.showerror("Ошибка", "Выберите объект для анимации")
            return
        
        if not self.keyframes:
            messagebox.showerror("Ошибка", "Добавьте хотя бы один ключевой кадр")
            return
        
        obj_id = self.obj_combo.get().split(" - ")[0]
        type_val = self.type_combo.get()
        
        if type_val == 'Персонаж':
            animation = {
                'character_id': obj_id,
                'keyframes': self.keyframes,
                'loop': self.loop_var.get()
            }
        else:  # Картинка
            animation = {
                'image_id': obj_id,
                'keyframes': self.keyframes,
                'loop': self.loop_var.get()
            }
        
        if self.on_save:
            self.on_save(animation, self.animation_index)
        
        self.destroy()


class ChoiceEditor(tk.Toplevel):
    """Окно редактирования выбора."""
    
    def __init__(self, parent, scenes: Dict[str, Scene], choice: Optional[Choice] = None, on_save: Optional[Callable] = None):
        super().__init__(parent)
        self.title("Редактор выбора")
        self.geometry("500x200")
        self.resizable(False, False)
        
        self.scenes = scenes
        self.choice = choice
        self.on_save = on_save
        
        self._create_widgets()
        
        if choice:
            self._load_choice()
        
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Текст выбора
        ttk.Label(main_frame, text="Текст выбора:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.text_entry = ttk.Entry(main_frame, width=50)
        self.text_entry.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Следующая сцена
        ttk.Label(main_frame, text="Следующая сцена:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.scene_combo = ttk.Combobox(main_frame, width=47, state='readonly')
        scene_list = [f"{s.id} - {s.name}" for s in self.scenes.values()]
        self.scene_combo['values'] = scene_list
        if scene_list:
            self.scene_combo.current(0)
        self.scene_combo.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # Кнопки
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        ttk.Button(buttons_frame, text="Сохранить", command=self._save).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="Отмена", command=self.destroy).pack(side=tk.LEFT, padx=10)
    
    def _load_choice(self):
        if self.choice:
            self.text_entry.insert(0, self.choice.text)
            
            for i, scene in enumerate(self.scenes.values()):
                if scene.id == self.choice.next_scene_id:
                    self.scene_combo.current(i)
                    break
    
    def _save(self):
        text = self.text_entry.get().strip()
        if not text:
            messagebox.showerror("Ошибка", "Текст выбора обязателен!")
            return
        
        scene_selection = self.scene_combo.get()
        if not scene_selection:
            messagebox.showerror("Ошибка", "Выберите сцену!")
            return
        
        scene_id = scene_selection.split(" - ")[0]
        
        choice = Choice(text=text, next_scene_id=scene_id)
        
        if self.on_save:
            self.on_save(choice)
        
        self.destroy()


class SceneEditor(ttk.Frame):
    """Панель редактирования сцены."""
    
    def __init__(self, parent, story: Story, on_scene_changed: Optional[Callable] = None):
        super().__init__(parent)
        self.story = story
        self.current_scene: Optional[Scene] = None
        self.on_scene_changed = on_scene_changed
        self.preview: Optional[ScenePreview] = None
        self.game_preview: Optional[multiprocessing.Process] = None
        
        self._create_widgets()
    
    def _create_widgets(self):
        # Создаём Canvas со скроллом для всего содержимого
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Привязываем прокрутку колёсиком мыши
        self.canvas.bind("<Enter>", lambda e: self._bind_mousewheel())
        self.canvas.bind("<Leave>", lambda e: self._unbind_mousewheel())
        
        # Растягиваем scrollable_frame по ширине canvas
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Далее все виджеты добавляем в self.scrollable_frame вместо self
        container = self.scrollable_frame
        
        # Основные настройки сцены
        settings_frame = ttk.LabelFrame(container, text="Настройки сцены", padding=10)
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # ID
        ttk.Label(settings_frame, text="ID:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.id_entry = ttk.Entry(settings_frame, width=30)
        self.id_entry.grid(row=0, column=1, sticky=tk.W, pady=2)
        
        # Название
        ttk.Label(settings_frame, text="Название:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.name_entry = ttk.Entry(settings_frame, width=30)
        self.name_entry.grid(row=1, column=1, sticky=tk.W, pady=2)
        
        # Фон
        ttk.Label(settings_frame, text="Фон:").grid(row=2, column=0, sticky=tk.W, pady=2)
        bg_frame = ttk.Frame(settings_frame)
        bg_frame.grid(row=2, column=1, sticky=tk.W, pady=2)
        self.bg_entry = ttk.Entry(bg_frame, width=20)
        self.bg_entry.pack(side=tk.LEFT)
        ttk.Button(bg_frame, text="Обзор", command=self._browse_background).pack(side=tk.LEFT, padx=2)
        
        # Цвет фона (если нет картинки)
        ttk.Label(settings_frame, text="Цвет фона:").grid(row=3, column=0, sticky=tk.W, pady=2)
        bg_color_frame = ttk.Frame(settings_frame)
        bg_color_frame.grid(row=3, column=1, sticky=tk.W, pady=2)
        self.bg_color_var = tk.StringVar(value="")
        self.bg_color_preview = tk.Label(bg_color_frame, bg="#333333", width=5, relief="solid")
        self.bg_color_preview.pack(side=tk.LEFT)
        ttk.Button(bg_color_frame, text="Выбрать", command=self._choose_bg_color).pack(side=tk.LEFT, padx=2)
        ttk.Button(bg_color_frame, text="Сбросить", command=self._reset_bg_color).pack(side=tk.LEFT, padx=2)
        
        # Музыка
        ttk.Label(settings_frame, text="Музыка:").grid(row=4, column=0, sticky=tk.W, pady=2)
        music_frame = ttk.Frame(settings_frame)
        music_frame.grid(row=4, column=1, sticky=tk.W, pady=2)
        self.music_entry = ttk.Entry(music_frame, width=25)
        self.music_entry.pack(side=tk.LEFT)
        ttk.Button(music_frame, text="Обзор", command=self._browse_music).pack(side=tk.LEFT, padx=5)
        
        # Следующая сцена
        ttk.Label(settings_frame, text="Следующая сцена:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.next_scene_combo = ttk.Combobox(settings_frame, width=28)
        self.next_scene_combo.grid(row=5, column=1, sticky=tk.W, pady=2)
        
        # Кнопки предпросмотра
        preview_buttons = ttk.Frame(settings_frame)
        preview_buttons.grid(row=6, column=0, columnspan=2, pady=10)
        
        ttk.Button(preview_buttons, text="🎬 Предпросмотр сцены", 
                   command=self._open_preview).pack(side=tk.LEFT, padx=5)
        ttk.Button(preview_buttons, text="▶️ Играть сцену", 
                   command=self._open_game_preview).pack(side=tk.LEFT, padx=5)
        
        # Персонажи на сцене
        chars_frame = ttk.LabelFrame(container, text="Персонажи на сцене (перетаскивайте в предпросмотре)", padding=10)
        chars_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.scene_chars_listbox = tk.Listbox(chars_frame, height=4)
        self.scene_chars_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        chars_buttons = ttk.Frame(chars_frame)
        chars_buttons.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(chars_buttons, text="Добавить", command=self._add_scene_character).pack(fill=tk.X, pady=2)
        ttk.Button(chars_buttons, text="Удалить", command=self._remove_scene_character).pack(fill=tk.X, pady=2)
        ttk.Button(chars_buttons, text="Позиция...", command=self._edit_character_position).pack(fill=tk.X, pady=2)
        
        # Картинки на сцене
        images_frame = ttk.LabelFrame(container, text="Картинки на сцене", padding=10)
        images_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.scene_images_listbox = tk.Listbox(images_frame, height=3)
        self.scene_images_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        images_buttons = ttk.Frame(images_frame)
        images_buttons.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(images_buttons, text="Добавить", command=self._add_scene_image).pack(fill=tk.X, pady=2)
        ttk.Button(images_buttons, text="Удалить", command=self._remove_scene_image).pack(fill=tk.X, pady=2)
        ttk.Button(images_buttons, text="Позиция...", command=self._edit_image_position).pack(fill=tk.X, pady=2)
        
        # Тексты на сцене
        texts_frame = ttk.LabelFrame(container, text="Тексты на сцене", padding=10)
        texts_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.scene_texts_listbox = tk.Listbox(texts_frame, height=3)
        self.scene_texts_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        texts_buttons = ttk.Frame(texts_frame)
        texts_buttons.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(texts_buttons, text="Добавить", command=self._add_scene_text).pack(fill=tk.X, pady=2)
        ttk.Button(texts_buttons, text="Редактировать", command=self._edit_scene_text).pack(fill=tk.X, pady=2)
        ttk.Button(texts_buttons, text="Удалить", command=self._remove_scene_text).pack(fill=tk.X, pady=2)
        
        # Фоновые анимации
        anims_frame = ttk.LabelFrame(container, text="Фоновые анимации (через предпросмотр)", padding=10)
        anims_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.bg_anims_listbox = tk.Listbox(anims_frame, height=3)
        self.bg_anims_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        anims_buttons = ttk.Frame(anims_frame)
        anims_buttons.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(anims_buttons, text="Удалить", command=self._remove_bg_animation).pack(fill=tk.X, pady=2)
        ttk.Button(anims_buttons, text="Очистить все", command=self._clear_bg_animations).pack(fill=tk.X, pady=2)
        
        ttk.Label(anims_frame, text="[R] - запись в предпросмотре, [S] - сохранить", 
                  font=('TkDefaultFont', 8), foreground='gray').pack(side=tk.BOTTOM, pady=2)
        
        # Диалоги
        dialogs_frame = ttk.LabelFrame(container, text="Диалоги", padding=10)
        dialogs_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.dialogs_listbox = tk.Listbox(dialogs_frame, height=6, selectmode=tk.EXTENDED)
        self.dialogs_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        dialogs_scroll = ttk.Scrollbar(dialogs_frame, orient=tk.VERTICAL, command=self.dialogs_listbox.yview)
        dialogs_scroll.pack(side=tk.LEFT, fill=tk.Y)
        self.dialogs_listbox.config(yscrollcommand=dialogs_scroll.set)
        
        dialogs_buttons = ttk.Frame(dialogs_frame)
        dialogs_buttons.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(dialogs_buttons, text="Добавить", command=self._add_dialog).pack(fill=tk.X, pady=2)
        ttk.Button(dialogs_buttons, text="Редактировать", command=self._edit_dialog).pack(fill=tk.X, pady=2)
        ttk.Button(dialogs_buttons, text="Удалить", command=self._remove_dialog).pack(fill=tk.X, pady=2)
        ttk.Button(dialogs_buttons, text="Удалить все", command=self._remove_all_dialogs).pack(fill=tk.X, pady=2)
        ttk.Button(dialogs_buttons, text="Вверх", command=self._move_dialog_up).pack(fill=tk.X, pady=2)
        ttk.Button(dialogs_buttons, text="Вниз", command=self._move_dialog_down).pack(fill=tk.X, pady=2)
        
        # Выборы
        choices_frame = ttk.LabelFrame(container, text="Выборы в конце сцены", padding=10)
        choices_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.choices_listbox = tk.Listbox(choices_frame, height=5)
        self.choices_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        choices_buttons = ttk.Frame(choices_frame)
        choices_buttons.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(choices_buttons, text="Добавить", command=self._add_choice).pack(fill=tk.X, pady=2)
        ttk.Button(choices_buttons, text="Редактировать", command=self._edit_choice).pack(fill=tk.X, pady=2)
        ttk.Button(choices_buttons, text="Удалить", command=self._remove_choice).pack(fill=tk.X, pady=2)
        
        # Автосохранение при изменении полей
        self.id_entry.bind('<FocusOut>', lambda e: self._auto_save_scene())
        self.name_entry.bind('<FocusOut>', lambda e: self._auto_save_scene())
        self.bg_entry.bind('<FocusOut>', lambda e: self._auto_save_scene())
        self.music_entry.bind('<FocusOut>', lambda e: self._auto_save_scene())
        self.next_scene_combo.bind('<<ComboboxSelected>>', lambda e: self._auto_save_scene())
    
    def _on_canvas_configure(self, event):
        """Растянуть scrollable_frame по ширине canvas."""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def _bind_mousewheel(self):
        """Привязать прокрутку колёсиком."""
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
    
    def _unbind_mousewheel(self):
        """Отвязать прокрутку колёсиком."""
        self.canvas.unbind_all("<MouseWheel>")
    
    def _on_mousewheel(self, event):
        """Прокрутка колёсиком мыши."""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def _open_preview(self):
        """Открыть окно предпросмотра."""
        if not self.current_scene:
            messagebox.showinfo("Предпросмотр", "Сначала выберите или создайте сцену")
            return
        
        # Проверяем, открыто ли уже окно предпросмотра
        if self.preview and self.preview.running:
            messagebox.showerror("Ошибка", "Окно предпросмотра уже открыто")
            return
        
        # Создаём новое
        self.preview = ScenePreview(960, 540)
        self.preview.on_position_changed = self._on_preview_position_changed
        self.preview.on_image_position_changed = self._on_preview_image_position_changed
        self.preview.on_text_position_changed = self._on_preview_text_position_changed
        self.preview.on_keyframe_added = self._on_keyframe_added
        self.preview.on_animation_saved = self._on_animation_saved
        self.preview.start()
        
        # Загружаем сцену в предпросмотр
        self.after(500, self._load_scene_to_preview)
    
    def _open_game_preview(self):
        """Открыть предпросмотр как в игре - с диалогами и анимациями."""
        if not self.current_scene:
            messagebox.showinfo("Предпросмотр", "Сначала выберите или создайте сцену")
            return
        
        # Проверяем, открыто ли уже окно предпросмотра
        if self.preview and self.preview.running:
            messagebox.showerror("Ошибка", "Окно предпросмотра сцены уже открыто. Закройте его для запуска игры.")
            return
        
        if hasattr(self, 'game_preview') and self.game_preview and self.game_preview.is_alive():
            messagebox.showerror("Ошибка", "Игра уже запущена")
            return
        
        # Запускаем предпросмотр игры
        self._start_game_preview()
    
    def _start_game_preview(self):
        """Запустить полноценную игру с текущей сцены в отдельном процессе."""
        if not self.current_scene:
            return
        
        # Запускаем полноценный движок в отдельном процессе
        self.game_preview_process = multiprocessing.Process(
            target=_run_engine_preview,
            args=(self.story, self.current_scene.id),
            daemon=True
        )
        self.game_preview_process.start()
        
        # Сохраняем ссылку на процесс для проверки
        self.game_preview = self.game_preview_process
    
    def _load_scene_to_preview(self):
        """Загрузить текущую сцену в предпросмотр."""
        if not self.preview or not self.current_scene:
            return
        
        # Фон
        self.preview.set_background(self.current_scene.background)
        if self.current_scene.background_color:
            self.preview.set_background_color(self.current_scene.background_color)
        
        # Картинки
        for img_data in self.current_scene.images_on_screen:
            img_id = img_data.get('id')
            img_path = img_data.get('path', '')
            img_name = img_data.get('name', img_id)
            x = img_data.get('x', 0.5)
            y = img_data.get('y', 0.5)
            layer = img_data.get('layer', 0)
            rotation = img_data.get('rotation', 0.0)
            flip_x = img_data.get('flip_x', False)
            flip_y = img_data.get('flip_y', False)
            scale = img_data.get('scale', 1.0)
            skew_x = img_data.get('skew_x', 0.0)
            skew_y = img_data.get('skew_y', 0.0)
            
            self.preview.add_image(img_id, img_name, img_path, x, y, layer,
                                   rotation, flip_x, flip_y, scale, skew_x, skew_y)
        
        # Тексты
        for text_data in self.current_scene.texts_on_screen:
            text_id = text_data.get('id', '')
            text = text_data.get('text', '')
            x = text_data.get('x', 0.5)
            y = text_data.get('y', 0.5)
            font_size = text_data.get('font_size', 36)
            color = text_data.get('color', (255, 255, 255))
            outline_color = text_data.get('outline_color', (0, 0, 0))
            outline_width = text_data.get('outline_width', 2)
            scale = text_data.get('scale', 1.0)
            rotation = text_data.get('rotation', 0.0)
            order = text_data.get('order', 0)
            
            self.preview.add_text(text_id, text, x, y, font_size, color,
                                  outline_color, outline_width, scale, rotation, order)
        
        # Персонажи
        for char_data in self.current_scene.characters_on_screen:
            char_id = char_data.get('id')
            character = self.story.get_character(char_id)
            if not character:
                continue
            
            emotion = char_data.get('emotion', 'default')
            image_path = character.images.get(emotion, character.images.get('default', ''))
            x = char_data.get('x', 0.5)
            y = char_data.get('y', 0.7)
            rotation = char_data.get('rotation', 0.0)
            flip_x = char_data.get('flip_x', False)
            flip_y = char_data.get('flip_y', False)
            scale = char_data.get('scale', 1.0)
            skew_x = char_data.get('skew_x', 0.0)
            skew_y = char_data.get('skew_y', 0.0)
            
            self.preview.add_character(char_id, character.name, image_path, x, y, emotion,
                                       rotation, flip_x, flip_y, scale, skew_x, skew_y)
    
    def _on_preview_image_position_changed(self, img_id: str, x: float, y: float, rotation: float = 0.0,
                                            flip_x: bool = False, flip_y: bool = False,
                                            scale: float = 1.0, skew_x: float = 0.0, skew_y: float = 0.0,
                                            layer: int = 0):
        """Callback когда позиция картинки изменилась в предпросмотре."""
        if not self.current_scene:
            return
        
        # Обновляем позицию в данных сцены
        for img_data in self.current_scene.images_on_screen:
            if img_data.get('id') == img_id:
                img_data['x'] = x
                img_data['y'] = y
                img_data['rotation'] = rotation
                img_data['flip_x'] = flip_x
                img_data['flip_y'] = flip_y
                img_data['scale'] = scale
                img_data['skew_x'] = skew_x
                img_data['skew_y'] = skew_y
                img_data['layer'] = layer
                break
        
        self._update_scene_images_list()
    
    def _on_preview_text_position_changed(self, text_id: str, x: float, y: float,
                                           scale: float = 1.0, rotation: float = 0.0):
        """Callback когда позиция текста изменилась в предпросмотре."""
        if not self.current_scene:
            return
        
        # Обновляем позицию в данных сцены
        for text_data in self.current_scene.texts_on_screen:
            if text_data.get('id') == text_id:
                text_data['x'] = x
                text_data['y'] = y
                text_data['scale'] = scale
                text_data['rotation'] = rotation
                break
        
        self._update_scene_texts_list()
        self._auto_save_scene()
    
    def _on_preview_position_changed(self, char_id: str, x: float, y: float, rotation: float = 0.0, 
                                       flip_x: bool = False, flip_y: bool = False,
                                       scale: float = 1.0, skew_x: float = 0.0, skew_y: float = 0.0):
        """Callback когда позиция персонажа изменилась в предпросмотре."""
        if not self.current_scene:
            return
        
        # Обновляем позицию в данных сцены
        for char_data in self.current_scene.characters_on_screen:
            if char_data.get('id') == char_id:
                char_data['x'] = x
                char_data['y'] = y
                char_data['rotation'] = rotation
                char_data['flip_x'] = flip_x
                char_data['flip_y'] = flip_y
                char_data['scale'] = scale
                char_data['skew_x'] = skew_x
                char_data['skew_y'] = skew_y
                break
        
        self._update_scene_chars_list()
    
    def _on_keyframe_added(self, obj_id: str, keyframe: dict, obj_type: str = "character"):
        """Callback когда добавлен ключевой кадр."""
        # Показываем краткое уведомление
        type_name = "персонажа" if obj_type == "character" else "картинки"
        print(f"Кадр для {type_name} {obj_id}: t={keyframe['time']:.2f}с pos=({keyframe['x']:.2f}, {keyframe['y']:.2f})")
    
    def _on_animation_saved(self, animation: dict, anim_type: str):
        """Callback когда анимация сохранена из предпросмотра."""
        if not self.current_scene:
            return
        
        # Спрашиваем нужно ли зацикливать
        loop = messagebox.askyesno("Фоновая анимация", 
                                   "Зациклить анимацию?\n\n"
                                   "Да - анимация будет повторяться\n"
                                   "Нет - проиграется один раз")
        animation['loop'] = loop
        
        # Добавляем в фоновые анимации сцены
        self.current_scene.background_animations.append(animation)
        self._update_bg_animations_list()
        self._auto_save_scene()
        
        obj_id = animation.get('character_id') or animation.get('image_id', '?')
        kf_count = len(animation.get('keyframes', []))
        messagebox.showinfo("Анимация сохранена", 
                          f"Фоновая анимация для '{obj_id}' сохранена!\n"
                          f"Кадров: {kf_count}\n"
                          f"Зацикливание: {'Да' if loop else 'Нет'}\n\n"
                          f"Анимация будет воспроизводиться при загрузке сцены.")
    
    def _add_scene_character(self):
        """Добавить персонажа на сцену."""
        if not self.current_scene:
            return
        
        # Диалог выбора персонажа
        dialog = tk.Toplevel(self)
        dialog.title("Добавить персонажа на сцену")
        dialog.geometry("400x500")
        dialog.transient(self)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Персонаж:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        char_combo = ttk.Combobox(dialog, width=30, state='readonly')
        char_list = [f"{c.id} - {c.name}" for c in self.story.characters.values()]
        char_combo['values'] = char_list
        if char_list:
            char_combo.current(0)
        char_combo.grid(row=0, column=1, padx=10, pady=10)
        
        ttk.Label(dialog, text="Эмоция:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        emotion_combo = ttk.Combobox(dialog, width=20, state='readonly')
        emotion_combo['values'] = ['default']
        emotion_combo.current(0)
        emotion_combo.grid(row=1, column=1, padx=10, pady=5, sticky=tk.W)
        
        def update_emotions(event=None):
            if not char_combo.get():
                return
            char_id = char_combo.get().split(" - ")[0]
            character = self.story.get_character(char_id)
            if character:
                emotions = list(character.images.keys()) if character.images else ['default']
                if not emotions:
                    emotions = ['default']
                emotion_combo['values'] = emotions
                emotion_combo.current(0)
        
        char_combo.bind('<<ComboboxSelected>>', update_emotions)
        update_emotions()  # Инициализация
        
        ttk.Label(dialog, text="Позиция X (0-1):").grid(row=2, column=0, padx=10, pady=5, sticky=tk.W)
        x_entry = ttk.Entry(dialog, width=10)
        x_entry.insert(0, "0.5")
        x_entry.grid(row=2, column=1, padx=10, pady=5, sticky=tk.W)
        
        ttk.Label(dialog, text="Позиция Y (0-1):").grid(row=3, column=0, padx=10, pady=5, sticky=tk.W)
        y_entry = ttk.Entry(dialog, width=10)
        y_entry.insert(0, "0.7")
        y_entry.grid(row=3, column=1, padx=10, pady=5, sticky=tk.W)
        
        ttk.Label(dialog, text="Поворот (градусы):").grid(row=4, column=0, padx=10, pady=5, sticky=tk.W)
        rot_entry = ttk.Entry(dialog, width=10)
        rot_entry.insert(0, "0")
        rot_entry.grid(row=4, column=1, padx=10, pady=5, sticky=tk.W)
        
        ttk.Label(dialog, text="Масштаб:").grid(row=5, column=0, padx=10, pady=5, sticky=tk.W)
        scale_entry = ttk.Entry(dialog, width=10)
        scale_entry.insert(0, "1.0")
        scale_entry.grid(row=5, column=1, padx=10, pady=5, sticky=tk.W)
        
        # Перспектива
        ttk.Label(dialog, text="Перспектива X:").grid(row=6, column=0, padx=10, pady=5, sticky=tk.W)
        skew_x_entry = ttk.Entry(dialog, width=10)
        skew_x_entry.insert(0, "0")
        skew_x_entry.grid(row=6, column=1, padx=10, pady=5, sticky=tk.W)
        
        ttk.Label(dialog, text="Перспектива Y:").grid(row=7, column=0, padx=10, pady=5, sticky=tk.W)
        skew_y_entry = ttk.Entry(dialog, width=10)
        skew_y_entry.insert(0, "0")
        skew_y_entry.grid(row=7, column=1, padx=10, pady=5, sticky=tk.W)
        
        # Отзеркаливание
        flip_frame = ttk.Frame(dialog)
        flip_frame.grid(row=8, column=0, columnspan=2, padx=10, pady=5, sticky=tk.W)
        
        flip_x_var = tk.BooleanVar(value=False)
        flip_y_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(flip_frame, text="Отзеркалить ↔", variable=flip_x_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(flip_frame, text="Отзеркалить ↕", variable=flip_y_var).pack(side=tk.LEFT, padx=5)
        
        def add():
            if not char_combo.get():
                return
            char_id = char_combo.get().split(" - ")[0]
            
            try:
                x = float(x_entry.get())
                y = float(y_entry.get())
            except ValueError:
                x, y = 0.5, 0.7
            
            try:
                rotation = float(rot_entry.get())
            except ValueError:
                rotation = 0.0
            
            try:
                scale = float(scale_entry.get())
            except ValueError:
                scale = 1.0
            
            try:
                skew_x = float(skew_x_entry.get())
                skew_y = float(skew_y_entry.get())
            except ValueError:
                skew_x, skew_y = 0.0, 0.0
            
            char_data = {
                'id': char_id,
                'x': x,
                'y': y,
                'rotation': rotation,
                'scale': scale,
                'skew_x': skew_x,
                'skew_y': skew_y,
                'flip_x': flip_x_var.get(),
                'flip_y': flip_y_var.get(),
                'emotion': emotion_combo.get() or 'default'
            }
            self.current_scene.characters_on_screen.append(char_data)
            self._update_scene_chars_list()
            
            # Обновляем предпросмотр
            if self.preview and self.preview.running:
                character = self.story.get_character(char_id)
                if character:
                    image_path = character.images.get(char_data['emotion'], 
                                                      character.images.get('default', ''))
                    self.preview.add_character(char_id, character.name, image_path, x, y, char_data['emotion'],
                                               rotation, flip_x_var.get(), flip_y_var.get(), scale, skew_x, skew_y)
            
            self._auto_save_scene()
            dialog.destroy()
        
        ttk.Button(dialog, text="Добавить", command=add).grid(row=9, column=1, pady=20)
    
    def _remove_scene_character(self):
        """Удалить персонажа со сцены."""
        if not self.current_scene:
            return
        
        selection = self.scene_chars_listbox.curselection()
        if selection:
            char_data = self.current_scene.characters_on_screen[selection[0]]
            char_id = char_data.get('id')
            
            del self.current_scene.characters_on_screen[selection[0]]
            self._update_scene_chars_list()
            
            # Обновляем предпросмотр
            if self.preview and self.preview.running:
                self.preview.remove_character(char_id)
            
            self._auto_save_scene()
    
    def _edit_character_position(self):
        """Редактировать позицию персонажа."""
        if not self.current_scene:
            return
        
        selection = self.scene_chars_listbox.curselection()
        if not selection:
            return
        
        char_data = self.current_scene.characters_on_screen[selection[0]]
        char_id = char_data.get('id')
        character = self.story.get_character(char_id)
        
        dialog = tk.Toplevel(self)
        dialog.title("Позиция персонажа")
        dialog.geometry("340x480")
        dialog.transient(self)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Позиция X (0-1):").grid(row=0, column=0, padx=10, pady=5)
        x_entry = ttk.Entry(dialog, width=10)
        x_entry.insert(0, str(char_data.get('x', 0.5)))
        x_entry.grid(row=0, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="Позиция Y (0-1):").grid(row=1, column=0, padx=10, pady=5)
        y_entry = ttk.Entry(dialog, width=10)
        y_entry.insert(0, str(char_data.get('y', 0.7)))
        y_entry.grid(row=1, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="Поворот (градусы):").grid(row=2, column=0, padx=10, pady=5)
        rot_entry = ttk.Entry(dialog, width=10)
        rot_entry.insert(0, str(char_data.get('rotation', 0)))
        rot_entry.grid(row=2, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="Масштаб:").grid(row=3, column=0, padx=10, pady=5)
        scale_entry = ttk.Entry(dialog, width=10)
        scale_entry.insert(0, str(char_data.get('scale', 1.0)))
        scale_entry.grid(row=3, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="Перспектива X:").grid(row=4, column=0, padx=10, pady=5)
        skew_x_entry = ttk.Entry(dialog, width=10)
        skew_x_entry.insert(0, str(char_data.get('skew_x', 0)))
        skew_x_entry.grid(row=4, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="Перспектива Y:").grid(row=5, column=0, padx=10, pady=5)
        skew_y_entry = ttk.Entry(dialog, width=10)
        skew_y_entry.insert(0, str(char_data.get('skew_y', 0)))
        skew_y_entry.grid(row=5, column=1, padx=10, pady=5)
        
        # Отзеркаливание
        flip_frame = ttk.Frame(dialog)
        flip_frame.grid(row=6, column=0, columnspan=2, padx=10, pady=5)
        
        flip_x_var = tk.BooleanVar(value=char_data.get('flip_x', False))
        flip_y_var = tk.BooleanVar(value=char_data.get('flip_y', False))
        ttk.Checkbutton(flip_frame, text="Отзеркалить ↔", variable=flip_x_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(flip_frame, text="Отзеркалить ↕", variable=flip_y_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(dialog, text="Эмоция:").grid(row=7, column=0, padx=10, pady=5)
        emotion_combo = ttk.Combobox(dialog, width=15, state='readonly')
        emotions = list(character.images.keys()) if character and character.images else ['default']
        if not emotions:
            emotions = ['default']
        emotion_combo['values'] = emotions
        current_emotion = char_data.get('emotion', 'default')
        if current_emotion in emotions:
            emotion_combo.current(emotions.index(current_emotion))
        else:
            emotion_combo.current(0)
        emotion_combo.grid(row=7, column=1, padx=10, pady=5)
        
        def save():
            try:
                char_data['x'] = float(x_entry.get())
                char_data['y'] = float(y_entry.get())
            except ValueError:
                pass
            try:
                char_data['rotation'] = float(rot_entry.get())
            except ValueError:
                char_data['rotation'] = 0.0
            try:
                char_data['scale'] = float(scale_entry.get())
            except ValueError:
                char_data['scale'] = 1.0
            try:
                char_data['skew_x'] = float(skew_x_entry.get())
                char_data['skew_y'] = float(skew_y_entry.get())
            except ValueError:
                char_data['skew_x'] = 0.0
                char_data['skew_y'] = 0.0
            char_data['flip_x'] = flip_x_var.get()
            char_data['flip_y'] = flip_y_var.get()
            char_data['emotion'] = emotion_combo.get() or 'default'
            self._update_scene_chars_list()
            
            # Обновляем предпросмотр
            if self.preview and self.preview.running:
                if character:
                    image_path = character.images.get(char_data['emotion'], 
                                                      character.images.get('default', ''))
                    self.preview.update_character(char_id, image_path, 
                                                  char_data['x'], char_data['y'], char_data['emotion'])
            
            self._auto_save_scene()
            dialog.destroy()
        
        ttk.Button(dialog, text="Сохранить", command=save).grid(row=8, column=1, pady=15)
    
    def _add_scene_image(self):
        """Добавить картинку на сцену."""
        if not self.current_scene:
            return
        
        # Диалог добавления картинки
        dialog = tk.Toplevel(self)
        dialog.title("Добавить картинку на сцену")
        dialog.geometry("400x400")
        dialog.transient(self)
        dialog.grab_set()
        
        ttk.Label(dialog, text="ID картинки:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        id_entry = ttk.Entry(dialog, width=30)
        id_entry.insert(0, f"img_{len(self.current_scene.images_on_screen) + 1}")
        id_entry.grid(row=0, column=1, padx=10, pady=10)
        
        ttk.Label(dialog, text="Название:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        name_entry = ttk.Entry(dialog, width=30)
        name_entry.insert(0, "Картинка")
        name_entry.grid(row=1, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="Файл:").grid(row=2, column=0, padx=10, pady=5, sticky=tk.W)
        path_entry = ttk.Entry(dialog, width=30)
        path_entry.grid(row=2, column=1, padx=10, pady=5)
        
        def browse():
            path = filedialog.askopenfilename(
                filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp *.gif")]
            )
            if path:
                path_entry.delete(0, tk.END)
                path_entry.insert(0, path)
        
        ttk.Button(dialog, text="Обзор", command=browse).grid(row=2, column=2, padx=5, pady=5)
        
        ttk.Label(dialog, text="Позиция X (0-1):").grid(row=3, column=0, padx=10, pady=5, sticky=tk.W)
        x_entry = ttk.Entry(dialog, width=10)
        x_entry.insert(0, "0.5")
        x_entry.grid(row=3, column=1, padx=10, pady=5, sticky=tk.W)
        
        ttk.Label(dialog, text="Позиция Y (0-1):").grid(row=4, column=0, padx=10, pady=5, sticky=tk.W)
        y_entry = ttk.Entry(dialog, width=10)
        y_entry.insert(0, "0.5")
        y_entry.grid(row=4, column=1, padx=10, pady=5, sticky=tk.W)
        
        ttk.Label(dialog, text="Слой (порядок):").grid(row=5, column=0, padx=10, pady=5, sticky=tk.W)
        layer_entry = ttk.Entry(dialog, width=10)
        layer_entry.insert(0, "0")
        layer_entry.grid(row=5, column=1, padx=10, pady=5, sticky=tk.W)
        
        ttk.Label(dialog, text="Масштаб:").grid(row=6, column=0, padx=10, pady=5, sticky=tk.W)
        scale_entry = ttk.Entry(dialog, width=10)
        scale_entry.insert(0, "1.0")
        scale_entry.grid(row=6, column=1, padx=10, pady=5, sticky=tk.W)
        
        def add():
            img_id = id_entry.get().strip()
            if not img_id:
                return
            
            try:
                x = float(x_entry.get())
                y = float(y_entry.get())
            except ValueError:
                x, y = 0.5, 0.5
            
            try:
                layer = int(layer_entry.get())
            except ValueError:
                layer = 0
            
            try:
                scale = float(scale_entry.get())
            except ValueError:
                scale = 1.0
            
            # Копируем в assets если нужно
            img_path = path_entry.get().strip()
            if img_path:
                img_path = ensure_asset_in_dir(img_path, "img")
            
            img_data = {
                'id': img_id,
                'name': name_entry.get().strip() or img_id,
                'path': img_path,
                'x': x,
                'y': y,
                'layer': layer,
                'scale': scale,
                'rotation': 0,
                'flip_x': False,
                'flip_y': False,
                'skew_x': 0.0,
                'skew_y': 0.0
            }
            self.current_scene.images_on_screen.append(img_data)
            self._update_scene_images_list()
            
            # Обновляем предпросмотр
            if self.preview and self.preview.running:
                self.preview.add_image(img_id, img_data['name'], img_data['path'], x, y, layer,
                                       img_data['rotation'], img_data['flip_x'], img_data['flip_y'],
                                       img_data['scale'], img_data['skew_x'], img_data['skew_y'])
            
            self._auto_save_scene()
            dialog.destroy()
        
        ttk.Button(dialog, text="Добавить", command=add).grid(row=7, column=1, pady=20)
    
    def _remove_scene_image(self):
        """Удалить картинку со сцены."""
        if not self.current_scene:
            return
        
        selection = self.scene_images_listbox.curselection()
        if selection:
            img_data = self.current_scene.images_on_screen[selection[0]]
            img_id = img_data.get('id')
            
            del self.current_scene.images_on_screen[selection[0]]
            self._update_scene_images_list()
            
            # Обновляем предпросмотр
            if self.preview and self.preview.running:
                self.preview.remove_image(img_id)
            
            self._auto_save_scene()
    
    def _edit_image_position(self):
        """Редактировать позицию картинки."""
        if not self.current_scene:
            return
        
        selection = self.scene_images_listbox.curselection()
        if not selection:
            return
        
        img_data = self.current_scene.images_on_screen[selection[0]]
        
        dialog = tk.Toplevel(self)
        dialog.title("Позиция картинки")
        dialog.geometry("340x400")
        dialog.transient(self)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Позиция X (0-1):").grid(row=0, column=0, padx=10, pady=5)
        x_entry = ttk.Entry(dialog, width=10)
        x_entry.insert(0, str(img_data.get('x', 0.5)))
        x_entry.grid(row=0, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="Позиция Y (0-1):").grid(row=1, column=0, padx=10, pady=5)
        y_entry = ttk.Entry(dialog, width=10)
        y_entry.insert(0, str(img_data.get('y', 0.5)))
        y_entry.grid(row=1, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="Поворот (градусы):").grid(row=2, column=0, padx=10, pady=5)
        rot_entry = ttk.Entry(dialog, width=10)
        rot_entry.insert(0, str(img_data.get('rotation', 0)))
        rot_entry.grid(row=2, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="Масштаб:").grid(row=3, column=0, padx=10, pady=5)
        scale_entry = ttk.Entry(dialog, width=10)
        scale_entry.insert(0, str(img_data.get('scale', 1.0)))
        scale_entry.grid(row=3, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="Слой:").grid(row=4, column=0, padx=10, pady=5)
        layer_entry = ttk.Entry(dialog, width=10)
        layer_entry.insert(0, str(img_data.get('layer', 0)))
        layer_entry.grid(row=4, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="Перспектива X:").grid(row=5, column=0, padx=10, pady=5)
        skew_x_entry = ttk.Entry(dialog, width=10)
        skew_x_entry.insert(0, str(img_data.get('skew_x', 0)))
        skew_x_entry.grid(row=5, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="Перспектива Y:").grid(row=6, column=0, padx=10, pady=5)
        skew_y_entry = ttk.Entry(dialog, width=10)
        skew_y_entry.insert(0, str(img_data.get('skew_y', 0)))
        skew_y_entry.grid(row=6, column=1, padx=10, pady=5)
        
        flip_frame = ttk.Frame(dialog)
        flip_frame.grid(row=7, column=0, columnspan=2, padx=10, pady=5)
        
        flip_x_var = tk.BooleanVar(value=img_data.get('flip_x', False))
        flip_y_var = tk.BooleanVar(value=img_data.get('flip_y', False))
        ttk.Checkbutton(flip_frame, text="Отзеркалить ↔", variable=flip_x_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(flip_frame, text="Отзеркалить ↕", variable=flip_y_var).pack(side=tk.LEFT, padx=5)
        
        def save():
            try:
                img_data['x'] = float(x_entry.get())
                img_data['y'] = float(y_entry.get())
            except ValueError:
                pass
            try:
                img_data['rotation'] = float(rot_entry.get())
            except ValueError:
                img_data['rotation'] = 0
            try:
                img_data['scale'] = float(scale_entry.get())
            except ValueError:
                img_data['scale'] = 1.0
            try:
                img_data['layer'] = int(layer_entry.get())
            except ValueError:
                img_data['layer'] = 0
            try:
                img_data['skew_x'] = float(skew_x_entry.get())
                img_data['skew_y'] = float(skew_y_entry.get())
            except ValueError:
                img_data['skew_x'] = 0.0
                img_data['skew_y'] = 0.0
            img_data['flip_x'] = flip_x_var.get()
            img_data['flip_y'] = flip_y_var.get()
            self._update_scene_images_list()
            self._auto_save_scene()
            dialog.destroy()
        
        ttk.Button(dialog, text="Сохранить", command=save).grid(row=8, column=1, pady=15)
    
    def _update_scene_images_list(self):
        """Обновить список картинок на сцене."""
        self.scene_images_listbox.delete(0, tk.END)
        if self.current_scene:
            for img_data in self.current_scene.images_on_screen:
                img_id = img_data.get('id', '?')
                name = img_data.get('name', img_id)
                x = img_data.get('x', 0.5)
                y = img_data.get('y', 0.5)
                layer = img_data.get('layer', 0)
                scale = img_data.get('scale', 1.0)
                rotation = img_data.get('rotation', 0)
                
                # Формируем строку
                trans_parts = []
                if rotation:
                    trans_parts.append(f"↻{rotation:.0f}°")
                if scale != 1.0:
                    trans_parts.append(f"×{scale:.1f}")
                trans_str = " " + " ".join(trans_parts) if trans_parts else ""
                
                self.scene_images_listbox.insert(tk.END, f"{name} @ ({x:.2f}, {y:.2f}){trans_str} [L{layer}]")
    
    def _update_scene_texts_list(self):
        """Обновить список текстов на сцене."""
        self.scene_texts_listbox.delete(0, tk.END)
        if self.current_scene:
            # Сортируем по порядку для отображения
            sorted_texts = sorted(self.current_scene.texts_on_screen, key=lambda t: t.get('order', 0))
            for text_data in sorted_texts:
                text_id = text_data.get('id', '?')
                text = text_data.get('text', '')[:15]
                if len(text_data.get('text', '')) > 15:
                    text += "..."
                order = text_data.get('order', 0)
                animation = text_data.get('animation', 'none')
                block_skip = text_data.get('block_skip', False)
                
                # Формируем строку
                anim_str = f" [{animation}]" if animation != 'none' else ""
                block_str = " 🔒" if block_skip else ""
                self.scene_texts_listbox.insert(tk.END, f"#{order} {text_id}: \"{text}\"{anim_str}{block_str}")
    
    def _update_bg_animations_list(self):
        """Обновить список фоновых анимаций."""
        self.bg_anims_listbox.delete(0, tk.END)
        if self.current_scene and hasattr(self.current_scene, 'background_animations'):
            for anim in self.current_scene.background_animations:
                obj_id = anim.get('character_id') or anim.get('image_id', '?')
                obj_type = "👤" if anim.get('character_id') else "🖼️"
                kf_count = len(anim.get('keyframes', []))
                loop = "🔄" if anim.get('loop', False) else ""
                self.bg_anims_listbox.insert(tk.END, f"{obj_type} {obj_id}: {kf_count} кадр(ов) {loop}")
    
    def _remove_bg_animation(self):
        """Удалить выбранную фоновую анимацию."""
        if not self.current_scene:
            return
        
        selection = self.bg_anims_listbox.curselection()
        if not selection:
            messagebox.showinfo("Удаление", "Выберите анимацию для удаления")
            return
        
        index = selection[0]
        if hasattr(self.current_scene, 'background_animations') and 0 <= index < len(self.current_scene.background_animations):
            del self.current_scene.background_animations[index]
            self._update_bg_animations_list()
            self._auto_save_scene()
    
    def _clear_bg_animations(self):
        """Очистить все фоновые анимации."""
        if not self.current_scene:
            return
        
        if messagebox.askyesno("Очистить анимации", "Удалить все фоновые анимации сцены?"):
            self.current_scene.background_animations = []
            self._update_bg_animations_list()
            self._auto_save_scene()
    
    def _add_scene_text(self):
        """Добавить текст на сцену."""
        if not self.current_scene:
            messagebox.showwarning("Внимание", "Сначала выберите сцену")
            return
        
        dialog = tk.Toplevel(self.master)
        dialog.title("Добавить текст на сцену")
        dialog.geometry("450x700")
        dialog.transient(self.master)
        dialog.grab_set()
        
        # ID
        ttk.Label(dialog, text="ID текста:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        id_entry = ttk.Entry(dialog, width=30)
        id_entry.grid(row=0, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        id_entry.insert(0, f"text_{len(self.current_scene.texts_on_screen) + 1}")
        
        # Текст
        ttk.Label(dialog, text="Текст:").grid(row=1, column=0, sticky="nw", padx=10, pady=5)
        text_entry = tk.Text(dialog, width=30, height=3)
        text_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        
        # Позиция
        ttk.Label(dialog, text="Позиция X (0-1):").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        x_entry = ttk.Entry(dialog, width=10)
        x_entry.grid(row=2, column=1, padx=10, pady=5, sticky="w")
        x_entry.insert(0, "0.5")
        
        ttk.Label(dialog, text="Позиция Y (0-1):").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        y_entry = ttk.Entry(dialog, width=10)
        y_entry.grid(row=3, column=1, padx=10, pady=5, sticky="w")
        y_entry.insert(0, "0.3")
        
        # Размер шрифта
        ttk.Label(dialog, text="Размер шрифта:").grid(row=4, column=0, sticky="w", padx=10, pady=5)
        font_size_entry = ttk.Entry(dialog, width=10)
        font_size_entry.grid(row=4, column=1, padx=10, pady=5, sticky="w")
        font_size_entry.insert(0, "36")
        
        # Цвет текста
        ttk.Label(dialog, text="Цвет текста:").grid(row=5, column=0, sticky="w", padx=10, pady=5)
        color_var = tk.StringVar(value="#FFFFFF")
        color_preview = tk.Label(dialog, bg="#FFFFFF", width=5, relief="solid")
        color_preview.grid(row=5, column=1, padx=10, pady=5, sticky="w")
        
        def choose_color():
            result = colorchooser.askcolor(color=color_var.get(), title="Выберите цвет текста")
            if result[1]:
                color_var.set(result[1])
                color_preview.config(bg=result[1])
        
        ttk.Button(dialog, text="Выбрать...", command=choose_color).grid(row=5, column=2, padx=5, pady=5)
        
        # Цвет обводки
        ttk.Label(dialog, text="Цвет обводки:").grid(row=6, column=0, sticky="w", padx=10, pady=5)
        outline_color_var = tk.StringVar(value="#000000")
        outline_preview = tk.Label(dialog, bg="#000000", width=5, relief="solid")
        outline_preview.grid(row=6, column=1, padx=10, pady=5, sticky="w")
        
        def choose_outline_color():
            result = colorchooser.askcolor(color=outline_color_var.get(), title="Выберите цвет обводки")
            if result[1]:
                outline_color_var.set(result[1])
                outline_preview.config(bg=result[1])
        
        ttk.Button(dialog, text="Выбрать...", command=choose_outline_color).grid(row=6, column=2, padx=5, pady=5)
        
        # Толщина обводки
        ttk.Label(dialog, text="Толщина обводки:").grid(row=7, column=0, sticky="w", padx=10, pady=5)
        outline_width_entry = ttk.Entry(dialog, width=10)
        outline_width_entry.grid(row=7, column=1, padx=10, pady=5, sticky="w")
        outline_width_entry.insert(0, "2")
        
        # Порядок запуска
        ttk.Label(dialog, text="Порядок (очередь):").grid(row=8, column=0, sticky="w", padx=10, pady=5)
        order_entry = ttk.Entry(dialog, width=10)
        order_entry.grid(row=8, column=1, padx=10, pady=5, sticky="w")
        order_entry.insert(0, str(len(self.current_scene.texts_on_screen)))
        
        # Анимация
        ttk.Label(dialog, text="Анимация:").grid(row=9, column=0, sticky="w", padx=10, pady=5)
        animation_combo = ttk.Combobox(dialog, values=["none", "fade_in", "fade_out", "fade_in_out"], state="readonly", width=15)
        animation_combo.grid(row=9, column=1, padx=10, pady=5, sticky="w")
        animation_combo.current(0)
        
        # Длительность fade_in
        ttk.Label(dialog, text="Fade In (сек):").grid(row=10, column=0, sticky="w", padx=10, pady=5)
        fade_in_entry = ttk.Entry(dialog, width=10)
        fade_in_entry.grid(row=10, column=1, padx=10, pady=5, sticky="w")
        fade_in_entry.insert(0, "1.0")
        
        # Длительность показа
        ttk.Label(dialog, text="Показ (сек):").grid(row=11, column=0, sticky="w", padx=10, pady=5)
        hold_entry = ttk.Entry(dialog, width=10)
        hold_entry.grid(row=11, column=1, padx=10, pady=5, sticky="w")
        hold_entry.insert(0, "2.0")
        
        # Длительность fade_out
        ttk.Label(dialog, text="Fade Out (сек):").grid(row=12, column=0, sticky="w", padx=10, pady=5)
        fade_out_entry = ttk.Entry(dialog, width=10)
        fade_out_entry.grid(row=12, column=1, padx=10, pady=5, sticky="w")
        fade_out_entry.insert(0, "1.0")
        
        # Блокировка пропуска
        block_skip_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dialog, text="Блокировать пропуск во время анимации", variable=block_skip_var).grid(
            row=13, column=0, columnspan=3, padx=10, pady=5, sticky="w")
        
        # Масштаб
        ttk.Label(dialog, text="Масштаб:").grid(row=14, column=0, sticky="w", padx=10, pady=5)
        scale_entry = ttk.Entry(dialog, width=10)
        scale_entry.grid(row=14, column=1, padx=10, pady=5, sticky="w")
        scale_entry.insert(0, "1.0")
        
        # Поворот
        ttk.Label(dialog, text="Поворот (градусы):").grid(row=15, column=0, sticky="w", padx=10, pady=5)
        rotation_entry = ttk.Entry(dialog, width=10)
        rotation_entry.grid(row=15, column=1, padx=10, pady=5, sticky="w")
        rotation_entry.insert(0, "0")
        
        def save():
            text_id = id_entry.get().strip()
            text = text_entry.get("1.0", tk.END).strip()
            
            if not text_id or not text:
                messagebox.showwarning("Внимание", "Заполните ID и текст")
                return
            
            # Проверка уникальности ID
            for t in self.current_scene.texts_on_screen:
                if t.get('id') == text_id:
                    messagebox.showwarning("Внимание", "Текст с таким ID уже существует")
                    return
            
            try:
                x = float(x_entry.get())
                y = float(y_entry.get())
                font_size = int(font_size_entry.get())
                outline_width = int(outline_width_entry.get())
                order = int(order_entry.get())
                fade_in = float(fade_in_entry.get())
                hold = float(hold_entry.get())
                fade_out = float(fade_out_entry.get())
                scale = float(scale_entry.get())
                rotation = float(rotation_entry.get())
            except ValueError:
                messagebox.showwarning("Внимание", "Некорректные числовые значения")
                return
            
            # Конвертируем hex цвет в tuple RGB
            def hex_to_rgb(hex_color):
                hex_color = hex_color.lstrip('#')
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            
            text_data = {
                'id': text_id,
                'text': text,
                'x': x,
                'y': y,
                'font_size': font_size,
                'color': hex_to_rgb(color_var.get()),
                'outline_color': hex_to_rgb(outline_color_var.get()),
                'outline_width': outline_width,
                'order': order,
                'animation': animation_combo.get(),
                'fade_in_duration': fade_in,
                'hold_duration': hold,
                'fade_out_duration': fade_out,
                'block_skip': block_skip_var.get(),
                'scale': scale,
                'rotation': rotation
            }
            
            self.current_scene.texts_on_screen.append(text_data)
            self._update_scene_texts_list()
            self._auto_save_scene()
            dialog.destroy()
        
        ttk.Button(dialog, text="Добавить", command=save).grid(row=16, column=1, pady=15)
    
    def _edit_scene_text(self):
        """Редактировать выбранный текст."""
        if not self.current_scene:
            return
        
        selection = self.scene_texts_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите текст для редактирования")
            return
        
        idx = selection[0]
        text_data = self.current_scene.texts_on_screen[idx]
        
        dialog = tk.Toplevel(self.master)
        dialog.title("Редактировать текст")
        dialog.geometry("450x700")
        dialog.transient(self.master)
        dialog.grab_set()
        
        # ID
        ttk.Label(dialog, text="ID текста:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        id_entry = ttk.Entry(dialog, width=30)
        id_entry.grid(row=0, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        id_entry.insert(0, text_data.get('id', ''))
        
        # Текст
        ttk.Label(dialog, text="Текст:").grid(row=1, column=0, sticky="nw", padx=10, pady=5)
        text_entry = tk.Text(dialog, width=30, height=3)
        text_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        text_entry.insert("1.0", text_data.get('text', ''))
        
        # Позиция
        ttk.Label(dialog, text="Позиция X (0-1):").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        x_entry = ttk.Entry(dialog, width=10)
        x_entry.grid(row=2, column=1, padx=10, pady=5, sticky="w")
        x_entry.insert(0, str(text_data.get('x', 0.5)))
        
        ttk.Label(dialog, text="Позиция Y (0-1):").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        y_entry = ttk.Entry(dialog, width=10)
        y_entry.grid(row=3, column=1, padx=10, pady=5, sticky="w")
        y_entry.insert(0, str(text_data.get('y', 0.5)))
        
        # Размер шрифта
        ttk.Label(dialog, text="Размер шрифта:").grid(row=4, column=0, sticky="w", padx=10, pady=5)
        font_size_entry = ttk.Entry(dialog, width=10)
        font_size_entry.grid(row=4, column=1, padx=10, pady=5, sticky="w")
        font_size_entry.insert(0, str(text_data.get('font_size', 36)))
        
        # Цвет текста - конвертируем tuple в hex
        def rgb_to_hex(rgb):
            if isinstance(rgb, (list, tuple)) and len(rgb) >= 3:
                return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))
            return '#FFFFFF'
        
        initial_color = rgb_to_hex(text_data.get('color', (255, 255, 255)))
        
        ttk.Label(dialog, text="Цвет текста:").grid(row=5, column=0, sticky="w", padx=10, pady=5)
        color_var = tk.StringVar(value=initial_color)
        color_preview = tk.Label(dialog, bg=initial_color, width=5, relief="solid")
        color_preview.grid(row=5, column=1, padx=10, pady=5, sticky="w")
        
        def choose_color():
            result = colorchooser.askcolor(color=color_var.get(), title="Выберите цвет текста")
            if result[1]:
                color_var.set(result[1])
                color_preview.config(bg=result[1])
        
        ttk.Button(dialog, text="Выбрать...", command=choose_color).grid(row=5, column=2, padx=5, pady=5)
        
        # Цвет обводки
        initial_outline = rgb_to_hex(text_data.get('outline_color', (0, 0, 0)))
        
        ttk.Label(dialog, text="Цвет обводки:").grid(row=6, column=0, sticky="w", padx=10, pady=5)
        outline_color_var = tk.StringVar(value=initial_outline)
        outline_preview = tk.Label(dialog, bg=initial_outline, width=5, relief="solid")
        outline_preview.grid(row=6, column=1, padx=10, pady=5, sticky="w")
        
        def choose_outline_color():
            result = colorchooser.askcolor(color=outline_color_var.get(), title="Выберите цвет обводки")
            if result[1]:
                outline_color_var.set(result[1])
                outline_preview.config(bg=result[1])
        
        ttk.Button(dialog, text="Выбрать...", command=choose_outline_color).grid(row=6, column=2, padx=5, pady=5)
        
        # Толщина обводки
        ttk.Label(dialog, text="Толщина обводки:").grid(row=7, column=0, sticky="w", padx=10, pady=5)
        outline_width_entry = ttk.Entry(dialog, width=10)
        outline_width_entry.grid(row=7, column=1, padx=10, pady=5, sticky="w")
        outline_width_entry.insert(0, str(text_data.get('outline_width', 2)))
        
        # Порядок запуска
        ttk.Label(dialog, text="Порядок (очередь):").grid(row=8, column=0, sticky="w", padx=10, pady=5)
        order_entry = ttk.Entry(dialog, width=10)
        order_entry.grid(row=8, column=1, padx=10, pady=5, sticky="w")
        order_entry.insert(0, str(text_data.get('order', 0)))
        
        # Анимация
        ttk.Label(dialog, text="Анимация:").grid(row=9, column=0, sticky="w", padx=10, pady=5)
        animation_combo = ttk.Combobox(dialog, values=["none", "fade_in", "fade_out", "fade_in_out"], state="readonly", width=15)
        animation_combo.grid(row=9, column=1, padx=10, pady=5, sticky="w")
        current_anim = text_data.get('animation', 'none')
        anim_values = ["none", "fade_in", "fade_out", "fade_in_out"]
        if current_anim in anim_values:
            animation_combo.current(anim_values.index(current_anim))
        else:
            animation_combo.current(0)
        
        # Длительность fade_in
        ttk.Label(dialog, text="Fade In (сек):").grid(row=10, column=0, sticky="w", padx=10, pady=5)
        fade_in_entry = ttk.Entry(dialog, width=10)
        fade_in_entry.grid(row=10, column=1, padx=10, pady=5, sticky="w")
        fade_in_entry.insert(0, str(text_data.get('fade_in_duration', text_data.get('animation_duration', 1.0))))
        
        # Длительность показа
        ttk.Label(dialog, text="Показ (сек):").grid(row=11, column=0, sticky="w", padx=10, pady=5)
        hold_entry = ttk.Entry(dialog, width=10)
        hold_entry.grid(row=11, column=1, padx=10, pady=5, sticky="w")
        hold_entry.insert(0, str(text_data.get('hold_duration', 2.0)))
        
        # Длительность fade_out
        ttk.Label(dialog, text="Fade Out (сек):").grid(row=12, column=0, sticky="w", padx=10, pady=5)
        fade_out_entry = ttk.Entry(dialog, width=10)
        fade_out_entry.grid(row=12, column=1, padx=10, pady=5, sticky="w")
        fade_out_entry.insert(0, str(text_data.get('fade_out_duration', 1.0)))
        
        # Блокировка пропуска
        block_skip_var = tk.BooleanVar(value=text_data.get('block_skip', False))
        ttk.Checkbutton(dialog, text="Блокировать пропуск во время анимации", variable=block_skip_var).grid(
            row=13, column=0, columnspan=3, padx=10, pady=5, sticky="w")
        
        # Масштаб
        ttk.Label(dialog, text="Масштаб:").grid(row=14, column=0, sticky="w", padx=10, pady=5)
        scale_entry = ttk.Entry(dialog, width=10)
        scale_entry.grid(row=14, column=1, padx=10, pady=5, sticky="w")
        scale_entry.insert(0, str(text_data.get('scale', 1.0)))
        
        # Поворот
        ttk.Label(dialog, text="Поворот (градусы):").grid(row=15, column=0, sticky="w", padx=10, pady=5)
        rotation_entry = ttk.Entry(dialog, width=10)
        rotation_entry.grid(row=15, column=1, padx=10, pady=5, sticky="w")
        rotation_entry.insert(0, str(text_data.get('rotation', 0)))
        
        def save():
            text_id = id_entry.get().strip()
            text = text_entry.get("1.0", tk.END).strip()
            
            if not text_id or not text:
                messagebox.showwarning("Внимание", "Заполните ID и текст")
                return
            
            # Проверка уникальности ID (кроме текущего)
            for i, t in enumerate(self.current_scene.texts_on_screen):
                if i != idx and t.get('id') == text_id:
                    messagebox.showwarning("Внимание", "Текст с таким ID уже существует")
                    return
            
            try:
                x = float(x_entry.get())
                y = float(y_entry.get())
                font_size = int(font_size_entry.get())
                outline_width = int(outline_width_entry.get())
                order = int(order_entry.get())
                fade_in = float(fade_in_entry.get())
                hold = float(hold_entry.get())
                fade_out = float(fade_out_entry.get())
                scale = float(scale_entry.get())
                rotation = float(rotation_entry.get())
            except ValueError:
                messagebox.showwarning("Внимание", "Некорректные числовые значения")
                return
            
            # Конвертируем hex цвет в tuple RGB
            def hex_to_rgb(hex_color):
                hex_color = hex_color.lstrip('#')
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            
            self.current_scene.texts_on_screen[idx] = {
                'id': text_id,
                'text': text,
                'x': x,
                'y': y,
                'font_size': font_size,
                'color': hex_to_rgb(color_var.get()),
                'outline_color': hex_to_rgb(outline_color_var.get()),
                'outline_width': outline_width,
                'order': order,
                'animation': animation_combo.get(),
                'fade_in_duration': fade_in,
                'hold_duration': hold,
                'fade_out_duration': fade_out,
                'block_skip': block_skip_var.get(),
                'scale': scale,
                'rotation': rotation
            }
            
            self._update_scene_texts_list()
            self._auto_save_scene()
            dialog.destroy()
        
        ttk.Button(dialog, text="Сохранить", command=save).grid(row=16, column=1, pady=15)
    
    def _remove_scene_text(self):
        """Удалить выбранный текст."""
        if not self.current_scene:
            return
        
        selection = self.scene_texts_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите текст для удаления")
            return
        
        idx = selection[0]
        text_data = self.current_scene.texts_on_screen[idx]
        
        if messagebox.askyesno("Подтверждение", f"Удалить текст '{text_data.get('id', '?')}'?"):
            del self.current_scene.texts_on_screen[idx]
            self._update_scene_texts_list()
            self._auto_save_scene()
    
    def _update_scene_chars_list(self):
        """Обновить список персонажей на сцене."""
        self.scene_chars_listbox.delete(0, tk.END)
        if self.current_scene:
            for char_data in self.current_scene.characters_on_screen:
                char_id = char_data.get('id', '?')
                x = char_data.get('x', 0.5)
                y = char_data.get('y', 0.7)
                rotation = char_data.get('rotation', 0)
                scale = char_data.get('scale', 1.0)
                flip_x = char_data.get('flip_x', False)
                flip_y = char_data.get('flip_y', False)
                emotion = char_data.get('emotion', 'default')
                character = self.story.get_character(char_id)
                name = character.name if character else char_id
                
                # Формируем строку с трансформациями
                trans_parts = []
                if rotation:
                    trans_parts.append(f"↻{rotation:.0f}°")
                if scale != 1.0:
                    trans_parts.append(f"×{scale:.1f}")
                if flip_x:
                    trans_parts.append("↔")
                if flip_y:
                    trans_parts.append("↕")
                trans_str = " " + " ".join(trans_parts) if trans_parts else ""
                
                self.scene_chars_listbox.insert(tk.END, f"{name} @ ({x:.2f}, {y:.2f}){trans_str} [{emotion}]")
    
    def load_scene(self, scene: Scene):
        """Загрузить сцену в редактор."""
        self.current_scene = scene
        
        # Очистка
        self.id_entry.delete(0, tk.END)
        self.name_entry.delete(0, tk.END)
        self.bg_entry.delete(0, tk.END)
        self.music_entry.delete(0, tk.END)
        
        # Заполнение
        self.id_entry.insert(0, scene.id)
        self.name_entry.insert(0, scene.name)
        self.bg_entry.insert(0, scene.background or "")
        self.music_entry.insert(0, scene.music or "")
        
        # Цвет фона
        if scene.background_color:
            hex_color = '#{:02x}{:02x}{:02x}'.format(*scene.background_color)
            self.bg_color_var.set(hex_color)
            self.bg_color_preview.config(bg=hex_color)
        else:
            self.bg_color_var.set("")
            self.bg_color_preview.config(bg="#333333")
        
        # Обновление списка следующих сцен
        self._update_next_scene_combo()
        if scene.next_scene_id:
            scenes_ids = [s.id for s in self.story.scenes.values()]
            if scene.next_scene_id in scenes_ids:
                self.next_scene_combo.current(scenes_ids.index(scene.next_scene_id) + 1)  # +1 из-за пустого варианта
        
        self._update_scene_chars_list()
        self._update_scene_images_list()
        self._update_scene_texts_list()
        self._update_bg_animations_list()
        self._update_dialogs_list()
        self._update_choices_list()
    
    def _update_next_scene_combo(self):
        scene_list = ["(Нет - конец или выбор)"] + [f"{s.id} - {s.name}" for s in self.story.scenes.values()]
        self.next_scene_combo['values'] = scene_list
        self.next_scene_combo.current(0)
    
    def _update_dialogs_list(self):
        self.dialogs_listbox.delete(0, tk.END)
        if self.current_scene:
            for dialog in self.current_scene.dialogs:
                # Проверяем, это delay-only диалог
                if dialog.is_delay_only:
                    delay_sec = dialog.delay or 0
                    self.dialogs_listbox.insert(tk.END, f"⏱ [Ожидание {delay_sec} сек]")
                    continue
                
                char_name = "(Рассказчик)"
                if dialog.character_id:
                    char = self.story.get_character(dialog.character_id)
                    char_name = char.name if char else dialog.character_id
                
                text_preview = dialog.text[:40] + "..." if len(dialog.text) > 40 else dialog.text
                
                # Добавляем индикаторы
                indicators = ""
                if dialog.delay and dialog.delay > 0:
                    indicators += f" ⏱{dialog.delay}с"
                if dialog.animations:
                    indicators += " 🎬"
                
                self.dialogs_listbox.insert(tk.END, f"[{char_name}] {text_preview}{indicators}")
    
    def _update_choices_list(self):
        self.choices_listbox.delete(0, tk.END)
        if self.current_scene:
            for choice in self.current_scene.choices:
                self.choices_listbox.insert(tk.END, f"{choice.text} -> {choice.next_scene_id}")
    
    def _browse_background(self):
        path = filedialog.askopenfilename(
            filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp")]
        )
        if path:
            # Копируем в assets если нужно
            path = ensure_asset_in_dir(path, "img")
            self.bg_entry.delete(0, tk.END)
            self.bg_entry.insert(0, path)
            self._auto_save_scene()
    
    def _choose_bg_color(self):
        """Выбор цвета фона через палитру."""
        initial = self.bg_color_var.get() or "#333333"
        result = colorchooser.askcolor(color=initial, title="Выберите цвет фона")
        if result[1]:
            self.bg_color_var.set(result[1])
            self.bg_color_preview.config(bg=result[1])
            self._auto_save_scene()
    
    def _reset_bg_color(self):
        """Сбросить цвет фона."""
        self.bg_color_var.set("")
        self.bg_color_preview.config(bg="#333333")
        self._auto_save_scene()
    
    def _browse_music(self):
        path = filedialog.askopenfilename(
            filetypes=[("Аудио", "*.mp3 *.ogg *.wav")]
        )
        if path:
            # Копируем в assets если нужно
            path = ensure_asset_in_dir(path, "sound")
            self.music_entry.delete(0, tk.END)
            self.music_entry.insert(0, path)
            self._auto_save_scene()
    
    def _add_dialog(self):
        if not self.current_scene:
            return
        
        def on_save(dialog: DialogLine):
            self.current_scene.dialogs.append(dialog)
            self._update_dialogs_list()
            self._auto_save_scene()
        
        DialogEditor(self, self.story.characters, on_save=on_save, 
                     current_scene=self.current_scene, story=self.story)
    
    def _edit_dialog(self):
        if not self.current_scene:
            return
        
        selection = self.dialogs_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        dialog = self.current_scene.dialogs[index]
        
        def on_save(new_dialog: DialogLine):
            self.current_scene.dialogs[index] = new_dialog
            self._update_dialogs_list()
            self._auto_save_scene()
        
        DialogEditor(self, self.story.characters, dialog, on_save,
                     current_scene=self.current_scene, story=self.story)
    
    def _remove_dialog(self):
        """Delete selected dialog(s)."""
        if not self.current_scene:
            return
        
        selection = self.dialogs_listbox.curselection()
        if not selection:
            return
        
        # Если выбрано несколько - спрашиваем подтверждение
        if len(selection) > 1:
            if not messagebox.askyesno("Подтверждение", f"Удалить {len(selection)} диалогов?"):
                return
        
        # Удаляем с конца чтобы индексы не сбивались
        for idx in reversed(selection):
            del self.current_scene.dialogs[idx]
        
        self._update_dialogs_list()
        self._auto_save_scene()
    
    def _remove_all_dialogs(self):
        """Удалить все диалоги сцены."""
        if not self.current_scene:
            return
        
        if not self.current_scene.dialogs:
            messagebox.showinfo("Инфо", "Нет диалогов для удаления")
            return
        
        count = len(self.current_scene.dialogs)
        if messagebox.askyesno("Подтверждение", f"Удалить ВСЕ {count} диалогов?"):
            self.current_scene.dialogs.clear()
            self._update_dialogs_list()
            self._auto_save_scene()

    def _move_dialog_up(self):
        if not self.current_scene:
            return
        
        selection = self.dialogs_listbox.curselection()
        if selection and selection[0] > 0:
            idx = selection[0]
            self.current_scene.dialogs[idx], self.current_scene.dialogs[idx - 1] = \
                self.current_scene.dialogs[idx - 1], self.current_scene.dialogs[idx]
            self._update_dialogs_list()
            self.dialogs_listbox.selection_set(idx - 1)
            self._auto_save_scene()
    
    def _move_dialog_down(self):
        if not self.current_scene:
            return
        
        selection = self.dialogs_listbox.curselection()
        if selection and selection[0] < len(self.current_scene.dialogs) - 1:
            idx = selection[0]
            self.current_scene.dialogs[idx], self.current_scene.dialogs[idx + 1] = \
                self.current_scene.dialogs[idx + 1], self.current_scene.dialogs[idx]
            self._update_dialogs_list()
            self.dialogs_listbox.selection_set(idx + 1)
            self._auto_save_scene()
    
    def _add_choice(self):
        if not self.current_scene:
            return
        
        def on_save(choice: Choice):
            self.current_scene.choices.append(choice)
            self._update_choices_list()
            self._auto_save_scene()
        
        ChoiceEditor(self, self.story.scenes, on_save=on_save)
    
    def _edit_choice(self):
        if not self.current_scene:
            return
        
        selection = self.choices_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        choice = self.current_scene.choices[index]
        
        def on_save(new_choice: Choice):
            self.current_scene.choices[index] = new_choice
            self._update_choices_list()
            self._auto_save_scene()
        
        ChoiceEditor(self, self.story.scenes, choice, on_save)
    
    def _remove_choice(self):
        if not self.current_scene:
            return
        
        selection = self.choices_listbox.curselection()
        if selection:
            del self.current_scene.choices[selection[0]]
            self._update_choices_list()
            self._auto_save_scene()
    
    def _auto_save_scene(self):
        """Автоматическое сохранение сцены без уведомления."""
        self._save_scene(silent=True)
    
    def _save_scene(self, silent: bool = False):
        if not self.current_scene:
            return
        
        # Обновление данных сцены
        new_id = self.id_entry.get().strip()
        old_id = self.current_scene.id
        
        if new_id and new_id != old_id:
            # Обновление ID сцены
            if new_id in self.story.scenes:
                if not silent:
                    messagebox.showerror("Ошибка", "Сцена с таким ID уже существует!")
                return
            
            del self.story.scenes[old_id]
            self.current_scene.id = new_id
            self.story.scenes[new_id] = self.current_scene
            
            if self.story.start_scene_id == old_id:
                self.story.start_scene_id = new_id
        
        self.current_scene.name = self.name_entry.get().strip()
        self.current_scene.background = self.bg_entry.get().strip()
        self.current_scene.music = self.music_entry.get().strip()
        
        # Цвет фона
        bg_color_hex = self.bg_color_var.get()
        if bg_color_hex:
            # Конвертируем hex в RGB tuple
            hex_color = bg_color_hex.lstrip('#')
            self.current_scene.background_color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        else:
            self.current_scene.background_color = None
        
        # Следующая сцена
        next_scene = self.next_scene_combo.get()
        if next_scene and not next_scene.startswith("(Нет"):
            self.current_scene.next_scene_id = next_scene.split(" - ")[0]
        else:
            self.current_scene.next_scene_id = None
        
        if self.on_scene_changed:
            self.on_scene_changed()


class MenuEditorDialog(tk.Toplevel):
    """Диалог редактирования главного меню."""
    
    def __init__(self, parent, story: Story, on_save: Optional[Callable] = None):
        super().__init__(parent)
        self.title("Редактор главного меню")
        self.geometry("900x700")
        self.resizable(True, True)
        
        self.story = story
        self.on_save = on_save
        self.preview: Optional[MenuPreview] = None
        self.selected_item = None  # (type, id)
        
        self._create_widgets()
        self._load_config()
        
        self.transient(parent)
        self.grab_set()
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_close(self):
        """Закрытие окна."""
        if self.preview and self.preview.running:
            self.preview.stop()
        self.destroy()
    
    def _create_widgets(self):
        """Создать виджеты."""
        # Основной контейнер
        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Левая панель - настройки
        left_frame = ttk.Frame(main_paned, width=400)
        main_paned.add(left_frame, weight=1)
        
        # Notebook для вкладок
        self.notebook = ttk.Notebook(left_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Вкладка "Общие"
        self._create_general_tab()
        
        # Вкладка "Кнопки"
        self._create_buttons_tab()
        
        # Вкладка "Настройки"
        self._create_settings_tab()
        
        # Вкладка "Звуки"
        self._create_sounds_tab()
        
        # Правая панель - кнопки действий
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=0)
        
        actions_frame = ttk.LabelFrame(right_frame, text="Действия", padding=10)
        actions_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(actions_frame, text="🎬 Предпросмотр", command=self._open_preview).pack(fill=tk.X, pady=2)
        ttk.Button(actions_frame, text="💾 Сохранить", command=self._save).pack(fill=tk.X, pady=2)
        ttk.Button(actions_frame, text="🔄 Сбросить к умолчанию", command=self._reset_to_default).pack(fill=tk.X, pady=2)
        
        # Статус
        self.status_var = tk.StringVar(value="Готово")
        ttk.Label(right_frame, textvariable=self.status_var).pack(fill=tk.X, padx=5, pady=5)
    
    def _create_general_tab(self):
        """Создать вкладку общих настроек."""
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text="Общие")
        
        # Включено ли меню
        self.enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Включить главное меню", variable=self.enabled_var).pack(anchor=tk.W, pady=5)
        
        # Фон
        bg_frame = ttk.LabelFrame(frame, text="Фон", padding=10)
        bg_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(bg_frame, text="Изображение:").pack(anchor=tk.W)
        bg_path_frame = ttk.Frame(bg_frame)
        bg_path_frame.pack(fill=tk.X, pady=2)
        self.bg_entry = ttk.Entry(bg_path_frame, width=35)
        self.bg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(bg_path_frame, text="Обзор", command=self._browse_background).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(bg_frame, text="Или цвет:").pack(anchor=tk.W, pady=(10, 0))
        bg_color_frame = ttk.Frame(bg_frame)
        bg_color_frame.pack(fill=tk.X, pady=2)
        self.bg_color_preview = tk.Label(bg_color_frame, bg="#333355", width=5, relief="solid")
        self.bg_color_preview.pack(side=tk.LEFT)
        ttk.Button(bg_color_frame, text="Выбрать", command=self._choose_bg_color).pack(side=tk.LEFT, padx=2)
        ttk.Button(bg_color_frame, text="Сбросить", command=self._reset_bg_color).pack(side=tk.LEFT, padx=2)
        self.bg_color_var = tk.StringVar(value="")
        
        # Логотип
        logo_frame = ttk.LabelFrame(frame, text="Логотип", padding=10)
        logo_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(logo_frame, text="Изображение:").pack(anchor=tk.W)
        logo_path_frame = ttk.Frame(logo_frame)
        logo_path_frame.pack(fill=tk.X, pady=2)
        self.logo_entry = ttk.Entry(logo_path_frame, width=35)
        self.logo_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(logo_path_frame, text="Обзор", command=self._browse_logo).pack(side=tk.LEFT, padx=2)
        
        logo_params = ttk.Frame(logo_frame)
        logo_params.pack(fill=tk.X, pady=5)
        
        ttk.Label(logo_params, text="Масштаб:").pack(side=tk.LEFT)
        self.logo_scale = ttk.Entry(logo_params, width=8)
        self.logo_scale.insert(0, "1.0")
        self.logo_scale.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(logo_params, text="X:").pack(side=tk.LEFT, padx=(10, 0))
        self.logo_x = ttk.Entry(logo_params, width=8)
        self.logo_x.insert(0, "0.5")
        self.logo_x.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(logo_params, text="Y:").pack(side=tk.LEFT, padx=(5, 0))
        self.logo_y = ttk.Entry(logo_params, width=8)
        self.logo_y.insert(0, "0.2")
        self.logo_y.pack(side=tk.LEFT, padx=2)
        
        # Анимации
        anim_frame = ttk.LabelFrame(frame, text="Анимации", padding=10)
        anim_frame.pack(fill=tk.X, pady=5)
        
        self.anim_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(anim_frame, text="Включить анимации", variable=self.anim_enabled_var).pack(anchor=tk.W)
        
        anim_params = ttk.Frame(anim_frame)
        anim_params.pack(fill=tk.X, pady=5)
        
        ttk.Label(anim_params, text="Масштаб при наведении:").pack(side=tk.LEFT)
        self.hover_scale = ttk.Entry(anim_params, width=8)
        self.hover_scale.insert(0, "1.05")
        self.hover_scale.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(anim_params, text="Время появления (сек):").pack(side=tk.LEFT, padx=(10, 0))
        self.fade_duration = ttk.Entry(anim_params, width=8)
        self.fade_duration.insert(0, "0.5")
        self.fade_duration.pack(side=tk.LEFT, padx=5)
    
    def _create_buttons_tab(self):
        """Создать вкладку кнопок."""
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text="Кнопки")
        
        # Список кнопок
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.buttons_listbox = tk.Listbox(list_frame, height=8)
        self.buttons_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.buttons_listbox.bind('<<ListboxSelect>>', self._on_button_selected)
        
        btns_frame = ttk.Frame(list_frame)
        btns_frame.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btns_frame, text="+", width=3, command=self._add_button).pack(pady=2)
        ttk.Button(btns_frame, text="−", width=3, command=self._remove_button).pack(pady=2)
        
        # Редактор выбранной кнопки
        self.btn_edit_frame = ttk.LabelFrame(frame, text="Редактировать кнопку", padding=10)
        self.btn_edit_frame.pack(fill=tk.X, pady=10)
        
        # ID и текст
        row1 = ttk.Frame(self.btn_edit_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="ID:").pack(side=tk.LEFT)
        self.btn_id_entry = ttk.Entry(row1, width=15)
        self.btn_id_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="Текст:").pack(side=tk.LEFT, padx=(10, 0))
        self.btn_text_entry = ttk.Entry(row1, width=20)
        self.btn_text_entry.pack(side=tk.LEFT, padx=5)
        
        # Действие
        row2 = ttk.Frame(self.btn_edit_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="Действие:").pack(side=tk.LEFT)
        self.btn_action_combo = ttk.Combobox(row2, width=15, state='readonly', 
                                              values=["start", "continue", "settings", "exit"])
        self.btn_action_combo.pack(side=tk.LEFT, padx=5)
        
        # Позиция
        row3 = ttk.Frame(self.btn_edit_frame)
        row3.pack(fill=tk.X, pady=2)
        ttk.Label(row3, text="X:").pack(side=tk.LEFT)
        self.btn_x_entry = ttk.Entry(row3, width=8)
        self.btn_x_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(row3, text="Y:").pack(side=tk.LEFT)
        self.btn_y_entry = ttk.Entry(row3, width=8)
        self.btn_y_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(row3, text="Ширина:").pack(side=tk.LEFT)
        self.btn_width_entry = ttk.Entry(row3, width=8)
        self.btn_width_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(row3, text="Высота:").pack(side=tk.LEFT)
        self.btn_height_entry = ttk.Entry(row3, width=8)
        self.btn_height_entry.pack(side=tk.LEFT, padx=5)
        
        # Цвета
        row4 = ttk.Frame(self.btn_edit_frame)
        row4.pack(fill=tk.X, pady=2)
        
        ttk.Label(row4, text="Цвет фона:").pack(side=tk.LEFT)
        self.btn_bg_color = tk.Label(row4, bg="#333366", width=3, relief="solid")
        self.btn_bg_color.pack(side=tk.LEFT, padx=2)
        ttk.Button(row4, text="...", width=2, command=lambda: self._choose_btn_color("bg")).pack(side=tk.LEFT)
        
        ttk.Label(row4, text="Текст:").pack(side=tk.LEFT, padx=(10, 0))
        self.btn_text_color = tk.Label(row4, bg="#FFFFFF", width=3, relief="solid")
        self.btn_text_color.pack(side=tk.LEFT, padx=2)
        ttk.Button(row4, text="...", width=2, command=lambda: self._choose_btn_color("text")).pack(side=tk.LEFT)
        
        # Цвета hover и border
        row5 = ttk.Frame(self.btn_edit_frame)
        row5.pack(fill=tk.X, pady=2)
        
        ttk.Label(row5, text="Наведение:").pack(side=tk.LEFT)
        self.btn_hover_color = tk.Label(row5, bg="#4444AA", width=3, relief="solid")
        self.btn_hover_color.pack(side=tk.LEFT, padx=2)
        ttk.Button(row5, text="...", width=2, command=lambda: self._choose_btn_color("hover")).pack(side=tk.LEFT)
        
        ttk.Label(row5, text="Рамка:").pack(side=tk.LEFT, padx=(10, 0))
        self.btn_border_color = tk.Label(row5, bg="#6666AA", width=3, relief="solid")
        self.btn_border_color.pack(side=tk.LEFT, padx=2)
        ttk.Button(row5, text="...", width=2, command=lambda: self._choose_btn_color("border")).pack(side=tk.LEFT)
        
        # Видимость
        self.btn_visible_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.btn_edit_frame, text="Видимая", variable=self.btn_visible_var).pack(anchor=tk.W, pady=2)
        
        # Кнопка применить
        ttk.Button(self.btn_edit_frame, text="Применить изменения", command=self._apply_button_changes).pack(pady=5)
    
    def _create_settings_tab(self):
        """Создать вкладку настроек (слайдеры)."""
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text="Настройки")
        
        # Заголовок
        title_frame = ttk.LabelFrame(frame, text="Заголовок экрана настроек", padding=10)
        title_frame.pack(fill=tk.X, pady=5)
        
        row1 = ttk.Frame(title_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="Текст:").pack(side=tk.LEFT)
        self.settings_title_entry = ttk.Entry(row1, width=25)
        self.settings_title_entry.pack(side=tk.LEFT, padx=5)
        
        row2 = ttk.Frame(title_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="X:").pack(side=tk.LEFT)
        self.settings_title_x = ttk.Entry(row2, width=8)
        self.settings_title_x.pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="Y:").pack(side=tk.LEFT)
        self.settings_title_y = ttk.Entry(row2, width=8)
        self.settings_title_y.pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="Размер:").pack(side=tk.LEFT)
        self.settings_title_size = ttk.Entry(row2, width=8)
        self.settings_title_size.pack(side=tk.LEFT, padx=5)
        
        # Слайдеры
        sliders_frame = ttk.LabelFrame(frame, text="Слайдеры", padding=10)
        sliders_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.sliders_listbox = tk.Listbox(sliders_frame, height=5)
        self.sliders_listbox.pack(fill=tk.BOTH, expand=True)
        self.sliders_listbox.bind('<<ListboxSelect>>', self._on_slider_selected)
        
        # Редактор слайдера
        self.slider_edit_frame = ttk.Frame(sliders_frame)
        self.slider_edit_frame.pack(fill=tk.X, pady=5)
        
        row1 = ttk.Frame(self.slider_edit_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="Подпись:").pack(side=tk.LEFT)
        self.slider_label_entry = ttk.Entry(row1, width=15)
        self.slider_label_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="X:").pack(side=tk.LEFT)
        self.slider_x_entry = ttk.Entry(row1, width=8)
        self.slider_x_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="Y:").pack(side=tk.LEFT)
        self.slider_y_entry = ttk.Entry(row1, width=8)
        self.slider_y_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(self.slider_edit_frame, text="Применить", command=self._apply_slider_changes).pack(pady=2)
        
        # Кнопка "Назад"
        back_frame = ttk.LabelFrame(frame, text="Кнопка 'Назад'", padding=10)
        back_frame.pack(fill=tk.X, pady=5)
        
        row = ttk.Frame(back_frame)
        row.pack(fill=tk.X)
        ttk.Label(row, text="Текст:").pack(side=tk.LEFT)
        self.back_btn_text = ttk.Entry(row, width=15)
        self.back_btn_text.pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="X:").pack(side=tk.LEFT)
        self.back_btn_x = ttk.Entry(row, width=8)
        self.back_btn_x.pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="Y:").pack(side=tk.LEFT)
        self.back_btn_y = ttk.Entry(row, width=8)
        self.back_btn_y.pack(side=tk.LEFT, padx=5)
        
        # Bind для автосохранения
        self.back_btn_text.bind('<FocusOut>', lambda e: self._apply_back_button_changes())
        self.back_btn_x.bind('<FocusOut>', lambda e: self._apply_back_button_changes())
        self.back_btn_y.bind('<FocusOut>', lambda e: self._apply_back_button_changes())
        self.back_btn_text.bind('<Return>', lambda e: self._apply_back_button_changes())
        self.back_btn_x.bind('<Return>', lambda e: self._apply_back_button_changes())
        self.back_btn_y.bind('<Return>', lambda e: self._apply_back_button_changes())
    
    def _create_sounds_tab(self):
        """Создать вкладку звуков."""
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text="Звуки")
        
        # Фоновая музыка
        ttk.Label(frame, text="Фоновая музыка:").pack(anchor=tk.W, pady=(5, 0))
        music_frame = ttk.Frame(frame)
        music_frame.pack(fill=tk.X, pady=2)
        self.music_entry = ttk.Entry(music_frame, width=40)
        self.music_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(music_frame, text="Обзор", command=lambda: self._browse_sound("music")).pack(side=tk.LEFT, padx=2)
        
        # Звук наведения
        ttk.Label(frame, text="Звук при наведении:").pack(anchor=tk.W, pady=(10, 0))
        hover_frame = ttk.Frame(frame)
        hover_frame.pack(fill=tk.X, pady=2)
        self.hover_sound_entry = ttk.Entry(hover_frame, width=40)
        self.hover_sound_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(hover_frame, text="Обзор", command=lambda: self._browse_sound("hover")).pack(side=tk.LEFT, padx=2)
        
        # Звук клика
        ttk.Label(frame, text="Звук при нажатии:").pack(anchor=tk.W, pady=(10, 0))
        click_frame = ttk.Frame(frame)
        click_frame.pack(fill=tk.X, pady=2)
        self.click_sound_entry = ttk.Entry(click_frame, width=40)
        self.click_sound_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(click_frame, text="Обзор", command=lambda: self._browse_sound("click")).pack(side=tk.LEFT, padx=2)
        
        # Звук "Назад"
        ttk.Label(frame, text="Звук 'Назад':").pack(anchor=tk.W, pady=(10, 0))
        back_frame = ttk.Frame(frame)
        back_frame.pack(fill=tk.X, pady=2)
        self.back_sound_entry = ttk.Entry(back_frame, width=40)
        self.back_sound_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(back_frame, text="Обзор", command=lambda: self._browse_sound("back")).pack(side=tk.LEFT, padx=2)
    
    def _load_config(self):
        """Загрузить конфигурацию в поля."""
        config = self.story.main_menu
        
        # Общие
        self.enabled_var.set(config.enabled)
        self.bg_entry.delete(0, tk.END)
        self.bg_entry.insert(0, config.background or "")
        
        if config.background_color:
            color = "#{:02x}{:02x}{:02x}".format(*config.background_color)
            self.bg_color_var.set(color)
            self.bg_color_preview.config(bg=color)
        
        # Логотип
        self.logo_entry.delete(0, tk.END)
        self.logo_entry.insert(0, config.logo.image_path or "")
        self.logo_scale.delete(0, tk.END)
        self.logo_scale.insert(0, str(config.logo.scale))
        self.logo_x.delete(0, tk.END)
        self.logo_x.insert(0, str(config.logo.x))
        self.logo_y.delete(0, tk.END)
        self.logo_y.insert(0, str(config.logo.y))
        
        # Анимации
        self.anim_enabled_var.set(config.animation_enabled)
        self.hover_scale.delete(0, tk.END)
        self.hover_scale.insert(0, str(config.button_hover_scale))
        self.fade_duration.delete(0, tk.END)
        self.fade_duration.insert(0, str(config.fade_in_duration))
        
        # Кнопки
        self._update_buttons_list()
        
        # Настройки
        self.settings_title_entry.delete(0, tk.END)
        self.settings_title_entry.insert(0, config.settings_title)
        self.settings_title_x.delete(0, tk.END)
        self.settings_title_x.insert(0, str(config.settings_title_x))
        self.settings_title_y.delete(0, tk.END)
        self.settings_title_y.insert(0, str(config.settings_title_y))
        self.settings_title_size.delete(0, tk.END)
        self.settings_title_size.insert(0, str(config.settings_title_size))
        
        self._update_sliders_list()
        
        # Кнопка "Назад"
        self.back_btn_text.delete(0, tk.END)
        self.back_btn_text.insert(0, config.back_button.text)
        self.back_btn_x.delete(0, tk.END)
        self.back_btn_x.insert(0, str(config.back_button.x))
        self.back_btn_y.delete(0, tk.END)
        self.back_btn_y.insert(0, str(config.back_button.y))
        
        # Звуки
        self.music_entry.delete(0, tk.END)
        self.music_entry.insert(0, config.sounds.background_music or "")
        self.hover_sound_entry.delete(0, tk.END)
        self.hover_sound_entry.insert(0, config.sounds.hover_sound or "")
        self.click_sound_entry.delete(0, tk.END)
        self.click_sound_entry.insert(0, config.sounds.click_sound or "")
        self.back_sound_entry.delete(0, tk.END)
        self.back_sound_entry.insert(0, config.sounds.back_sound or "")
    
    def _update_buttons_list(self):
        """Обновить список кнопок."""
        self.buttons_listbox.delete(0, tk.END)
        for btn in self.story.main_menu.buttons:
            self.buttons_listbox.insert(tk.END, f"{btn.id}: {btn.text}")
    
    def _update_sliders_list(self):
        """Обновить список слайдеров."""
        self.sliders_listbox.delete(0, tk.END)
        for slider in self.story.main_menu.sliders:
            self.sliders_listbox.insert(tk.END, f"{slider.label} ({slider.setting})")
    
    def _on_button_selected(self, event):
        """Обработка выбора кнопки."""
        selection = self.buttons_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        if idx < len(self.story.main_menu.buttons):
            btn = self.story.main_menu.buttons[idx]
            
            self.btn_id_entry.delete(0, tk.END)
            self.btn_id_entry.insert(0, btn.id)
            self.btn_text_entry.delete(0, tk.END)
            self.btn_text_entry.insert(0, btn.text)
            self.btn_action_combo.set(btn.action)
            self.btn_x_entry.delete(0, tk.END)
            self.btn_x_entry.insert(0, str(btn.x))
            self.btn_y_entry.delete(0, tk.END)
            self.btn_y_entry.insert(0, str(btn.y))
            self.btn_width_entry.delete(0, tk.END)
            self.btn_width_entry.insert(0, str(btn.width))
            self.btn_height_entry.delete(0, tk.END)
            self.btn_height_entry.insert(0, str(btn.height))
            self.btn_visible_var.set(btn.visible)
            
            # Цвета
            bg_color = btn.bg_color[:7] if len(btn.bg_color) > 7 else btn.bg_color
            self.btn_bg_color.config(bg=bg_color)
            self.btn_text_color.config(bg=btn.text_color)
            hover_color = btn.hover_color[:7] if len(btn.hover_color) > 7 else btn.hover_color
            self.btn_hover_color.config(bg=hover_color)
            border_color = btn.border_color[:7] if len(btn.border_color) > 7 else btn.border_color
            self.btn_border_color.config(bg=border_color)
    
    def _on_slider_selected(self, event):
        """Обработка выбора слайдера."""
        selection = self.sliders_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        if idx < len(self.story.main_menu.sliders):
            slider = self.story.main_menu.sliders[idx]
            
            self.slider_label_entry.delete(0, tk.END)
            self.slider_label_entry.insert(0, slider.label)
            self.slider_x_entry.delete(0, tk.END)
            self.slider_x_entry.insert(0, str(slider.x))
            self.slider_y_entry.delete(0, tk.END)
            self.slider_y_entry.insert(0, str(slider.y))
    
    def _add_button(self):
        """Добавить новую кнопку."""
        new_id = f"btn_{len(self.story.main_menu.buttons) + 1}"
        new_btn = MenuButton(id=new_id, text="Новая кнопка", action="start", x=0.5, y=0.5)
        self.story.main_menu.buttons.append(new_btn)
        self._update_buttons_list()
    
    def _remove_button(self):
        """Удалить кнопку."""
        selection = self.buttons_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        if idx < len(self.story.main_menu.buttons):
            del self.story.main_menu.buttons[idx]
            self._update_buttons_list()
    
    def _apply_button_changes(self):
        """Применить изменения кнопки."""
        selection = self.buttons_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        if idx < len(self.story.main_menu.buttons):
            btn = self.story.main_menu.buttons[idx]
            
            btn.id = self.btn_id_entry.get().strip()
            btn.text = self.btn_text_entry.get().strip()
            btn.action = self.btn_action_combo.get()
            btn.x = float(self.btn_x_entry.get() or 0.5)
            btn.y = float(self.btn_y_entry.get() or 0.5)
            btn.width = int(self.btn_width_entry.get() or 300)
            btn.height = int(self.btn_height_entry.get() or 60)
            btn.visible = self.btn_visible_var.get()
            
            self._update_buttons_list()
            self._update_preview()
    
    def _apply_slider_changes(self):
        """Применить изменения слайдера."""
        selection = self.sliders_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        if idx < len(self.story.main_menu.sliders):
            slider = self.story.main_menu.sliders[idx]
            
            slider.label = self.slider_label_entry.get().strip()
            slider.x = float(self.slider_x_entry.get() or 0.5)
            slider.y = float(self.slider_y_entry.get() or 0.5)
            
            self._update_sliders_list()
            self._update_preview()
    
    def _apply_back_button_changes(self):
        """Применить изменения кнопки Назад."""
        config = self.story.main_menu
        config.back_button.text = self.back_btn_text.get().strip() or "Назад"
        try:
            config.back_button.x = float(self.back_btn_x.get() or 0.5)
        except ValueError:
            config.back_button.x = 0.5
        try:
            config.back_button.y = float(self.back_btn_y.get() or 0.85)
        except ValueError:
            config.back_button.y = 0.85
        self._update_preview()
    
    def _choose_btn_color(self, color_type: str):
        """Выбрать цвет кнопки."""
        titles = {"bg": "фона", "text": "текста", "hover": "наведения", "border": "рамки"}
        color = colorchooser.askcolor(title=f"Выберите цвет {titles.get(color_type, '')}")
        if color[1]:
            selection = self.buttons_listbox.curselection()
            if not selection:
                return
            idx = selection[0]
            if idx >= len(self.story.main_menu.buttons):
                return
            btn = self.story.main_menu.buttons[idx]
            
            if color_type == "bg":
                self.btn_bg_color.config(bg=color[1])
                btn.bg_color = color[1] + "AA"
            elif color_type == "text":
                self.btn_text_color.config(bg=color[1])
                btn.text_color = color[1]
            elif color_type == "hover":
                self.btn_hover_color.config(bg=color[1])
                btn.hover_color = color[1] + "CC"
            elif color_type == "border":
                self.btn_border_color.config(bg=color[1])
                btn.border_color = color[1]
            
            self._update_preview()
    
    def _browse_background(self):
        """Выбрать фон."""
        path = filedialog.askopenfilename(
            title="Выберите фон",
            filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp *.webp")]
        )
        if path:
            path = ensure_asset_in_dir(path, "img")
            self.bg_entry.delete(0, tk.END)
            self.bg_entry.insert(0, path)
            self._collect_config()
            self._update_preview()
    
    def _browse_logo(self):
        """Выбрать логотип."""
        path = filedialog.askopenfilename(
            title="Выберите логотип",
            filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp *.webp")]
        )
        if path:
            path = ensure_asset_in_dir(path, "img")
            self.logo_entry.delete(0, tk.END)
            self.logo_entry.insert(0, path)
            self._collect_config()
            self._update_preview()
    
    def _browse_sound(self, sound_type: str):
        """Выбрать звуковой файл."""
        path = filedialog.askopenfilename(
            title="Выберите звуковой файл",
            filetypes=[("Аудио", "*.mp3 *.wav *.ogg")]
        )
        if path:
            path = ensure_asset_in_dir(path, "sound")
            if sound_type == "music":
                self.music_entry.delete(0, tk.END)
                self.music_entry.insert(0, path)
            elif sound_type == "hover":
                self.hover_sound_entry.delete(0, tk.END)
                self.hover_sound_entry.insert(0, path)
            elif sound_type == "click":
                self.click_sound_entry.delete(0, tk.END)
                self.click_sound_entry.insert(0, path)
            elif sound_type == "back":
                self.back_sound_entry.delete(0, tk.END)
                self.back_sound_entry.insert(0, path)
            self._collect_config()
            self._update_preview()
    
    def _choose_bg_color(self):
        """Выбрать цвет фона."""
        color = colorchooser.askcolor(title="Выберите цвет фона")
        if color[1]:
            self.bg_color_var.set(color[1])
            self.bg_color_preview.config(bg=color[1])
            self._collect_config()
            self._update_preview()
    
    def _reset_bg_color(self):
        """Сбросить цвет фона."""
        self.bg_color_var.set("")
        self.bg_color_preview.config(bg="#333355")
        self._collect_config()
        self._update_preview()
    
    def _open_preview(self):
        """Открыть предпросмотр."""
        # Сначала сохраняем текущие значения
        self._collect_config()
        
        if self.preview and self.preview.running:
            messagebox.showerror("Ошибка", "Предпросмотр уже открыт")
            return
        
        self.preview = MenuPreview(960, 540)
        self.preview.on_position_changed = self._on_preview_position_changed
        self.preview.on_item_selected = self._on_preview_item_selected
        self.preview.start()
        
        # Загружаем конфигурацию
        self.after(500, lambda: self.preview.load_config(self.story.main_menu))
    
    def _on_preview_position_changed(self, item_type, item_id, x, y):
        """Обработка изменения позиции в предпросмотре."""
        # Обновляем поля ввода
        if item_type == "logo":
            self.logo_x.delete(0, tk.END)
            self.logo_x.insert(0, f"{x:.3f}")
            self.logo_y.delete(0, tk.END)
            self.logo_y.insert(0, f"{y:.3f}")
        elif item_type == "button":
            # Обновляем кнопку в конфиге
            for btn in self.story.main_menu.buttons:
                if btn.id == item_id:
                    btn.x = x
                    btn.y = y
                    break
            if self.story.main_menu.back_button.id == item_id:
                self.story.main_menu.back_button.x = x
                self.story.main_menu.back_button.y = y
            self._update_buttons_list()
        elif item_type == "slider":
            for slider in self.story.main_menu.sliders:
                if slider.id == item_id:
                    slider.x = x
                    slider.y = y
                    break
            self._update_sliders_list()
        elif item_type == "title":
            self.settings_title_x.delete(0, tk.END)
            self.settings_title_x.insert(0, f"{x:.3f}")
            self.settings_title_y.delete(0, tk.END)
            self.settings_title_y.insert(0, f"{y:.3f}")
    
    def _on_preview_item_selected(self, item_type, item_id):
        """Обработка выбора элемента в предпросмотре."""
        self.selected_item = (item_type, item_id) if item_type else None
        self.status_var.set(f"Выбрано: {item_type} - {item_id}" if item_type else "Готово")
    
    def _update_preview(self):
        """Обновить предпросмотр."""
        if self.preview and self.preview.running:
            self.preview.load_config(self.story.main_menu)
    
    def _collect_config(self):
        """Собрать конфигурацию из полей."""
        config = self.story.main_menu
        
        config.enabled = self.enabled_var.get()
        config.background = self.bg_entry.get().strip()
        
        bg_color = self.bg_color_var.get()
        if bg_color:
            hex_color = bg_color.lstrip('#')
            config.background_color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        else:
            config.background_color = None
        
        # Логотип
        config.logo.image_path = self.logo_entry.get().strip()
        config.logo.scale = float(self.logo_scale.get() or 1.0)
        config.logo.x = float(self.logo_x.get() or 0.5)
        config.logo.y = float(self.logo_y.get() or 0.2)
        
        # Анимации
        config.animation_enabled = self.anim_enabled_var.get()
        config.button_hover_scale = float(self.hover_scale.get() or 1.05)
        config.fade_in_duration = float(self.fade_duration.get() or 0.5)
        
        # Настройки
        config.settings_title = self.settings_title_entry.get().strip()
        config.settings_title_x = float(self.settings_title_x.get() or 0.5)
        config.settings_title_y = float(self.settings_title_y.get() or 0.15)
        config.settings_title_size = int(self.settings_title_size.get() or 48)
        
        # Кнопка "Назад"
        config.back_button.text = self.back_btn_text.get().strip()
        config.back_button.x = float(self.back_btn_x.get() or 0.5)
        config.back_button.y = float(self.back_btn_y.get() or 0.85)
        
        # Звуки
        config.sounds.background_music = self.music_entry.get().strip()
        config.sounds.hover_sound = self.hover_sound_entry.get().strip()
        config.sounds.click_sound = self.click_sound_entry.get().strip()
        config.sounds.back_sound = self.back_sound_entry.get().strip()
    
    def _save(self):
        """Сохранить конфигурацию."""
        self._collect_config()
        
        if self.on_save:
            self.on_save()
        
        self.status_var.set("Сохранено")
        messagebox.showinfo("Сохранено", "Настройки меню сохранены")
    
    def _reset_to_default(self):
        """Сбросить к настройкам по умолчанию."""
        if messagebox.askyesno("Подтверждение", "Сбросить все настройки меню к значениям по умолчанию?"):
            self.story.main_menu = MainMenuConfig()
            self._load_config()
            self._update_preview()


class PauseMenuEditorDialog(tk.Toplevel):
    """Диалог редактирования меню паузы."""
    
    def __init__(self, parent, story: Story, on_save: Optional[Callable] = None):
        super().__init__(parent)
        self.title("Редактор меню паузы")
        self.geometry("900x700")
        self.resizable(True, True)
        
        self.story = story
        self.on_save = on_save
        self.preview = None
        self.selected_item = None
        
        self._create_widgets()
        self._load_config()
        self._start_preview()
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_widgets(self):
        """Создание виджетов."""
        from tkinter import ttk
        
        # Основной контейнер
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Notebook с вкладками
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Вкладка "Общие"
        general_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(general_frame, text="Общие")
        self._create_general_tab(general_frame)
        
        # Вкладка "Кнопки"
        buttons_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(buttons_frame, text="Кнопки")
        self._create_buttons_tab(buttons_frame)
        
        # Вкладка "Сохранения"
        saves_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(saves_frame, text="Сохранения")
        self._create_saves_tab(saves_frame)
        
        # Вкладка "Настройки"
        settings_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(settings_frame, text="Настройки")
        self._create_settings_tab(settings_frame)
        
        # Вкладка "Звуки"
        sounds_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(sounds_frame, text="Звуки")
        self._create_sounds_tab(sounds_frame)
        
        # Кнопки внизу
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(btn_frame, text="Сохранить", command=self._save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Сбросить", command=self._reset).pack(side=tk.RIGHT, padx=5)
        
        # Переключатель экрана превью
        ttk.Label(btn_frame, text="Превью экрана:").pack(side=tk.LEFT, padx=5)
        self.screen_var = tk.StringVar(value="main")
        screen_combo = ttk.Combobox(btn_frame, textvariable=self.screen_var, values=["main", "save", "load", "settings"], state="readonly", width=15)
        screen_combo.pack(side=tk.LEFT, padx=5)
        screen_combo.bind("<<ComboboxSelected>>", self._on_screen_changed)
    
    def _create_general_tab(self, parent):
        """Создание вкладки общих настроек."""
        from tkinter import ttk
        
        # Включить меню паузы
        self.enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text="Включить меню паузы (ESC)", variable=self.enabled_var, command=self._on_change).pack(anchor=tk.W, pady=5)
        
        ttk.Separator(parent, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Затемнение
        ttk.Label(parent, text="Затемнение фона", font=('', 10, 'bold')).pack(anchor=tk.W, pady=5)
        
        overlay_frame = ttk.Frame(parent)
        overlay_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(overlay_frame, text="Цвет:").pack(side=tk.LEFT, padx=5)
        self.overlay_color_btn = tk.Button(overlay_frame, width=5, bg="#000000", command=self._choose_overlay_color)
        self.overlay_color_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(overlay_frame, text="Прозрачность:").pack(side=tk.LEFT, padx=(20, 5))
        self.overlay_alpha_var = tk.IntVar(value=180)
        ttk.Scale(overlay_frame, from_=0, to=255, variable=self.overlay_alpha_var, command=lambda e: self._on_change()).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        ttk.Separator(parent, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Панель меню
        ttk.Label(parent, text="Панель меню", font=('', 10, 'bold')).pack(anchor=tk.W, pady=5)
        
        panel_frame = ttk.Frame(parent)
        panel_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(panel_frame, text="Ширина:").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        self.panel_width_var = tk.IntVar(value=400)
        ttk.Spinbox(panel_frame, from_=200, to=800, textvariable=self.panel_width_var, width=10, command=self._on_change).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(panel_frame, text="Высота:").grid(row=0, column=2, padx=5, pady=2, sticky=tk.W)
        self.panel_height_var = tk.IntVar(value=500)
        ttk.Spinbox(panel_frame, from_=200, to=800, textvariable=self.panel_height_var, width=10, command=self._on_change).grid(row=0, column=3, padx=5, pady=2)
        
        ttk.Label(panel_frame, text="Цвет фона:").grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)
        self.panel_bg_btn = tk.Button(panel_frame, width=5, bg="#1A1A3C", command=self._choose_panel_bg)
        self.panel_bg_btn.grid(row=1, column=1, padx=5, pady=2, sticky=tk.W)
        
        ttk.Label(panel_frame, text="Цвет рамки:").grid(row=1, column=2, padx=5, pady=2, sticky=tk.W)
        self.panel_border_btn = tk.Button(panel_frame, width=5, bg="#4444AA", command=self._choose_panel_border)
        self.panel_border_btn.grid(row=1, column=3, padx=5, pady=2, sticky=tk.W)
        
        ttk.Separator(parent, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Заголовок
        ttk.Label(parent, text="Заголовок", font=('', 10, 'bold')).pack(anchor=tk.W, pady=5)
        
        title_frame = ttk.Frame(parent)
        title_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(title_frame, text="Текст:").pack(side=tk.LEFT, padx=5)
        self.title_var = tk.StringVar(value="Пауза")
        ttk.Entry(title_frame, textvariable=self.title_var, width=30).pack(side=tk.LEFT, padx=5)
        self.title_var.trace_add("write", lambda *a: self._on_change())
        
        ttk.Label(title_frame, text="Размер:").pack(side=tk.LEFT, padx=5)
        self.title_size_var = tk.IntVar(value=42)
        ttk.Spinbox(title_frame, from_=20, to=100, textvariable=self.title_size_var, width=5, command=self._on_change).pack(side=tk.LEFT, padx=5)
    
    def _create_buttons_tab(self, parent):
        """Создание вкладки кнопок."""
        from tkinter import ttk
        
        # Список кнопок
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(list_frame, text="Кнопки меню паузы:").pack(anchor=tk.W)
        
        self.buttons_listbox = tk.Listbox(list_frame, height=8)
        self.buttons_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.buttons_listbox.bind("<<ListboxSelect>>", self._on_button_selected)
        
        # Кнопки управления
        btn_manage = ttk.Frame(list_frame)
        btn_manage.pack(fill=tk.X, pady=5)
        ttk.Button(btn_manage, text="Добавить", command=self._add_button).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_manage, text="Удалить", command=self._delete_button).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_manage, text="Вверх", command=self._move_button_up).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_manage, text="Вниз", command=self._move_button_down).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(parent, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Редактирование выбранной кнопки
        edit_frame = ttk.LabelFrame(parent, text="Редактирование кнопки", padding=10)
        edit_frame.pack(fill=tk.X, pady=5)
        
        # Текст
        row1 = ttk.Frame(edit_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="Текст:").pack(side=tk.LEFT, padx=5)
        self.btn_text_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.btn_text_var, width=30).pack(side=tk.LEFT, padx=5)
        self.btn_text_var.trace_add("write", lambda *a: self._on_button_change())
        
        # Действие
        ttk.Label(row1, text="Действие:").pack(side=tk.LEFT, padx=5)
        self.btn_action_var = tk.StringVar()
        actions = ["resume", "save", "load", "settings", "main_menu", "exit"]
        ttk.Combobox(row1, textvariable=self.btn_action_var, values=actions, state="readonly", width=15).pack(side=tk.LEFT, padx=5)
        self.btn_action_var.trace_add("write", lambda *a: self._on_button_change())
        
        # Размеры
        row2 = ttk.Frame(edit_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="Ширина:").pack(side=tk.LEFT, padx=5)
        self.btn_width_var = tk.IntVar(value=250)
        ttk.Spinbox(row2, from_=100, to=500, textvariable=self.btn_width_var, width=6, command=self._on_button_change).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row2, text="Высота:").pack(side=tk.LEFT, padx=5)
        self.btn_height_var = tk.IntVar(value=50)
        ttk.Spinbox(row2, from_=30, to=100, textvariable=self.btn_height_var, width=6, command=self._on_button_change).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row2, text="Шрифт:").pack(side=tk.LEFT, padx=5)
        self.btn_font_var = tk.IntVar(value=28)
        ttk.Spinbox(row2, from_=16, to=48, textvariable=self.btn_font_var, width=5, command=self._on_button_change).pack(side=tk.LEFT, padx=5)
        
        # Видимость
        self.btn_visible_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="Видимая", variable=self.btn_visible_var, command=self._on_button_change).pack(side=tk.LEFT, padx=10)
        
        # Цвета
        row3 = ttk.Frame(edit_frame)
        row3.pack(fill=tk.X, pady=2)
        
        ttk.Label(row3, text="Фон:").pack(side=tk.LEFT, padx=5)
        self.pause_btn_bg_color = tk.Label(row3, bg="#333366", width=3, relief="solid")
        self.pause_btn_bg_color.pack(side=tk.LEFT, padx=2)
        ttk.Button(row3, text="...", width=2, command=lambda: self._choose_pause_btn_color("bg")).pack(side=tk.LEFT)
        
        ttk.Label(row3, text="Наведение:").pack(side=tk.LEFT, padx=(10, 5))
        self.pause_btn_hover_color = tk.Label(row3, bg="#4444AA", width=3, relief="solid")
        self.pause_btn_hover_color.pack(side=tk.LEFT, padx=2)
        ttk.Button(row3, text="...", width=2, command=lambda: self._choose_pause_btn_color("hover")).pack(side=tk.LEFT)
        
        ttk.Label(row3, text="Рамка:").pack(side=tk.LEFT, padx=(10, 5))
        self.pause_btn_border_color = tk.Label(row3, bg="#6666AA", width=3, relief="solid")
        self.pause_btn_border_color.pack(side=tk.LEFT, padx=2)
        ttk.Button(row3, text="...", width=2, command=lambda: self._choose_pause_btn_color("border")).pack(side=tk.LEFT)
    
    def _create_saves_tab(self, parent):
        """Создание вкладки сохранений."""
        from tkinter import ttk
        
        ttk.Label(parent, text="Экран сохранения/загрузки", font=('', 10, 'bold')).pack(anchor=tk.W, pady=5)
        
        # Заголовки
        title_frame = ttk.Frame(parent)
        title_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(title_frame, text="Заголовок (сохранение):").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        self.save_title_var = tk.StringVar(value="Сохранение")
        ttk.Entry(title_frame, textvariable=self.save_title_var, width=20).grid(row=0, column=1, padx=5, pady=2)
        self.save_title_var.trace_add("write", lambda *a: self._on_change())
        
        ttk.Label(title_frame, text="Заголовок (загрузка):").grid(row=0, column=2, padx=5, pady=2, sticky=tk.W)
        self.load_title_var = tk.StringVar(value="Загрузка")
        ttk.Entry(title_frame, textvariable=self.load_title_var, width=20).grid(row=0, column=3, padx=5, pady=2)
        self.load_title_var.trace_add("write", lambda *a: self._on_change())
        
        ttk.Separator(parent, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Сетка слотов
        ttk.Label(parent, text="Сетка слотов", font=('', 10, 'bold')).pack(anchor=tk.W, pady=5)
        
        grid_frame = ttk.Frame(parent)
        grid_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(grid_frame, text="Слотов на страницу:").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        self.slots_per_page_var = tk.IntVar(value=4)
        ttk.Spinbox(grid_frame, from_=2, to=8, textvariable=self.slots_per_page_var, width=5, command=self._on_change).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(grid_frame, text="Всего страниц:").grid(row=0, column=2, padx=5, pady=2, sticky=tk.W)
        self.total_pages_var = tk.IntVar(value=5)
        ttk.Spinbox(grid_frame, from_=1, to=20, textvariable=self.total_pages_var, width=5, command=self._on_change).grid(row=0, column=3, padx=5, pady=2)
        
        ttk.Label(grid_frame, text="Расстояние X:").grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)
        self.slots_spacing_x_var = tk.IntVar(value=300)
        ttk.Spinbox(grid_frame, from_=200, to=500, textvariable=self.slots_spacing_x_var, width=5, command=self._on_change).grid(row=1, column=1, padx=5, pady=2)
        
        ttk.Label(grid_frame, text="Расстояние Y:").grid(row=1, column=2, padx=5, pady=2, sticky=tk.W)
        self.slots_spacing_y_var = tk.IntVar(value=200)
        ttk.Spinbox(grid_frame, from_=150, to=400, textvariable=self.slots_spacing_y_var, width=5, command=self._on_change).grid(row=1, column=3, padx=5, pady=2)
        
        ttk.Separator(parent, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Слот
        ttk.Label(parent, text="Настройки слота", font=('', 10, 'bold')).pack(anchor=tk.W, pady=5)
        
        slot_frame = ttk.Frame(parent)
        slot_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(slot_frame, text="Ширина:").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        self.slot_width_var = tk.IntVar(value=280)
        ttk.Spinbox(slot_frame, from_=200, to=400, textvariable=self.slot_width_var, width=5, command=self._on_change).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(slot_frame, text="Высота:").grid(row=0, column=2, padx=5, pady=2, sticky=tk.W)
        self.slot_height_var = tk.IntVar(value=180)
        ttk.Spinbox(slot_frame, from_=120, to=300, textvariable=self.slot_height_var, width=5, command=self._on_change).grid(row=0, column=3, padx=5, pady=2)
        
        ttk.Label(slot_frame, text="Текст пустого:").grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)
        self.slot_empty_text_var = tk.StringVar(value="Пустой слот")
        ttk.Entry(slot_frame, textvariable=self.slot_empty_text_var, width=20).grid(row=1, column=1, columnspan=3, padx=5, pady=2, sticky=tk.W)
        self.slot_empty_text_var.trace_add("write", lambda *a: self._on_change())
    
    def _create_settings_tab(self, parent):
        """Создание вкладки настроек."""
        from tkinter import ttk
        
        ttk.Label(parent, text="Экран настроек в меню паузы", font=('', 10, 'bold')).pack(anchor=tk.W, pady=5)
        
        # Заголовок
        title_frame = ttk.Frame(parent)
        title_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(title_frame, text="Заголовок:").pack(side=tk.LEFT, padx=5)
        self.settings_title_var = tk.StringVar(value="Настройки")
        ttk.Entry(title_frame, textvariable=self.settings_title_var, width=30).pack(side=tk.LEFT, padx=5)
        self.settings_title_var.trace_add("write", lambda *a: self._on_change())
        
        ttk.Separator(parent, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Слайдеры
        ttk.Label(parent, text="Слайдеры громкости", font=('', 10, 'bold')).pack(anchor=tk.W, pady=5)
        
        self.sliders_listbox = tk.Listbox(parent, height=5)
        self.sliders_listbox.pack(fill=tk.X, pady=5)
        self.sliders_listbox.bind("<<ListboxSelect>>", self._on_slider_selected)
        
        # Редактирование слайдера
        slider_edit = ttk.LabelFrame(parent, text="Редактирование слайдера", padding=10)
        slider_edit.pack(fill=tk.X, pady=5)
        
        row1 = ttk.Frame(slider_edit)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="Подпись:").pack(side=tk.LEFT, padx=5)
        self.slider_label_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.slider_label_var, width=20).pack(side=tk.LEFT, padx=5)
        self.slider_label_var.trace_add("write", lambda *a: self._on_slider_change())
        
        ttk.Label(row1, text="Настройка:").pack(side=tk.LEFT, padx=5)
        self.slider_setting_var = tk.StringVar()
        settings = ["music_volume", "sound_volume", "voice_volume"]
        ttk.Combobox(row1, textvariable=self.slider_setting_var, values=settings, state="readonly", width=15).pack(side=tk.LEFT, padx=5)
        self.slider_setting_var.trace_add("write", lambda *a: self._on_slider_change())
        
        row2 = ttk.Frame(slider_edit)
        row2.pack(fill=tk.X, pady=2)
        
        ttk.Label(row2, text="Ширина:").pack(side=tk.LEFT, padx=5)
        self.slider_width_var = tk.IntVar(value=300)
        ttk.Spinbox(row2, from_=150, to=500, textvariable=self.slider_width_var, width=6, command=self._on_slider_change).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row2, text="Значение по умолчанию:").pack(side=tk.LEFT, padx=5)
        self.slider_value_var = tk.DoubleVar(value=0.8)
        ttk.Scale(row2, from_=0, to=1, variable=self.slider_value_var, command=lambda e: self._on_slider_change()).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    
    def _create_sounds_tab(self, parent):
        """Создание вкладки звуков."""
        from tkinter import ttk
        
        ttk.Label(parent, text="Звуки меню паузы", font=('', 10, 'bold')).pack(anchor=tk.W, pady=5)
        
        sounds = [
            ("open_sound", "Звук открытия:", self._browse_open_sound),
            ("close_sound", "Звук закрытия:", self._browse_close_sound),
            ("hover_sound", "Звук наведения:", self._browse_hover_sound),
            ("click_sound", "Звук клика:", self._browse_click_sound),
        ]
        
        self.sound_vars = {}
        for sound_id, label, command in sounds:
            frame = ttk.Frame(parent)
            frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(frame, text=label, width=20).pack(side=tk.LEFT, padx=5)
            self.sound_vars[sound_id] = tk.StringVar()
            ttk.Entry(frame, textvariable=self.sound_vars[sound_id], width=40).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            ttk.Button(frame, text="Обзор", command=command).pack(side=tk.LEFT, padx=5)
            ttk.Button(frame, text="X", width=3, command=lambda s=sound_id: self._clear_sound(s)).pack(side=tk.LEFT, padx=2)
    
    def _load_config(self):
        """Загрузить конфигурацию."""
        config = self.story.pause_menu
        
        self.enabled_var.set(config.enabled)
        self.overlay_color_btn.configure(bg=config.overlay_color)
        self.overlay_alpha_var.set(config.overlay_alpha)
        
        self.panel_width_var.set(config.panel_width)
        self.panel_height_var.set(config.panel_height)
        self.panel_bg_btn.configure(bg=config.panel_bg_color[:7])
        self.panel_border_btn.configure(bg=config.panel_border_color[:7])
        
        self.title_var.set(config.title)
        self.title_size_var.set(config.title_size)
        
        # Кнопки
        self._update_buttons_list()
        
        # Сохранения
        sl = config.save_load_screen
        self.save_title_var.set(sl.title_save)
        self.load_title_var.set(sl.title_load)
        self.slots_per_page_var.set(sl.slots_per_page)
        self.total_pages_var.set(sl.total_pages)
        self.slots_spacing_x_var.set(sl.slots_spacing_x)
        self.slots_spacing_y_var.set(sl.slots_spacing_y)
        self.slot_width_var.set(sl.slot_config.width)
        self.slot_height_var.set(sl.slot_config.height)
        self.slot_empty_text_var.set(sl.slot_config.empty_text)
        
        # Настройки
        self.settings_title_var.set(config.settings_title)
        self._update_sliders_list()
        
        # Звуки
        self.sound_vars["open_sound"].set(config.open_sound)
        self.sound_vars["close_sound"].set(config.close_sound)
        self.sound_vars["hover_sound"].set(config.hover_sound)
        self.sound_vars["click_sound"].set(config.click_sound)
    
    def _update_buttons_list(self):
        """Обновить список кнопок."""
        self.buttons_listbox.delete(0, tk.END)
        for btn in self.story.pause_menu.buttons:
            self.buttons_listbox.insert(tk.END, f"{btn.text} [{btn.action}]")
    
    def _update_sliders_list(self):
        """Обновить список слайдеров."""
        self.sliders_listbox.delete(0, tk.END)
        for slider in self.story.pause_menu.settings_sliders:
            self.sliders_listbox.insert(tk.END, f"{slider.label} [{slider.setting}]")
    
    def _on_button_selected(self, event):
        """Обработка выбора кнопки."""
        sel = self.buttons_listbox.curselection()
        if not sel:
            return
        
        idx = sel[0]
        if idx < len(self.story.pause_menu.buttons):
            btn = self.story.pause_menu.buttons[idx]
            self.btn_text_var.set(btn.text)
            self.btn_action_var.set(btn.action)
            self.btn_width_var.set(btn.width)
            self.btn_height_var.set(btn.height)
            self.btn_font_var.set(btn.font_size)
            self.btn_visible_var.set(btn.visible)
            
            # Цвета
            bg_color = btn.bg_color[:7] if len(btn.bg_color) > 7 else btn.bg_color
            self.pause_btn_bg_color.config(bg=bg_color)
            hover_color = btn.hover_color[:7] if len(btn.hover_color) > 7 else btn.hover_color
            self.pause_btn_hover_color.config(bg=hover_color)
            border_color = btn.border_color[:7] if len(btn.border_color) > 7 else btn.border_color
            self.pause_btn_border_color.config(bg=border_color)
    
    def _on_button_change(self):
        """Обработка изменения кнопки."""
        sel = self.buttons_listbox.curselection()
        if not sel:
            return
        
        idx = sel[0]
        if idx < len(self.story.pause_menu.buttons):
            btn = self.story.pause_menu.buttons[idx]
            btn.text = self.btn_text_var.get()
            btn.action = self.btn_action_var.get()
            btn.width = self.btn_width_var.get()
            btn.height = self.btn_height_var.get()
            btn.font_size = self.btn_font_var.get()
            btn.visible = self.btn_visible_var.get()
            
            self._update_buttons_list()
            self.buttons_listbox.selection_set(idx)
            self._update_preview()
    
    def _add_button(self):
        """Добавить кнопку."""
        from story import PauseMenuButton
        btn_id = f"btn_custom_{len(self.story.pause_menu.buttons)}"
        new_btn = PauseMenuButton(id=btn_id, text="Новая кнопка", action="resume", y=0.5)
        self.story.pause_menu.buttons.append(new_btn)
        self._update_buttons_list()
        self._update_preview()
    
    def _choose_pause_btn_color(self, color_type: str):
        """Выбрать цвет кнопки паузы."""
        titles = {"bg": "фона", "hover": "наведения", "border": "рамки"}
        color = colorchooser.askcolor(title=f"Выберите цвет {titles.get(color_type, '')}")
        if color[1]:
            sel = self.buttons_listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            if idx >= len(self.story.pause_menu.buttons):
                return
            btn = self.story.pause_menu.buttons[idx]
            
            if color_type == "bg":
                self.pause_btn_bg_color.config(bg=color[1])
                btn.bg_color = color[1] + "CC"
            elif color_type == "hover":
                self.pause_btn_hover_color.config(bg=color[1])
                btn.hover_color = color[1] + "DD"
            elif color_type == "border":
                self.pause_btn_border_color.config(bg=color[1])
                btn.border_color = color[1]
            
            self._update_preview()
    
    def _delete_button(self):
        """Удалить кнопку."""
        sel = self.buttons_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self.story.pause_menu.buttons):
            del self.story.pause_menu.buttons[idx]
            self._update_buttons_list()
            self._update_preview()
    
    def _move_button_up(self):
        """Переместить кнопку вверх."""
        sel = self.buttons_listbox.curselection()
        if not sel or sel[0] == 0:
            return
        idx = sel[0]
        buttons = self.story.pause_menu.buttons
        buttons[idx], buttons[idx-1] = buttons[idx-1], buttons[idx]
        self._update_buttons_list()
        self.buttons_listbox.selection_set(idx-1)
        self._update_preview()
    
    def _move_button_down(self):
        """Переместить кнопку вниз."""
        sel = self.buttons_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        buttons = self.story.pause_menu.buttons
        if idx >= len(buttons) - 1:
            return
        buttons[idx], buttons[idx+1] = buttons[idx+1], buttons[idx]
        self._update_buttons_list()
        self.buttons_listbox.selection_set(idx+1)
        self._update_preview()
    
    def _on_slider_selected(self, event):
        """Обработка выбора слайдера."""
        sel = self.sliders_listbox.curselection()
        if not sel:
            return
        
        idx = sel[0]
        if idx < len(self.story.pause_menu.settings_sliders):
            slider = self.story.pause_menu.settings_sliders[idx]
            self.slider_label_var.set(slider.label)
            self.slider_setting_var.set(slider.setting)
            self.slider_width_var.set(slider.width)
            self.slider_value_var.set(slider.value)
    
    def _on_slider_change(self):
        """Обработка изменения слайдера."""
        sel = self.sliders_listbox.curselection()
        if not sel:
            return
        
        idx = sel[0]
        if idx < len(self.story.pause_menu.settings_sliders):
            slider = self.story.pause_menu.settings_sliders[idx]
            slider.label = self.slider_label_var.get()
            slider.setting = self.slider_setting_var.get()
            slider.width = self.slider_width_var.get()
            slider.value = self.slider_value_var.get()
            
            self._update_sliders_list()
            self.sliders_listbox.selection_set(idx)
            self._update_preview()
    
    def _on_change(self):
        """Обработка изменения общих настроек."""
        config = self.story.pause_menu
        
        config.enabled = self.enabled_var.get()
        config.overlay_alpha = self.overlay_alpha_var.get()
        config.panel_width = self.panel_width_var.get()
        config.panel_height = self.panel_height_var.get()
        config.title = self.title_var.get()
        config.title_size = self.title_size_var.get()
        
        # Сохранения
        sl = config.save_load_screen
        sl.title_save = self.save_title_var.get()
        sl.title_load = self.load_title_var.get()
        sl.slots_per_page = self.slots_per_page_var.get()
        sl.total_pages = self.total_pages_var.get()
        sl.slots_spacing_x = self.slots_spacing_x_var.get()
        sl.slots_spacing_y = self.slots_spacing_y_var.get()
        sl.slot_config.width = self.slot_width_var.get()
        sl.slot_config.height = self.slot_height_var.get()
        sl.slot_config.empty_text = self.slot_empty_text_var.get()
        
        config.settings_title = self.settings_title_var.get()
        
        # Звуки
        config.open_sound = self.sound_vars["open_sound"].get()
        config.close_sound = self.sound_vars["close_sound"].get()
        config.hover_sound = self.sound_vars["hover_sound"].get()
        config.click_sound = self.sound_vars["click_sound"].get()
        
        self._update_preview()
    
    def _on_screen_changed(self, event):
        """Переключение экрана превью."""
        if self.preview:
            self.preview.set_screen(self.screen_var.get())
    
    def _choose_overlay_color(self):
        """Выбор цвета затемнения."""
        color = colorchooser.askcolor(self.overlay_color_btn.cget("bg"))[1]
        if color:
            self.overlay_color_btn.configure(bg=color)
            self.story.pause_menu.overlay_color = color
            self._update_preview()
    
    def _choose_panel_bg(self):
        """Выбор цвета фона панели."""
        color = colorchooser.askcolor(self.panel_bg_btn.cget("bg"))[1]
        if color:
            self.panel_bg_btn.configure(bg=color)
            self.story.pause_menu.panel_bg_color = color + "DD"
            self._update_preview()
    
    def _choose_panel_border(self):
        """Выбор цвета рамки панели."""
        color = colorchooser.askcolor(self.panel_border_btn.cget("bg"))[1]
        if color:
            self.panel_border_btn.configure(bg=color)
            self.story.pause_menu.panel_border_color = color
            self._update_preview()
    
    def _browse_open_sound(self):
        self._browse_sound("open_sound")
    
    def _browse_close_sound(self):
        self._browse_sound("close_sound")
    
    def _browse_hover_sound(self):
        self._browse_sound("hover_sound")
    
    def _browse_click_sound(self):
        self._browse_sound("click_sound")
    
    def _browse_sound(self, sound_id):
        """Выбор звукового файла."""
        path = filedialog.askopenfilename(filetypes=[("Audio", "*.mp3 *.wav *.ogg")])
        if path:
            self.sound_vars[sound_id].set(path)
            self._on_change()
    
    def _clear_sound(self, sound_id):
        """Очистить звук."""
        self.sound_vars[sound_id].set("")
        self._on_change()
    
    def _start_preview(self):
        """Запуск превью."""
        from preview import PauseMenuPreview
        self.preview = PauseMenuPreview()
        self.preview.load_config(self.story.pause_menu)
        self.preview.on_position_changed = self._on_position_changed
        self.preview.start()
    
    def _update_preview(self):
        """Обновить превью."""
        if self.preview:
            self.preview.load_config(self.story.pause_menu)
            self.preview.refresh()
    
    def _on_position_changed(self, elem_type, elem_id, x, y):
        """Обработка изменения позиции в превью."""
        self.after(0, lambda: self._on_change())
    
    def _save(self):
        """Сохранить изменения."""
        self._on_change()
        if self.on_save:
            self.on_save()
        messagebox.showinfo("Сохранено", "Настройки меню паузы сохранены")
    
    def _reset(self):
        """Сбросить к настройкам по умолчанию."""
        from story import PauseMenuConfig
        if messagebox.askyesno("Подтверждение", "Сбросить все настройки меню паузы?"):
            self.story.pause_menu = PauseMenuConfig()
            self._load_config()
            self._update_preview()
    
    def _on_close(self):
        """Закрытие диалога."""
        if self.preview:
            self.preview.stop()
        self.destroy()


class VisualNovelEditor(tk.Tk):
    """Главное окно редактора визуальной новеллы."""
    
    def __init__(self):
        super().__init__()
        self.title("UNSRIAL ENGINE 69")
        
        # Загружаем настройки
        self.settings = load_settings()
        self.geometry(f"{self.settings.get('window_width', 1200)}x{self.settings.get('window_height', 800)}")
        
        self.story = Story()
        self.current_file: Optional[str] = None
        
        # Таймер автосохранения
        self.autosave_job = None
        
        self._create_menu()
        self._create_widgets()
        
        # Новый пустой проект при старте
        self._update_lists()
        
        # Запускаем автосохранение если включено
        self._schedule_autosave()
        
        # Сохраняем размер окна при закрытии
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_close(self):
        """Обработка закрытия окна."""
        # Сохраняем размер окна
        self.settings['window_width'] = self.winfo_width()
        self.settings['window_height'] = self.winfo_height()
        if self.current_file:
            self.settings['last_project'] = self.current_file
        save_settings(self.settings)
        self.destroy()
    
    def _schedule_autosave(self):
        """Запланировать автосохранение."""
        if self.autosave_job:
            self.after_cancel(self.autosave_job)
            self.autosave_job = None
        
        if self.settings.get('autosave_enabled', False) and self.current_file:
            interval = self.settings.get('autosave_interval', 60) * 1000  # в миллисекунды
            self.autosave_job = self.after(interval, self._autosave)
    
    def _autosave(self):
        """Выполнить автосохранение."""
        if self.current_file and self.settings.get('autosave_enabled', False):
            try:
                self.story.save(self.current_file)
                self.status_var.set(f"Автосохранено: {self.current_file}")
            except Exception:
                pass
        # Планируем следующее автосохранение
        self._schedule_autosave()
    
    def _open_settings(self):
        """Открыть окно настроек."""
        def on_save(new_settings):
            self.settings = new_settings
            save_settings(self.settings)
            self._schedule_autosave()
            self.status_var.set("Настройки сохранены")
        
        SettingsDialog(self, self.settings, on_save)
    
    def _create_menu(self):
        menubar = tk.Menu(self)
        
        # Файл
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Новый проект", command=self._new_project, accelerator="Ctrl+N")
        file_menu.add_command(label="Открыть...", command=self._open_project, accelerator="Ctrl+O")
        file_menu.add_command(label="Сохранить", command=self._save_project, accelerator="Ctrl+S")
        file_menu.add_command(label="Сохранить как...", command=self._save_project_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Запустить игру", command=self._run_game, accelerator="Ctrl+R")
        file_menu.add_separator()
        file_menu.add_command(label="Собрать в EXE...", command=self._build_game, accelerator="Ctrl+B")
        file_menu.add_command(label="Собрать и загрузить на сервер...", command=self._upload_to_server, accelerator="Ctrl+U")
        file_menu.add_command(label="Удалить с сервера...", command=self._delete_from_server)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self._on_close)
        menubar.add_cascade(label="Файл", menu=file_menu)
        
        # Редактирование
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Настройки проекта", command=self._edit_project_settings)
        edit_menu.add_command(label="Главное меню", command=self._edit_main_menu, accelerator="Ctrl+M")
        edit_menu.add_command(label="Меню паузы", command=self._edit_pause_menu, accelerator="Ctrl+P")
        edit_menu.add_separator()
        edit_menu.add_command(label="Настройки редактора", command=self._open_settings)
        menubar.add_cascade(label="Редактирование", menu=edit_menu)
        
        # Помощь
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="О программе", command=self._show_about)
        menubar.add_cascade(label="Помощь", menu=help_menu)
        
        self.config(menu=menubar)
        
        # Горячие клавиши
        def hotkey_handler(func):
            def wrapper(event):
                # Не перехватываем если фокус на текстовом поле
                widget = event.widget
                if isinstance(widget, (tk.Entry, tk.Text, ttk.Entry)):
                    return  # Пропускаем, чтобы стандартные хоткеи работали
                func()
                return "break"
            return wrapper
        
        self.bind_all('<Control-n>', hotkey_handler(self._new_project))
        self.bind_all('<Control-N>', hotkey_handler(self._new_project))
        self.bind_all('<Control-o>', hotkey_handler(self._open_project))
        self.bind_all('<Control-O>', hotkey_handler(self._open_project))
        self.bind_all('<Control-s>', hotkey_handler(self._save_project))
        self.bind_all('<Control-S>', hotkey_handler(self._save_project))
        self.bind_all('<Control-r>', hotkey_handler(self._run_game))
        self.bind_all('<Control-R>', hotkey_handler(self._run_game))
        self.bind_all('<Control-b>', hotkey_handler(self._build_game))
        self.bind_all('<Control-B>', hotkey_handler(self._build_game))
        self.bind_all('<Control-u>', hotkey_handler(self._upload_to_server))
        self.bind_all('<Control-U>', hotkey_handler(self._upload_to_server))
        self.bind_all('<Control-m>', hotkey_handler(self._edit_main_menu))
        self.bind_all('<Control-M>', hotkey_handler(self._edit_main_menu))
        self.bind_all('<Control-p>', hotkey_handler(self._edit_pause_menu))
        self.bind_all('<Control-P>', hotkey_handler(self._edit_pause_menu))
    
    def _create_widgets(self):
        # Основной контейнер
        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Левая панель - списки
        left_frame = ttk.Frame(main_paned, width=300)
        main_paned.add(left_frame, weight=1)
        
        # Персонажи
        chars_frame = ttk.LabelFrame(left_frame, text="Персонажи", padding=5)
        chars_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.chars_listbox = tk.Listbox(chars_frame)
        self.chars_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        chars_scroll = ttk.Scrollbar(chars_frame, orient=tk.VERTICAL, command=self.chars_listbox.yview)
        chars_scroll.pack(side=tk.LEFT, fill=tk.Y)
        self.chars_listbox.config(yscrollcommand=chars_scroll.set)
        
        chars_buttons = ttk.Frame(chars_frame)
        chars_buttons.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(chars_buttons, text="+", width=3, command=self._add_character).pack(pady=2)
        ttk.Button(chars_buttons, text="✎", width=3, command=self._edit_character).pack(pady=2)
        ttk.Button(chars_buttons, text="−", width=3, command=self._remove_character).pack(pady=2)
        
        # Сцены
        scenes_frame = ttk.LabelFrame(left_frame, text="Сцены", padding=5)
        scenes_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.scenes_listbox = tk.Listbox(scenes_frame)
        self.scenes_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scenes_listbox.bind('<<ListboxSelect>>', self._on_scene_selected)
        
        scenes_scroll = ttk.Scrollbar(scenes_frame, orient=tk.VERTICAL, command=self.scenes_listbox.yview)
        scenes_scroll.pack(side=tk.LEFT, fill=tk.Y)
        self.scenes_listbox.config(yscrollcommand=scenes_scroll.set)
        
        scenes_buttons = ttk.Frame(scenes_frame)
        scenes_buttons.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(scenes_buttons, text="+", width=3, command=self._add_scene).pack(pady=2)
        ttk.Button(scenes_buttons, text="⧉", width=3, command=self._copy_scene).pack(pady=2)
        ttk.Button(scenes_buttons, text="−", width=3, command=self._remove_scene).pack(pady=2)
        ttk.Button(scenes_buttons, text="★", width=3, command=self._set_start_scene).pack(pady=2)
        
        # Правая панель - редактор сцены
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=3)
        
        self.scene_editor = SceneEditor(right_frame, self.story, self._on_story_changed)
        self.scene_editor.pack(fill=tk.BOTH, expand=True)
        
        # Статус бар
        self.status_var = tk.StringVar(value="Готово")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
    
    def _update_lists(self):
        """Обновить списки персонажей и сцен."""
        # Персонажи
        self.chars_listbox.delete(0, tk.END)
        for char in self.story.characters.values():
            self.chars_listbox.insert(tk.END, f"{char.id} - {char.name}")
        
        # Сцены
        self.scenes_listbox.delete(0, tk.END)
        for scene in self.story.scenes.values():
            prefix = "★ " if scene.id == self.story.start_scene_id else "  "
            self.scenes_listbox.insert(tk.END, f"{prefix}{scene.id} - {scene.name}")
    
    def _on_story_changed(self):
        """Вызывается при изменении истории."""
        self._update_lists()
        self.status_var.set("Изменения не сохранены")
    
    def _on_scene_selected(self, event):
        """Обработка выбора сцены."""
        selection = self.scenes_listbox.curselection()
        if selection:
            scene_id = list(self.story.scenes.keys())[selection[0]]
            scene = self.story.get_scene(scene_id)
            if scene:
                self.scene_editor.story = self.story
                self.scene_editor.load_scene(scene)
    
    def _add_character(self):
        def on_save(character: Character):
            self.story.add_character(character)
            self._update_lists()
        
        CharacterEditor(self, on_save=on_save)
    
    def _edit_character(self):
        selection = self.chars_listbox.curselection()
        if not selection:
            return
        
        char_id = list(self.story.characters.keys())[selection[0]]
        character = self.story.get_character(char_id)
        
        def on_save(updated_char: Character):
            self.story.characters[char_id] = updated_char
            self._update_lists()
        
        CharacterEditor(self, character, on_save)
    
    def _remove_character(self):
        selection = self.chars_listbox.curselection()
        if selection:
            char_id = list(self.story.characters.keys())[selection[0]]
            if messagebox.askyesno("Подтверждение", f"Удалить персонажа '{char_id}'?"):
                del self.story.characters[char_id]
                self._update_lists()
    
    def _add_scene(self):
        # Создаём новую сцену с уникальным ID
        base_id = "scene"
        counter = 1
        while f"{base_id}_{counter}" in self.story.scenes:
            counter += 1
        
        scene = Scene(id=f"{base_id}_{counter}", name=f"Сцена {counter}")
        self.story.add_scene(scene)
        self._update_lists()
        
        # Выбираем новую сцену
        self.scenes_listbox.selection_clear(0, tk.END)
        self.scenes_listbox.selection_set(tk.END)
        self._on_scene_selected(None)
    
    def _copy_scene(self):
        """Копировать выбранную сцену."""
        selection = self.scenes_listbox.curselection()
        if not selection:
            messagebox.showinfo("Копирование", "Сначала выберите сцену для копирования")
            return
        
        scene_id = list(self.story.scenes.keys())[selection[0]]
        original_scene = self.story.get_scene(scene_id)
        if not original_scene:
            return
        
        # Создаём уникальный ID для копии
        base_id = f"{scene_id}_copy"
        counter = 1
        new_id = base_id
        while new_id in self.story.scenes:
            new_id = f"{base_id}_{counter}"
            counter += 1
        
        # Создаём копию сцены
        import copy
        new_scene = Scene(
            id=new_id,
            name=f"{original_scene.name} (копия)",
            background=original_scene.background,
            background_color=original_scene.background_color,
            dialogs=copy.deepcopy(original_scene.dialogs),
            characters_on_screen=copy.deepcopy(original_scene.characters_on_screen),
            images_on_screen=copy.deepcopy(original_scene.images_on_screen),
            texts_on_screen=copy.deepcopy(original_scene.texts_on_screen),
            choices=copy.deepcopy(original_scene.choices),
            next_scene_id=original_scene.next_scene_id,
            music=original_scene.music
        )
        
        self.story.add_scene(new_scene)
        self._update_lists()
        
        # Выбираем новую сцену
        self.scenes_listbox.selection_clear(0, tk.END)
        self.scenes_listbox.selection_set(tk.END)
        self._on_scene_selected(None)
        
        self.status_var.set(f"Создана копия сцены: {new_id}")
    
    def _remove_scene(self):
        selection = self.scenes_listbox.curselection()
        if selection:
            scene_id = list(self.story.scenes.keys())[selection[0]]
            if messagebox.askyesno("Подтверждение", f"Удалить сцену '{scene_id}'?"):
                del self.story.scenes[scene_id]
                if self.story.start_scene_id == scene_id:
                    self.story.start_scene_id = list(self.story.scenes.keys())[0] if self.story.scenes else ""
                self._update_lists()
    
    def _set_start_scene(self):
        """Установить выбранную сцену как стартовую."""
        selection = self.scenes_listbox.curselection()
        if selection:
            scene_id = list(self.story.scenes.keys())[selection[0]]
            self.story.start_scene_id = scene_id
            self._update_lists()
            self.status_var.set(f"Стартовая сцена: {scene_id}")
    
    def _new_project(self):
        """Создать новый проект и сразу предложить сохранить."""
        if messagebox.askyesno("Новый проект", "Создать новый проект? Несохранённые изменения будут потеряны."):
            self.story = Story()
            self.scene_editor.story = self.story
            self._update_lists()
            
            # Сразу предлагаем сохранить
            projects_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "projects")
            os.makedirs(projects_dir, exist_ok=True)
            
            dialog = ProjectSelectDialog(self, projects_dir, mode="save")
            self.wait_window(dialog)
            
            if dialog.result:
                try:
                    self.story.save(dialog.result)
                    self.current_file = dialog.result
                    self.status_var.set(f"Создан: {os.path.basename(dialog.result)}")
                    self._schedule_autosave()
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{e}")
                    self.current_file = None
            else:
                self.current_file = None
                self.status_var.set("Новый проект (не сохранён)")
    
    def _open_project(self):
        projects_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "projects")
        os.makedirs(projects_dir, exist_ok=True)
        
        dialog = ProjectSelectDialog(self, projects_dir, mode="open")
        self.wait_window(dialog)
        
        if dialog.result:
            try:
                self.story = Story.load(dialog.result)
                self.current_file = dialog.result
                self.scene_editor.story = self.story
                self._update_lists()
                self.status_var.set(f"Открыт: {os.path.basename(dialog.result)}")
                # Запускаем автосохранение
                self._schedule_autosave()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{e}")
    
    def open_project_file(self, file_path: str):
        """Открыть проект по указанному пути (публичный метод для внешнего вызова)."""
        if not file_path or not os.path.exists(file_path):
            return
        try:
            self.story = Story.load(file_path)
            self.current_file = file_path
            self.scene_editor.story = self.story
            self._update_lists()
            self.status_var.set(f"Открыт: {os.path.basename(file_path)}")
            self._schedule_autosave()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{e}")
    
    def _save_project(self):
        if self.current_file:
            try:
                self.story.save(self.current_file)
                self.status_var.set(f"Сохранено: {os.path.basename(self.current_file)}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{e}")
        else:
            self._save_project_as()
    
    def _save_project_as(self):
        projects_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "projects")
        os.makedirs(projects_dir, exist_ok=True)
        
        dialog = ProjectSelectDialog(self, projects_dir, mode="save")
        self.wait_window(dialog)
        
        if dialog.result:
            try:
                self.story.save(dialog.result)
                self.current_file = dialog.result
                self.status_var.set(f"Сохранено: {os.path.basename(dialog.result)}")
                # Запускаем автосохранение если не было
                self._schedule_autosave()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{e}")
    
    def _run_game(self):
        """Запустить игру с текущей историей."""
        # Сохраняем во временный файл
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(self.story.to_dict(), f, ensure_ascii=False, indent=2)
            temp_file = f.name
        
        # Запускаем игру в отдельном процессе
        import subprocess
        import sys
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        engine_path = os.path.join(script_dir, "engine.py")
        
        # Создаём временный скрипт запуска (с debug_mode=True)
        run_script = f'''
import sys
sys.path.insert(0, r"{script_dir}")
from engine import VisualNovelEngine
from story import Story

engine = VisualNovelEngine(1280, 720, "{self.story.title}", debug_mode=True)
story = Story.load(r"{temp_file}")
engine.load_story(story)
engine.run()

import os
os.remove(r"{temp_file}")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(run_script)
            run_file = f.name
        
        subprocess.Popen([sys.executable, run_file])
        self.status_var.set("Игра запущена")
    
    def _edit_main_menu(self, event=None):
        """Редактировать главное меню."""
        MenuEditorDialog(self, self.story, self._on_story_changed)
    
    def _edit_pause_menu(self, event=None):
        """Редактировать меню паузы."""
        PauseMenuEditorDialog(self, self.story, self._on_story_changed)
    
    def _edit_project_settings(self):
        """Редактировать настройки проекта."""
        dialog = tk.Toplevel(self)
        dialog.title("Настройки проекта")
        dialog.geometry("500x400")
        dialog.transient(self)
        dialog.grab_set()
        
        # Основные настройки
        ttk.Label(dialog, text="Название:").grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        title_entry = ttk.Entry(dialog, width=40)
        title_entry.insert(0, self.story.title)
        title_entry.grid(row=0, column=1, columnspan=2, padx=10, pady=5)
        
        ttk.Label(dialog, text="Автор:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        author_entry = ttk.Entry(dialog, width=40)
        author_entry.insert(0, self.story.author)
        author_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=5)
        
        ttk.Label(dialog, text="Версия:").grid(row=2, column=0, padx=10, pady=5, sticky=tk.W)
        version_entry = ttk.Entry(dialog, width=40)
        version_entry.insert(0, self.story.version)
        version_entry.grid(row=2, column=1, columnspan=2, padx=10, pady=5)
        
        # Разделитель
        ttk.Separator(dialog, orient='horizontal').grid(row=3, column=0, columnspan=3, sticky='ew', pady=10)
        ttk.Label(dialog, text="Цвета панели диалога:", font=('', 10, 'bold')).grid(row=4, column=0, columnspan=3, padx=10, pady=5, sticky=tk.W)
        
        # Цвет фона панели
        dialog_bg = self.story.dialog_bg_color[:7] if len(self.story.dialog_bg_color) > 7 else self.story.dialog_bg_color
        ttk.Label(dialog, text="Фон панели:").grid(row=5, column=0, padx=10, pady=5, sticky=tk.W)
        bg_color_frame = tk.Frame(dialog, width=100, height=25, bg=dialog_bg)
        bg_color_frame.grid(row=5, column=1, sticky=tk.W, padx=10, pady=5)
        
        def choose_bg_color():
            color = colorchooser.askcolor(dialog_bg, title="Цвет фона панели")[1]
            if color:
                self.story.dialog_bg_color = color + "90"  # Добавляем альфа
                bg_color_frame.config(bg=color)
        
        ttk.Button(dialog, text="Выбрать", command=choose_bg_color).grid(row=5, column=2, padx=5, pady=5)
        
        # Цвет рамки панели
        ttk.Label(dialog, text="Рамка панели:").grid(row=6, column=0, padx=10, pady=5, sticky=tk.W)
        border_color_frame = tk.Frame(dialog, width=100, height=25, bg=self.story.dialog_border_color)
        border_color_frame.grid(row=6, column=1, sticky=tk.W, padx=10, pady=5)
        
        def choose_border_color():
            color = colorchooser.askcolor(self.story.dialog_border_color, title="Цвет рамки")[1]
            if color:
                self.story.dialog_border_color = color
                border_color_frame.config(bg=color)
        
        ttk.Button(dialog, text="Выбрать", command=choose_border_color).grid(row=6, column=2, padx=5, pady=5)
        
        # Цвет текста
        ttk.Label(dialog, text="Цвет текста:").grid(row=7, column=0, padx=10, pady=5, sticky=tk.W)
        text_color_frame = tk.Frame(dialog, width=100, height=25, bg=self.story.dialog_text_color)
        text_color_frame.grid(row=7, column=1, sticky=tk.W, padx=10, pady=5)
        
        def choose_text_color():
            color = colorchooser.askcolor(self.story.dialog_text_color, title="Цвет текста")[1]
            if color:
                self.story.dialog_text_color = color
                text_color_frame.config(bg=color)
        
        ttk.Button(dialog, text="Выбрать", command=choose_text_color).grid(row=7, column=2, padx=5, pady=5)
        
        def save():
            self.story.title = title_entry.get().strip()
            self.story.author = author_entry.get().strip()
            self.story.version = version_entry.get().strip()
            self.title(f"mpy - {self.story.title}")
            dialog.destroy()
        
        ttk.Button(dialog, text="Сохранить", command=save).grid(row=8, column=1, pady=20)
    
    def _show_about(self):
        messagebox.showinfo(
            "о этом ахуительнейшем движке:",
            "mpy (UNSRIAL ENGINE)\n\n"
            "renpy СОСЕТ ХУЙ\n"
            "мой движок самый ахуительнейший\n"
            "сосите хуй\n"
            "ЗАЙЧИК БЫЛ НАПИСАН НА ЭТОМ ДВИЖКЕ, НЕ НА renpy\n\n"
            "да нахуй"
        )
    
    def _build_game(self):
        """Собрать игру в EXE."""
        # Сначала сохраняем проект
        if not self.current_file:
            messagebox.showwarning(
                "Внимание", 
                "Сначала сохраните проект (Ctrl+S или Ctrl+Shift+S)"
            )
            return
        
        # Автосохраняем перед сборкой
        try:
            self.story.save(self.current_file)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить проект:\n{e}")
            return
        
        # Открываем диалог сборки
        BuildDialog(self, self.current_file, self.story.title)

    def _upload_to_server(self):
        """Собрать и загрузить игру на сервер."""
        # Сначала сохраняем проект
        if not self.current_file:
            messagebox.showwarning(
                "Внимание", 
                "Сначала сохраните проект (Ctrl+S или Ctrl+Shift+S)"
            )
            return
        
        # Автосохраняем перед загрузкой
        try:
            self.story.save(self.current_file)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить проект:\n{e}")
            return
        
        # Открываем диалог загрузки
        UploadDialog(self, self.current_file, self.story, self._on_upload_complete)

    def _on_upload_complete(self, game_id: str, version: str):
        """Callback после успешной загрузки на сервер."""
        # Обновляем данные проекта
        self.story.game_id = game_id
        self.story.server_version = version
        
        # Сохраняем проект с обновлёнными данными
        try:
            self.story.save(self.current_file)
            self.status_var.set(f"Загружено на сервер: {game_id}")
        except Exception as e:
            messagebox.showwarning("Внимание", f"Не удалось сохранить game_id в проект:\n{e}")
    
    def _delete_from_server(self):
        """Удалить игру с сервера."""
        # Проверяем, что у проекта есть game_id
        if not self.story.game_id:
            messagebox.showwarning(
                "Внимание", 
                "Этот проект не загружен на сервер.\n\n"
                "Game ID не указан."
            )
            return
        
        # Подтверждение
        game_id = self.story.game_id
        result = messagebox.askyesno(
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить игру с сервера?\n\n"
            f"Название: {self.story.title}\n"
            f"Game ID: {game_id}\n\n"
            f"Это действие необратимо!",
            icon='warning'
        )
        
        if not result:
            return
        
        # Выполняем удаление
        try:
            import client
            from hwid import get_hardware_id
            
            hwid = get_hardware_id()
            
            success = client.delete_game(
                game_id=game_id,
                hwid=hwid
            )
            
            if success:
                # Очищаем game_id в проекте
                self.story.game_id = ""
                self.story.server_version = ""
                
                # Сохраняем проект
                if self.current_file:
                    try:
                        self.story.save(self.current_file)
                    except:
                        pass
                
                messagebox.showinfo(
                    "Успех", 
                    f"Игра удалена с сервера.\n\n"
                    f"Game ID {game_id} очищен из проекта."
                )
                self.status_var.set("Игра удалена с сервера")
            else:
                messagebox.showerror(
                    "Ошибка", 
                    "Не удалось удалить игру с сервера.\n\n"
                    "Возможно, вы не являетесь её автором."
                )
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при удалении:\n{e}")


class BuildDialog(tk.Toplevel):
    """Диалог сборки игры в EXE."""
    
    def __init__(self, parent, json_path: str, game_title: str):
        super().__init__(parent)
        self.title("билд")
        self.geometry("700x650")
        self.resizable(True, True)
        
        self.json_path = json_path
        self.game_title = game_title
        self.build_thread = None
        self.is_building = False
        
        self._create_widgets()
        
        self.transient(parent)
        self.grab_set()
        
        # Обработка закрытия окна
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок
        ttk.Label(
            main_frame, 
            text="билд под exe", 
            font=('Arial', 12, 'bold')
        ).pack(anchor=tk.W)
        
        ttk.Label(
            main_frame, 
            text="создаст директорию со всеми ассетами и exe-шником игры",
            foreground='gray'
        ).pack(anchor=tk.W, pady=(0, 15))
        
        # Информация о проекте
        info_frame = ttk.LabelFrame(main_frame, text="проект", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(info_frame, text=f"название: {self.game_title}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"файл: {os.path.basename(self.json_path)}").pack(anchor=tk.W)
        
        # Выбор папки для билда
        output_frame = ttk.LabelFrame(main_frame, text="папка для билда", padding=10)
        output_frame.pack(fill=tk.X, pady=(0, 10))
        
        path_frame = ttk.Frame(output_frame)
        path_frame.pack(fill=tk.X)
        
        # По умолчанию папка build рядом с проектом
        default_output = os.path.join(
            os.path.dirname(self.json_path), 
            "build",
            self._safe_name(self.game_title)
        )
        
        self.output_var = tk.StringVar(value=default_output)
        self.output_entry = ttk.Entry(path_frame, textvariable=self.output_var, width=60)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        ttk.Button(
            path_frame, 
            text="обзор...", 
            command=self._browse_output
        ).pack(side=tk.LEFT)
        
        # Прогресс
        progress_frame = ttk.LabelFrame(main_frame, text="шо там", padding=10)
        progress_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            progress_frame, 
            variable=self.progress_var, 
            maximum=100
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = ttk.Label(progress_frame, text="готов к билду")
        self.status_label.pack(anchor=tk.W)
        
        # Лог
        log_frame = ttk.Frame(progress_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        self.log_text = tk.Text(log_frame, height=10, state=tk.DISABLED, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=log_scroll.set)
        
        # Кнопки
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.build_btn = ttk.Button(
            buttons_frame, 
            text="▶ запустить билд", 
            command=self._start_build
        )
        self.build_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.open_folder_btn = ttk.Button(
            buttons_frame, 
            text="📁 открыть билд", 
            command=self._open_output_folder,
            state=tk.DISABLED
        )
        self.open_folder_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.copy_log_btn = ttk.Button(
            buttons_frame,
            text="📋 копировать лог",
            command=self._copy_log
        )
        self.copy_log_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.close_btn = ttk.Button(
            buttons_frame, 
            text="закрыть", 
            command=self._on_close
        )
        self.close_btn.pack(side=tk.RIGHT)
    
    def _copy_log(self):
        """Копировать содержимое лога в буфер обмена."""
        log_content = self.log_text.get("1.0", tk.END).strip()
        if log_content:
            self.clipboard_clear()
            self.clipboard_append(log_content)
            self.status_label.config(text="Лог скопирован в буфер обмена")
    
    def _safe_name(self, name: str) -> str:
        """Создать безопасное имя для папки."""
        safe = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        return safe.replace(' ', '_') or "game"
    
    def _browse_output(self):
        """Выбрать папку для билда."""
        folder = filedialog.askdirectory(
            title="Выберите папку для сборки",
            initialdir=os.path.dirname(self.output_var.get())
        )
        if folder:
            # Добавляем имя игры к выбранной папке
            self.output_var.set(os.path.join(folder, self._safe_name(self.game_title)))
    
    def _log(self, message: str):
        """Добавить сообщение в лог."""
        self._pending_log_message = message
        self.after(0, self._do_log_update)
    
    def _do_log_update(self):
        """Выполнить обновление лога в главном потоке."""
        msg = getattr(self, '_pending_log_message', '')
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def _update_progress(self, value: int):
        """Обновить прогресс."""
        self._pending_progress_value = value
        self.after(0, self._do_progress_update)
    
    def _do_progress_update(self):
        """Выполнить обновление прогресса в главном потоке."""
        value = getattr(self, '_pending_progress_value', 0)
        self.progress_var.set(value)
        if value < 100:
            self.status_label.config(text=f"Сборка... {value}%")
        else:
            self.status_label.config(text="Сборка завершена!")
        self.update_idletasks()  # Принудительное обновление UI
    
    def _start_build(self):
        """Начать сборку."""
        if self.is_building:
            return
        
        output_dir = self.output_var.get().strip()
        if not output_dir:
            messagebox.showwarning("Внимание", "Укажите папку для сборки")
            return
        
        # Предупреждение о перезаписи
        if os.path.exists(output_dir) and os.listdir(output_dir):
            if not messagebox.askyesno(
                "Подтверждение", 
                f"Папка '{output_dir}' не пуста.\nПерезаписать содержимое?"
            ):
                return
        
        # Блокируем UI
        self.is_building = True
        self.build_btn.config(state=tk.DISABLED)
        self.output_entry.config(state=tk.DISABLED)
        self.close_btn.config(text="Отмена")
        
        # Очищаем лог
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        # Запускаем сборку в отдельном потоке
        self.build_thread = threading.Thread(
            target=self._build_thread,
            args=(output_dir,),
            daemon=True
        )
        self.build_thread.start()
    
    def _build_thread(self, output_dir: str):
        """Поток сборки."""
        try:
            from builder import build_game
            
            success = build_game(
                self.json_path,
                output_dir,
                self.game_title,
                progress_callback=self._update_progress,
                log_callback=self._log
            )
            
            # Обновляем UI в главном потоке
            self._build_success = success
            self._build_output_dir = output_dir
            self.after(0, self._do_build_finish)
            
        except Exception as e:
            self._build_error = str(e)
            self.after(0, self._do_build_error)
    
    def _do_build_finish(self):
        """Завершение сборки в главном потоке."""
        self.is_building = False
        self.build_btn.config(state=tk.NORMAL)
        self.output_entry.config(state=tk.NORMAL)
        self.close_btn.config(text="Закрыть")
        
        if getattr(self, '_build_success', False):
            self.open_folder_btn.config(state=tk.NORMAL)
            messagebox.showinfo(
                "Успех", 
                f"билд успешно собран, директория: {getattr(self, '_build_output_dir', '')}"
            )
        else:
            messagebox.showerror(
                "Ошибка", 
                "билд вышел с ошибкой. чек консоль или лог"
            )
    
    def _do_build_error(self):
        """Обработка ошибки сборки в главном потоке."""
        self.is_building = False
        self.build_btn.config(state=tk.NORMAL)
        self.output_entry.config(state=tk.NORMAL)
        self.close_btn.config(text="закрыть")
        error_msg = getattr(self, '_build_error', 'Unknown error')
        self._log(f"КРИТИЧЕСКАЯ ОШИБКА: {error_msg}")
        messagebox.showerror("Ошибка", f"еррор какой то ебнутый:\n{error_msg}")
    
    def _open_output_folder(self):
        """Открыть папку с билдом."""
        output_dir = self.output_var.get().strip()
        if os.path.exists(output_dir):
            os.startfile(output_dir)
    
    def _on_close(self):
        """Закрытие окна."""
        if self.is_building:
            if messagebox.askyesno(
                "точно?", 
                "билд ещё идёт. прервать?"
            ):
                # Просто закрываем - поток daemon и завершится сам
                self.destroy()
        else:
            self.destroy()


class UploadDialog(tk.Toplevel):
    """Диалог загрузки игры на сервер."""
    
    def __init__(self, parent, json_path: str, story, on_complete_callback=None):
        super().__init__(parent)
        self.title("Загрузка на сервер")
        self.geometry("700x750")
        self.resizable(True, True)
        
        self.json_path = json_path
        self.story = story
        self.on_complete_callback = on_complete_callback
        self.upload_thread = None
        self.is_uploading = False
        self.temp_zip_path = None
        
        self._create_widgets()
        
        self.transient(parent)
        self.grab_set()
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок
        ttk.Label(
            main_frame, 
            text="Загрузка игры на сервер", 
            font=('Arial', 12, 'bold')
        ).pack(anchor=tk.W)
        
        ttk.Label(
            main_frame, 
            text="Игра будет собрана в ZIP и загружена в библиотеку",
            foreground='gray'
        ).pack(anchor=tk.W, pady=(0, 15))
        
        # Информация о проекте
        info_frame = ttk.LabelFrame(main_frame, text="Информация об игре", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Название
        name_frame = ttk.Frame(info_frame)
        name_frame.pack(fill=tk.X, pady=2)
        ttk.Label(name_frame, text="Название:", width=15).pack(side=tk.LEFT)
        self.name_var = tk.StringVar(value=self.story.title or "")
        ttk.Entry(name_frame, textvariable=self.name_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Версия
        version_frame = ttk.Frame(info_frame)
        version_frame.pack(fill=tk.X, pady=2)
        ttk.Label(version_frame, text="Версия:", width=15).pack(side=tk.LEFT)
        self.version_var = tk.StringVar(value=self.story.version or "1.0")
        ttk.Entry(version_frame, textvariable=self.version_var, width=20).pack(side=tk.LEFT)
        
        # Автор
        author_frame = ttk.Frame(info_frame)
        author_frame.pack(fill=tk.X, pady=2)
        ttk.Label(author_frame, text="Автор:", width=15).pack(side=tk.LEFT)
        self.author_var = tk.StringVar(value=self.story.author or "")
        ttk.Entry(author_frame, textvariable=self.author_var, width=30).pack(side=tk.LEFT)
        
        # Описание
        desc_frame = ttk.Frame(info_frame)
        desc_frame.pack(fill=tk.X, pady=2)
        ttk.Label(desc_frame, text="Описание:", width=15).pack(side=tk.LEFT, anchor=tk.N)
        self.desc_text = tk.Text(desc_frame, height=4, width=50)
        self.desc_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.desc_text.insert('1.0', self.story.description or "")
        
        # Показываем game_id и fork info если есть
        if self.story.game_id:
            ttk.Label(info_frame, text=f"Game ID: {self.story.game_id}", foreground='blue').pack(anchor=tk.W, pady=(5, 0))
            ttk.Label(info_frame, text="(Обновление существующей игры)", foreground='gray').pack(anchor=tk.W)
        
        if self.story.forked_from:
            ttk.Label(info_frame, text=f"Форк игры: {self.story.forked_from}", foreground='green').pack(anchor=tk.W, pady=(5, 0))
        
        # Информация о сервере (URL берётся из client.get_server_url())
        server_frame = ttk.LabelFrame(main_frame, text="Сервер", padding=10)
        server_frame.pack(fill=tk.X, pady=(0, 10))
        
        try:
            import client
            server_url = client.get_server_url()
        except:
            server_url = "https://mpy.mc-c0rp.xyz"
        
        ttk.Label(server_frame, text=f"Сервер: {server_url}").pack(anchor=tk.W)
        ttk.Label(server_frame, text="(настраивается в лаунчере или через MPY_SERVER_URL)", 
                 foreground='gray').pack(anchor=tk.W)
        
        # Опции
        options_frame = ttk.LabelFrame(main_frame, text="Опции", padding=10)
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.include_exe_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Включить EXE для Windows", 
                       variable=self.include_exe_var).pack(anchor=tk.W)
        
        ttk.Label(options_frame, text="(EXE сборка занимает больше времени)", 
                 foreground='gray').pack(anchor=tk.W, padx=(20, 0))
        
        # Прогресс
        progress_frame = ttk.LabelFrame(main_frame, text="Прогресс", padding=10)
        progress_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = ttk.Label(progress_frame, text="Готово к загрузке")
        self.status_label.pack(anchor=tk.W)
        
        # Лог
        log_frame = ttk.Frame(progress_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        self.log_text = tk.Text(log_frame, height=8, state=tk.DISABLED, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=log_scroll.set)
        
        # Кнопки
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.upload_btn = ttk.Button(buttons_frame, text="▶ Собрать и загрузить", command=self._start_upload)
        self.upload_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.copy_log_btn = ttk.Button(buttons_frame, text="📋 Копировать лог", command=self._copy_log)
        self.copy_log_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.close_btn = ttk.Button(buttons_frame, text="Закрыть", command=self._on_close)
        self.close_btn.pack(side=tk.RIGHT)
    
    def _copy_log(self):
        """Копировать содержимое лога в буфер обмена."""
        log_content = self.log_text.get("1.0", tk.END).strip()
        if log_content:
            self.clipboard_clear()
            self.clipboard_append(log_content)
            self.status_label.config(text="Лог скопирован в буфер обмена")
    
    def _log(self, message: str):
        """Добавить сообщение в лог."""
        self._pending_log_message = message
        self.after(0, self._do_log_update)
    
    def _do_log_update(self):
        """Выполнить обновление лога в главном потоке."""
        msg = getattr(self, '_pending_log_message', '')
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.update_idletasks()  # Принудительное обновление UI
    
    def _update_progress(self, value: int):
        """Обновить прогресс."""
        self._pending_progress_value = value
        self.after(0, self._do_progress_update)
    
    def _do_progress_update(self):
        """Выполнить обновление прогресса в главном потоке."""
        value = getattr(self, '_pending_progress_value', 0)
        self.progress_var.set(value)
        if value < 100:
            self.status_label.config(text=f"Загрузка... {value}%")
        self.update_idletasks()  # Принудительное обновление UI
    
    def _start_upload(self):
        """Начать сборку и загрузку."""
        if self.is_uploading:
            return
        
        # Валидация
        name = self.name_var.get().strip()
        version = self.version_var.get().strip()
        
        if not name:
            messagebox.showwarning("Внимание", "Укажите название игры")
            return
        
        if not version:
            messagebox.showwarning("Внимание", "Укажите версию")
            return
        
        # Блокируем UI
        self.is_uploading = True
        self.upload_btn.config(state=tk.DISABLED)
        self.close_btn.config(text="Отмена")
        
        # Очищаем лог
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        # Запускаем в отдельном потоке
        self.upload_thread = threading.Thread(target=self._upload_thread, daemon=True)
        self.upload_thread.start()
    
    def _upload_thread(self):
        """Поток загрузки."""
        import tempfile
        import os
        
        try:
            # Получаем данные
            name = self.name_var.get().strip()
            version = self.version_var.get().strip()
            author = self.author_var.get().strip()
            description = self.desc_text.get('1.0', tk.END).strip()
            include_exe = self.include_exe_var.get()
            
            # Импортируем необходимые модули
            from builder import build_for_upload
            from hwid import get_hardware_id
            import client
            
            hwid = get_hardware_id()
            
            # Создаём временный файл для ZIP
            fd, self.temp_zip_path = tempfile.mkstemp(suffix='.zip')
            os.close(fd)
            
            self._log("Начинаем сборку...")
            
            # Собираем ZIP
            success, error_msg, thumbnail_bytes = build_for_upload(
                self.json_path,
                self.temp_zip_path,
                include_exe=include_exe,
                progress_callback=lambda v: self._update_progress(int(v * 0.7)),  # 0-70%
                log_callback=self._log
            )
            
            if not success:
                raise Exception(f"Ошибка сборки: {error_msg}")
            
            self._log("")
            self._log("Загрузка на сервер...")
            self._update_progress(75)
            
            # Callback для прогресса загрузки (75-100%)
            def upload_progress(uploaded, total):
                if total > 0:
                    upload_pct = int(uploaded * 100 / total)
                    overall_pct = 75 + int(upload_pct * 0.25)  # 75-100%
                    self._update_progress(overall_pct)
            
            # Загружаем на сервер
            game_id = client.upload_game(
                zip_path=self.temp_zip_path,
                name=name,
                version=version,
                description=description,
                author=author,
                hwid=hwid,
                game_id=self.story.game_id or None,
                forked_from=self.story.forked_from,
                thumbnail_path=None,  # Thumbnail уже в ZIP
                progress_callback=upload_progress,
                log_callback=self._log
            )
            
            if not game_id:
                raise Exception("Сервер не вернул game_id")
            
            self._update_progress(100)
            self._log("")
            self._log(f"✓ Успешно загружено!")
            self._log(f"  Game ID: {game_id}")
            
            # Обновляем UI
            self._upload_game_id = game_id
            self._upload_version = version
            self.after(0, self._do_upload_finish)
            
        except Exception as e:
            import traceback
            self._log(f"ОШИБКА: {e}")
            self._log(traceback.format_exc())
            
            self._upload_error = str(e)
            self.after(0, self._do_upload_error)
    
    def _do_upload_finish(self):
        """Завершение загрузки в главном потоке."""
        self.is_uploading = False
        self.upload_btn.config(state=tk.NORMAL)
        self.close_btn.config(text="Закрыть")
        self.status_label.config(text="Загрузка завершена!")
        
        game_id = getattr(self, '_upload_game_id', '')
        version = getattr(self, '_upload_version', '')
        
        # Callback для обновления story
        if self.on_complete_callback:
            self.on_complete_callback(game_id, version)
        
        # Удаляем временный файл при успехе
        self._cleanup_temp_file()
        
        messagebox.showinfo("Успех", f"Игра загружена на сервер!\n\nGame ID: {game_id}")
    
    def _do_upload_error(self):
        """Обработка ошибки загрузки в главном потоке."""
        self.is_uploading = False
        self.upload_btn.config(state=tk.NORMAL)
        self.close_btn.config(text="Закрыть")
        self.status_label.config(text="Ошибка загрузки")
        error_msg = getattr(self, '_upload_error', 'Unknown error')
        messagebox.showerror("Ошибка", f"Не удалось загрузить игру:\n{error_msg}")
        # Удаляем временный файл при ошибке
        self._cleanup_temp_file()
    
    def _cleanup_temp_file(self):
        """Удалить временный ZIP файл."""
        import os
        if self.temp_zip_path and os.path.exists(self.temp_zip_path):
            try:
                os.remove(self.temp_zip_path)
            except:
                pass
        self.temp_zip_path = None
    
    def _on_close(self):
        """Закрытие окна."""
        if self.is_uploading:
            if messagebox.askyesno("Подтверждение", "Загрузка ещё идёт. Прервать?"):
                self.destroy()
        else:
            self.destroy()


def main():
    app = VisualNovelEditor()
    app.mainloop()


if __name__ == "__main__":
    main()
