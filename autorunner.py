from json import dump, load
from os import getenv, makedirs, path, remove
from threading import Thread, Event
from time import time

from pynput.keyboard import GlobalHotKeys, Controller as KeyboardController, Key
from tkinter import Event as TkEvent

from customtkinter import (
    CTk, CTkButton, CTkCheckBox, CTkFrame, CTkFont, CTkLabel,
    BooleanVar, set_appearance_mode, set_default_color_theme
)


class Settings:
    app_title = "AutoRunner"
    app_version = "1.0"
    settings_folder_name = "AutoRunner"
    init_size = "490x170"
    scaled_size = "490x200"

    def __init__(self):
        self.shift_key = "f7"
        self.start_key = "f8"
        self.quit_key = "f9"
        self.shifting = True
        self.save_settings = False
        self.winfo_x = None
        self.winfo_y = None
        self.load()

    def _get_config_path(self, create_if_not_exists=False) -> str:
        appdata_path = getenv("APPDATA")
        if appdata_path:
            folder = path.join(appdata_path, self.settings_folder_name)
            if create_if_not_exists:
                makedirs(folder, exist_ok=True)
            filepath = path.join(folder, "settings.json")
        else:
            folder = path.dirname(path.abspath(__file__))
            filepath = path.join(folder, "settings.json")
        return filepath

    def save(
        self, shift_key: str, start_key: str, quit_key: str, shifting: bool,
        save_settings: bool, winfo_x: int, winfo_y: int
    ) -> None:
        data = {
            "shift_key": shift_key,
            "start_key": start_key,
            "quit_key": quit_key,
            "shifting": shifting,
            "save_settings": save_settings,
            "winfo_x": winfo_x,
            "winfo_y": winfo_y
        }
        with open(self._get_config_path(create_if_not_exists=True), "w", encoding="utf-8") as f:
            dump(data, f, indent=2)

    def load(self) -> None:
        settings_file_path = self._get_config_path()
        if not path.exists(settings_file_path):
            return
        with open(settings_file_path, "r", encoding="utf-8") as f:
            data = load(f)
        self.shift_key = data.get("shift_key", self.shift_key)
        self.start_key = data.get("start_key", self.start_key)
        self.quit_key = data.get("quit_key", self.quit_key)
        self.shifting = data.get("shifting", self.shifting)
        self.save_settings = data.get("save_settings", self.save_settings)
        self.winfo_x = data.get("winfo_x", self.winfo_x)
        self.winfo_y = data.get("winfo_y", self.winfo_y)

    def reset_settings(self) -> None:
        settings_file_path = self._get_config_path()
        if path.exists(settings_file_path):
            remove(settings_file_path)


