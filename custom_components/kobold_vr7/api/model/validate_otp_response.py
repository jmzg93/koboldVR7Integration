from dataclasses import dataclass

@dataclass
class ValidateOtpResponse:
  access_token: str
  expires_in: int
  id_token: str
  scope: str
  token_type: str