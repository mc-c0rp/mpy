"""
Модуль для структуры данных визуальной новеллы.
Содержит классы для сцен, диалогов, персонажей и выборов.
"""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Tuple


@dataclass
class MenuButton:
    """Кнопка главного меню."""
    id: str  # Уникальный ID кнопки
    text: str  # Текст на кнопке
    action: str  # Действие: "start", "continue", "settings", "exit"
    x: float = 0.5  # Позиция X (0.0 - 1.0)
    y: float = 0.5  # Позиция Y (0.0 - 1.0)
    width: int = 300  # Ширина кнопки
    height: int = 60  # Высота кнопки
    font_size: int = 32  # Размер шрифта
    text_color: str = "#FFFFFF"  # Цвет текста
    bg_color: str = "#333366AA"  # Цвет фона (с альфой)
    hover_color: str = "#4444AACC"  # Цвет при наведении
    click_color: str = "#222244DD"  # Цвет при нажатии
    border_color: str = "#6666AA"  # Цвет рамки
    border_width: int = 2  # Толщина рамки
    border_radius: int = 10  # Скругление углов
    visible: bool = True  # Видимость кнопки
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MenuButton':
        return cls(**data)


@dataclass
class MenuSlider:
    """Ползунок настроек."""
    id: str  # Уникальный ID
    label: str  # Подпись
    setting: str  # Настройка: "music_volume", "sound_volume", "voice_volume"
    x: float = 0.5
    y: float = 0.5
    width: int = 300
    height: int = 40
    min_value: float = 0.0
    max_value: float = 1.0
    value: float = 0.8
    label_color: str = "#FFFFFF"
    track_color: str = "#333333"
    fill_color: str = "#6666AA"
    handle_color: str = "#AAAAFF"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MenuSlider':
        return cls(**data)


@dataclass
class MenuLogo:
    """Логотип игры в меню."""
    image_path: str = ""  # Путь к изображению
    x: float = 0.5  # Позиция X (0.0 - 1.0)
    y: float = 0.2  # Позиция Y (0.0 - 1.0)
    scale: float = 1.0  # Масштаб
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MenuLogo':
        return cls(**data)


@dataclass
class MenuSounds:
    """Звуки меню."""
    background_music: str = ""  # Фоновая музыка
    hover_sound: str = ""  # Звук при наведении
    click_sound: str = ""  # Звук при клике
    back_sound: str = ""  # Звук при возврате
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MenuSounds':
        return cls(**data)


