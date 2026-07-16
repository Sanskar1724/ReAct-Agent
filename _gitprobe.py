import subprocess, pathlib
p = pathlib.Path(r"L:\bakchodi\Single-Agent\_git.txt")
lines = []
def run(cmd):
    try:
        out = subprocess.run(cmd, cwd=r"L:\bakchodi\Single-Agent", capture_output=True, text=True, shell=True)
        lines.append(f"$ {cmd}")
        lines.append(out.stdout or "")
        lines.append(out.stderr or "")
        lines.append("-"*40)
    except Exception as e:
        lines.append(f"ERR {e}")
p.write_text("\n".join(lines), encoding="utf-8")