class AutoRunner:
    def __init__(self, master):
        self.settings = Settings()

        set_appearance_mode("dark")
        set_default_color_theme("dark-blue")

        self.init_size = self.settings.init_size
        self.scaled_size = self.settings.scaled_size
        self.running = False
        self.shifting = BooleanVar(value=self.settings.shifting)

        self.master = master
        self.master.title(self.settings.app_title)
        self.master.resizable(False, False)
        self.master.geometry(self.init_size)
        self.master.protocol("WM_DELETE_WINDOW", self.on_quit)

        self.timer_start = None
        self.update_timer_running = False

        self.always_on_top_var = BooleanVar(value=True)
        self.master.wm_attributes("-topmost", True)

        self.save_settings_var = BooleanVar(value=self.settings.save_settings)

        self.shift_key = self.settings.shift_key
        self.start_key = self.settings.start_key
        self.quit_key = self.settings.quit_key
        self.listening_for = None
        self.hotkey_prompt = None

        self.master.columnconfigure(0, weight=1, minsize=270)
        self.master.columnconfigure(1, weight=1, minsize=250)
        self.master.rowconfigure(0, weight=1)

        # Left frame (settings)
        left_frame = CTkFrame(master)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(5, 0), pady=(0, 5))
        left_frame.columnconfigure(1, weight=1)

        left_frame.columnconfigure(0, weight=0)  # labels
        left_frame.columnconfigure(1, weight=0)  # hotkeys
        left_frame.columnconfigure(2, weight=0)  # buttons

        # Start/Stop hotkey
        self.start_key_label = CTkLabel(left_frame, text="Start/Stop hotkey:")
        self.start_key_label.grid(row=0, column=0, sticky="w")
        self.start_key_display = CTkLabel(
            left_frame, text=self.start_key.upper(), fg_color="green", corner_radius=5,
            font=CTkFont(size=14, weight="bold"), width=50, height=25, anchor="center"
        )
        self.start_key_display.grid(row=0, column=1, sticky="w", padx=(1, 0))
        self.set_start_key_btn = CTkButton(
            left_frame, text="Set hotkey", command=self.listen_for_start_key, width=100, height=25)
        self.set_start_key_btn.grid(row=0, column=2, sticky="w", pady=2)

        # Shift hotkey
        self.shift_key_label = CTkLabel(left_frame, text="Shift hotkey:")
        self.shift_key_label.grid(row=1, column=0, sticky="w")
        self.shift_key_display = CTkLabel(
            left_frame, text=self.shift_key.upper(), fg_color="green", corner_radius=5,
            font=CTkFont(size=14, weight="bold"), width=50, height=25, anchor="center"
        )
        self.shift_key_display.grid(row=1, column=1, sticky="w", padx=(1, 0))
        self.set_shift_key_btn = CTkButton(
            left_frame, text="Set hotkey", command=self.listen_for_shift_key, width=100, height=25)
        self.set_shift_key_btn.grid(row=1, column=2, sticky="w", pady=2)

        # Quit hotkey
        self.quit_key_label = CTkLabel(left_frame, text="Exit hotkey:")
        self.quit_key_label.grid(row=2, column=0, sticky="w")
        self.quit_key_display = CTkLabel(
            left_frame, text=self.quit_key.upper(), fg_color="green", corner_radius=5,
            font=CTkFont(size=14, weight="bold"), width=50, height=25, anchor="center"
        )
        self.quit_key_display.grid(row=2, column=1, sticky="w", padx=(1, 0))
        self.set_quit_key_btn = CTkButton(
            left_frame, text="Set hotkey", command=self.listen_for_quit_key, width=100, height=25)
        self.set_quit_key_btn.grid(row=2, column=2, sticky="w", pady=2)

        # Use shift checkbox
        self.use_shift_cb = CTkCheckBox(
            left_frame, text="Use shift", variable=self.shifting,
            command=self.toggle_shift, state="disabled"
        )
        self.use_shift_cb.grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 0))

        # Always on top checkbox
        self.always_on_top_cb = CTkCheckBox(
            left_frame, text="Always on top", variable=self.always_on_top_var,
            command=self.toggle_always_on_top
        )
        self.always_on_top_cb.grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 0))

        # Save settings checkbox
        self.save_settings_cb = CTkCheckBox(
            left_frame, text="Save settings", variable=self.save_settings_var)
        self.save_settings_cb.grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 0))

        # Right frame (status/stats)
        right_frame = CTkFrame(master)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=(0, 5))
        right_frame.columnconfigure(0, weight=1)

        self.status_label = CTkLabel(
            right_frame, text="Status: Stopped", text_color="#b80202",
            font=CTkFont(size=16, weight="bold")
        )
        self.status_label.grid(row=0, column=0, sticky="w", pady=(0, 10))

        self.timer_label = CTkLabel(right_frame, text="Time elapsed: 0 sec", font=CTkFont(size=14))
        self.timer_label.grid(row=2, column=0, sticky="w", pady=(5, 0))

        # Keyboard controller for holding keys
        self.keyboard_controller = KeyboardController()

        # Event to control thread stop
        self.stop_event = Event()

        # Start GlobalHotKeys listener (threaded)
        self.global_hotkeys = None
        self.hotkeys_thread = None
        self.start_global_hotkeys()

        # Update window position
        self.center_window_or_load_position()

    def center_window_or_load_position(self) -> None:
        self.master.update_idletasks()
        size: list[str] = self.init_size.split("x")
        width: int = int(size[0])
        height: int = int(size[1])
        screen_width: int = self.master.winfo_screenwidth()
        screen_height: int = self.master.winfo_screenheight()

        if self.settings.winfo_x is not None and self.settings.winfo_y is not None:
            self.settings.winfo_x = max(0, self.settings.winfo_x)
            self.settings.winfo_y = max(0, self.settings.winfo_y)
            if self.settings.winfo_y + height > screen_height:
                self.settings.winfo_y = screen_height - height - 40
            x: int = self.settings.winfo_x
            y: int = self.settings.winfo_y
        else:
            x: int = (screen_width // 2) - (width // 2)
            y: int = (screen_height // 2) - (height // 2)
        self.master.geometry(f"{width}x{height}+{x}+{y}")

    def start_global_hotkeys(self) -> None:
        if self.global_hotkeys:
            self.global_hotkeys.stop()
        if self.hotkeys_thread and self.hotkeys_thread.is_alive():
            self.stop_event.set()
            self.hotkeys_thread.join()
            self.stop_event.clear()

        # Create the hotkey to callback dictionary
        hotkeys = {
            f"<{self.start_key}>": self.on_start_stop_hotkey,
            f"<{self.shift_key}>": self.on_shift_hotkey,
            f"<{self.quit_key}>": self.on_quit_hotkey
        }

        self.global_hotkeys = GlobalHotKeys(hotkeys)
        self.hotkeys_thread = Thread(target=self.global_hotkeys.start, daemon=True)
        self.hotkeys_thread.start()

    def on_start_stop_hotkey(self) -> None:
        self.master.after(0, self.toggle_running)

    def on_shift_hotkey(self) -> None:
        self.master.after(0, self.toggle_shift)

    def on_quit_hotkey(self) -> None:
        self.master.after(0, self.on_quit)

    def show_key_prompt(self, text: str) -> None:
        frame = self.set_start_key_btn.master
        if self.hotkey_prompt is None:
            self.hotkey_prompt = CTkLabel(frame, text=text, text_color="#ffaa00")
        self.hotkey_prompt.grid(row=3, column=0, columnspan=3, sticky="w", pady=(2, 5))
        self.hotkey_prompt.update()
        self.master.geometry(self.scaled_size)

    def hide_key_prompt(self) -> None:
        if self.hotkey_prompt is not None:
            self.hotkey_prompt.grid_remove()
        self.master.geometry(self.init_size)

    def listen_for_start_key(self) -> None:
        if not self.running and self.listening_for is None:
            self.listening_for = "start"
            self.show_key_prompt("Press any key to set Start hotkey...")
            self.master.bind_all("<Key>", self.on_key_press)

    def listen_for_shift_key(self) -> None:
        if not self.running and self.listening_for is None:
            self.listening_for = "shift"
            self.show_key_prompt("Press any key to set Shift hotkey...")
            self.master.bind_all("<Key>", self.on_key_press)

    def listen_for_quit_key(self) -> None:
        if not self.running and self.listening_for is None:
            self.listening_for = "quit"
            self.show_key_prompt("Press any key to set Exit hotkey...")
            self.master.bind_all("<Key>", self.on_key_press)

    def on_key_press(self, event: TkEvent) -> None:
        key = event.keysym.lower()
        if self.listening_for == "start":
            if key == self.quit_key:
                return
            self.master.unbind_all("<Key>")
            self.start_key = key
            self.start_key_display.configure(text=self.start_key.upper())
            self.start_global_hotkeys()
        elif self.listening_for == "shift":
            if key == self.shift_key:
                return
            self.master.unbind_all("<Key>")
            self.shift_key = key
            self.shift_key_display.configure(text=self.shift_key.upper())
            self.start_global_hotkeys()
        elif self.listening_for == "quit":
            if key == self.start_key:
                return
            self.master.unbind_all("<Key>")
            self.quit_key = key
            self.quit_key_display.configure(text=self.quit_key.upper())
            self.start_global_hotkeys()

        self.hide_key_prompt()
        self.listening_for = None

    def toggle_shift(self) -> None:
        if self.running and not self.shifting.get():
            self.keyboard_controller.press(Key.shift)
        elif self.shifting.get():
            self.keyboard_controller.release(Key.shift)
        self.shifting.set(False if self.shifting.get() else True)

    def toggle_always_on_top(self) -> None:
        self.master.wm_attributes("-topmost", self.always_on_top_var.get())

    def reset_entry_focus(self) -> None:
        self.status_label.focus_set()

    def toggle_running(self) -> None:
        if not self.running:
            self.stop_event.clear()
            self.status_label.configure(text="Status: Running", text_color="green")
            self.timer_start = time()
            self.update_timer_running = True
            self.update_timer()
            self.keyboard_controller.press("w")
            if self.shifting.get():
                self.keyboard_controller.press(Key.shift)
        else:
            self.stop_event.set()
            self.status_label.configure(text="Status: Stopped", text_color="#b80202")
            self.update_timer_running = False
            self.timer_label.configure(text="Time elapsed: 0 sec")
            self.keyboard_controller.release("w")
            self.keyboard_controller.release(Key.shift)
        self.running = not self.running
        self.reset_entry_focus()

    def update_timer(self) -> None:
        if self.update_timer_running:
            elapsed = int(time() - self.timer_start)
            self.timer_label.configure(text=f"Time elapsed: {elapsed} sec")
            self.master.after(1000, self.update_timer)

    def on_quit(self) -> None:
        if self.running:
            self.keyboard_controller.release("w")
            self.keyboard_controller.release(Key.shift)
            self.toggle_running()

        if self.global_hotkeys:
            self.global_hotkeys.stop()

        if self.save_settings_var.get():
            self.settings.save(
                self.shift_key, self.start_key, self.quit_key, self.shifting.get(),
                self.save_settings_var.get(), self.master.winfo_x(), self.master.winfo_y()
            )
        else:
            self.settings.reset_settings()

        self.master.quit()


if __name__ == "__main__":
    root = CTk()
    app = AutoRunner(root)
    root.mainloop()
