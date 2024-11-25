import logging

class UserDataServiceException(Exception):
  pass

class UserDataService:
  def __init__(self, user_api_client):
    self.user_api_client = user_api_client
    self._logger = logging.getLogger(__name__)

  async def send_otp_mail(self, username: str):
    await self._execute(
        self.user_api_client.request_otp(username),
        "Sending OTP mail to user %s",
        username,
        f"Failed to send OTP mail for user: {username}",
    )

  async def validate_otp(self, username: str, otp: str):
    return await self._execute(
        self.user_api_client.validate_otp(username, otp),
        "Validating OTP for user %s",
        username,
        f"Failed to validate OTP for user: {username}",
    )

  async def _execute(
      self, coroutine, log_message: str, identifier: str, error_message: str
  ):
    try:
      self._logger.info(log_message, identifier)
      result = await coroutine
      return result
    except Exception as e:
      self._logger.error("Error " + log_message, identifier, exc_info=True)
      raise UserDataServiceException(error_message) from e