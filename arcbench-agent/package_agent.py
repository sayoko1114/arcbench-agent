"""Build an explicit allowlist archive, never the sibling application demo."""
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = ('main.py', 'requirements.txt')

def build(destination=None):
    destination = Path(destination or ROOT.parent / 'arcbench-agent.zip')
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            path = ROOT / name
            if path.is_symlink():
                raise ValueError('No symlinks in submission sources')
            archive.write(path, name)
    with zipfile.ZipFile(destination) as archive:
        assert sorted(archive.namelist()) == sorted(FILES)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix('.zip.sha256').write_text(digest + '\n', encoding='ascii')
    return destination

if __name__ == '__main__':
    print(build())
