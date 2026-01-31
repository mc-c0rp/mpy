"""
GUI Launcher for the Visual Novel Engine.
Provides a graphical interface to:
- Browse and download games from the library
- Launch the editor
- Play local game files
"""

import os
import sys
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from typing import Optional, Callable
from pathlib import Path
import platform

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hwid import get_hardware_id
import client


# Try to import PIL for image handling
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class ServerConfigDialog(tk.Toplevel):
    """Dialog for configuring server URL."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Настройки сервера")
        self.geometry("400x150")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 150) // 2
        self.geometry(f"+{x}+{y}")
        
        self.result = None
        self._create_widgets()
        
    def _create_widgets(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill='both', expand=True)
        
        ttk.Label(frame, text="URL сервера:").pack(anchor='w')
        
        self.url_var = tk.StringVar(value=client.get_server_url())
        self.url_entry = ttk.Entry(frame, textvariable=self.url_var, width=50)
        self.url_entry.pack(fill='x', pady=(5, 15))
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')
        
        ttk.Button(btn_frame, text="Сохранить", command=self._save).pack(side='right', padx=(5, 0))
        ttk.Button(btn_frame, text="Отмена", command=self.destroy).pack(side='right')
        
    def _save(self):
        url = self.url_var.get().strip()
        if url:
            client.set_server_url(url)
            self.result = url
        self.destroy()


class GameCard(ttk.Frame):
    """A card widget displaying game info in the library."""
    
    def __init__(self, parent, game_info: dict, on_download: Callable, on_play: Callable, 
                 on_update: Callable, on_fork: Callable, on_delete: Callable, hwid: str):
        super().__init__(parent, relief='solid', borderwidth=1)
        
        self.game_info = game_info
        self.game_id = game_info['game_id']
        self.on_download = on_download
        self.on_play = on_play
        self.on_update = on_update
        self.on_fork = on_fork
        self.on_delete = on_delete
        self.hwid = hwid
        
        self._create_widgets()
        self._load_thumbnail()
        
    def _create_widgets(self):
        # Main container
        self.configure(padding=10)
        
        # Thumbnail placeholder
        self.thumb_label = ttk.Label(self, text="[Нет изображения]", 
                                      anchor='center', width=30)
        self.thumb_label.pack(pady=(0, 10))
        
        # Game name
        name = self.game_info.get('name', 'Unknown')
        ttk.Label(self, text=name, font=('TkDefaultFont', 11, 'bold'),
                  wraplength=200).pack()
        
        # Version
        version = self.game_info.get('version', '?')
        ttk.Label(self, text=f"v{version}", foreground='gray').pack()
        
        # Description (truncated)
        desc = self.game_info.get('description', '')
        if len(desc) > 100:
            desc = desc[:97] + '...'
        if desc:
            ttk.Label(self, text=desc, wraplength=200, foreground='gray').pack(pady=(5, 0))
        
        # Fork info
        forked_from = self.game_info.get('forked_from')
        if forked_from:
            ttk.Label(self, text=f"Форк: {forked_from[:8]}...", 
                      foreground='blue').pack(pady=(5, 0))
        
        # Downloads count
        downloads = self.game_info.get('downloads', 0)
        ttk.Label(self, text=f"Скачиваний: {downloads}", foreground='gray').pack(pady=(5, 0))
        
        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=(10, 0), fill='x')
        
        # Check if installed
        is_installed = client.is_game_installed(self.game_id)
        installed_version = client.get_installed_version(self.game_id)
        
        if is_installed:
            # Check for updates
            has_update = installed_version != self.game_info.get('version')
            
            play_btn = ttk.Button(btn_frame, text="Играть", 
                                  command=lambda: self.on_play(self.game_id))
            play_btn.pack(side='left', padx=(0, 5))
            
            if has_update:
                update_btn = ttk.Button(btn_frame, text="Обновить",
                                       command=lambda: self.on_update(self.game_id))
                update_btn.pack(side='left', padx=(0, 5))
        else:
            download_btn = ttk.Button(btn_frame, text="Скачать",
                                     command=lambda: self.on_download(self.game_id))
            download_btn.pack(side='left', padx=(0, 5))
        
        # Fork button
        fork_btn = ttk.Button(btn_frame, text="Форк",
                             command=lambda: self.on_fork(self.game_id))
        fork_btn.pack(side='left', padx=(0, 5))
        
        # Delete button (only for author)
        # We can't check author_hwid from client, but we can try and server will reject
        if is_installed:
            delete_btn = ttk.Button(btn_frame, text="✕",
                                   command=lambda: self.on_delete(self.game_id),
                                   width=3)
            delete_btn.pack(side='right')
        
    def _load_thumbnail(self):
        """Load thumbnail in background thread."""
        def load():
            try:
                data = client.get_thumbnail(self.game_id)
                if data and HAS_PIL:
                    # Convert to PhotoImage
                    from io import BytesIO
                    img = Image.open(BytesIO(data))
                    img = img.resize((200, 112), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    
                    # Update label in main thread
                    self.after(0, lambda: self._set_thumbnail(photo))
            except Exception as e:
                print(f"Thumbnail load error: {e}")
        
        threading.Thread(target=load, daemon=True).start()
    
    def _set_thumbnail(self, photo):
        """Set thumbnail image (must be called from main thread)."""
        self.thumb_label.configure(image=photo, text='')
        self.thumb_label.image = photo  # Keep reference


class LibraryTab(ttk.Frame):
    """Tab showing the game library from the server."""
    
    def __init__(self, parent, hwid: str, status_callback: Callable):
        super().__init__(parent)
        
        self.hwid = hwid
        self.status_callback = status_callback
        self.games = []
        self.game_cards = []
        
        self._create_widgets()
        
    def _create_widgets(self):
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(toolbar, text="Обновить", command=self.refresh_games).pack(side='left')
        ttk.Button(toolbar, text="Настройки сервера", 
                  command=self._show_server_config).pack(side='left', padx=(10, 0))
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *args: self._filter_games())
        ttk.Entry(toolbar, textvariable=self.search_var, width=30).pack(side='right')
        ttk.Label(toolbar, text="Поиск:").pack(side='right', padx=(0, 5))
        
        # Scrollable game grid
        self.canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind canvas resize
        self.canvas.bind('<Configure>', self._on_canvas_resize)
        
        # Mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)
        
        scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        
        # Status label
        self.status_label = ttk.Label(self, text="Загрузка...", foreground='gray')
        self.status_label.pack(side='bottom', pady=5)
        
    def _on_canvas_resize(self, event):
        """Resize canvas frame to fill width."""
        self.canvas.itemconfig(self.canvas_frame, width=event.width)
        
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling."""
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")
            
    def _show_server_config(self):
        """Show server configuration dialog."""
        dialog = ServerConfigDialog(self.winfo_toplevel())
        self.wait_window(dialog)
        if dialog.result:
            self.refresh_games()
            
    def refresh_games(self):
        """Refresh games list from server."""
        self.status_label.configure(text="Загрузка списка игр...")
        self.status_callback("Загрузка списка игр...")
        
        def fetch():
            try:
                self.games = client.get_games_list()
                self.after(0, self._display_games)
            except Exception as e:
                error_msg = str(e)
                self.after(0, lambda msg=error_msg: self._show_error(msg))
        
        threading.Thread(target=fetch, daemon=True).start()
        
    def _show_error(self, message):
        """Show error message."""
        self.status_label.configure(text=f"Ошибка: {message}")
        self.status_callback(f"Ошибка: {message}")
        
    def _display_games(self):
        """Display games in the grid."""
        # Clear existing cards
        for card in self.game_cards:
            card.destroy()
        self.game_cards.clear()
        
        # Apply search filter
        search = self.search_var.get().lower()
        filtered = [g for g in self.games 
                   if search in g.get('name', '').lower() 
                   or search in g.get('description', '').lower()]
        
        # Create cards in grid
        cols = 3
        for i, game in enumerate(filtered):
            card = GameCard(
                self.scrollable_frame, 
                game,
                on_download=self._download_game,
                on_play=self._play_game,
                on_update=self._update_game,
                on_fork=self._fork_game,
                on_delete=self._delete_game,
                hwid=self.hwid
            )
            row, col = divmod(i, cols)
            card.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')
            self.game_cards.append(card)
        
        # Configure grid weights
        for i in range(cols):
            self.scrollable_frame.columnconfigure(i, weight=1)
            
        self.status_label.configure(text=f"Найдено игр: {len(filtered)}")
        self.status_callback(f"Загружено игр: {len(filtered)}")
        
    def _filter_games(self):
        """Filter displayed games based on search."""
        self._display_games()
        
    def _download_game(self, game_id: str):
        """Download a game."""
        self.status_callback(f"Скачивание игры {game_id}...")
        
        def download():
            def log(msg):
                self.after(0, lambda: self.status_callback(msg))
            
            success = client.download_game(game_id, log_callback=log)
            if success:
                self.after(0, self.refresh_games)
                self.after(0, lambda: messagebox.showinfo("Успех", "Игра скачана!"))
            else:
                self.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось скачать игру"))
        
        threading.Thread(target=download, daemon=True).start()
        
    def _play_game(self, game_id: str):
        """Play an installed game."""
        self.status_callback(f"Запуск игры {game_id}...")
        
        def run():
            def log(msg):
                self.after(0, lambda: self.status_callback(msg))
            
            client.run_game(game_id, log_callback=log)
        
        threading.Thread(target=run, daemon=True).start()
        
    def _update_game(self, game_id: str):
        """Update an installed game."""
        self.status_callback(f"Обновление игры {game_id}...")
        
        def update():
            def log(msg):
                self.after(0, lambda: self.status_callback(msg))
            
            success = client.update_game(game_id, log_callback=log)
            if success:
                self.after(0, self.refresh_games)
                self.after(0, lambda: messagebox.showinfo("Успех", "Игра обновлена!"))
            else:
                self.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось обновить игру"))
        
        threading.Thread(target=update, daemon=True).start()
        
    def _fork_game(self, game_id: str):
        """Fork a game."""
        if not messagebox.askyesno("Форк", 
                                    "Создать форк этой игры?\n\n"
                                    "Копия будет скачана для редактирования."):
            return
        
        self.status_callback(f"Создание форка {game_id}...")
        
        def fork():
            def log(msg):
                self.after(0, lambda: self.status_callback(msg))
            
            # Create fork on server
            log("Создание форка на сервере...")
            new_game_id = client.fork_game(game_id, self.hwid)
            
            if not new_game_id:
                self.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось создать форк"))
                return
            
            # Ask where to save
            self.after(0, lambda: self._ask_fork_destination(new_game_id))
        
        threading.Thread(target=fork, daemon=True).start()
        
    def _ask_fork_destination(self, game_id: str):
        """Ask user where to save forked project."""
        dest_dir = filedialog.askdirectory(title="Выберите папку для проекта")
        if not dest_dir:
            return
        
        def download():
            def log(msg):
                self.after(0, lambda: self.status_callback(msg))
            
            success = client.download_fork_for_editing(game_id, dest_dir, log_callback=log)
            if success:
                self.after(0, lambda: messagebox.showinfo(
                    "Успех", 
                    f"Проект скачан в:\n{dest_dir}\n\n"
                    "Откройте game.json в редакторе для редактирования."
                ))
            else:
                self.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось скачать проект"))
        
        threading.Thread(target=download, daemon=True).start()
        
    def _delete_game(self, game_id: str):
        """Delete an installed game."""
        if not messagebox.askyesno("Удаление", 
                                    "Удалить установленную игру?\n\n"
                                    "Сохранения будут удалены!"):
            return
        
        if client.uninstall_game(game_id):
            self.refresh_games()
            messagebox.showinfo("Успех", "Игра удалена")
        else:
            messagebox.showerror("Ошибка", "Не удалось удалить игру")


