# SPDX-License-Identifier: MIT

"""Root-scoped SQLite storage APIs.

The task and duplicate-result flows now use these repositories for root-scoped
SQLite writes and reads. Some legacy JSON/CSV formats remain as compatibility
inputs while the migration proceeds incrementally.
"""
