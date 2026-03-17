"""Модели и адаптеры входящего потока сообщений."""

from app.upstream.consumer import KafkaUpdatesConsumer

__all__ = ["KafkaUpdatesConsumer"]