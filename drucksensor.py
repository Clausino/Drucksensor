"""GUI zum Importieren und Prüfen von Drucksensormessungen."""

from __future__ import annotations

import configparser
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    import ttkbootstrap as tb
    from ttkbootstrap.dialogs import Messagebox
except ModuleNotFoundError as exc:
    if exc.name != "ttkbootstrap":
        raise
    tb = None

    class Messagebox:
        @staticmethod
        def show_warning(message: str, title: str) -> None:
            messagebox.showwarning(title, message)

        @staticmethod
        def show_info(message: str, title: str) -> None:
            messagebox.showinfo(title, message)

        @staticmethod
        def yesno(message: str, title: str, buttons: list[str] | None = None) -> str:
            return "Ja" if messagebox.askyesno(title, message) else "Nein"

from drucksensor_core import CsvImportError, MeasurementFile, read_measurement_csv


APP_NAME = "Drucksensor"
APP_VERSION = "0.1"
GUI_THEME = "superhero"
GUI_THEME_LIGHT = "flatly"
HEADER_BG = "#12233a"
HEADER_BADGE_BG = "#2a6fdb"
HEADER_ICON_FG = "#dce6f2"
SETTINGS_PATH = Path(__file__).resolve().with_name("drucksensor_settings.ini")


def _button(parent: tk.Misc, **options):
    bootstyle = options.pop("bootstyle", None)
    if tb is not None:
        if bootstyle is not None:
            options["bootstyle"] = bootstyle
    else:
        options["style"] = {
            "primary": "Primary.TButton",
            "success": "Success.TButton",
        }.get(bootstyle, "TButton")
    return ttk.Button(parent, **options)


def _label(parent: tk.Misc, **options):
    bootstyle = options.pop("bootstyle", None)
    if tb is not None:
        if bootstyle is not None:
            options["bootstyle"] = bootstyle
    elif bootstyle == "secondary":
        options["style"] = "Muted.TLabel"
    return ttk.Label(parent, **options)


def _configure_fallback_theme(root: tk.Misc, dark_mode: bool) -> None:
    if tb is not None:
        tb.Style().theme_use(GUI_THEME if dark_mode else GUI_THEME_LIGHT)
        return

    style = ttk.Style(root)
    style.theme_use("clam")
    if dark_mode:
        background, foreground, muted = "#202d3d", "#dce6f2", "#9fb3cc"
        field_background, selection = "#172333", "#2a6fdb"
    else:
        background, foreground, muted = "#f5f7fa", "#263445", "#65758b"
        field_background, selection = "#ffffff", "#2a6fdb"
    style.configure("TFrame", background=background)
    style.configure("TLabel", background=background, foreground=foreground)
    style.configure("Muted.TLabel", background=background, foreground=muted)
    style.configure("TButton", padding=(9, 5))
    for name, color in (("Primary.TButton", selection), ("Success.TButton", "#198754")):
        style.configure(name, background=color, foreground="white", padding=(9, 5))
        style.map(name, background=[("active", color), ("pressed", color)])
    style.configure(
        "Treeview",
        background=field_background,
        fieldbackground=field_background,
        foreground=foreground,
        rowheight=25,
    )
    style.configure(
        "Treeview.Heading",
        background=background,
        foreground=foreground,
        font=("TkDefaultFont", 9, "bold"),
    )
    style.map("Treeview", background=[("selected", selection)])


def _default_import_dir() -> str:
    candidates = (
        Path.home() / "Schreibtisch" / "Austausch",
        Path.home() / "Desktop" / "Austausch",
        Path.home(),
    )
    return str(next((candidate for candidate in candidates if candidate.is_dir()), Path.home()))


def _load_import_dir() -> str:
    config = configparser.ConfigParser()
    if SETTINGS_PATH.exists():
        try:
            config.read(SETTINGS_PATH, encoding="utf-8")
        except (OSError, configparser.Error):
            pass
    saved = config.get("GUI", "import_dir", fallback="")
    return saved if saved and Path(saved).is_dir() else _default_import_dir()


def _save_import_dir(path: str) -> None:
    config = configparser.ConfigParser()
    if SETTINGS_PATH.exists():
        try:
            config.read(SETTINGS_PATH, encoding="utf-8")
        except (OSError, configparser.Error):
            pass
    if not config.has_section("GUI"):
        config.add_section("GUI")
    config.set("GUI", "import_dir", path)
    try:
        with SETTINGS_PATH.open("w", encoding="utf-8") as settings_file:
            config.write(settings_file)
    except OSError as exc:
        Messagebox.show_warning(
            f"Der Importordner konnte nicht gespeichert werden:\n{exc}",
            "Einstellungen",
        )


