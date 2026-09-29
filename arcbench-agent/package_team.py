"""Package development sources for teammates, excluding all local credentials and outputs."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = ('main.py', 'requirements.txt', 'package_agent.py', 'package_team.py',
         'run_local.ps1', 'check_connection.py', 'env.example', '.gitignore',
         'AGENTS.md', 'DEVELOPMENT.md', 'README.md', 'VERIFICATION.md', 'tests/test_agent.py')

def build():
    for line in (ROOT/'env.example').read_text(encoding='utf-8').splitlines():
        if line.strip().startswith('OPENAI_API_KEY=') and line.split('=',1)[1].strip():
            raise ValueError('Remove the real key from env.example before sharing')
    destination = ROOT.parent/'arcbench-agent-team.zip'
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            path = ROOT/name
            if path.is_symlink():
                raise ValueError('No symlinks in shared files')
            archive.write(path, 'arcbench-agent/'+name)
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {'arcbench-agent/'+name for name in FILES}
    print(destination)

if __name__ == '__main__':
    build()
