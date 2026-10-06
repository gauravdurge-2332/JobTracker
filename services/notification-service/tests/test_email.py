import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch


class EmailTests(unittest.TestCase):
    def test_authenticated_sender_recipient_and_tls(self):
        environment = {
            "RABBITMQ_URL": "amqp://localhost/",
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "sender@example.com",
            "SMTP_PASSWORD": "test-only",
        }
        source = Path(__file__).resolve().parents[1] / "app" / "main.py"
        spec = importlib.util.spec_from_file_location("notification_main", source)
        worker = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, environment):
            spec.loader.exec_module(worker)
        with patch.object(worker.smtplib, "SMTP") as smtp_factory:
            smtp = smtp_factory.return_value.__enter__.return_value
            worker.send_Email({
                "email": "recipient@example.com",
                "company": "Example",
                "role": "Engineer",
                "old_status": "Applied",
                "new_status": "interview",
            })
            message = smtp.send_message.call_args.args[0]
            self.assertEqual(message["From"], "sender@example.com")
            self.assertEqual(message["To"], "recipient@example.com")
            self.assertIn("interview", message["Subject"])
            smtp.login.assert_called_once_with("sender@example.com", "test-only")
            context = smtp.starttls.call_args.kwargs["context"]
            self.assertTrue(context.check_hostname)


if __name__ == "__main__":
    unittest.main()
