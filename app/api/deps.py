from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.evaluation import EvaluationService
from app.services.ingestion import DocumentIngestionService
from app.services.qa import QAService

FEATURE_FLAG_LABELS = {
    "evals": "评测与回归功能",
    "replay_experiments": "回放实验功能",
}


def get_settings_dep() -> Settings:
    return get_settings()


def get_feature_flags_dep(settings: Settings = Depends(get_settings_dep)) -> dict[str, bool]:
    return settings.feature_flags


def require_feature_enabled(feature_name: str):
    feature_label = FEATURE_FLAG_LABELS[feature_name]

    def dependency(feature_flags: dict[str, bool] = Depends(get_feature_flags_dep)) -> None:
        if feature_flags.get(feature_name, False):
            return
        raise HTTPException(status_code=503, detail=f"当前环境未启用{feature_label}")

    return dependency


def get_session_dep(session: Session = Depends(get_db_session)) -> Session:
    return session


def get_ingestion_service(session: Session = Depends(get_session_dep)) -> DocumentIngestionService:
    return DocumentIngestionService(session)


def get_qa_service(session: Session = Depends(get_session_dep)) -> QAService:
    return QAService(session)


def get_evaluation_service(session: Session = Depends(get_session_dep)) -> EvaluationService:
    return EvaluationService(session)
