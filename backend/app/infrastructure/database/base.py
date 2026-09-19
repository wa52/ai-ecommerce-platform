from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """AI 扩展层自有表的声明式基类（Alembic 的 target_metadata）。"""
