from fastapi import APIRouter, Depends, HTTPException

from app.services.kakao_map import KakaoMapClient, get_kakao_map_client

router = APIRouter(prefix="/maps", tags=["maps"])


@router.get("/geocode")
async def geocode_address(query: str, kakao_map: KakaoMapClient = Depends(get_kakao_map_client)):
    """
    카카오 지도 REST API를 사용해 주소를 좌표로 변환합니다.
    """
    data = await kakao_map.geocode(query)
    if not data.get("documents"):
        raise HTTPException(status_code=404, detail="No results")
    return data
