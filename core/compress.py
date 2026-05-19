import os
from concurrent.futures import ProcessPoolExecutor
from config import DEFAULT_OUTPUT_DIR, GS_PATH
from core.cache import get_cached_result, save_to_cache
from core.executor import run_command
from core.output import output_path
from core.validation import validate_output_pdf, validate_pdf_file


COMPRESSION_LEVELS = {
    "1": "/prepress",
    "2": "/printer",
    "3": "/default",
    "4": "/ebook",
    "5": "/screen",
}

COMPRESSION_LEVEL_LABELS = {
    "1": "Level 1 - least compression, highest quality",
    "2": "Level 2 - light compression",
    "3": "Level 3 - balanced",
    "4": "Level 4 - strong compression",
    "5": "Level 5 - most compression, smallest size",
}

LEGACY_COMPRESSION_LEVELS = {
    "prepress": "1",
    "printer": "2",
    "default": "3",
    "ebook": "4",
    "screen": "5",
}

PERFORMANCE_PROFILES = {
    "fast": "Fast - maximize throughput",
    "balanced": "Balanced - recommended",
    "quality": "Quality - lower system load",
}


def normalize_compression_level(level):
    normalized = level.strip().lower().lstrip("/")
    normalized = LEGACY_COMPRESSION_LEVELS.get(normalized, normalized)
    if normalized not in COMPRESSION_LEVELS:
        valid = ", ".join(COMPRESSION_LEVELS)
        raise ValueError(f"Invalid compression level '{level}'. Choose one of: {valid}")
    return COMPRESSION_LEVELS[normalized]


def compression_level_description(level):
    normalized = level.strip().lower().lstrip("/")
    normalized = LEGACY_COMPRESSION_LEVELS.get(normalized, normalized)
    if normalized not in COMPRESSION_LEVEL_LABELS:
        valid = ", ".join(COMPRESSION_LEVELS)
        raise ValueError(f"Invalid compression level '{level}'. Choose one of: {valid}")
    return COMPRESSION_LEVEL_LABELS[normalized]


def normalize_performance_profile(profile):
    normalized = (profile or "balanced").strip().lower()
    if normalized not in PERFORMANCE_PROFILES:
        valid = ", ".join(PERFORMANCE_PROFILES)
        raise ValueError(f"Invalid performance profile '{profile}'. Choose one of: {valid}")
    return normalized


def get_parallelism_settings(file_count, profile="balanced", total_cpus=None):
    total_cpus = total_cpus or (os.cpu_count() or 2)
    profile = normalize_performance_profile(profile)
    file_count = max(1, int(file_count or 1))

    if file_count == 1:
        if profile == "fast":
            return 1, total_cpus
        if profile == "quality":
            return 1, max(1, total_cpus // 2)
        return 1, max(1, total_cpus - 1)

    if profile == "fast":
        max_workers = min(file_count, total_cpus, 6)
    elif profile == "quality":
        max_workers = min(file_count, 2, max(1, total_cpus // 2))
    else:
        max_workers = min(file_count, max(1, total_cpus - 1), 4)

    threads_per_worker = max(1, total_cpus // max_workers)
    return max_workers, threads_per_worker


def compression_stats(input_file, output_file):
    original_size = os.path.getsize(input_file)
    compressed_size = os.path.getsize(output_file)
    saved_bytes = original_size - compressed_size
    saved_percent = (saved_bytes / original_size * 100) if original_size else 0
    return {
        "original_size": original_size,
        "compressed_size": compressed_size,
        "saved_bytes": saved_bytes,
        "saved_percent": saved_percent,
    }


def format_size(size_bytes):
    units = ["B", "KB", "MB", "GB"]
    size = float(size_bytes)
    for unit in units:
        if abs(size) < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def format_compression_summary(stats):
    return (
        f"original {format_size(stats['original_size'])}, "
        f"compressed {format_size(stats['compressed_size'])}, "
        f"saved {format_size(stats['saved_bytes'])} ({stats['saved_percent']:.1f}%)"
    )


def build_compress_command(input_file, output_file, level="/ebook", password=None, threads=None):
    level = normalize_compression_level(level)
    cpu_count = threads if threads is not None else (os.cpu_count() or 2)
    cmd = [
        GS_PATH,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={level}",
        f"-dNumRenderingThreads={cpu_count}",
        "-dFastWebView=true",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={output_file}",
    ]
    if password:
        cmd.append(f"-sPDFPassword={password}")
    cmd.append(input_file)
    return cmd


def compress_pdf(input_file, output_file, level="/ebook", runner=None, include_summary=False, password=None, progress_callback=None, threads=None):
    input_error = validate_pdf_file(input_file)
    if input_error:
        return f"ERROR: {input_error}"

    output_error = validate_output_pdf([input_file], output_file)
    if output_error:
        return f"ERROR: {output_error}"

    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    cmd = build_compress_command(input_file, output_file, level, password=password, threads=threads)
    
    # Check cache
    cached = get_cached_result(input_file, "compress", {"level": level, "password": password})
    if cached and os.path.exists(cached):
        try:
            import shutil
            shutil.copy2(cached, output_file)
            if include_summary:
                return f"SUCCESS (from cache): {format_compression_summary(compression_stats(input_file, output_file))}"
            return "SUCCESS"
        except Exception:
            pass # Fallback to real compression if copy fails

    result = runner.run(cmd, progress_callback=progress_callback, output_path=output_file) if runner else run_command(cmd)

    if result == "SUCCESS":
        save_to_cache(input_file, "compress", {"level": level, "password": password}, output_file)
        if include_summary:
            try:
                return f"SUCCESS: {format_compression_summary(compression_stats(input_file, output_file))}"
            except OSError as e:
                return f"SUCCESS: summary unavailable ({e})"

    return result


def _compress_many_worker(file, lvl, out_dir, out_template, pwd, threads_per_worker):
    try:
        os.makedirs(out_dir, exist_ok=True)
        output = output_path(out_dir, out_template, file, level=lvl)
        result = compress_pdf(
            file,
            output,
            lvl,
            include_summary=True,
            password=pwd,
            threads=threads_per_worker,
        )
        return (file, output, result)
    except Exception as e:
        return (file, None, f"ERROR: {e}")


def compress_many(
    files,
    level="/ebook",
    max_workers=None,
    output_dir=DEFAULT_OUTPUT_DIR,
    output_template="{name}.pdf",
    password=None,
    progress_callback=None,
    profile="balanced",
):
    del progress_callback
    total_cpus = os.cpu_count() or 2
    computed_workers, threads_per_worker = get_parallelism_settings(
        len(files),
        profile=profile,
        total_cpus=total_cpus,
    )
    if max_workers is None:
        max_workers = computed_workers

    total = len(files)
    completed = 0
    results = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                _compress_many_worker,
                f,
                level,
                output_dir,
                output_template,
                password,
                threads_per_worker,
            )
            for f in files
        ]

        for future in futures:
            res = future.result()
            results.append(res)
            completed += 1
            print(f"[{completed}/{total}] Done: {res[0]}")

    return results
