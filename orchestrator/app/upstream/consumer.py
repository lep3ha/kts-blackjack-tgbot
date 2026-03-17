import logging
from contextlib import suppress
from typing import Awaitable
from typing import Callable

from aiokafka import AIOKafkaConsumer
from aiokafka.structs import ConsumerRecord
from pydantic import ValidationError

from app.core.config import Settings
from app.upstream.models import TelegramUpdateEnvelope


logger = logging.getLogger(__name__)


class KafkaUpdatesConsumer:
    def __init__(
        self,
        settings: Settings,
        *,
        envelope_handler: Callable[[TelegramUpdateEnvelope], Awaitable[None]] | None = None,
    ) -> None:
        self._settings = settings
        self._started = False
        self._envelope_handler = envelope_handler
        self._consumer = AIOKafkaConsumer(
            settings.kafka_topic_updates,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_group_id,
            client_id=settings.kafka_client_id,
            auto_offset_reset=settings.kafka_auto_offset_reset,
        )

    async def start(self) -> None:
        logger.info(
            "Starting Kafka consumer topic=%s group_id=%s bootstrap_servers=%s",
            self._settings.kafka_topic_updates,
            self._settings.kafka_group_id,
            self._settings.kafka_bootstrap_servers,
        )
        try:
            await self._consumer.start()
        except Exception:
            with suppress(Exception):
                await self._consumer.stop()
            raise

        self._started = True
        logger.info("Kafka consumer started")

    async def stop(self) -> None:
        if not self._started:
            return

        logger.info("Stopping Kafka consumer")
        await self._consumer.stop()
        self._started = False
        logger.info("Kafka consumer stopped")

    async def consume_forever(self) -> None:
        async for message in self._consumer:
            await self._handle_message(message)

    async def _handle_message(self, message: ConsumerRecord) -> None:
        try:
            envelope = TelegramUpdateEnvelope.model_validate_json(message.value)
        except ValidationError:
            self._log_invalid_message(message)
            return

        self._log_envelope(message, envelope)
        if self._envelope_handler is None:
            return

        try:
            await self._envelope_handler(envelope)
        except Exception:
            logger.exception("Envelope handler failed update_id=%s", envelope.update_id)

    @staticmethod
    def _log_envelope(
        message: ConsumerRecord,
        envelope: TelegramUpdateEnvelope,
    ) -> None:
        key_preview = message.key.decode("utf-8", errors="replace") if message.key else None
        logger.info(
            "Kafka envelope received topic=%s partition=%s offset=%s timestamp=%s key=%s update_id=%s update_type=%s source_key=%s partition_key=%s",
            message.topic,
            message.partition,
            message.offset,
            message.timestamp,
            key_preview,
            envelope.update_id,
            envelope.update_type,
            envelope.source_key,
            envelope.partition_key,
        )
        logger.info("Envelope payload:\n%s", envelope.model_dump_json(indent=2))

    @staticmethod
    def _log_invalid_message(message: ConsumerRecord) -> None:
        key_preview = message.key.decode("utf-8", errors="replace") if message.key else None
        raw_preview = message.value.decode("utf-8", errors="replace")
        logger.exception(
            "Invalid Kafka message topic=%s partition=%s offset=%s key=%s raw_value=%s",
            message.topic,
            message.partition,
            message.offset,
            key_preview,
            raw_preview,
        )