"""
Окно предпросмотра сцены с возможностью перетаскивания персонажей
и редактирования анимаций.
"""

import pygame
import threading
import queue
import os
from typing import Optional, Dict, List, Tuple, Callable, Any
from dataclasses import dataclass


@dataclass
class DraggableCharacter:
    """Персонаж который можно перетаскивать."""
    id: str
    name: str
    image: Optional[pygame.Surface] = None
    original_image: Optional[pygame.Surface] = None  # Исходное изображение для поворота
    x: float = 0.5  # Позиция 0.0 - 1.0
    y: float = 0.7
    scale: float = 1.0  # Масштаб
    alpha: float = 1.0
    rotation: float = 0.0  # Угол поворота в градусах
    flip_x: bool = False  # Отзеркаливание по горизонтали
    flip_y: bool = False  # Отзеркаливание по вертикали
    skew_x: float = 0.0  # Перспектива/наклон по X
    skew_y: float = 0.0  # Перспектива/наклон по Y
    emotion: str = "default"
    is_selected: bool = False
    is_dragging: bool = False


@dataclass
class DraggableImage:
    """Картинка которую можно перетаскивать."""
    id: str
    name: str
    path: str = ""
    image: Optional[pygame.Surface] = None
    original_image: Optional[pygame.Surface] = None
    x: float = 0.5
    y: float = 0.5
    scale: float = 1.0
    alpha: float = 1.0
    rotation: float = 0.0
    flip_x: bool = False
    flip_y: bool = False
    skew_x: float = 0.0
    skew_y: float = 0.0
    layer: int = 0  # Слой для порядка отрисовки
    is_selected: bool = False
    is_dragging: bool = False


@dataclass
class DraggableText:
    """Текст который можно перетаскивать."""
    id: str
    text: str
    x: float = 0.5
    y: float = 0.5
    font_size: int = 36
    color: Tuple[int, int, int] = (255, 255, 255)
    outline_color: Tuple[int, int, int] = (0, 0, 0)
    outline_width: int = 2
    scale: float = 1.0
    rotation: float = 0.0
    order: int = 0
    is_selected: bool = False
    is_dragging: bool = False
    surface: Optional[pygame.Surface] = None


