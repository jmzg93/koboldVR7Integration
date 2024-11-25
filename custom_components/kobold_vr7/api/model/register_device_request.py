from dataclasses import dataclass, asdict
from uuid import uuid4


@dataclass
class RegisterDeviceRequest:
  app_version: str = "3.9.0"
  device_id: str = str(uuid4())  # Genera un UUID automáticamente
  locale: str = "es"
  notification_token: str = "dUpdkdKaS6u5wptzZkTVH6:APA91bFkznZLRKgzDOi8qnw_ehqtdE82kZ7IwG3TFa7yvrTsVnkYUGKhccQ_ki0xlbQ_YT4kK1cVhiYSGU16jYAApEpF1pQzR7LfaA1eK7HITz4I2BDfrSM"
  platform: str = "android"
  version: str = "11"

  def to_dict(self) -> dict:
    """Convierte la clase RegisterDeviceRequest en un diccionario."""
    return asdict(self)
