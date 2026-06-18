from django.db import models
from django.contrib.auth.models import User


class FocusSession(models.Model):
    STATUS_RUNNING = "running"
    STATUS_PAUSED = "paused"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_RUNNING, "进行中"),
        (STATUS_PAUSED, "已暂停"),
        (STATUS_COMPLETED, "已完成"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="focus_sessions", db_index=True)
    title = models.CharField(max_length=200, blank=True, default="专注会话")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RUNNING, db_index=True)
    speed_rate = models.FloatField(default=10.0, help_text="虚拟时间倍速系数，如 10 表示 1:10")

    start_real_timestamp = models.FloatField(help_text="任务开始时的真实 Unix 时间戳")
    last_pause_real_timestamp = models.FloatField(null=True, blank=True, help_text="上次暂停时的真实时间戳")

    accumulated_virtual_seconds = models.FloatField(default=0.0, help_text="已累积的虚拟秒数（暂停前累计）")
    total_planned_virtual_seconds = models.FloatField(default=3600.0, help_text="计划的虚拟总时长（秒）")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["start_real_timestamp"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.status}] {self.title} (x{self.speed_rate})"
