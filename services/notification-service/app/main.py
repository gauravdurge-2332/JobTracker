import asyncio
import json
import os
import smtplib
import ssl
from email.message import EmailMessage

import aio_pika

RABBITMQ_URL = os.environ["RABBITMQ_URL"]
SMTP_HOST = os.environ["SMTP_HOST"]
SMTP_PORT = int(os.environ["SMTP_PORT"])
SMTP_USER = os.environ["SMTP_USER"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]
EXCHANGE_NAME = "jobs"
QUEUE_NAME = "notification"

def send_Email(event : dict) ->None :
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = event["email"]
    msg["Subject"] = (
        f"Your {event['company']} application moved to {event['new_status']}"
    )
    msg.set_content(
        f"Hi,\n\n"
        f"Your application for {event['role']} at {event['company']} "
        f"changed from {event['old_status']} to {event['new_status']}.\n\n"
        f"Good luck!\n"
    )
    
    with smtplib.SMTP(SMTP_HOST , SMTP_PORT , timeout=15) as smtp : 
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(SMTP_USER , SMTP_PASSWORD)
        smtp.send_message(msg)
    

async def handle(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        event = json.loads(message.body)
        await asyncio.to_thread(send_Email, event)
        print(f"Email sent to {event['email']} for {event['company']}", flush=True)

        
        



async def main() -> None:
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    await queue.bind(exchange , routing_key="job.status_changed")
    await queue.consume(handle)
    print("Notification worker ready: consuming job.status_changed", flush=True)
    await asyncio.Future()  # keeps the program alive forever


if __name__ == "__main__":
    asyncio.run(main())
