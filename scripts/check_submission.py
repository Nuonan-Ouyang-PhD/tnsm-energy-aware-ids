"""Verify the published submission ZIP without compiling or running experiments."""

from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile


def main():
    release = Path(__file__).resolve().parents[1] / "releases/submission"
    archive = release / "TNSM_Submission_Final.zip"
    expected = (release / "ARCHIVE_SHA256.txt").read_text().split()[0]
    if sha256(archive.read_bytes()).hexdigest() != expected:
        raise SystemExit("FAIL: submission ZIP hash mismatch")
    with ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise SystemExit("FAIL: ZIP CRC")
        files = {name for name in zipped.namelist() if not name.endswith("/")}
        for name in files:
            if name.startswith("/") or ".." in Path(name).parts:
                raise SystemExit("FAIL: unsafe ZIP path")
            if name.endswith((".zip", ".aux", ".log", ".blg", ".out")):
                raise SystemExit("FAIL: nested archive or build artifact")
            if zipped.read(name) != (release / "package" / name).read_bytes():
                raise SystemExit(f"FAIL: extracted package differs: {name}")
        manifest = "Source_Files/MANIFEST_SHA256.txt"
        listed = set()
        for line in zipped.read(manifest).decode().splitlines():
            digest, relative = line.split(None, 1)
            name = "Source_Files/" + relative
            if name in listed or sha256(zipped.read(name)).hexdigest() != digest:
                raise SystemExit(f"FAIL: source manifest: {name}")
            listed.add(name)
        source_files = {name for name in files if name.startswith("Source_Files/")}
        if listed != source_files - {manifest}:
            raise SystemExit("FAIL: manifest coverage")
    print(f"PASS: ZIP hash, CRC, {len(files)} files, {len(listed)} source hashes, package equality")


if __name__ == "__main__":
    main()
