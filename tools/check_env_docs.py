import pathlib

files = ["ENVIRONMENT.md", "环境配置说明.md", "環境設定ガイド.md"]
terms = ["ztb/", "hash_db.json", "hash_db.sqlite3", "<hash_id>",
         "<root_id>", "root.json", "requirements-dev.txt", "pyproject.toml",
         "context_modules", "use_cases", "infrastructure", "core/"]

for fname in files:
    content = pathlib.Path(fname).read_text(encoding="utf-8")
    print(f"=== {fname} ===")
    for t in terms:
        print(f"  {t}: {'YES' if t in content else 'no'}")
    # Count pip install lines
    lines = content.split("\n")
    pip_no_dev = sum(1 for l in lines if "pip install -r requirements.txt" in l and "-r requirements-dev.txt" not in l and "--upgrade" not in l)
    pip_with_dev = sum(1 for l in lines if "pip install -r requirements.txt -r requirements-dev.txt" in l)
    print(f"  pip w/o dev: {pip_no_dev}")
    print(f"  pip with dev: {pip_with_dev}")
    print()