class ScenePreview:
    """Окно предпросмотра сцены в pygame."""
    
    def __init__(self, width: int = 960, height: int = 540):
        self.width = width
        self.height = height
        self.running = False
        self.screen: Optional[pygame.Surface] = None
        
        # Состояние
        self.background: Optional[pygame.Surface] = None
        self.background_color: Optional[Tuple[int, int, int]] = None
        self.characters: Dict[str, DraggableCharacter] = {}
        self.images: Dict[str, DraggableImage] = {}  # Картинки на сцене
        self.texts: Dict[str, DraggableText] = {}  # Тексты на сцене
        self.selected_character: Optional[str] = None
        self.selected_image: Optional[str] = None  # Выбранная картинка
        self.selected_text: Optional[str] = None  # Выбранный текст
        self.drag_offset = (0, 0)
        
        # Анимации
        self.is_recording = False
        self.recording_target: Optional[str] = None  # ID объекта для записи (char_id или img_id)
        self.recording_type: str = ""  # "character" или "image"
        self.animation_keyframes: Dict[str, List[Dict]] = {}  # id -> keyframes
        self.recording_start_time = 0
        
        # Callback для обновления позиций в редакторе
        self.on_position_changed: Optional[Callable] = None
        self.on_image_position_changed: Optional[Callable] = None  # Callback для картинок
        self.on_text_position_changed: Optional[Callable] = None  # Callback для текстов
        self.on_keyframe_added: Optional[Callable] = None
        self.on_animation_saved: Optional[Callable] = None  # Callback при сохранении анимации
        
        # Очередь команд от главного потока
        self.command_queue = queue.Queue()
        
        # Кэш изображений
        self.image_cache: Dict[str, pygame.Surface] = {}
        
        # UI
        self.show_grid = True
        self.grid_size = 0.1  # 10% шаг сетки
        
    def start(self):
        """Запустить окно предпросмотра в отдельном потоке."""
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Остановить окно."""
        self.running = False
    
    def _run(self):
        """Главный цикл pygame."""
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("preview")
        clock = pygame.time.Clock()
        
        font = pygame.font.Font(None, 24)
        
        while self.running:
            # Обработка команд от главного потока
            self._process_commands()
            
            # Обработка событий pygame
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # ЛКМ
                        self._handle_mouse_down(event.pos)
                    elif event.button == 3:  # ПКМ - добавить ключевой кадр
                        if self.is_recording and self.selected_character:
                            self._add_keyframe()
                            
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self._handle_mouse_up(event.pos)
                        
                elif event.type == pygame.MOUSEMOTION:
                    if pygame.mouse.get_pressed()[0]:  # ЛКМ зажата
                        self._handle_mouse_drag(event.pos)
                        
                elif event.type == pygame.MOUSEWHEEL:
                    # Колесико мышки - разные трансформации
                    if self.selected_character:
                        char = self.characters[self.selected_character]
                        mods = pygame.key.get_mods()
                        if mods & pygame.KMOD_SHIFT:
                            # Shift + колесико = масштаб
                            char.scale += event.y * 0.05
                            char.scale = max(0.1, min(3.0, char.scale))
                        elif mods & pygame.KMOD_CTRL:
                            # Ctrl + колесико = перспектива X
                            char.skew_x += event.y * 0.02
                            char.skew_x = max(-0.5, min(0.5, char.skew_x))
                        elif mods & pygame.KMOD_ALT:
                            # Alt + колесико = перспектива Y
                            char.skew_y += event.y * 0.02
                            char.skew_y = max(-0.5, min(0.5, char.skew_y))
                        else:
                            # Просто колесико = поворот
                            char.rotation += event.y * 5
                            char.rotation = char.rotation % 360
                        self._update_transformed_image(char)
                        self._notify_position_changed(char)
                    
                    elif self.selected_image:
                        img = self.images[self.selected_image]
                        mods = pygame.key.get_mods()
                        if mods & pygame.KMOD_SHIFT:
                            img.scale += event.y * 0.05
                            img.scale = max(0.1, min(3.0, img.scale))
                        elif mods & pygame.KMOD_CTRL:
                            img.skew_x += event.y * 0.02
                            img.skew_x = max(-0.5, min(0.5, img.skew_x))
                        elif mods & pygame.KMOD_ALT:
                            img.skew_y += event.y * 0.02
                            img.skew_y = max(-0.5, min(0.5, img.skew_y))
                        else:
                            img.rotation += event.y * 5
                            img.rotation = img.rotation % 360
                        self._update_image_transform(img)
                        self._notify_image_position_changed(img)
                        
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_g:
                        self.show_grid = not self.show_grid
                    elif event.key == pygame.K_r:
                        self._toggle_recording()
                    elif event.key == pygame.K_k:
                        # Добавить ключевой кадр для выбранного объекта
                        if self.selected_character or self.selected_image:
                            self._add_keyframe()
                    elif event.key == pygame.K_s and self.is_recording:
                        # Сохранить записанную анимацию
                        self._save_recorded_animation()
                    elif event.key == pygame.K_DELETE:
                        if self.selected_character:
                            self._delete_selected()
                        elif self.selected_image:
                            self._delete_selected_image()
                    elif event.key == pygame.K_0:  # Сброс всех трансформаций
                        if self.selected_character:
                            char = self.characters[self.selected_character]
                            char.rotation = 0
                            char.flip_x = False
                            char.flip_y = False
                            char.scale = 1.0
                            char.skew_x = 0.0
                            char.skew_y = 0.0
                            self._update_transformed_image(char)
                            self._notify_position_changed(char)
                        elif self.selected_image:
                            img = self.images[self.selected_image]
                            img.rotation = 0
                            img.flip_x = False
                            img.flip_y = False
                            img.scale = 1.0
                            img.skew_x = 0.0
                            img.skew_y = 0.0
                            self._update_image_transform(img)
                            self._notify_image_position_changed(img)
                    elif event.key == pygame.K_h:  # Отзеркалить по горизонтали
                        if self.selected_character:
                            char = self.characters[self.selected_character]
                            char.flip_x = not char.flip_x
                            self._update_transformed_image(char)
                            self._notify_position_changed(char)
                        elif self.selected_image:
                            img = self.images[self.selected_image]
                            img.flip_x = not img.flip_x
                            self._update_image_transform(img)
                            self._notify_image_position_changed(img)
                    elif event.key == pygame.K_v:  # Отзеркалить по вертикали
                        if self.selected_character:
                            char = self.characters[self.selected_character]
                            char.flip_y = not char.flip_y
                            self._update_transformed_image(char)
                            self._notify_position_changed(char)
                        elif self.selected_image:
                            img = self.images[self.selected_image]
                            img.flip_y = not img.flip_y
                            self._update_image_transform(img)
                            self._notify_image_position_changed(img)
            
            # Отрисовка
            self._draw(font)
            pygame.display.flip()
            clock.tick(60)
        
        pygame.quit()
    
    def _process_commands(self):
        """Обработать команды от главного потока."""
        while not self.command_queue.empty():
            try:
                cmd, args = self.command_queue.get_nowait()
                if cmd == 'set_background':
                    self._load_background(args)
                elif cmd == 'set_background_color':
                    self.background_color = args
                elif cmd == 'add_character':
                    self._add_character(*args)
                elif cmd == 'remove_character':
                    self._remove_character(args)
                elif cmd == 'update_character':
                    self._update_character(*args)
                elif cmd == 'add_image':
                    self._add_image(*args)
                elif cmd == 'remove_image':
                    self._remove_image(args)
                elif cmd == 'add_text':
                    self._add_text(*args)
                elif cmd == 'remove_text':
                    self._remove_text(args)
                elif cmd == 'clear':
                    self.characters.clear()
                    self.images.clear()
                    self.texts.clear()
                    self.background = None
                    self.background_color = None
            except queue.Empty:
                break
    
    def _load_background(self, path: str):
        """Загрузить фон."""
        if not path or not os.path.exists(path):
            self.background = None
            return
        
        try:
            bg = pygame.image.load(path).convert()
            self.background = pygame.transform.scale(bg, (self.width, self.height))
        except pygame.error:
            self.background = None
    
    def _add_character(self, char_id: str, name: str, image_path: str, x: float, y: float, emotion: str,
                       rotation: float = 0.0, flip_x: bool = False, flip_y: bool = False,
                       scale: float = 1.0, skew_x: float = 0.0, skew_y: float = 0.0):
        """Добавить персонажа."""
        char = DraggableCharacter(
            id=char_id,
            name=name,
            x=x,
            y=y,
            emotion=emotion,
            rotation=rotation,
            flip_x=flip_x,
            flip_y=flip_y,
            scale=scale,
            skew_x=skew_x,
            skew_y=skew_y
        )
        
        # Загрузка изображения
        if image_path and os.path.exists(image_path):
            try:
                if image_path not in self.image_cache:
                    img = pygame.image.load(image_path).convert_alpha()
                    # Масштабируем большие картинки под размер окна
                    scale_h = self.height * 0.8 / max(img.get_height(), 1)
                    scale_w = self.width * 0.8 / max(img.get_width(), 1)
                    base_scale = min(scale_h, scale_w, 1.0)  # Не увеличиваем маленькие
                    if base_scale < 1.0:
                        new_size = (int(img.get_width() * base_scale), int(img.get_height() * base_scale))
                        img = pygame.transform.smoothscale(img, new_size)
                    self.image_cache[image_path] = img
                char.original_image = self.image_cache[image_path]
                # Применяем трансформации
                self._update_transformed_image(char)
            except pygame.error:
                pass
        
        self.characters[char_id] = char
    
    def _update_transformed_image(self, char: DraggableCharacter):
        """Обновить изображение с учётом всех трансформаций."""
        if char.original_image:
            img = char.original_image
            
            # 1. Масштабирование
            if char.scale != 1.0:
                new_w = int(img.get_width() * char.scale)
                new_h = int(img.get_height() * char.scale)
                if new_w > 0 and new_h > 0:
                    img = pygame.transform.smoothscale(img, (new_w, new_h))
            
            # 2. Отзеркаливание
            if char.flip_x or char.flip_y:
                img = pygame.transform.flip(img, char.flip_x, char.flip_y)
            
            # 3. Перспектива (skew) - используем rotozoom для эффекта
            if char.skew_x != 0 or char.skew_y != 0:
                img = self._apply_skew(img, char.skew_x, char.skew_y)
            
            # 4. Поворот
            if char.rotation != 0:
                img = pygame.transform.rotate(img, char.rotation)
            
            char.image = img
    
    def _apply_skew(self, surface: pygame.Surface, skew_x: float, skew_y: float) -> pygame.Surface:
        """Применить эффект перспективы (наклон)."""
        w, h = surface.get_size()
        
        # Вычисляем смещения для углов
        dx = int(w * abs(skew_x))
        dy = int(h * abs(skew_y))
        
        new_w = w + dx
        new_h = h + dy
        
        new_surface = pygame.Surface((new_w, new_h), pygame.SRCALPHA)
        
        # Копируем построчно с смещением
        for y in range(h):
            # Вычисляем смещение для этой строки
            if skew_x >= 0:
                offset_x = int(skew_x * w * (1 - y / h))
            else:
                offset_x = int(-skew_x * w * (y / h))
            
            if skew_y >= 0:
                offset_y = int(skew_y * h * (1 - y / h))
            else:
                offset_y = int(-skew_y * h * (y / h))
            
            # Копируем строку
            line = surface.subsurface((0, y, w, 1))
            new_surface.blit(line, (offset_x, y + offset_y))
        
        return new_surface
    
    def _remove_character(self, char_id: str):
        """Удалить персонажа."""
        if char_id in self.characters:
            del self.characters[char_id]
    
    def _add_image(self, img_id: str, name: str, image_path: str, x: float, y: float, layer: int = 0,
                   rotation: float = 0.0, flip_x: bool = False, flip_y: bool = False,
                   scale: float = 1.0, skew_x: float = 0.0, skew_y: float = 0.0):
        """Добавить картинку на сцену."""
        img_obj = DraggableImage(
            id=img_id,
            name=name,
            path=image_path,
            x=x,
            y=y,
            layer=layer,
            rotation=rotation,
            flip_x=flip_x,
            flip_y=flip_y,
            scale=scale,
            skew_x=skew_x,
            skew_y=skew_y
        )
        
        # Загрузка изображения
        if image_path and os.path.exists(image_path):
            try:
                if image_path not in self.image_cache:
                    img = pygame.image.load(image_path).convert_alpha()
                    # Масштабируем под размер окна - учитываем и ширину и высоту
                    scale_h = self.height * 0.8 / max(img.get_height(), 1)
                    scale_w = self.width * 0.8 / max(img.get_width(), 1)
                    base_scale = min(scale_h, scale_w, 1.0)  # Не увеличиваем маленькие
                    new_size = (int(img.get_width() * base_scale), int(img.get_height() * base_scale))
                    if new_size[0] > 0 and new_size[1] > 0:
                        img = pygame.transform.smoothscale(img, new_size)
                    self.image_cache[image_path] = img
                img_obj.original_image = self.image_cache[image_path]
                # Применяем трансформации
                self._update_image_transform(img_obj)
            except pygame.error:
                pass
        
        self.images[img_id] = img_obj
    
    def _remove_image(self, img_id: str):
        """Удалить картинку."""
        if img_id in self.images:
            del self.images[img_id]
    
    def _add_text(self, text_id: str, text: str, x: float, y: float, font_size: int = 36,
                  color: Tuple[int, int, int] = (255, 255, 255),
                  outline_color: Tuple[int, int, int] = (0, 0, 0), outline_width: int = 2,
                  scale: float = 1.0, rotation: float = 0.0, order: int = 0):
        """Добавить текст на сцену."""
        # Парсинг цвета если пришёл как список
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            color = (int(color[0]), int(color[1]), int(color[2]))
        if isinstance(outline_color, (list, tuple)) and len(outline_color) >= 3:
            outline_color = (int(outline_color[0]), int(outline_color[1]), int(outline_color[2]))
        
        text_obj = DraggableText(
            id=text_id,
            text=text,
            x=x,
            y=y,
            font_size=font_size,
            color=color,
            outline_color=outline_color,
            outline_width=outline_width,
            scale=scale,
            rotation=rotation,
            order=order
        )
        
        # Рендерим текст
        self._render_text_surface(text_obj)
        
        self.texts[text_id] = text_obj
    
    def _remove_text(self, text_id: str):
        """Удалить текст."""
        if text_id in self.texts:
            del self.texts[text_id]
    
    def _render_text_surface(self, text_obj: DraggableText):
        """Отрендерить текст в surface."""
        pygame.font.init()
        font = pygame.font.Font(None, text_obj.font_size)
        
        # Основной текст
        text_surface = font.render(text_obj.text, True, text_obj.color)
        
        # Если есть обводка
        if text_obj.outline_color and text_obj.outline_width > 0:
            w = text_surface.get_width() + text_obj.outline_width * 2
            h = text_surface.get_height() + text_obj.outline_width * 2
            outline_surface = pygame.Surface((w, h), pygame.SRCALPHA)
            
            outline_text = font.render(text_obj.text, True, text_obj.outline_color)
            for dx in range(-text_obj.outline_width, text_obj.outline_width + 1):
                for dy in range(-text_obj.outline_width, text_obj.outline_width + 1):
                    if dx != 0 or dy != 0:
                        outline_surface.blit(outline_text, (text_obj.outline_width + dx, text_obj.outline_width + dy))
            
            outline_surface.blit(text_surface, (text_obj.outline_width, text_obj.outline_width))
            text_surface = outline_surface
        
        # Масштаб
        if text_obj.scale != 1.0:
            new_w = int(text_surface.get_width() * text_obj.scale)
            new_h = int(text_surface.get_height() * text_obj.scale)
            if new_w > 0 and new_h > 0:
                text_surface = pygame.transform.smoothscale(text_surface, (new_w, new_h))
        
        # Поворот
        if text_obj.rotation != 0:
            text_surface = pygame.transform.rotate(text_surface, -text_obj.rotation)
        
        text_obj.surface = text_surface
    
    def _get_text_rect(self, text_obj: DraggableText) -> pygame.Rect:
        """Получить прямоугольник текста."""
        if text_obj.surface is None:
            w, h = 100, 30
        else:
            w, h = text_obj.surface.get_width(), text_obj.surface.get_height()
        
        x = int(text_obj.x * self.width - w / 2)
        y = int(text_obj.y * self.height - h / 2)
        return pygame.Rect(x, y, w, h)
    
    def _notify_text_position_changed(self, text_obj: DraggableText):
        """Уведомить об изменении позиции текста."""
        if self.on_text_position_changed:
            self.on_text_position_changed(
                text_obj.id, text_obj.x, text_obj.y, text_obj.scale, text_obj.rotation
            )
    
    def _update_image_transform(self, img: DraggableImage):
        """Обновить изображение картинки с учётом трансформаций."""
        if img.original_image:
            result = img.original_image
            
            # 1. Масштабирование
            if img.scale != 1.0:
                new_w = int(result.get_width() * img.scale)
                new_h = int(result.get_height() * img.scale)
                if new_w > 0 and new_h > 0:
                    result = pygame.transform.smoothscale(result, (new_w, new_h))
            
            # 2. Отзеркаливание
            if img.flip_x or img.flip_y:
                result = pygame.transform.flip(result, img.flip_x, img.flip_y)
            
            # 3. Перспектива
            if img.skew_x != 0 or img.skew_y != 0:
                result = self._apply_skew(result, img.skew_x, img.skew_y)
            
            # 4. Поворот
            if img.rotation != 0:
                result = pygame.transform.rotate(result, -img.rotation)
            
            img.image = result
    
    def _get_image_rect(self, img: DraggableImage) -> pygame.Rect:
        """Получить прямоугольник картинки."""
        if img.image is None:
            w, h = 100, 100
        else:
            w, h = img.image.get_width(), img.image.get_height()
        
        x = int(img.x * self.width - w / 2)
        y = int(img.y * self.height - h / 2)
        return pygame.Rect(x, y, w, h)
    
    def _notify_image_position_changed(self, img: DraggableImage):
        """Уведомить об изменении позиции картинки."""
        if self.on_image_position_changed:
            self.on_image_position_changed(
                img.id, img.x, img.y, img.rotation,
                img.flip_x, img.flip_y, img.scale,
                img.skew_x, img.skew_y, img.layer
            )

    def _update_character(self, char_id: str, image_path: str, x: float, y: float, emotion: str):
        """Обновить персонажа."""
        if char_id in self.characters:
            char = self.characters[char_id]
            char.x = x
            char.y = y
            char.emotion = emotion
            
            # Обновляем изображение если изменилось
            if image_path and os.path.exists(image_path):
                try:
                    if image_path not in self.image_cache:
                        img = pygame.image.load(image_path).convert_alpha()
                        # Масштабируем большие картинки под размер окна
                        scale_h = self.height * 0.8 / max(img.get_height(), 1)
                        scale_w = self.width * 0.8 / max(img.get_width(), 1)
                        base_scale = min(scale_h, scale_w, 1.0)
                        if base_scale < 1.0:
                            new_size = (int(img.get_width() * base_scale), int(img.get_height() * base_scale))
                            img = pygame.transform.smoothscale(img, new_size)
                        self.image_cache[image_path] = img
                    char.original_image = self.image_cache[image_path]
                    self._update_transformed_image(char)
                except pygame.error:
                    pass
    
    def _get_character_rect(self, char: DraggableCharacter) -> pygame.Rect:
        """Получить прямоугольник персонажа."""
        if char.image is None:
            # Заглушка
            w, h = 100, 200
        else:
            w, h = char.image.get_width(), char.image.get_height()
        
        x = int(char.x * self.width - w / 2)
        y = int(char.y * self.height - h / 2)
        return pygame.Rect(x, y, w, h)
    
    def _handle_mouse_down(self, pos: Tuple[int, int]):
        """Обработка нажатия мыши."""
        # Сначала проверяем клик по персонажам (в обратном порядке - верхние первые)
        for char_id in reversed(list(self.characters.keys())):
            char = self.characters[char_id]
            rect = self._get_character_rect(char)
            
            if rect.collidepoint(pos):
                # Снимаем выделение с картинки и текста если были
                if self.selected_image:
                    self.images[self.selected_image].is_selected = False
                    self.selected_image = None
                if self.selected_text:
                    self.texts[self.selected_text].is_selected = False
                    self.selected_text = None
                
                # Выбираем персонажа
                if self.selected_character:
                    self.characters[self.selected_character].is_selected = False
                
                char.is_selected = True
                char.is_dragging = True
                self.selected_character = char_id
                
                # Смещение от центра персонажа
                self.drag_offset = (
                    pos[0] - char.x * self.width,
                    pos[1] - char.y * self.height
                )
                return
        
        # Проверяем клик по текстам
        for text_id in reversed(list(self.texts.keys())):
            text_obj = self.texts[text_id]
            rect = self._get_text_rect(text_obj)
            
            if rect.collidepoint(pos):
                # Снимаем выделение с персонажа и картинки если были
                if self.selected_character:
                    self.characters[self.selected_character].is_selected = False
                    self.selected_character = None
                if self.selected_image:
                    self.images[self.selected_image].is_selected = False
                    self.selected_image = None
                
                # Выбираем текст
                if self.selected_text:
                    self.texts[self.selected_text].is_selected = False
                
                text_obj.is_selected = True
                text_obj.is_dragging = True
                self.selected_text = text_id
                
                # Смещение от центра
                self.drag_offset = (
                    pos[0] - text_obj.x * self.width,
                    pos[1] - text_obj.y * self.height
                )
                return
        
        # Проверяем клик по картинкам
        for img_id in reversed(list(self.images.keys())):
            img = self.images[img_id]
            rect = self._get_image_rect(img)
            
            if rect.collidepoint(pos):
                # Снимаем выделение с персонажа и текста если были
                if self.selected_character:
                    self.characters[self.selected_character].is_selected = False
                    self.selected_character = None
                if self.selected_text:
                    self.texts[self.selected_text].is_selected = False
                    self.selected_text = None
                
                # Выбираем картинку
                if self.selected_image:
                    self.images[self.selected_image].is_selected = False
                
                img.is_selected = True
                img.is_dragging = True
                self.selected_image = img_id
                
                # Смещение от центра
                self.drag_offset = (
                    pos[0] - img.x * self.width,
                    pos[1] - img.y * self.height
                )
                return
        
        # Клик мимо - снимаем выделение
        if self.selected_character:
            self.characters[self.selected_character].is_selected = False
            self.selected_character = None
        if self.selected_image:
            self.images[self.selected_image].is_selected = False
            self.selected_image = None
        if self.selected_text:
            self.texts[self.selected_text].is_selected = False
            self.selected_text = None
    
    def _notify_position_changed(self, char: 'DraggableCharacter'):
        """Уведомить редактор об изменении трансформаций персонажа."""
        if self.on_position_changed:
            self.on_position_changed(
                char.id, char.x, char.y, char.rotation, 
                char.flip_x, char.flip_y, char.scale, char.skew_x, char.skew_y
            )
    
    def _handle_mouse_up(self, pos: Tuple[int, int]):
        """Обработка отпускания мыши."""
        if self.selected_character:
            char = self.characters[self.selected_character]
            char.is_dragging = False
            
            # Callback для обновления позиции в редакторе
            self._notify_position_changed(char)
        
        if self.selected_image:
            img = self.images[self.selected_image]
            img.is_dragging = False
            
            # Callback для обновления позиции в редакторе
            self._notify_image_position_changed(img)
        
        if self.selected_text:
            text_obj = self.texts[self.selected_text]
            text_obj.is_dragging = False
            
            # Callback для обновления позиции в редакторе
            self._notify_text_position_changed(text_obj)
    
    def _handle_mouse_drag(self, pos: Tuple[int, int]):
        """Обработка перетаскивания."""
        if self.selected_character:
            char = self.characters[self.selected_character]
            if char.is_dragging:
                # Новая позиция с учётом смещения
                new_x = (pos[0] - self.drag_offset[0]) / self.width
                new_y = (pos[1] - self.drag_offset[1]) / self.height
                
                # Ограничиваем в пределах экрана
                char.x = max(0.1, min(0.9, new_x))
                char.y = max(0.1, min(0.95, new_y))
        
        if self.selected_image:
            img = self.images[self.selected_image]
            if img.is_dragging:
                # Новая позиция с учётом смещения
                new_x = (pos[0] - self.drag_offset[0]) / self.width
                new_y = (pos[1] - self.drag_offset[1]) / self.height
                
                # Ограничиваем в пределах экрана
                img.x = max(0.05, min(0.95, new_x))
                img.y = max(0.05, min(0.95, new_y))
        
        if self.selected_text:
            text_obj = self.texts[self.selected_text]
            if text_obj.is_dragging:
                # Новая позиция с учётом смещения
                new_x = (pos[0] - self.drag_offset[0]) / self.width
                new_y = (pos[1] - self.drag_offset[1]) / self.height
                
                # Ограничиваем в пределах экрана
                text_obj.x = max(0.05, min(0.95, new_x))
                text_obj.y = max(0.05, min(0.95, new_y))
    
    def _toggle_recording(self):
        """Включить/выключить запись анимации."""
        if self.is_recording:
            # Выключаем запись
            self.is_recording = False
            self.recording_target = None
            self.recording_type = ""
        else:
            # Включаем запись для выбранного объекта
            if self.selected_character:
                self.is_recording = True
                self.recording_target = self.selected_character
                self.recording_type = "character"
                self.recording_start_time = pygame.time.get_ticks()
                self.animation_keyframes[self.selected_character] = []
                self._add_keyframe()
            elif self.selected_image:
                self.is_recording = True
                self.recording_target = self.selected_image
                self.recording_type = "image"
                self.recording_start_time = pygame.time.get_ticks()
                self.animation_keyframes[self.selected_image] = []
                self._add_keyframe()
    
    def _add_keyframe(self):
        """Добавить ключевой кадр для выбранного объекта."""
        time = (pygame.time.get_ticks() - self.recording_start_time) / 1000.0 if self.is_recording else 0
        
        if self.selected_character:
            char = self.characters[self.selected_character]
            keyframe = {
                'time': time,
                'x': char.x,
                'y': char.y,
                'scale': char.scale,
                'alpha': char.alpha,
                'rotation': char.rotation
            }
            if char.id not in self.animation_keyframes:
                self.animation_keyframes[char.id] = []
            self.animation_keyframes[char.id].append(keyframe)
            
            if self.on_keyframe_added:
                self.on_keyframe_added(char.id, keyframe, "character")
                
        elif self.selected_image:
            img = self.images[self.selected_image]
            keyframe = {
                'time': time,
                'x': img.x,
                'y': img.y,
                'scale': img.scale,
                'alpha': img.alpha,
                'rotation': img.rotation
            }
            if img.id not in self.animation_keyframes:
                self.animation_keyframes[img.id] = []
            self.animation_keyframes[img.id].append(keyframe)
            
            if self.on_keyframe_added:
                self.on_keyframe_added(img.id, keyframe, "image")
    
    def _save_recorded_animation(self):
        """Сохранить записанную анимацию."""
        if not self.recording_target or self.recording_target not in self.animation_keyframes:
            return
        
        keyframes = self.animation_keyframes[self.recording_target]
        if not keyframes:
            return
        
        animation = {
            'keyframes': keyframes,
            'loop': True  # По умолчанию зацикленная
        }
        
        if self.recording_type == "character":
            animation['character_id'] = self.recording_target
        else:
            animation['image_id'] = self.recording_target
        
        if self.on_animation_saved:
            self.on_animation_saved(animation, self.recording_type)
    
    def _delete_selected(self):
        """Удалить выбранного персонажа из сцены."""
        if self.selected_character:
            del self.characters[self.selected_character]
            self.selected_character = None
    
    def _delete_selected_image(self):
        """Удалить выбранную картинку из сцены."""
        if self.selected_image:
            del self.images[self.selected_image]
            self.selected_image = None
    
    def _draw(self, font: pygame.font.Font):
        """Отрисовка сцены."""
        # Фон
        if self.background:
            self.screen.blit(self.background, (0, 0))
        elif self.background_color:
            self.screen.fill(self.background_color)
        else:
            # Градиент
            for y in range(self.height):
                r = int(30 + (y / self.height) * 20)
                g = int(30 + (y / self.height) * 30)
                b = int(50 + (y / self.height) * 40)
                pygame.draw.line(self.screen, (r, g, b), (0, y), (self.width, y))
        
        # Сетка
        if self.show_grid:
            self._draw_grid()
        
        # Картинки (сортируем по слою)
        sorted_images = sorted(self.images.values(), key=lambda img: img.layer)
        for img in sorted_images:
            self._draw_image(img, font)
        
        # Персонажи
        for char_id, char in self.characters.items():
            self._draw_character(char, font)
        
        # Тексты
        for text_id, text_obj in self.texts.items():
            self._draw_text(text_obj, font)
        
        # UI панель сверху
        self._draw_ui(font)
    
    def _draw_grid(self):
        """Отрисовать сетку."""
        grid_color = (255, 255, 255, 30)
        
        # Вертикальные линии
        for i in range(1, 10):
            x = int(i * 0.1 * self.width)
            pygame.draw.line(self.screen, (100, 100, 100), (x, 0), (x, self.height), 1)
        
        # Горизонтальные линии
        for i in range(1, 10):
            y = int(i * 0.1 * self.height)
            pygame.draw.line(self.screen, (100, 100, 100), (0, y), (self.width, y), 1)
        
        # Центральные линии ярче
        cx = self.width // 2
        cy = self.height // 2
        pygame.draw.line(self.screen, (150, 150, 150), (cx, 0), (cx, self.height), 2)
        pygame.draw.line(self.screen, (150, 150, 150), (0, cy), (self.width, cy), 2)
    
    def _draw_image(self, img: DraggableImage, font: pygame.font.Font):
        """Отрисовать картинку."""
        rect = self._get_image_rect(img)
        
        if img.image:
            self.screen.blit(img.image, rect.topleft)
        else:
            # Заглушка
            pygame.draw.rect(self.screen, (80, 120, 80), rect)
            pygame.draw.rect(self.screen, (120, 180, 120), rect, 2)
            
            # Имя внутри
            name_text = font.render(img.name or img.id, True, (255, 255, 255))
            name_rect = name_text.get_rect(center=rect.center)
            self.screen.blit(name_text, name_rect)
        
        # Рамка выделения (зелёная для картинок)
        if img.is_selected:
            pygame.draw.rect(self.screen, (0, 255, 100), rect, 3)
            
            # Подпись с позицией и ID
            pos_text = font.render(f"[IMG] {img.id} ({img.name}): ({img.x:.2f}, {img.y:.2f}) L{img.layer}", True, (0, 255, 100))
            self.screen.blit(pos_text, (rect.x, rect.y - 25))
            
            # Точки масштабирования
            for corner in [(rect.left, rect.top), (rect.right, rect.top),
                          (rect.left, rect.bottom), (rect.right, rect.bottom)]:
                pygame.draw.circle(self.screen, (0, 255, 100), corner, 6)
        
        # Отображение ключевых кадров анимации для картинки
        if img.id in self.animation_keyframes and self.animation_keyframes[img.id]:
            self._draw_animation_path(img.id, (0, 255, 100))
    
    def _draw_character(self, char: DraggableCharacter, font: pygame.font.Font):
        """Отрисовать персонажа."""
        rect = self._get_character_rect(char)
        
        if char.image:
            self.screen.blit(char.image, rect.topleft)
        else:
            # Заглушка
            pygame.draw.rect(self.screen, (100, 100, 150), rect)
            pygame.draw.rect(self.screen, (150, 150, 200), rect, 2)
            
            # Имя внутри
            name_text = font.render(char.name or char.id, True, (255, 255, 255))
            name_rect = name_text.get_rect(center=rect.center)
            self.screen.blit(name_text, name_rect)
        
        # Рамка выделения
        if char.is_selected:
            pygame.draw.rect(self.screen, (255, 200, 0), rect, 3)
            
            # Подпись с позицией
            pos_text = font.render(f"{char.name}: ({char.x:.2f}, {char.y:.2f})", True, (255, 255, 0))
            self.screen.blit(pos_text, (rect.x, rect.y - 25))
            
            # Точки масштабирования
            for corner in [(rect.left, rect.top), (rect.right, rect.top),
                          (rect.left, rect.bottom), (rect.right, rect.bottom)]:
                pygame.draw.circle(self.screen, (255, 200, 0), corner, 6)
        
        # Отображение ключевых кадров анимации
        if char.id in self.animation_keyframes and self.animation_keyframes[char.id]:
            self._draw_animation_path(char.id, (255, 200, 0))
    
    def _draw_text(self, text_obj: DraggableText, font: pygame.font.Font):
        """Отрисовать текстовый элемент."""
        rect = self._get_text_rect(text_obj)
        
        if text_obj.surface:
            self.screen.blit(text_obj.surface, rect.topleft)
        else:
            # Заглушка
            pygame.draw.rect(self.screen, (50, 50, 80), rect)
            pygame.draw.rect(self.screen, (100, 100, 150), rect, 2)
            
            # Текст внутри
            preview_text = text_obj.text[:15] + "..." if len(text_obj.text) > 15 else text_obj.text
            name_text = font.render(preview_text, True, (255, 255, 255))
            name_rect = name_text.get_rect(center=rect.center)
            self.screen.blit(name_text, name_rect)
        
        # Рамка выделения
        if text_obj.is_selected:
            pygame.draw.rect(self.screen, (100, 200, 255), rect, 3)
            
            # Подпись с позицией
            pos_text = font.render(f"[TXT] {text_obj.id}: ({text_obj.x:.2f}, {text_obj.y:.2f})", True, (100, 200, 255))
            self.screen.blit(pos_text, (rect.x, rect.y - 25))
            
            # Точки масштабирования
            for corner in [(rect.left, rect.top), (rect.right, rect.top),
                          (rect.left, rect.bottom), (rect.right, rect.bottom)]:
                pygame.draw.circle(self.screen, (100, 200, 255), corner, 6)
    
    def _draw_animation_path(self, obj_id: str, color: Tuple[int, int, int] = (255, 100, 100)):
        """Отрисовать путь анимации."""
        keyframes = self.animation_keyframes.get(obj_id, [])
        if len(keyframes) < 2:
            return
        
        points = []
        for kf in keyframes:
            x = int(kf['x'] * self.width)
            y = int(kf['y'] * self.height)
            points.append((x, y))
        
        # Линия пути
        pygame.draw.lines(self.screen, color, False, points, 2)
        
        # Точки ключевых кадров
        for i, point in enumerate(points):
            point_color = (color[0], max(0, color[1] - 100), max(0, color[2] - 100)) if i == 0 else color
            pygame.draw.circle(self.screen, point_color, point, 8)
            pygame.draw.circle(self.screen, (255, 255, 255), point, 8, 2)
    
    def _draw_ui(self, font: pygame.font.Font):
        """Отрисовать UI."""
        # Полупрозрачная панель сверху
        ui_surface = pygame.Surface((self.width, 60 if self.is_recording else 40), pygame.SRCALPHA)
        ui_surface.fill((0, 0, 0, 150))
        self.screen.blit(ui_surface, (0, 0))
        
        # Подсказки
        hints = [
            "preview",
            f"[G] Сетка: {'ВКЛ' if self.show_grid else 'ВЫКЛ'}",
            f"[R] Запись: {'●REC' if self.is_recording else 'ВЫКЛ'}",
            "[K/ПКМ] Кадр"
        ]
        
        x = 10
        for hint in hints:
            color = (255, 100, 100) if 'REC' in hint and self.is_recording else (255, 255, 255)
            text = font.render(hint, True, color)
            self.screen.blit(text, (x, 10))
            x += text.get_width() + 20
        
        # Дополнительная информация при записи
        if self.is_recording and self.recording_target:
            kf_count = len(self.animation_keyframes.get(self.recording_target, []))
            elapsed = (pygame.time.get_ticks() - self.recording_start_time) / 1000.0
            rec_info = f"Запись: {self.recording_target} | Кадров: {kf_count} | Время: {elapsed:.1f}с | [S] Сохранить | [R] Стоп"
            rec_text = font.render(rec_info, True, (255, 150, 150))
            self.screen.blit(rec_text, (10, 35))
    
    # === Публичные методы для вызова из главного потока ===
    
    def set_background(self, path: str):
        """Установить фон (вызывается из главного потока)."""
        self.command_queue.put(('set_background', path))
    
    def add_character(self, char_id: str, name: str, image_path: str, 
                      x: float = 0.5, y: float = 0.7, emotion: str = "default",
                      rotation: float = 0.0, flip_x: bool = False, flip_y: bool = False,
                      scale: float = 1.0, skew_x: float = 0.0, skew_y: float = 0.0):
        """Добавить персонажа (вызывается из главного потока)."""
        self.command_queue.put(('add_character', (char_id, name, image_path, x, y, emotion,
                                                   rotation, flip_x, flip_y, scale, skew_x, skew_y)))
    
    def remove_character(self, char_id: str):
        """Удалить персонажа (вызывается из главного потока)."""
        self.command_queue.put(('remove_character', char_id))
    
    def update_character(self, char_id: str, image_path: str, x: float, y: float, emotion: str):
        """Обновить персонажа (вызывается из главного потока)."""
        self.command_queue.put(('update_character', (char_id, image_path, x, y, emotion)))
    
    def add_image(self, img_id: str, name: str, image_path: str, 
                  x: float = 0.5, y: float = 0.5, layer: int = 0,
                  rotation: float = 0.0, flip_x: bool = False, flip_y: bool = False,
                  scale: float = 1.0, skew_x: float = 0.0, skew_y: float = 0.0):
        """Добавить картинку на сцену (вызывается из главного потока)."""
        self.command_queue.put(('add_image', (img_id, name, image_path, x, y, layer,
                                               rotation, flip_x, flip_y, scale, skew_x, skew_y)))
    
    def remove_image(self, img_id: str):
        """Удалить картинку со сцены (вызывается из главного потока)."""
        self.command_queue.put(('remove_image', img_id))
    
    def add_text(self, text_id: str, text: str, x: float = 0.5, y: float = 0.5,
                 font_size: int = 36, color: Tuple[int, int, int] = (255, 255, 255),
                 outline_color: Tuple[int, int, int] = (0, 0, 0), outline_width: int = 2,
                 scale: float = 1.0, rotation: float = 0.0, order: int = 0):
        """Добавить текст на сцену (вызывается из главного потока)."""
        self.command_queue.put(('add_text', (text_id, text, x, y, font_size, color,
                                              outline_color, outline_width, scale, rotation, order)))
    
    def remove_text(self, text_id: str):
        """Удалить текст со сцены (вызывается из главного потока)."""
        self.command_queue.put(('remove_text', text_id))
    
    def set_background_color(self, color: Optional[Tuple[int, int, int]]):
        """Установить цвет фона (вызывается из главного потока)."""
        self.command_queue.put(('set_background_color', color))
    
    def clear(self):
        """Очистить сцену (вызывается из главного потока)."""
        self.command_queue.put(('clear', None))
    
    def get_character_positions(self) -> Dict[str, Tuple[float, float]]:
        """Получить текущие позиции всех персонажей."""
        return {char_id: (char.x, char.y) for char_id, char in self.characters.items()}
    
    def get_keyframes(self, char_id: str) -> List[Dict]:
        """Получить ключевые кадры анимации персонажа."""
        return self.animation_keyframes.get(char_id, [])
    
    def clear_keyframes(self, char_id: str = None):
        """Очистить ключевые кадры."""
        if char_id:
            self.animation_keyframes[char_id] = []
        else:
            self.animation_keyframes.clear()


class GamePreview:
    """Предпросмотр сцены как в игре - с диалогами и анимациями."""
    
    def __init__(self, width: int = 960, height: int = 540):
        self.width = width
        self.height = height
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.command_queue = queue.Queue()
        
        # Данные сцены
        self.story = None
        self.scene = None
        self.characters_data: Dict[str, Any] = {}  # character_id -> Character
        
        # Состояние
        self.background: Optional[pygame.Surface] = None
        self.background_color: Optional[Tuple[int, int, int]] = None
        self.characters: Dict[str, Dict] = {}  # char_id -> {image, x, y, ...}
        self.images: Dict[str, Dict] = {}  # img_id -> {image, x, y, ...}
        
        # Диалоги
        self.current_dialog_index = 0
        self.dialog_text = ""
        self.dialog_name = ""
        self.dialog_name_color = (255, 255, 255)
        self.typing_progress = 0.0
        self.typing_speed = 0.03  # Секунд на символ
        self.typing_start_time = 0
        self.typing_duration = 0
        
        # Анимации
        self.animations: Dict[str, Dict] = {}  # char_id -> {keyframes, loop, start_time}
        
        # Задержка
        self.delay_start = None
        self.delay_duration = 0
        
        # Выборы
        self.show_choices = False
        self.choice_rects: List[pygame.Rect] = []  # Прямоугольники кнопок выборов
        self.hovered_choice = -1
        
        # Шрифты
        self.font = None
        self.name_font = None
    
    def start(self):
        """Запустить предпросмотр в отдельном потоке."""
        if self.running:
            return
        
        # Сброс состояния
        self.current_dialog_index = 0
        self.dialog_text = ""
        self.dialog_name = ""
        self.typing_progress = 0.0
        self.show_choices = False
        self.choice_rects = []
        self.hovered_choice = -1
        self.animations.clear()
        self.characters.clear()
        self.images.clear()
        self.background = None
        self.delay_start = None
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Остановить предпросмотр."""
        self.running = False
        try:
            pygame.mixer.music.stop()
        except:
            pass
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None
        # Очищаем очередь команд
        while not self.command_queue.empty():
            try:
                self.command_queue.get_nowait()
            except:
                pass
    
    def _run_loop(self):
        """Основной цикл pygame."""
        try:
            pygame.init()
            pygame.font.init()
            try:
                pygame.mixer.init()
            except:
                pass
            
            screen = pygame.display.set_mode((self.width, self.height))
            pygame.display.set_caption("Предпросмотр игры")
            
            clock = pygame.time.Clock()
            self.font = pygame.font.Font(None, 28)
            self.name_font = pygame.font.Font(None, 32)
            
            while self.running:
                # Обработка команд
                self._process_commands()
                
                mouse_pos = pygame.mouse.get_pos()
                
                # Обновление hovered выбора
                self.hovered_choice = -1
                if self.show_choices:
                    for i, rect in enumerate(self.choice_rects):
                        if rect.collidepoint(mouse_pos):
                            self.hovered_choice = i
                            break
                
                # События
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            self.running = False
                        elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                            if not self.show_choices:
                                self._next_dialog()
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:  # ЛКМ
                            if self.show_choices and self.hovered_choice >= 0:
                                self._select_choice(self.hovered_choice)
                            else:
                                self._next_dialog()
                
                # Обновление
                self._update()
                
                # Отрисовка
                self._draw(screen)
                
                pygame.display.flip()
                clock.tick(60)
        
        finally:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            except:
                pass
            try:
                pygame.quit()
            except:
                pass
            self.running = False
    
    def _process_commands(self):
        """Обработать команды из очереди."""
        while not self.command_queue.empty():
            try:
                cmd, data = self.command_queue.get_nowait()
                
                if cmd == 'load_scene':
                    self._cmd_load_scene(data)
                elif cmd == 'set_background':
                    self._cmd_set_background(data)
                
            except queue.Empty:
                break
    
    def _cmd_load_scene(self, data):
        """Загрузить сцену."""
        self.scene, self.story, self.characters_data = data
        
        # Сбрасываем состояние
        self.current_dialog_index = 0
        self.characters.clear()
        self.images.clear()
        self.animations.clear()
        self.show_choices = False
        self.choice_rects.clear()
        
        if not self.scene:
            return
        
        # Фон
        if self.scene.background and os.path.exists(self.scene.background):
            try:
                bg = pygame.image.load(self.scene.background).convert()
                self.background = pygame.transform.smoothscale(bg, (self.width, self.height))
            except:
                self.background = None
        else:
            self.background = None
        
        self.background_color = self.scene.background_color
        
        # Музыка
        if self.scene.music and os.path.exists(self.scene.music):
            try:
                pygame.mixer.music.load(self.scene.music)
                pygame.mixer.music.play(-1)  # Зацикленное воспроизведение
            except:
                pass
        
        # Персонажи на сцене
        for char_data in self.scene.characters_on_screen:
            char_id = char_data.get('id')
            character = self.characters_data.get(char_id)
            if not character:
                continue
            
            emotion = char_data.get('emotion', 'default')
            image_path = character.images.get(emotion, character.images.get('default', ''))
            
            char_info = {
                'x': char_data.get('x', 0.5),
                'y': char_data.get('y', 0.7),
                'scale': char_data.get('scale', 1.0),
                'rotation': char_data.get('rotation', 0),
                'flip_x': char_data.get('flip_x', False),
                'flip_y': char_data.get('flip_y', False),
                'alpha': 255,
                'image': None,
                'original_image': None
            }
            
            if image_path and os.path.exists(image_path):
                try:
                    img = pygame.image.load(image_path).convert_alpha()
                    # Масштабируем
                    scale_h = self.height * 0.8 / max(img.get_height(), 1)
                    scale_w = self.width * 0.8 / max(img.get_width(), 1)
                    base_scale = min(scale_h, scale_w, 1.0)
                    if base_scale < 1.0:
                        new_w = int(img.get_width() * base_scale)
                        new_h = int(img.get_height() * base_scale)
                        if new_w > 0 and new_h > 0:
                            img = pygame.transform.smoothscale(img, (new_w, new_h))
                    char_info['original_image'] = img
                    char_info['image'] = img
                except:
                    pass
            
            self.characters[char_id] = char_info
        
        # Картинки на сцене
        for img_data in self.scene.images_on_screen:
            img_id = img_data.get('id')
            img_path = img_data.get('path', '')
            
            img_info = {
                'x': img_data.get('x', 0.5),
                'y': img_data.get('y', 0.5),
                'scale': img_data.get('scale', 1.0),
                'layer': img_data.get('layer', 0),
                'image': None
            }
            
            if img_path and os.path.exists(img_path):
                try:
                    img = pygame.image.load(img_path).convert_alpha()
                    scale_h = self.height * 0.8 / max(img.get_height(), 1)
                    scale_w = self.width * 0.8 / max(img.get_width(), 1)
                    base_scale = min(scale_h, scale_w, 1.0)
                    if base_scale < 1.0:
                        new_w = int(img.get_width() * base_scale)
                        new_h = int(img.get_height() * base_scale)
                        if new_w > 0 and new_h > 0:
                            img = pygame.transform.smoothscale(img, (new_w, new_h))
                    img_info['image'] = img
                except:
                    pass
            
            self.images[img_id] = img_info
        
        # Запуск фоновых анимаций сцены
        if hasattr(self.scene, 'background_animations') and self.scene.background_animations:
            self._start_background_animations(self.scene.background_animations)
        
        # Показываем первый диалог
        self._show_dialog(0)
    
    def _start_background_animations(self, animations: List[Dict]):
        """Запустить фоновые анимации сцены."""
        current_time = pygame.time.get_ticks()
        
        for anim in animations:
            char_id = anim.get('character_id')
            image_id = anim.get('image_id')
            keyframes = anim.get('keyframes', [])
            loop = anim.get('loop', False)
            
            if keyframes:
                if char_id:
                    self.animations[char_id] = {
                        'keyframes': keyframes,
                        'loop': loop,
                        'start_time': current_time
                    }
                elif image_id:
                    self.animations[f"img_{image_id}"] = {
                        'keyframes': keyframes,
                        'loop': loop,
                        'start_time': current_time
                    }
    
    def _show_dialog(self, index: int):
        """Показать диалог."""
        if not self.scene or index >= len(self.scene.dialogs):
            # Конец диалогов - проверяем выборы
            if self.scene and self.scene.choices:
                self.show_choices = True
                self.dialog_text = ""
                self.dialog_name = ""
            elif self.scene and self.scene.next_scene_id:
                # Переход на следующую сцену
                next_scene = self.story.get_scene(self.scene.next_scene_id) if self.story else None
                if next_scene:
                    self._internal_load_scene(next_scene)
                    return
                else:
                    self.dialog_text = "[Конец сцены - нажмите ESC]"
                    self.dialog_name = ""
            else:
                self.dialog_text = "[Конец сцены - нажмите ESC]"
                self.dialog_name = ""
            self.typing_progress = 1.0
            return
        
        dialog = self.scene.dialogs[index]
        self.current_dialog_index = index
        
        # Задержка
        self.delay_duration = dialog.delay or 0
        if self.delay_duration > 0:
            self.delay_start = pygame.time.get_ticks()
        else:
            self.delay_start = None
        
        # Имя и цвет
        self.dialog_name = ""
        self.dialog_name_color = (255, 255, 255)
        
        if dialog.character_id and self.characters_data:
            character = self.characters_data.get(dialog.character_id)
            if character:
                self.dialog_name = character.name
                # Парсинг цвета
                color = character.color
                if isinstance(color, str) and color.startswith('#'):
                    hex_color = color.lstrip('#')
                    if len(hex_color) == 6:
                        self.dialog_name_color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                
                # Обновляем эмоцию персонажа
                if dialog.character_id in self.characters:
                    emotion = dialog.emotion or 'default'
                    image_path = character.images.get(emotion, character.images.get('default', ''))
                    if image_path and os.path.exists(image_path):
                        try:
                            img = pygame.image.load(image_path).convert_alpha()
                            scale_h = self.height * 0.8 / max(img.get_height(), 1)
                            scale_w = self.width * 0.8 / max(img.get_width(), 1)
                            base_scale = min(scale_h, scale_w, 1.0)
                            if base_scale < 1.0:
                                new_w = int(img.get_width() * base_scale)
                                new_h = int(img.get_height() * base_scale)
                                if new_w > 0 and new_h > 0:
                                    img = pygame.transform.smoothscale(img, (new_w, new_h))
                            self.characters[dialog.character_id]['original_image'] = img
                            self.characters[dialog.character_id]['image'] = img
                        except:
                            pass
                
                # Позиция из диалога
                if dialog.position and dialog.character_id in self.characters:
                    char = self.characters[dialog.character_id]
                    char['x'] = dialog.position.get('x', char['x'])
                    char['y'] = dialog.position.get('y', char['y'])
                    char['scale'] = dialog.position.get('scale', char.get('scale', 1.0))
                    char['rotation'] = dialog.position.get('rotation', char.get('rotation', 0))
        
        # Текст
        if dialog.is_delay_only:
            self.dialog_text = ""
            self.typing_progress = 1.0
        else:
            self.dialog_text = dialog.text
            self.typing_progress = 0.0
            self.typing_start_time = pygame.time.get_ticks()
            
            # Скорость печати
            if dialog.typing_speed is not None:
                if dialog.typing_speed == 0:
                    self.typing_progress = 1.0
                    self.typing_duration = 0
                else:
                    self.typing_duration = dialog.typing_speed * 1000
            else:
                self.typing_duration = len(self.dialog_text) * self.typing_speed * 1000
        
        # Анимации
        if dialog.animations:
            self._start_animations(dialog.animations)
    
    def _start_animations(self, animations: List[Dict]):
        """Запустить анимации."""
        self.animations.clear()
        current_time = pygame.time.get_ticks()
        
        for anim in animations:
            char_id = anim.get('character_id')
            image_id = anim.get('image_id')
            keyframes = anim.get('keyframes', [])
            loop = anim.get('loop', False)
            
            if keyframes:
                if char_id:
                    self.animations[char_id] = {
                        'keyframes': keyframes,
                        'loop': loop,
                        'start_time': current_time
                    }
                elif image_id:
                    # Анимация картинки - добавляем с префиксом img_
                    self.animations[f"img_{image_id}"] = {
                        'keyframes': keyframes,
                        'loop': loop,
                        'start_time': current_time
                    }
    
    def _next_dialog(self):
        """Перейти к следующему диалогу."""
        # Если показываем выборы - ничего не делаем
        if self.show_choices:
            return
        
        # Проверка задержки
        if self.delay_start is not None:
            elapsed = (pygame.time.get_ticks() - self.delay_start) / 1000.0
            if elapsed < self.delay_duration:
                return  # Ещё ждём
        
        # Если текст ещё печатается - показать весь
        if self.typing_progress < 1.0:
            self.typing_progress = 1.0
            return
        
        # Следующий диалог
        if self.scene and self.current_dialog_index < len(self.scene.dialogs) - 1:
            self._show_dialog(self.current_dialog_index + 1)
        elif self.scene:
            # Конец диалогов - вызываем _show_dialog для обработки выборов/перехода
            self._show_dialog(len(self.scene.dialogs))
    
    def _select_choice(self, choice_index: int):
        """Выбрать вариант ответа."""
        if not self.scene or not self.scene.choices:
            return
        
        if 0 <= choice_index < len(self.scene.choices):
            choice = self.scene.choices[choice_index]
            next_scene_id = choice.next_scene_id
            
            if next_scene_id and self.story:
                next_scene = self.story.get_scene(next_scene_id)
                if next_scene:
                    self._internal_load_scene(next_scene)
                    return
        
        # Если переход не удался
        self.show_choices = False
        self.dialog_text = "[Конец - нажмите ESC]"
        self.dialog_name = ""
    
    def _internal_load_scene(self, scene):
        """Внутренняя загрузка сцены (без очереди команд)."""
        self.scene = scene
        
        # Сбрасываем состояние
        self.current_dialog_index = 0
        self.characters.clear()
        self.images.clear()
        self.animations.clear()
        self.show_choices = False
        self.choice_rects.clear()
        
        if not self.scene:
            return
        
        # Фон
        if self.scene.background and os.path.exists(self.scene.background):
            try:
                bg = pygame.image.load(self.scene.background).convert()
                self.background = pygame.transform.smoothscale(bg, (self.width, self.height))
            except:
                self.background = None
        else:
            self.background = None
        
        self.background_color = self.scene.background_color
        
        # Музыка
        if self.scene.music and os.path.exists(self.scene.music):
            try:
                pygame.mixer.music.load(self.scene.music)
                pygame.mixer.music.play(-1)
            except:
                pass
        
        # Персонажи на сцене
        for char_data in self.scene.characters_on_screen:
            char_id = char_data.get('id')
            character = self.characters_data.get(char_id)
            if not character:
                continue
            
            emotion = char_data.get('emotion', 'default')
            image_path = character.images.get(emotion, character.images.get('default', ''))
            
            char_info = {
                'x': char_data.get('x', 0.5),
                'y': char_data.get('y', 0.7),
                'scale': char_data.get('scale', 1.0),
                'rotation': char_data.get('rotation', 0),
                'flip_x': char_data.get('flip_x', False),
                'flip_y': char_data.get('flip_y', False),
                'alpha': 255,
                'image': None,
                'original_image': None
            }
            
            if image_path and os.path.exists(image_path):
                try:
                    img = pygame.image.load(image_path).convert_alpha()
                    scale_h = self.height * 0.8 / max(img.get_height(), 1)
                    scale_w = self.width * 0.8 / max(img.get_width(), 1)
                    base_scale = min(scale_h, scale_w, 1.0)
                    if base_scale < 1.0:
                        new_w = int(img.get_width() * base_scale)
                        new_h = int(img.get_height() * base_scale)
                        if new_w > 0 and new_h > 0:
                            img = pygame.transform.smoothscale(img, (new_w, new_h))
                    char_info['original_image'] = img
                    char_info['image'] = img
                except:
                    pass
            
            self.characters[char_id] = char_info
        
        # Картинки на сцене
        for img_data in self.scene.images_on_screen:
            img_id = img_data.get('id')
            img_path = img_data.get('path', '')
            
            img_info = {
                'x': img_data.get('x', 0.5),
                'y': img_data.get('y', 0.5),
                'scale': img_data.get('scale', 1.0),
                'rotation': img_data.get('rotation', 0.0),
                'layer': img_data.get('layer', 0),
                'image': None,
                'original_image': None
            }
            
            if img_path and os.path.exists(img_path):
                try:
                    img = pygame.image.load(img_path).convert_alpha()
                    # Базовое масштабирование под размер экрана
                    scale_h = self.height * 0.8 / max(img.get_height(), 1)
                    scale_w = self.width * 0.8 / max(img.get_width(), 1)
                    base_scale = min(scale_h, scale_w, 1.0)
                    if base_scale < 1.0:
                        new_w = int(img.get_width() * base_scale)
                        new_h = int(img.get_height() * base_scale)
                        if new_w > 0 and new_h > 0:
                            img = pygame.transform.smoothscale(img, (new_w, new_h))
                    img_info['original_image'] = img
                    img_info['image'] = img
                except:
                    pass
            
            self.images[img_id] = img_info
        
        # Показываем первый диалог
        self._show_dialog(0)
    
    def _update(self):
        """Обновить состояние."""
        current_time = pygame.time.get_ticks()
        
        # Эффект печати
        if self.typing_progress < 1.0 and self.typing_duration > 0:
            elapsed = current_time - self.typing_start_time
            self.typing_progress = min(elapsed / self.typing_duration, 1.0)
        
        # Авто-переход для delay_only
        if self.scene and self.current_dialog_index < len(self.scene.dialogs):
            dialog = self.scene.dialogs[self.current_dialog_index]
            if dialog.is_delay_only and self.delay_start is not None:
                elapsed = (current_time - self.delay_start) / 1000.0
                if elapsed >= self.delay_duration:
                    if self.current_dialog_index < len(self.scene.dialogs) - 1:
                        self._show_dialog(self.current_dialog_index + 1)
        
        # Обновление анимаций персонажей и картинок
        for anim_id, anim_data in list(self.animations.items()):
            elapsed = (current_time - anim_data['start_time']) / 1000.0
            keyframes = anim_data['keyframes']
            loop = anim_data['loop']
            
            if not keyframes:
                continue
            
            total_duration = keyframes[-1]['time']
            
            # Зацикливание
            if loop and total_duration > 0:
                elapsed = elapsed % total_duration
            elif elapsed > total_duration:
                # Анимация закончилась
                del self.animations[anim_id]
                continue
            
            # Интерполяция
            prev_kf = keyframes[0]
            next_kf = keyframes[-1]
            
            for i, kf in enumerate(keyframes):
                if kf['time'] <= elapsed:
                    prev_kf = kf
                    if i + 1 < len(keyframes):
                        next_kf = keyframes[i + 1]
                else:
                    next_kf = kf
                    break
            
            if prev_kf['time'] == next_kf['time']:
                t = 0
            else:
                t = (elapsed - prev_kf['time']) / (next_kf['time'] - prev_kf['time'])
                t = max(0, min(1, t))
            
            # Применяем к персонажу или картинке
            x = prev_kf.get('x', 0.5) + (next_kf.get('x', 0.5) - prev_kf.get('x', 0.5)) * t
            y = prev_kf.get('y', 0.7) + (next_kf.get('y', 0.7) - prev_kf.get('y', 0.7)) * t
            scale = prev_kf.get('scale', 1.0) + (next_kf.get('scale', 1.0) - prev_kf.get('scale', 1.0)) * t
            rotation = prev_kf.get('rotation', 0) + (next_kf.get('rotation', 0) - prev_kf.get('rotation', 0)) * t
            alpha = int((prev_kf.get('alpha', 1.0) + (next_kf.get('alpha', 1.0) - prev_kf.get('alpha', 1.0)) * t) * 255)
            
            # Проверяем, это анимация картинки или персонажа
            if anim_id.startswith('img_'):
                img_id = anim_id[4:]  # Убираем префикс "img_"
                if img_id in self.images:
                    img = self.images[img_id]
                    img['x'] = x
                    img['y'] = y
                    img['scale'] = scale
                    img['rotation'] = rotation
                    img['alpha'] = alpha
            else:
                if anim_id in self.characters:
                    char = self.characters[anim_id]
                    char['x'] = x
                    char['y'] = y
                    char['scale'] = scale
                    char['rotation'] = rotation
                    char['alpha'] = alpha
    
    def _draw(self, screen: pygame.Surface):
        """Отрисовка."""
        # Фон
        if self.background:
            screen.blit(self.background, (0, 0))
        elif self.background_color:
            screen.fill(self.background_color)
        else:
            screen.fill((30, 30, 40))
        
        # Картинки (по слоям)
        sorted_images = sorted(self.images.items(), key=lambda x: x[1].get('layer', 0))
        for img_id, img_data in sorted_images:
            img = img_data.get('original_image')
            if not img:
                continue
            
            # Применяем масштаб
            scale = img_data.get('scale', 1.0)
            if scale != 1.0:
                new_w = int(img.get_width() * scale)
                new_h = int(img.get_height() * scale)
                if new_w > 0 and new_h > 0:
                    img = pygame.transform.smoothscale(img, (new_w, new_h))
            
            # Поворот
            rotation = img_data.get('rotation', 0.0)
            if rotation != 0:
                img = pygame.transform.rotate(img, rotation)
            
            # Альфа
            alpha = img_data.get('alpha', 255)
            if alpha < 255:
                img = img.copy()
                img.set_alpha(alpha)
            
            x = int(img_data['x'] * self.width - img.get_width() / 2)
            y = int(img_data['y'] * self.height - img.get_height() / 2)
            screen.blit(img, (x, y))
        
        # Персонажи
        for char_id, char_data in self.characters.items():
            img = char_data.get('original_image')
            if not img:
                continue
            
            # Применяем трансформации
            scale = char_data.get('scale', 1.0)
            rotation = char_data.get('rotation', 0)
            alpha = char_data.get('alpha', 255)
            
            # Масштаб
            if scale != 1.0:
                new_w = int(img.get_width() * scale)
                new_h = int(img.get_height() * scale)
                if new_w > 0 and new_h > 0:
                    img = pygame.transform.smoothscale(img, (new_w, new_h))
            
            # Поворот
            if rotation != 0:
                img = pygame.transform.rotate(img, rotation)
            
            # Альфа
            if alpha < 255:
                img = img.copy()
                img.set_alpha(alpha)
            
            x = int(char_data['x'] * self.width - img.get_width() / 2)
            y = int(char_data['y'] * self.height - img.get_height() / 2)
            screen.blit(img, (x, y))
        
        # Диалоговое окно или выборы
        if self.show_choices:
            self._draw_choices(screen)
        else:
            self._draw_dialog_box(screen)
        
        # Подсказка
        hint_font = pygame.font.Font(None, 20)
        hint = hint_font.render("Пробел/Клик - далее | ESC - закрыть", True, (180, 180, 180))
        screen.blit(hint, (10, 10))
    
    def _draw_choices(self, screen: pygame.Surface):
        """Отрисовка меню выборов."""
        if not self.scene or not self.scene.choices:
            return
        
        self.choice_rects.clear()
        
        choice_font = pygame.font.Font(None, 32)
        choice_height = 50
        choice_spacing = 10
        total_height = len(self.scene.choices) * (choice_height + choice_spacing)
        start_y = (self.height - total_height) // 2
        choice_width = min(600, self.width - 100)
        start_x = (self.width - choice_width) // 2
        
        for i, choice in enumerate(self.scene.choices):
            y = start_y + i * (choice_height + choice_spacing)
            rect = pygame.Rect(start_x, y, choice_width, choice_height)
            self.choice_rects.append(rect)
            
            # Цвет фона
            if i == self.hovered_choice:
                bg_color = (80, 80, 120, 230)
                border_color = (150, 150, 200)
            else:
                bg_color = (40, 40, 60, 200)
                border_color = (100, 100, 140)
            
            # Рисуем кнопку
            button_surface = pygame.Surface((choice_width, choice_height), pygame.SRCALPHA)
            pygame.draw.rect(button_surface, bg_color, (0, 0, choice_width, choice_height), border_radius=8)
            pygame.draw.rect(button_surface, border_color, (0, 0, choice_width, choice_height), width=2, border_radius=8)
            screen.blit(button_surface, (start_x, y))
            
            # Текст
            text_surface = choice_font.render(choice.text, True, (255, 255, 255))
            text_x = start_x + (choice_width - text_surface.get_width()) // 2
            text_y = y + (choice_height - text_surface.get_height()) // 2
            screen.blit(text_surface, (text_x, text_y))
    
    def _draw_dialog_box(self, screen: pygame.Surface):
        """Отрисовка диалогового окна."""
        if not self.dialog_text and not self.dialog_name:
            return
        
        # Размеры окна
        box_height = 150
        box_y = self.height - box_height - 20
        box_x = 40
        box_width = self.width - 80
        
        # Фон
        box_surface = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
        pygame.draw.rect(box_surface, (20, 20, 35, 220), (0, 0, box_width, box_height), border_radius=10)
        pygame.draw.rect(box_surface, (100, 100, 140, 180), (0, 0, box_width, box_height), width=2, border_radius=10)
        screen.blit(box_surface, (box_x, box_y))
        
        # Имя персонажа
        if self.dialog_name:
            name_surface = self.name_font.render(self.dialog_name, True, self.dialog_name_color)
            # Фон под именем
            name_bg = pygame.Surface((name_surface.get_width() + 20, 30), pygame.SRCALPHA)
            pygame.draw.rect(name_bg, (40, 40, 60, 200), (0, 0, name_bg.get_width(), 30), border_radius=5)
            screen.blit(name_bg, (box_x + 15, box_y - 20))
            screen.blit(name_surface, (box_x + 25, box_y - 15))
        
        # Текст с эффектом печати
        if self.dialog_text:
            visible_len = int(len(self.dialog_text) * self.typing_progress)
            visible_text = self.dialog_text[:visible_len]
            
            # Разбиваем на строки
            words = visible_text.split(' ')
            lines = []
            current_line = ""
            max_width = box_width - 40
            
            for word in words:
                test_line = current_line + (" " if current_line else "") + word
                test_surface = self.font.render(test_line, True, (255, 255, 255))
                if test_surface.get_width() > max_width:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
                else:
                    current_line = test_line
            if current_line:
                lines.append(current_line)
            
            # Рисуем строки
            y_offset = box_y + 20
            for line in lines[:4]:  # Максимум 4 строки
                lines.append(current_line)
                text_surface = self.font.render(line, True, (255, 255, 255))
                screen.blit(text_surface, (box_x + 20, y_offset))
                y_offset += 30
        
        # Индикатор продолжения
        if self.typing_progress >= 1.0:
            indicator = "▼"
            ind_surface = self.font.render(indicator, True, (200, 200, 200))
            screen.blit(ind_surface, (box_x + box_width - 30, box_y + box_height - 30))
    
    def load_scene(self, scene, story, characters_data: Dict):
        """Загрузить сцену (вызывается из главного потока)."""
        self.command_queue.put(('load_scene', (scene, story, characters_data)))


