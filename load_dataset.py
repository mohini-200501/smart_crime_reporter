import argparse
import csv
import os
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATE_FORMAT = "%d-%m-%Y %H:%M"
OCCURRENCE_DATE_FORMAT = "%m-%d-%Y %H:%M"
REQUIRED_COLUMNS = {
    "Report Number",
    "Date Reported",
    "Date of Occurrence",
    "Time of Occurrence",
    "City",
    "Crime Code",
    "Crime Description",
    "Victim Age",
    "Victim Gender",
    "Weapon Used",
    "Crime Domain",
    "Police Deployed",
    "Case Closed",
    "Date Case Closed",
}


def parse_integer(value, column, row_number, required=False):
    value = (value or "").strip()
    if not value:
        if required:
            raise ValueError(f"CSV row {row_number}: {column} is required")
        return None
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(
            f"CSV row {row_number}: invalid integer in {column}: {value!r}"
        ) from error


def parse_datetime(value, column, row_number, date_format, required=False):
    value = (value or "").strip()
    if not value:
        if required:
            raise ValueError(f"CSV row {row_number}: {column} is required")
        return None
    try:
        return datetime.strptime(value, date_format)
    except ValueError as error:
        raise ValueError(
            f"CSV row {row_number}: invalid date in {column}: {value!r}"
        ) from error


def parse_case_closed(value, row_number):
    value = (value or "").strip().lower()
    if not value:
        return None
    if value == "yes":
        return True
    if value == "no":
        return False
    raise ValueError(
        f"CSV row {row_number}: Case Closed must be Yes or No, got {value!r}"
    )


def read_records(csv_path):
    records = []
    seen_report_numbers = set()

    with csv_path.open(encoding="utf-8-sig", newline="") as dataset:
        reader = csv.DictReader(dataset)
        if reader.fieldnames is None:
            raise ValueError(f"{csv_path} is empty or has no header row")

        missing_columns = REQUIRED_COLUMNS.difference(reader.fieldnames)
        if missing_columns:
            columns = ", ".join(sorted(missing_columns))
            raise ValueError(f"{csv_path} is missing required columns: {columns}")

        for row in reader:
            row_number = reader.line_num
            if None in row:
                raise ValueError(f"CSV row {row_number}: too many columns")

            report_number = parse_integer(
                row["Report Number"], "Report Number", row_number, required=True
            )
            if report_number in seen_report_numbers:
                raise ValueError(
                    f"CSV row {row_number}: duplicate Report Number {report_number}"
                )
            seen_report_numbers.add(report_number)

            city = (row["City"] or "").strip()
            crime_description = (row["Crime Description"] or "").strip()
            if not city:
                raise ValueError(f"CSV row {row_number}: City is required")
            if not crime_description:
                raise ValueError(
                    f"CSV row {row_number}: Crime Description is required"
                )

            records.append(
                {
                    "report_number": report_number,
                    "date_reported": parse_datetime(
                        row["Date Reported"],
                        "Date Reported",
                        row_number,
                        DATE_FORMAT,
                        required=True,
                    ),
                    # The source occurrence-date column uses month-first dates.
                    "date_of_occurrence": parse_datetime(
                        row["Date of Occurrence"],
                        "Date of Occurrence",
                        row_number,
                        OCCURRENCE_DATE_FORMAT,
                    ),
                    "time_of_occurrence": parse_datetime(
                        row["Time of Occurrence"],
                        "Time of Occurrence",
                        row_number,
                        DATE_FORMAT,
                    ),
                    "city": city,
                    "crime_code": parse_integer(
                        row["Crime Code"], "Crime Code", row_number
                    ),
                    "crime_description": crime_description,
                    "victim_age": parse_integer(
                        row["Victim Age"], "Victim Age", row_number
                    ),
                    "victim_gender": (row["Victim Gender"] or "").strip(),
                    "weapon_used": (row["Weapon Used"] or "").strip(),
                    "crime_domain": (row["Crime Domain"] or "").strip(),
                    "police_deployed": parse_integer(
                        row["Police Deployed"], "Police Deployed", row_number
                    ),
                    "case_closed": parse_case_closed(row["Case Closed"], row_number),
                    "date_case_closed": parse_datetime(
                        row["Date Case Closed"],
                        "Date Case Closed",
                        row_number,
                        DATE_FORMAT,
                    ),
                }
            )

    return records


def import_records(records, batch_size):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crime_analyzer.settings")

    import django

    django.setup()

    from django.db import transaction
    from django.utils import timezone

    from crime.models import CrimeReport

    existing_numbers = set(
        CrimeReport.objects.filter(report_number__isnull=False).values_list(
            "report_number", flat=True
        )
    )
    new_reports = []
    skipped = 0

    for record in records:
        if record["report_number"] in existing_numbers:
            skipped += 1
            continue

        report = record.copy()
        for field in (
            "date_reported",
            "date_of_occurrence",
            "time_of_occurrence",
            "date_case_closed",
        ):
            if report[field] is not None:
                report[field] = timezone.make_aware(report[field])

        new_reports.append(
            CrimeReport(
                title=f"Report {record['report_number']}: {record['crime_description']}",
                description=record["crime_description"],
                location=record["city"],
                **report,
            )
        )

    with transaction.atomic():
        for start in range(0, len(new_reports), batch_size):
            CrimeReport.objects.bulk_create(
                new_reports[start : start + batch_size], batch_size=batch_size
            )

    print(f"Inserted {len(new_reports)} records; skipped {skipped} already present.")


def main():
    parser = argparse.ArgumentParser(
        description="Import the crime CSV dataset into the configured Django database."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=BASE_DIR / "crime_dataset_india.csv",
        help="CSV file to import (default: crime_dataset_india.csv beside this script)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of records inserted per batch (default: 1000)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the CSV without connecting to or changing the database",
    )
    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error("--batch-size must be greater than zero")

    try:
        records = read_records(args.csv)
    except (OSError, csv.Error, ValueError) as error:
        parser.exit(1, f"Import failed: {error}\n")

    if args.dry_run:
        print(f"Validated {len(records)} records from {args.csv}; database unchanged.")
        return

    import_records(records, args.batch_size)


if __name__ == "__main__":
    main()
