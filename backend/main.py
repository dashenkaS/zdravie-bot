# Запуск: uvicorn backend.main:app --reload --port 8000
# --reload означает что сервер перезапускается при изменении кода

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

from backend.database import create_tables, get_db, UserResponse as DBUserResponse

# Создаём приложение
app = FastAPI(
    title="Zdravie Bot Backend",
    description="Бэкенд для опросного бота Галины Старшиновой. "
                "Документация API — /docs, альтернативная — /redoc",
    version="1.0.0",
)

# Создаём таблицы при старте сервера
create_tables()


# Pydantic-схема
class UserResponseSchema(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    visit_frequency: Optional[str] = None
    topics: Optional[str] = None
    health_satisfaction: Optional[str] = None
    consultation: Optional[str] = None
    social_network: Optional[str] = None



# Декораторы

@app.get("/")
def root():
    """Проверка что сервер работает"""

    return {"status": "Бэкенд работает", "docs": "/docs"}


@app.post("/save_response")
def save_response(data: UserResponseSchema, db: Session = Depends(get_db)):
    """
    Сохраняем ответ пользователя в БД:
	Если пользователь уже есть - обновляем его запись
    Бот отправляет данные после каждого вопроса,
    так мы не теряем данные, если человек бросил опрос

    Depends(get_db) — FastAPI сам создаст сессию БД и передаст её сюда.
    """

    existing = db.query(DBUserResponse).filter(
        DBUserResponse.user_id == data.user_id
    ).first()

    if existing:
        for field, value in data.model_dump().items():
        # Обновляем только те поля которые пришли
            if value is not None:
                setattr(existing, field, value)
        existing.updated_at = datetime.utcnow()
    else:
        new_record = DBUserResponse(**data.model_dump())
        db.add(new_record)

    db.commit()
    return {"status": "ok", "message": "Ответ сохранён"}


@app.get("/responses")
def get_all_responses(db: Session = Depends(get_db)):
    """
    Возвращает все ответы из БД.
    http://localhost:8000/responses
    """

    rows = db.query(DBUserResponse).all()
    result = []
    for r in rows:
        result.append({
            "user_id": r.user_id,
            "username": r.username,
            "first_name": r.first_name,
            "visit_frequency": r.visit_frequency,
            "topics": r.topics,
            "health_satisfaction": r.health_satisfaction,
            "consultation": r.consultation,
            "social_network": r.social_network,
            "created_at": str(r.created_at),
            "updated_at": str(r.updated_at),
        })
    return result


@app.get("/user/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Получить ответы конкретного пользователя по его Telegram ID"""

    user = db.query(DBUserResponse).filter(
        DBUserResponse.user_id == user_id
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {
        "user_id": user.user_id,
        "username": user.username,
        "first_name": user.first_name,
        "visit_frequency": user.visit_frequency,
        "topics": user.topics,
        "health_satisfaction": user.health_satisfaction,
        "consultation": user.consultation,
        "social_network": user.social_network,
    }


@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """
    Статистика по всем ответам.
    Показывает сколько раз выбирался каждый вариант ответа.
    """

    rows = db.query(DBUserResponse).all()

    freq_stats, topics_stats, health_stats, consult_stats, social_stats = {}, {}, {}, {}, {}

    for r in rows:
        if r.visit_frequency:
            freq_stats[r.visit_frequency] = freq_stats.get(r.visit_frequency, 0) + 1
        if r.topics:
            topics_stats[r.topics] = topics_stats.get(r.topics, 0) + 1
        if r.health_satisfaction:
            health_stats[r.health_satisfaction] = health_stats.get(r.health_satisfaction, 0) + 1
        if r.consultation:
            consult_stats[r.consultation] = consult_stats.get(r.consultation, 0) + 1
        if r.social_network:
            social_stats[r.social_network] = social_stats.get(r.social_network, 0) + 1

    return {
        "total_users": len(rows),
        "visit_frequency": freq_stats,
        "topics": topics_stats,
        "health_satisfaction": health_stats,
        "consultation": consult_stats,
        "social_network": social_stats,
    }

@app.delete("/user/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Удалить пользователя по его Telegram ID"""
    user = db.query(DBUserResponse).filter(
        DBUserResponse.user_id == user_id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    db.delete(user)
    db.commit()
    return {"status": "ok", "message": f"Пользователь {user_id} удалён"}
