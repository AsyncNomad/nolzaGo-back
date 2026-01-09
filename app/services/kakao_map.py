from typing import Any, Dict, Optional

import httpx

from app.core.config import get_settings


class KakaoMapClient:
    def __init__(self, rest_api_key: Optional[str]):
        self.rest_api_key = rest_api_key
        self.enabled = bool(rest_api_key)
        self.base_url = "https://dapi.kakao.com"

    async def geocode(self, query: str) -> Dict[str, Any]:
        """
        주소 → 좌표. 카카오 REST API 키가 없으면 빈 결과 반환.
        """
        if not self.enabled:
            return {"documents": []}
        url = f"{self.base_url}/v2/local/search/address.json"
        headers = {"Authorization": f"KakaoAK {self.rest_api_key}"}
        params = {"query": query}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()


def get_kakao_map_client() -> KakaoMapClient:
    settings = get_settings()
    return KakaoMapClient(settings.kakao_map_rest_api_key or settings.kakao_rest_api_key)
