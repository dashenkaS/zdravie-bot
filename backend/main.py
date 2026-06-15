# Запуск: uvicorn backend.main:app --reload --port 8000
# --reload означает что сервер перезапускается при изменении кода

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

from backend.database import create_tables, get_db, UserResponse as DBUserResponse
from backend.ml_analysis import train_model, predict_segment, get_readiness_score

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
    Сохраняем ответ пользователя в БД

    Логика:
    Если пользователь уже есть - обновляем его запись
    Это нужно потому что бот отправляет данные после каждого вопроса,
    а не один раз в конце - так мы не теряем данные, если человек бросил опрос

    Depends(get_db) — FastAPI сам создаст сессию БД и передаст её сюда.
    """

    existing = db.query(DBUserResponse).filter(
        DBUserResponse.user_id == data.user_id
    ).first()

    if existing:
        for field, value in data.model_dump().items():
            if value is not None:                           # Обновляем только те поля которые пришли
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
    Агрегированная статистика по всем ответам.
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


# ML-эндпоинты
@app.post("/ml/train")
def train_ml(db: Session = Depends(get_db)):
    """
    Обучаем модель кластеризации KMeans.
    Вызывать когда накопилось хотя бы 10 ответов.
    После обучения модель сохраняется в файл ml_model.pkl.
    """

    rows = db.query(DBUserResponse).all()
    responses_list = [
        {
            "visit_frequency": r.visit_frequency,
            "health_satisfaction": r.health_satisfaction,
            "consultation": r.consultation,
            "topics": r.topics,
        }
        for r in rows
    ]
    return train_model(responses_list)


@app.get("/ml/segment/{user_id}")
def get_segment(user_id: int, db: Session = Depends(get_db)):
    """
    Определяем к какому сегменту (типу аудитории) относится пользователь.
    Возвращает название сегмента и рекомендацию для работы с ним.
    """

    user = db.query(DBUserResponse).filter(
        DBUserResponse.user_id == user_id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    response_dict = {
        "visit_frequency": user.visit_frequency,
        "health_satisfaction": user.health_satisfaction,
        "consultation": user.consultation,
        "topics": user.topics,
    }
    segment = predict_segment(response_dict)
    score = get_readiness_score(response_dict)
    return {**segment, **score}


@app.get("/ml/all_segments")
def get_all_segments(db: Session = Depends(get_db)):
    """
    Показывает сегмент и балл готовности для каждого пользователя.
    Удобно чтобы увидеть картину по всей аудитории.
    """

    rows = db.query(DBUserResponse).all()
    result = []
    for r in rows:
        resp = {
            "visit_frequency": r.visit_frequency,
            "health_satisfaction": r.health_satisfaction,
            "consultation": r.consultation,
            "topics": r.topics,
        }
        seg = predict_segment(resp)
        score = get_readiness_score(resp)
        result.append({
            "user_id": r.user_id,
            "username": r.username,
            "first_name": r.first_name,
            "segment": seg.get("segment"),
            "readiness_score": score.get("readiness_score"),
            "readiness_level": score.get("readiness_level"),
        })
    return result
