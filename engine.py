"""
Движок визуальной новеллы на pygame.
Отображает фоны, персонажей, диалоги, обрабатывает выборы.
"""

import pygame
import os
from typing import Optional, Tuple, List, Dict
from story import Story, Scene, Character, Choice, DialogLine


class TextRenderer:
    """Рендерер текста с поддержкой переноса строк."""
    
    def __init__(self, font: pygame.font.Font, max_width: int, color: Tuple[int, int, int] = (255, 255, 255)):
        self.font = font
        self.max_width = max_width
        self.color = color
    
    def wrap_text(self, text: str) -> List[str]:
        """Разбить текст на строки по ширине."""
        words = text.split(' ')
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if self.font.size(test_line)[0] <= self.max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines if lines else [""]
    
    def render(self, surface: pygame.Surface, text: str, pos: Tuple[int, int], color: Optional[Tuple[int, int, int]] = None):
        """Отрендерить текст с переносом строк."""
        if color is None:
            color = self.color
        
        lines = self.wrap_text(text)
        y = pos[1]
        line_height = self.font.get_height() + 5
        
        for line in lines:
            text_surface = self.font.render(line, True, color)
            surface.blit(text_surface, (pos[0], y))
            y += line_height
        
        return y - pos[1]  # Возвращаем высоту отрендеренного текста


class DialogBox:
    """Диалоговое окно."""
    
    def __init__(self, screen_width: int, screen_height: int):
        self.width = screen_width - 40
        self.height = 200
        self.x = 20
        self.y = screen_height - self.height - 20
        
        # Цвета (могут быть изменены через set_colors)
        self.bg_color = (20, 20, 40, 144)
        self.border_color = (100, 100, 150)
        self.text_color = (255, 255, 255)
        
        # Шрифты
        pygame.font.init()
        self.name_font = pygame.font.Font(None, 36)
        self.text_font = pygame.font.Font(None, 28)
        self.text_renderer = TextRenderer(self.text_font, self.width - 40)
        
        # Анимация текста
        self.full_text = ""
        self.displayed_text = ""
        self.char_index = 0
        self.text_speed = 2  # Символов за кадр
        self.is_complete = True
        
        # Текущий диалог
        self.current_name = ""
        self.current_name_color = (255, 255, 255)
        self.current_name_bg_color: Optional[Tuple[int, int, int, int]] = None  # Фон под именем
    
    def set_colors(self, bg_color: Tuple, border_color: Tuple, text_color: Tuple):
        """Установить цвета панели."""
        self.bg_color = bg_color
        self.border_color = border_color
        self.text_color = text_color
    
    def set_dialog(self, name: str, text: str, name_color: Tuple[int, int, int] = (255, 255, 255), 
                   name_bg_color: Optional[Tuple[int, int, int, int]] = None,
                   typing_duration: Optional[float] = None):
        """Установить новый диалог.
        
        Args:
            typing_duration: Длительность появления текста в секундах. None = авто, 0 = мгновенно
        """
        self.current_name = name
        self.current_name_color = name_color
        self.current_name_bg_color = name_bg_color
        self.full_text = text
        self.displayed_text = ""
        self.char_index = 0
        
        # Устанавливаем скорость печати
        text_len = len(text) if text else 1
        if typing_duration is not None:
            if typing_duration == 0:
                # Мгновенное отображение
                self.text_speed = text_len + 1
            else:
                # Рассчитываем символов/кадр исходя из длительности и FPS=60
                total_frames = typing_duration * 60
                self.text_speed = text_len / total_frames if total_frames > 0 else text_len
        else:
            # По умолчанию ~1 символ/кадр (60 символов/сек)
            self.text_speed = 1
        
        self.is_complete = False
    
    def update(self):
        """Обновить анимацию текста."""
        if not self.is_complete:
            self.char_index += self.text_speed
            if self.char_index >= len(self.full_text):
                self.char_index = len(self.full_text)
                self.is_complete = True
            self.displayed_text = self.full_text[:int(self.char_index)]
    
    def skip_animation(self):
        """Пропустить анимацию и показать весь текст."""
        self.displayed_text = self.full_text
        self.char_index = len(self.full_text)
        self.is_complete = True
    
    def draw(self, screen: pygame.Surface):
        """Отрисовать диалоговое окно."""
        # Полупрозрачный фон
        dialog_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.rect(dialog_surface, self.bg_color, (0, 0, self.width, self.height), border_radius=10)
        pygame.draw.rect(dialog_surface, self.border_color, (0, 0, self.width, self.height), 3, border_radius=10)
        screen.blit(dialog_surface, (self.x, self.y))
        
        # Имя персонажа
        if self.current_name:
            name_surface = self.name_font.render(self.current_name, True, self.current_name_color)
            name_width = name_surface.get_width()
            name_height = name_surface.get_height()
            
            # Фон под именем
            if self.current_name_bg_color:
                name_bg_surface = pygame.Surface((name_width + 20, name_height + 10), pygame.SRCALPHA)
                pygame.draw.rect(name_bg_surface, self.current_name_bg_color, 
                               (0, 0, name_width + 20, name_height + 10), border_radius=5)
                screen.blit(name_bg_surface, (self.x + 10, self.y + 10))
                screen.blit(name_surface, (self.x + 20, self.y + 15))
            else:
                screen.blit(name_surface, (self.x + 20, self.y + 15))
            text_y = self.y + 55
        else:
            text_y = self.y + 25
        
        # Текст диалога
        self.text_renderer.render(screen, self.displayed_text, (self.x + 20, text_y), self.text_color)
        
        # Индикатор продолжения (стрелка)
        if self.is_complete:
            indicator_x = self.x + self.width - 40
            indicator_y = self.y + self.height - 30
            pygame.draw.polygon(screen, (255, 255, 255), [
                (indicator_x, indicator_y),
                (indicator_x + 15, indicator_y),
                (indicator_x + 7, indicator_y + 10)
            ])
    
    def draw_skip_button(self, screen: pygame.Surface, is_active: bool = False):
        """Отрисовать кнопку Skip."""
        # Кнопка слева от стрелки продолжения
        btn_w, btn_h = 50, 24
        btn_x = self.x + self.width - 100
        btn_y = self.y + self.height - 35
        
        # Цвет зависит от состояния
        if is_active:
            bg_color = (255, 200, 50, 200)
            text_color = (0, 0, 0)
        else:
            bg_color = (80, 80, 100, 180)
            text_color = (200, 200, 200)
        
        # Фон кнопки
        btn_surface = pygame.Surface((btn_w, btn_h), pygame.SRCALPHA)
        btn_surface.fill(bg_color)
        screen.blit(btn_surface, (btn_x, btn_y))
        
        # Рамка
        pygame.draw.rect(screen, (150, 150, 180), (btn_x, btn_y, btn_w, btn_h), 1)
        
        # Текст "▶▶"
        font = pygame.font.Font(None, 20)
        text = font.render("▶▶", True, text_color)
        text_rect = text.get_rect(center=(btn_x + btn_w // 2, btn_y + btn_h // 2))
        screen.blit(text, text_rect)
        
        return pygame.Rect(btn_x, btn_y, btn_w, btn_h)  # Возвращаем прямоугольник для проверки клика


class ChoiceMenu:
    """Меню выбора."""
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.choices: List[Choice] = []
        self.selected_index = 0
        self.is_active = False
        
        pygame.font.init()
        self.font = pygame.font.Font(None, 32)
        
        self.bg_color = (30, 30, 50, 230)
        self.selected_color = (80, 120, 200)
        self.text_color = (255, 255, 255)
        self.hover_color = (60, 80, 140)
    
    def set_choices(self, choices: List[Choice]):
        """Установить варианты выбора."""
        self.choices = choices
        self.selected_index = 0
        self.is_active = len(choices) > 0
    
    def handle_input(self, event: pygame.event.Event) -> Optional[str]:
        """Обработать ввод. Возвращает ID следующей сцены или None."""
        if not self.is_active:
            return None
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected_index = (self.selected_index - 1) % len(self.choices)
            elif event.key == pygame.K_DOWN:
                self.selected_index = (self.selected_index + 1) % len(self.choices)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                return self.choices[self.selected_index].next_scene_id
        
        elif event.type == pygame.MOUSEMOTION:
            self._update_hover(event.pos)
        
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            idx = self._get_choice_at_pos(event.pos)
            if idx is not None:
                return self.choices[idx].next_scene_id
        
        return None
    
    def _get_choice_rect(self, index: int) -> pygame.Rect:
        """Получить прямоугольник варианта выбора."""
        choice_height = 50
        choice_width = 500
        total_height = len(self.choices) * (choice_height + 10)
        start_y = (self.screen_height - total_height) // 2
        
        x = (self.screen_width - choice_width) // 2
        y = start_y + index * (choice_height + 10)
        
        return pygame.Rect(x, y, choice_width, choice_height)
    
    def _update_hover(self, pos: Tuple[int, int]):
        """Обновить выбор при наведении мыши."""
        for i in range(len(self.choices)):
            if self._get_choice_rect(i).collidepoint(pos):
                self.selected_index = i
                break
    
    def _get_choice_at_pos(self, pos: Tuple[int, int]) -> Optional[int]:
        """Получить индекс варианта под курсором."""
        for i in range(len(self.choices)):
            if self._get_choice_rect(i).collidepoint(pos):
                return i
        return None
    
    def draw(self, screen: pygame.Surface):
        """Отрисовать меню выбора."""
        if not self.is_active:
            return
        
        # Затемнение фона
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, 0))
        
        # Отрисовка вариантов
        for i, choice in enumerate(self.choices):
            rect = self._get_choice_rect(i)
            
            # Фон варианта
            color = self.selected_color if i == self.selected_index else self.bg_color
            choice_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            pygame.draw.rect(choice_surface, color, (0, 0, rect.width, rect.height), border_radius=8)
            screen.blit(choice_surface, rect.topleft)
            
            # Рамка
            pygame.draw.rect(screen, (150, 150, 200), rect, 2, border_radius=8)
            
            # Текст
            text_surface = self.font.render(choice.text, True, self.text_color)
            text_rect = text_surface.get_rect(center=rect.center)
            screen.blit(text_surface, text_rect)


class CharacterSprite:
    """Спрайт персонажа на экране."""
    
    POSITIONS = {
        'left': 0.2,
        'center': 0.5,
        'right': 0.8
    }
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.image: Optional[pygame.Surface] = None
        self.original_image: Optional[pygame.Surface] = None  # Для трансформаций
        self.position = 'center'
        self.x: float = 0.5  # Точная позиция X (0.0 - 1.0)
        self.y: float = 0.7  # Точная позиция Y (0.0 - 1.0)
        self.rotation: float = 0.0  # Угол поворота в градусах
        self.flip_x: bool = False  # Отзеркаливание по горизонтали
        self.flip_y: bool = False  # Отзеркаливание по вертикали
        self.scale: float = 1.0  # Масштаб
        self.skew_x: float = 0.0  # Перспектива/наклон по X
        self.skew_y: float = 0.0  # Перспектива/наклон по Y
        self.alpha = 255
        self.use_exact_position = False  # Использовать точные координаты
        self.character_id: Optional[str] = None
    
    def load_image(self, path: str) -> bool:
        """Загрузить изображение персонажа."""
        if not path or not os.path.exists(path):
            self.image = None
            self.original_image = None
            return False
        
        try:
            img = pygame.image.load(path).convert_alpha()
            # Масштабируем большие картинки под размер экрана
            scale_h = self.screen_height * 0.9 / max(img.get_height(), 1)
            scale_w = self.screen_width * 0.9 / max(img.get_width(), 1)
            base_scale = min(scale_h, scale_w, 1.0)  # Не увеличиваем маленькие
            if base_scale < 1.0:
                new_w = int(img.get_width() * base_scale)
                new_h = int(img.get_height() * base_scale)
                if new_w > 0 and new_h > 0:
                    img = pygame.transform.smoothscale(img, (new_w, new_h))
            self.original_image = img
            self.image = self.original_image
            self._apply_transforms()
            return True
        except pygame.error:
            self.image = None
            self.original_image = None
            return False
    
    def set_rotation(self, angle: float):
        """Установить угол поворота."""
        self.rotation = angle
        self._apply_transforms()
    
    def set_flip(self, flip_x: bool, flip_y: bool):
        """Установить отзеркаливание."""
        self.flip_x = flip_x
        self.flip_y = flip_y
        self._apply_transforms()
    
    def set_scale(self, scale: float):
        """Установить масштаб."""
        self.scale = scale
        self._apply_transforms()
    
    def set_skew(self, skew_x: float, skew_y: float):
        """Установить перспективу."""
        self.skew_x = skew_x
        self.skew_y = skew_y
        self._apply_transforms()
    
    def _apply_skew(self, surface: pygame.Surface, skew_x: float, skew_y: float) -> pygame.Surface:
        """Применить эффект перспективы (наклон)."""
        w, h = surface.get_size()
        
        dx = int(w * abs(skew_x))
        dy = int(h * abs(skew_y))
        
        new_w = w + dx
        new_h = h + dy
        
        new_surface = pygame.Surface((new_w, new_h), pygame.SRCALPHA)
        
        for y in range(h):
            if skew_x >= 0:
                offset_x = int(skew_x * w * (1 - y / h))
            else:
                offset_x = int(-skew_x * w * (y / h))
            
            if skew_y >= 0:
                offset_y = int(skew_y * h * (1 - y / h))
            else:
                offset_y = int(-skew_y * h * (y / h))
            
            line = surface.subsurface((0, y, w, 1))
            new_surface.blit(line, (offset_x, y + offset_y))
        
        return new_surface
    
    def _apply_transforms(self):
        """Применить все трансформации к изображению."""
        if not self.original_image:
            return
        
        img = self.original_image
        
        # 1. Масштабирование
        if self.scale != 1.0:
            new_w = int(img.get_width() * self.scale)
            new_h = int(img.get_height() * self.scale)
            if new_w > 0 and new_h > 0:
                img = pygame.transform.smoothscale(img, (new_w, new_h))
        
        # 2. Отзеркаливание
        if self.flip_x or self.flip_y:
            img = pygame.transform.flip(img, self.flip_x, self.flip_y)
        
        # 3. Перспектива (skew)
        if self.skew_x != 0 or self.skew_y != 0:
            img = self._apply_skew(img, self.skew_x, self.skew_y)
        
        # 4. Поворот
        if self.rotation != 0:
            img = pygame.transform.rotate(img, self.rotation)
        
        self.image = img
    
    def set_position(self, position):
        """Установить позицию (left, center, right или точные координаты)."""
        if isinstance(position, str):
            self.position = position if position in self.POSITIONS else 'center'
            self.use_exact_position = False
        elif isinstance(position, (tuple, list)) and len(position) >= 2:
            self.x = position[0]
            self.y = position[1]
            self.use_exact_position = True
    
    def set_exact_position(self, x: float, y: float, rotation: float = 0.0, flip_x: bool = False, flip_y: bool = False,
                           scale: float = 1.0, skew_x: float = 0.0, skew_y: float = 0.0):
        """Установить точную позицию и все трансформации."""
        self.x = x
        self.y = y
        self.use_exact_position = True
        needs_transform = False
        if rotation != self.rotation:
            self.rotation = rotation
            needs_transform = True
        if flip_x != self.flip_x or flip_y != self.flip_y:
            self.flip_x = flip_x
            self.flip_y = flip_y
            needs_transform = True
        if scale != self.scale:
            self.scale = scale
            needs_transform = True
        if skew_x != self.skew_x or skew_y != self.skew_y:
            self.skew_x = skew_x
            self.skew_y = skew_y
            needs_transform = True
        if needs_transform:
            self._apply_transforms()
    
    def draw(self, screen: pygame.Surface):
        """Отрисовать персонажа."""
        if self.image is None:
            return
        
        if self.use_exact_position:
            # Точная позиция
            x = int(self.x * self.screen_width - self.image.get_width() / 2)
            y = int(self.y * self.screen_height - self.image.get_height() / 2)
        else:
            # Позиция по названию
            x_ratio = self.POSITIONS.get(self.position, 0.5)
            x = int(self.screen_width * x_ratio - self.image.get_width() / 2)
            y = self.screen_height - self.image.get_height() - 220  # Над диалоговым окном
        
        screen.blit(self.image, (x, y))


