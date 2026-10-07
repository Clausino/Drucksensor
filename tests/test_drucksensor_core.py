import tempfile
import unittest
from pathlib import Path

from drucksensor_core import CsvImportError, read_measurement_csv


class ReadMeasurementCsvTests(unittest.TestCase):
    def test_reads_sensor_export_with_metadata_and_trailing_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "messung.csv"
            path.write_text(
                "sep=,\n"
                ",,LP 01,LA 02,\n"
                ",,890564,890564,\n"
                ",,490893,490893,\n"
                "Date,Time,bar,°C,\n"
                "06.10.2026,10:14:35,0.9577,26.52,\n"
                "06.10.2026,10:14:36,0.9579,26.53,\n",
                encoding="utf-8",
            )
            measurement = read_measurement_csv(path)

        self.assertEqual(len(measurement.points), 2)
        self.assertEqual(measurement.pressure_sensor, "LP 01")
        self.assertEqual(measurement.temperature_sensor, "LA 02")
        self.assertEqual(measurement.points[0].pressure_bar, 0.9577)
        self.assertEqual(measurement.points[0].temperature_c, 26.52)
        self.assertEqual(measurement.points[0].timestamp.strftime("%d.%m.%Y %H:%M:%S"),
                         "06.10.2026 10:14:35")

    def test_reads_decimal_comma_without_sensor_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "messung.csv"
            path.write_text(
                "Date;Time;bar;°C\n07.10.2026;09:10:11;1,25;22,5\n",
                encoding="utf-8",
            )
            measurement = read_measurement_csv(path)

        self.assertEqual(len(measurement.points), 1)
        self.assertEqual(measurement.points[0].pressure_bar, 1.25)
        self.assertEqual(measurement.points[0].temperature_c, 22.5)

    def test_reports_invalid_measurement_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ungueltig.csv"
            path.write_text(
                "Date,Time,bar,°C\n07.10.2026,09:10:11,n/a,22.5\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(CsvImportError, "Zeile 2"):
                read_measurement_csv(path)

if __name__ == "__main__":
    unittest.main()
