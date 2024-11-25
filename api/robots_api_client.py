import logging
from typing import List, Dict, Any, Optional
import aiohttp

from .model.register_device_request import RegisterDeviceRequest
from .model.register_device_response import RegisterDeviceResponse
from .model.robot_map_zones import CleaningTracksResponse
from .model.robot_response import RobotResponse
from .model.cleaning_modes_response import CleaningModesResponse
from .model.robot_map_response import RobotMapResponse
from .model.cleaning_show_response import CleaningShowResponse
from .model.cleaning_start_request import CleaningStartRequest

class RobotsApiClient:
  def __init__(self, session: aiohttp.ClientSession, token: str, host: str):
    self._session = session
    self._token = token
    self._host = host
    self._logger = logging.getLogger(__name__)


  async def register_device(self) -> RegisterDeviceResponse:
    url = f"{self._host}/mobile_devices"
    payload = RegisterDeviceRequest().to_dict()
    response = await self._make_request("POST", url, json=payload)
    return RegisterDeviceResponse(**response)

  async def get_user_robots(self) -> List[RobotResponse]:
    url = f"{self._host}/users/me/robots"
    response = await self._make_request("GET", url)
    return [RobotResponse(**robot) for robot in response]

  async def get_cleaning_modes(self, robot_id: str) -> CleaningModesResponse:
    url = f"{self._host}/robots/{robot_id}/features"
    response = await self._make_request("GET", url)
    return CleaningModesResponse(**response)

  async def get_robot_maps(self, robot_id: str) -> List[RobotMapResponse]:
    url = f"{self._host}/robots/{robot_id}/floorplans?sort_by=promoted_at&sort_order=asc"
    response = await self._make_request("GET", url)
    return [RobotMapResponse(**map_data) for map_data in response]

  async def get_recent_cleaning_maps(self, robot_id: str) -> List[Dict[str, Any]]:
    url = f"{self._host}/robots/{robot_id}/cleaningmaps?cleaning_types[]=persistent"
    response = await self._make_request("GET", url)
    return response

  async def get_zones_by_floor_plan(self, floorplan_uuid: str) -> List[CleaningTracksResponse]:
    url = f"{self._host}/maps/floorplans/{floorplan_uuid}/tracks"
    response = await self._make_request("GET", url)
    return [CleaningTracksResponse(**zone) for zone in response]

  async def start_cleaning(self, robot_id: str, cleaning_request: CleaningStartRequest) -> str:
    url = f"{self._host}/robots/{robot_id}/cleaning/v2"
    headers = {
      "mobile-app-version": "3.9.0",
      "mobile-app-build": "37883",
      "mobile-app-os": "android",
      "mobile-app-os-version": "11",
    }
    payload = cleaning_request.to_dict()  # Assuming you have a method to convert dataclass to dict
    response = await self._make_request("POST", url, json=payload, additional_headers=headers)
    return response

  async def send_to_base(self, serial_robot_id: str) -> str:
    return await self._send_message_to_robot(serial_robot_id, "navigation.return_to_base")

  async def pause_cleaning(self, serial_robot_id: str) -> str:
    return await self._send_message_to_robot(serial_robot_id, "cleaning.pause")

  async def show_cleaning(self, serial_robot_id: str) -> CleaningShowResponse:
    response = await self._send_message_to_robot(serial_robot_id, "cleaning.show")
    return CleaningShowResponse(**response)

  async def resume_clean(self, serial_robot_id: str) -> str:
    return await self._send_message_to_robot(serial_robot_id, "cleaning.resume")

  async def find_me(self, serial_robot_id: str) -> str:
    return await self._send_message_to_robot(serial_robot_id, "utilities.find_me")

  async def _send_message_to_robot(self, robot_id: str, ability: str) -> Any:
    url = f"{self._host}/vendors/3/robots/{robot_id}/messages"
    payload = {"ability": ability}
    response = await self._make_request("POST", url, json=payload)
    return response



  async def _make_request(
      self,
      method: str,
      url: str,
      json: Optional[Dict[str, Any]] = None,
      additional_headers: Optional[Dict[str, str]] = None,
  ) -> Any:
    headers = self._create_headers()
    if additional_headers:
      headers.update(additional_headers)

    # Log del body enviado
    self._logger.debug("Making %s request to %s with body: %s and headers %s", method, url, json, headers)

    async with self._session.request(method, url, json=json, headers=headers) as response:
      if response.status == 200:
        response_json = await response.json()  # Resuelve el JSON de la respuesta
        self._logger.debug("Received response: %s. Response: %s",  response, response_json)
        return response_json
      else:
        error_text = await response.text()
        self._logger.error("Request failed: %s %s", response.status, error_text)
        raise Exception(f"Request failed: {response.status} {error_text}")

  def _create_headers(self) -> Dict[str, str]:
    return {
      "Authorization": f"Auth0Bearer {self._token}",
      "accept": "application/vnd.neato.orbital-http.v1+json",
      "user-agent": "okhttp/4.12.0",
      "Content-Type": "application/json",
    }