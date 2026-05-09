import os
from pathlib import Path


def render_template(template, input_file, **values):
    path = Path(input_file)
    base_values = {
        "name": path.stem,
        "ext": path.suffix.lstrip(".") or "pdf",
    }
    base_values.update(values)
    filename = template.format(**base_values)
    return filename if filename.lower().endswith(".pdf") else f"{filename}.pdf"


def output_path(output_dir, template, input_file, **values):
    return os.path.join(output_dir, render_template(template, input_file, **values))


def output_exists(path):
    return bool(path and os.path.exists(path))