class MenuPreview:
    """Предпросмотр главного меню с возможностью перетаскивания элементов."""
    
    def __init__(self, width: int = 960, height: int = 540):
        self.width = width
        self.height = height
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.command_queue = queue.Queue()
        
        # Конфигурация меню
        self.config = None
        self.current_screen = "main"  # "main" или "settings"
        
        # Состояние drag & drop
        self.dragging_item = None  # (type, id) - "button", "logo", "slider", "title"
        self.drag_offset = (0, 0)
        
        # Выбранный элемент
        self.selected_item = None  # (type, id)
        
        # Ресурсы
        self.background: Optional[pygame.Surface] = None
        self.logo: Optional[pygame.Surface] = None
        self.fonts = {}
        
        # Callbacks
        self.on_position_changed: Optional[Callable] = None  # (item_type, item_id, x, y)
        self.on_item_selected: Optional[Callable] = None  # (item_type, item_id)
    
    def start(self):
        """Запустить предпросмотр в отдельном потоке."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Остановить предпросмотр."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None
    
    def load_config(self, config):
        """Загрузить конфигурацию меню."""
        self.command_queue.put(('load_config', config))
    
    def set_screen(self, screen: str):
        """Переключить экран: 'main' или 'settings'."""
        self.command_queue.put(('set_screen', screen))
    
    def update_button(self, btn_id: str, **kwargs):
        """Обновить параметры кнопки."""
        self.command_queue.put(('update_button', (btn_id, kwargs)))
    
    def update_slider(self, slider_id: str, **kwargs):
        """Обновить параметры слайдера."""
        self.command_queue.put(('update_slider', (slider_id, kwargs)))
    
    def update_logo(self, **kwargs):
        """Обновить параметры логотипа."""
        self.command_queue.put(('update_logo', kwargs))
    
    def _run_loop(self):
        """Основной цикл pygame."""
        try:
            pygame.init()
            pygame.font.init()
            
            screen = pygame.display.set_mode((self.width, self.height))
            pygame.display.set_caption("Предпросмотр меню (drag & drop)")
            
            clock = pygame.time.Clock()
            
            while self.running:
                # Обработка команд
                self._process_commands()
                
                # События
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            self.running = False
                        elif event.key == pygame.K_TAB:
                            # Переключение экрана
                            self.current_screen = "settings" if self.current_screen == "main" else "main"
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:
                            self._handle_mouse_down(event.pos)
                    elif event.type == pygame.MOUSEBUTTONUP:
                        if event.button == 1:
                            self._handle_mouse_up(event.pos)
                    elif event.type == pygame.MOUSEMOTION:
                        self._handle_mouse_motion(event.pos)
                
                # Отрисовка
                self._draw(screen)
                
                pygame.display.flip()
                clock.tick(60)
        
        finally:
            try:
                pygame.quit()
            except:
                pass
            self.running = False
    
    def _process_commands(self):
        """Обработать команды из очереди."""
        while not self.command_queue.empty():
            try:
                cmd, data = self.command_queue.get_nowait()
                
                if cmd == 'load_config':
                    self._cmd_load_config(data)
                elif cmd == 'set_screen':
                    self.current_screen = data
                elif cmd == 'update_button':
                    self._cmd_update_button(data)
                elif cmd == 'update_slider':
                    self._cmd_update_slider(data)
                elif cmd == 'update_logo':
                    self._cmd_update_logo(data)
                
            except queue.Empty:
                break
    
    def _cmd_load_config(self, config):
        """Загрузить конфигурацию."""
        self.config = config
        self._load_resources()
    
    def _cmd_update_button(self, data):
        """Обновить кнопку."""
        btn_id, kwargs = data
        if not self.config:
            return
        
        for btn in self.config.buttons:
            if btn.id == btn_id:
                for key, value in kwargs.items():
                    if hasattr(btn, key):
                        setattr(btn, key, value)
                return
        
        if self.config.back_button.id == btn_id:
            for key, value in kwargs.items():
                if hasattr(self.config.back_button, key):
                    setattr(self.config.back_button, key, value)
    
    def _cmd_update_slider(self, data):
        """Обновить слайдер."""
        slider_id, kwargs = data
        if not self.config:
            return
        
        for slider in self.config.sliders:
            if slider.id == slider_id:
                for key, value in kwargs.items():
                    if hasattr(slider, key):
                        setattr(slider, key, value)
                return
    
    def _cmd_update_logo(self, kwargs):
        """Обновить логотип."""
        if not self.config:
            return
        
        for key, value in kwargs.items():
            if hasattr(self.config.logo, key):
                setattr(self.config.logo, key, value)
        
        # Перезагружаем логотип если изменился путь
        if 'image_path' in kwargs:
            self._load_logo()
    
    def _load_resources(self):
        """Загрузить ресурсы."""
        if not self.config:
            return
        
        # Фон
        if self.config.background and os.path.exists(self.config.background):
            try:
                self.background = pygame.image.load(self.config.background).convert()
                self.background = pygame.transform.smoothscale(self.background, (self.width, self.height))
            except:
                self.background = None
        else:
            self.background = None
        
        # Логотип
        self._load_logo()
    
    def _load_logo(self):
        """Загрузить логотип."""
        if not self.config:
            return
        
        if self.config.logo.image_path and os.path.exists(self.config.logo.image_path):
            try:
                self.logo = pygame.image.load(self.config.logo.image_path).convert_alpha()
                if self.config.logo.scale != 1.0:
                    new_w = int(self.logo.get_width() * self.config.logo.scale)
                    new_h = int(self.logo.get_height() * self.config.logo.scale)
                    if new_w > 0 and new_h > 0:
                        self.logo = pygame.transform.smoothscale(self.logo, (new_w, new_h))
            except:
                self.logo = None
        else:
            self.logo = None
    
    def _get_font(self, size: int) -> pygame.font.Font:
        """Получить шрифт."""
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(None, size)
        return self.fonts[size]
    
    def _hex_to_rgba(self, hex_color: str) -> Tuple[int, int, int, int]:
        """Конвертировать HEX в RGBA."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            return (r, g, b, 255)
        elif len(hex_color) == 8:
            r, g, b, a = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16), int(hex_color[6:8], 16)
            return (r, g, b, a)
        return (255, 255, 255, 255)
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Конвертировать HEX в RGB."""
        rgba = self._hex_to_rgba(hex_color)
        return (rgba[0], rgba[1], rgba[2])
    
    def _handle_mouse_down(self, pos):
        """Обработать нажатие мыши."""
        if not self.config:
            return
        
        # Проверяем логотип (только на главном экране)
        if self.current_screen == "main" and self.logo:
            logo_rect = self._get_logo_rect()
            if logo_rect.collidepoint(pos):
                self.dragging_item = ("logo", "logo")
                self.drag_offset = (pos[0] - logo_rect.centerx, pos[1] - logo_rect.centery)
                self.selected_item = ("logo", "logo")
                if self.on_item_selected:
                    self.on_item_selected("logo", "logo")
                return
        
        # Проверяем кнопки
        if self.current_screen == "main":
            for btn in self.config.buttons:
                if btn.visible:
                    rect = self._get_button_rect(btn)
                    if rect.collidepoint(pos):
                        self.dragging_item = ("button", btn.id)
                        self.drag_offset = (pos[0] - rect.centerx, pos[1] - rect.centery)
                        self.selected_item = ("button", btn.id)
                        if self.on_item_selected:
                            self.on_item_selected("button", btn.id)
                        return
        else:
            # Настройки
            # Заголовок
            title_rect = self._get_title_rect()
            if title_rect.collidepoint(pos):
                self.dragging_item = ("title", "settings_title")
                self.drag_offset = (pos[0] - title_rect.centerx, pos[1] - title_rect.centery)
                self.selected_item = ("title", "settings_title")
                if self.on_item_selected:
                    self.on_item_selected("title", "settings_title")
                return
            
            # Слайдеры
            for slider in self.config.sliders:
                track_rect = self._get_slider_track_rect(slider)
                # Расширенная область для перетаскивания (включая подпись)
                drag_rect = pygame.Rect(track_rect.x, track_rect.y - 30, track_rect.width + 60, track_rect.height + 35)
                if drag_rect.collidepoint(pos):
                    self.dragging_item = ("slider", slider.id)
                    self.drag_offset = (pos[0] - track_rect.centerx, pos[1] - track_rect.centery)
                    self.selected_item = ("slider", slider.id)
                    if self.on_item_selected:
                        self.on_item_selected("slider", slider.id)
                    return
            
            # Кнопка "Назад"
            btn = self.config.back_button
            rect = self._get_button_rect(btn)
            if rect.collidepoint(pos):
                self.dragging_item = ("button", btn.id)
                self.drag_offset = (pos[0] - rect.centerx, pos[1] - rect.centery)
                self.selected_item = ("button", btn.id)
                if self.on_item_selected:
                    self.on_item_selected("button", btn.id)
                return
        
        # Клик мимо - снимаем выделение
        self.selected_item = None
        if self.on_item_selected:
            self.on_item_selected(None, None)
    
    def _handle_mouse_up(self, pos):
        """Обработать отпускание мыши."""
        self.dragging_item = None
    
    def _handle_mouse_motion(self, pos):
        """Обработать движение мыши."""
        if not self.dragging_item or not self.config:
            return
        
        item_type, item_id = self.dragging_item
        
        # Вычисляем новую позицию (0.0 - 1.0)
        new_x = (pos[0] - self.drag_offset[0]) / self.width
        new_y = (pos[1] - self.drag_offset[1]) / self.height
        
        # Ограничиваем
        new_x = max(0.05, min(0.95, new_x))
        new_y = max(0.05, min(0.95, new_y))
        
        # Применяем
        if item_type == "logo":
            self.config.logo.x = new_x
            self.config.logo.y = new_y
        elif item_type == "button":
            for btn in self.config.buttons:
                if btn.id == item_id:
                    btn.x = new_x
                    btn.y = new_y
                    break
            if self.config.back_button.id == item_id:
                self.config.back_button.x = new_x
                self.config.back_button.y = new_y
        elif item_type == "slider":
            for slider in self.config.sliders:
                if slider.id == item_id:
                    slider.x = new_x
                    slider.y = new_y
                    break
        elif item_type == "title":
            self.config.settings_title_x = new_x
            self.config.settings_title_y = new_y
        
        # Callback
        if self.on_position_changed:
            self.on_position_changed(item_type, item_id, new_x, new_y)
    
    def _get_logo_rect(self) -> pygame.Rect:
        """Получить прямоугольник логотипа."""
        if not self.logo or not self.config:
            return pygame.Rect(0, 0, 0, 0)
        
        x = int(self.config.logo.x * self.width - self.logo.get_width() / 2)
        y = int(self.config.logo.y * self.height - self.logo.get_height() / 2)
        return pygame.Rect(x, y, self.logo.get_width(), self.logo.get_height())
    
    def _get_button_rect(self, btn) -> pygame.Rect:
        """Получить прямоугольник кнопки."""
        x = int(btn.x * self.width - btn.width / 2)
        y = int(btn.y * self.height - btn.height / 2)
        return pygame.Rect(x, y, btn.width, btn.height)
    
    def _get_slider_track_rect(self, slider) -> pygame.Rect:
        """Получить прямоугольник трека слайдера."""
        x = int(slider.x * self.width - slider.width / 2)
        y = int(slider.y * self.height - slider.height / 2)
        return pygame.Rect(x, y, slider.width, slider.height)
    
    def _get_title_rect(self) -> pygame.Rect:
        """Получить прямоугольник заголовка настроек."""
        if not self.config:
            return pygame.Rect(0, 0, 0, 0)
        
        font = self._get_font(self.config.settings_title_size)
        text_surface = font.render(self.config.settings_title, True, (255, 255, 255))
        x = int(self.config.settings_title_x * self.width - text_surface.get_width() / 2)
        y = int(self.config.settings_title_y * self.height - text_surface.get_height() / 2)
        return pygame.Rect(x, y, text_surface.get_width(), text_surface.get_height())
    
    def _draw(self, screen: pygame.Surface):
        """Отрисовка."""
        if not self.config:
            screen.fill((30, 30, 50))
            font = self._get_font(36)
            text = font.render("Загрузите конфигурацию меню", True, (150, 150, 150))
            screen.blit(text, (self.width // 2 - text.get_width() // 2, self.height // 2))
            return
        
        # Фон
        if self.background:
            screen.blit(self.background, (0, 0))
        elif self.config.background_color:
            screen.fill(self.config.background_color)
        else:
            # Градиент
            for y in range(self.height):
                color = (
                    int(20 + (y / self.height) * 30),
                    int(20 + (y / self.height) * 40),
                    int(40 + (y / self.height) * 60)
                )
                pygame.draw.line(screen, color, (0, y), (self.width, y))
        
        if self.current_screen == "main":
            self._draw_main_menu(screen)
        else:
            self._draw_settings_menu(screen)
        
        # Подсказка
        hint_font = self._get_font(20)
        hint = hint_font.render("Tab - переключить экран | Перетаскивайте элементы мышью", True, (200, 200, 200))
        screen.blit(hint, (10, self.height - 25))
    
    def _draw_main_menu(self, screen: pygame.Surface):
        """Отрисовать главное меню."""
        # Логотип
        if self.logo:
            rect = self._get_logo_rect()
            screen.blit(self.logo, rect.topleft)
            
            # Выделение
            if self.selected_item == ("logo", "logo"):
                pygame.draw.rect(screen, (255, 255, 0), rect, 2)
        
        # Заглушка для логотипа если нет изображения
        if not self.logo:
            font = self._get_font(48)
            text = font.render("[ЛОГОТИП]", True, (100, 100, 100))
            x = int(self.config.logo.x * self.width - text.get_width() / 2)
            y = int(self.config.logo.y * self.height - text.get_height() / 2)
            rect = pygame.Rect(x - 10, y - 10, text.get_width() + 20, text.get_height() + 20)
            pygame.draw.rect(screen, (50, 50, 70), rect, border_radius=10)
            pygame.draw.rect(screen, (80, 80, 100), rect, 2, border_radius=10)
            screen.blit(text, (x, y))
            
            if self.selected_item == ("logo", "logo"):
                pygame.draw.rect(screen, (255, 255, 0), rect, 2)
        
        # Кнопки
        for btn in self.config.buttons:
            if btn.visible:
                self._draw_button(screen, btn)
    
    def _draw_settings_menu(self, screen: pygame.Surface):
        """Отрисовать меню настроек."""
        # Заголовок
        font = self._get_font(self.config.settings_title_size)
        title_color = self._hex_to_rgb(self.config.settings_title_color)
        title_surface = font.render(self.config.settings_title, True, title_color)
        title_x = int(self.config.settings_title_x * self.width - title_surface.get_width() / 2)
        title_y = int(self.config.settings_title_y * self.height - title_surface.get_height() / 2)
        screen.blit(title_surface, (title_x, title_y))
        
        # Выделение заголовка
        if self.selected_item == ("title", "settings_title"):
            title_rect = self._get_title_rect()
            pygame.draw.rect(screen, (255, 255, 0), title_rect.inflate(10, 10), 2)
        
        # Слайдеры
        for slider in self.config.sliders:
            self._draw_slider(screen, slider)
        
        # Кнопка "Назад"
        self._draw_button(screen, self.config.back_button)
    
    def _draw_button(self, screen: pygame.Surface, btn):
        """Отрисовать кнопку."""
        rect = self._get_button_rect(btn)
        
        bg_color = self._hex_to_rgba(btn.bg_color)
        border_color = self._hex_to_rgb(btn.border_color)
        text_color = self._hex_to_rgb(btn.text_color)
        
        # Фон
        btn_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(btn_surface, bg_color, (0, 0, rect.width, rect.height), border_radius=btn.border_radius)
        
        # Рамка
        if btn.border_width > 0:
            pygame.draw.rect(btn_surface, border_color, (0, 0, rect.width, rect.height), btn.border_width, border_radius=btn.border_radius)
        
        screen.blit(btn_surface, rect.topleft)
        
        # Текст
        font = self._get_font(btn.font_size)
        text_surface = font.render(btn.text, True, text_color)
        text_x = rect.centerx - text_surface.get_width() // 2
        text_y = rect.centery - text_surface.get_height() // 2
        screen.blit(text_surface, (text_x, text_y))
        
        # Выделение
        if self.selected_item == ("button", btn.id):
            pygame.draw.rect(screen, (255, 255, 0), rect.inflate(4, 4), 2)
    
    def _draw_slider(self, screen: pygame.Surface, slider):
        """Отрисовать слайдер."""
        track_rect = self._get_slider_track_rect(slider)
        
        track_color = self._hex_to_rgb(slider.track_color)
        fill_color = self._hex_to_rgb(slider.fill_color)
        handle_color = self._hex_to_rgb(slider.handle_color)
        label_color = self._hex_to_rgb(slider.label_color)
        
        # Подпись
        font = self._get_font(24)
        label_surface = font.render(slider.label, True, label_color)
        screen.blit(label_surface, (track_rect.x, track_rect.y - 25))
        
        # Трек
        pygame.draw.rect(screen, track_color, track_rect, border_radius=5)
        
        # Заполнение
        relative_value = (slider.value - slider.min_value) / (slider.max_value - slider.min_value)
        fill_width = int(track_rect.width * relative_value)
        fill_rect = pygame.Rect(track_rect.x, track_rect.y, fill_width, track_rect.height)
        pygame.draw.rect(screen, fill_color, fill_rect, border_radius=5)
        
        # Ручка
        handle_x = track_rect.x + fill_width - 10
        handle_rect = pygame.Rect(handle_x, track_rect.y - 5, 20, track_rect.height + 10)
        pygame.draw.rect(screen, handle_color, handle_rect, border_radius=3)
        
        # Значение
        value_text = f"{int(slider.value * 100)}%"
        value_surface = font.render(value_text, True, label_color)
        screen.blit(value_surface, (track_rect.right + 10, track_rect.centery - value_surface.get_height() // 2))
        
        # Выделение
        if self.selected_item == ("slider", slider.id):
            select_rect = pygame.Rect(track_rect.x - 5, track_rect.y - 30, track_rect.width + 70, track_rect.height + 40)
            pygame.draw.rect(screen, (255, 255, 0), select_rect, 2)


# Тест
if __name__ == "__main__":
    preview = ScenePreview()
    preview.start()
    
    import time
    time.sleep(1)
    
    # Тестовые персонажи
    preview.add_character("test1", "Персонаж 1", "", 0.3, 0.7, "default")
    preview.add_character("test2", "Персонаж 2", "", 0.7, 0.7, "default")
    
    # Ждём пока окно не закроется
    while preview.running:
        time.sleep(0.1)


class PauseMenuPreview:
    """Превью меню паузы с drag & drop."""
    
    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height
        self.running = False
        self.thread = None
        self.config = None
        self.current_screen = "main"
        self.selected_element = None
        self.dragging = False
        self.drag_offset = (0, 0)
        self.command_queue = queue.Queue()
        self.on_position_changed = None
        self.on_element_selected = None
        self.fonts = {}
    
    def _get_font(self, size: int) -> pygame.font.Font:
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(None, size)
        return self.fonts[size]
    
    def _parse_color(self, color_str: str) -> Tuple[int, int, int, int]:
        color_str = color_str.lstrip('#')
        if len(color_str) == 6:
            r, g, b = int(color_str[0:2], 16), int(color_str[2:4], 16), int(color_str[4:6], 16)
            return (r, g, b, 255)
        elif len(color_str) == 8:
            r, g, b = int(color_str[0:2], 16), int(color_str[2:4], 16), int(color_str[4:6], 16)
            a = int(color_str[6:8], 16)
            return (r, g, b, a)
        return (255, 255, 255, 255)
    
    def load_config(self, config):
        self.config = config
    
    def set_screen(self, screen_name: str):
        self.current_screen = screen_name
        self.command_queue.put(("set_screen", screen_name))
    
    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
    
    def _run(self):
        pygame.init()
        screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Превью меню паузы")
        clock = pygame.time.Clock()
        
        while self.running:
            while not self.command_queue.empty():
                try:
                    cmd, args = self.command_queue.get_nowait()
                    if cmd == "set_screen":
                        self.current_screen = args
                except queue.Empty:
                    break
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_mouse_down(event.pos)
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self.dragging = False
                elif event.type == pygame.MOUSEMOTION and self.dragging:
                    self._handle_drag(event.pos)
            
            self._draw(screen)
            pygame.display.flip()
            clock.tick(60)
        pygame.quit()
    
    def _get_panel_rect(self) -> pygame.Rect:
        if not self.config:
            return pygame.Rect(self.width // 2 - 200, self.height // 2 - 250, 400, 500)
        x = int(self.config.panel_x * self.width) - self.config.panel_width // 2
        y = int(self.config.panel_y * self.height) - self.config.panel_height // 2
        return pygame.Rect(x, y, self.config.panel_width, self.config.panel_height)
    
    def _get_button_rect(self, button, panel_rect=None) -> pygame.Rect:
        if panel_rect:
            x = panel_rect.x + int(button.x * panel_rect.width) - button.width // 2
            y = panel_rect.y + int(button.y * panel_rect.height) - button.height // 2
        else:
            x = int(button.x * self.width) - button.width // 2
            y = int(button.y * self.height) - button.height // 2
        return pygame.Rect(x, y, button.width, button.height)
    
    def _get_slider_rect(self, slider) -> pygame.Rect:
        x = int(slider.x * self.width) - slider.width // 2
        y = int(slider.y * self.height) - slider.height // 2
        return pygame.Rect(x, y, slider.width, slider.height)
    
    def _get_slot_rect(self, slot_index: int) -> pygame.Rect:
        if not self.config:
            return pygame.Rect(0, 0, 0, 0)
        sl = self.config.save_load_screen
        row, col = slot_index // 2, slot_index % 2
        x = int(sl.slots_start_x * self.width) + col * sl.slots_spacing_x
        y = int(sl.slots_start_y * self.height) + row * sl.slots_spacing_y
        return pygame.Rect(x, y, sl.slot_config.width, sl.slot_config.height)
    
    def _handle_mouse_down(self, pos):
        if not self.config:
            return
        panel_rect = self._get_panel_rect()
        self.selected_element = None
        
        if self.current_screen == "main":
            if panel_rect.collidepoint(pos):
                inner = panel_rect.inflate(-40, -40)
                if not inner.collidepoint(pos):
                    self.selected_element = ("panel", "main")
                    self.dragging = True
                    self.drag_offset = (pos[0] - panel_rect.centerx, pos[1] - panel_rect.centery)
                    return
            for btn in self.config.buttons:
                rect = self._get_button_rect(btn, panel_rect)
                if rect.collidepoint(pos):
                    self.selected_element = ("button", btn.id)
                    self.dragging = True
                    self.drag_offset = (pos[0] - rect.centerx, pos[1] - rect.centery)
                    return
        elif self.current_screen == "settings":
            for slider in self.config.settings_sliders:
                rect = self._get_slider_rect(slider)
                if rect.collidepoint(pos):
                    self.selected_element = ("slider", slider.id)
                    self.dragging = True
                    self.drag_offset = (pos[0] - rect.centerx, pos[1] - rect.centery)
                    return
            rect = self._get_button_rect(self.config.settings_back_button)
            if rect.collidepoint(pos):
                self.selected_element = ("button", self.config.settings_back_button.id)
                self.dragging = True
                self.drag_offset = (pos[0] - rect.centerx, pos[1] - rect.centery)
        elif self.current_screen in ("save", "load"):
            sl = self.config.save_load_screen
            for i in range(4):
                rect = self._get_slot_rect(i)
                if rect.collidepoint(pos):
                    self.selected_element = ("slot_grid", "grid")
                    self.dragging = True
                    gx = int(sl.slots_start_x * self.width)
                    gy = int(sl.slots_start_y * self.height)
                    self.drag_offset = (pos[0] - gx, pos[1] - gy)
                    return
            rect = self._get_button_rect(sl.back_button)
            if rect.collidepoint(pos):
                self.selected_element = ("button", sl.back_button.id)
                self.dragging = True
                self.drag_offset = (pos[0] - rect.centerx, pos[1] - rect.centery)
    
    def _handle_drag(self, pos):
        if not self.config or not self.selected_element:
            return
        elem_type, elem_id = self.selected_element
        new_x = max(0.05, min(0.95, (pos[0] - self.drag_offset[0]) / self.width))
        new_y = max(0.05, min(0.95, (pos[1] - self.drag_offset[1]) / self.height))
        panel_rect = self._get_panel_rect()
        
        if elem_type == "panel":
            self.config.panel_x, self.config.panel_y = new_x, new_y
            if self.on_position_changed:
                self.on_position_changed("panel", "main", new_x, new_y)
        elif elem_type == "button":
            if self.current_screen == "main":
                for btn in self.config.buttons:
                    if btn.id == elem_id:
                        btn.x = max(0.1, min(0.9, (pos[0] - self.drag_offset[0] - panel_rect.x) / panel_rect.width))
                        btn.y = max(0.1, min(0.9, (pos[1] - self.drag_offset[1] - panel_rect.y) / panel_rect.height))
                        if self.on_position_changed:
                            self.on_position_changed("button", btn.id, btn.x, btn.y)
                        break
            elif self.current_screen == "settings" and elem_id == self.config.settings_back_button.id:
                self.config.settings_back_button.x, self.config.settings_back_button.y = new_x, new_y
                if self.on_position_changed:
                    self.on_position_changed("button", elem_id, new_x, new_y)
            elif self.current_screen in ("save", "load") and elem_id == self.config.save_load_screen.back_button.id:
                self.config.save_load_screen.back_button.x = new_x
                self.config.save_load_screen.back_button.y = new_y
                if self.on_position_changed:
                    self.on_position_changed("button", elem_id, new_x, new_y)
        elif elem_type == "slider":
            for slider in self.config.settings_sliders:
                if slider.id == elem_id:
                    slider.x, slider.y = new_x, new_y
                    if self.on_position_changed:
                        self.on_position_changed("slider", elem_id, new_x, new_y)
                    break
        elif elem_type == "slot_grid":
            self.config.save_load_screen.slots_start_x = new_x
            self.config.save_load_screen.slots_start_y = new_y
            if self.on_position_changed:
                self.on_position_changed("slot_grid", "grid", new_x, new_y)
    
    def _draw(self, screen):
        screen.fill((30, 30, 50))
        if self.config:
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            c = self._parse_color(self.config.overlay_color)
            overlay.fill((c[0], c[1], c[2], self.config.overlay_alpha))
            screen.blit(overlay, (0, 0))
        
        if self.current_screen == "main":
            self._draw_main(screen)
        elif self.current_screen == "settings":
            self._draw_settings(screen)
        elif self.current_screen in ("save", "load"):
            self._draw_save_load(screen)
        
        hint = self._get_font(20).render("Перетаскивайте элементы", True, (200, 200, 200))
        screen.blit(hint, (10, self.height - 30))
    
    def _draw_main(self, screen):
        if not self.config:
            return
        panel_rect = self._get_panel_rect()
        sel = self.selected_element == ("panel", "main")
        
        ps = pygame.Surface((panel_rect.width, panel_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(ps, self._parse_color(self.config.panel_bg_color), ps.get_rect(), border_radius=self.config.panel_border_radius)
        bc = (255, 200, 0) if sel else self._parse_color(self.config.panel_border_color)[:3]
        pygame.draw.rect(ps, bc, ps.get_rect(), width=self.config.panel_border_width + (2 if sel else 0), border_radius=self.config.panel_border_radius)
        screen.blit(ps, panel_rect.topleft)
        
        tf = self._get_font(self.config.title_size)
        ts = tf.render(self.config.title, True, self._parse_color(self.config.title_color)[:3])
        tx = panel_rect.x + int(self.config.title_x * panel_rect.width) - ts.get_width() // 2
        ty = panel_rect.y + int(self.config.title_y * panel_rect.height)
        screen.blit(ts, (tx, ty))
        
        for btn in self.config.buttons:
            if btn.visible:
                self._draw_btn(screen, btn, panel_rect)
    
    def _draw_settings(self, screen):
        if not self.config:
            return
        tf = self._get_font(self.config.settings_title_size)
        ts = tf.render(self.config.settings_title, True, self._parse_color(self.config.settings_title_color)[:3])
        tx = int(self.config.settings_title_x * self.width) - ts.get_width() // 2
        ty = int(self.config.settings_title_y * self.height)
        screen.blit(ts, (tx, ty))
        
        for slider in self.config.settings_sliders:
            self._draw_slider(screen, slider)
        self._draw_btn(screen, self.config.settings_back_button)
    
    def _draw_save_load(self, screen):
        if not self.config:
            return
        sl = self.config.save_load_screen
        title = sl.title_save if self.current_screen == "save" else sl.title_load
        tf = self._get_font(sl.title_size)
        ts = tf.render(title, True, self._parse_color(sl.title_color)[:3])
        tx = int(sl.title_x * self.width) - ts.get_width() // 2
        ty = int(sl.title_y * self.height)
        screen.blit(ts, (tx, ty))
        
        sel = self.selected_element == ("slot_grid", "grid")
        for i in range(4):
            rect = self._get_slot_rect(i)
            sc = sl.slot_config
            ss = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            pygame.draw.rect(ss, self._parse_color(sc.empty_color), ss.get_rect(), border_radius=sc.border_radius)
            bc = (255, 200, 0) if sel else self._parse_color(sc.border_color)[:3]
            pygame.draw.rect(ss, bc, ss.get_rect(), width=sc.border_width + (2 if sel else 0), border_radius=sc.border_radius)
            screen.blit(ss, rect.topleft)
            
            f = self._get_font(sc.font_size)
            t = f.render(sc.empty_text, True, self._parse_color(sc.text_color)[:3])
            screen.blit(t, (rect.centerx - t.get_width() // 2, rect.centery - t.get_height() // 2))
            sn = f.render(f"Слот {i + 1}", True, (150, 150, 180))
            screen.blit(sn, (rect.x + 10, rect.y + 10))
        
        self._draw_btn(screen, sl.back_button)
    
    def _draw_btn(self, screen, btn, panel_rect=None):
        rect = self._get_button_rect(btn, panel_rect)
        sel = self.selected_element == ("button", btn.id)
        bs = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(bs, self._parse_color(btn.bg_color), bs.get_rect(), border_radius=btn.border_radius)
        bc = (255, 200, 0) if sel else self._parse_color(btn.border_color)[:3]
        pygame.draw.rect(bs, bc, bs.get_rect(), width=btn.border_width + (2 if sel else 0), border_radius=btn.border_radius)
        screen.blit(bs, rect.topleft)
        f = self._get_font(btn.font_size)
        t = f.render(btn.text, True, self._parse_color(btn.text_color)[:3])
        screen.blit(t, (rect.centerx - t.get_width() // 2, rect.centery - t.get_height() // 2))
    
    def _draw_slider(self, screen, slider):
        rect = self._get_slider_rect(slider)
        sel = self.selected_element == ("slider", slider.id)
        lf = self._get_font(24)
        lc = (255, 200, 0) if sel else self._parse_color(slider.label_color)[:3]
        screen.blit(lf.render(slider.label, True, lc), (rect.x, rect.y - 30))
        pygame.draw.rect(screen, self._parse_color(slider.track_color)[:3], rect, border_radius=5)
        fw = int(slider.value * rect.width)
        pygame.draw.rect(screen, self._parse_color(slider.fill_color)[:3], pygame.Rect(rect.x, rect.y, fw, rect.height), border_radius=5)
        if sel:
            pygame.draw.rect(screen, (255, 200, 0), rect.inflate(6, 6), 2, border_radius=7)
        hx = rect.x + fw - 10
        pygame.draw.rect(screen, self._parse_color(slider.handle_color)[:3], pygame.Rect(hx, rect.y - 5, 20, rect.height + 10), border_radius=3)
    
    def refresh(self):
        self.command_queue.put(("refresh", None))