class EditorTab(ttk.Frame):
    """Tab for launching the editor."""
    
    def __init__(self, parent, status_callback: Callable):
        super().__init__(parent)
        
        self.status_callback = status_callback
        self._create_widgets()
        
    def _create_widgets(self):
        # Center content
        center_frame = ttk.Frame(self)
        center_frame.place(relx=0.5, rely=0.5, anchor='center')
        
        ttk.Label(center_frame, text="mpy (UNSRIAL ENGINE) ахуительно",
                  font=('TkDefaultFont', 16, 'bold')).pack(pady=(0, 20))
        
        ttk.Button(center_frame, text="Новый проект", 
                  command=self._new_project, width=25).pack(pady=5)
        
        ttk.Button(center_frame, text="Открыть проект...", 
                  command=self._open_project, width=25).pack(pady=5)
        
        # Recent projects
        ttk.Label(center_frame, text="Последние проекты:",
                  font=('TkDefaultFont', 10)).pack(pady=(20, 10))
        
        self.recent_frame = ttk.Frame(center_frame)
        self.recent_frame.pack(fill='x')
        
        self._load_recent_projects()
        
    def _load_recent_projects(self):
        """Load and display recent projects."""
        # Clear existing
        for child in self.recent_frame.winfo_children():
            child.destroy()
        
        # Load from editor settings
        settings_path = os.path.join(os.path.dirname(__file__), 'editor_settings.json')
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                last_project = settings.get('last_project')
                if last_project and os.path.exists(last_project):
                    btn = ttk.Button(self.recent_frame, 
                                    text=os.path.basename(last_project),
                                    command=lambda p=last_project: self._launch_editor(p))
                    btn.pack(fill='x', pady=2)
            except:
                pass
        
        # Also show projects from projects folder
        projects_dir = os.path.join(os.path.dirname(__file__), 'projects')
        if os.path.exists(projects_dir):
            for f in os.listdir(projects_dir):
                if f.endswith('.json'):
                    path = os.path.join(projects_dir, f)
                    btn = ttk.Button(self.recent_frame,
                                    text=f,
                                    command=lambda p=path: self._launch_editor(p))
                    btn.pack(fill='x', pady=2)
                    
    def _new_project(self):
        """Create a new project."""
        self._launch_editor(None)
        
    def _open_project(self):
        """Open an existing project."""
        path = filedialog.askopenfilename(
            title="Открыть проект",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.path.join(os.path.dirname(__file__), 'projects')
        )
        if path:
            self._launch_editor(path)
            
    def _launch_editor(self, project_path: Optional[str]):
        """Launch the editor with optional project."""
        self.status_callback("Запуск редактора...")
        
        # Import and run editor
        try:
            from editor import VisualNovelEditor
            
            # Hide launcher temporarily
            root = self.winfo_toplevel()
            root.withdraw()
            
            # Create editor
            editor_window = VisualNovelEditor()
            
            if project_path:
                # Сохраняем ссылку на метод до вызова after
                open_func = editor_window.open_project_file
                editor_window.after(100, lambda: open_func(project_path))
            
            editor_window.mainloop()
            
            # Show launcher again
            root.deiconify()
            self._load_recent_projects()
            
        except Exception as e:
            self.status_callback(f"Ошибка запуска редактора: {e}")
            messagebox.showerror("Ошибка", f"Не удалось запустить редактор:\n{e}")