class ImageSprite:
    """Спрайт картинки на сцене."""
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.image: Optional[pygame.Surface] = None
        self.original_image: Optional[pygame.Surface] = None
        self.image_id: str = ""
        self.x: float = 0.5
        self.y: float = 0.5
        self.rotation: float = 0.0
        self.flip_x: bool = False
        self.flip_y: bool = False
        self.scale: float = 1.0
        self.skew_x: float = 0.0
        self.skew_y: float = 0.0
        self.layer: int = 0
        self.alpha = 255
    
    def load_image(self, path: str) -> bool:
        """Загрузить изображение."""
        if not path or not os.path.exists(path):
            self.image = None
            self.original_image = None
            return False
        
        try:
            img = pygame.image.load(path).convert_alpha()
            # Масштабируем большие картинки под размер экрана
            scale_h = self.screen_height * 0.9 / max(img.get_height(), 1)
            scale_w = self.screen_width * 0.9 / max(img.get_width(), 1)
            base_scale = min(scale_h, scale_w, 1.0)  # Не увеличиваем маленькие
            if base_scale < 1.0:
                new_w = int(img.get_width() * base_scale)
                new_h = int(img.get_height() * base_scale)
                if new_w > 0 and new_h > 0:
                    img = pygame.transform.smoothscale(img, (new_w, new_h))
            self.original_image = img
            self.image = self.original_image
            self._apply_transforms()
            return True
        except pygame.error:
            self.image = None
            self.original_image = None
            return False
    
    def set_transform(self, x: float, y: float, rotation: float = 0.0, 
                      flip_x: bool = False, flip_y: bool = False,
                      scale: float = 1.0, skew_x: float = 0.0, skew_y: float = 0.0,
                      layer: int = 0):
        """Установить все трансформации."""
        self.x = x
        self.y = y
        self.rotation = rotation
        self.flip_x = flip_x
        self.flip_y = flip_y
        self.scale = scale
        self.skew_x = skew_x
        self.skew_y = skew_y
        self.layer = layer
        self._apply_transforms()
    
    def _apply_transforms(self):
        """Применить все трансформации к изображению."""
        if self.original_image is None:
            return
        
        img = self.original_image
        
        # 1. Масштабирование
        if self.scale != 1.0:
            new_w = int(img.get_width() * self.scale)
            new_h = int(img.get_height() * self.scale)
            if new_w > 0 and new_h > 0:
                img = pygame.transform.smoothscale(img, (new_w, new_h))
        
        # 2. Отзеркаливание
        if self.flip_x or self.flip_y:
            img = pygame.transform.flip(img, self.flip_x, self.flip_y)
        
        # 3. Перспектива
        if self.skew_x != 0 or self.skew_y != 0:
            img = self._apply_skew(img, self.skew_x, self.skew_y)
        
        # 4. Поворот
        if self.rotation != 0:
            img = pygame.transform.rotate(img, self.rotation)
        
        self.image = img
    
    def _apply_skew(self, surface: pygame.Surface, skew_x: float, skew_y: float) -> pygame.Surface:
        """Применить эффект перспективы."""
        w, h = surface.get_size()
        dx = int(w * abs(skew_x))
        dy = int(h * abs(skew_y))
        new_w = w + dx
        new_h = h + dy
        new_surface = pygame.Surface((new_w, new_h), pygame.SRCALPHA)
        
        for y in range(h):
            if skew_x >= 0:
                offset_x = int(skew_x * w * (1 - y / h))
            else:
                offset_x = int(-skew_x * w * (y / h))
            
            if skew_y >= 0:
                offset_y = int(skew_y * h * (1 - y / h))
            else:
                offset_y = int(-skew_y * h * (y / h))
            
            line = surface.subsurface((0, y, w, 1))
            new_surface.blit(line, (offset_x, y + offset_y))
        
        return new_surface
    
    def draw(self, screen: pygame.Surface):
        """Отрисовать картинку."""
        if self.image is None:
            return
        
        x = int(self.x * self.screen_width - self.image.get_width() / 2)
        y = int(self.y * self.screen_height - self.image.get_height() / 2)
        
        # Применяем alpha если нужно
        if self.alpha < 255:
            img = self.image.copy()
            img.set_alpha(self.alpha)
            screen.blit(img, (x, y))
        else:
            screen.blit(self.image, (x, y))


class TextSprite:
    """Текстовый элемент на сцене с поддержкой анимации."""
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.text_id: str = ""
        self.text: str = ""
        self.x: float = 0.5
        self.y: float = 0.5
        self.font_size: int = 36
        self.color: Tuple[int, int, int] = (255, 255, 255)
        self.outline_color: Optional[Tuple[int, int, int]] = (0, 0, 0)
        self.outline_width: int = 2
        self.alpha: int = 255
        self.rotation: float = 0.0
        self.scale: float = 1.0
        
        # Анимация
        self.animation: str = "none"  # "none", "fade_in", "fade_out", "fade_in_out"
        self.fade_in_duration: float = 1.0  # Длительность появления
        self.fade_out_duration: float = 1.0  # Длительность исчезновения
        self.hold_duration: float = 2.0  # Время показа между fade_in и fade_out
        self.block_skip: bool = False  # Блокировать пропуск во время анимации
        self.order: int = 0  # Порядок запуска (меньше = раньше)
        
        self.animation_start_time: Optional[int] = None
        self.animation_phase: str = "waiting"  # "waiting", "fade_in", "hold", "fade_out", "complete"
        self.animation_complete: bool = False
        self.started: bool = False  # Началась ли анимация
        self.visible: bool = False  # Виден ли текст
        
        self.font: Optional[pygame.font.Font] = None
        self.surface: Optional[pygame.Surface] = None
    
    def setup(self, text_id: str, text: str, x: float, y: float, font_size: int = 36,
              color: str = "#FFFFFF", outline_color: str = "#000000", outline_width: int = 2,
              animation: str = "none", animation_duration: float = 1.0, block_skip: bool = False,
              rotation: float = 0.0, scale: float = 1.0, order: int = 0,
              fade_in_duration: float = 1.0, fade_out_duration: float = 1.0, hold_duration: float = 2.0):
        """Настроить текстовый элемент."""
        self.text_id = text_id
        self.text = text
        self.x = x
        self.y = y
        self.font_size = font_size
        self.rotation = rotation
        self.scale = scale
        self.animation = animation
        self.block_skip = block_skip
        self.order = order
        
        # Длительности анимации
        # Для обратной совместимости: если указан animation_duration, используем его для fade_in
        self.fade_in_duration = fade_in_duration if fade_in_duration != 1.0 else animation_duration
        self.fade_out_duration = fade_out_duration
        self.hold_duration = hold_duration
        
        # Парсинг цветов
        self.color = self._parse_color(color)
        self.outline_color = self._parse_color(outline_color) if outline_color else None
        self.outline_width = outline_width
        
        # Создаём шрифт
        pygame.font.init()
        self.font = pygame.font.Font(None, font_size)
        
        # Инициализация состояния анимации
        self.started = False
        self.animation_complete = False
        
        if animation == "none":
            self.alpha = 255
            self.animation_complete = True
            self.started = True
            self.visible = True
            self.animation_phase = "complete"
        else:
            self.alpha = 0
            self.visible = False
            self.animation_phase = "waiting"
        
        self._render_surface()
    
    def start(self):
        """Запустить анимацию текста."""
        if self.started or self.animation == "none":
            return
        
        self.started = True
        self.visible = True
        self.animation_start_time = pygame.time.get_ticks()
        
        if self.animation in ["fade_in", "fade_in_out"]:
            self.alpha = 0
            self.animation_phase = "fade_in"
        elif self.animation == "fade_out":
            self.alpha = 255
            self.animation_phase = "fade_out"
    
    def _parse_color(self, color) -> Tuple[int, int, int]:
        """Парсинг цвета из разных форматов."""
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            return (int(color[0]), int(color[1]), int(color[2]))
        elif isinstance(color, str):
            hex_color = color.lstrip('#')
            if len(hex_color) == 6:
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return (255, 255, 255)
    
    def _render_surface(self):
        """Отрендерить текст в surface."""
        if not self.font or not self.text:
            self.surface = None
            return
        
        # Основной текст
        text_surface = self.font.render(self.text, True, self.color)
        
        # Если есть обводка
        if self.outline_color and self.outline_width > 0:
            # Создаём surface с обводкой
            w = text_surface.get_width() + self.outline_width * 2
            h = text_surface.get_height() + self.outline_width * 2
            outline_surface = pygame.Surface((w, h), pygame.SRCALPHA)
            
            # Рисуем обводку
            outline_text = self.font.render(self.text, True, self.outline_color)
            for dx in range(-self.outline_width, self.outline_width + 1):
                for dy in range(-self.outline_width, self.outline_width + 1):
                    if dx != 0 or dy != 0:
                        outline_surface.blit(outline_text, (self.outline_width + dx, self.outline_width + dy))
            
            # Основной текст поверх
            outline_surface.blit(text_surface, (self.outline_width, self.outline_width))
            text_surface = outline_surface
        
        # Масштабирование
        if self.scale != 1.0:
            new_w = int(text_surface.get_width() * self.scale)
            new_h = int(text_surface.get_height() * self.scale)
            if new_w > 0 and new_h > 0:
                text_surface = pygame.transform.smoothscale(text_surface, (new_w, new_h))
        
        # Поворот
        if self.rotation != 0:
            text_surface = pygame.transform.rotate(text_surface, self.rotation)
        
        self.surface = text_surface
    
    def update(self):
        """Обновить анимацию."""
        if self.animation_complete or not self.started or self.animation_start_time is None:
            return
        
        elapsed = (pygame.time.get_ticks() - self.animation_start_time) / 1000.0
        
        if self.animation == "fade_in":
            progress = min(elapsed / self.fade_in_duration, 1.0)
            self.alpha = int(255 * progress)
            if progress >= 1.0:
                self.animation_complete = True
                self.animation_phase = "complete"
        
        elif self.animation == "fade_out":
            progress = min(elapsed / self.fade_out_duration, 1.0)
            self.alpha = int(255 * (1 - progress))
            if progress >= 1.0:
                self.animation_complete = True
                self.animation_phase = "complete"
                self.visible = False
        
        elif self.animation == "fade_in_out":
            if self.animation_phase == "fade_in":
                progress = min(elapsed / self.fade_in_duration, 1.0)
                self.alpha = int(255 * progress)
                if progress >= 1.0:
                    self.animation_phase = "hold"
                    self.animation_start_time = pygame.time.get_ticks()
            
            elif self.animation_phase == "hold":
                if elapsed >= self.hold_duration:
                    self.animation_phase = "fade_out"
                    self.animation_start_time = pygame.time.get_ticks()
            
            elif self.animation_phase == "fade_out":
                progress = min(elapsed / self.fade_out_duration, 1.0)
                self.alpha = int(255 * (1 - progress))
                if progress >= 1.0:
                    self.animation_complete = True
                    self.animation_phase = "complete"
                    self.visible = False
    
    def is_blocking(self) -> bool:
        """Проверить, блокирует ли анимация пропуск."""
        return self.block_skip and not self.animation_complete
    
    def draw(self, screen: pygame.Surface):
        """Отрисовать текст."""
        if self.surface is None or not self.visible:
            return
        
        # Применяем альфу
        if self.alpha < 255:
            temp_surface = self.surface.copy()
            temp_surface.set_alpha(self.alpha)
        else:
            temp_surface = self.surface
        
        x = int(self.x * self.screen_width - temp_surface.get_width() / 2)
        y = int(self.y * self.screen_height - temp_surface.get_height() / 2)
        screen.blit(temp_surface, (x, y))


