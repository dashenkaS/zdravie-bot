# Подключение к базе данных через SQLAlchemy
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./zdravie.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# каждый запрос к API получает свою сессию, соединение с БД
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# базовый класс от которого наследуются все модели
Base = declarative_base()


class UserResponse(Base):
    """Модель таблицы в базе данных. Каждый атрибут класса = столбец в таблице."""

    __tablename__ = "user_responses"

    id = Column(Integer, primary_key=True, index=True)

    # ID пользователя
    user_id = Column(Integer, unique=True, index=True)

    # @username
    username = Column(String, nullable=True)

    # Имя
    first_name = Column(String, nullable=True)

    # Ответы на вопросы
    visit_frequency = Column(String, nullable=True)
    topics = Column(String, nullable=True)
    health_satisfaction = Column(String, nullable=True)
    consultation = Column(String, nullable=True)
    social_network = Column(String, nullable=True)

    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def create_tables():
    """Создаём все таблицы в БД, если их ещё нет"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Генератор сессии для FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