class LocalGameTab(ttk.Frame):
    """Tab for playing local game files."""
    
    def __init__(self, parent, status_callback: Callable):
        super().__init__(parent)
        
        self.status_callback = status_callback
        self._create_widgets()
        
    def _create_widgets(self):
        # Center content
        center_frame = ttk.Frame(self)
        center_frame.place(relx=0.5, rely=0.5, anchor='center')
        
        ttk.Label(center_frame, text="Запустить локальную игру",
                  font=('TkDefaultFont', 16, 'bold')).pack(pady=(0, 20))
        
        ttk.Button(center_frame, text="Выбрать JSON файл игры...",
                  command=self._select_game, width=30).pack(pady=5)
        
        ttk.Label(center_frame, 
                  text="Выберите .json файл проекта визуальной новеллы",
                  foreground='gray').pack(pady=(10, 0))
        
    def _select_game(self):
        """Select and run a local game file."""
        path = filedialog.askopenfilename(
            title="Выбрать игру",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.path.join(os.path.dirname(__file__), 'projects')
        )
        if path:
            self._run_game(path)
            
    def _run_game(self, json_path: str):
        """Run a game from JSON file."""
        self.status_callback(f"Запуск: {os.path.basename(json_path)}")
        
        def run():
            try:
                from engine import VisualNovelEngine
                from story import Story
                
                story = Story.load(json_path)
                
                # Create save directory next to the JSON file
                base_dir = os.path.dirname(json_path)
                save_dir = os.path.join(base_dir, 'saves')
                os.makedirs(save_dir, exist_ok=True)
                
                engine = VisualNovelEngine(1280, 720, story.title, save_dir=save_dir)
                engine.load_story(story)
                engine.run()
                
            except Exception as e:
                error_msg = str(e)
                self.after(0, lambda msg=error_msg: messagebox.showerror("Ошибка", f"Не удалось запустить игру:\n{msg}"))
                import traceback
                traceback.print_exc()
        
        # Run in separate thread to not block UI
        threading.Thread(target=run, daemon=True).start()


