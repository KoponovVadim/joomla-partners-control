#!/usr/bin/env python3
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "joomla_connector" / "plg_ajax_jpcconnector"
OUTPUT = ROOT / "dist" / "plg_ajax_jpcconnector-1.0.0.zip"
FILES = (
    "jpcconnector.php",
    "jpcconnector.xml",
    "script.php",
    "README.txt",
    "index.html",
)


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for name in FILES:
            source = SOURCE / name
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    build()