class AnimationPlayer:
    """Проигрыватель анимаций для персонажей."""
    
    def __init__(self):
        self.animations: Dict[str, List[dict]] = {}  # char_id -> keyframes
        self.active_animations: Dict[str, dict] = {}  # char_id -> {start_time, keyframes, loop}
        self.start_time = 0
    
    def add_animation(self, char_id: str, keyframes: List[dict], loop: bool = False):
        """Добавить анимацию для персонажа."""
        self.animations[char_id] = {'keyframes': keyframes, 'loop': loop}
    
    def start_animation(self, char_id: str):
        """Начать проигрывание анимации."""
        if char_id in self.animations:
            anim = self.animations[char_id]
            self.active_animations[char_id] = {
                'start_time': pygame.time.get_ticks(),
                'keyframes': anim['keyframes'],
                'loop': anim.get('loop', False)
            }
    
    def start_all(self):
        """Начать все анимации."""
        for char_id in self.animations:
            self.start_animation(char_id)
    
    def stop_animation(self, char_id: str):
        """Остановить анимацию."""
        if char_id in self.active_animations:
            del self.active_animations[char_id]
    
    def clear(self):
        """Очистить все анимации."""
        self.animations.clear()
        self.active_animations.clear()
    
    def update(self, sprites: List[CharacterSprite], images: List[Dict] = None):
        """Обновить позиции спрайтов и картинок по анимациям."""
        current_time = pygame.time.get_ticks()
        if images is None:
            images = []
        
        for anim_id, anim_data in list(self.active_animations.items()):
            elapsed = (current_time - anim_data['start_time']) / 1000.0
            keyframes = anim_data['keyframes']
            loop = anim_data.get('loop', False)
            
            if not keyframes:
                continue
            
            total_duration = keyframes[-1]['time']
            
            # Для зацикленных анимаций вычисляем время в цикле
            if loop and total_duration > 0:
                elapsed = elapsed % total_duration
            
            # Найти текущие ключевые кадры для интерполяции
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
            
            # Интерполяция
            if prev_kf['time'] == next_kf['time']:
                t = 0
            else:
                t = (elapsed - prev_kf['time']) / (next_kf['time'] - prev_kf['time'])
                t = max(0, min(1, t))
            
            x = prev_kf['x'] + (next_kf['x'] - prev_kf['x']) * t
            y = prev_kf['y'] + (next_kf['y'] - prev_kf['y']) * t
            
            # Также интерполируем scale, rotation, alpha если есть
            scale = prev_kf.get('scale', 1.0)
            if 'scale' in next_kf:
                scale = prev_kf.get('scale', 1.0) + (next_kf.get('scale', 1.0) - prev_kf.get('scale', 1.0)) * t
            
            rotation = prev_kf.get('rotation', 0.0)
            if 'rotation' in next_kf:
                rotation = prev_kf.get('rotation', 0.0) + (next_kf.get('rotation', 0.0) - prev_kf.get('rotation', 0.0)) * t
            
            alpha = prev_kf.get('alpha', 1.0)
            if 'alpha' in next_kf:
                alpha = prev_kf.get('alpha', 1.0) + (next_kf.get('alpha', 1.0) - prev_kf.get('alpha', 1.0)) * t
            
            found = False
            
            # Проверяем, это анимация картинки или персонажа
            if anim_id.startswith('img_'):
                # Это анимация картинки (ImageSprite)
                img_id = anim_id[4:]  # Убираем префикс "img_"
                for img in images:
                    if hasattr(img, 'image_id') and img.image_id == img_id:
                        img.x = x
                        img.y = y
                        img.scale = scale
                        img.rotation = rotation
                        img.alpha = int(alpha * 255)
                        img._apply_transforms()
                        found = True
                        break
            else:
                # Это анимация персонажа
                for sprite in sprites:
                    if hasattr(sprite, 'character_id') and sprite.character_id == anim_id:
                        sprite.set_exact_position(x, y, rotation=rotation, scale=scale)
                        sprite.alpha = int(alpha * 255)
                        found = True
                        break
            
            # Проверка окончания анимации (только для не-зацикленных)
            if not loop and elapsed > keyframes[-1]['time']:
                del self.active_animations[anim_id]


class DebugPanel:
    """Панель отладки для выбора сцен."""
    
    def __init__(self, screen_width: int, screen_height: int):
        self.width = 280
        self.height = screen_height
        self.x = screen_width - self.width
        self.y = 0
        self.visible = False
        
        pygame.font.init()
        self.font = pygame.font.Font(None, 24)
        self.title_font = pygame.font.Font(None, 32)
        
        self.scenes: List[Tuple[str, str]] = []  # [(scene_id, scene_name), ...]
        self.scroll_offset = 0
        self.item_height = 35
        self.selected_scene: Optional[str] = None
        
        # Цвета
        self.bg_color = (30, 30, 45, 230)
        self.title_color = (255, 220, 100)
        self.item_color = (200, 200, 200)
        self.item_hover_color = (255, 255, 255)
        self.item_bg_hover = (60, 60, 90)
        
        self.hovered_index = -1
    
    def set_scenes(self, scenes: List[Tuple[str, str]]):
        """Установить список сцен."""
        self.scenes = scenes
        self.scroll_offset = 0
    
    def toggle(self):
        """Переключить видимость."""
        self.visible = not self.visible
    
    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """Обработать событие. Возвращает scene_id если выбрана сцена."""
        if not self.visible:
            return None
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Левый клик
                mx, my = event.pos
                if mx >= self.x:
                    # Проверяем клик по элементу списка
                    list_y = 60  # Начало списка
                    for i, (scene_id, scene_name) in enumerate(self.scenes):
                        item_y = list_y + i * self.item_height - self.scroll_offset
                        if item_y < 50 or item_y > self.height - 10:
                            continue
                        if item_y <= my <= item_y + self.item_height:
                            return scene_id
            
            elif event.button == 4:  # Колёсико вверх
                self.scroll_offset = max(0, self.scroll_offset - 30)
            elif event.button == 5:  # Колёсико вниз
                max_scroll = max(0, len(self.scenes) * self.item_height - (self.height - 100))
                self.scroll_offset = min(max_scroll, self.scroll_offset + 30)
        
        elif event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            self.hovered_index = -1
            if mx >= self.x:
                list_y = 60
                for i, (scene_id, scene_name) in enumerate(self.scenes):
                    item_y = list_y + i * self.item_height - self.scroll_offset
                    if item_y < 50 or item_y > self.height - 10:
                        continue
                    if item_y <= my <= item_y + self.item_height:
                        self.hovered_index = i
                        break
        
        return None
    
    def draw(self, screen: pygame.Surface, current_scene_id: Optional[str] = None):
        """Отрисовать панель."""
        if not self.visible:
            return
        
        # Фон панели
        panel_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        panel_surface.fill(self.bg_color)
        screen.blit(panel_surface, (self.x, self.y))
        
        # Заголовок
        title = self.title_font.render("🛠 DEBUG - Сцены", True, self.title_color)
        screen.blit(title, (self.x + 15, 15))
        
        # Линия под заголовком
        pygame.draw.line(screen, (80, 80, 120), (self.x + 10, 50), (self.x + self.width - 10, 50), 2)
        
        # Список сцен
        list_y = 60
        for i, (scene_id, scene_name) in enumerate(self.scenes):
            item_y = list_y + i * self.item_height - self.scroll_offset
            
            # Пропускаем элементы за пределами видимости
            if item_y < 50 or item_y > self.height - 10:
                continue
            
            # Фон при наведении или текущая сцена
            is_current = (scene_id == current_scene_id)
            is_hovered = (i == self.hovered_index)
            
            if is_current:
                bg_rect = pygame.Rect(self.x + 5, item_y, self.width - 10, self.item_height - 2)
                pygame.draw.rect(screen, (80, 120, 80), bg_rect, border_radius=5)
            elif is_hovered:
                bg_rect = pygame.Rect(self.x + 5, item_y, self.width - 10, self.item_height - 2)
                pygame.draw.rect(screen, self.item_bg_hover, bg_rect, border_radius=5)
            
            # Текст
            color = self.item_hover_color if is_hovered else self.item_color
            if is_current:
                color = (150, 255, 150)
            
            # Обрезаем длинные названия
            display_name = scene_name if len(scene_name) < 25 else scene_name[:22] + "..."
            text = self.font.render(f"• {display_name}", True, color)
            screen.blit(text, (self.x + 15, item_y + 8))
            
            # ID сцены мелким шрифтом
            id_font = pygame.font.Font(None, 18)
            id_text = id_font.render(f"[{scene_id}]", True, (120, 120, 140))
            screen.blit(id_text, (self.x + 20, item_y + 22))
        
        # Подсказка внизу
        hint_font = pygame.font.Font(None, 20)
        hint = hint_font.render("F3 - скрыть панель", True, (120, 120, 140))
        screen.blit(hint, (self.x + 15, self.height - 25))