class LauncherApp(tk.Tk):
    """Main launcher application window."""
    
    def __init__(self):
        super().__init__()
        
        self.title("MPY Visual Novel - Лаунчер")
        self.geometry("900x650")
        self.minsize(800, 600)
        
        # Get hardware ID
        self.hwid = get_hardware_id()
        
        self._create_widgets()
        self._center_window()
        
        # Load library on start
        self.after(100, self._initial_load)
        
    def _center_window(self):
        """Center window on screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
    def _create_widgets(self):
        # Status bar
        self.status_var = tk.StringVar(value="Готово")
        status_bar = ttk.Label(self, textvariable=self.status_var, 
                               relief='sunken', anchor='w', padding=(5, 2))
        status_bar.pack(side='bottom', fill='x')
        
        # Hardware ID display
        hwid_label = ttk.Label(self, text=f"HWID: {self.hwid[:8]}...", 
                               foreground='gray')
        hwid_label.pack(side='bottom', anchor='e', padx=10)
        
        # Tab control
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Library tab
        self.library_tab = LibraryTab(self.notebook, self.hwid, self._set_status)
        self.notebook.add(self.library_tab, text="Библиотека")
        
        # Editor tab
        self.editor_tab = EditorTab(self.notebook, self._set_status)
        self.notebook.add(self.editor_tab, text="Редактор")
        
        # Local game tab
        self.local_tab = LocalGameTab(self.notebook, self._set_status)
        self.notebook.add(self.local_tab, text="Локальная игра")
        
    def _set_status(self, message: str):
        """Update status bar."""
        self.status_var.set(message)
        
    def _initial_load(self):
        """Initial load after window is shown."""
        self.library_tab.refresh_games()


def main():
    """Run the launcher application."""
    app = LauncherApp()
    app.mainloop()


if __name__ == '__main__':
    main()