class DrucksensorApp:
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} - Messdaten")
        self.root.geometry("1040x680")
        self.root.minsize(800, 520)
        self.dark_mode = True
        self.import_dir = _load_import_dir()
        self.measurements: list[MeasurementFile] = []

        self._build_menubar()
        self._build_main_view()
        self._update_status()

    def _build_menubar(self) -> None:
        menu_colors = {
            "bg": HEADER_BG,
            "fg": "white",
            "activebackground": HEADER_BADGE_BG,
            "activeforeground": "white",
            "disabledforeground": HEADER_ICON_FG,
            "selectcolor": "white",
            "relief": "flat",
            "borderwidth": 0,
        }
        menubar = tk.Menu(self.root, **menu_colors)

        data_menu = tk.Menu(menubar, tearoff=False, **menu_colors)
        data_menu.add_command(label="Neu", command=self.clear_measurements)
        data_menu.add_separator()
        data_menu.add_command(label="Messdaten importieren ...", command=self.open_import_dialog)
        data_menu.add_command(label="Datensatz entfernen ...", command=self.remove_selected)
        menubar.add_cascade(label="Daten", menu=data_menu)

        for title, placeholder in (
            ("Modelle", "Auswertung wird später ergänzt"),
            ("Simulation", "Simulation wird später ergänzt"),
            ("Ausgabe", "Export wird später ergänzt"),
        ):
            submenu = tk.Menu(menubar, tearoff=False, **menu_colors)
            submenu.add_command(label=placeholder, state="disabled")
            menubar.add_cascade(label=title, menu=submenu)

        settings_menu = tk.Menu(menubar, tearoff=False, **menu_colors)
        settings_menu.add_command(
            label="Importordner ...", command=self.choose_import_dir
        )
        settings_menu.add_command(
            label="Darstellung wechseln", command=self.toggle_theme
        )
        menubar.add_cascade(label="Einstellungen", menu=settings_menu)

        help_menu = tk.Menu(menubar, tearoff=False, **menu_colors)
        help_menu.add_command(label="Über dieses Programm", command=self.show_about)
        menubar.add_cascade(label="Hilfe", menu=help_menu)
        self.root.config(menu=menubar)

    def _build_main_view(self) -> None:
        header = tk.Frame(self.root, bg=HEADER_BG, height=64)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="DRUCKSENSOR",
            bg=HEADER_BG,
            fg="white",
            font=("TkDefaultFont", 16, "bold"),
        ).pack(side="left", padx=(22, 6), pady=14)
        tk.Label(
            header,
            text="MESSDATEN",
            bg=HEADER_BADGE_BG,
            fg="white",
            font=("TkDefaultFont", 9, "bold"),
            padx=9,
            pady=4,
        ).pack(side="left", pady=18)
        self.theme_button = tk.Label(
            header,
            text="☀",
            bg=HEADER_BG,
            fg=HEADER_ICON_FG,
            font=("TkDefaultFont", 15),
            cursor="hand2",
        )
        self.theme_button.pack(side="right", padx=18)
        self.theme_button.bind("<Button-1>", lambda _event: self.toggle_theme())

        content = ttk.Frame(self.root, padding=18)
        content.pack(fill="both", expand=True)
        title_row = ttk.Frame(content)
        title_row.pack(fill="x", pady=(0, 14))
        ttk.Label(
            title_row,
            text="Messdaten",
            font=("TkDefaultFont", 18, "bold"),
        ).pack(side="left")
        _button(
            title_row,
            text="＋  Messdaten importieren ...",
            bootstyle="primary",
            command=self.open_import_dialog,
        ).pack(side="right")

        _label(
            content,
            text="CSV-Dateien mit Zeitstempel, Druck [bar] und Temperatur [°C]",
            bootstyle="secondary",
        ).pack(anchor="w", pady=(0, 10))

        table_frame = ttk.Frame(content)
        table_frame.pack(fill="both", expand=True)
        columns = ("file", "records", "start", "end", "pressure", "temperature")
        self.file_table = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="browse"
        )
        headings = {
            "file": ("Datei", 230),
            "records": ("Messpunkte", 90),
            "start": ("Beginn", 145),
            "end": ("Ende", 145),
            "pressure": ("Druck [bar]", 135),
            "temperature": ("Temperatur [°C]", 155),
        }
        for key, (label, width) in headings.items():
            self.file_table.heading(key, text=label)
            self.file_table.column(key, width=width, minwidth=70, anchor="w")
        table_scroll = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.file_table.yview
        )
        self.file_table.configure(yscrollcommand=table_scroll.set)
        self.file_table.pack(side="left", fill="both", expand=True)
        table_scroll.pack(side="right", fill="y")
        self.file_table.bind("<Double-1>", lambda _event: self.show_selected_preview())
        self.file_table.bind("<<TreeviewSelect>>", lambda _event: self._update_status())

        footer = ttk.Frame(content)
        footer.pack(fill="x", pady=(12, 0))
        self.status_var = tk.StringVar()
        _label(footer, textvariable=self.status_var, bootstyle="secondary").pack(
            side="left"
        )
        ttk.Button(
            footer,
            text="Vorschau öffnen",
            command=self.show_selected_preview,
        ).pack(side="right")

    def _update_status(self) -> None:
        count = len(self.measurements)
        points = sum(len(item.points) for item in self.measurements)
        if count:
            self.status_var.set(
                f"{count} Datei(en) · {points:,} Messpunkte".replace(",", ".")
            )
        else:
            self.status_var.set("Noch keine Messdaten importiert.")

    def _refresh_file_table(self) -> None:
        self.file_table.delete(*self.file_table.get_children())
        for index, item in enumerate(self.measurements):
            pressure_min, pressure_max = item.pressure_range
            temperature_min, temperature_max = item.temperature_range
            self.file_table.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    item.path.name,
                    f"{len(item.points):,}".replace(",", "."),
                    item.start_time.strftime("%d.%m.%Y %H:%M:%S"),
                    item.end_time.strftime("%d.%m.%Y %H:%M:%S"),
                    f"{pressure_min:.4f} – {pressure_max:.4f}",
                    f"{temperature_min:.2f} – {temperature_max:.2f}",
                ),
            )
        self._update_status()

    def open_import_dialog(self) -> None:
        ImportDialog(self)

    def _accept_measurements(self, incoming: list[MeasurementFile]) -> None:
        existing_paths = {item.path for item in self.measurements}
        added: list[MeasurementFile] = []
        for item in incoming:
            if item.path not in existing_paths:
                existing_paths.add(item.path)
                added.append(item)
        skipped = len(incoming) - len(added)
        self.measurements.extend(added)
        self._refresh_file_table()
        if added and skipped:
            Messagebox.show_info(
                f"{len(added)} Datei(en) importiert. {skipped} bereits geladene "
                "Datei(en) wurden übersprungen.",
                "Import abgeschlossen",
            )
        elif not added and skipped:
            Messagebox.show_info(
                "Alle ausgewählten Dateien sind bereits geladen.",
                "Keine neuen Daten",
            )

    def show_selected_preview(self) -> None:
        selected = self.file_table.selection()
        if not selected:
            Messagebox.show_info(
                "Bitte wählen Sie zuerst einen Datensatz aus.",
                "Keine Auswahl",
            )
            return
        index = int(selected[0])
        self._show_measurement_preview(self.measurements[index])

    def _show_measurement_preview(self, item: MeasurementFile) -> None:
        window = tk.Toplevel(self.root)
        window.title(f"Vorschau - {item.path.name}")
        window.transient(self.root)
        window.geometry("720x440")

        pressure_min, pressure_max = item.pressure_range
        temperature_min, temperature_max = item.temperature_range
        details = (
            f"{item.path.name}  ·  {len(item.points):,} Messpunkte\n"
            f"Drucksensor: {item.pressure_sensor}  ·  "
            f"Temperatursensor: {item.temperature_sensor}\n"
            f"Druck: {pressure_min:.4f}–{pressure_max:.4f} bar  ·  "
            f"Temperatur: {temperature_min:.2f}–{temperature_max:.2f} °C"
        ).replace(",", ".")
        ttk.Label(
            window, text=details, padding=12, justify="left"
        ).pack(fill="x")

        frame = ttk.Frame(window, padding=(12, 0, 12, 12))
        frame.pack(fill="both", expand=True)
        columns = ("timestamp", "pressure", "temperature")
        preview = ttk.Treeview(frame, columns=columns, show="headings", height=15)
        preview.heading("timestamp", text="Zeitpunkt")
        preview.heading("pressure", text=f"{item.pressure_sensor} [bar]")
        preview.heading("temperature", text=f"{item.temperature_sensor} [°C]")
        preview.column("timestamp", width=240)
        preview.column("pressure", width=170, anchor="e")
        preview.column("temperature", width=170, anchor="e")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=preview.yview)
        preview.configure(yscrollcommand=scrollbar.set)
        preview.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for point in item.points[:500]:
            preview.insert(
                "",
                "end",
                values=(
                    point.timestamp.strftime("%d.%m.%Y %H:%M:%S"),
                    f"{point.pressure_bar:.4f}",
                    f"{point.temperature_c:.2f}",
                ),
            )
        if len(item.points) > 500:
            _label(
                window,
                text="Es werden die ersten 500 Messpunkte angezeigt.",
                padding=(12, 0, 12, 10),
                bootstyle="secondary",
            ).pack(anchor="w")

    def remove_selected(self) -> None:
        selected = self.file_table.selection()
        if not selected:
            Messagebox.show_info("Bitte wählen Sie einen Datensatz aus.", "Keine Auswahl")
            return
        del self.measurements[int(selected[0])]
        self._refresh_file_table()

    def clear_measurements(self) -> None:
        if not self.measurements:
            return
        answer = Messagebox.yesno(
            "Alle importierten Messdaten wirklich entfernen?",
            "Messdaten löschen",
            buttons=["Nein", "Ja"],
        )
        if answer == "Ja":
            self.measurements.clear()
            self._refresh_file_table()

    def choose_import_dir(self) -> None:
        chosen = filedialog.askdirectory(
            title="Standard-Importordner wählen",
            initialdir=self.import_dir,
            parent=self.root,
        )
        if chosen:
            self.import_dir = chosen
            _save_import_dir(chosen)

    def toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        _configure_fallback_theme(self.root, self.dark_mode)
        self.theme_button.configure(text="☀" if self.dark_mode else "☽")

    def show_about(self) -> None:
        Messagebox.show_info(
            f"{APP_NAME}\n\nImport und Prüfung von Drucksensormessdaten.\n"
            f"Version {APP_VERSION}",
            "Über dieses Programm",
        )


