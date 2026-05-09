def parse_page_ranges(ranges):
    if not ranges:
        return []

    pages = []
    for part in ranges.split(","):
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            start, end = [value.strip() for value in part.split("-", 1)]
            if not start.isdigit() or not end.isdigit():
                raise ValueError(f"Invalid page range: {part}")
            if int(start) < 1 or int(end) < int(start):
                raise ValueError(f"Invalid page range: {part}")
            pages.append(f"{int(start)}-{int(end)}")
        else:
            if not part.isdigit() or int(part) < 1:
                raise ValueError(f"Invalid page number: {part}")
            pages.append(str(int(part)))

    if not pages:
        raise ValueError("Page range cannot be empty")

    return pages


def page_range_args(ranges):
    return [",".join(parse_page_ranges(ranges))] if ranges else ["1-z"]
