"""Kafka-based downstream sink for Telegram updates."""
import json
import logging
from typing import Protocol

from aiokafka import AIOKafkaProducer

from app.downstream.envelope import build_update_envelope
from app.downstream.sink import UpdateSink
from app.telegram.types import TelegramUpdate

logger = logging.getLogger(__name__)


class KafkaProducerProtocol(Protocol):
    """Minimal protocol required from a Kafka producer."""

    async def start(self) -> None:
        """Start the producer."""

    async def stop(self) -> None:
        """Stop the producer."""

    async def send_and_wait(
        self,
        topic: str,
        value: bytes,
        key: bytes | None = None,
    ) -> object:
        """Publish a message and wait for broker acknowledgement."""


class KafkaUpdateSink(UpdateSink):
    """Publishes Telegram updates into Kafka as validated envelopes."""

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        client_id: str,
        required_acks: str,
        producer: KafkaProducerProtocol | None = None,
    ) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.client_id = client_id
        self.required_acks = required_acks
        self._producer = producer
        self._started = False

    async def start(self) -> None:
        """Start the Kafka producer if it is not started yet."""
        if self._started:
            return

        if self._producer is None:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=self.client_id,
                acks=self.required_acks,
            )

        await self._producer.start()
        self._started = True
        logger.info(
            "Kafka producer started: bootstrap_servers=%s topic=%s client_id=%s",
            self.bootstrap_servers,
            self.topic,
            self.client_id,
        )

    async def stop(self) -> None:
        """Stop the Kafka producer if it has been started."""
        if not self._started or self._producer is None:
            return

        await self._producer.stop()
        self._started = False
        logger.info("Kafka producer stopped: topic=%s client_id=%s", self.topic, self.client_id)

    async def handle(self, update: TelegramUpdate) -> None:
        """Serialize and publish a Telegram update to Kafka."""
        if not self._started or self._producer is None:
            raise RuntimeError("KafkaUpdateSink must be started before handle()")

        envelope = build_update_envelope(update)
        key = envelope.partition_key.encode("utf-8")
        value = json.dumps(
            envelope.model_dump(mode="json"),
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")

        try:
            await self._producer.send_and_wait(self.topic, value=value, key=key)
        except Exception:
            logger.exception(
                "Kafka publish failed: topic=%s update_id=%s partition_key=%s",
                self.topic,
                envelope.update_id,
                envelope.partition_key,
            )
            raise

        logger.debug(
            "Published Telegram update to Kafka: topic=%s update_id=%s partition_key=%s",
            self.topic,
            envelope.update_id,
            envelope.partition_key,
        )
