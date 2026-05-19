def parse_page_ranges(ranges):
    if not ranges or not ranges.strip():
        return []

    def validate_val(val):
        v = val.lower()
        if v == "z":
            return v
        if v.isdigit() and int(v) >= 1:
            return v
        return None

    pages = []
    for part in ranges.split(","):
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            raw_start, raw_end = [p.strip() for p in part.split("-", 1)]
            start = validate_val(raw_start)
            end = validate_val(raw_end)

            if not start or not end:
                raise ValueError(f"Invalid page range: {part}")

            # Logical check for numeric ranges
            if start.isdigit() and end.isdigit() and int(end) < int(start):
                raise ValueError(f"Invalid page range: {part}")

            pages.append(f"{start}-{end}")
        else:
            val = validate_val(part)
            if not val:
                raise ValueError(f"Invalid page number: {part}")
            pages.append(val)

    if not pages:
        raise ValueError("Page range cannot be empty")

    return pages


def page_range_args(ranges):
    return [",".join(parse_page_ranges(ranges))] if ranges else ["1-z"]