@dataclass
class MainMenuConfig:
    """Конфигурация главного меню."""
    enabled: bool = True  # Включено ли меню
    background: str = ""  # Путь к фону
    background_color: Optional[Tuple[int, int, int]] = None  # Цвет фона
    
    # Логотип
    logo: MenuLogo = field(default_factory=MenuLogo)
    
    # Кнопки главного меню
    buttons: List[MenuButton] = field(default_factory=lambda: [
        MenuButton(id="btn_start", text="Начать игру", action="start", x=0.5, y=0.45),
        MenuButton(id="btn_continue", text="Продолжить", action="continue", x=0.5, y=0.55),
        MenuButton(id="btn_settings", text="Настройки", action="settings", x=0.5, y=0.65),
        MenuButton(id="btn_exit", text="Выход", action="exit", x=0.5, y=0.75),
    ])
    
    # Настройки (отдельный экран)
    settings_title: str = "Настройки"
    settings_title_x: float = 0.5
    settings_title_y: float = 0.15
    settings_title_size: int = 48
    settings_title_color: str = "#FFFFFF"
    
    # Слайдеры настроек
    sliders: List[MenuSlider] = field(default_factory=lambda: [
        MenuSlider(id="slider_music", label="Музыка", setting="music_volume", x=0.5, y=0.35, value=0.8),
        MenuSlider(id="slider_sound", label="Звуки", setting="sound_volume", x=0.5, y=0.50, value=0.8),
        MenuSlider(id="slider_voice", label="Голос", setting="voice_volume", x=0.5, y=0.65, value=0.8),
    ])
    
    # Кнопка "Назад" в настройках
    back_button: MenuButton = field(default_factory=lambda: MenuButton(
        id="btn_back", text="Назад", action="back", x=0.5, y=0.85
    ))
    
    # Звуки
    sounds: MenuSounds = field(default_factory=MenuSounds)
    
    # Анимации (фиксированные, нельзя менять в редакторе)
    animation_enabled: bool = True
    button_hover_scale: float = 1.05  # Масштаб при наведении
    button_click_scale: float = 0.95  # Масштаб при клике
    fade_in_duration: float = 0.5  # Длительность появления
    
    def to_dict(self) -> dict:
        return {
            'enabled': self.enabled,
            'background': self.background,
            'background_color': self.background_color,
            'logo': self.logo.to_dict(),
            'buttons': [b.to_dict() for b in self.buttons],
            'settings_title': self.settings_title,
            'settings_title_x': self.settings_title_x,
            'settings_title_y': self.settings_title_y,
            'settings_title_size': self.settings_title_size,
            'settings_title_color': self.settings_title_color,
            'sliders': [s.to_dict() for s in self.sliders],
            'back_button': self.back_button.to_dict(),
            'sounds': self.sounds.to_dict(),
            'animation_enabled': self.animation_enabled,
            'button_hover_scale': self.button_hover_scale,
            'button_click_scale': self.button_click_scale,
            'fade_in_duration': self.fade_in_duration,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MainMenuConfig':
        config = cls(
            enabled=data.get('enabled', True),
            background=data.get('background', ''),
            background_color=tuple(data['background_color']) if data.get('background_color') else None,
        )
        if 'logo' in data:
            config.logo = MenuLogo.from_dict(data['logo'])
        if 'buttons' in data:
            config.buttons = [MenuButton.from_dict(b) for b in data['buttons']]
        if 'sliders' in data:
            config.sliders = [MenuSlider.from_dict(s) for s in data['sliders']]
        if 'back_button' in data:
            config.back_button = MenuButton.from_dict(data['back_button'])
        if 'sounds' in data:
            config.sounds = MenuSounds.from_dict(data['sounds'])
        
        config.settings_title = data.get('settings_title', 'Настройки')
        config.settings_title_x = data.get('settings_title_x', 0.5)
        config.settings_title_y = data.get('settings_title_y', 0.15)
        config.settings_title_size = data.get('settings_title_size', 48)
        config.settings_title_color = data.get('settings_title_color', '#FFFFFF')
        config.animation_enabled = data.get('animation_enabled', True)
        config.button_hover_scale = data.get('button_hover_scale', 1.05)
        config.button_click_scale = data.get('button_click_scale', 0.95)
        config.fade_in_duration = data.get('fade_in_duration', 0.5)
        
        return config


@dataclass
class PauseMenuButton:
    """Кнопка меню паузы."""
    id: str  # Уникальный ID кнопки
    text: str  # Текст на кнопке
    action: str  # Действие: "resume", "save", "load", "settings", "main_menu", "exit"
    x: float = 0.5  # Позиция X (0.0 - 1.0)
    y: float = 0.5  # Позиция Y (0.0 - 1.0)
    width: int = 250  # Ширина кнопки
    height: int = 50  # Высота кнопки
    font_size: int = 28  # Размер шрифта
    text_color: str = "#FFFFFF"  # Цвет текста
    bg_color: str = "#333366CC"  # Цвет фона (с альфой)
    hover_color: str = "#4444AADD"  # Цвет при наведении
    click_color: str = "#222244EE"  # Цвет при нажатии
    border_color: str = "#6666AA"  # Цвет рамки
    border_width: int = 2  # Толщина рамки
    border_radius: int = 8  # Скругление углов
    visible: bool = True  # Видимость кнопки
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PauseMenuButton':
        return cls(**data)


@dataclass
class SaveSlotConfig:
    """Конфигурация отображения слота сохранения."""
    width: int = 280  # Ширина слота
    height: int = 180  # Высота слота
    thumbnail_height: int = 120  # Высота миниатюры
    bg_color: str = "#222244DD"  # Цвет фона
    hover_color: str = "#333366EE"  # Цвет при наведении
    selected_color: str = "#4444AAFF"  # Цвет выбранного
    empty_color: str = "#1A1A2ADD"  # Цвет пустого слота
    border_color: str = "#6666AA"  # Цвет рамки
    border_width: int = 2
    border_radius: int = 8
    text_color: str = "#FFFFFF"  # Цвет текста
    date_color: str = "#AAAACC"  # Цвет даты
    empty_text: str = "Пустой слот"  # Текст пустого слота
    font_size: int = 18
    date_font_size: int = 14
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SaveSlotConfig':
        return cls(**data)


@dataclass
class SaveLoadScreenConfig:
    """Конфигурация экрана сохранения/загрузки."""
    title_save: str = "Сохранение"
    title_load: str = "Загрузка"
    title_x: float = 0.5
    title_y: float = 0.08
    title_size: int = 42
    title_color: str = "#FFFFFF"
    
    # Сетка слотов (4 слота на страницу, 2x2)
    slots_start_x: float = 0.25  # Начальная позиция X
    slots_start_y: float = 0.18  # Начальная позиция Y
    slots_spacing_x: int = 300  # Расстояние между слотами по X
    slots_spacing_y: int = 200  # Расстояние между слотами по Y
    slots_per_page: int = 4  # Слотов на страницу
    total_pages: int = 5  # Всего страниц (20 слотов)
    
    # Конфигурация слота
    slot_config: SaveSlotConfig = field(default_factory=SaveSlotConfig)
    
    # Навигация по страницам
    page_indicator_y: float = 0.88
    page_button_width: int = 100
    page_button_height: int = 40
    prev_button_x: float = 0.35
    next_button_x: float = 0.65
    
    # Кнопка "Назад"
    back_button: PauseMenuButton = field(default_factory=lambda: PauseMenuButton(
        id="btn_back_save", text="Назад", action="back", x=0.5, y=0.95, width=150, height=40
    ))
    
    def to_dict(self) -> dict:
        return {
            'title_save': self.title_save,
            'title_load': self.title_load,
            'title_x': self.title_x,
            'title_y': self.title_y,
            'title_size': self.title_size,
            'title_color': self.title_color,
            'slots_start_x': self.slots_start_x,
            'slots_start_y': self.slots_start_y,
            'slots_spacing_x': self.slots_spacing_x,
            'slots_spacing_y': self.slots_spacing_y,
            'slots_per_page': self.slots_per_page,
            'total_pages': self.total_pages,
            'slot_config': self.slot_config.to_dict(),
            'page_indicator_y': self.page_indicator_y,
            'page_button_width': self.page_button_width,
            'page_button_height': self.page_button_height,
            'prev_button_x': self.prev_button_x,
            'next_button_x': self.next_button_x,
            'back_button': self.back_button.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SaveLoadScreenConfig':
        config = cls(
            title_save=data.get('title_save', 'Сохранение'),
            title_load=data.get('title_load', 'Загрузка'),
            title_x=data.get('title_x', 0.5),
            title_y=data.get('title_y', 0.08),
            title_size=data.get('title_size', 42),
            title_color=data.get('title_color', '#FFFFFF'),
            slots_start_x=data.get('slots_start_x', 0.25),
            slots_start_y=data.get('slots_start_y', 0.18),
            slots_spacing_x=data.get('slots_spacing_x', 300),
            slots_spacing_y=data.get('slots_spacing_y', 200),
            slots_per_page=data.get('slots_per_page', 4),
            total_pages=data.get('total_pages', 5),
            page_indicator_y=data.get('page_indicator_y', 0.88),
            page_button_width=data.get('page_button_width', 100),
            page_button_height=data.get('page_button_height', 40),
            prev_button_x=data.get('prev_button_x', 0.35),
            next_button_x=data.get('next_button_x', 0.65),
        )
        if 'slot_config' in data:
            config.slot_config = SaveSlotConfig.from_dict(data['slot_config'])
        if 'back_button' in data:
            config.back_button = PauseMenuButton.from_dict(data['back_button'])
        return config


@dataclass
class PauseMenuConfig:
    """Конфигурация меню паузы."""
    enabled: bool = True  # Включено ли меню паузы
    
    # Затемнение фона
    overlay_color: str = "#000000"  # Цвет затемнения
    overlay_alpha: int = 180  # Прозрачность (0-255)
    
    # Панель меню
    panel_width: int = 400
    panel_height: int = 500
    panel_x: float = 0.5  # Позиция центра панели (0.0 - 1.0)
    panel_y: float = 0.5
    panel_bg_color: str = "#1A1A3CDD"
    panel_border_color: str = "#4444AA"
    panel_border_width: int = 3
    panel_border_radius: int = 15
    
    # Заголовок
    title: str = "Пауза"
    title_x: float = 0.5
    title_y: float = 0.12
    title_size: int = 42
    title_color: str = "#FFFFFF"
    
    # Кнопки меню паузы
    buttons: List[PauseMenuButton] = field(default_factory=lambda: [
        PauseMenuButton(id="btn_resume", text="Продолжить", action="resume", x=0.5, y=0.28),
        PauseMenuButton(id="btn_save", text="Сохранить", action="save", x=0.5, y=0.40),
        PauseMenuButton(id="btn_load", text="Загрузить", action="load", x=0.5, y=0.52),
        PauseMenuButton(id="btn_settings", text="Настройки", action="settings", x=0.5, y=0.64),
        PauseMenuButton(id="btn_main_menu", text="В главное меню", action="main_menu", x=0.5, y=0.76),
        PauseMenuButton(id="btn_exit", text="Выход из игры", action="exit", x=0.5, y=0.88),
    ])
    
    # Экран сохранения/загрузки
    save_load_screen: SaveLoadScreenConfig = field(default_factory=SaveLoadScreenConfig)
    
    # Настройки (слайдеры)
    settings_title: str = "Настройки"
    settings_title_x: float = 0.5
    settings_title_y: float = 0.12
    settings_title_size: int = 42
    settings_title_color: str = "#FFFFFF"
    
    settings_sliders: List[MenuSlider] = field(default_factory=lambda: [
        MenuSlider(id="pause_slider_music", label="Музыка", setting="music_volume", x=0.5, y=0.30, value=0.8),
        MenuSlider(id="pause_slider_sound", label="Звуки", setting="sound_volume", x=0.5, y=0.45, value=0.8),
        MenuSlider(id="pause_slider_voice", label="Голос", setting="voice_volume", x=0.5, y=0.60, value=0.8),
    ])
    
    settings_back_button: PauseMenuButton = field(default_factory=lambda: PauseMenuButton(
        id="btn_settings_back", text="Назад", action="back", x=0.5, y=0.80
    ))
    
    # Звуки
    open_sound: str = ""  # Звук открытия меню
    close_sound: str = ""  # Звук закрытия
    hover_sound: str = ""  # Звук наведения
    click_sound: str = ""  # Звук клика
    
    # Анимации
    animation_enabled: bool = True
    fade_duration: float = 0.2  # Длительность появления
    
    def to_dict(self) -> dict:
        return {
            'enabled': self.enabled,
            'overlay_color': self.overlay_color,
            'overlay_alpha': self.overlay_alpha,
            'panel_width': self.panel_width,
            'panel_height': self.panel_height,
            'panel_x': self.panel_x,
            'panel_y': self.panel_y,
            'panel_bg_color': self.panel_bg_color,
            'panel_border_color': self.panel_border_color,
            'panel_border_width': self.panel_border_width,
            'panel_border_radius': self.panel_border_radius,
            'title': self.title,
            'title_x': self.title_x,
            'title_y': self.title_y,
            'title_size': self.title_size,
            'title_color': self.title_color,
            'buttons': [b.to_dict() for b in self.buttons],
            'save_load_screen': self.save_load_screen.to_dict(),
            'settings_title': self.settings_title,
            'settings_title_x': self.settings_title_x,
            'settings_title_y': self.settings_title_y,
            'settings_title_size': self.settings_title_size,
            'settings_title_color': self.settings_title_color,
            'settings_sliders': [s.to_dict() for s in self.settings_sliders],
            'settings_back_button': self.settings_back_button.to_dict(),
            'open_sound': self.open_sound,
            'close_sound': self.close_sound,
            'hover_sound': self.hover_sound,
            'click_sound': self.click_sound,
            'animation_enabled': self.animation_enabled,
            'fade_duration': self.fade_duration,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PauseMenuConfig':
        config = cls(
            enabled=data.get('enabled', True),
            overlay_color=data.get('overlay_color', '#000000'),
            overlay_alpha=data.get('overlay_alpha', 180),
            panel_width=data.get('panel_width', 400),
            panel_height=data.get('panel_height', 500),
            panel_x=data.get('panel_x', 0.5),
            panel_y=data.get('panel_y', 0.5),
            panel_bg_color=data.get('panel_bg_color', '#1A1A3CDD'),
            panel_border_color=data.get('panel_border_color', '#4444AA'),
            panel_border_width=data.get('panel_border_width', 3),
            panel_border_radius=data.get('panel_border_radius', 15),
            title=data.get('title', 'Пауза'),
            title_x=data.get('title_x', 0.5),
            title_y=data.get('title_y', 0.12),
            title_size=data.get('title_size', 42),
            title_color=data.get('title_color', '#FFFFFF'),
            settings_title=data.get('settings_title', 'Настройки'),
            settings_title_x=data.get('settings_title_x', 0.5),
            settings_title_y=data.get('settings_title_y', 0.12),
            settings_title_size=data.get('settings_title_size', 42),
            settings_title_color=data.get('settings_title_color', '#FFFFFF'),
            open_sound=data.get('open_sound', ''),
            close_sound=data.get('close_sound', ''),
            hover_sound=data.get('hover_sound', ''),
            click_sound=data.get('click_sound', ''),
            animation_enabled=data.get('animation_enabled', True),
            fade_duration=data.get('fade_duration', 0.2),
        )
        if 'buttons' in data:
            config.buttons = [PauseMenuButton.from_dict(b) for b in data['buttons']]
        if 'save_load_screen' in data:
            config.save_load_screen = SaveLoadScreenConfig.from_dict(data['save_load_screen'])
        if 'settings_sliders' in data:
            config.settings_sliders = [MenuSlider.from_dict(s) for s in data['settings_sliders']]
        if 'settings_back_button' in data:
            config.settings_back_button = PauseMenuButton.from_dict(data['settings_back_button'])
        return config


@dataclass
class Character:
    """Персонаж визуальной новеллы."""
    id: str
    name: str
    color: str = "#FFFFFF"  # Цвет имени в диалогах
    name_bg_color: str = ""  # Цвет фона под именем (пусто = прозрачный)
    images: Dict[str, str] = field(default_factory=dict)  # emotion -> image_path
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Character':
        return cls(**data)


@dataclass
class Choice:
    """Выбор в диалоге."""
    text: str
    next_scene_id: str
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Choice':
        return cls(**data)


@dataclass
class DialogLine:
    """Одна строка диалога."""
    character_id: Optional[str] = None  # None для повествователя
    text: str = ""
    emotion: str = "default"  # Эмоция персонажа (для выбора спрайта)
    animations: List[Dict[str, Any]] = field(default_factory=list)  # Анимации для этой реплики
    # Позиция персонажа для этой реплики (None = использовать позицию из сцены)
    position: Optional[Dict[str, float]] = None  # {'x': 0.5, 'y': 0.7, 'rotation': 0}
    sound_file: Optional[str] = None  # Путь к звуковому файлу (mp3/wav) для этой реплики
    typing_speed: Optional[float] = None  # Длительность появления текста в секундах, None = по умолчанию, 0 = мгновенно
    delay: Optional[float] = None  # Задержка перед возможностью пролистнуть (секунды), None = без задержки
    is_delay_only: bool = False  # Если True - это просто задержка без текста
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DialogLine':
        return cls(
            character_id=data.get('character_id'),
            text=data.get('text', ''),
            emotion=data.get('emotion', 'default'),
            animations=data.get('animations', []),
            position=data.get('position'),
            sound_file=data.get('sound_file'),
            typing_speed=data.get('typing_speed'),
            delay=data.get('delay'),
            is_delay_only=data.get('is_delay_only', False)
        )


@dataclass
class AnimationKeyframe:
    """Ключевой кадр анимации."""
    time: float  # Время в секундах
    x: float  # Позиция X (0.0 - 1.0, относительно ширины экрана)
    y: float  # Позиция Y (0.0 - 1.0, относительно высоты экрана)
    scale: float = 1.0  # Масштаб
    alpha: float = 1.0  # Прозрачность (0.0 - 1.0)
    rotation: float = 0.0  # Угол поворота в градусах
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AnimationKeyframe':
        return cls(**data)


@dataclass 
class CharacterAnimation:
    """Анимация персонажа."""
    character_id: str
    keyframes: List[AnimationKeyframe] = field(default_factory=list)
    loop: bool = False  # Зацикленная анимация
    
    def to_dict(self) -> dict:
        return {
            'character_id': self.character_id,
            'keyframes': [k.to_dict() for k in self.keyframes],
            'loop': self.loop
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CharacterAnimation':
        return cls(
            character_id=data['character_id'],
            keyframes=[AnimationKeyframe.from_dict(k) for k in data.get('keyframes', [])],
            loop=data.get('loop', False)
        )


@dataclass
class Scene:
    """Сцена визуальной новеллы."""
    id: str
    name: str = "Новая сцена"
    background: str = ""  # Путь к фону
    background_color: Optional[Tuple[int, int, int]] = None  # Цвет фона если нет картинки
    dialogs: List[DialogLine] = field(default_factory=list)
    characters_on_screen: List[Dict[str, Any]] = field(default_factory=list)  # [{id, position, emotion}]
    images_on_screen: List[Dict[str, Any]] = field(default_factory=list)  # Картинки на сцене [{id, path, x, y, ...}]
    texts_on_screen: List[Dict[str, Any]] = field(default_factory=list)  # Тексты на сцене [{id, text, x, y, font_size, color, animation, ...}]
    background_animations: List[Dict[str, Any]] = field(default_factory=list)  # Фоновые анимации [{image_id/character_id, keyframes, loop}]
    choices: List[Choice] = field(default_factory=list)  # Выборы в конце сцены
    next_scene_id: Optional[str] = None  # Следующая сцена (если нет выборов)
    music: str = ""  # Путь к музыке
    
    def to_dict(self) -> dict:
        data = {
            'id': self.id,
            'name': self.name,
            'background': self.background,
            'background_color': self.background_color,
            'dialogs': [d.to_dict() for d in self.dialogs],
            'characters_on_screen': self.characters_on_screen,
            'images_on_screen': self.images_on_screen,
            'texts_on_screen': self.texts_on_screen,
            'background_animations': self.background_animations,
            'choices': [c.to_dict() for c in self.choices],
            'next_scene_id': self.next_scene_id,
            'music': self.music
        }
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Scene':
        return cls(
            id=data['id'],
            name=data.get('name', 'Сцена'),
            background=data.get('background', ''),
            background_color=tuple(data['background_color']) if data.get('background_color') else None,
            dialogs=[DialogLine.from_dict(d) for d in data.get('dialogs', [])],
            characters_on_screen=data.get('characters_on_screen', []),
            images_on_screen=data.get('images_on_screen', []),
            texts_on_screen=data.get('texts_on_screen', []),
            background_animations=data.get('background_animations', []),
            choices=[Choice.from_dict(c) for c in data.get('choices', [])],
            next_scene_id=data.get('next_scene_id'),
            music=data.get('music', '')
        )


@dataclass
class Story:
    """Полная история/проект визуальной новеллы."""
    title: str = "Моя визуальная новелла"
    author: str = ""
    version: str = "1.0"
    start_scene_id: str = ""
    dialog_bg_color: str = "#14142890"  # Цвет фона панели диалога (RGBA hex)
    dialog_border_color: str = "#646496"  # Цвет рамки панели
    dialog_text_color: str = "#FFFFFF"  # Цвет текста диалога
    main_menu: MainMenuConfig = field(default_factory=MainMenuConfig)  # Конфигурация главного меню
    pause_menu: PauseMenuConfig = field(default_factory=PauseMenuConfig)  # Конфигурация меню паузы
    characters: Dict[str, Character] = field(default_factory=dict)
    scenes: Dict[str, Scene] = field(default_factory=dict)
    
    # Server/distribution fields
    game_id: str = ""  # Unique ID on server (generated on first upload)
    description: str = ""  # Game description for library
    forked_from: Optional[str] = None  # Original game_id if this is a fork
    server_version: str = ""  # Version currently on server (for update checking)
    
    def add_character(self, character: Character):
        self.characters[character.id] = character
    
    def add_scene(self, scene: Scene):
        self.scenes[scene.id] = scene
        if not self.start_scene_id:
            self.start_scene_id = scene.id
    
    def get_character(self, char_id: str) -> Optional[Character]:
        return self.characters.get(char_id)
    
    def get_scene(self, scene_id: str) -> Optional[Scene]:
        return self.scenes.get(scene_id)
    
    def to_dict(self) -> dict:
        return {
            'title': self.title,
            'author': self.author,
            'version': self.version,
            'start_scene_id': self.start_scene_id,
            'dialog_bg_color': self.dialog_bg_color,
            'dialog_border_color': self.dialog_border_color,
            'dialog_text_color': self.dialog_text_color,
            'main_menu': self.main_menu.to_dict(),
            'pause_menu': self.pause_menu.to_dict(),
            'characters': {k: v.to_dict() for k, v in self.characters.items()},
            'scenes': {k: v.to_dict() for k, v in self.scenes.items()},
            'game_id': self.game_id,
            'description': self.description,
            'forked_from': self.forked_from,
            'server_version': self.server_version
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Story':
        story = cls(
            title=data.get('title', 'Без названия'),
            author=data.get('author', ''),
            version=data.get('version', '1.0'),
            start_scene_id=data.get('start_scene_id', ''),
            dialog_bg_color=data.get('dialog_bg_color', '#14142890'),
            dialog_border_color=data.get('dialog_border_color', '#646496'),
            dialog_text_color=data.get('dialog_text_color', '#FFFFFF'),
            game_id=data.get('game_id', ''),
            description=data.get('description', ''),
            forked_from=data.get('forked_from'),
            server_version=data.get('server_version', '')
        )
        if 'main_menu' in data:
            story.main_menu = MainMenuConfig.from_dict(data['main_menu'])
        if 'pause_menu' in data:
            story.pause_menu = PauseMenuConfig.from_dict(data['pause_menu'])
        for char_id, char_data in data.get('characters', {}).items():
            story.characters[char_id] = Character.from_dict(char_data)
        for scene_id, scene_data in data.get('scenes', {}).items():
            story.scenes[scene_id] = Scene.from_dict(scene_data)
        return story
    
    def save(self, filepath: str):
        """Сохранить историю в JSON файл с относительными путями."""
        import os
        base_dir = os.path.dirname(os.path.abspath(filepath))
        
        def to_relative(path: str) -> str:
            """Конвертировать абсолютный путь в относительный."""
            if not path:
                return path
            try:
                abs_path = os.path.abspath(path)
                rel_path = os.path.relpath(abs_path, base_dir)
                # Используем / для кроссплатформенности
                return rel_path.replace('\\', '/')
            except ValueError:
                # Разные диски на Windows - оставляем как есть
                return path
        
        def convert_paths_in_dict(data: dict) -> dict:
            """Рекурсивно конвертировать пути в словаре."""
            result = {}
            for key, value in data.items():
                if isinstance(value, str) and (
                    value.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp',
                                   '.mp3', '.wav', '.ogg', '.flac', '.JPEG', '.PNG', '.JPG'))
                    or '\\' in value or (len(value) > 2 and value[1] == ':')
                ):
                    result[key] = to_relative(value)
                elif isinstance(value, dict):
                    result[key] = convert_paths_in_dict(value)
                elif isinstance(value, list):
                    result[key] = [
                        convert_paths_in_dict(item) if isinstance(item, dict) else item
                        for item in value
                    ]
                else:
                    result[key] = value
            return result
        
        data = convert_paths_in_dict(self.to_dict())
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, filepath: str) -> 'Story':
        """Загрузить историю из JSON файла и преобразовать относительные пути в абсолютные."""
        import os
        base_dir = os.path.dirname(os.path.abspath(filepath))
        
        def to_absolute(path: str) -> str:
            """Конвертировать относительный путь в абсолютный."""
            if not path:
                return path
            # Уже абсолютный путь
            if os.path.isabs(path):
                return path
            # Относительный путь - делаем абсолютным
            abs_path = os.path.normpath(os.path.join(base_dir, path))
            return abs_path
        
        def convert_paths_in_dict(data: dict) -> dict:
            """Рекурсивно конвертировать пути в словаре."""
            result = {}
            for key, value in data.items():
                if isinstance(value, str) and (
                    value.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp',
                                   '.mp3', '.wav', '.ogg', '.flac', '.JPEG', '.PNG', '.JPG'))
                    or '/' in value or '\\' in value
                ):
                    result[key] = to_absolute(value)
                elif isinstance(value, dict):
                    result[key] = convert_paths_in_dict(value)
                elif isinstance(value, list):
                    result[key] = [
                        convert_paths_in_dict(item) if isinstance(item, dict) else item
                        for item in value
                    ]
                else:
                    result[key] = value
            return result
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        data = convert_paths_in_dict(data)
        return cls.from_dict(data)