class ImportDialog:
    def __init__(self, app: DrucksensorApp) -> None:
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("Messdaten importieren")
        self.window.transient(app.root)
        self.window.geometry("940x590")
        self.window.minsize(760, 460)
        self.window.grab_set()
        self.files: list[MeasurementFile] = []
        self._build()

    def _build(self) -> None:
        content = ttk.Frame(self.window, padding=16)
        content.pack(fill="both", expand=True)

        header = ttk.Frame(content)
        header.pack(fill="x")
        ttk.Label(
            header, text="Messdaten importieren", font=("TkDefaultFont", 17, "bold")
        ).pack(side="left")
        _button(
            header,
            text="Dateien auswählen ...",
            bootstyle="primary",
            command=self.choose_files,
        ).pack(side="right")

        _label(
            content,
            text=(
                "CSV-Dateien mit Datum, Uhrzeit, Druck [bar] und Temperatur [°C]. "
                "Mehrere Dateien können gemeinsam ausgewählt werden."
            ),
            bootstyle="secondary",
            wraplength=880,
        ).pack(anchor="w", pady=(8, 14))

        table_frame = ttk.Frame(content)
        table_frame.pack(fill="both", expand=True)
        columns = ("file", "records", "pressure", "temperature", "range")
        self.file_table = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="browse"
        )
        headings = (
            ("file", "Datei", 240),
            ("records", "Messpunkte", 90),
            ("pressure", "Druck [bar]", 140),
            ("temperature", "Temperatur [°C]", 150),
            ("range", "Messzeitraum", 260),
        )
        for key, label, width in headings:
            self.file_table.heading(key, text=label)
            self.file_table.column(key, width=width, minwidth=70, anchor="w")
        scrollbar = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.file_table.yview
        )
        self.file_table.configure(yscrollcommand=scrollbar.set)
        self.file_table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.file_table.bind("<<TreeviewSelect>>", lambda _event: self._show_preview())
        self.file_table.bind("<Double-1>", lambda _event: self._show_preview())

        self.preview_label = _label(
            content, text="Datei auswählen, um eine Messwertvorschau anzuzeigen.",
            bootstyle="secondary",
        )
        self.preview_label.pack(anchor="w", pady=(10, 4))
        preview_frame = ttk.Frame(content)
        preview_frame.pack(fill="x")
        self.preview_table = ttk.Treeview(
            preview_frame,
            columns=("timestamp", "pressure", "temperature"),
            show="headings",
            height=5,
        )
        for column, title, width in (
            ("timestamp", "Zeitpunkt", 240),
            ("pressure", "Druck [bar]", 140),
            ("temperature", "Temperatur [°C]", 160),
        ):
            self.preview_table.heading(column, text=title)
            self.preview_table.column(column, width=width, anchor="w")
        self.preview_table.pack(fill="x")

        controls = ttk.Frame(content)
        controls.pack(fill="x", pady=(14, 0))
        ttk.Button(
            controls, text="Auswahl entfernen", command=self.remove_selected
        ).pack(side="left")
        ttk.Button(
            controls, text="Abbrechen", command=self.window.destroy
        ).pack(side="right")
        _button(
            controls,
            text="Importieren",
            bootstyle="success",
            command=self.import_files,
        ).pack(side="right", padx=(0, 8))

    def choose_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Drucksensordateien auswählen",
            initialdir=self.app.import_dir,
            filetypes=(("CSV-Dateien", "*.csv"), ("Alle Dateien", "*.*")),
            parent=self.window,
        )
        if not paths:
            return
        errors: list[str] = []
        known_paths = {item.path for item in self.files}
        for path_string in paths:
            path = Path(path_string)
            try:
                measurement = read_measurement_csv(path)
            except CsvImportError as exc:
                errors.append(f"{path.name}: {exc}")
                continue
            if measurement.path in known_paths:
                continue
            known_paths.add(measurement.path)
            self.files.append(measurement)
        self.app.import_dir = str(Path(paths[0]).parent)
        _save_import_dir(self.app.import_dir)
        self._refresh()
        if errors:
            Messagebox.show_warning(
                "Folgende Datei(en) konnten nicht importiert werden:\n\n"
                + "\n\n".join(errors),
                "Importfehler",
            )

    def _refresh(self) -> None:
        self.file_table.delete(*self.file_table.get_children())
        for index, item in enumerate(self.files):
            pressure_min, pressure_max = item.pressure_range
            temperature_min, temperature_max = item.temperature_range
            self.file_table.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    item.path.name,
                    f"{len(item.points):,}".replace(",", "."),
                    f"{pressure_min:.4f}–{pressure_max:.4f}",
                    f"{temperature_min:.2f}–{temperature_max:.2f}",
                    f"{item.start_time:%d.%m.%Y %H:%M:%S} – "
                    f"{item.end_time:%d.%m.%Y %H:%M:%S}",
                ),
            )
        children = self.file_table.get_children()
        if children:
            self.file_table.selection_set(children[0])
            self._show_preview()
        else:
            self._clear_preview()

    def _clear_preview(self) -> None:
        self.preview_table.delete(*self.preview_table.get_children())
        self.preview_label.configure(
            text="Datei auswählen, um eine Messwertvorschau anzuzeigen."
        )

    def _show_preview(self) -> None:
        selection = self.file_table.selection()
        if not selection:
            self._clear_preview()
            return
        item = self.files[int(selection[0])]
        self.preview_table.delete(*self.preview_table.get_children())
        self.preview_label.configure(
            text=(
                f"Vorschau: {item.path.name} · "
                f"{item.pressure_sensor} / {item.temperature_sensor}"
            )
        )
        for point in item.points[:5]:
            self.preview_table.insert(
                "",
                "end",
                values=(
                    point.timestamp.strftime("%d.%m.%Y %H:%M:%S"),
                    f"{point.pressure_bar:.4f}",
                    f"{point.temperature_c:.2f}",
                ),
            )

    def remove_selected(self) -> None:
        selection = self.file_table.selection()
        if not selection:
            Messagebox.show_info("Bitte wählen Sie eine Datei aus.", "Keine Auswahl")
            return
        del self.files[int(selection[0])]
        self._refresh()

    def import_files(self) -> None:
        if not self.files:
            Messagebox.show_warning(
                "Bitte wählen Sie zuerst mindestens eine gültige CSV-Datei aus.",
                "Keine Dateien ausgewählt",
            )
            return
        self.app._accept_measurements(self.files)
        self.window.destroy()


def main() -> None:
    if tb is None:
        root = tk.Tk()
        _configure_fallback_theme(root, dark_mode=True)
    else:
        root = tb.Window(themename=GUI_THEME)
    DrucksensorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
