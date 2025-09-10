from tortoise.models import Model
from tortoise import fields
from enum import Enum


class EmailCategory(str, Enum):
    QUESTION = "question"
    REFUND = "refund"
    OTHER = "other"


class ImportanceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RefundStatus(str, Enum):
    REQUESTED = "requested"
    PROCESSING = "processing"
    COMPLETED = "completed"


class User(Model):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255, unique=True)
    gmail_token = fields.TextField()
    gmail_refresh_token = fields.TextField()
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"


class Order(Model):
    id = fields.IntField(pk=True)
    order_id = fields.CharField(max_length=100, unique=True)
    customer_email = fields.CharField(max_length=255)
    amount = fields.DecimalField(max_digits=10, decimal_places=2)
    status = fields.CharField(max_length=50, default="completed")
    refund_status = fields.CharEnumField(RefundStatus, null=True)
    refund_requested_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "orders"


class Email(Model):
    id = fields.IntField(pk=True)
    gmail_message_id = fields.CharField(max_length=255, unique=True)
    user = fields.ForeignKeyField("models.User", related_name="emails")
    sender_email = fields.CharField(max_length=255)
    subject = fields.TextField()
    body = fields.TextField()
    category = fields.CharEnumField(EmailCategory)
    processed_at = fields.DatetimeField(auto_now_add=True)
    response_sent = fields.BooleanField(default=False)

    class Meta:
        table = "emails"


class UnhandledEmail(Model):
    id = fields.IntField(pk=True)
    email = fields.ForeignKeyField("models.Email", related_name="unhandled")
    importance_level = fields.CharEnumField(ImportanceLevel, default=ImportanceLevel.MEDIUM)
    reason = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "unhandled_emails"


class RefundRequest(Model):
    id = fields.IntField(pk=True)
    email = fields.ForeignKeyField("models.Email", related_name="refund_requests")
    order = fields.ForeignKeyField("models.Order", related_name="refund_requests", null=True)
    customer_email = fields.CharField(max_length=255)
    requested_order_id = fields.CharField(max_length=100, null=True)
    status = fields.CharField(max_length=50, default="pending")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "refund_requests"


class NotFoundRefundRequest(Model):
    id = fields.IntField(pk=True)
    customer_email = fields.CharField(max_length=255)
    invalid_order_id = fields.CharField(max_length=100, null=True)
    email_content = fields.TextField()
    attempt_count = fields.IntField(default=1)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "not_found_refund_requests"


class KnowledgeBase(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255)
    content = fields.TextField()
    embedding_id = fields.CharField(max_length=255, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "knowledge_base"