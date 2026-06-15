# Модуль машинного обучения - анализ ответов подписчиков

import os
import pickle
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

MODEL_FILE = "ml_model.pkl"
SCALER_FILE = "ml_scaler.pkl"

FREQUENCY_MAP = {
    "Часто": 4,
    "1-2 раза в неделю": 3,
    "1 раз в месяц": 2,
    "Напомните, что за канал": 1
}

HEALTH_MAP = {
    "100%": 1,
    "75%": 2,
    "50%": 3,
    "Менее 50%": 4
}

CONSULTATION_MAP = {
    "Ребалансинг": 5,
    "Психологическая консультация": 5,
    "Клуб «Свобода дышать»": 4,
    "Собираюсь записаться": 3,
    "Не планирую": 1,
}

TOPICS_MAP = {
    "Психосоматика": 4,
    "Телесная терапия": 3,
    "Общие темы про здоровье": 2,
    "Саморазвитие": 1,
}

# Названия сегментов
SEGMENT_NAMES = {
    0: "Горячие клиенты", # активные, высокая вовлечённость
    1: "Тёплые читатели", # регулярно читают, пока не готовы платить
    2: "Случайные гости", # редко заходят, низкая вовлечённость
}

# Что рекомендовать для каждого сегмента
SEGMENT_TIPS = {
    0: "Предложите личную консультацию - они готовы!",
    1: "Делитесь кейсами, отзывами клиентов, постепенно подогревайте интерес.",
    2: "Напомните о ценности канала, предложите бесплатный материал для знакомства.",
}


def encode_response(resp: dict) -> list:
    """
    Кодируем один ответ в числовой вектор [x1, x2, x3, x4].
    """

    return [
        FREQUENCY_MAP.get(resp.get("visit_frequency") or "", 0),
        HEALTH_MAP.get(resp.get("health_satisfaction") or "", 0),
        CONSULTATION_MAP.get(resp.get("consultation") or "", 0),
        TOPICS_MAP.get(resp.get("topics") or "", 0),
    ]


def train_model(responses: list) -> dict:
    """
    Обучаем модель KMeans на всех собранных ответах.
    responses - список словарей с ответами из БД
    """
    if len(responses) < 3:
        return {
            "error": "Нужно минимум 3 заполненные анкеты для обучения модели"
        }

    # Кодируем ответы
    X = []
    for r in responses:
        encoded = encode_response(r)
        # Берём только тех у кого есть хотя бы 2 ответа
        if sum(1 for v in encoded if v > 0) >= 2:
            X.append(encoded)

    if len(X) < 10:
        return {"error": "Недостаточно заполненных анкет (нужно минимум 10 с 2+ ответами)"}

    X = np.array(X, dtype=float)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    n_clusters = min(3, len(X))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    # Сохраняем модель и нормализатор в файлы
    with open(MODEL_FILE, "wb") as f:
        pickle.dump(kmeans, f)
    with open(SCALER_FILE, "wb") as f:
        pickle.dump(scaler, f)

    # Считаем статистику по кластерам
    cluster_stats = {}
    for i in range(n_clusters):
        count = int(np.sum(labels == i))
        name = SEGMENT_NAMES.get(i, f"Сегмент {i+1}")
        cluster_stats[name] = count

    return {
        "status": "Модель обучена",
        "total_processed": len(X),
        "segments": cluster_stats,
        "model_quality": f"Inertia = {kmeans.inertia_}"
    }


def predict_segment(response_dict: dict) -> dict:
    """
    Определяем сегмент конкретного пользователя.
    Если модель не обучена: возвращаем подсказку.
    """
    if not os.path.exists(MODEL_FILE):
        return {
            "segment": "Модель не обучена",
            "tip": "Сначала вызовите POST /ml/train",
        }

    with open(MODEL_FILE, "rb") as f:
        kmeans = pickle.load(f)
    with open(SCALER_FILE, "rb") as f:
        scaler = pickle.load(f)

    encoded = np.array([encode_response(response_dict)], dtype=float)
    scaled = scaler.transform(encoded)
    cluster = int(kmeans.predict(scaled)[0])

    return {
        "segment": SEGMENT_NAMES.get(cluster, f"Сегмент {cluster}"),
        "recommendation": SEGMENT_TIPS.get(cluster, "")
    }


def get_readiness_score(response_dict: dict) -> dict:
    """Метрика готовности к покупке от 0 до 100."""
    encoded = encode_response(response_dict)
    # Максимально возможный балл: 4 + 4 + 5 + 4 = 17
    raw = sum(encoded)
    score = int((raw / 17) * 100) if raw > 0 else 0

    if score >= 70:
        level = "Высокая"
    elif score >= 40:
        level = "Средняя"
    else:
        level = "Низкая"

    return {"readiness_score": score, "readiness_level": level}
