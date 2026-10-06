import json
import os

import aio_pika

RABBITMQ_URL = os.getenv("RABBITMQ_URL")
EXCHANGE_NAME = "jobs"

async def connect() -> aio_pika.abc.AbstractRobustConnection | None:
    if not RABBITMQ_URL:
        return None
    return await aio_pika.connect_robust(RABBITMQ_URL)

async def publish_status_change(connection , event : dict):
    async with connection.channel() as channel :
        exchange = await channel.declare_exchange(
            EXCHANGE_NAME , aio_pika.ExchangeType.TOPIC , durable = True
        )
        message = aio_pika.Message(
            body=json.dumps(event).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await exchange.publish(message, routing_key="job.status_changed")
