"""Update section 9 (Main Files and Directories) in ENVIRONMENT docs."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

files = {
    "ENVIRONMENT.md": {
        "ztb_section": """├── static/                     # Frontend pages, CSS, JavaScript
├── ztb/                        # Backend services and routes
├── MediaArchiveOrganizer/      # Image analysis and organization modules
├── tests/                      # Automated tests
├── data/                       # Runtime data
├── logs/                       # Logs
└── thumbnails/                 # Legacy or compatibility thumbnail directory""",
        "ztb_replacement": """├── core/                       # Backend core
│   ├── app/                    # Factory, lifespan, middleware
│   ├── config/                 # Paths, extensions, supported formats
│   ├── context_modules/        # Context modules (split by domain)
│   ├── domain/                 # Domain models: RootContext, ImageEntry, etc.
│   ├── infrastructure/         # File transfer, hashing, image processing
│   ├── repositories/           # Data access layer
│   ├── routes/                 # API route handlers
│   ├── services/               # Business services
│   └── use_cases/              # Use-case layer (copy, delete, restore, etc.)
├── MediaArchiveOrganizer/      # Image analysis and organization modules
├── tests/                      # Automated tests
├── data/                       # Runtime data (isolated by image root)
│   └── roots/<root_id>/
│       ├── root.json           # Root configuration
│       ├── deleted/            # App-level recycle area
│       ├── thumbnails/         # Thumbnail cache
│       ├── logs/               # Operation logs (CSV)
│       ├── indexes/            # Image index / timeline index
│       ├── tasks/              # Task scoped outputs
│       ├── hash_db.sqlite3     # Content hash database
│       └── duplicates.json     # Duplicate detection results""",
        "top_entries_old": """├── app.py                      # FastAPI application entry point
├── requirements.txt            # Python dependencies
├── settings.json               # Local settings
├── start.ps1                   # Startup script
├── test.ps1                    # Test script""",
        "top_entries_new": """├── app.py                      # FastAPI application entry point
├── requirements.txt            # Python dependencies
├── requirements-dev.txt        # Test dependencies
├── start.ps1                   # Startup script
├── test.ps1                    # Test script
├── pyproject.toml              # Project metadata""",
        "runtime_path_old": "data/roots/<hash_id>/",
        "runtime_path_new": "data/roots/<root_id>/",
        "hash_db_old": "hash_db.json",
        "hash_db_new": "hash_db.sqlite3",
        "runtime_items_old": """- `deleted/`: app-level recycle area
- `thumbnails/`: thumbnail cache
- `logs/`: operation logs
- `indexes/`: image index and timeline index
- `tasks/`: task outputs
- `duplicates.json`: duplicate image results
- `hash_db.json`: Hash DB""",
        "runtime_items_new": """- `root.json`: root configuration
- `deleted/`: app-level recycle area
- `thumbnails/`: thumbnail cache
- `logs/`: operation logs (CSV format)
- `indexes/`: image index and timeline index
- `tasks/`: task scoped outputs
- `hash_db.sqlite3`: content hash database
- `duplicates.json`: duplicate detection results""",
        "safety_old": "data/roots/<hash_id>/",
        "safety_new": "data/roots/<root_id>/",
        "pip_old": ".\venv\Scripts\python.exe -m pip install -r requirements.txt",
        "pip_new": ".\venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt",
        "quick_pip_old": ".\venv\Scripts\python.exe -m pip install -r requirements.txt",
        "quick_pip_new": ".\venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt",
    },
    "环境配置说明.md": {
        "ztb_section": """├── static/                     # 前端页面、CSS、JavaScript
├── ztb/                        # 后端服务与路由
├── MediaArchiveOrganizer/      # 图片分析与整理相关模块
├── tests/                      # 自动化测试
├── data/                       # 运行数据
├── logs/                       # 日志
└── thumbnails/                 # 旧版或兼容缩略图目录""",
        "ztb_replacement": """├── core/                       # 后端核心
│   ├── app/                    # 应用工厂、生命周期、中间件
│   ├── config/                 # 路径、扩展名、支持格式
│   ├── context_modules/        # 上下文模块（按领域拆分）
│   ├── domain/                 # 领域模型：RootContext、ImageEntry 等
│   ├── infrastructure/         # 文件传输、哈希计算、图片处理
│   ├── repositories/           # 数据访问层
│   ├── routes/                 # API 路由
│   ├── services/               # 业务服务
│   └── use_cases/              # Use-case 层（复制、删除、恢复等）
├── MediaArchiveOrganizer/      # 图片分析与整理相关模块
├── tests/                      # 自动化测试
├── data/                       # 运行数据（按图片根目录隔离）
│   └── roots/<root_id>/
│       ├── root.json           # 根目录配置
│       ├── deleted/            # 应用内回收区
│       ├── thumbnails/         # 缩略图缓存
│       ├── logs/               # 操作日志（CSV 格式）
│       ├── indexes/            # 图片索引 / 时间线索引
│       ├── tasks/              # 任务输出（按任务隔离）
│       ├── hash_db.sqlite3     # 内容哈希数据库
│       └── duplicates.json     # 重复图片检测结果""",
        "top_entries_old": """├── app.py                      # FastAPI 应用入口
├── requirements.txt            # Python 依赖
├── settings.json               # 本地设置
├── start.ps1                   # 启动脚本
├── test.ps1                    # 测试脚本""",
        "top_entries_new": """├── app.py                      # FastAPI 应用入口
├── requirements.txt            # Python 依赖
├── requirements-dev.txt        # 测试依赖
├── start.ps1                   # 启动脚本
├── test.ps1                    # 测试脚本
├── pyproject.toml              # 项目元数据""",
        "runtime_path_old": "data/roots/<hash_id>/",
        "runtime_path_new": "data/roots/<root_id>/",
        "hash_db_old": "hash_db.json",
        "hash_db_new": "hash_db.sqlite3",
        "runtime_items_old": """- `deleted/`：应用内回收区
- `thumbnails/`：缩略图缓存
- `logs/`：操作日志
- `indexes/`：图片索引和时间线索引
- `tasks/`：任务输出
- `duplicates.json`：重复图片结果
- `hash_db.json`：Hash DB""",
        "runtime_items_new": """- `root.json`：根目录配置
- `deleted/`：应用内回收区
- `thumbnails/`：缩略图缓存
- `logs/`：操作日志（CSV 格式）
- `indexes/`：图片索引和时间线索引
- `tasks/`：任务输出（按任务隔离）
- `hash_db.sqlite3`：内容哈希数据库
- `duplicates.json`：重复图片检测结果""",
        "safety_old": "data/roots/<hash_id>/",
        "safety_new": "data/roots/<root_id>/",
        "pip_old": ".\venv\Scripts\python.exe -m pip install -r requirements.txt",
        "pip_new": ".\venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt",
        "quick_pip_old": ".\venv\Scripts\python.exe -m pip install -r requirements.txt",
        "quick_pip_new": ".\venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt",
    },
    "環境設定ガイド.md": {
        "ztb_section": """├── static/                     # フロントエンドページ、CSS、JavaScript
├── ztb/                        # バックエンドサービスとルート
├── MediaArchiveOrganizer/      # 画像解析・整理関連モジュール
├── tests/                      # 自動テスト
├── data/                       # 実行時データ
├── logs/                       # ログ
└── thumbnails/                 # 旧版または互換用サムネイルディレクトリ""",
        "ztb_replacement": """├── core/                       # バックエンド中核
│   ├── app/                    # アプリケーションファクトリ、ライフサイクル、ミドルウェア
│   ├── config/                 # パス、拡張子、対応フォーマット
│   ├── context_modules/        # コンテキストモジュール（ドメイン別に分割）
│   ├── domain/                 # ドメインモデル：RootContext、ImageEntry など
│   ├── infrastructure/         # ファイル転送、ハッシュ計算、画像処理
│   ├── repositories/           # データアクセス層
│   ├── routes/                 # API ルートハンドラ
│   ├── services/               # ビジネスサービス
│   └── use_cases/              # ユースケース層（コピー、削除、復元など）
├── MediaArchiveOrganizer/      # 画像解析・整理関連モジュール
├── tests/                      # 自動テスト
├── data/                       # 実行時データ（画像ルートごとに分離）
│   └── roots/<root_id>/
│       ├── root.json           # ルート設定
│       ├── deleted/            # アプリ内リサイクル領域
│       ├── thumbnails/         # サムネイルキャッシュ
│       ├── logs/               # 操作ログ（CSV 形式）
│       ├── indexes/            # 画像インデックス / タイムラインインデックス
│       ├── tasks/              # タスク出力（タスク別）
│       ├── hash_db.sqlite3     # コンテンツハッシュデータベース
│       └── duplicates.json     # 重複画像検出結果""",
        "top_entries_old": """├── app.py                      # FastAPI アプリケーション入口
├── requirements.txt            # Python 依存関係
├── settings.json               # ローカル設定
├── start.ps1                   # 起動スクリプト
├── test.ps1                    # テストスクリプト""",
        "top_entries_new": """├── app.py                      # FastAPI アプリケーション入口
├── requirements.txt            # Python 依存関係
├── requirements-dev.txt        # テスト依存関係
├── start.ps1                   # 起動スクリプト
├── test.ps1                    # テストスクリプト
├── pyproject.toml              # プロジェクトメタデータ""",
        "runtime_path_old": "data/roots/<hash_id>/",
        "runtime_path_new": "data/roots/<root_id>/",
        "hash_db_old": "hash_db.json",
        "hash_db_new": "hash_db.sqlite3",
        "runtime_items_old": """- `deleted/`: アプリ内リサイクル領域
- `thumbnails/`: サムネイルキャッシュ
- `logs/`: 操作ログ
- `indexes/`: 画像インデックスとタイムラインインデックス
- `tasks/`: タスク出力
- `duplicates.json`: 重複画像結果
- `hash_db.json`: Hash DB""",
        "runtime_items_new": """- `root.json`: ルート設定
- `deleted/`: アプリ内リサイクル領域
- `thumbnails/`: サムネイルキャッシュ
- `logs/`: 操作ログ（CSV 形式）
- `indexes/`: 画像インデックスとタイムラインインデックス
- `tasks/`: タスク出力（タスク別）
- `hash_db.sqlite3`: コンテンツハッシュデータベース
- `duplicates.json`: 重複画像検出結果""",
        "safety_old": "data/roots/<hash_id>/",
        "safety_new": "data/roots/<root_id>/",
        "pip_old": ".\venv\Scripts\python.exe -m pip install -r requirements.txt",
        "pip_new": ".\venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt",
        "quick_pip_old": ".\venv\Scripts\python.exe -m pip install -r requirements.txt",
        "quick_pip_new": ".\venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt",
    },
}


def main():
    for fname, repl in files.items():
        fpath = REPO / fname
        print(f"\n=== {fname} ===")
        content = fpath.read_text(encoding="utf-8")
        changes = 0

        for key, old, new in [
            ("ztb_section", repl["ztb_section"], repl["ztb_replacement"]),
            ("top_entries", repl["top_entries_old"], repl["top_entries_new"]),
            ("runtime_path", repl["runtime_path_old"], repl["runtime_path_new"]),
            ("hash_db", repl["hash_db_old"], repl["hash_db_new"]),
            ("runtime_items", repl["runtime_items_old"], repl["runtime_items_new"]),
            ("pip", repl["pip_old"], repl["pip_new"]),
            ("quick_pip", repl["quick_pip_old"], repl["quick_pip_new"]),
            ("safety", repl["safety_old"], repl["safety_new"]),
        ]:
            if old in content:
                content = content.replace(old, new, 1)
                changes += 1
                print(f"  REPLACED: {key}")
            else:
                print(f"  SKIPPED (not found): {key}")

        fpath.write_text(content, encoding="utf-8")
        print(f"  Total: {changes} replacements")


if __name__ == "__main__":
    main()
