from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from typing import Type, TypeVar, Generic
from sqlalchemy.orm import DeclarativeBase

T = TypeVar("T", bound=DeclarativeBase)


def upsert_model(
    db: Session,
    model: Type[T],
    conflict_columns: list[str],
    data: dict,
    update_columns: list[str] | None = None,
) -> T:
    """
    Perform an upsert using PostgreSQL's ON CONFLICT.
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        conflict_columns: Columns that define the unique constraint for conflict detection
        data: Dictionary of column values to insert/update
        update_columns: Columns to update on conflict (defaults to all non-conflict columns)
    
    Returns:
        The inserted or updated model instance
    """
    if update_columns is None:
        mapper = inspect(model)
        all_columns = [c.key for c in mapper.columns if not c.primary_key]
        update_columns = [c for c in all_columns if c not in conflict_columns]
    
    stmt = pg_insert(model).values(**data)
    stmt = stmt.on_conflict_do_update(
        index_elements=conflict_columns,
        set_={col: stmt.excluded[col] for col in update_columns}
    ).returning(model)
    
    result = db.execute(stmt)
    db.commit()
    return result.scalar_one()


def get_or_create(
    db: Session,
    model: Type[T],
    filter_by: dict,
    create_data: dict | None = None,
) -> tuple[T, bool]:
    """
    Get existing instance or create new one atomically.
    
    Returns:
        Tuple of (instance, created)
    """
    instance = db.query(model).filter_by(**filter_by).first()
    if instance:
        return instance, False
    
    if create_data is None:
        create_data = filter_by
    
    instance = model(**create_data)
    db.add(instance)
    try:
        db.commit()
        db.refresh(instance)
        return instance, True
    except IntegrityError:
        db.rollback()
        # Race condition - another process created it
        instance = db.query(model).filter_by(**filter_by).first()
        if instance:
            return instance, False
        raise


def get_by_unique_field(
    db: Session,
    model: Type[T],
    field_name: str,
    value: str,
    case_insensitive: bool = False,
) -> T | None:
    """Get a model instance by a unique field, optionally case-insensitive."""
    col = getattr(model, field_name)
    if case_insensitive:
        from sqlalchemy import func
        return db.query(model).filter(func.lower(col) == value.lower()).first()
    return db.query(model).filter(col == value).first()