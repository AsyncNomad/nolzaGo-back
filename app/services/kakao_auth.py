import httpx


class KakaoOAuthClient:
    BASE_URL = "https://kapi.kakao.com"

    async def verify_access_token(self, access_token: str) -> dict | None:
        """
        카카오 액세스 토큰을 /v2/user/me 호출로 검증.
        유효하면 프로필 JSON, 실패하면 None 반환.
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        url = f"{self.BASE_URL}/v2/user/me"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    return None
                return resp.json()
        except Exception:
            return None
