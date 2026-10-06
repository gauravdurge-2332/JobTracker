# RabbitMQ and notification deployment

This extends the already deployed auth/jobs application. No additional AWS IAM
permissions are needed: notifications use RabbitMQ and SMTP, not AWS APIs.
The production Compose file now includes all five containers: postgres,
auth-service, jobs-service, rabbitmq and notification-service.

## Prepare locally

Commit and push these changes to main so CI publishes the updated notification
image. Wait for the notification publish job to succeed before pulling on EC2.
The current workflow already builds and publishes this service.

Copy the updated `docker-compose.prod.yml` and `rabbitmq.prod.conf` to
`~/jobtracker/` on EC2 using your existing SSH/SCP connection. Preserve any working
server-specific auth image/URL values. Do not replace the server's `.env` with
the development `.env`, and do not delete either named volume.

## Server environment

Edit the protected server `.env` privately. Keep its existing Postgres/JWT/region
values and add these keys (replace each descriptive placeholder yourself):

```dotenv
RABBITMQ_PASSWORD=<new URL-safe password>
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<your sending Gmail address>
SMTP_PASSWORD=<new Gmail app password without spaces>
```

Generate a RabbitMQ password on the server with `openssl rand -hex 24` and copy
the output privately into `.env`. Hex avoids special characters that need URL
encoding in the AMQP URL. Never use the guest account for container connections.
The Compose file sets RabbitMQ's username to `jobtracker` and builds the same
AMQP URL for jobs and the worker.

For Gmail, enable 2-Step Verification and create an app password at
https://myaccount.google.com/apppasswords. Revoke the app password previously
exposed in chat and use a new one. A normal Google account password will not
work for this setup. App passwords may be unavailable for some managed accounts;
use an approved SMTP provider in that case. Change SMTP_HOST/SMTP_PORT if using
another provider that supports STARTTLS. This worker expects STARTTLS (typically
587), not implicit TLS on port 465.
See [Google app password help](https://support.google.com/mail/answer/185833).

```bash
cd ~/jobtracker
chmod 600 .env
free -h
docker stats --no-stream
docker compose -f docker-compose.prod.yml config --quiet
```

Expect the Compose validation to exit successfully with no output. Use
`--quiet`: normal `config` output contains resolved secrets. The container limits
total 1152 MiB, above this instance's 1 GiB RAM; the existing 2 GiB swap provides
headroom but can cause slower responses. Check actual usage, swap and OOM events.
Limits are ceilings, not reservations. If workloads exceed capacity, increase
instance memory rather than continually increasing limits on this small host.

## Start in order

1. Start RabbitMQ and the worker while the current jobs container keeps running:
   ```bash
   docker compose -f docker-compose.prod.yml pull rabbitmq notification-service
   docker compose -f docker-compose.prod.yml up -d rabbitmq notification-service
   docker compose -f docker-compose.prod.yml ps
   docker compose -f docker-compose.prod.yml logs --tail=60 rabbitmq notification-service
   ```
   RabbitMQ should become healthy. The worker must print
   `Notification worker ready: consuming job.status_changed` without a traceback.
   Wait for that line before generating status-change events.
2. Check SMTP login without sending email:
   ```bash
   docker compose -f docker-compose.prod.yml exec -T notification-service python -c 'import os,smtplib,ssl; s=smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"]), timeout=15); s.starttls(context=ssl.create_default_context()); s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"]); s.quit(); print("SMTP login OK")'
   ```
   Expected: `SMTP login OK`. This does not expose passwords or send a message.
3. Enable publishing in jobs by recreating it with the new environment:
   ```bash
   docker compose -f docker-compose.prod.yml pull jobs-service
   docker compose -f docker-compose.prod.yml up -d --force-recreate jobs-service
   docker compose -f docker-compose.prod.yml logs --tail=50 jobs-service
   ```
   Expected: application startup complete on 8001. No restart of Postgres or
   auth-service is required when those services are already running unchanged.

Do not run `docker compose down -v`: that would delete persistent data.
RabbitMQ credentials configured via RABBITMQ_DEFAULT_USER/PASS are initialized
on a new database. Changing the env password later does not rotate an existing
broker user; use RabbitMQ's user administration and update both clients together.
See [official RabbitMQ image](https://hub.docker.com/_/rabbitmq).

## End-to-end test

Keep the existing SSH tunnel open and use the Swagger pages:

1. Log in on http://localhost:8002/docs using an account with a real email inbox
   you control. Events use that account's email address, not SMTP_USER.
2. Authorize http://localhost:8001/docs with the returned token.
3. Create a job with status `Applied`, or use an existing job.
4. Use PUT `/jobs/{job_id}` with the same company/role and change status to
   `interview`. Example body:
   ```json
   {"company":"Example","role":"Backend Engineer","status":"interview","note":"notification test"}
   ```
   Expect HTTP 200. Creating a job alone does not send an email; only a changed
   status on update triggers the event. Repeating the same status does not send
   another event.
5. On EC2:
   ```bash
   docker compose -f docker-compose.prod.yml logs --tail=50 notification-service
   docker compose -f docker-compose.prod.yml exec -T rabbitmq rabbitmqctl list_queues name messages_ready messages_unacknowledged consumers
   docker compose -f docker-compose.prod.yml ps
   docker stats --no-stream
   ```
   Expect an `Email sent to ...` log and email in the user's inbox (check spam).
   The `notification` queue should have one consumer and drain to zero ready and
   unacknowledged messages. All five containers should remain running, RabbitMQ
   and postgres healthy.

RabbitMQ persists its database to `rabbitmq-data`; the exchange and queue are
durable, and publisher messages are persistent. The queue must exist before
events are published: an exchange alone cannot retain messages for a missing
queue. This deployment is suitable for a small demonstration workload, but the
current worker rejects failed sends without retry/dead-letter handling. Failed
SMTP messages need a fresh status change after fixing the cause; do not assume
automatic replay or guaranteed delivery.

## Troubleshooting

| Symptom | Action |
|---|---|
| RabbitMQ unhealthy / restarts | Inspect RabbitMQ logs, `free -h`, swap and `docker stats`. Check `sudo dmesg -T` for OOM kills. Ensure rabbitmq.prod.conf is a file in ~/jobtracker and contains the supplied settings. |
| AMQP authentication failure | Both clients must use the same URL-safe password as the broker's initialized jobtracker user. Check if the volume was previously initialized with different credentials. Do not delete data to reset credentials. |
| SMTPAuthenticationError / 535 | Use a fresh Gmail app password without display spaces and the correct SMTP_USER. Confirm 2-Step Verification. |
| SMTP timeout | Check DNS and outbound connectivity to the SMTP host on 587. This does not require an inbound SMTP port. |
| No notification | Use a real signup email, change the job status, check worker readiness and logs, verify queue consumer count, then check spam. Old changes made before the queue existed cannot be replayed. |
| Jobs update returns 200 but no email | Sending is asynchronous. A successful job update does not prove SMTP delivery; inspect the worker's logs and inbox. |
| Worker restarts or memory alarm blocks publishing | Inspect memory usage and logs. The absolute RabbitMQ watermark is 192 MiB with a 384 MiB hard container limit; adjust only with available server capacity. |

RabbitMQ has no published host ports in this configuration. Applications reach
it via `rabbitmq:5672` on the Compose network. The existing SSH tunnel continues
to provide API browser access. A public domain, HTTPS, automated deployment,
email retry handling and monitoring remain separate work.
See [RabbitMQ memory guidance](https://www.rabbitmq.com/docs/memory).
