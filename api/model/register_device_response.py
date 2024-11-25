from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RegisterDeviceResponse:
  app_version: str
  device_id: str
  id: str
  inserted_at: datetime
  locale: str
  notification_token: str
  platform: str
  updated_at: datetime
  user_id: str
  version: str