"""Remove PNG metadata without decoding or recompressing image pixels."""

import os
import struct
import sys
import tempfile

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
COPY_BLOCK_SIZE = 1024 * 1024


def do_backup():
    try:
        eworker_dir = r"d:\Github\eworker"
        if eworker_dir not in sys.path:
            sys.path.insert(0, eworker_dir)
        from auto_donate_watcher import backup_desktop_files

        backup_desktop_files()
        print("[clean_metadata] Backup completed successfully")
    except Exception as exc:
        print(f"[clean_metadata] Backup error: {exc}")


def _copy_chunk_data(source, destination, length):
    remaining = length
    while remaining:
        block = source.read(min(remaining, COPY_BLOCK_SIZE))
        if not block:
            raise ValueError("Unexpected end of file inside PNG chunk")
        destination.write(block)
        remaining -= len(block)
    crc = source.read(4)
    if len(crc) != 4:
        raise ValueError("Unexpected end of file inside PNG chunk CRC")
    destination.write(crc)


def _strip_png_chunks(path):
    folder = os.path.dirname(os.path.abspath(path))
    temp_path = None
    try:
        with open(path, "rb") as source:
            if source.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                raise ValueError("File is not a valid PNG")
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=folder, prefix=".clean_metadata_", suffix=".tmp", delete=False
            ) as destination:
                temp_path = destination.name
                destination.write(PNG_SIGNATURE)
                saw_header = False
                saw_image_data = False
                saw_end = False

                while not saw_end:
                    header = source.read(8)
                    if len(header) != 8:
                        raise ValueError("PNG ended before IEND chunk")
                    length, chunk_type = struct.unpack(">I4s", header)
                    if not saw_header and chunk_type != b"IHDR":
                        raise ValueError("PNG does not start with IHDR")
                    if chunk_type == b"IHDR":
                        if saw_header or length != 13:
                            raise ValueError("Invalid IHDR chunk")
                        saw_header = True
                    if chunk_type == b"IDAT":
                        saw_image_data = True

                    # Keep image-structure chunks and tRNS (transparency is pixel
                    # semantics for palette/grayscale/RGB PNGs, not removable metadata).
                    is_critical = not (chunk_type[0] & 0x20)
                    keep = is_critical or chunk_type == b"tRNS"
                    if keep:
                        destination.write(header)
                        _copy_chunk_data(source, destination, length)
                    else:
                        _discard_chunk(source, length)

                    if chunk_type == b"IEND":
                        if length != 0 or not saw_image_data:
                            raise ValueError("Invalid PNG IEND or missing image data")
                        saw_end = True

                destination.flush()
                os.fsync(destination.fileno())

        # Windows cannot replace a file while its source handle is still open.
        source.close()
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def _discard_chunk(source, length):
    remaining = length + 4  # chunk data plus CRC
    while remaining:
        block = source.read(min(remaining, COPY_BLOCK_SIZE))
        if not block:
            raise ValueError("Unexpected end of file inside PNG chunk")
        remaining -= len(block)


def _create_example(path):
    if os.path.basename(path).lower() != "complete.png":
        return
    try:
        eworker_dir = r"d:\Github\eworker"
        if eworker_dir not in sys.path:
            sys.path.insert(0, eworker_dir)
        from watermark_engine import create_anti_ai_watermark
        from PIL import Image

        with Image.open(path) as image:
            example = create_anti_ai_watermark(image)
            example.save(os.path.join(os.path.dirname(os.path.abspath(path)), "example.png"), format="PNG")
        print("[clean_metadata] Auto-generated example.png")
    except Exception as exc:
        print(f"[clean_metadata] Watermark generation error: {exc}")


def clean_metadata(path):
    if not os.path.isfile(path):
        print(f"[clean_metadata] File not found: {path}", file=sys.stderr)
        return 1
    try:
        _strip_png_chunks(path)
        print(f"[clean_metadata] Metadata removed: {path}")
        _create_example(path)
        return 0
    except Exception as exc:
        print(f"[clean_metadata] Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--backup":
        do_backup()
    elif len(sys.argv) > 1:
        sys.exit(clean_metadata(sys.argv[1]))
    else:
        print("Usage: clean_metadata.py <png_path> | --backup", file=sys.stderr)
        sys.exit(2)