class SaveManager:
    """Менеджер сохранений игры."""
    
    def __init__(self, save_dir: str = "saves"):
        self.save_dir = save_dir
        self.slots = {}  # slot_id -> save_data
        self.thumbnails = {}  # slot_id -> pygame.Surface
        self._ensure_save_dir()
        self._load_saves_info()
    
    def _ensure_save_dir(self):
        """Создать папку для сохранений."""
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
    
    def _load_saves_info(self):
        """Загрузить информацию о всех сохранениях."""
        import json
        self.slots = {}
        self.thumbnails = {}
        
        if not os.path.exists(self.save_dir):
            return
        
        for filename in os.listdir(self.save_dir):
            if filename.startswith("save_") and filename.endswith(".json"):
                slot_id = filename[5:-5]  # save_X.json -> X
                filepath = os.path.join(self.save_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.slots[slot_id] = {
                            'scene_id': data.get('scene_id', ''),
                            'scene_name': data.get('scene_name', ''),
                            'dialog_index': data.get('dialog_index', 0),
                            'timestamp': data.get('timestamp', ''),
                            'play_time': data.get('play_time', 0),
                        }
                except:
                    pass
            
            # Загружаем миниатюры
            if filename.startswith("save_") and filename.endswith(".png"):
                slot_id = filename[5:-4]  # save_X.png -> X
                thumb_path = os.path.join(self.save_dir, filename)
                try:
                    self.thumbnails[slot_id] = pygame.image.load(thumb_path)
                except:
                    pass
    
    def save_game(self, slot_id: str, scene_id: str, scene_name: str, dialog_index: int,
                  screenshot: pygame.Surface, game_state: dict = None):
        """Сохранить игру в слот."""
        import json
        from datetime import datetime
        
        # Сохраняем данные
        save_data = {
            'scene_id': scene_id,
            'scene_name': scene_name,
            'dialog_index': dialog_index,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'play_time': game_state.get('play_time', 0) if game_state else 0,
            'game_state': game_state or {}
        }
        
        filepath = os.path.join(self.save_dir, f"save_{slot_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        # Сохраняем миниатюру
        thumbnail = pygame.transform.smoothscale(screenshot, (280, 157))
        thumb_path = os.path.join(self.save_dir, f"save_{slot_id}.png")
        pygame.image.save(thumbnail, thumb_path)
        
        # Обновляем кеш
        self.slots[slot_id] = {
            'scene_id': scene_id,
            'scene_name': scene_name,
            'dialog_index': dialog_index,
            'timestamp': save_data['timestamp'],
            'play_time': save_data['play_time'],
        }
        self.thumbnails[slot_id] = thumbnail
    
    def load_game(self, slot_id: str) -> Optional[dict]:
        """Загрузить игру из слота."""
        import json
        
        filepath = os.path.join(self.save_dir, f"save_{slot_id}.json")
        if not os.path.exists(filepath):
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    
    def delete_save(self, slot_id: str):
        """Удалить сохранение."""
        filepath = os.path.join(self.save_dir, f"save_{slot_id}.json")
        thumb_path = os.path.join(self.save_dir, f"save_{slot_id}.png")
        
        if os.path.exists(filepath):
            os.remove(filepath)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        
        if slot_id in self.slots:
            del self.slots[slot_id]
        if slot_id in self.thumbnails:
            del self.thumbnails[slot_id]
    
    def get_slot_info(self, slot_id: str) -> Optional[dict]:
        """Получить информацию о слоте."""
        return self.slots.get(slot_id)
    
    def get_thumbnail(self, slot_id: str) -> Optional[pygame.Surface]:
        """Получить миниатюру слота."""
        return self.thumbnails.get(slot_id)
    
    def has_any_save(self) -> bool:
        """Есть ли хотя бы одно сохранение."""
        return len(self.slots) > 0


class PauseMenu:
    """Меню паузы с сохранениями, настройками и выходом."""
    
    def __init__(self, width: int, height: int, save_manager: SaveManager):
        self.width = width
        self.height = height
        self.save_manager = save_manager
        self.config = None  # PauseMenuConfig
        
        # Состояние
        self.active = False
        self.current_screen = "main"  # "main", "save", "load", "settings"
        self.hovered_button = None
        self.pressed_button = None
        self.hovered_slot = None
        self.selected_slot = None
        self.dragging_slider = None
        
        # Страницы слотов
        self.current_page = 0
        
        # Анимации
        self.fade_alpha = 0
        self.fade_start_time = 0
        self.button_scales = {}
        self.button_target_scales = {}
        
        # Ресурсы
        self.fonts = {}
        
        # Звуки
        self.open_sound: Optional[pygame.mixer.Sound] = None
        self.close_sound: Optional[pygame.mixer.Sound] = None
        self.hover_sound: Optional[pygame.mixer.Sound] = None
        self.click_sound: Optional[pygame.mixer.Sound] = None
        
        # Настройки звука
        self.music_volume = 0.8
        self.sound_volume = 0.8
        self.voice_volume = 0.8
        
        # Колбэки
        self.on_resume = None
        self.on_save = None
        self.on_load = None
        self.on_main_menu = None
        self.on_exit = None
        
        # Скриншот текущей сцены для сохранения
        self.current_screenshot = None
    
    def load_config(self, config):
        """Загрузить конфигурацию меню паузы."""
        from story import PauseMenuConfig
        self.config = config
        
        # Инициализация масштабов кнопок
        for btn in self.config.buttons:
            self.button_scales[btn.id] = 1.0
            self.button_target_scales[btn.id] = 1.0
        
        self.button_scales[self.config.settings_back_button.id] = 1.0
        self.button_target_scales[self.config.settings_back_button.id] = 1.0
        
        # Загрузка звуков
        self._load_sounds()
    
    def _load_sounds(self):
        """Загрузить звуки меню."""
        if not self.config:
            return
        
        try:
            if self.config.open_sound and os.path.exists(self.config.open_sound):
                self.open_sound = pygame.mixer.Sound(self.config.open_sound)
            if self.config.close_sound and os.path.exists(self.config.close_sound):
                self.close_sound = pygame.mixer.Sound(self.config.close_sound)
            if self.config.hover_sound and os.path.exists(self.config.hover_sound):
                self.hover_sound = pygame.mixer.Sound(self.config.hover_sound)
            if self.config.click_sound and os.path.exists(self.config.click_sound):
                self.click_sound = pygame.mixer.Sound(self.config.click_sound)
        except:
            pass
    
    def open(self, screenshot: pygame.Surface = None):
        """Открыть меню паузы."""
        self.active = True
        self.current_screen = "main"
        self.fade_alpha = 0
        self.fade_start_time = pygame.time.get_ticks()
        self.current_screenshot = screenshot
        self.hovered_button = None
        self.hovered_slot = None
        self.selected_slot = None
        self.current_page = 0
        
        # Обновляем информацию о сохранениях
        self.save_manager._load_saves_info()
        
        if self.open_sound:
            self.open_sound.set_volume(self.sound_volume)
            self.open_sound.play()
    
    def close(self):
        """Закрыть меню паузы."""
        self.active = False
        
        if self.close_sound:
            self.close_sound.set_volume(self.sound_volume)
            self.close_sound.play()
    
    def _play_hover_sound(self):
        """Воспроизвести звук наведения."""
        if self.hover_sound:
            self.hover_sound.set_volume(self.sound_volume * 0.5)
            self.hover_sound.play()
    
    def _play_click_sound(self):
        """Воспроизвести звук клика."""
        if self.click_sound:
            self.click_sound.set_volume(self.sound_volume)
            self.click_sound.play()
    
    def _get_font(self, size: int) -> pygame.font.Font:
        """Получить шрифт заданного размера."""
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(None, size)
        return self.fonts[size]
    
    def _parse_color(self, color_str: str) -> Tuple[int, int, int, int]:
        """Парсинг цвета из строки #RRGGBB или #RRGGBBAA."""
        color_str = color_str.lstrip('#')
        if len(color_str) == 6:
            r, g, b = int(color_str[0:2], 16), int(color_str[2:4], 16), int(color_str[4:6], 16)
            return (r, g, b, 255)
        elif len(color_str) == 8:
            r, g, b = int(color_str[0:2], 16), int(color_str[2:4], 16), int(color_str[4:6], 16)
            a = int(color_str[6:8], 16)
            return (r, g, b, a)
        return (255, 255, 255, 255)
    
    def _get_button_rect(self, button, panel_rect: pygame.Rect = None) -> pygame.Rect:
        """Получить прямоугольник кнопки."""
        if panel_rect:
            # Кнопка внутри панели
            x = panel_rect.x + int(button.x * panel_rect.width) - button.width // 2
            y = panel_rect.y + int(button.y * panel_rect.height) - button.height // 2
        else:
            # Кнопка на весь экран
            x = int(button.x * self.width) - button.width // 2
            y = int(button.y * self.height) - button.height // 2
        return pygame.Rect(x, y, button.width, button.height)
    
    def _get_slot_rect(self, slot_index: int) -> pygame.Rect:
        """Получить прямоугольник слота сохранения."""
        if not self.config:
            return pygame.Rect(0, 0, 0, 0)
        
        sl_config = self.config.save_load_screen
        slot_config = sl_config.slot_config
        
        # Позиция в сетке 2x2
        row = slot_index // 2
        col = slot_index % 2
        
        x = int(sl_config.slots_start_x * self.width) + col * sl_config.slots_spacing_x
        y = int(sl_config.slots_start_y * self.height) + row * sl_config.slots_spacing_y
        
        return pygame.Rect(x, y, slot_config.width, slot_config.height)
    
    def _get_slider_rect(self, slider) -> pygame.Rect:
        """Получить прямоугольник слайдера."""
        x = int(slider.x * self.width) - slider.width // 2
        y = int(slider.y * self.height) - slider.height // 2
        return pygame.Rect(x, y, slider.width, slider.height)
    
    def _get_slider_handle_rect(self, slider, slider_rect: pygame.Rect) -> pygame.Rect:
        """Получить прямоугольник ручки слайдера."""
        value = getattr(self, f"{slider.setting}", slider.value)
        handle_x = slider_rect.x + int(value * (slider_rect.width - 20))
        return pygame.Rect(handle_x, slider_rect.y - 5, 20, slider_rect.height + 10)
    
    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """Обработка событий. Возвращает действие или None."""
        if not self.active or not self.config:
            return None
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.current_screen == "main":
                    self._play_click_sound()
                    self.close()
                    return "resume"
                else:
                    self._play_click_sound()
                    self.current_screen = "main"
                    return None
        
        elif event.type == pygame.MOUSEMOTION:
            self._handle_mouse_motion(event.pos)
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                return self._handle_mouse_down(event.pos)
        
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                return self._handle_mouse_up(event.pos)
        
        return None
    
    def _handle_mouse_motion(self, pos: Tuple[int, int]):
        """Обработка движения мыши."""
        if self.dragging_slider:
            self._update_slider_value(pos)
            return
        
        panel_rect = self._get_panel_rect()
        old_hovered = self.hovered_button
        self.hovered_button = None
        self.hovered_slot = None
        
        if self.current_screen == "main":
            for btn in self.config.buttons:
                if not btn.visible:
                    continue
                rect = self._get_button_rect(btn, panel_rect)
                if rect.collidepoint(pos):
                    self.hovered_button = btn.id
                    self.button_target_scales[btn.id] = 1.05
                else:
                    self.button_target_scales[btn.id] = 1.0
        
        elif self.current_screen == "settings":
            back_btn = self.config.settings_back_button
            rect = self._get_button_rect(back_btn)
            if rect.collidepoint(pos):
                self.hovered_button = back_btn.id
                self.button_target_scales[back_btn.id] = 1.05
            else:
                self.button_target_scales[back_btn.id] = 1.0
        
        elif self.current_screen in ("save", "load"):
            # Проверяем слоты
            for i in range(4):
                rect = self._get_slot_rect(i)
                if rect.collidepoint(pos):
                    self.hovered_slot = i
                    break
            
            # Проверяем кнопку назад
            back_btn = self.config.save_load_screen.back_button
            rect = self._get_button_rect(back_btn)
            if rect.collidepoint(pos):
                self.hovered_button = back_btn.id
        
        # Звук при наведении на новую кнопку
        if self.hovered_button and self.hovered_button != old_hovered:
            self._play_hover_sound()
    
    def _handle_mouse_down(self, pos: Tuple[int, int]) -> Optional[str]:
        """Обработка нажатия мыши."""
        if self.current_screen == "settings":
            # Проверяем слайдеры
            for slider in self.config.settings_sliders:
                slider_rect = self._get_slider_rect(slider)
                handle_rect = self._get_slider_handle_rect(slider, slider_rect)
                if handle_rect.collidepoint(pos) or slider_rect.collidepoint(pos):
                    self.dragging_slider = slider
                    self._update_slider_value(pos)
                    return None
        
        if self.hovered_button:
            self.pressed_button = self.hovered_button
        
        return None
    
    def _handle_mouse_up(self, pos: Tuple[int, int]) -> Optional[str]:
        """Обработка отпускания мыши."""
        if self.dragging_slider:
            self.dragging_slider = None
            return None
        
        panel_rect = self._get_panel_rect()
        
        if self.current_screen == "main":
            for btn in self.config.buttons:
                if not btn.visible:
                    continue
                rect = self._get_button_rect(btn, panel_rect)
                if rect.collidepoint(pos):
                    self._play_click_sound()
                    return self._handle_button_action(btn.action)
        
        elif self.current_screen == "settings":
            back_btn = self.config.settings_back_button
            rect = self._get_button_rect(back_btn)
            if rect.collidepoint(pos):
                self._play_click_sound()
                self.current_screen = "main"
                return None
        
        elif self.current_screen in ("save", "load"):
            # Проверяем слоты
            for i in range(4):
                rect = self._get_slot_rect(i)
                if rect.collidepoint(pos):
                    self._play_click_sound()
                    slot_id = str(self.current_page * 4 + i)
                    if self.current_screen == "save":
                        return f"save:{slot_id}"
                    else:
                        return f"load:{slot_id}"
            
            # Проверяем кнопки навигации
            sl_config = self.config.save_load_screen
            
            # Кнопка "Назад"
            back_btn = sl_config.back_button
            rect = self._get_button_rect(back_btn)
            if rect.collidepoint(pos):
                self._play_click_sound()
                self.current_screen = "main"
                return None
            
            # Кнопки страниц
            page_y = int(sl_config.page_indicator_y * self.height)
            prev_x = int(sl_config.prev_button_x * self.width) - sl_config.page_button_width // 2
            next_x = int(sl_config.next_button_x * self.width) - sl_config.page_button_width // 2
            
            prev_rect = pygame.Rect(prev_x, page_y, sl_config.page_button_width, sl_config.page_button_height)
            next_rect = pygame.Rect(next_x, page_y, sl_config.page_button_width, sl_config.page_button_height)
            
            if prev_rect.collidepoint(pos) and self.current_page > 0:
                self._play_click_sound()
                self.current_page -= 1
            elif next_rect.collidepoint(pos) and self.current_page < sl_config.total_pages - 1:
                self._play_click_sound()
                self.current_page += 1
        
        self.pressed_button = None
        return None
    
    def _handle_button_action(self, action: str) -> Optional[str]:
        """Обработка действия кнопки."""
        if action == "resume":
            self.close()
            return "resume"
        elif action == "save":
            self.current_screen = "save"
            return None
        elif action == "load":
            self.current_screen = "load"
            return None
        elif action == "settings":
            self.current_screen = "settings"
            return None
        elif action == "main_menu":
            self.close()
            return "main_menu"
        elif action == "exit":
            return "exit"
        return None
    
    def _update_slider_value(self, pos: Tuple[int, int]):
        """Обновить значение слайдера при перетаскивании."""
        if not self.dragging_slider:
            return
        
        slider_rect = self._get_slider_rect(self.dragging_slider)
        value = (pos[0] - slider_rect.x) / slider_rect.width
        value = max(0.0, min(1.0, value))
        
        setting = self.dragging_slider.setting
        if setting == "music_volume":
            self.music_volume = value
            pygame.mixer.music.set_volume(value)
        elif setting == "sound_volume":
            self.sound_volume = value
        elif setting == "voice_volume":
            self.voice_volume = value
    
    def _get_panel_rect(self) -> pygame.Rect:
        """Получить прямоугольник панели меню."""
        if not self.config:
            return pygame.Rect(0, 0, 400, 500)
        
        x = int(self.config.panel_x * self.width) - self.config.panel_width // 2
        y = int(self.config.panel_y * self.height) - self.config.panel_height // 2
        return pygame.Rect(x, y, self.config.panel_width, self.config.panel_height)
    
    def update(self, dt: float):
        """Обновление анимаций."""
        if not self.active or not self.config:
            return
        
        # Анимация появления
        if self.config.animation_enabled:
            elapsed = (pygame.time.get_ticks() - self.fade_start_time) / 1000
            progress = min(1.0, elapsed / self.config.fade_duration)
            self.fade_alpha = int(progress * self.config.overlay_alpha)
        else:
            self.fade_alpha = self.config.overlay_alpha
        
        # Анимация масштабов кнопок
        for btn_id in self.button_scales:
            current = self.button_scales[btn_id]
            target = self.button_target_scales.get(btn_id, 1.0)
            if current != target:
                diff = target - current
                self.button_scales[btn_id] += diff * min(1.0, dt * 10)
    
    def draw(self, screen: pygame.Surface):
        """Отрисовка меню паузы."""
        if not self.active or not self.config:
            return
        
        # Затемнение фона
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay_color = self._parse_color(self.config.overlay_color)
        overlay.fill((overlay_color[0], overlay_color[1], overlay_color[2], self.fade_alpha))
        screen.blit(overlay, (0, 0))
        
        if self.current_screen == "main":
            self._draw_main_screen(screen)
        elif self.current_screen == "settings":
            self._draw_settings_screen(screen)
        elif self.current_screen in ("save", "load"):
            self._draw_save_load_screen(screen)
    
    def _draw_main_screen(self, screen: pygame.Surface):
        """Отрисовка главного экрана паузы."""
        panel_rect = self._get_panel_rect()
        
        # Панель
        panel_surface = pygame.Surface((panel_rect.width, panel_rect.height), pygame.SRCALPHA)
        bg_color = self._parse_color(self.config.panel_bg_color)
        pygame.draw.rect(panel_surface, bg_color, 
                        pygame.Rect(0, 0, panel_rect.width, panel_rect.height),
                        border_radius=self.config.panel_border_radius)
        
        border_color = self._parse_color(self.config.panel_border_color)[:3]
        pygame.draw.rect(panel_surface, border_color,
                        pygame.Rect(0, 0, panel_rect.width, panel_rect.height),
                        width=self.config.panel_border_width,
                        border_radius=self.config.panel_border_radius)
        
        screen.blit(panel_surface, panel_rect.topleft)
        
        # Заголовок
        title_font = self._get_font(self.config.title_size)
        title_color = self._parse_color(self.config.title_color)[:3]
        title_surface = title_font.render(self.config.title, True, title_color)
        title_x = panel_rect.x + int(self.config.title_x * panel_rect.width) - title_surface.get_width() // 2
        title_y = panel_rect.y + int(self.config.title_y * panel_rect.height)
        screen.blit(title_surface, (title_x, title_y))
        
        # Кнопки
        for btn in self.config.buttons:
            if not btn.visible:
                continue
            self._draw_button(screen, btn, panel_rect)
    
    def _draw_settings_screen(self, screen: pygame.Surface):
        """Отрисовка экрана настроек."""
        # Заголовок
        title_font = self._get_font(self.config.settings_title_size)
        title_color = self._parse_color(self.config.settings_title_color)[:3]
        title_surface = title_font.render(self.config.settings_title, True, title_color)
        title_x = int(self.config.settings_title_x * self.width) - title_surface.get_width() // 2
        title_y = int(self.config.settings_title_y * self.height)
        screen.blit(title_surface, (title_x, title_y))
        
        # Слайдеры
        for slider in self.config.settings_sliders:
            self._draw_slider(screen, slider)
        
        # Кнопка назад
        self._draw_button(screen, self.config.settings_back_button)
    
    def _draw_save_load_screen(self, screen: pygame.Surface):
        """Отрисовка экрана сохранения/загрузки."""
        sl_config = self.config.save_load_screen
        
        # Заголовок
        title = sl_config.title_save if self.current_screen == "save" else sl_config.title_load
        title_font = self._get_font(sl_config.title_size)
        title_color = self._parse_color(sl_config.title_color)[:3]
        title_surface = title_font.render(title, True, title_color)
        title_x = int(sl_config.title_x * self.width) - title_surface.get_width() // 2
        title_y = int(sl_config.title_y * self.height)
        screen.blit(title_surface, (title_x, title_y))
        
        # Слоты
        for i in range(4):
            self._draw_save_slot(screen, i)
        
        # Навигация по страницам
        self._draw_page_navigation(screen)
        
        # Кнопка назад
        self._draw_button(screen, sl_config.back_button)
    
    def _draw_button(self, screen: pygame.Surface, button, panel_rect: pygame.Rect = None):
        """Отрисовка кнопки."""
        rect = self._get_button_rect(button, panel_rect)
        is_hovered = self.hovered_button == button.id
        is_pressed = self.pressed_button == button.id
        
        # Масштаб
        scale = self.button_scales.get(button.id, 1.0)
        if scale != 1.0:
            new_width = int(button.width * scale)
            new_height = int(button.height * scale)
            rect = pygame.Rect(
                rect.centerx - new_width // 2,
                rect.centery - new_height // 2,
                new_width, new_height
            )
        
        # Цвет фона
        if is_pressed:
            bg_color = self._parse_color(button.click_color)
        elif is_hovered:
            bg_color = self._parse_color(button.hover_color)
        else:
            bg_color = self._parse_color(button.bg_color)
        
        # Отрисовка
        btn_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(btn_surface, bg_color, 
                        pygame.Rect(0, 0, rect.width, rect.height),
                        border_radius=button.border_radius)
        
        border_color = self._parse_color(button.border_color)[:3]
        pygame.draw.rect(btn_surface, border_color,
                        pygame.Rect(0, 0, rect.width, rect.height),
                        width=button.border_width,
                        border_radius=button.border_radius)
        
        screen.blit(btn_surface, rect.topleft)
        
        # Текст
        font = self._get_font(button.font_size)
        text_color = self._parse_color(button.text_color)[:3]
        text_surface = font.render(button.text, True, text_color)
        text_x = rect.centerx - text_surface.get_width() // 2
        text_y = rect.centery - text_surface.get_height() // 2
        screen.blit(text_surface, (text_x, text_y))
    
    def _draw_slider(self, screen: pygame.Surface, slider):
        """Отрисовка слайдера."""
        slider_rect = self._get_slider_rect(slider)
        
        # Подпись
        label_font = self._get_font(24)
        label_color = self._parse_color(slider.label_color)[:3]
        label_surface = label_font.render(slider.label, True, label_color)
        label_x = slider_rect.x
        label_y = slider_rect.y - 30
        screen.blit(label_surface, (label_x, label_y))
        
        # Дорожка
        track_color = self._parse_color(slider.track_color)[:3]
        pygame.draw.rect(screen, track_color, slider_rect, border_radius=5)
        
        # Заполнение
        value = getattr(self, f"{slider.setting}", slider.value)
        fill_width = int(value * slider_rect.width)
        fill_rect = pygame.Rect(slider_rect.x, slider_rect.y, fill_width, slider_rect.height)
        fill_color = self._parse_color(slider.fill_color)[:3]
        pygame.draw.rect(screen, fill_color, fill_rect, border_radius=5)
        
        # Ручка
        handle_rect = self._get_slider_handle_rect(slider, slider_rect)
        handle_color = self._parse_color(slider.handle_color)[:3]
        pygame.draw.rect(screen, handle_color, handle_rect, border_radius=3)
        
        # Процент
        percent_text = f"{int(value * 100)}%"
        percent_surface = label_font.render(percent_text, True, label_color)
        screen.blit(percent_surface, (slider_rect.right + 15, slider_rect.centery - percent_surface.get_height() // 2))
    
    def _draw_save_slot(self, screen: pygame.Surface, slot_index: int):
        """Отрисовка слота сохранения."""
        slot_id = str(self.current_page * 4 + slot_index)
        slot_info = self.save_manager.get_slot_info(slot_id)
        thumbnail = self.save_manager.get_thumbnail(slot_id)
        
        rect = self._get_slot_rect(slot_index)
        sl_config = self.config.save_load_screen.slot_config
        
        is_hovered = self.hovered_slot == slot_index
        is_empty = slot_info is None
        
        # Цвет фона
        if is_hovered:
            bg_color = self._parse_color(sl_config.hover_color)
        elif is_empty:
            bg_color = self._parse_color(sl_config.empty_color)
        else:
            bg_color = self._parse_color(sl_config.bg_color)
        
        # Фон слота
        slot_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(slot_surface, bg_color,
                        pygame.Rect(0, 0, rect.width, rect.height),
                        border_radius=sl_config.border_radius)
        
        border_color = self._parse_color(sl_config.border_color)[:3]
        pygame.draw.rect(slot_surface, border_color,
                        pygame.Rect(0, 0, rect.width, rect.height),
                        width=sl_config.border_width,
                        border_radius=sl_config.border_radius)
        
        screen.blit(slot_surface, rect.topleft)
        
        if is_empty:
            # Пустой слот
            font = self._get_font(sl_config.font_size)
            text_color = self._parse_color(sl_config.text_color)[:3]
            text_surface = font.render(sl_config.empty_text, True, text_color)
            text_x = rect.centerx - text_surface.get_width() // 2
            text_y = rect.centery - text_surface.get_height() // 2
            screen.blit(text_surface, (text_x, text_y))
            
            # Номер слота
            slot_num_surface = font.render(f"Слот {int(slot_id) + 1}", True, (150, 150, 180))
            screen.blit(slot_num_surface, (rect.x + 10, rect.y + 10))
        else:
            # Миниатюра
            if thumbnail:
                thumb_rect = pygame.Rect(rect.x + 5, rect.y + 5, rect.width - 10, sl_config.thumbnail_height)
                scaled_thumb = pygame.transform.smoothscale(thumbnail, (thumb_rect.width, thumb_rect.height))
                screen.blit(scaled_thumb, thumb_rect.topleft)
            
            # Информация
            font = self._get_font(sl_config.font_size)
            date_font = self._get_font(sl_config.date_font_size)
            text_color = self._parse_color(sl_config.text_color)[:3]
            date_color = self._parse_color(sl_config.date_color)[:3]
            
            # Название сцены
            scene_name = slot_info.get('scene_name', 'Неизвестно')[:25]
            scene_surface = font.render(scene_name, True, text_color)
            screen.blit(scene_surface, (rect.x + 10, rect.y + sl_config.thumbnail_height + 15))
            
            # Дата
            timestamp = slot_info.get('timestamp', '')
            date_surface = date_font.render(timestamp, True, date_color)
            screen.blit(date_surface, (rect.x + 10, rect.y + sl_config.thumbnail_height + 38))
            
            # Номер слота
            slot_num_surface = date_font.render(f"Слот {int(slot_id) + 1}", True, date_color)
            screen.blit(slot_num_surface, (rect.right - slot_num_surface.get_width() - 10, rect.y + 10))
    
    def _draw_page_navigation(self, screen: pygame.Surface):
        """Отрисовка навигации по страницам."""
        sl_config = self.config.save_load_screen
        page_y = int(sl_config.page_indicator_y * self.height)
        
        # Индикатор страницы
        font = self._get_font(24)
        page_text = f"Страница {self.current_page + 1} / {sl_config.total_pages}"
        page_surface = font.render(page_text, True, (255, 255, 255))
        page_x = self.width // 2 - page_surface.get_width() // 2
        screen.blit(page_surface, (page_x, page_y + 5))
        
        # Кнопки навигации
        prev_x = int(sl_config.prev_button_x * self.width) - sl_config.page_button_width // 2
        next_x = int(sl_config.next_button_x * self.width) - sl_config.page_button_width // 2
        
        # Кнопка "Назад"
        prev_color = (100, 100, 150) if self.current_page > 0 else (60, 60, 80)
        prev_rect = pygame.Rect(prev_x, page_y, sl_config.page_button_width, sl_config.page_button_height)
        pygame.draw.rect(screen, prev_color, prev_rect, border_radius=5)
        prev_text = font.render("◀ Назад", True, (255, 255, 255))
        screen.blit(prev_text, (prev_rect.centerx - prev_text.get_width() // 2, 
                                prev_rect.centery - prev_text.get_height() // 2))
        
        # Кнопка "Далее"
        next_color = (100, 100, 150) if self.current_page < sl_config.total_pages - 1 else (60, 60, 80)
        next_rect = pygame.Rect(next_x, page_y, sl_config.page_button_width, sl_config.page_button_height)
        pygame.draw.rect(screen, next_color, next_rect, border_radius=5)
        next_text = font.render("Далее ▶", True, (255, 255, 255))
        screen.blit(next_text, (next_rect.centerx - next_text.get_width() // 2,
                                next_rect.centery - next_text.get_height() // 2))


class MainMenu:
    """Главное меню игры с анимациями и настройками."""
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.config = None  # MainMenuConfig
        
        # Состояние
        self.active = True
        self.current_screen = "main"  # "main" или "settings"
        self.hovered_button = None
        self.pressed_button = None
        self.dragging_slider = None
        
        # Анимации
        self.fade_alpha = 0
        self.fade_start_time = 0
        self.button_scales = {}  # button_id -> scale
        self.button_target_scales = {}  # button_id -> target_scale
        
        # Ресурсы
        self.background: Optional[pygame.Surface] = None
        self.logo: Optional[pygame.Surface] = None
        self.fonts = {}
        
        # Звуки
        self.hover_sound: Optional[pygame.mixer.Sound] = None
        self.click_sound: Optional[pygame.mixer.Sound] = None
        self.back_sound: Optional[pygame.mixer.Sound] = None
        self.music_playing = False
        
        # Настройки звука (сохраняются между сессиями)
        self.music_volume = 0.8
        self.sound_volume = 0.8
        self.voice_volume = 0.8
        
        # Рекомендации для кнопок
        self.button_rects = {}  # button_id -> pygame.Rect
        self.slider_rects = {}  # slider_id -> (track_rect, handle_rect)
        
    def load_config(self, config):
        """Загрузить конфигурацию меню."""
        from story import MainMenuConfig
        self.config = config
        
        # Сброс анимаций
        self.fade_alpha = 0
        self.fade_start_time = pygame.time.get_ticks()
        
        # Инициализация масштабов кнопок
        for btn in self.config.buttons:
            self.button_scales[btn.id] = 1.0
            self.button_target_scales[btn.id] = 1.0
        self.button_scales[self.config.back_button.id] = 1.0
        self.button_target_scales[self.config.back_button.id] = 1.0
        
        # Загрузка значений слайдеров
        for slider in self.config.sliders:
            if slider.setting == "music_volume":
                self.music_volume = slider.value
            elif slider.setting == "sound_volume":
                self.sound_volume = slider.value
            elif slider.setting == "voice_volume":
                self.voice_volume = slider.value
        
        # Загрузка ресурсов
        self._load_resources()
        
    def _load_resources(self):
        """Загрузить все ресурсы меню."""
        if not self.config:
            return
        
        # Фон
        if self.config.background and os.path.exists(self.config.background):
            try:
                self.background = pygame.image.load(self.config.background).convert()
                self.background = pygame.transform.smoothscale(self.background, (self.width, self.height))
            except pygame.error:
                self.background = None
        
        # Логотип
        if self.config.logo.image_path and os.path.exists(self.config.logo.image_path):
            try:
                self.logo = pygame.image.load(self.config.logo.image_path).convert_alpha()
                if self.config.logo.scale != 1.0:
                    new_w = int(self.logo.get_width() * self.config.logo.scale)
                    new_h = int(self.logo.get_height() * self.config.logo.scale)
                    self.logo = pygame.transform.smoothscale(self.logo, (new_w, new_h))
            except pygame.error:
                self.logo = None
        
        # Звуки
        sounds = self.config.sounds
        if sounds.hover_sound and os.path.exists(sounds.hover_sound):
            try:
                self.hover_sound = pygame.mixer.Sound(sounds.hover_sound)
                self.hover_sound.set_volume(self.sound_volume)
            except:
                pass
        
        if sounds.click_sound and os.path.exists(sounds.click_sound):
            try:
                self.click_sound = pygame.mixer.Sound(sounds.click_sound)
                self.click_sound.set_volume(self.sound_volume)
            except:
                pass
        
        if sounds.back_sound and os.path.exists(sounds.back_sound):
            try:
                self.back_sound = pygame.mixer.Sound(sounds.back_sound)
                self.back_sound.set_volume(self.sound_volume)
            except:
                pass
        
        # Фоновая музыка
        if sounds.background_music and os.path.exists(sounds.background_music):
            try:
                pygame.mixer.music.load(sounds.background_music)
                pygame.mixer.music.set_volume(self.music_volume)
                pygame.mixer.music.play(-1)
                self.music_playing = True
            except:
                pass
    
    def _hex_to_rgba(self, hex_color: str) -> Tuple[int, int, int, int]:
        """Конвертировать HEX цвет в RGBA."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            return (r, g, b, 255)
        elif len(hex_color) == 8:
            r, g, b, a = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16), int(hex_color[6:8], 16)
            return (r, g, b, a)
        return (255, 255, 255, 255)
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Конвертировать HEX цвет в RGB."""
        rgba = self._hex_to_rgba(hex_color)
        return (rgba[0], rgba[1], rgba[2])
    
    def _get_font(self, size: int) -> pygame.font.Font:
        """Получить шрифт нужного размера из кэша."""
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(None, size)
        return self.fonts[size]
    
    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """Обработать событие. Возвращает действие или None."""
        if not self.config or not self.active:
            return None
        
        if event.type == pygame.MOUSEMOTION:
            self._handle_mouse_motion(event.pos)
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                return self._handle_mouse_down(event.pos)
        
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                return self._handle_mouse_up(event.pos)
        
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.current_screen == "settings":
                    self._play_sound(self.back_sound)
                    self.current_screen = "main"
                else:
                    return "exit"
        
        return None
    
    def _handle_mouse_motion(self, pos):
        """Обработать движение мыши."""
        old_hovered = self.hovered_button
        self.hovered_button = None
        
        # Обновление слайдеров при перетаскивании
        if self.dragging_slider:
            self._update_slider_drag(pos)
            return
        
        # Проверяем кнопки
        buttons = self.config.buttons if self.current_screen == "main" else [self.config.back_button]
        
        for btn in buttons:
            if not btn.visible:
                continue
            rect = self._get_button_rect(btn)
            if rect.collidepoint(pos):
                self.hovered_button = btn.id
                if old_hovered != btn.id:
                    self._play_sound(self.hover_sound)
                break
    
    def _handle_mouse_down(self, pos) -> Optional[str]:
        """Обработать нажатие мыши."""
        # Проверяем слайдеры
        if self.current_screen == "settings":
            for slider in self.config.sliders:
                track_rect, handle_rect = self._get_slider_rects(slider)
                if track_rect.collidepoint(pos) or handle_rect.collidepoint(pos):
                    self.dragging_slider = slider.id
                    self._update_slider_drag(pos)
                    self._play_sound(self.click_sound)
                    return None
        
        # Проверяем кнопки
        buttons = self.config.buttons if self.current_screen == "main" else [self.config.back_button]
        
        for btn in buttons:
            if not btn.visible:
                continue
            rect = self._get_button_rect(btn)
            if rect.collidepoint(pos):
                self.pressed_button = btn.id
                self._play_sound(self.click_sound)
                return None
        
        return None
    
    def _handle_mouse_up(self, pos) -> Optional[str]:
        """Обработать отпускание мыши."""
        # Отпускаем слайдер
        if self.dragging_slider:
            self.dragging_slider = None
            return None
        
        # Проверяем кнопки
        if self.pressed_button:
            buttons = self.config.buttons if self.current_screen == "main" else [self.config.back_button]
            
            for btn in buttons:
                if btn.id == self.pressed_button and btn.visible:
                    rect = self._get_button_rect(btn)
                    if rect.collidepoint(pos):
                        self.pressed_button = None
                        return self._execute_action(btn.action)
            
            self.pressed_button = None
        
        return None
    
    def _execute_action(self, action: str) -> Optional[str]:
        """Выполнить действие кнопки."""
        if action == "start":
            self.active = False
            if self.music_playing:
                pygame.mixer.music.fadeout(500)
            return "start"
        elif action == "continue":
            # TODO: Реализовать сохранения
            return "continue"
        elif action == "settings":
            self.current_screen = "settings"
            return None
        elif action == "back":
            self._play_sound(self.back_sound)
            self.current_screen = "main"
            return None
        elif action == "exit":
            return "exit"
        return None
    
    def _update_slider_drag(self, pos):
        """Обновить значение слайдера при перетаскивании."""
        for slider in self.config.sliders:
            if slider.id == self.dragging_slider:
                track_rect, _ = self._get_slider_rects(slider)
                # Вычисляем значение
                relative_x = (pos[0] - track_rect.x) / track_rect.width
                relative_x = max(0.0, min(1.0, relative_x))
                value = slider.min_value + relative_x * (slider.max_value - slider.min_value)
                slider.value = value
                
                # Применяем настройку
                if slider.setting == "music_volume":
                    self.music_volume = value
                    pygame.mixer.music.set_volume(value)
                elif slider.setting == "sound_volume":
                    self.sound_volume = value
                    if self.hover_sound:
                        self.hover_sound.set_volume(value)
                    if self.click_sound:
                        self.click_sound.set_volume(value)
                    if self.back_sound:
                        self.back_sound.set_volume(value)
                elif slider.setting == "voice_volume":
                    self.voice_volume = value
                break
    
    def _get_button_rect(self, btn) -> pygame.Rect:
        """Получить прямоугольник кнопки с учётом масштаба."""
        scale = self.button_scales.get(btn.id, 1.0)
        w = int(btn.width * scale)
        h = int(btn.height * scale)
        x = int(btn.x * self.width - w / 2)
        y = int(btn.y * self.height - h / 2)
        return pygame.Rect(x, y, w, h)
    
    def _get_slider_rects(self, slider) -> Tuple[pygame.Rect, pygame.Rect]:
        """Получить прямоугольники трека и ручки слайдера."""
        x = int(slider.x * self.width - slider.width / 2)
        y = int(slider.y * self.height - slider.height / 2)
        track_rect = pygame.Rect(x, y, slider.width, slider.height)
        
        # Позиция ручки
        relative_value = (slider.value - slider.min_value) / (slider.max_value - slider.min_value)
        handle_x = x + int(relative_value * slider.width) - 10
        handle_rect = pygame.Rect(handle_x, y - 5, 20, slider.height + 10)
        
        return track_rect, handle_rect
    
    def _play_sound(self, sound: Optional[pygame.mixer.Sound]):
        """Воспроизвести звук если он есть."""
        if sound:
            try:
                sound.play()
            except:
                pass
    
    def update(self):
        """Обновить состояние меню."""
        if not self.config or not self.active:
            return
        
        current_time = pygame.time.get_ticks()
        
        # Анимация появления
        if self.config.animation_enabled:
            elapsed = (current_time - self.fade_start_time) / 1000.0
            fade_progress = min(1.0, elapsed / self.config.fade_in_duration)
            self.fade_alpha = int(255 * fade_progress)
        else:
            self.fade_alpha = 255
        
        # Анимация кнопок
        if self.config.animation_enabled:
            for btn_id in self.button_scales:
                # Определяем целевой масштаб
                if btn_id == self.pressed_button:
                    target = self.config.button_click_scale
                elif btn_id == self.hovered_button:
                    target = self.config.button_hover_scale
                else:
                    target = 1.0
                
                self.button_target_scales[btn_id] = target
                
                # Плавное изменение масштаба
                current = self.button_scales[btn_id]
                diff = target - current
                self.button_scales[btn_id] = current + diff * 0.2
    
    def draw(self, screen: pygame.Surface):
        """Отрисовать меню."""
        if not self.config or not self.active:
            return
        
        # Фон
        if self.background:
            screen.blit(self.background, (0, 0))
        elif self.config.background_color:
            screen.fill(self.config.background_color)
        else:
            # Градиент по умолчанию
            for y in range(self.height):
                color = (
                    int(20 + (y / self.height) * 30),
                    int(20 + (y / self.height) * 40),
                    int(40 + (y / self.height) * 60)
                )
                pygame.draw.line(screen, color, (0, y), (self.width, y))
        
        # Применяем альфу к содержимому
        if self.fade_alpha < 255:
            fade_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self._draw_content(fade_surface)
            fade_surface.set_alpha(self.fade_alpha)
            screen.blit(fade_surface, (0, 0))
        else:
            self._draw_content(screen)
    
    def _draw_content(self, screen: pygame.Surface):
        """Отрисовать содержимое меню."""
        if self.current_screen == "main":
            self._draw_main_menu(screen)
        else:
            self._draw_settings_menu(screen)
    
    def _draw_main_menu(self, screen: pygame.Surface):
        """Отрисовать главное меню."""
        # Логотип
        if self.logo:
            logo_x = int(self.config.logo.x * self.width - self.logo.get_width() / 2)
            logo_y = int(self.config.logo.y * self.height - self.logo.get_height() / 2)
            screen.blit(self.logo, (logo_x, logo_y))
        
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
        
        # Слайдеры
        for slider in self.config.sliders:
            self._draw_slider(screen, slider)
        
        # Кнопка "Назад"
        self._draw_button(screen, self.config.back_button)
    
    def _draw_button(self, screen: pygame.Surface, btn):
        """Отрисовать кнопку."""
        rect = self._get_button_rect(btn)
        
        # Определяем цвет
        if btn.id == self.pressed_button:
            bg_color = self._hex_to_rgba(btn.click_color)
        elif btn.id == self.hovered_button:
            bg_color = self._hex_to_rgba(btn.hover_color)
        else:
            bg_color = self._hex_to_rgba(btn.bg_color)
        
        border_color = self._hex_to_rgb(btn.border_color)
        text_color = self._hex_to_rgb(btn.text_color)
        
        # Рисуем фон
        btn_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(btn_surface, bg_color, (0, 0, rect.width, rect.height), border_radius=btn.border_radius)
        
        # Рисуем рамку
        if btn.border_width > 0:
            pygame.draw.rect(btn_surface, border_color, (0, 0, rect.width, rect.height), btn.border_width, border_radius=btn.border_radius)
        
        screen.blit(btn_surface, rect.topleft)
        
        # Текст
        scale = self.button_scales.get(btn.id, 1.0)
        font_size = int(btn.font_size * scale)
        font = self._get_font(font_size)
        text_surface = font.render(btn.text, True, text_color)
        text_x = rect.centerx - text_surface.get_width() // 2
        text_y = rect.centery - text_surface.get_height() // 2
        screen.blit(text_surface, (text_x, text_y))
    
    def _draw_slider(self, screen: pygame.Surface, slider):
        """Отрисовать слайдер."""
        track_rect, handle_rect = self._get_slider_rects(slider)
        
        track_color = self._hex_to_rgb(slider.track_color)
        fill_color = self._hex_to_rgb(slider.fill_color)
        handle_color = self._hex_to_rgb(slider.handle_color)
        label_color = self._hex_to_rgb(slider.label_color)
        
        # Подпись
        font = self._get_font(24)
        label_surface = font.render(slider.label, True, label_color)
        label_x = track_rect.x
        label_y = track_rect.y - 25
        screen.blit(label_surface, (label_x, label_y))
        
        # Трек (фон)
        pygame.draw.rect(screen, track_color, track_rect, border_radius=5)
        
        # Заполнение
        relative_value = (slider.value - slider.min_value) / (slider.max_value - slider.min_value)
        fill_width = int(track_rect.width * relative_value)
        fill_rect = pygame.Rect(track_rect.x, track_rect.y, fill_width, track_rect.height)
        pygame.draw.rect(screen, fill_color, fill_rect, border_radius=5)
        
        # Ручка
        pygame.draw.rect(screen, handle_color, handle_rect, border_radius=3)
        
        # Значение в процентах
        value_text = f"{int(slider.value * 100)}%"
        value_surface = font.render(value_text, True, label_color)
        value_x = track_rect.right + 10
        value_y = track_rect.centery - value_surface.get_height() // 2
        screen.blit(value_surface, (value_x, value_y))


class VisualNovelEngine:
    """Основной движок визуальной новеллы."""
    
    def __init__(self, width: int = 1280, height: int = 720, title: str = "Visual Novel", debug_mode: bool = False, save_dir: str = "saves"):
        pygame.init()
        pygame.mixer.init()
        
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(title)
        
        self.clock = pygame.time.Clock()
        self.fps = 60
        self.running = False
        
        # Компоненты
        self.dialog_box = DialogBox(width, height)
        self.choice_menu = ChoiceMenu(width, height)
        self.animation_player = AnimationPlayer()
        self.debug_panel = DebugPanel(width, height)
        self.main_menu = MainMenu(width, height)  # Главное меню
        self.save_manager = SaveManager(save_dir)  # Менеджер сохранений с указанной папкой
        self.pause_menu = PauseMenu(width, height, self.save_manager)  # Меню паузы
        
        # Громкость
        self.music_volume = 0.8
        self.sound_volume = 0.8
        self.voice_volume = 0.8
        self.music_playing = False
        
        # Режим отладки (показывать панель выбора сцен)
        self.debug_mode = debug_mode
        if debug_mode:
            self.debug_panel.visible = True
        
        # Состояние
        self.story: Optional[Story] = None
        self.current_scene: Optional[Scene] = None
        self.current_dialog_index = 0
        self.background: Optional[pygame.Surface] = None
        self.background_color: Optional[Tuple[int, int, int]] = None
        self.characters_on_screen: List[CharacterSprite] = []
        self.images_on_screen: List[ImageSprite] = []  # Картинки на сцене
        self.texts_on_screen: List[TextSprite] = []  # Тексты на сцене
        
        # Состояние игры: "menu", "dialog", "choice", "end", "paused"
        self.state = "menu"
        self.state_before_pause = "dialog"  # Состояние перед паузой
        
        # Задержка диалога
        self.dialog_delay_start: Optional[int] = None  # Время начала задержки
        self.dialog_delay_duration: float = 0  # Длительность задержки в секундах
        self.dialog_is_delay_only: bool = False  # Текущий диалог - только задержка
        
        # Перемотка (skip)
        self.skip_mode = False  # Режим быстрой перемотки
        self.skip_delay = 50  # Задержка между диалогами при перемотке (мс)
        self.last_skip_time = 0
        self.skip_button_rect: Optional[pygame.Rect] = None  # Прямоугольник кнопки skip
        
        # Ресурсы
        self.backgrounds_cache = {}
        self.character_images_cache = {}
        
        # Звуковой канал для реплик
        self.dialog_sound_channel = pygame.mixer.Channel(1)  # Канал 1 для звуков диалога
    
    def _play_dialog_sound(self, sound_path: str):
        """Воспроизвести звук для реплики."""
        try:
            sound = pygame.mixer.Sound(sound_path)
            self.dialog_sound_channel.play(sound)
        except pygame.error:
            pass  # Игнорируем ошибки загрузки звука
    
    def _stop_dialog_sound(self):
        """Остановить звук текущей реплики."""
        try:
            self.dialog_sound_channel.stop()
        except pygame.error:
            pass

    def load_story(self, story: Story):
        """Загрузить историю."""
        self.story = story
        
        # Применяем цвета панели диалога из настроек проекта
        bg_color = self._hex_to_rgba(story.dialog_bg_color)
        border_color = self._hex_to_rgb(story.dialog_border_color)
        text_color = self._hex_to_rgb(story.dialog_text_color)
        self.dialog_box.set_colors(bg_color, border_color, text_color)
        
        # Загружаем список сцен для debug панели
        scenes_list = [(s.id, s.name or s.id) for s in story.scenes.values()]
        self.debug_panel.set_scenes(scenes_list)
        
        # Загружаем главное меню
        if story.main_menu.enabled:
            self.main_menu.load_config(story.main_menu)
            self.state = "menu"
        else:
            # Меню выключено - сразу переходим к игре
            self.state = "dialog"
            if story.start_scene_id:
                self.go_to_scene(story.start_scene_id)
        
        # Загружаем меню паузы
        if story.pause_menu.enabled:
            self.pause_menu.load_config(story.pause_menu)
    
    def _start_game(self):
        """Начать игру (из меню)."""
        if self.story and self.story.start_scene_id:
            self.state = "dialog"
            self.go_to_scene(self.story.start_scene_id)
    
    def load_story_from_file(self, filepath: str):
        """Загрузить историю из файла."""
        story = Story.load(filepath)
        self.load_story(story)
    
    def go_to_scene(self, scene_id: str):
        """Перейти к сцене."""
        if not self.story:
            return
        
        scene = self.story.get_scene(scene_id)
        if not scene:
            print(f"Сцена '{scene_id}' не найдена!")
            return
        
        # Останавливаем текущую музыку и звук диалога перед сменой сцены
        self._stop_music()
        self._stop_dialog_sound()
        
        self.current_scene = scene
        self.current_dialog_index = 0
        self.state = "dialog"
        self.choice_menu.is_active = False
        
        # Загрузка фона
        self._load_background(scene.background)
        self.background_color = scene.background_color
        
        # Загрузка картинок на сцене
        self._load_images(scene.images_on_screen)
        
        # Загрузка текстов на сцене
        self._load_texts(scene.texts_on_screen)
        
        # Загрузка персонажей на сцене
        self._load_characters(scene.characters_on_screen)
        
        # Загрузка музыки
        if scene.music:
            self._play_music(scene.music)
        
        # Загрузка фоновых анимаций
        self._start_background_animations(scene.background_animations)
        
        # Показать первый диалог
        if scene.dialogs:
            self._show_dialog(0)
    
    def _load_background(self, path: str):
        """Загрузить фон."""
        if not path:
            self.background = None
            return
        
        if path in self.backgrounds_cache:
            self.background = self.backgrounds_cache[path]
            return
        
        if os.path.exists(path):
            try:
                bg = pygame.image.load(path).convert()
                bg = pygame.transform.scale(bg, (self.width, self.height))
                self.backgrounds_cache[path] = bg
                self.background = bg
            except pygame.error:
                self.background = None
        else:
            self.background = None
    
    def _load_images(self, images_data: List[dict]):
        """Загрузить картинки на сцену."""
        self.images_on_screen = []
        
        for img_data in images_data:
            sprite = ImageSprite(self.width, self.height)
            sprite.image_id = img_data.get('id', '')
            
            # Загружаем изображение
            path = img_data.get('path', '')
            if path:
                sprite.load_image(path)
            
            # Устанавливаем трансформации
            sprite.set_transform(
                x=img_data.get('x', 0.5),
                y=img_data.get('y', 0.5),
                rotation=img_data.get('rotation', 0.0),
                flip_x=img_data.get('flip_x', False),
                flip_y=img_data.get('flip_y', False),
                scale=img_data.get('scale', 1.0),
                skew_x=img_data.get('skew_x', 0.0),
                skew_y=img_data.get('skew_y', 0.0),
                layer=img_data.get('layer', 0)
            )
            
            self.images_on_screen.append(sprite)
        
        # Сортируем по слою
        self.images_on_screen.sort(key=lambda s: s.layer)
    
    def _load_texts(self, texts_data: List[dict]):
        """Загрузить текстовые элементы на сцену."""
        self.texts_on_screen = []
        
        for text_data in texts_data:
            sprite = TextSprite(self.width, self.height)
            sprite.setup(
                text_id=text_data.get('id', ''),
                text=text_data.get('text', ''),
                x=text_data.get('x', 0.5),
                y=text_data.get('y', 0.5),
                font_size=text_data.get('font_size', 36),
                color=text_data.get('color', '#FFFFFF'),
                outline_color=text_data.get('outline_color', '#000000'),
                outline_width=text_data.get('outline_width', 2),
                animation=text_data.get('animation', 'none'),
                animation_duration=text_data.get('animation_duration', 1.0),
                block_skip=text_data.get('block_skip', False),
                rotation=text_data.get('rotation', 0.0),
                scale=text_data.get('scale', 1.0),
                order=text_data.get('order', 0),
                fade_in_duration=text_data.get('fade_in_duration', 1.0),
                fade_out_duration=text_data.get('fade_out_duration', 1.0),
                hold_duration=text_data.get('hold_duration', 2.0)
            )
            self.texts_on_screen.append(sprite)
        
        # Сортируем по порядку
        self.texts_on_screen.sort(key=lambda s: s.order)
        
        # Запускаем первый текст если он есть
        self._start_next_text()
    
    def _start_next_text(self):
        """Запустить следующий текст в очереди."""
        for sprite in self.texts_on_screen:
            if not sprite.started and sprite.animation != "none":
                sprite.start()
                return
    
    def _load_characters(self, characters_data: List[dict]):
        """Загрузить персонажей на сцену."""
        self.characters_on_screen = []
        
        for char_data in characters_data:
            char_id = char_data.get('id')
            emotion = char_data.get('emotion', 'default')
            
            if not self.story:
                continue
            
            character = self.story.get_character(char_id)
            if not character:
                continue
            
            sprite = CharacterSprite(self.width, self.height)
            sprite.character_id = char_id
            
            # Загрузка изображения по эмоции (сначала загружаем, потом трансформируем)
            image_path = character.images.get(emotion, character.images.get('default', ''))
            if image_path:
                sprite.load_image(image_path)
            
            # Проверяем есть ли точные координаты x, y
            if 'x' in char_data and 'y' in char_data:
                rotation = char_data.get('rotation', 0.0)
                flip_x = char_data.get('flip_x', False)
                flip_y = char_data.get('flip_y', False)
                scale = char_data.get('scale', 1.0)
                skew_x = char_data.get('skew_x', 0.0)
                skew_y = char_data.get('skew_y', 0.0)
                sprite.set_exact_position(char_data['x'], char_data['y'], rotation, flip_x, flip_y, scale, skew_x, skew_y)
            else:
                # Старый формат с position
                position = char_data.get('position', 'center')
                sprite.set_position(position)
            
            self.characters_on_screen.append(sprite)
    
    def _stop_music(self):
        """Остановить текущую музыку."""
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            self.music_playing = False
        except pygame.error:
            pass
    
    def _play_music(self, path: str):
        """Воспроизвести музыку."""
        if not path:
            return
        if os.path.exists(path):
            try:
                # Убеждаемся что предыдущая музыка выгружена
                try:
                    pygame.mixer.music.unload()
                except:
                    pass
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(self.music_volume)
                pygame.mixer.music.play(-1)  # Зациклить
                self.music_playing = True
            except pygame.error as e:
                print(f"Ошибка воспроизведения музыки: {e}")
                self.music_playing = False
        else:
            print(f"Файл музыки не найден: {path}")
    
    def _show_dialog(self, index: int):
        """Показать диалог по индексу."""
        if not self.current_scene or index >= len(self.current_scene.dialogs):
            return
        
        # Останавливаем звук предыдущей реплики
        self._stop_dialog_sound()
        
        dialog = self.current_scene.dialogs[index]
        
        # Устанавливаем задержку
        self.dialog_delay_duration = dialog.delay or 0
        self.dialog_is_delay_only = dialog.is_delay_only
        if self.dialog_delay_duration > 0:
            self.dialog_delay_start = pygame.time.get_ticks()
        else:
            self.dialog_delay_start = None
        
        # Воспроизвести звук для реплики (если есть)
        if dialog.sound_file and os.path.exists(dialog.sound_file):
            self._play_dialog_sound(dialog.sound_file)
        
        # Запускаем анимации для этой реплики
        if dialog.animations:
            self._start_dialog_animations(dialog.animations)
        
        # Если это просто задержка без текста - показываем пустой диалог
        if dialog.is_delay_only:
            self.dialog_box.set_dialog("", "", (255, 255, 255), None, 0)
            self.current_dialog_index = index
            return
        
        # Получение имени и цвета персонажа
        name = ""
        color = (255, 255, 255)
        name_bg_color = None
        
        if dialog.character_id and self.story:
            character = self.story.get_character(dialog.character_id)
            if character:
                name = character.name
                # Парсинг цвета из hex
                color = self._hex_to_rgb(character.color)
                # Фон под именем
                if character.name_bg_color:
                    name_bg_color = self._hex_to_rgba(character.name_bg_color)
                
                # Автоматически показываем персонажа когда он говорит
                # Если указана позиция в диалоге - используем её
                self._show_speaking_character(character, dialog.emotion, dialog.position)
        
        self.dialog_box.set_dialog(name, dialog.text, color, name_bg_color, dialog.typing_speed)
        self.current_dialog_index = index
    
    def _start_dialog_animations(self, animations: List[Dict]):
        """Запустить анимации для текущей реплики (добавляет к фоновым)."""
        # Не очищаем animation_player - оставляем фоновые анимации
        
        for anim in animations:
            char_id = anim.get('character_id')
            image_id = anim.get('image_id')
            keyframes = anim.get('keyframes', [])
            loop = anim.get('loop', False)
            
            if keyframes and (char_id or image_id):
                # Преобразуем keyframes в нужный формат если нужно
                kf_list = []
                for kf in keyframes:
                    kf_dict = {
                        'time': kf.get('time', 0),
                        'x': kf.get('x', 0.5),
                        'y': kf.get('y', 0.7),
                        'scale': kf.get('scale', 1.0),
                        'rotation': kf.get('rotation', 0),
                        'alpha': kf.get('alpha', 1.0)
                    }
                    kf_list.append(kf_dict)
                
                # Добавляем анимацию - используем character_id или image_id с префиксом
                anim_id = char_id if char_id else f"img_{image_id}"
                self.animation_player.add_animation(anim_id, kf_list, loop)
        
        # Запускаем все анимации
        self.animation_player.start_all()
    
    def _start_background_animations(self, animations: List[Dict]):
        """Запустить фоновые анимации сцены."""
        # Очищаем предыдущие анимации
        self.animation_player.clear()
        
        for anim in animations:
            char_id = anim.get('character_id')
            image_id = anim.get('image_id')
            keyframes = anim.get('keyframes', [])
            loop = anim.get('loop', False)
            
            if keyframes and (char_id or image_id):
                kf_list = []
                for kf in keyframes:
                    kf_dict = {
                        'time': kf.get('time', 0),
                        'x': kf.get('x', 0.5),
                        'y': kf.get('y', 0.7),
                        'scale': kf.get('scale', 1.0),
                        'rotation': kf.get('rotation', 0),
                        'alpha': kf.get('alpha', 1.0)
                    }
                    kf_list.append(kf_dict)
                
                anim_id = char_id if char_id else f"img_{image_id}"
                self.animation_player.add_animation(anim_id, kf_list, loop)
        
        # Запускаем все фоновые анимации
        self.animation_player.start_all()
    
    def _show_speaking_character(self, character: Character, emotion: str, position: Optional[Dict] = None):
        """Показать говорящего персонажа на экране."""
        # Проверяем, есть ли уже этот персонаж на экране
        # Если нет - добавляем в центр
        image_path = character.images.get(emotion, character.images.get('default', ''))
        
        if not image_path:
            return
        
        # Ищем существующий спрайт этого персонажа
        existing_sprite = None
        for sprite in self.characters_on_screen:
            if hasattr(sprite, 'character_id') and sprite.character_id == character.id:
                existing_sprite = sprite
                break
        
        if existing_sprite:
            # Обновляем эмоцию
            existing_sprite.load_image(image_path)
            # Если указана позиция в диалоге - применяем
            if position:
                rotation = position.get('rotation', 0.0)
                flip_x = position.get('flip_x', False)
                flip_y = position.get('flip_y', False)
                scale = position.get('scale', 1.0)
                skew_x = position.get('skew_x', 0.0)
                skew_y = position.get('skew_y', 0.0)
                existing_sprite.set_exact_position(position['x'], position['y'], rotation, flip_x, flip_y, scale, skew_x, skew_y)
        else:
            # Создаём новый спрайт
            sprite = CharacterSprite(self.width, self.height)
            sprite.character_id = character.id  # Сохраняем ID для идентификации
            
            # Позиция из диалога или по умолчанию
            if position:
                if sprite.load_image(image_path):
                    rotation = position.get('rotation', 0.0)
                    flip_x = position.get('flip_x', False)
                    flip_y = position.get('flip_y', False)
                    scale = position.get('scale', 1.0)
                    skew_x = position.get('skew_x', 0.0)
                    skew_y = position.get('skew_y', 0.0)
                    sprite.set_exact_position(position['x'], position['y'], rotation, flip_x, flip_y, scale, skew_x, skew_y)
                    self.characters_on_screen.append(sprite)
            else:
                sprite.set_position('center')
                if sprite.load_image(image_path):
                    self.characters_on_screen.append(sprite)
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Конвертировать HEX цвет в RGB."""
        hex_color = hex_color.lstrip('#')
        try:
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except (ValueError, IndexError):
            return (255, 255, 255)
    
    def _hex_to_rgba(self, hex_color: str) -> Tuple[int, int, int, int]:
        """Конвертировать HEX цвет в RGBA."""
        hex_color = hex_color.lstrip('#')
        try:
            if len(hex_color) == 8:  # RRGGBBAA
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4, 6))
            elif len(hex_color) == 6:  # RRGGBB
                rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                return rgb + (255,)
            else:
                return (255, 255, 255, 255)
        except (ValueError, IndexError):
            return (255, 255, 255, 255)
    
    def _is_delay_active(self) -> bool:
        """Проверить, активна ли задержка диалога."""
        if self.dialog_delay_start is None or self.dialog_delay_duration <= 0:
            return False
        elapsed = (pygame.time.get_ticks() - self.dialog_delay_start) / 1000.0
        return elapsed < self.dialog_delay_duration
    
    def _next_dialog(self):
        """Перейти к следующему диалогу."""
        if not self.current_scene:
            return
        
        # Проверяем, блокирует ли анимация текста пропуск
        if self._is_text_animation_blocking():
            return
        
        # Проверяем задержку (нельзя пропустить пока идёт задержка)
        if self._is_delay_active():
            return
        
        # Если текст ещё печатается - показать весь (кроме delay-only)
        if not self.dialog_box.is_complete and not self.dialog_is_delay_only:
            self.dialog_box.skip_animation()
            return
        
        # Следующий диалог
        next_index = self.current_dialog_index + 1
        
        if next_index < len(self.current_scene.dialogs):
            self._show_dialog(next_index)
        else:
            # Конец диалогов - показать выборы или перейти к следующей сцене
            if self.current_scene.choices:
                self.state = "choice"
                self.choice_menu.set_choices(self.current_scene.choices)
            elif self.current_scene.next_scene_id:
                self.go_to_scene(self.current_scene.next_scene_id)
            else:
                # Конец истории
                self._show_end_screen()
    
    def _show_end_screen(self):
        """Показать экран конца."""
        self.state = "end"
    
    def handle_events(self):
        """Обработка событий."""
        # Проверяем зажатие Ctrl для временной перемотки
        keys = pygame.key.get_pressed()
        ctrl_held = keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            # Обработка событий меню паузы (если активно)
            if self.pause_menu.active:
                action = self.pause_menu.handle_event(event)
                if action == "resume":
                    self.state = self.state_before_pause
                elif action == "main_menu":
                    self._return_to_menu()
                elif action == "exit":
                    self.running = False
                elif action and action.startswith("save:"):
                    slot_id = action.split(":")[1]
                    self._save_game(slot_id)
                elif action and action.startswith("load:"):
                    slot_id = action.split(":")[1]
                    self._load_game(slot_id)
                continue
            
            # Обработка событий главного меню
            if self.state == "menu":
                action = self.main_menu.handle_event(event)
                if action == "start":
                    self._start_game()
                elif action == "continue":
                    # Открываем экран загрузки
                    if self.save_manager.has_any_save():
                        self._open_pause_menu()
                        self.pause_menu.current_screen = "load"
                    else:
                        self._start_game()
                elif action == "exit":
                    self.running = False
                continue
            
            # Обработка событий debug панели (если видима)
            if self.debug_panel.visible:
                selected_scene = self.debug_panel.handle_event(event)
                if selected_scene:
                    self.go_to_scene(selected_scene)
                    continue
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # Открываем меню паузы если оно включено
                    if self.story and self.story.pause_menu.enabled and self.state in ("dialog", "choice"):
                        self._open_pause_menu()
                    # Иначе возвращаемся в главное меню если оно включено
                    elif self.story and self.story.main_menu.enabled and self.state != "menu":
                        self._return_to_menu()
                    else:
                        self.running = False
                
                # F3 - переключение debug панели
                elif event.key == pygame.K_F3:
                    self.debug_panel.toggle()
                
                # Клавиша S - включить/выключить перемотку
                elif event.key == pygame.K_s and self.state == "dialog":
                    self.skip_mode = not self.skip_mode
                
                elif self.state == "dialog":
                    if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        self._next_dialog()
                
                elif self.state == "choice":
                    # На выборе перемотка отключается
                    self.skip_mode = False
                    result = self.choice_menu.handle_input(event)
                    if result:
                        self.go_to_scene(result)
                
                elif self.state == "end":
                    if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        if self.story and self.story.main_menu.enabled:
                            self._return_to_menu()
                        else:
                            self.running = False
            
            elif event.type == pygame.KEYUP:
                # При отпускании Ctrl перемотка не отключается если была включена S
                pass
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if self.state == "dialog" and event.button == 1:
                    # Проверяем клик по кнопке Skip
                    if self.skip_button_rect and self.skip_button_rect.collidepoint(event.pos):
                        self.skip_mode = not self.skip_mode
                    else:
                        self._next_dialog()
                elif self.state == "choice":
                    self.skip_mode = False
                    result = self.choice_menu.handle_input(event)
                    if result:
                        self.go_to_scene(result)
            
            elif event.type == pygame.MOUSEMOTION:
                if self.state == "choice":
                    self.choice_menu.handle_input(event)
        
        # Перемотка при зажатом Ctrl или включённом режиме
        if self.state == "dialog" and (ctrl_held or self.skip_mode):
            current_time = pygame.time.get_ticks()
            if current_time - self.last_skip_time >= self.skip_delay:
                self.last_skip_time = current_time
                if self.dialog_box.is_complete:
                    self._next_dialog()
                else:
                    self.dialog_box.skip_animation()
    
    def _open_pause_menu(self):
        """Открыть меню паузы."""
        self.state_before_pause = self.state
        # Делаем скриншот текущего состояния
        screenshot = self.screen.copy()
        self.pause_menu.open(screenshot)
    
    def _save_game(self, slot_id: str):
        """Сохранить игру."""
        if not self.current_scene:
            return
        
        screenshot = self.pause_menu.current_screenshot or self.screen.copy()
        self.save_manager.save_game(
            slot_id=slot_id,
            scene_id=self.current_scene.id,
            scene_name=self.current_scene.name or self.current_scene.id,
            dialog_index=self.current_dialog_index,
            screenshot=screenshot
        )
        # Обновляем информацию о сохранениях
        self.save_manager._load_saves_info()
    
    def _load_game(self, slot_id: str):
        """Загрузить игру."""
        save_data = self.save_manager.load_game(slot_id)
        if not save_data:
            return
        
        scene_id = save_data.get('scene_id')
        dialog_index = save_data.get('dialog_index', 0)
        
        if scene_id:
            self.go_to_scene(scene_id)
            # Переходим к сохранённому диалогу
            self.current_dialog_index = min(dialog_index, len(self.current_scene.dialogs) - 1 if self.current_scene and self.current_scene.dialogs else 0)
            if self.current_scene and self.current_scene.dialogs:
                self._show_dialog(self.current_dialog_index)
            self.pause_menu.close()
            self.state = "dialog"
    
    def _return_to_menu(self):
        """Вернуться в главное меню."""
        self._stop_music()
        self._stop_dialog_sound()
        self.current_scene = None
        self.characters_on_screen.clear()
        self.images_on_screen.clear()
        self.texts_on_screen.clear()
        self.background = None
        
        # Перезагружаем меню
        if self.story:
            self.main_menu.load_config(self.story.main_menu)
            self.main_menu.active = True
        self.state = "menu"
    
    def _is_text_animation_blocking(self) -> bool:
        """Проверить, блокирует ли анимация текста пропуск."""
        for text_sprite in self.texts_on_screen:
            if text_sprite.is_blocking():
                return True
        return False
    
    def update(self):
        """Обновление состояния."""
        dt = self.clock.get_time() / 1000.0  # delta time в секундах
        
        # Обновление меню паузы
        if self.pause_menu.active:
            self.pause_menu.update(dt)
            return
        
        if self.state == "menu":
            self.main_menu.update()
        elif self.state == "dialog":
            self.dialog_box.update()
            
            # Автопереход для delay_only диалогов когда задержка закончилась
            if self.dialog_is_delay_only and not self._is_delay_active():
                self._next_dialog()
        
        # Обновление анимаций (кроме меню)
        if self.state != "menu":
            self.animation_player.update(self.characters_on_screen, self.images_on_screen)
            
            # Обновление анимаций текстов и запуск следующего
            any_just_completed = False
            for text_sprite in self.texts_on_screen:
                was_complete = text_sprite.animation_complete
                text_sprite.update()
                if not was_complete and text_sprite.animation_complete:
                    any_just_completed = True
            
            # Если текст завершился, запускаем следующий
            if any_just_completed:
                self._start_next_text()
    
    def draw(self):
        """Отрисовка."""
        # Отрисовка главного меню
        if self.state == "menu":
            self.main_menu.draw(self.screen)
            pygame.display.flip()
            return
        
        # Фон
        if self.background:
            self.screen.blit(self.background, (0, 0))
        elif self.background_color:
            # Заливка выбранным цветом
            self.screen.fill(self.background_color)
        else:
            # Градиент по умолчанию
            for y in range(self.height):
                color = (
                    int(30 + (y / self.height) * 20),
                    int(30 + (y / self.height) * 30),
                    int(50 + (y / self.height) * 40)
                )
                pygame.draw.line(self.screen, color, (0, y), (self.width, y))
        
        # Картинки (отрисовываются за персонажами)
        for sprite in self.images_on_screen:
            sprite.draw(self.screen)
        
        # Персонажи
        for sprite in self.characters_on_screen:
            sprite.draw(self.screen)
        
        # Тексты на сцене
        for text_sprite in self.texts_on_screen:
            text_sprite.draw(self.screen)
        
        # Диалоговое окно (показываем только если есть диалоги на сцене)
        has_dialogs = self.current_scene and len(self.current_scene.dialogs) > 0
        if self.state in ("dialog", "end") and has_dialogs:
            self.dialog_box.draw(self.screen)
            # Кнопка Skip (рядом со стрелкой)
            if self.state == "dialog":
                keys = pygame.key.get_pressed()
                ctrl_held = keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]
                self.skip_button_rect = self.dialog_box.draw_skip_button(
                    self.screen, 
                    is_active=(self.skip_mode or ctrl_held)
                )
        
        # Меню выбора
        if self.state == "choice":
            self.choice_menu.draw(self.screen)
        
        # Индикатор режима перемотки (в углу)
        keys = pygame.key.get_pressed()
        ctrl_held = keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]
        if self.skip_mode or (ctrl_held and self.state == "dialog"):
            self._draw_skip_indicator()
        
        # Экран конца
        if self.state == "end":
            self._draw_end_screen()
        
        # Debug панель (поверх всего)
        current_scene_id = self.current_scene.id if self.current_scene else None
        self.debug_panel.draw(self.screen, current_scene_id)
        
        # Меню паузы (поверх всего)
        if self.pause_menu.active:
            self.pause_menu.draw(self.screen)
        
        pygame.display.flip()
    
    def _draw_skip_indicator(self):
        """Отрисовать индикатор перемотки."""
        font = pygame.font.Font(None, 28)
        text = font.render("▶▶ SKIP (S)", True, (255, 255, 100))
        # В правом верхнем углу
        text_rect = text.get_rect(topright=(self.width - 15, 15))
        # Полупрозрачный фон
        bg_rect = text_rect.inflate(16, 8)
        bg_surface = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
        bg_surface.fill((0, 0, 0, 150))
        self.screen.blit(bg_surface, bg_rect.topleft)
        self.screen.blit(text, text_rect)
    
    def _draw_end_screen(self):
        """Отрисовать экран конца."""
        font = pygame.font.Font(None, 72)
        text = font.render("Конец", True, (255, 255, 255))
        text_rect = text.get_rect(center=(self.width // 2, self.height // 2 - 50))
        self.screen.blit(text, text_rect)
        
        small_font = pygame.font.Font(None, 32)
        hint = small_font.render("Нажмите любую клавишу для выхода", True, (200, 200, 200))
        hint_rect = hint.get_rect(center=(self.width // 2, self.height // 2 + 30))
        self.screen.blit(hint, hint_rect)
    
    def run(self):
        """Запустить игровой цикл."""
        self.running = True
        
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(self.fps)
        
        pygame.quit()


def run_demo():
    """Запустить демо-версию."""
    from story import create_demo_story
    
    engine = VisualNovelEngine(1280, 720, "Visual Novel Demo")
    story = create_demo_story()
    engine.load_story(story)
    engine.run()


if __name__ == "__main__":
    run_demo()
