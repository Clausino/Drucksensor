"""Einlesen und Zusammenfassen von Drucksensor-CSV-Dateien."""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class MeasurementPoint:
    timestamp: datetime
    pressure_bar: float
    temperature_c: float


@dataclass(frozen=True)
class MeasurementFile:
    path: Path
    pressure_sensor: str
    temperature_sensor: str
    points: tuple[MeasurementPoint, ...]

    @property
    def start_time(self) -> datetime:
        return self.points[0].timestamp

    @property
    def end_time(self) -> datetime:
        return self.points[-1].timestamp

    @property
    def pressure_range(self) -> tuple[float, float]:
        values = [point.pressure_bar for point in self.points]
        return min(values), max(values)

    @property
    def temperature_range(self) -> tuple[float, float]:
        values = [point.temperature_c for point in self.points]
        return min(values), max(values)


class CsvImportError(ValueError):
    """Fehler mit verständlicher Ursache beim Einlesen einer Messdatei."""


def _normalise_cell(value: str) -> str:
    return value.strip().lstrip("\ufeff").casefold()


def _parse_number(value: str, *, line_number: int, column_name: str) -> float:
    cleaned = value.strip().replace(",", ".")
    try:
        number = float(cleaned)
    except ValueError as exc:
        raise CsvImportError(
            f"Zeile {line_number}: ungültiger Wert in Spalte "
            f"„{column_name}“: {value!r}."
        ) from exc
    if not math.isfinite(number):
        raise CsvImportError(
            f"Zeile {line_number}: der Wert in Spalte "
            f"„{column_name}“ ist nicht endlich."
        )
    return number


def _parse_timestamp(date_value: str, time_value: str, *, line_number: int) -> datetime:
    combined = f"{date_value.strip()} {time_value.strip()}"
    for date_format in ("%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(combined, date_format)
        except ValueError:
            continue
    raise CsvImportError(
        f"Zeile {line_number}: Datum/Uhrzeit {combined!r} konnte nicht gelesen werden."
    )


def _sensor_name(rows: list[list[str]], header_index: int, column_index: int, fallback: str) -> str:
    for row in reversed(rows[:header_index]):
        if column_index >= len(row):
            continue
        value = row[column_index].strip()
        if value and not value.isdecimal():
            return value
    return fallback


def read_measurement_csv(path: str | Path) -> MeasurementFile:
    """Liest eine Messreihe mit Datum, Uhrzeit, Druck [bar] und Temperatur [°C]."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise CsvImportError(f"Datei konnte nicht gelesen werden: {exc}") from exc

    lines = text.splitlines()
    if not lines:
        raise CsvImportError("Die Datei ist leer.")

    delimiter = ","
    first_line = lines[0].strip()
    if first_line.casefold().startswith("sep="):
        declared_delimiter = first_line[4:]
        if len(declared_delimiter) != 1:
            raise CsvImportError("Die Trennzeichen-Angabe in der ersten Zeile ist ungültig.")
        delimiter = declared_delimiter
    else:
        try:
            delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",;\t").delimiter
        except csv.Error:
            pass

    rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))
    header_index = -1
    date_index = time_index = pressure_index = temperature_index = -1
    for index, row in enumerate(rows[:20]):
        normalised = [_normalise_cell(cell) for cell in row]
        if "date" not in normalised or "time" not in normalised:
            continue
        pressure_columns = [i for i, value in enumerate(normalised) if value == "bar"]
        temperature_columns = [
            i for i, value in enumerate(normalised)
            if value in {"°c", "c", "degc", "celsius"}
        ]
        if len(pressure_columns) != 1 or len(temperature_columns) != 1:
            continue
        header_index = index
        date_index = normalised.index("date")
        time_index = normalised.index("time")
        pressure_index = pressure_columns[0]
        temperature_index = temperature_columns[0]
        break

    if header_index < 0:
        raise CsvImportError(
            "Keine passende Kopfzeile gefunden. Erwartet werden die Spalten "
        "Date, Time, bar und °C."
        )

    points: list[MeasurementPoint] = []
    expected_indices = (date_index, time_index, pressure_index, temperature_index)
    for row_index, row in enumerate(rows[header_index + 1:], start=header_index + 2):
        if not row or not any(cell.strip() for cell in row):
            continue
        if all(index < len(row) for index in expected_indices):
            required_values = [row[index].strip() for index in expected_indices]
        else:
            raise CsvImportError(f"Zeile {row_index}: es fehlen erwartete Spaltenwerte.")
        if not any(required_values):
            continue
        if not all(required_values):
            raise CsvImportError(f"Zeile {row_index}: unvollständiger Messdatensatz.")
        timestamp = _parse_timestamp(
            required_values[0], required_values[1], line_number=row_index
        )
        pressure = _parse_number(
            required_values[2], line_number=row_index, column_name="bar"
        )
        temperature = _parse_number(
            required_values[3], line_number=row_index, column_name="°C"
        )
        points.append(MeasurementPoint(timestamp, pressure, temperature))

    if not points:
        raise CsvImportError("Die Datei enthält keine Messwerte.")

    return MeasurementFile(
        path=file_path.resolve(),
        pressure_sensor=_sensor_name(rows, header_index, pressure_index, "Drucksensor"),
        temperature_sensor=_sensor_name(rows, header_index, temperature_index, "Temperatursensor"),
        points=tuple(points),
    )
